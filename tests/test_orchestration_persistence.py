"""Sprint 005 Slice A — Orchestration persistence hardening tests."""

import hashlib
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _idempotency_key(job_type: str, scheduled_at: datetime) -> str:
    """Deterministic idempotency key per Technical Design §8 — date-only."""
    scheduled_date = scheduled_at.date().isoformat()
    payload = f"{job_type}||{scheduled_date}"
    return hashlib.sha256(payload.encode()).hexdigest()


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


def _setup_job(session: Session, hid: str, job_type: str = "guardian.evaluate_all") -> str:
    jid = uuid4()
    session.execute(text(
        "INSERT INTO job_definitions (id, household_id, job_type)"
        " VALUES (:id, :hid, :jt)"
    ), {"id": jid, "hid": hid, "jt": job_type})
    session.commit()
    return str(jid)


def _setup_schedule(session: Session, jid: str) -> str:
    sid = uuid4()
    session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'UTC', :nr)"
    ), {"id": sid, "jid": jid, "nr": _now()})
    session.commit()
    return str(sid)


def _setup_run(
    session: Session,
    hid: str,
    jid: str,
    *,
    sid: Optional[str] = None,
    status: str = "pending",
    triggered_by: str = "schedule",
) -> str:
    rid = uuid4()
    now = _now()
    session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, schedule_id, idempotency_key, status,"
        " triggered_by, scheduled_at, household_id)"
        " VALUES (:id, :jid, :sid, :ik, :st, :tb, :sa, :hid)"
    ), {
        "id": rid, "jid": jid, "sid": sid,
        "ik": _idempotency_key("guardian.evaluate_all", now),
        "st": status, "tb": triggered_by, "sa": now, "hid": hid,
    })
    session.commit()
    return str(rid)


def _setup_lease(session: Session, rid: str, worker_id: str) -> int:
    lid = uuid4()
    exp = _now() + timedelta(seconds=60)
    session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, :wid, :exp)"
    ), {"id": lid, "rid": rid, "wid": worker_id, "exp": exp})
    session.commit()
    row = session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    return row[0]


# ── Migration ──


def test_migration_head_is_0009(postgres_engine: Engine) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0009_hardening"


# ── CHECK constraints ──


def test_check_runs_status_rejects_invalid(db_session: Session) -> None:
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
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text(
            "UPDATE runs SET status = 'unknown' WHERE id = :id"
        ), {"id": rid})
        db_session.commit()


def test_check_runs_triggered_by_rejects_invalid(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    now = _now()
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'pending', 'api', :sa, :hid)"
        ), {"id": uuid4(), "jid": jid, "ik": _idempotency_key("guardian.evaluate_all", now),
            "sa": now, "hid": hid})
        db_session.commit()


def test_check_attempts_attempt_number_positive(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number)"
            " VALUES (:id, :rid, 0)"
        ), {"id": uuid4(), "rid": rid})
        db_session.commit()


# ── Full terminal immutability (v2: entire row frozen) ──


def test_run_terminal_fully_immutable(db_session: Session) -> None:
    """Terminal runs reject ANY field modification, not just status."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="completed")
    # Attempt to modify any column — must be rejected
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE runs SET scheduled_at = :sa WHERE id = :id"
        ), {"id": rid, "sa": _now()})
        db_session.commit()


def test_attempt_terminal_fully_immutable(db_session: Session) -> None:
    """Terminal attempts reject ANY field modification, not just status."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    aid = uuid4()
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'succeeded')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    # Attempt to modify error_message — must be rejected
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE attempts SET error_message = 'x' WHERE id = :id"
        ), {"id": aid})
        db_session.commit()


def test_run_deletion_forbidden(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="completed")
    with pytest.raises(Exception, match="deletion_forbidden"):
        db_session.execute(text("DELETE FROM runs WHERE id = :id"), {"id": rid})
        db_session.commit()


def test_attempt_deletion_forbidden(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    aid = uuid4()
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'succeeded')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    with pytest.raises(Exception, match="deletion_forbidden"):
        db_session.execute(text("DELETE FROM attempts WHERE id = :id"), {"id": aid})
        db_session.commit()


# ── Overlap: partial unique index (isolated from idempotency) ──


def test_overlap_active_run_partial_index_only(db_session: Session) -> None:
    """Two threads, same schedule, DIFFERENT idempotency_keys.
    Exactly one wins; conflict is from the partial unique index only."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = _setup_schedule(db_session, jid)
    now = _now()
    engine = db_session.get_bind()

    barrier = threading.Barrier(2, timeout=5)
    results: list[str] = []

    def _insert(offset: int) -> None:
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
                    "ik": _idempotency_key(f"guardian.evaluate_all:{offset}", now),
                    "sa": now, "hid": hid,
                })
                c.commit()
                results.append("inserted")
            except Exception:
                results.append("conflict")

    t1 = threading.Thread(target=_insert, args=(0,))
    t2 = threading.Thread(target=_insert, args=(1,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results.count("inserted") == 1, (
        f"Expected exactly 1 insert, got: {results}"
    )
    assert results.count("conflict") == 1


# ── Idempotency: unique constraint (isolated from overlap) ──


def test_idempotency_key_unique_independent(db_session: Session) -> None:
    """Same idempotency_key, no schedule — rejected by uq_runs_idempotency_key."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    now = _now()
    ikey = _idempotency_key("guardian.evaluate_all", now)
    db_session.execute(text(
        "INSERT INTO runs"
        " (id, job_definition_id, idempotency_key, status, triggered_by,"
        " scheduled_at, household_id)"
        " VALUES (:id, :jid, :ik, 'pending', 'manual', :sa, :hid)"
    ), {"id": uuid4(), "jid": jid, "ik": ikey, "sa": now, "hid": hid})
    db_session.commit()
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'pending', 'manual', :sa, :hid)"
        ), {"id": uuid4(), "jid": jid, "ik": ikey, "sa": now, "hid": hid})
        db_session.commit()


