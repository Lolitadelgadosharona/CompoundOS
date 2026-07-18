"""Job executor with max-runtime enforcement via subprocess timeout.

Sprint 005 Slice B — Worker reliability corrective closure.
A timed-out child process cannot submit results — its database
connection is severed when the parent kills it.
"""

from __future__ import annotations

import logging
import multiprocessing
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("orchestration.executor")

Clock = Callable[[], datetime]

MAX_RUNTIME_SECONDS = 300


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Child-process job runner (runs in a separate process)
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
) -> None:
    """Executes the Guardian job in a child process.

    All database work is done here. If the parent kills the process,
    any in-flight transaction is terminated by PostgreSQL.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    try:
        with session_factory() as session:
            # Re-import inside child to avoid pickling issues
            from datetime import date as _date
            from uuid import UUID

            from apps.api.services.guardian import (
                evaluate_all_checks,
                evaluate_one_check,
            )

            if job_type == "guardian.evaluate_all":
                evaluate_all_checks(
                    session,
                    household_id=UUID(household_id),
                    as_of_date=_date.today(),
                )
            elif job_type == "guardian.evaluate_one":
                evaluate_one_check(
                    session,
                    check_id=UUID(job_params["check_id"]),
                    household_id=UUID(household_id),
                    as_of_date=_date.today(),
                )
            session.commit()

        result_queue.put({"status": "completed"})

    except Exception as exc:
        try:
            result_queue.put({"status": "failed", "error": str(exc)[:500]})
        except Exception:
            pass  # Queue may be closed if parent already timed out
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Timeout-enforcing executor
# ---------------------------------------------------------------------------


class TimeoutJobExecutor:
    """Executes Guardian jobs in a child process with a hard timeout.

    After timeout: the child process is terminated via SIGTERM/SIGKILL.
    Its database connection is severed, so it CANNOT commit results.
    The parent detects timeout via the empty result queue.
    """

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
    ) -> dict:
        """Execute a job with timeout. Returns {"status": ..., "error": ...}."""
        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue(maxsize=1)
        child_kwargs = dict(
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
        )
        proc = ctx.Process(target=_run_job_in_child, kwargs=child_kwargs)
        proc.start()
        proc.join(timeout=self.max_runtime)

        if proc.is_alive():
            # Timeout: kill child — it cannot commit
            logger.warning("Job %s timed out after %ds — terminating", run_id, self.max_runtime)
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join()
            return {"status": "terminated", "error": f"Max runtime {self.max_runtime}s exceeded"}

        # Child finished — get result
        try:
            result = queue.get_nowait()
            return result
        except Exception:
            return {"status": "failed", "error": "Child process exited without result"}


# ---------------------------------------------------------------------------
# Fake executor for tests (injectable timing)
# ---------------------------------------------------------------------------


class FakeJobExecutor:
    """Test executor that can simulate success, failure, or timeout."""

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
