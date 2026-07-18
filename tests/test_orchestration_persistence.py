"""Sprint 005 Slice A — Orchestration persistence tests."""

import hashlib
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _idempotency_key(job_type: str, scheduled_at: datetime) -> str:
    """Deterministic idempotency key per Technical Design §8.

    Daily-only scheduling: the time bucket is the calendar date.
    Formula: SHA256(job_type || canonical_job_params || scheduled_date).
    """
    scheduled_date = scheduled_at.date().isoformat()
    payload = f"{job_type}||{scheduled_date}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _setup_household(session: Session) -> str:
    """Create a household and return its id."""
    hid = uuid4()
    session.execute(text(
        "INSERT INTO household_profiles"
        " (id, singleton_key, household_name, base_currency,"
        " investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"
    ), {"id": hid})
    session.commit()
    return str(hid)


def _setup_job(session: Session, hid: str, job_type: str = "guardian.evaluate_all") -> str:
    """Create a job definition and return its id."""
    jid = uuid4()
    session.execute(text(
        "INSERT INTO job_definitions (id, household_id, job_type)"
        " VALUES (:id, :hid, :jt)"
    ), {"id": jid, "hid": hid, "jt": job_type})
    session.commit()
    return str(jid)


def _setup_schedule(session: Session, jid: str, execution_time: str = "09:00") -> str:
    """Create a schedule and return its id."""
    sid = uuid4()
    session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at)"
        " VALUES (:id, :jid, :et, 'UTC', :nr)"
    ), {"id": sid, "jid": jid, "et": execution_time, "nr": _now()})
    session.commit()
    return str(sid)


# ── Migration ──


def test_migration_head_is_0008(postgres_engine: Engine) -> None:
    """Alembic head must be 0008 — interaction tests prove migration applied."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0008_orchestration_foundation"


# ── Allowlist ──


def test_job_allowlist_rejects_unknown_type(db_session: Session) -> None:
    hid = _setup_household(db_session)
    _setup_job(db_session, hid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'shell.run')"
        ), {"id": uuid4(), "hid": hid})
        db_session.commit()


def test_job_allowlist_accepts_approved_types(db_session: Session) -> None:
    hid = _setup_household(db_session)
    for jt in ("guardian.evaluate_all", "guardian.evaluate_one"):
        db_session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, :jt)"
        ), {"id": uuid4(), "hid": hid, "jt": jt})
    db_session.commit()


# ── Schedule defaults ──


def test_schedule_enabled_defaults_false(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = uuid4()
    db_session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'UTC', :nr)"
    ), {"id": sid, "jid": jid, "nr": _now()})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT enabled FROM schedules WHERE id = :sid"
    ), {"sid": sid}).fetchone()
    assert row[0] is False


def test_schedule_one_per_job(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    db_session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'UTC', :nr)"
    ), {"id": uuid4(), "jid": jid, "nr": _now()})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at)"
            " VALUES (:id, :jid, '10:00', 'UTC', :nr)"
        ), {"id": uuid4(), "jid": jid, "nr": _now()})
        db_session.commit()


# ── Run lifecycle ──


def test_run_terminal_state_cannot_revert(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'completed', 'manual', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.commit()
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE runs SET status = 'running' WHERE id = :id"
        ), {"id": rid})
        db_session.commit()


def test_run_deletion_forbidden(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'completed', 'manual', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.commit()
    with pytest.raises(Exception, match="deletion_forbidden"):
        db_session.execute(text("DELETE FROM runs WHERE id = :id"), {"id": rid})
        db_session.commit()


# ── Idempotency ──


def test_idempotency_key_unique(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    now = _now()
    ikey = _idempotency_key("guardian.evaluate_all", now)
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'pending', 'schedule', :sa, :hid)"
    ), {"id": uuid4(), "jid": jid, "ik": ikey, "sa": now, "hid": hid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'pending', 'schedule', :sa, :hid)"
        ), {"id": uuid4(), "jid": jid, "ik": ikey, "sa": now, "hid": hid})
        db_session.commit()


# ── Overlap prevention ──


def test_overlap_one_active_run_per_schedule(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = _setup_schedule(db_session, jid)
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, schedule_id, idempotency_key, status,"
        " triggered_by, scheduled_at, household_id)"
        " VALUES (:id, :jid, :sid, :ik, 'running', 'schedule', :sa, :hid)"
    ), {"id": uuid4(), "jid": jid, "sid": sid,
        "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, schedule_id, idempotency_key, status,"
            " triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, :sid, :ik2, 'pending', 'schedule', :sa, :hid)"
        ), {"id": uuid4(), "jid": jid, "sid": sid,
            "ik2": _idempotency_key("guardian.evaluate_all", now + timedelta(seconds=1)),
            "sa": now, "hid": hid})
        db_session.commit()


def test_overlap_allows_different_schedules(db_session: Session) -> None:
    hid = _setup_household(db_session)
    now = _now()
    for i in range(2):
        jid = _setup_job(db_session, hid)
        sid = _setup_schedule(db_session, jid)
        db_session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, schedule_id, idempotency_key, status,"
            " triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, :sid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": uuid4(), "jid": jid, "sid": sid,
            "ik": _idempotency_key(f"guardian.evaluate_all:{i}", now),
            "sa": now, "hid": hid})
    db_session.commit()


# ── Lease / Fencing ──


def test_lease_first_acquisition_token_1(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'pending', 'schedule', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert row[0] == 1


def test_lease_takeover_after_expiry_gets_fresh_token(db_session: Session) -> None:
    """After old lease is deleted (expired), new lease starts at token 1."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'pending', 'schedule', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": uuid4(), "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    # Old lease expires → new worker takes over
    db_session.execute(text("DELETE FROM leases WHERE run_id = :rid"), {"rid": rid})
    lid2 = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-2', :exp)"
    ), {"id": lid2, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT fencing_token, worker_id FROM leases WHERE id = :id"
    ), {"id": lid2}).fetchone()
    assert row[0] == 1
    assert row[1] == "worker-2"


