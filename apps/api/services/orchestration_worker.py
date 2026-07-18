"""Standalone Worker process — direct PostgreSQL, no HTTP loopback.

Sprint 005 Slice B — Data Orchestration Worker.
"""

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.services.orchestration_repository import (
    HEARTBEAT_INTERVAL_SECONDS,
    acquire_lease,
    advance_next_run_at,
    claim_due_schedules,
    complete_attempt,
    complete_run,
    create_attempt,
    create_run,
    finalize_run,
    recover_stale_runs,
    release_lease,
    start_attempt,
    start_run,
)
from apps.api.services.orchestration_scheduling import (
    compute_idempotency_key,
    compute_next_daily_run,
    validate_job_params,
)

logger = logging.getLogger("orchestration.worker")

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Guardian executor (no HTTP — imports Guardian service directly)
# ---------------------------------------------------------------------------


class GuardianExecutor:
    """Executes Guardian evaluation jobs directly (not via HTTP)."""

    @staticmethod
    def evaluate_all(
        session: Session,
        household_id: str,
        *,
        clock: Clock = _utc_now,
    ) -> dict:
        """Run evaluate_all for a household. Returns result dict."""
        from datetime import date as _date

        from apps.api.services.guardian import evaluate_all_checks
        try:
            result = evaluate_all_checks(
                session,
                household_id=UUID(household_id),
                as_of_date=_date.today(),
            )
            return {"status": "completed", "result": result}
        except Exception as exc:
            logger.exception("guardian.evaluate_all failed for household %s", household_id)
            return {"status": "failed", "error": str(exc)[:500]}

    @staticmethod
    def evaluate_one(
        session: Session,
        household_id: str,
        check_id: str,
        *,
        clock: Clock = _utc_now,
    ) -> dict:
        """Run evaluate_one for a specific check."""
        from datetime import date as _date

        from apps.api.services.guardian import evaluate_one_check
        try:
            result = evaluate_one_check(
                session,
                check_id=UUID(check_id),
                household_id=UUID(household_id),
                as_of_date=_date.today(),
            )
            return {"status": "completed", "result": result}
        except Exception as exc:
            logger.exception(
                "guardian.evaluate_one failed for check %s", check_id
            )
            return {"status": "failed", "error": str(exc)[:500]}


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class OrchestrationWorker:
    """Standalone Worker that polls schedules and executes jobs.

    Direct PostgreSQL connection — no HTTP loopback.
    Graceful shutdown via SIGTERM/SIGINT.
    """

    def __init__(
        self,
        database_url: str,
        *,
        worker_id: str | None = None,
        clock: Clock = _utc_now,
        poll_interval: float = 5.0,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        executor: GuardianExecutor | None = None,
    ):
        self.database_url = database_url
        self.worker_id = worker_id or str(uuid4())
        self._clock = clock
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.executor = executor or GuardianExecutor()

        self._shutdown_flag = threading.Event()
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    # ── Lifecycle ──

    def start(self) -> None:
        """Run the main worker loop. Blocks until shutdown."""
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("Worker %s starting (poll=%.1fs)", self.worker_id, self.poll_interval)

        self._recover_on_startup()

        while not self._shutdown_flag.is_set():
            try:
                claimed = self._claim_and_execute()
                if claimed == 0:
                    self._shutdown_flag.wait(timeout=self.poll_interval)
            except Exception:
                logger.exception("Worker loop error")
                self._shutdown_flag.wait(timeout=self.poll_interval)

        self._graceful_shutdown()
        logger.info("Worker %s stopped", self.worker_id)

    def stop(self) -> None:
        """Signal the worker to stop gracefully."""
        self._shutdown_flag.set()

    # ── Recovery ──

    def _recover_on_startup(self) -> None:
        """On restart, recover stale runs from PostgreSQL state."""
        with self._session_factory() as session:
            try:
                stale = recover_stale_runs(session, clock=self._clock)
                for r in stale:
                    self._abort_stale_run(session, r)
                session.commit()
                if stale:
                    logger.info("Recovered %d stale runs", len(stale))
            except Exception:
                logger.exception("Recovery failed")

    def _abort_stale_run(self, session: Session, stale: dict) -> None:
        """Abort a stale run with expired lease."""
        complete_run(session, stale["run_id"], "aborted", clock=self._clock)
        logger.info("Aborted stale run %s", stale["run_id"])

    # ── Claim + execute ──

    def _claim_and_execute(self) -> int:
        """Claim due schedules and execute them. Returns count claimed."""
        with self._session_factory() as session:
            try:
                due = claim_due_schedules(session, clock=self._clock)
                if not due:
                    session.rollback()
                    return 0

                claimed_count = 0
                for item in due:
                    try:
                        self._execute_scheduled(session, item)
                        claimed_count += 1
                    except Exception:
                        logger.exception("Failed to claim schedule %s", item["schedule_id"])
                        session.rollback()
                        continue

                session.commit()
                return claimed_count

            except Exception:
                session.rollback()
                raise

    def _execute_scheduled(self, session: Session, schedule_info: dict) -> None:
        """Execute one due schedule: claim → run → attempt → execute → finalize."""
        job_type = schedule_info["job_type"]
        job_params = schedule_info["job_params"]
        household_id = schedule_info["household_id"]
        schedule_id = schedule_info["schedule_id"]
        job_def_id = schedule_info["job_definition_id"]

        # Validate job type
        validate_job_params(job_type, job_params)

        # Compute idempotency key
        now = self._clock()
        ikey = compute_idempotency_key(job_type, job_params, now.date())

        # Create run
        try:
            run_id = create_run(
                session,
                job_definition_id=job_def_id,
                schedule_id=schedule_id,
                idempotency_key=ikey,
                status="pending",
                triggered_by="schedule",
                scheduled_at=now,
                household_id=household_id,
                clock=self._clock,
            )
        except Exception:
            # Idempotency or overlap conflict — already claimed
            logger.debug("Run already claimed for schedule %s", schedule_id)
            return

        # Advance next_run_at
        new_next = compute_next_daily_run(
            schedule_info["execution_time"],
            schedule_info["timezone"],
            after=now,
            clock=self._clock,
        )
        advance_next_run_at(session, schedule_id, new_next, clock=self._clock)

        # Create attempt
        aid = create_attempt(session, run_id=run_id, attempt_number=1, clock=self._clock)

        # Start run + attempt
        start_run(session, run_id, clock=self._clock)
        start_attempt(session, aid, clock=self._clock)

        # Acquire lease
        lease = acquire_lease(session, run_id=run_id, worker_id=self.worker_id, clock=self._clock)

        # Execute the job
        try:
            result = self._execute_job(session, job_type, job_params, household_id)

            # Finalize (token-gated)
            finalize_result = finalize_run(
                session,
                run_id=run_id,
                lease_id=lease["lease_id"],
                worker_id=self.worker_id,
                fencing_token=lease["fencing_token"],
                status=result["status"],
                clock=self._clock,
            )
            if finalize_result == 0:
                logger.warning("Finalize failed — stale token for run %s", run_id)
                return

            attempt_status = "succeeded" if result["status"] == "completed" else "failed"
            complete_attempt(
                session,
                aid,
                attempt_status,
                error_message=result.get("error"),
                clock=self._clock,
            )

            # Release lease
            release_lease(
                session,
                lease_id=lease["lease_id"],
                worker_id=self.worker_id,
                fencing_token=lease["fencing_token"],
                clock=self._clock,
            )

        except Exception as exc:
            logger.exception("Job execution failed for run %s", run_id)
            err_msg = str(exc)[:500]
            complete_attempt(session, aid, "failed", error_message=err_msg, clock=self._clock)
            finalize_run(
                session,
                run_id=run_id,
                lease_id=lease["lease_id"],
                worker_id=self.worker_id,
                fencing_token=lease["fencing_token"],
                status="failed",
                clock=self._clock,
            )
            try:
                release_lease(
                    session,
                    lease_id=lease["lease_id"],
                    worker_id=self.worker_id,
                    fencing_token=lease["fencing_token"],
                    clock=self._clock,
                )
            except Exception:
                pass

    # ── Job execution dispatcher ──

    def _execute_job(
        self,
        session: Session,
        job_type: str,
        job_params: dict,
        household_id: str,
    ) -> dict:
        """Dispatch to the appropriate executor based on job_type."""
        if job_type == "guardian.evaluate_all":
            return self.executor.evaluate_all(session, household_id, clock=self._clock)
        elif job_type == "guardian.evaluate_one":
            check_id = job_params["check_id"]
            return self.executor.evaluate_one(
                session, household_id, check_id, clock=self._clock
            )
        else:
            return {"status": "failed", "error": f"Unknown job type: {job_type}"}

    # ── Graceful shutdown ──

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("Received signal %d, initiating graceful shutdown", signum)
        self.stop()

    def _graceful_shutdown(self) -> None:
        """Stop claiming new work, wait for in-flight work (max 30s)."""
        logger.info("Graceful shutdown — no new claims")
        # In-flight work is handled within the loop's transaction boundary.
        # After the loop exits, any uncommitted work is rolled back.
        # The _shutdown_flag prevents new claims.
        self._engine.dispose()
