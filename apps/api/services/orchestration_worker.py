"""Standalone Worker — timeout enforcement, stale recovery, graceful shutdown.

Sprint 005 Slice B — Worker reliability corrective closure.
Sprint 005 Corrective — Authoritative reconciliation + lock ordering.
"""

from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Literal
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
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


def _get_sqlstate(exc: DBAPIError) -> str:
    """Extract SQLSTATE from a DBAPIError using the driver's pgcode."""
    orig = getattr(exc, "orig", None)
    if orig is not None:
        code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        if code:
            return str(code)
    return ""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Sprint 005 Corrective: Reconciliation result and entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReconciliationResult:
    """Immutable result from post-child-exit authoritative reconciliation."""
    outcome: Literal[
        "terminal_consistent",
        "not_owner",
        "invariant_repaired",
        "reconciliation_deferred",
        "parent_finalized",
    ]
    run_status: str | None = None
    attempt_status: str | None = None
    message: str = ""


def reconcile_after_child_exit(
    session: Session,
    run_id: str,
    expected_attempt_id: str,
    expected_lease_id: str,
    expected_worker: str,
    expected_token: int,
    *,
    max_retries: int = 3,
    finalize_status: str = "failed",
    attempt_status: str = "failed",
) -> ReconciliationResult:
    """Authoritative reconciliation after child process exits.

    Lock order: runs → leases → ALL attempts ORDER BY id.
    Terminal check BEFORE lease ownership check.
    Retries on PostgreSQL 40P01 deadlock, returns reconciliation_deferred on exhaustion.
    """
    for attempt_num in range(max_retries):
        try:
            return _reconcile_attempt(
                session, run_id, expected_attempt_id,
                expected_lease_id, expected_worker, expected_token,
                finalize_status, attempt_status,
            )
        except DBAPIError as e:
            session.rollback()
            sqlstate = _get_sqlstate(e)
            if sqlstate == "40P01":
                if attempt_num == max_retries - 1:
                    return ReconciliationResult(
                        "reconciliation_deferred",
                        message=f"Deadlock retry exhausted after {max_retries} attempts "
                                f"(SQLSTATE=40P01)",
                    )
                continue
            raise

    return ReconciliationResult("reconciliation_deferred")


def _reconcile_attempt(
    session: Session,
    run_id: str,
    expected_attempt_id: str,
    expected_lease_id: str,
    expected_worker: str,
    expected_token: int,
    finalize_status: str,
    attempt_status: str,
) -> ReconciliationResult:
    """Single reconciliation attempt. Assumes session is clean."""

    # 1) runs FOR UPDATE
    run_row = session.execute(text(
        "SELECT status FROM runs WHERE id = :rid FOR UPDATE"
    ), {"rid": run_id}).fetchone()
    if run_row is None:
        return ReconciliationResult("not_owner", message="Run missing")
    rs = run_row[0]

    # 2) leases FOR UPDATE
    lease_row = session.execute(text(
        "SELECT id, worker_id, fencing_token, released_at,"
        " (expires_at > clock_timestamp()) AS alive"
        " FROM leases WHERE run_id = :rid FOR UPDATE"
    ), {"rid": run_id}).fetchone()

    # 3) ALL attempts FOR UPDATE ORDER BY id
    attempts = session.execute(text(
        "SELECT id, status FROM attempts"
        " WHERE run_id = :rid ORDER BY id FOR UPDATE"
    ), {"rid": run_id}).fetchall()

    # 4) Locate expected attempt
    expected_att = None
    for a in attempts:
        if str(a[0]) == expected_attempt_id:
            expected_att = a
            break
    if expected_att is None:
        raise ValueError(
            f"Expected attempt {expected_attempt_id} not found for run {run_id}"
        )
    at = expected_att[1]

    # STEP 1: Terminal check (before lease ownership)
    if rs in ("completed", "failed", "aborted"):
        if (rs == "completed" and at == "succeeded") or \
           (rs == "failed" and at == "failed") or \
           (rs == "aborted" and at == "aborted"):
            session.rollback()
            return ReconciliationResult("terminal_consistent",
                run_status=rs, attempt_status=at)

        if at in ("pending", "running"):
            session.execute(text(
                "UPDATE attempts SET status = 'aborted',"
                " completed_at = clock_timestamp(),"
                " error_message = 'Consistency repair'"
                " WHERE id = :aid AND status IN ('pending', 'running')"
            ), {"aid": expected_attempt_id})
            session.commit()
            return ReconciliationResult("invariant_repaired",
                run_status=rs, attempt_status="aborted",
                message=f"Repaired attempt {expected_attempt_id} ({at} -> aborted)")

        session.rollback()
        return ReconciliationResult("invariant_repaired",
            run_status=rs, attempt_status=at,
            message="Terminal run with terminal mismatched attempt — not auto-repaired")

    # STEP 2: Not running -> invariant
    if rs != "running":
        session.rollback()
        return ReconciliationResult("invariant_repaired",
            message=f"Run status '{rs}' is neither terminal nor running")

    # STEP 3: running + released -> invariant violation
    if lease_row and lease_row[3] is not None:
        for a in attempts:
            if a[1] in ("pending", "running"):
                session.execute(text(
                    "UPDATE attempts SET status = 'aborted',"
                    " completed_at = clock_timestamp(),"
                    " error_message = 'Invariant repair — released without terminal'"
                    " WHERE id = :aid AND status IN ('pending', 'running')"
                ), {"aid": str(a[0])})
        session.execute(text(
            "UPDATE runs SET status = 'aborted', completed_at = clock_timestamp()"
            " WHERE id = :rid AND status = 'running'"
        ), {"rid": run_id})
        session.commit()
        return ReconciliationResult("invariant_repaired",
            run_status="aborted",
            message="Running run with released lease — repaired to aborted")

    # STEP 4: Parent ownership gate
    if lease_row is None:
        session.rollback()
        return ReconciliationResult("not_owner", message="Lease missing")

    this_parent_owns = (
        str(lease_row[0]) == expected_lease_id
        and lease_row[1] == expected_worker
        and lease_row[2] == expected_token
        and lease_row[3] is None
        and lease_row[4]
    )
    if not this_parent_owns:
        session.rollback()
        return ReconciliationResult("not_owner",
            message="Lease not owned by this parent")

    # STEP 5: Parent finalizes (token-gated)
    rc = finalize_run(
        session,
        run_id=run_id,
        lease_id=expected_lease_id,
        worker_id=expected_worker,
        fencing_token=expected_token,        status=finalize_status,
    )
    if rc == 0:
        session.rollback()
        return ReconciliationResult("not_owner",
            message="finalize_run returned 0 — stale token")

    complete_attempt(session, expected_attempt_id, attempt_status)
    session.execute(text(
        "UPDATE leases SET released_at = NOW()"
        " WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
    ), {"lid": expected_lease_id, "wid": expected_worker, "token": expected_token})
    session.commit()
    return ReconciliationResult("parent_finalized",
        run_status=finalize_status, attempt_status=attempt_status)


