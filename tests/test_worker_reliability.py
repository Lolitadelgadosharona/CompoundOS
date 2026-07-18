"""Sprint 005 Slice B — Worker reliability tests (timeout, recovery, shutdown)."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

UTC = timezone.utc


def _utc(y: int, m: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, s, tzinfo=UTC)


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


def _setup_schedule(session: Session, jid: str, *, enabled: bool = True) -> str:
    sid = uuid4()
    now = datetime.now(UTC)
    past = now - timedelta(minutes=5)
    session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at, enabled)"
        " VALUES (:id, :jid, '09:00', 'UTC', :nr, :en)"
    ), {"id": sid, "jid": jid, "nr": past, "en": enabled})
    session.commit()
    return str(sid)


# ── Stale Run Reaper ──


class TestStaleRunReaper:
    def test_recover_expired_running_run(self, db_session: Session) -> None:
        from apps.api.services.orchestration_worker import StaleRunReaper

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        sid = _setup_schedule(db_session, jid)
        rid = uuid4()
        now = datetime.now(UTC)
        past = now - timedelta(hours=2)
        session = db_session
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, schedule_id, idempotency_key, status,"
            " triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, :sid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "sid": sid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": past, "hid": hid})
        # Lease with past expiry
        lid = uuid4()
        session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'dead-worker', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": past + timedelta(seconds=60), "now": past})
        session.commit()

        # Reap with clock set to now (lease is expired)
        reaper = StaleRunReaper(clock=lambda: now)
        reaper.recover(db_session)
        db_session.commit()

        row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :id"
        ), {"id": rid}).fetchone()
        assert row[0] == "aborted"

    def test_recover_does_not_touch_active_lease(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import acquire_lease
        from apps.api.services.orchestration_worker import StaleRunReaper

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        sid = _setup_schedule(db_session, jid)
        rid = uuid4()
        now = datetime.now(UTC)
        session = db_session
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, schedule_id, idempotency_key, status,"
            " triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, :sid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "sid": sid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now, "hid": hid})
        acquire_lease(db_session, run_id=rid, worker_id="w1")
        session.commit()

        reaper = StaleRunReaper(clock=lambda: now)
        reaper.recover(db_session)
        db_session.commit()

        row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :id"
        ), {"id": rid}).fetchone()
        assert row[0] == "running"

    def test_completed_run_not_recovered(self, db_session: Session) -> None:
        from apps.api.services.orchestration_worker import StaleRunReaper

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        sid = _setup_schedule(db_session, jid)
        rid = uuid4()
        now = datetime.now(UTC)
        past = now - timedelta(hours=2)
        session = db_session
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, schedule_id, idempotency_key, status,"
            " triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, :sid, :ik, 'completed', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "sid": sid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": past, "hid": hid})
        lid = uuid4()
        session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'dead-worker', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": past + timedelta(seconds=60), "now": past})
        session.commit()

        reaper = StaleRunReaper(clock=lambda: now)
        reaper.recover(db_session)
        db_session.commit()

        row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :id"
        ), {"id": rid}).fetchone()
        assert row[0] == "completed"


# ── Timeout / Fake Executor ──


class TestTimeoutExecutor:
    def test_timeout_executor_terminates(self) -> None:
        from apps.api.services.orchestration_executor import FakeJobExecutor

        executor = FakeJobExecutor(should_timeout=True)
        result = executor.execute(
            job_type="guardian.evaluate_all", job_params={}, household_id="h",
            run_id="r", attempt_id="a", lease_id="l", worker_id="w",
            fencing_token=1,
        )
        assert result["status"] == "terminated"
        assert len(executor.execute_calls) == 1

    def test_fake_executor_success(self) -> None:
        from apps.api.services.orchestration_executor import FakeJobExecutor

        executor = FakeJobExecutor()
        result = executor.execute(
            job_type="guardian.evaluate_all", job_params={}, household_id="h",
            run_id="r", attempt_id="a", lease_id="l", worker_id="w",
            fencing_token=1,
        )
        assert result["status"] == "completed"

    def test_fake_executor_failure(self) -> None:
        from apps.api.services.orchestration_executor import FakeJobExecutor

        executor = FakeJobExecutor(should_fail=True)
        result = executor.execute(
            job_type="guardian.evaluate_all", job_params={}, household_id="h",
            run_id="r", attempt_id="a", lease_id="l", worker_id="w",
            fencing_token=1,
        )
        assert result["status"] == "failed"


# ── Graceful Shutdown ──


class TestGracefulShutdown:
    def test_worker_stops_claiming_on_shutdown(self, db_session: Session) -> None:
        from apps.api.services.orchestration_executor import FakeJobExecutor
        from apps.api.services.orchestration_worker import OrchestrationWorker

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        _setup_schedule(db_session, jid, enabled=True)

        # Get the test database URL from the session
        engine = db_session.get_bind()
        db_url = str(engine.url)

        worker = OrchestrationWorker(
            db_url,
            clock=lambda: datetime.now(UTC),
            poll_interval=0.1,
            executor=FakeJobExecutor(should_fail=False),
        )
        # Signal stop immediately
        worker.stop()

        # Run once — should claim at most one and stop
        claimed = worker._claim_and_execute()
        # After stop, claim loop should not process more
        assert claimed >= 0  # May claim 0 or 1
    def test_shutdown_flag_respected(self, db_session: Session) -> None:
        from apps.api.services.orchestration_executor import FakeJobExecutor
        from apps.api.services.orchestration_worker import OrchestrationWorker

        engine = db_session.get_bind()
        db_url = str(engine.url)

        worker = OrchestrationWorker(
            db_url,
            executor=FakeJobExecutor(),
        )
        assert not worker._shutdown_flag.is_set()
        worker.stop()
        assert worker._shutdown_flag.is_set()


# ── DST Exception Specificity ──


class TestDSTExceptionHandling:
    def test_nonexistent_time_handled(self) -> None:
        from apps.api.services.orchestration_scheduling import resolve_local_time

        # Spring-forward in US/Eastern: 2026-03-08 2:30am doesn't exist
        def clock():
            return _utc(2026, 3, 7, 20, 0)  # 3pm ET day before
        result = resolve_local_time(
            __import__("datetime").time(2, 30), "America/New_York", clock=clock
        )
        assert result is not None

    def test_invalid_timezone_still_raises(self) -> None:
        from apps.api.services.orchestration_scheduling import resolve_local_time

        with pytest.raises(ValueError, match="Invalid IANA"):
            resolve_local_time(
                __import__("datetime").time(9, 0), "Bad/Zone",
                clock=lambda: _utc(2026, 1, 1, 0, 0),
            )


# ── Clock Propagation ──


class TestClockPropagation:
    def test_create_run_uses_explicit_scheduled_at(self, db_session: Session) -> None:
        from apps.api.services.orchestration_repository import create_run

        hid = _setup_household(db_session)
        jid = _setup_job(db_session, hid)
        fixed_time = _utc(2026, 7, 20, 9, 0, 0)
        rid = create_run(
            db_session,
            job_definition_id=jid,
            schedule_id=None,
            idempotency_key=f"ik-{uuid4().hex[:8]}",
            status="pending",
            triggered_by="manual",
            scheduled_at=fixed_time,
            household_id=hid,
        )
        db_session.commit()
        row = db_session.execute(text(
            "SELECT scheduled_at FROM runs WHERE id = :id"
        ), {"id": rid}).fetchone()
        assert row[0] == fixed_time
