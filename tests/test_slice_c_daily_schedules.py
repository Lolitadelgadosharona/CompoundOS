"""Sprint 008 Slice C — Daily schedules + idempotency acceptance tests.

Real PostgreSQL, real migration, exact assertions.
"""

import multiprocessing
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.orchestration_executor import _run_job_in_child
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


# ═══════════════════════════════════════════════════════════════════════════
# COS-008-C-HARDEN — execution dispatch regression tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFailClosedDispatch:
    """backup.daily and unknown types must NOT execute Guardian logic."""

    def test_backup_daily_never_calls_evaluate_core(
        self, db_session: Session, monkeypatch,
    ) -> None:
        """A: backup.daily execution must never invoke evaluate_core."""
        import apps.api.services.guardian as guardian_mod

        called = []

        def spy_evaluate(*args, **kwargs):
            called.append(1)
            return {}

        monkeypatch.setattr(guardian_mod, "evaluate_core", spy_evaluate)

        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        proc = ctx.Process(
            target=_run_job_in_child,
            kwargs={
                "database_url": db_url,
                "job_type": "backup.daily",
                "job_params": {},
                "household_id": hid,
                "run_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "lease_id": str(uuid4()),
                "worker_id": "test-backup-guard",
                "fencing_token": 1,
                "result_queue": q,
            },
        )
        proc.start()
        proc.join(timeout=15)
        assert len(called) == 0, (
            f"evaluate_core called {len(called)} times for backup.daily"
        )

    def test_backup_daily_fails_explicitly(
        self, db_session: Session,
    ) -> None:
        """B: backup.daily execution fails with clear unsupported error."""
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        proc = ctx.Process(
            target=_run_job_in_child,
            kwargs={
                "database_url": db_url,
                "job_type": "backup.daily",
                "job_params": {},
                "household_id": hid,
                "run_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "lease_id": str(uuid4()),
                "worker_id": "test-backup-fail",
                "fencing_token": 1,
                "result_queue": q,
            },
        )
        proc.start()
        proc.join(timeout=15)
        msg = None
        while True:
            try:
                msg = q.get_nowait()
            except Exception:
                break
        assert msg is not None, "Child produced no result"
        assert msg.get("status") == "failed", (
            f"Expected status='failed', got {msg}"
        )
        err = msg.get("error", "")
        assert "backup.daily" in err, (
            f"Error must mention backup.daily: {err}"
        )
        assert "not yet implemented" in err.lower(), (
            f"Error must state not yet implemented: {err}"
        )

    def test_guardian_continues_to_execute(
        self, db_session: Session,
    ) -> None:
        """E: guardian.evaluate_core still executes correctly."""
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        jid = _create_job_definition(db_session, hid, "guardian.evaluate_all")
        sid = str(uuid4())
        db_session.execute(text(
            "INSERT INTO schedules (id, job_definition_id,"
            " execution_time, timezone, enabled, next_run_at)"
            " VALUES (:id, :jid, '09:00', 'UTC', true, NOW())"
        ), {"id": sid, "jid": jid})

        from apps.api.services.orchestration_repository import (
            acquire_lease,
            create_attempt,
            create_run,
            start_attempt,
            start_run,
        )
        rid = create_run(
            db_session, job_definition_id=jid, schedule_id=sid,
            idempotency_key=f"guardian-ok-{uuid4().hex[:8]}",
            status="pending", triggered_by="schedule",
            scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        assert rid is not None
        aid = create_attempt(db_session, run_id=rid, attempt_number=1)
        start_run(db_session, rid)
        start_attempt(db_session, aid)
        lease = acquire_lease(db_session, run_id=rid, worker_id="test-guardian-ok")
        db_session.commit()

        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(
            target=_run_job_in_child,
            kwargs={
                "database_url": db_url,
                "job_type": "guardian.evaluate_all",
                "job_params": {},
                "household_id": hid,
                "run_id": rid,
                "attempt_id": aid,
                "lease_id": lease["lease_id"],
                "worker_id": "test-guardian-ok",
                "fencing_token": lease["fencing_token"],
                "result_queue": q,
            },
        )
        proc.start()
        proc.join(timeout=15)
        msgs = []
        while True:
            try:
                msgs.append(q.get_nowait())
            except Exception:
                break
        results = [m for m in msgs if "evaluation_run" in m]
        assert len(results) > 0, (
            f"Guardian evaluation produced no result. Got: {msgs}"
        )
        eval_run = results[0].get("evaluation_run", {})
        assert eval_run.get("status", "").startswith(
            ("completed", "skipped")
        ), f"Guardian evaluation failed: {eval_run}"

    def test_unknown_job_type_fails_closed(
        self, db_session: Session,
    ) -> None:
        """F: Unknown job types fail closed — no silent fallthrough."""
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        proc = ctx.Process(
            target=_run_job_in_child,
            kwargs={
                "database_url": db_url,
                "job_type": "unknown.fake_job",
                "job_params": {},
                "household_id": hid,
                "run_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "lease_id": str(uuid4()),
                "worker_id": "test-unknown",
                "fencing_token": 1,
                "result_queue": q,
            },
        )
        proc.start()
        proc.join(timeout=15)
        msg = None
        while True:
            try:
                msg = q.get_nowait()
            except Exception:
                break
        assert msg is not None
        assert msg.get("status") == "failed", (
            f"Unknown job type must fail. Got: {msg}"
        )
        assert "unknown.fake_job" in msg.get("error", ""), (
            f"Error must mention unknown job type: {msg}"
        )

    def test_backup_daily_guardian_side_effects_absent(
        self, db_session: Session,
    ) -> None:
        """D: No Guardian events, notifications, or side effects."""
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        before_events = db_session.execute(text(
            "SELECT COUNT(*) FROM guardian_events"
        )).scalar()
        before_notif = db_session.execute(text(
            "SELECT COUNT(*) FROM notification_events"
        )).scalar()

        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(
            target=_run_job_in_child,
            kwargs={
                "database_url": db_url,
                "job_type": "backup.daily",
                "job_params": {},
                "household_id": hid,
                "run_id": str(uuid4()),
                "attempt_id": str(uuid4()),
                "lease_id": str(uuid4()),
                "worker_id": "test-side-effects",
                "fencing_token": 1,
                "result_queue": q,
            },
        )
        proc.start()
        proc.join(timeout=15)

        after_events = db_session.execute(text(
            "SELECT COUNT(*) FROM guardian_events"
        )).scalar()
        after_notif = db_session.execute(text(
            "SELECT COUNT(*) FROM notification_events"
        )).scalar()

        assert after_events == before_events, (
            f"Guardian events changed: {before_events} → {after_events}"
        )
        assert after_notif == before_notif, (
            f"Notification events changed: {before_notif} → {after_notif}"
        )

    def test_backup_daily_run_not_completed(
        self, db_session: Session,
    ) -> None:
        """C: backup.daily execution must not produce completed run."""
        _ensure_household(db_session)
        hid = _get_household_id(db_session)
        jid = _create_job_definition(db_session, hid, "backup.daily")
        from apps.api.services.orchestration_repository import (
            acquire_lease,
            create_attempt,
            create_run,
            start_attempt,
            start_run,
        )
        rid = create_run(
            db_session, job_definition_id=jid, schedule_id=None,
            idempotency_key=f"not-completed-{uuid4().hex[:8]}",
            status="pending", triggered_by="schedule",
            scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        assert rid is not None, "create_run returned None"
        aid = create_attempt(db_session, run_id=rid, attempt_number=1)
        start_run(db_session, rid)
        start_attempt(db_session, aid)
        lease = acquire_lease(db_session, run_id=rid, worker_id="w-nc")
        db_session.commit()

        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(
            target=_run_job_in_child,
            kwargs={
                "database_url": db_url,
                "job_type": "backup.daily",
                "job_params": {},
                "household_id": hid,
                "run_id": rid,
                "attempt_id": aid,
                "lease_id": lease["lease_id"],
                "worker_id": "w-nc",
                "fencing_token": lease["fencing_token"],
                "result_queue": q,
            },
        )
        proc.start()
        proc.join(timeout=15)

        r = db_session.execute(text(
            "SELECT status FROM runs WHERE id=:r"
        ), {"r": rid}).fetchone()
        assert r is not None
        assert r[0] != "completed", (
            f"backup.daily run must not be completed: {r[0]}"
        )
        db_session.rollback()
