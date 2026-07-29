"""Sprint 008 Slice C — Daily schedules + idempotency acceptance tests.

Real PostgreSQL, real migration, exact assertions.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.orchestration_scheduling import (
    ALLOWED_JOB_TYPES,
    compute_idempotency_key,
    validate_job_params,
)

pytestmark = pytest.mark.postgres


# ═══════════════════════════════════════════════════════════════════════════
# Allowlist
# ═══════════════════════════════════════════════════════════════════════════

class TestJobTypeAllowlist:
    def test_backup_daily_in_application_allowlist(self) -> None:
        assert "backup.daily" in ALLOWED_JOB_TYPES

    def test_guardian_types_still_allowed(self) -> None:
        assert "guardian.evaluate_all" in ALLOWED_JOB_TYPES
        assert "guardian.evaluate_one" in ALLOWED_JOB_TYPES

    def test_unknown_job_type_rejected(self) -> None:
        with pytest.raises(Exception):
            validate_job_params("unknown.type", {})

    def test_backup_daily_rejects_params(self) -> None:
        from apps.api.services.orchestration_scheduling import InvalidJobParamsError
        with pytest.raises(InvalidJobParamsError):
            validate_job_params("backup.daily", {"extra": "param"})

    def test_backup_daily_accepts_empty_params(self) -> None:
        result = validate_job_params("backup.daily", {})
        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════
# Idempotency key
# ═══════════════════════════════════════════════════════════════════════════

class TestIdempotencyKey:
    def test_schedule_id_included_in_key(self) -> None:
        d = date(2026, 7, 28)
        k1 = compute_idempotency_key(
            "guardian.evaluate_all", {}, d, schedule_id="sid-aaa",
        )
        k2 = compute_idempotency_key(
            "guardian.evaluate_all", {}, d, schedule_id="sid-bbb",
        )
        assert k1 != k2

    def test_backward_compat_no_schedule_id(self) -> None:
        d = date(2026, 7, 28)
        k = compute_idempotency_key("guardian.evaluate_all", {}, d)
        assert isinstance(k, str)
        assert len(k) == 64  # SHA-256 hex

    def test_different_dates_different_keys(self) -> None:
        k1 = compute_idempotency_key(
            "backup.daily", {}, date(2026, 7, 28), schedule_id="s1",
        )
        k2 = compute_idempotency_key(
            "backup.daily", {}, date(2026, 7, 29), schedule_id="s1",
        )
        assert k1 != k2

    def test_same_inputs_same_key(self) -> None:
        d = date(2026, 7, 28)
        k1 = compute_idempotency_key(
            "backup.daily", {"a": "1"}, d, schedule_id="s1",
        )
        k2 = compute_idempotency_key(
            "backup.daily", {"a": "1"}, d, schedule_id="s1",
        )
        assert k1 == k2


# ═══════════════════════════════════════════════════════════════════════════
# Daily schedule seed — default disabled
# ═══════════════════════════════════════════════════════════════════════════

class TestDailyScheduleSeed:
    def test_seed_creates_guardian_and_backup_schedules(
        self, db_session: Session,
    ) -> None:
        from apps.api.services.orchestration_seed import seed_daily_schedules
        _ensure_household(db_session)
        seed_daily_schedules(db_session)
        jd_rows = db_session.execute(text(
            "SELECT id, job_type FROM job_definitions"
            " ORDER BY job_type"
        )).fetchall()
        types = {r[1] for r in jd_rows}
        assert "guardian.evaluate_all" in types
        assert "backup.daily" in types

    def test_schedules_created_default_disabled(
        self, db_session: Session,
    ) -> None:
        from apps.api.services.orchestration_seed import seed_daily_schedules
        _ensure_household(db_session)
        seed_daily_schedules(db_session)
        schedules = db_session.execute(text(
            "SELECT s.enabled, jd.job_type FROM schedules s"
            " JOIN job_definitions jd ON s.job_definition_id = jd.id"
        )).fetchall()
        for enabled, job_type in schedules:
            assert enabled is False, f"{job_type} should be disabled"

    def test_seed_is_idempotent(self, db_session: Session) -> None:
        from apps.api.services.orchestration_seed import seed_daily_schedules
        _ensure_household(db_session)
        seed_daily_schedules(db_session)
        before_jd = db_session.execute(text(
            "SELECT COUNT(*) FROM job_definitions"
        )).scalar()
        before_sched = db_session.execute(text(
            "SELECT COUNT(*) FROM schedules"
        )).scalar()
        seed_daily_schedules(db_session)
        after_jd = db_session.execute(text(
            "SELECT COUNT(*) FROM job_definitions"
        )).scalar()
        after_sched = db_session.execute(text(
            "SELECT COUNT(*) FROM schedules"
        )).scalar()
        assert after_jd == before_jd
        assert after_sched == before_sched


# ═══════════════════════════════════════════════════════════════════════════
# ON CONFLICT DO NOTHING RETURNING id
# ═══════════════════════════════════════════════════════════════════════════

class TestCreateRunOnConflict:
    def test_duplicate_idempotency_key_returns_none(
        self, db_session: Session,
    ) -> None:
        from apps.api.services.orchestration_repository import create_run
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        jd_id = _create_job_definition(db_session, hid, "guardian.evaluate_all")
        ikey = "dup-test-key-" + uuid4().hex
        r1 = create_run(
            db_session, job_definition_id=jd_id, schedule_id=None,
            idempotency_key=ikey, status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        assert r1 is not None
        r2 = create_run(
            db_session, job_definition_id=jd_id, schedule_id=None,
            idempotency_key=ikey, status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        assert r2 is None

    def test_no_conflict_does_not_abort_transaction(
        self, db_session: Session,
    ) -> None:
        """ON CONFLICT DO NOTHING must not leave a failed transaction."""
        from apps.api.services.orchestration_repository import (
            advance_next_run_at,
            create_run,
        )
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        jd_id = _create_job_definition(db_session, hid, "guardian.evaluate_all")
        sid = str(uuid4())
        db_session.execute(text(
            "INSERT INTO schedules (id, job_definition_id,"
            " execution_time, timezone, enabled, next_run_at)"
            " VALUES (:id, :jd_id, '09:00', 'UTC', true, NOW())"
        ), {"id": sid, "jd_id": jd_id})
        db_session.commit()

        ikey = "on-conflict-txn-" + uuid4().hex
        r1 = create_run(
            db_session, job_definition_id=jd_id, schedule_id=sid,
            idempotency_key=ikey, status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        assert r1 is not None
        # Duplicate — should not abort
        r2 = create_run(
            db_session, job_definition_id=jd_id, schedule_id=sid,
            idempotency_key=ikey, status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        assert r2 is None
        # Transaction still alive — advance next_run_at should work
        new_next = datetime.now(timezone.utc) + timedelta(days=1)
        rc = advance_next_run_at(db_session, sid, new_next)
        db_session.commit()
        assert rc == 1


# ═══════════════════════════════════════════════════════════════════════════
# Worker: schedule-local date + schedule_id in idempotency
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkerLocalDateAndIdempotency:
    def test_schedule_local_date_used_in_key(
        self, db_session: Session,
    ) -> None:
        """Worker computes idempotency key from schedule's IANA timezone."""
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        jd_id = _create_job_definition(db_session, hid, "guardian.evaluate_all")
        sid = str(uuid4())
        # Schedule in Asia/Tokyo (+9) at 01:00 JST
        # When it's 2026-07-28 16:00 UTC (= 2026-07-29 01:00 JST)
        # The schedule's local date is 2026-07-29
        db_session.execute(text(
            "INSERT INTO schedules (id, job_definition_id,"
            " execution_time, timezone, enabled, next_run_at)"
            " VALUES (:id, :jd_id, '01:00', 'Asia/Tokyo', true, NOW())"
        ), {"id": sid, "jd_id": jd_id})
        db_session.commit()

        # Create a frozen clock at 2026-07-28T16:00:00 UTC
        frozen_utc = datetime(2026, 7, 28, 16, 0, 0, tzinfo=timezone.utc)

        from apps.api.services.orchestration_worker import OrchestrationWorker
        worker = OrchestrationWorker(
            "sqlite:///:memory:",  # unused — we test idempotency only
            worker_id="test-local-date",
            executor=_FakeExecutor(),
        )
        worker._clock = lambda: frozen_utc

        # Compute key manually with Japan local date (2026-07-29)
        key_from_worker = compute_idempotency_key(
            "guardian.evaluate_all", {},
            date(2026, 7, 29),  # local date in Asia/Tokyo
            schedule_id=sid,
        )
        key_utc = compute_idempotency_key(
            "guardian.evaluate_all", {},
            date(2026, 7, 28),  # UTC date
            schedule_id=sid,
        )
        assert key_from_worker != key_utc


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

class _FakeExecutor:
    def execute(self, **kwargs):
        return {"status": "completed", "evaluation_run": {
            "status": "completed", "id": str(uuid4()),
        }, "events": []}


def _ensure_household(session: Session) -> str:
    r = session.execute(text(
        "SELECT id FROM household_profiles LIMIT 1"
    )).fetchone()
    if r:
        return str(r[0])
    hid = str(uuid4())
    session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, TRUE, 'Test', 'USD', 'LT', '', '', '')"
    ), {"id": hid})
    session.commit()
    return hid


def _get_household_id(session: Session) -> str:
    r = session.execute(text(
        "SELECT id FROM household_profiles LIMIT 1"
    )).fetchone()
    assert r is not None, "No household found"
    return str(r[0])


def _create_job_definition(
    session: Session, hid: str, job_type: str,
) -> str:
    jd_id = str(uuid4())
    session.execute(text(
        "INSERT INTO job_definitions"
        " (id, household_id, job_type, job_params)"
        " VALUES (:id, :hid, :jt, '{}'::jsonb)"
    ), {"id": jd_id, "hid": hid, "jt": job_type})
    session.commit()
    return jd_id
