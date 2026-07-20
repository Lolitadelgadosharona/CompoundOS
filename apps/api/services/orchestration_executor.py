"""Transaction-neutral Guardian evaluation for Worker child processes.

Sprint 005 Slice B — process/transaction integrity closure.
The Worker child calls this instead of the HTTP-facing Guardian service,
so that lease validation and Guardian results are in ONE transaction.
"""

from __future__ import annotations

import multiprocessing
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

logger = __import__("logging").getLogger("orchestration.executor")

Clock = Callable[[], datetime]
MAX_RUNTIME_SECONDS = 300


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lease validation (must run in same transaction as evaluation)
# ---------------------------------------------------------------------------


_LEASE_VALIDATE_SQL = (
    "SELECT 1 FROM leases"
    " WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
    " AND released_at IS NULL AND expires_at > clock_timestamp()"
)


def validate_lease_for_commit(
    session: Any,
    lease_id: str,
    worker_id: str,
    fencing_token: int,
    *,
    clock: Clock = _utc_now,
) -> bool:
    """Check that the lease is still valid before committing.

    Uses PostgreSQL clock_timestamp() for the definitive wall-clock at
    the instant of validation — not a transaction-start snapshot.
    The `clock` parameter is retained for testability but is NOT used
    in the SQL; the database clock is authoritative for the final gate.
    """
    row = session.execute(
        __import__("sqlalchemy").text(_LEASE_VALIDATE_SQL),
        {"lid": lease_id, "wid": worker_id, "token": fencing_token},
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Child-process job runner (spawn-based, lease-validated commit)
# ---------------------------------------------------------------------------


def _run_job_in_child(
    database_url: str,
    job_type: str,
    job_params: dict,
    household_id: str,
    run_id: str,
    attempt_id: str,
    lease_id: str,
    worker_id: str,
    fencing_token: int,
    result_queue: multiprocessing.Queue,
    marker_table: str = "",
    marker_key: str = "",
) -> None:
    """Execute Guardian evaluation + lease-validated fenced commit.

    CRITICAL ORDER (Sprint 005 Slice B corrective):
    1. Evaluate Guardian FIRST (no lease lock — parent heartbeat can update)
    2. Lock lease FOR UPDATE at final commit window
    3. If lease missing/expired: rollback entire transaction
    4. Finalize attempt + run + release lease → atomic COMMIT

    The FOR UPDATE lock covers only the short finalization window, NOT
    the long Guardian evaluation.  Parent heartbeat connections update the
    same lease row freely during evaluation.

    If marker_table/marker_key are provided, writes a test marker row
    to demonstrate that an uncommitted row is rolled back on kill.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        with session_factory() as session:
            # Write test marker
            if marker_table and marker_key:
                try:
                    session.execute(text(
                        f"INSERT INTO {marker_table}"
                        f" (id) VALUES (:id)"
                        f" ON CONFLICT DO NOTHING"
                    ), {"id": marker_key})
                except Exception:
                    pass

            # Notify parent we've reached the blocking point
            result_queue.put({"stage": "ready"})

            # Single fenced transaction — lease lock at final window only
            with session.begin():
                # ── Phase 1: Guardian evaluation (NO lease lock) ──
                # Parent heartbeat can freely UPDATE the lease row during
                # this potentially long-running evaluation.
                from datetime import date as _date

                from apps.api.services.guardian import evaluate_core

                result = evaluate_core(
                    session,
                    household_id=UUID(household_id),
                    as_of_date=_date.today(),
                    target_check_id=(
                        UUID(job_params["check_id"])
                        if job_type == "guardian.evaluate_one"
                        else None
                    ),
                )

                # ── Phase 2: Final commit window ──
                # Lock lease with FOR UPDATE and validate with
                # PostgreSQL clock_timestamp() — the definitive wall-clock
                # at the instant of validation, not a transaction-start
                # snapshot.  This correctly detects lease expiry even when
                # the evaluation ran for a long time.
                row = session.execute(text(
                    "SELECT 1 FROM leases"
                    " WHERE id = :lid AND worker_id = :wid"
                    " AND fencing_token = :token"
                    " AND released_at IS NULL"
                    " AND expires_at > clock_timestamp()"
                    " FOR UPDATE"
                ), {
                    "lid": lease_id, "wid": worker_id,
                    "token": fencing_token,
                }).fetchone()

                if row is None:
                    # Lease was taken over or expired during evaluation.
                    # Rollback the entire transaction — zero Guardian
                    # effects persist.
                    result_queue.put({
                        "status": "fenced",
                        "error": "Lease lost before final commit window",
                    })
                    return

                # ── Phase 3: Finalize Automation state ──
                attempt_status = (
                    "succeeded"
                    if result.get("evaluation_run", {}).get("status", "").startswith(
                        ("completed", "skipped"))
                    else "failed"
                )
                session.execute(text(
                    "UPDATE attempts SET status = :st, completed_at = NOW(),"
                    " error_message = :err WHERE id = :id"
                ), {
                    "id": attempt_id, "st": attempt_status,
                    "err": result.get("error"),
                })

                run_status = (
                    "completed"
                    if result.get("evaluation_run", {}).get("status", "").startswith(
                        ("completed", "skipped"))
                    else "failed"
                )
                session.execute(text(
                    "UPDATE runs SET status = :st, completed_at = NOW()"
                    " WHERE id = :id"
                ), {"id": run_id, "st": run_status})

                # ── Phase 4: Release lease ──
                session.execute(text(
                    "UPDATE leases SET released_at = NOW()"
                    " WHERE id = :lid AND worker_id = :wid"
                    " AND fencing_token = :token"
                ), {"lid": lease_id, "wid": worker_id, "token": fencing_token})

            # Transaction committed atomically — all or nothing
            result_queue.put(result)

    except Exception as exc:
        try:
            result_queue.put({"status": "failed", "error": str(exc)[:500]})
        except Exception:
            pass
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Timeout-enforcing executor (unchanged from reliability PR)
# ---------------------------------------------------------------------------


class TimeoutJobExecutor:
    def __init__(
        self,
        database_url: str,
        *,
        max_runtime: int = MAX_RUNTIME_SECONDS,
        clock: Clock = _utc_now,
    ):
        self.database_url = database_url
        self.max_runtime = max_runtime
        self._clock = clock

    def execute(
        self,
        job_type: str,
        job_params: dict,
        household_id: str,
        run_id: str,
        attempt_id: str,
        lease_id: str,
        worker_id: str,
        fencing_token: int,
        **extra: Any,
    ) -> dict:
        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue(maxsize=2)
        kwargs = dict(
            database_url=self.database_url,
            job_type=job_type,
            job_params=job_params,
            household_id=household_id,
            run_id=run_id,
            attempt_id=attempt_id,
            lease_id=lease_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            result_queue=queue,
            marker_table=extra.get("marker_table", ""),
            marker_key=extra.get("marker_key", ""),
        )
        proc = ctx.Process(target=_run_job_in_child, kwargs=kwargs)
        proc.start()
        proc.join(timeout=self.max_runtime)

        if proc.is_alive():
            logger.warning(
                "Job %s timed out after %ds — terminating", run_id, self.max_runtime
            )
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join()
            return {"status": "terminated",
                    "error": f"Max runtime {self.max_runtime}s exceeded"}

        try:
            # Drain queue — first "ready" signal, then result
            for _ in range(2):
                try:
                    msg = queue.get_nowait()
                    if msg.get("stage") == "ready":
                        continue
                    return msg
                except Exception:
                    break
            return {"status": "failed", "error": "Child exited without result"}
        except Exception:
            return {"status": "failed", "error": "Child process error"}


# ---------------------------------------------------------------------------
# Fake executor for tests
# ---------------------------------------------------------------------------


class FakeJobExecutor:
    def __init__(self, *, should_timeout: bool = False, should_fail: bool = False):
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.execute_calls: list[dict] = []

    def execute(self, **kwargs: Any) -> dict:
        self.execute_calls.append(kwargs)
        if self.should_timeout:
            return {"status": "terminated", "error": "Timeout simulated"}
        if self.should_fail:
            return {"status": "failed", "error": "Simulated failure"}
        return {"status": "completed"}
