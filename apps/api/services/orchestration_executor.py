"""Transaction-neutral Guardian evaluation for Worker child processes.

Sprint 005 Slice B — process/transaction integrity closure.
The Worker child calls this instead of the HTTP-facing Guardian service,
so that lease validation and Guardian results are in ONE transaction.

Sprint 005 Orchestration Corrective:
- Phase A/B separation with explicit commit/rollback
- runs→leases→ALL attempts lock order
- _FencedError for proper rollback on lease loss
"""

from __future__ import annotations

import multiprocessing
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

logger = __import__("logging").getLogger("orchestration.executor")

Clock = Callable[[], datetime]
MAX_RUNTIME_SECONDS = 300


class _FencedError(Exception):
    """Raised when lease validation fails during Phase B finalization.

    Caught internally to trigger rollback + fenced result.
    Never propagates outside _run_job_in_child.
    """


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

    CORRECTED ORDER (Sprint 005 Orchestration Corrective):
    1. Phase A: Guardian evaluation (NO orchestration locks)
    2. Phase B: runs→leases→ALL attempts FOR UPDATE
    3. If lease invalid: raise _FencedError → rollback
    4. Finalize attempt + run + release lease → commit
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        session = session_factory()

        if marker_table and marker_key:
            try:
                session.execute(text(
                    f"INSERT INTO {marker_table}"
                    f" (id) VALUES (:id)"
                    f" ON CONFLICT DO NOTHING"
                ), {"id": marker_key})
            except Exception:
                pass

        result_queue.put({"stage": "ready"})

        try:
            # Phase A: Business operation (NO orchestration locks)
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

            # Phase B: Short finalization window
            # Lock order: runs → leases → ALL attempts ORDER BY id

            # 1) runs FOR UPDATE
            run_row = session.execute(text(
                "SELECT id FROM runs WHERE id = :rid FOR UPDATE"
            ), {"rid": run_id}).fetchone()
            if run_row is None:
                raise _FencedError("Run missing during finalization")

            # 2) leases FOR UPDATE
            lease_row = session.execute(text(
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

            if lease_row is None:
                raise _FencedError("Lease lost before final commit window")

            # 3) ALL attempts FOR UPDATE ORDER BY id
            session.execute(text(
                "SELECT id FROM attempts"
                " WHERE run_id = :rid ORDER BY id FOR UPDATE"
            ), {"rid": run_id})

            # Finalize
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

            session.execute(text(
                "UPDATE leases SET released_at = NOW()"
                " WHERE id = :lid AND worker_id = :wid"
                " AND fencing_token = :token"
            ), {"lid": lease_id, "wid": worker_id, "token": fencing_token})

            session.commit()
            result_queue.put(result)

        except _FencedError as e:
            session.rollback()
            import os as _os

            result_queue.put({
                "status": "fenced",
                "pid": _os.getpid(),
                "error_type": "_FencedError",
                "error_message": str(e),
            })

        except Exception as exc:
            session.rollback()
            import os as _os2

            diag = {
                "status": "failed",
                "pid": _os2.getpid(),
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
                "sqlstate": "",
            }
            orig = getattr(exc, "orig", None)
            if orig:
                diag["sqlstate"] = str(
                    getattr(orig, "sqlstate", "")
                    or getattr(orig, "pgcode", "")
                )
            result_queue.put(diag)

        finally:
            session.close()

    except Exception as exc:
        try:
            import os as _os3

            diag2 = {
                "status": "failed",
                "pid": _os3.getpid(),
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
                "sqlstate": "",
            }
            orig2 = getattr(exc, "orig", None)
            if orig2:
                diag2["sqlstate"] = str(
                    getattr(orig2, "sqlstate", "")
                    or getattr(orig2, "pgcode", "")
                )
            result_queue.put(diag2)
        except Exception:
            pass
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Timeout-enforcing executor
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
