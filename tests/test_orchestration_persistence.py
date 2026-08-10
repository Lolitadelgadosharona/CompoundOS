"""Sprint 005 Slice A — Final fencing semantics tests (migration 0011)."""

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


def _setup_job(session: Session, hid: str) -> str:
    jid = uuid4()
    session.execute(text(
        "INSERT INTO job_definitions (id, household_id, job_type)"
        " VALUES (:id, :hid, 'guardian.evaluate_all')"
    ), {"id": jid, "hid": hid})
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


def _setup_run(session: Session, hid: str, jid: str, *,
               sid: Optional[str] = None, status: str = "pending",
               triggered_by: str = "schedule") -> str:
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


# ── Migration ──


def test_migration_head_is_0016(postgres_engine: Engine) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0020_investment_idea_bridge"


# ── CHECK constraints ──


def test_check_runs_status_rejects_invalid(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "UPDATE runs SET status = 'unknown' WHERE id = :id"), {"id": rid})
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


def test_check_attempts_status_rejects_invalid(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="pending")
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'completed')"
        ), {"id": uuid4(), "rid": rid})
        db_session.commit()


def test_check_attempts_attempt_number_positive(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number)"
            " VALUES (:id, :rid, 0)"), {"id": uuid4(), "rid": rid})
        db_session.commit()


def test_check_attempts_attempt_number_negative(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number)"
            " VALUES (:id, :rid, -1)"), {"id": uuid4(), "rid": rid})
        db_session.commit()


# ── Full terminal immutability ──


def test_run_terminal_fully_immutable(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="completed")
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE runs SET scheduled_at = :sa WHERE id = :id"
        ), {"id": rid, "sa": _now()})
        db_session.commit()


def test_run_terminal_immutable_status_and_household(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="completed")
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE runs SET status = 'pending' WHERE id = :id"), {"id": rid})
        db_session.commit()


def test_run_terminal_immutable_timestamp(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="failed")
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE runs SET started_at = :sa WHERE id = :id"
        ), {"id": rid, "sa": _now()})
        db_session.commit()


def test_attempt_terminal_fully_immutable(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    aid = uuid4()
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'succeeded')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE attempts SET error_message = 'x' WHERE id = :id"), {"id": aid})
        db_session.commit()


