"""Sprint 005 Slice B — Process/transaction integrity tests (real subprocess)."""

import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


def _setup_household(session: Session) -> str:
    hid = uuid4()
    session.execute(text(
        "INSERT INTO household_profiles"
        " (id, singleton_key, household_name, base_currency,"
        " investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"
    ), {"id": hid})
    session.commit()
    return str(hid)


def _setup_job(session: Session, hid: str) -> str:
    jid = uuid4()
    session.execute(text(
        "INSERT INTO job_definitions (id, household_id, job_type)"
        " VALUES (:id, :hid, 'guardian.evaluate_all')"
    ), {"id": jid, "hid": hid})
    session.commit()
    return str(jid)


# ── Real subprocess: timeout kills uncommitted work ──


class TestRealSubprocessTimeout:
    """Uses real multiprocessing spawn to verify timeout rollback."""

    def test_timeout_kills_uncommitted_transaction(self, db_session: Session) -> None:
        """Child writes uncommitted marker, parent kills, marker doesn't exist."""
        import multiprocessing

        from apps.api.services.orchestration_executor import _run_job_in_child

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        engine = db_session.get_bind()
        db_url = str(engine.url)

        rid = str(uuid4())
        aid = str(uuid4())
        lid = str(uuid4())
        marker = str(uuid4())

        # Set up lease that will be valid during execution but expired for timeout
        now = _now()
        past_exp = now - timedelta(seconds=1)
        # Insert a run, attempt, lease for the child to reference
        db_session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now, "hid": hid})
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})
        db_session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'test-w', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": past_exp, "now": now})
        db_session.commit()

        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue(maxsize=2)

        proc = ctx.Process(target=_run_job_in_child, kwargs=dict(
            database_url=db_url,
            job_type="guardian.evaluate_all",
            job_params={},
            household_id=hid,
            run_id=rid,
            attempt_id=aid,
            lease_id=lid,
            worker_id="test-w",
            fencing_token=1,
            result_queue=queue,
            marker_table="job_definitions",
            marker_key=marker,
        ))
        proc.start()

        # Wait for child to signal it's ready (past the marker INSERT)
        try:
            msg = queue.get(timeout=10)
            assert msg.get("stage") == "ready"
        except Exception:
            proc.terminate()
            proc.join()
            pytest.fail("Child didn't signal readiness")

        # Kill the child
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join()

        # Verify the marker row does NOT exist (transaction rolled back)
        row = db_session.execute(text(
            "SELECT 1 FROM job_definitions WHERE id = :id"
        ), {"id": marker}).fetchone()
        assert row is None, "Uncommitted marker survived process kill"


# ── Reaper concurrency ──


class TestReaperConcurrency:
    def _setup_stale(self, session: Session) -> tuple[str, str, str]:
        hid = uuid4()
        session.execute(text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"
        ), {"id": hid})
        jid = uuid4()
        session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'guardian.evaluate_all')"
        ), {"id": jid, "hid": hid})
        now = _now()
        rid = uuid4()
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now - timedelta(hours=2), "hid": str(hid)})
        lid = uuid4()
        past = now - timedelta(hours=1)
        session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'dead', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": past, "now": past})
        session.commit()
        return str(hid), str(rid), str(lid)

    def test_concurrent_reapers_one_winner(self, db_session: Session) -> None:
        from apps.api.services.orchestration_worker import StaleRunReaper

        hid, rid, lid = self._setup_stale(db_session)
        now = _now()
        engine = db_session.get_bind()

        barrier = threading.Barrier(2, timeout=5)
        results: list[int] = []

        def _reap() -> None:
            with engine.connect() as c:
                from sqlalchemy.orm import Session as _Session
                s = _Session(bind=c)
                try:
                    barrier.wait()
                    reaper = StaleRunReaper(clock=lambda: now)
                    count = reaper.recover(s)
                    s.commit()
                    results.append(count)
                except Exception:
                    results.append(-1)
                finally:
                    s.close()

        t1 = threading.Thread(target=_reap)
        t2 = threading.Thread(target=_reap)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one thread should have recovered (the other finds status != running)
        assert results.count(1) == 1, f"Expected 1 reaper winner, got: {results}"


# ── DST exception handling ──


class TestDSTExceptionSpec:
    def test_nonexistent_time_handled_no_bare_except(self) -> None:
        from datetime import time as _time

        from apps.api.services.orchestration_scheduling import resolve_local_time

        def clock():
            return datetime(2026, 3, 7, 20, 0, tzinfo=UTC)
        result = resolve_local_time(_time(2, 30), "America/New_York", clock=clock)
        assert result is not None

    def test_invalid_tz_still_raises_value_error(self) -> None:
        from datetime import time as _time

        from apps.api.services.orchestration_scheduling import resolve_local_time

        with pytest.raises(ValueError, match="Invalid IANA"):
            resolve_local_time(
                _time(9, 0), "Bad/Zone",
                clock=lambda: datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            )


# ── Clock propagation ──


class TestClockPropagation:
    def test_create_run_timestamp_preserved(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import create_run

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        fixed = datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC)
        rid = create_run(
            db_session, job_definition_id=jid, schedule_id=None,
            idempotency_key=f"ik-{uuid4().hex[:8]}",
            status="pending", triggered_by="manual",
            scheduled_at=fixed, household_id=hid,
        )
        db_session.commit()
        row = db_session.execute(text(
            "SELECT scheduled_at FROM runs WHERE id = :id"
        ), {"id": rid}).fetchone()
        assert row[0] == fixed