def lock_for_finalization(session: Session, run_id: str):
    """Acquire production lock order: runs -> leases -> ALL attempts ORDER BY id.

    Returns (run_status, lease_row, attempts_list).
    Raises ValueError if run not found.
    """
    r = session.execute(text(
        "SELECT status FROM runs WHERE id = :rid FOR UPDATE"
    ), {"rid": run_id}).fetchone()
    if r is None:
        raise ValueError(f"Run {run_id} not found")

    lr = session.execute(text(
        "SELECT id, worker_id, fencing_token, released_at,"
        " (expires_at > clock_timestamp()) AS alive"
        " FROM leases WHERE run_id = :rid FOR UPDATE"
    ), {"rid": run_id}).fetchone()

    attempts = session.execute(text(
        "SELECT id, status FROM attempts"
        " WHERE run_id = :rid ORDER BY id FOR UPDATE"
    ), {"rid": run_id}).fetchall()

    return r[0], lr, attempts


# ---------------------------------------------------------------------------
# Stale-run reaper
# ---------------------------------------------------------------------------


class StaleRunReaper:
    """Recovers stale runs on startup and periodically."""

    def __init__(self, clock: Clock = _utc_now):
        self._clock = clock

    def recover(self, session: Session) -> int:
        stale = recover_stale_runs(session, clock=self._clock)
        count = 0
        for r in stale:
            if self._abort_one(session, r):
                count += 1
        if count:
            logger.info("Reaper: recovered %d stale runs", count)
        return count

    def _abort_one(self, session: Session, stale: dict) -> bool:
        row = session.execute(
            text("SELECT status FROM runs WHERE id = :id FOR UPDATE"),
            {"id": stale["run_id"]},
        ).fetchone()
        if not row or row[0] != "running":
            return False
        complete_run(session, stale["run_id"], "aborted", clock=self._clock)
        release_lease(
            session, lease_id=stale["lease_id"],
            worker_id=stale["worker_id"], fencing_token=stale["fencing_token"],
            clock=self._clock,
        )
        logger.info("Aborted stale run %s", stale["run_id"])
        return True


# ---------------------------------------------------------------------------
# Orchestration Worker
# ---------------------------------------------------------------------------


