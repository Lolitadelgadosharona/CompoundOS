"""Sprint 005 Slice A — Orchestration persistence tests."""

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


# ── Migration (verified by interaction tests — tables must exist for INSERTs) ──


def test_migration_head_is_0008(postgres_engine: Engine) -> None:
    """Alembic head must be 0008 — interaction tests prove migration applied."""
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0008_orchestration_foundation"


# ── Allowlist ──


def test_job_allowlist_rejects_unknown_type(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": uuid4(), "hid": hid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'shell.run')"), {"id": uuid4(), "hid": hid})
        db_session.commit()


def test_job_allowlist_accepts_approved_types(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    for jt in ("guardian.evaluate_all", "guardian.evaluate_one"):
        db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, :jt)"), {"id": uuid4(), "hid": hid, "jt": jt})
    db_session.commit()


# ── Schedule defaults ──


def test_schedule_enabled_defaults_false(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO schedules (id, job_definition_id, execution_time, timezone, next_run_at) VALUES (:id, :jid, '09:00', 'UTC', :nr)"), {"id": uuid4(), "jid": jid, "nr": _now()})
    db_session.commit()
    row = db_session.execute(text("SELECT enabled FROM schedules WHERE job_definition_id = :jid"), {"jid": jid}).fetchone()
    assert row[0] is False


def test_schedule_one_per_job(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO schedules (id, job_definition_id, execution_time, timezone, next_run_at) VALUES (:id, :jid, '09:00', 'UTC', :nr)"), {"id": uuid4(), "jid": jid, "nr": _now()})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text("INSERT INTO schedules (id, job_definition_id, execution_time, timezone, next_run_at) VALUES (:id, :jid, '10:00', 'UTC', :nr)"), {"id": uuid4(), "jid": jid, "nr": _now()})
        db_session.commit()


# ── Run lifecycle ──


def test_run_terminal_state_cannot_revert(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    rid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, 'completed', 'manual', :sa, :hid)"), {"id": rid, "jid": jid, "sa": _now(), "hid": hid})
    db_session.commit()
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text("UPDATE runs SET status = 'running' WHERE id = :id"), {"id": rid})
        db_session.commit()


def test_run_deletion_forbidden(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    rid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, 'completed', 'manual', :sa, :hid)"), {"id": rid, "jid": jid, "sa": _now(), "hid": hid})
    db_session.commit()
    with pytest.raises(Exception, match="deletion_forbidden"):
        db_session.execute(text("DELETE FROM runs WHERE id = :id"), {"id": rid})
        db_session.commit()


# ── Overlap prevention ──


def test_overlap_one_active_run_per_schedule(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    sid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO schedules (id, job_definition_id, execution_time, timezone, next_run_at) VALUES (:id, :jid, '09:00', 'UTC', :nr)"), {"id": sid, "jid": jid, "nr": _now()})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, schedule_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, :sid, 'running', 'schedule', :sa, :hid)"), {"id": uuid4(), "jid": jid, "sid": sid, "sa": _now(), "hid": hid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text("INSERT INTO runs (id, job_definition_id, schedule_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, :sid, 'pending', 'schedule', :sa, :hid)"), {"id": uuid4(), "jid": jid, "sid": sid, "sa": _now(), "hid": hid})
        db_session.commit()


def test_overlap_allows_different_schedules(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    for _ in range(2):
        jid = uuid4()
        sid = uuid4()
        db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
        db_session.execute(text("INSERT INTO schedules (id, job_definition_id, execution_time, timezone, next_run_at) VALUES (:id, :jid, '09:00', 'UTC', :nr)"), {"id": sid, "jid": jid, "nr": _now()})
        db_session.execute(text("INSERT INTO runs (id, job_definition_id, schedule_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, :sid, 'running', 'schedule', :sa, :hid)"), {"id": uuid4(), "jid": jid, "sid": sid, "sa": _now(), "hid": hid})
    db_session.commit()


# ── Lease / Fencing ──


def test_lease_first_acquisition_token_1(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    rid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, 'pending', 'schedule', :sa, :hid)"), {"id": rid, "jid": jid, "sa": _now(), "hid": hid})
    lid = uuid4()
    db_session.execute(text("INSERT INTO leases (id, run_id, worker_id, expires_at) VALUES (:id, :rid, 'worker-1', :exp)"), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    row = db_session.execute(text("SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()
    assert row[0] == 1


def test_lease_takeover_after_expiry_gets_fresh_token(db_session: Session) -> None:
    """After old lease is deleted (expired), new lease starts at token 1."""
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    rid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, 'pending', 'schedule', :sa, :hid)"), {"id": rid, "jid": jid, "sa": _now(), "hid": hid})
    # First worker acquires lease
    db_session.execute(text("INSERT INTO leases (id, run_id, worker_id, expires_at) VALUES (:id, :rid, 'worker-1', :exp)"), {"id": uuid4(), "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    # Old lease expires → new worker takes over (delete old, insert new)
    db_session.execute(text("DELETE FROM leases WHERE run_id = :rid"), {"rid": rid})
    lid2 = uuid4()
    db_session.execute(text("INSERT INTO leases (id, run_id, worker_id, expires_at) VALUES (:id, :rid, 'worker-2', :exp)"), {"id": lid2, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    row = db_session.execute(text("SELECT fencing_token, worker_id FROM leases WHERE id = :id"), {"id": lid2}).fetchone()
    assert row[0] == 1  # Fresh lease after expiry, token resets
    assert row[1] == "worker-2"


def test_fencing_token_not_directly_modifiable(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    rid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, 'pending', 'schedule', :sa, :hid)"), {"id": rid, "jid": jid, "sa": _now(), "hid": hid})
    db_session.execute(text("INSERT INTO leases (id, run_id, worker_id, expires_at) VALUES (:id, :rid, 'worker-1', :exp)"), {"id": uuid4(), "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    with pytest.raises(Exception, match="fencing_token"):
        db_session.execute(text("UPDATE leases SET fencing_token = 999"))
        db_session.commit()


def test_attempt_unique_per_run(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    rid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO runs (id, job_definition_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, 'pending', 'manual', :sa, :hid)"), {"id": rid, "jid": jid, "sa": _now(), "hid": hid})
    db_session.execute(text("INSERT INTO attempts (id, run_id, attempt_number) VALUES (:id, :rid, 1)"), {"id": uuid4(), "rid": rid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text("INSERT INTO attempts (id, run_id, attempt_number) VALUES (:id, :rid, 1)"), {"id": uuid4(), "rid": rid})
        db_session.commit()


# ── Concurrency: overlap with barrier ──


def test_concurrent_active_run_insertion(db_session: Session) -> None:
    db_session.execute(text("INSERT INTO household_profiles (id, singleton_key, household_name, base_currency, investment_horizon, liquidity_needs, risk_statement, notes) VALUES (:id, TRUE, 'T', 'USD', 'L', '', '', '')"), {"id": uuid4()})
    hid = db_session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()[0]
    jid = uuid4()
    sid = uuid4()
    db_session.execute(text("INSERT INTO job_definitions (id, household_id, job_type) VALUES (:id, :hid, 'guardian.evaluate_all')"), {"id": jid, "hid": hid})
    db_session.execute(text("INSERT INTO schedules (id, job_definition_id, execution_time, timezone, next_run_at) VALUES (:id, :jid, '09:00', 'UTC', :nr)"), {"id": sid, "jid": jid, "nr": _now()})
    db_session.commit()

    engine = db_session.get_bind()
    barrier = threading.Barrier(2, timeout=5)
    results: list[str] = []

    def _insert_run() -> None:
        with engine.connect() as c:
            barrier.wait()
            try:
                c.execute(text("INSERT INTO runs (id, job_definition_id, schedule_id, status, triggered_by, scheduled_at, household_id) VALUES (:id, :jid, :sid, 'pending', 'schedule', :sa, :hid)"), {"id": uuid4(), "jid": jid, "sid": sid, "sa": _now(), "hid": hid})
                c.commit()
                results.append("inserted")
            except Exception:
                results.append("conflict")

    t1 = threading.Thread(target=_insert_run)
    t2 = threading.Thread(target=_insert_run)
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert results.count("inserted") == 1
    assert results.count("conflict") == 1