def test_attempt_terminal_immutable_status(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    aid = uuid4()
    db_session.execute(text(
        "INSERT INTO attempts (id, run_id, attempt_number, status)"
        " VALUES (:id, :rid, 1, 'succeeded')"
    ), {"id": aid, "rid": rid})
    db_session.commit()
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE attempts SET status = 'pending' WHERE id = :id"), {"id": aid})
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


# ── Overlap + Idempotency ──


def test_overlap_active_run_partial_index_only(db_session: Session) -> None:
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

    assert results.count("inserted") == 1
    assert results.count("conflict") == 1


def test_idempotency_key_unique_independent(db_session: Session) -> None:
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


# ── Lease Fencing v4: Application Atomic Takeover Contract ──

_TAKEOVER_SQL = (
    "UPDATE leases SET"
    " fencing_token = fencing_token + 1,"
    " worker_id = :wid,"
    " acquired_at = :as_of,"
    " heartbeat_at = :as_of,"
    " expires_at = :new_exp,"
    " released_at = NULL"
    " WHERE id = :lid"
    " AND fencing_token = :base"
    " AND expires_at <= :as_of"
    " RETURNING fencing_token"
)

_HEARTBEAT_SQL = (
    "UPDATE leases SET heartbeat_at = :as_of"
    " WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
    " AND released_at IS NULL AND expires_at > :as_of"
)

_FINALIZE_SQL = (
    "UPDATE runs SET status = :st, completed_at = :as_of"
    " WHERE id = :rid AND EXISTS ("
    "  SELECT 1 FROM leases"
    "  WHERE id = :lid AND worker_id = :wid AND fencing_token = :token"
    "  AND released_at IS NULL AND expires_at > :as_of"
    " )"
)


def _run_takeover(session, lid, wid, base, as_of, new_exp):
    return session.execute(text(_TAKEOVER_SQL), {
        "lid": lid, "wid": wid, "base": base,
        "as_of": as_of, "new_exp": new_exp,
    })


def _run_heartbeat(session, lid, wid, token, as_of):
    return session.execute(text(_HEARTBEAT_SQL), {
        "lid": lid, "wid": wid, "token": token, "as_of": as_of,
    })


def _run_finalize(session, rid, lid, wid, token, st, as_of):
    return session.execute(text(_FINALIZE_SQL), {
        "rid": rid, "lid": lid, "wid": wid, "token": token,
        "st": st, "as_of": as_of,
    })


# ── Takeover complete window refresh ──


def test_takeover_unexpired_rejected_rowcount_zero(db_session: Session) -> None:
    """M-1: application WHERE with expiry — unexpired returns rowcount=0."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    future_exp = as_of + timedelta(hours=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": future_exp, "now": as_of})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]

    new_exp = as_of + timedelta(seconds=60)
    result = _run_takeover(db_session, lid, "w2", token, as_of, new_exp)
    db_session.commit()
    # Unexpired lease: WHERE expires_at <= as_of fails → rowcount=0
    assert result.rowcount == 0


def test_takeover_expired_refreshes_window(db_session: Session) -> None:
    """Expired takeover refreshes complete lease window."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]

    new_exp = as_of + timedelta(seconds=60)
    result = _run_takeover(db_session, lid, "w2", token, as_of, new_exp)
    db_session.commit()
    assert result.rowcount == 1
    new_token = result.fetchone()[0]
    assert new_token == token + 1

    # Verify complete window refresh
    row = db_session.execute(text(
        "SELECT worker_id, fencing_token, acquired_at, heartbeat_at,"
        " expires_at, released_at FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert row[0] == "w2"
    assert row[1] == new_token
    assert row[2] is not None  # acquired_at refreshed
    assert row[3] is not None  # heartbeat_at refreshed
    assert row[4] > as_of  # expires_at is future
    assert row[5] is None  # released_at is NULL


def test_takeover_noop_token_only_bump_rejected(db_session: Session) -> None:
    """M-2: token increment without window refresh is rejected."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    # Token-only bump: no window refresh
    with pytest.raises(Exception, match="incomplete"):
        db_session.execute(text(
            "UPDATE leases SET fencing_token = fencing_token + 1 WHERE id = :id"
        ), {"id": lid})
        db_session.commit()


def test_takeover_same_worker_reacquire(db_session: Session) -> None:
    """Same worker reacquire with full window refresh."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]

    new_exp = as_of + timedelta(seconds=60)
    result = _run_takeover(db_session, lid, "w1", token, as_of, new_exp)
    db_session.commit()
    assert result.rowcount == 1
    assert result.fetchone()[0] == token + 1


def test_worker_id_without_token_rejected(db_session: Session) -> None:
    """F-2: worker_id change without token increment rejected."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": as_of + timedelta(seconds=60), "now": as_of})
    db_session.commit()
    with pytest.raises(Exception, match="worker_id"):
        db_session.execute(text(
            "UPDATE leases SET worker_id = 'rogue' WHERE id = :id"), {"id": lid})
        db_session.commit()


# ── Expired-holder protection ──


def test_expired_holder_heartbeat_zero(db_session: Session) -> None:
    """Heartbeat on expired lease → 0 rows."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    result = _run_heartbeat(db_session, lid, "w1", token, as_of)
    assert result.rowcount == 0


def test_unexpired_holder_heartbeat_one(db_session: Session) -> None:
    """Heartbeat on unexpired lease → 1 row."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    future_exp = as_of + timedelta(seconds=60)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": future_exp, "now": as_of})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    result = _run_heartbeat(db_session, lid, "w1", token, as_of)
    assert result.rowcount == 1


def test_expired_holder_finalize_zero(db_session: Session) -> None:
    """Finalize on expired lease → 0 rows."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    result = _run_finalize(db_session, rid, lid, "w1", token, "completed", as_of)
    assert result.rowcount == 0


def test_unexpired_holder_finalize_one(db_session: Session) -> None:
    """Finalize on unexpired lease → 1 row, run transitions."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    as_of = _now()
    future_exp = as_of + timedelta(seconds=60)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": future_exp, "now": as_of})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    result = _run_finalize(db_session, rid, lid, "w1", token, "completed", as_of)
    assert result.rowcount == 1
    row = db_session.execute(text(
        "SELECT status, completed_at FROM runs WHERE id = :rid"), {"rid": rid}).fetchone()
    assert row[0] == "completed"
    assert row[1] is not None


def test_stale_token_heartbeat_zero(db_session: Session) -> None:
    """Stale token heartbeat → 0 rows."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    base = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    # Takeover: w2 gets token 2
    new_exp = as_of + timedelta(seconds=60)
    _run_takeover(db_session, lid, "w2", base, as_of, new_exp)
    db_session.commit()
    # Stale w1 heartbeat with token 1 → 0 rows
    result = _run_heartbeat(db_session, lid, "w1", base, as_of)
    assert result.rowcount == 0


def test_stale_token_finalize_zero(db_session: Session) -> None:
    """Stale token finalize → 0 rows."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    base = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    new_exp = as_of + timedelta(seconds=60)
    _run_takeover(db_session, lid, "w2", base, as_of, new_exp)
    db_session.commit()
    result = _run_finalize(db_session, rid, lid, "w1", base, "completed", as_of)
    assert result.rowcount == 0


def test_released_lease_heartbeat_zero(db_session: Session) -> None:
    """Heartbeat on released lease → 0 rows."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    future_exp = as_of + timedelta(seconds=60)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at,"
        " released_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": future_exp, "now": as_of})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    result = _run_heartbeat(db_session, lid, "w1", token, as_of)
    assert result.rowcount == 0


# ── Boundary: expires_at = now() ──


def test_takeover_expires_at_equals_now_allowed(db_session: Session) -> None:
    """L-1: expires_at exactly equals now() → takeover allowed."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    exact_exp = as_of  # exactly at boundary
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'w1', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": exact_exp, "now": exact_exp})
    db_session.commit()
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]
    new_exp = as_of + timedelta(seconds=60)
    result = _run_takeover(db_session, lid, "w2", token, as_of, new_exp)
    db_session.commit()
    assert result.rowcount == 1


# ── Concurrent takeover with expiry predicate ──


def test_concurrent_takeover_one_winner(db_session: Session) -> None:
    """Two workers race with expiry predicate → exactly one winner."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    as_of = _now()
    past_exp = as_of - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases"
        " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
        " VALUES (:id, :rid, 'original', :exp, :now, :now)"
    ), {"id": lid, "rid": rid, "exp": past_exp, "now": past_exp})
    db_session.commit()
    base = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"), {"id": lid}).fetchone()[0]

    engine = db_session.get_bind()
    barrier = threading.Barrier(2, timeout=5)
    results: list[str] = []

    def _takeover(wid: str) -> None:
        with engine.connect() as c:
            barrier.wait()
            try:
                new_exp_val = as_of + timedelta(seconds=60)
                result = c.execute(text(_TAKEOVER_SQL), {
                    "lid": lid, "wid": wid, "base": base,
                    "as_of": as_of, "new_exp": new_exp_val,
                })
                c.commit()
                if result.rowcount > 0:
                    results.append(f"won:{wid}")
                else:
                    results.append(f"lost:{wid}")
            except Exception:
                results.append(f"error:{wid}")

    t1 = threading.Thread(target=_takeover, args=("worker-a",))
    t2 = threading.Thread(target=_takeover, args=("worker-b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    winners = [r for r in results if r.startswith("won:")]
    losers = [r for r in results if r.startswith("lost:")]
    assert len(winners) == 1, f"Expected 1 winner, got: {results}"
    assert len(losers) == 1, f"Expected 1 loser, got: {results}"

    row = db_session.execute(text(
        "SELECT fencing_token, worker_id FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert row[0] == base + 1
    assert row[1] in ("worker-a", "worker-b")


# ── Schedule / timezone ──


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
        "SELECT enabled FROM schedules WHERE id = :sid"), {"sid": sid}).fetchone()
    assert row[0] is False


def test_schedule_one_per_job(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    _setup_schedule(db_session, jid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO schedules"
            " (id, job_definition_id, execution_time, timezone, next_run_at)"
            " VALUES (:id, :jid, '10:00', 'UTC', :nr)"
        ), {"id": uuid4(), "jid": jid, "nr": _now()})
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
        "SELECT timezone FROM schedules WHERE id = :sid"), {"sid": sid}).fetchone()
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
        "SELECT next_run_at FROM schedules WHERE id = :sid"), {"sid": sid}).fetchone()
    assert row[0] is not None
    assert row[0].tzinfo is not None


def test_disabled_schedule_identifiable(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = _setup_schedule(db_session, jid)
    row = db_session.execute(text(
        "SELECT enabled FROM schedules WHERE id = :sid"), {"sid": sid}).fetchone()
    assert row[0] is False


def test_job_allowlist_accepts(db_session: Session) -> None:
    hid = _setup_household(db_session)
    for jt in ("guardian.evaluate_all", "guardian.evaluate_one"):
        db_session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, :jt)"
        ), {"id": uuid4(), "hid": hid, "jt": jt})
    db_session.commit()


def test_job_allowlist_rejects(db_session: Session) -> None:
    hid = _setup_household(db_session)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'shell.run')"
        ), {"id": uuid4(), "hid": hid})
        db_session.commit()