def test_fencing_token_not_directly_modifiable(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'pending', 'schedule', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": uuid4(), "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    with pytest.raises(Exception, match="fencing_token"):
        db_session.execute(text("UPDATE leases SET fencing_token = 999"))
        db_session.commit()


def test_attempt_unique_per_run(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'pending', 'manual', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number)"
        " VALUES (:id, :rid, 1)"
    ), {"id": uuid4(), "rid": rid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number)"
            " VALUES (:id, :rid, 1)"
        ), {"id": uuid4(), "rid": rid})
        db_session.commit()


# ── Attempt immutability ──


def test_attempt_terminal_state_cannot_revert(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    aid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'running', 'manual', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'succeeded')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE attempts SET status = 'running' WHERE id = :id"
        ), {"id": aid})
        db_session.commit()


def test_attempt_deletion_forbidden(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = uuid4()
    aid = uuid4()
    now = _now()
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'running', 'manual', :sa, :hid)"
    ), {"id": rid, "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
        "sa": now, "hid": hid})
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'succeeded')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    with pytest.raises(Exception, match="deletion_forbidden"):
        db_session.execute(text("DELETE FROM attempts WHERE id = :id"), {"id": aid})
        db_session.commit()


# ── Concurrency: overlap with barrier ──


def test_concurrent_active_run_insertion(postgres_engine: Engine, db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = _setup_schedule(db_session, jid)
    now = _now()

    engine = postgres_engine
    barrier = threading.Barrier(2, timeout=5)
    results: list[str] = []

    def _insert_run() -> None:
        with engine.connect() as c:
            barrier.wait()
            try:
                c.execute(text(
                    "INSERT INTO runs"
                    " (id, job_definition_id, schedule_id, idempotency_key,"
                    " status, triggered_by, scheduled_at, household_id)"
                    " VALUES (:id, :jid, :sid, :ik, 'pending', 'schedule', :sa, :hid)"
                ), {
                    "id": uuid4(), "jid": jid, "sid": sid,
                    "ik": _idempotency_key("guardian.evaluate_all", now),
                    "sa": now, "hid": hid,
                })
                c.commit()
                results.append("inserted")
            except Exception:
                results.append("conflict")

    t1 = threading.Thread(target=_insert_run)
    t2 = threading.Thread(target=_insert_run)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results.count("inserted") == 1
    assert results.count("conflict") == 1