class OrchestrationWorker:
    """Standalone Worker with timeout enforcement and graceful shutdown."""

    def __init__(
        self, database_url: str, *,
        worker_id: str | None = None, clock: Clock = _utc_now,
        poll_interval: float = 5.0,
        executor: Any = None,
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

    def _recover_on_startup(self) -> None:
        with self._session_factory() as session:
            try:
                self._reaper.recover(session)
                session.commit()
            except Exception:
                session.rollback()
                logger.exception("Recovery failed")

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
                self._maybe_notify_guardian_worker(guardian_result, item)
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
            run_id = create_run(session, job_definition_id=job_def_id,
                schedule_id=schedule_id, idempotency_key=ikey,
                status="pending", triggered_by="schedule",
                scheduled_at=now, household_id=household_id)
        except IntegrityError:
            logger.debug("Run already claimed for schedule %s", schedule_id)
            return
        new_next = compute_next_daily_run(
            schedule_info["execution_time"], schedule_info["timezone"],
            after=now, clock=self._clock)
        advance_next_run_at(session, schedule_id, new_next, clock=self._clock)
        aid = create_attempt(session, run_id=run_id, attempt_number=1)
        start_run(session, run_id, clock=self._clock)
        start_attempt(session, aid, clock=self._clock)
        lease = acquire_lease(session, run_id=run_id, worker_id=self.worker_id,
            clock=self._clock)

        # Pre-spawn commit
        expected_lease_id = lease["lease_id"]
        expected_token = lease["fencing_token"]
        expected_worker = self.worker_id
        expected_run_id = run_id
        expected_attempt_id = aid
        session.commit()

        result = self._executor.execute(
            job_type=job_type, job_params=job_params, household_id=household_id,
            run_id=run_id, attempt_id=aid, lease_id=expected_lease_id,
            worker_id=expected_worker, fencing_token=expected_token)

        is_guardian = job_type.startswith("guardian.")
        if is_guardian and "evaluation_run" in result:
            # Child successfully committed — DB is authoritative
            row = session.execute(text(
                "SELECT r.status, a.status FROM runs r"
                " JOIN attempts a ON a.run_id = r.id"
                " WHERE r.id = :rid AND a.id = :aid"
            ), {"rid": expected_run_id, "aid": expected_attempt_id}).fetchone()
            if row and row[0] in ("completed", "failed", "aborted"):
                return result

        is_timeout = result.get("status") == "terminated"
        is_fenced = result.get("status") == "fenced"
        if is_fenced:
            session.rollback()
            return None

        finalize_status = "aborted" if is_timeout else (
            "completed" if result.get("status") == "completed" else "failed")
        attempt_status = "aborted" if is_timeout else (
            "succeeded" if result.get("status") == "completed" else "failed")

        # ── Production reconciliation: replace duplicate logic ──
        rec_result = reconcile_after_child_exit(
            session, expected_run_id, expected_attempt_id,
            expected_lease_id, expected_worker, expected_token,
            finalize_status=finalize_status,
            attempt_status=attempt_status,
        )
        if rec_result.outcome == "not_owner":
            return None

        session.commit()
        eval_status = result.get("evaluation_run", {}).get("status", "")
        if is_guardian and eval_status.startswith(("completed", "skipped")):
            return result
        # Sprint 008 Slice B: return failure info for failed runs
        if finalize_status == "failed":
            return {"run_id": str(expected_run_id),
                    "household_id": str(household_id),
                    "finalize_status": "failed"}
        return None

    @staticmethod
    def _maybe_notify_guardian_worker(guardian_result: dict | None, item: dict) -> None:
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
            str(e.get("check_id", "")) for e in events if e.get("check_id")))
        if not breached:
            return
        entity_id = hashlib.sha256("|".join(breached).encode()).hexdigest()[:16]
        try:
            from apps.api.database import SessionLocal
            from apps.api.services.notification_service import dispatch_notification
            ns = SessionLocal()
            try:
                dispatch_notification(ns, source="guardian",
                    event_type="threshold_breach", severity="warning",
                    household_id=household_id, entity_id=entity_id,
                    context={"evaluation_run_id": str(run.get("id", ""))})
            except Exception:
                ns.rollback()
                logger.warning("Guardian notification dispatch failed", exc_info=True)
            finally:
                ns.close()
        except Exception:
            logger.warning("Guardian notification session unavailable", exc_info=True)

    @staticmethod
    def _maybe_notify_automation_worker(worker_result: dict | None) -> None:
        if worker_result is None or worker_result.get("finalize_status") != "failed":
            return
        run_id = worker_result.get("run_id", "")
        household_id = worker_result.get("household_id", "")
        if not run_id or not household_id:
            return
        try:
            from uuid import UUID

            from apps.api.database import SessionLocal
            from apps.api.services.notification_service import dispatch_notification
            ns = SessionLocal()
            try:
                dispatch_notification(ns, source="automation",
                    event_type="run_failed", severity="warning",
                    household_id=UUID(household_id), entity_id=run_id,
                    context={"run_id": run_id})
            except Exception:
                ns.rollback()
                logger.warning("Automation notification dispatch failed for run %s",
                    run_id)
            finally:
                ns.close()
        except Exception:
            logger.warning("Automation notification session unavailable")

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("Signal %d — graceful shutdown", signum)
        self.stop()

    def _graceful_shutdown(self) -> None:
        logger.info("Graceful shutdown — waiting up to %ds", GRACEFUL_SHUTDOWN_SECONDS)
        deadline = self._clock() + __import__("datetime").timedelta(
            seconds=GRACEFUL_SHUTDOWN_SECONDS)
        while self._clock() < deadline:
            remaining = (deadline - self._clock()).total_seconds()
            if remaining <= 0:
                break
            self._shutdown_flag.wait(timeout=min(1.0, remaining))
        self._engine.dispose()
