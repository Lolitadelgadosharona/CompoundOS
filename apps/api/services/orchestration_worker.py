"""Standalone Worker — timeout enforcement, stale recovery, graceful shutdown.

Sprint 005 Slice B — Worker reliability corrective closure.
"""

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from apps.api.services.orchestration_executor import (
    TimeoutJobExecutor,
)
from apps.api.services.orchestration_repository import (
    GRACEFUL_SHUTDOWN_SECONDS,
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
# Stale-run reaper
# ---------------------------------------------------------------------------


class StaleRunReaper:
    """Recovers stale runs on startup and periodically.

    Uses atomic claim to avoid double-recovery.
    """

    def __init__(self, clock: Clock = _utc_now):
        self._clock = clock

    def recover(self, session: Session) -> int:
        """Recover stale runs. Returns count recovered."""
        stale = recover_stale_runs(session, clock=self._clock)
        count = 0
        for r in stale:
            if self._abort_one(session, r):
                count += 1
        if count:
            logger.info("Reaper: recovered %d stale runs", count)
        return count

    def _abort_one(self, session: Session, stale: dict) -> bool:
        """Atomically abort one stale run. Returns True if aborted."""
        row = session.execute(
            text("SELECT status FROM runs WHERE id = :id FOR UPDATE"),
            {"id": stale["run_id"]},
        ).fetchone()
        if not row or row[0] != "running":
            return False

        complete_run(session, stale["run_id"], "aborted", clock=self._clock)
        release_lease(
            session,
            lease_id=stale["lease_id"],
            worker_id=stale["worker_id"],
            fencing_token=stale["fencing_token"],
            clock=self._clock,
        )
        logger.info("Aborted stale run %s", stale["run_id"])
        return True


# ---------------------------------------------------------------------------
# Orchestration Worker (reliability-hardened)
# ---------------------------------------------------------------------------


class OrchestrationWorker:
    """Standalone Worker with timeout enforcement and graceful shutdown."""

    def __init__(
        self,
        database_url: str,
        *,
        worker_id: str | None = None,
        clock: Clock = _utc_now,
        poll_interval: float = 5.0,
        executor: Any = None,  # TimeoutJobExecutor or FakeJobExecutor
        reaper: StaleRunReaper | None = None,
    ):
        self.database_url = database_url
        self.worker_id = worker_id or str(uuid4())
        self._clock = clock
        self.poll_interval = poll_interval
        self._executor = executor or TimeoutJobExecutor(database_url)
        self._reaper = reaper or StaleRunReaper(clock=self._clock)

        self._shutdown_flag = threading.Event()
        self._engine = create_engine(database_url, pool_pre_ping=True)
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    # ── Lifecycle ──

    def start(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        logger.info("Worker %s starting", self.worker_id)
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
        self._shutdown_flag.set()

    # ── Recovery ──

    def _recover_on_startup(self) -> None:
        with self._session_factory() as session:
            try:
                self._reaper.recover(session)
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("Recovery failed")

    # ── Claim + execute ──

    def _claim_and_execute(self) -> int:
        due = []
        with self._session_factory() as session:
            try:
                due = claim_due_schedules(session, clock=self._clock)
                session.commit()
            except Exception:
                session.rollback()
                return 0

        if not due:
            return 0

        claimed = 0
        for item in due:
            if self._shutdown_flag.is_set():
                break
            guardian_result = None
            try:
                with self._session_factory() as session:
                    guardian_result = self._execute_scheduled(session, item)
                    session.commit()
                claimed += 1
                # Dispatch Guardian notification after business commit
                self._maybe_notify_guardian_worker(guardian_result, item)
                # Dispatch Automation notification if run failed
                self._maybe_notify_automation_worker(guardian_result)
            except Exception:
                logger.exception("Failed schedule %s", item["schedule_id"])
        return claimed

    def _execute_scheduled(self, session: Session, schedule_info: dict) -> dict | None:
        job_type = schedule_info["job_type"]
        job_params = schedule_info["job_params"]
        household_id = schedule_info["household_id"]
        schedule_id = schedule_info["schedule_id"]
        job_def_id = schedule_info["job_definition_id"]

        validate_job_params(job_type, job_params)

        now = self._clock()
        ikey = compute_idempotency_key(job_type, job_params, now.date())

        from sqlalchemy.exc import IntegrityError
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
            )
        except IntegrityError:
            logger.debug("Run already claimed for schedule %s", schedule_id)
            return

        new_next = compute_next_daily_run(
            schedule_info["execution_time"],
            schedule_info["timezone"],
            after=now,
            clock=self._clock,
        )
        advance_next_run_at(session, schedule_id, new_next, clock=self._clock)

        aid = create_attempt(session, run_id=run_id, attempt_number=1)
        start_run(session, run_id, clock=self._clock)
        start_attempt(session, aid, clock=self._clock)

        lease = acquire_lease(session, run_id=run_id, worker_id=self.worker_id, clock=self._clock)

        # Execute with timeout
        result = self._executor.execute(
            job_type=job_type,
            job_params=job_params,
            household_id=household_id,
            run_id=run_id,
            attempt_id=aid,
            lease_id=lease["lease_id"],
            worker_id=self.worker_id,
            fencing_token=lease["fencing_token"],
        )

        is_guardian = job_type.startswith("guardian.")

        # Determine final status from the result
        if is_guardian and "evaluation_run" in result:
            eval_status = result.get("evaluation_run", {}).get("status", "")
            finalize_status = (
                "completed" if eval_status.startswith(("completed", "skipped"))
                else "failed"
            )
            is_timeout = False
        else:
            is_timeout = result.get("status") == "terminated"
            finalize_status = "aborted" if is_timeout else (
                "completed" if result.get("status") == "completed" else "failed"
            )

        # Finalize run (token-gated) — parent owns this for all job types
        fr = finalize_run(
            session,
            run_id=run_id,
            lease_id=lease["lease_id"],
            worker_id=self.worker_id,
            fencing_token=lease["fencing_token"],
            status=finalize_status,
            clock=self._clock,
        )
        if fr == 0:
            logger.warning("Finalize failed — stale token for run %s", run_id)
            complete_attempt(session, aid, "failed",
                             error_message="Lease expired during execution",
                             clock=self._clock)
            return None

        attempt_status = "succeeded" if finalize_status == "completed" else "failed"
        complete_attempt(session, aid, attempt_status,
                         error_message=result.get("error") if not is_guardian else None,
                         clock=self._clock)

        release_lease(
            session,
            lease_id=lease["lease_id"],
            worker_id=self.worker_id,
            fencing_token=lease["fencing_token"],
            clock=self._clock,
        )

        # Return Guardian result for notification dispatch after parent commit
        if is_guardian and finalize_status == "completed" and "evaluation_run" in result:
            return result
        # Return run-failure info for automation notification dispatch
        if not is_guardian and finalize_status == "failed":
            return {"run_id": run_id, "household_id": household_id,
                    "job_type": job_type, "finalize_status": "failed",
                    "error": result.get("error", "")}
        return None
    @staticmethod
    def _maybe_notify_guardian_worker(guardian_result: dict | None, item: dict) -> None:
        """Dispatch Guardian notification from worker after child's business commit."""
        if guardian_result is None:
            return
        run = guardian_result.get("evaluation_run", {})
        status = run.get("status", "")
        events = guardian_result.get("events", [])
        if not status.startswith("completed") or len(events) == 0:
            return
        import hashlib
        from uuid import UUID
        household_id = UUID(item["household_id"])
        breached = sorted(set(
            str(e.get("check_id", "")) for e in events if e.get("check_id")
        ))
        if not breached:
            return
        entity_id = hashlib.sha256("|".join(breached).encode()).hexdigest()[:16]
        try:
            from apps.api.database import SessionLocal
            from apps.api.services.notification_service import dispatch_notification
            ns = SessionLocal()
            try:
                dispatch_notification(
                    ns, source="guardian", event_type="threshold_breach",
                    severity="warning", household_id=household_id,
                    entity_id=entity_id,
                    context={"evaluation_run_id": str(run.get("id", ""))},
                )
            except Exception:
                ns.rollback()
                logger.warning("Guardian notification dispatch failed for run", exc_info=True)
            finally:
                ns.close()
        except Exception:
            logger.warning("Guardian notification session unavailable", exc_info=True)

    @staticmethod
    def _maybe_notify_automation_worker(worker_result: dict | None) -> None:
        """Dispatch Automation run_failed notification from worker after business commit."""
        if worker_result is None or worker_result.get("finalize_status") != "failed":
            return
        try:
            from uuid import UUID

            from apps.api.database import SessionLocal
            from apps.api.services.notification_service import dispatch_notification
            ns = SessionLocal()
            try:
                dispatch_notification(
                    ns, source="automation", event_type="run_failed",
                    severity="warning",
                    household_id=UUID(worker_result["household_id"]),
                    entity_id=str(worker_result["run_id"]),
                    context={"run_id": str(worker_result["run_id"])},
                )
            except Exception:
                ns.rollback()
                logger.warning(
                    "Automation notification dispatch failed for run %s",
                    worker_result.get("run_id"), exc_info=True,
                )
            finally:
                ns.close()
        except Exception:
            logger.warning("Automation notification session unavailable", exc_info=True)

    # ── Graceful shutdown ──

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("Signal %d — graceful shutdown", signum)
        self.stop()

    def _graceful_shutdown(self) -> None:
        """Stop claiming, wait for in-flight work (max GRACEFUL_SHUTDOWN_SECONDS)."""
        logger.info("Graceful shutdown — waiting up to %ds", GRACEFUL_SHUTDOWN_SECONDS)
        deadline = self._clock() + __import__("datetime").timedelta(
            seconds=GRACEFUL_SHUTDOWN_SECONDS
        )
        # The main loop already stopped claiming (shutdown_flag set).
        # Any in-flight work in _execute_scheduled has its own transaction.
        # We just wait for the loop to finish.
        while self._clock() < deadline:
            remaining = (deadline - self._clock()).total_seconds()
            if remaining <= 0:
                break
            self._shutdown_flag.wait(timeout=min(1.0, remaining))
        self._engine.dispose()