# ── Fencing token: monotonic takeover chain ──


def test_fencing_token_takeover_chain_1_2_3(db_session: Session) -> None:
    """Sequential atomic takeovers: token 1 → 2 → 3, strictly monotonic."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)

    # First worker acquires lease (token 1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    t1 = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()[0]
    assert t1 == 1

    # Takeover 1: atomic UPDATE — inc token, change worker
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    t2 = db_session.execute(text(
        "SELECT fencing_token, worker_id FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert t2[0] == 2
    assert t2[1] == "worker-2"

    # Takeover 2: atomic UPDATE — inc token, change worker
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-3'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    t3 = db_session.execute(text(
        "SELECT fencing_token, worker_id FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert t3[0] == 3
    assert t3[1] == "worker-3"


# ── Stale token protection: atomic conditional SQL ──


def test_stale_token_heartbeat_zero_rows(db_session: Session) -> None:
    """Heartbeat with stale token affects 0 rows; current token succeeds."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)

    # Worker 1 acquires lease (token 1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()

    # Takeover: Worker 2 atomically takes over (token 2)
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()

    # Stale heartbeat (token 1) — must affect 0 rows
    result = db_session.execute(text(
        "UPDATE leases SET heartbeat_at = NOW()"
        " WHERE id = :id AND fencing_token = :token"
    ), {"id": lid, "token": 1})
    assert result.rowcount == 0  # stale token rejected

    # Current heartbeat (token 2) — must succeed
    result = db_session.execute(text(
        "UPDATE leases SET heartbeat_at = NOW()"
        " WHERE id = :id AND fencing_token = :token"
    ), {"id": lid, "token": 2})
    assert result.rowcount == 1


def test_stale_token_finalize_zero_rows(db_session: Session) -> None:
    """Finalize with stale token must not change run/attempt state."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")

    # Worker 1 acquires lease, inserts attempt
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    aid = uuid4()
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'running')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    token1 = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()[0]

    # Takeover: Worker 2 atomically takes over (token 2 > token 1)
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    token2 = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()[0]
    assert token2 > token1  # monotonic

    # Stale worker (token 1) tries to finalize — must affect 0 rows
    result = db_session.execute(text(
        "UPDATE runs SET status = 'completed', completed_at = NOW()"
        " WHERE id = :rid AND EXISTS ("
        "  SELECT 1 FROM leases"
        "  WHERE id = :lid AND fencing_token = :token"
        " )"
    ), {"rid": rid, "lid": lid, "token": token1})
    assert result.rowcount == 0  # stale token rejected

    # Current worker (token 2) finalizes — must succeed
    result = db_session.execute(text(
        "UPDATE runs SET status = 'completed', completed_at = NOW()"
        " WHERE id = :rid AND EXISTS ("
        "  SELECT 1 FROM leases"
        "  WHERE id = :lid AND fencing_token = :token"
        " )"
    ), {"rid": rid, "lid": lid, "token": token2})
    assert result.rowcount == 1, "Current token finalize must succeed"

    # Verify run actually transitioned
    row = db_session.execute(text(
        "SELECT status, completed_at FROM runs WHERE id = :rid"
    ), {"rid": rid}).fetchone()
    assert row[0] == "completed"
    assert row[1] is not None


# ── Schedule / timezone verification ──


def test_schedule_enabled_default_false(db_session: Session) -> None:
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
    assert row[0] is False, "Schedule must default to disabled"


def test_schedule_one_per_job(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    _setup_schedule(db_session, jid)
    with pytest.raises(Exception):
        sid2 = uuid4()
        db_session.execute(text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at)"
            " VALUES (:id, :jid, '10:00', 'UTC', :nr)"
        ), {"id": sid2, "jid": jid, "nr": _now()})
        db_session.commit()


def test_schedule_valid_iana_timezone_accepted(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = uuid4()
    db_session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'America/New_York', :nr)"
    ), {"id": sid, "jid": jid, "nr": _now()})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT timezone FROM schedules WHERE id = :sid"
    ), {"sid": sid}).fetchone()
    assert row[0] == "America/New_York"


def test_schedule_next_run_at_is_timestamptz(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    now = _now()
    sid = uuid4()
    db_session.execute(text(
        "INSERT INTO schedules"
        " (id, job_definition_id, execution_time, timezone, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'UTC', :nr)"
    ), {"id": sid, "jid": jid, "nr": now})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT next_run_at FROM schedules WHERE id = :sid"
    ), {"sid": sid}).fetchone()
    assert row[0] is not None
    assert row[0].tzinfo is not None, "next_run_at must be timezone-aware"


def test_disabled_schedule_identifiable(db_session: Session) -> None:
    """A disabled schedule can be distinguished from an enabled one."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = _setup_schedule(db_session, jid)
    # Verify it's disabled
    row = db_session.execute(text(
        "SELECT enabled FROM schedules WHERE id = :sid"
    ), {"sid": sid}).fetchone()
    assert row[0] is False


def test_job_allowlist_accepts_approved_types(db_session: Session) -> None:
    hid = _setup_household(db_session)
    for jt in ("guardian.evaluate_all", "guardian.evaluate_one"):
        db_session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, :jt)"
        ), {"id": uuid4(), "hid": hid, "jt": jt})
    db_session.commit()


def test_job_allowlist_rejects_unknown(db_session: Session) -> None:
    hid = _setup_household(db_session)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'shell.run')"
        ), {"id": uuid4(), "hid": hid})
        db_session.commit()
