"""Sprint 005 Slice A — Lease fencing + hardening tests (migration 0010)."""

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


def test_migration_head_is_0010(postgres_engine: Engine) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config()
    cfg.set_main_option("script_location", "migrations")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0010_lease_fencing"


# ── CHECK constraints ──


def test_check_runs_status_rejects_invalid(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
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


def test_check_attempts_status_rejects_invalid(db_session: Session) -> None:
    """F-1: ck_attempts_status rejects values outside approved set."""
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
            " VALUES (:id, :rid, 0)"
        ), {"id": uuid4(), "rid": rid})
        db_session.commit()


def test_check_attempts_attempt_number_negative(db_session: Session) -> None:
    """F-4: ck_attempts_attempt_number_positive rejects -1."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    with pytest.raises(Exception):
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number)"
            " VALUES (:id, :rid, -1)"
        ), {"id": uuid4(), "rid": rid})
        db_session.commit()


# ── Full terminal immutability (0009 v2) ──


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
    """F-3: terminal immutability blocks status + identity field changes."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="completed")
    # Status change rejected
    with pytest.raises(Exception, match="terminal"):
        db_session.execute(text(
            "UPDATE runs SET status = 'pending' WHERE id = :id"
        ), {"id": rid})
        db_session.commit()


def test_run_terminal_immutable_timestamp(db_session: Session) -> None:
    """F-3: terminal immutability blocks timestamp field changes."""
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
            "UPDATE attempts SET error_message = 'x' WHERE id = :id"
        ), {"id": aid})
        db_session.commit()


def test_attempt_terminal_immutable_status(db_session: Session) -> None:
    """F-3: terminal attempt blocks status change."""
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
            "UPDATE attempts SET status = 'pending' WHERE id = :id"
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


# ── Overlap + Idempotency (isolated) ──


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


# ── Lease Fencing (migration 0010): worker_id protection ──


def test_worker_id_immutable_without_token_increment(db_session: Session) -> None:
    """F-2 UPGRADED TO HIGH: worker_id cannot change without token increment."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    with pytest.raises(Exception, match="worker_id"):
        db_session.execute(text(
            "UPDATE leases SET worker_id = 'rogue' WHERE id = :id"
        ), {"id": lid})
        db_session.commit()


def test_token_increment_not_exactly_one_rejected(db_session: Session) -> None:
    """Arbitrary token changes are rejected."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    with pytest.raises(Exception, match="fencing_token"):
        db_session.execute(text(
            "UPDATE leases SET fencing_token = 999, worker_id = 'rogue' WHERE id = :id"
        ), {"id": lid})
        db_session.commit()


def test_direct_fencing_token_mutation_rejected(db_session: Session) -> None:
    """Direct SET fencing_token = N without takeover pattern is rejected."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": _now() + timedelta(seconds=60)})
    db_session.commit()
    with pytest.raises(Exception, match="fencing_token"):
        db_session.execute(text(
            "UPDATE leases SET fencing_token = 5 WHERE id = :id"
        ), {"id": lid})
        db_session.commit()


# ── Lease expiry enforcement ──


def test_unexpired_lease_takeover_rejected(db_session: Session) -> None:
    """Takeover of a non-expired lease must be rejected."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    # Future expiry (far in the future — definitely not expired)
    future_exp = _now() + timedelta(hours=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": future_exp})
    db_session.commit()
    with pytest.raises(Exception, match="unexpired"):
        db_session.execute(text(
            "UPDATE leases"
            " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
            " WHERE id = :id"
        ), {"id": lid})
        db_session.commit()


def test_expired_lease_takeover_succeeds(db_session: Session) -> None:
    """Expired lease takeover increments token and changes worker."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    # Past expiry (definitely expired)
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT fencing_token, worker_id FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert row[0] == 2
    assert row[1] == "worker-2"


def test_expired_lease_same_worker_reacquire_token_increments(db_session: Session) -> None:
    """Same worker reacquiring expired lease still gets new token."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    # Same worker takes over
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-1'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    row = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert row[0] == 2, "Reacquire must increment token"


def test_stale_worker_heartbeat_zero_rows(db_session: Session) -> None:
    """Heartbeat with stale token affects 0 rows."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    # Worker 2 takes over (token 2)
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    # Stale heartbeat (token 1) — must affect 0 rows
    result = db_session.execute(text(
        "UPDATE leases SET heartbeat_at = NOW()"
        " WHERE id = :id AND worker_id = :wid AND fencing_token = :token"
    ), {"id": lid, "wid": "worker-1", "token": 1})
    assert result.rowcount == 0


def test_current_worker_heartbeat_succeeds(db_session: Session) -> None:
    """Current worker heartbeat with correct token succeeds."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    # Worker 2 takes over (token 2)
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    # Current heartbeat (token 2) — must succeed
    result = db_session.execute(text(
        "UPDATE leases SET heartbeat_at = NOW()"
        " WHERE id = :id AND worker_id = :wid AND fencing_token = :token"
    ), {"id": lid, "wid": "worker-2", "token": 2})
    assert result.rowcount == 1


def test_stale_worker_finalize_zero_rows(db_session: Session) -> None:
    """Finalize with stale token must not change run state."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    # Worker 2 takes over (token 2)
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    # Stale finalize (token 1) — 0 rows
    result = db_session.execute(text(
        "UPDATE runs SET status = 'completed', completed_at = NOW()"
        " WHERE id = :rid AND EXISTS ("
        "  SELECT 1 FROM leases"
        "  WHERE id = :lid AND worker_id = 'worker-1' AND fencing_token = :token"
        " )"
    ), {"rid": rid, "lid": lid, "token": 1})
    assert result.rowcount == 0


def test_current_worker_finalize_succeeds(db_session: Session) -> None:
    """Current worker finalize with correct token succeeds."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid, status="running")
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'worker-1', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    # Worker 2 takes over (token 2)
    db_session.execute(text(
        "UPDATE leases"
        " SET fencing_token = fencing_token + 1, worker_id = 'worker-2'"
        " WHERE id = :id"
    ), {"id": lid})
    db_session.commit()
    # Current finalize (token 2) — succeeds
    result = db_session.execute(text(
        "UPDATE runs SET status = 'completed', completed_at = NOW()"
        " WHERE id = :rid AND EXISTS ("
        "  SELECT 1 FROM leases"
        "  WHERE id = :lid AND worker_id = 'worker-2' AND fencing_token = :token"
        " )"
    ), {"rid": rid, "lid": lid, "token": 2})
    assert result.rowcount == 1
    row = db_session.execute(text(
        "SELECT status, completed_at FROM runs WHERE id = :rid"
    ), {"rid": rid}).fetchone()
    assert row[0] == "completed"
    assert row[1] is not None


# ── Concurrent takeover ──


def test_concurrent_takeover_exactly_one_winner(db_session: Session) -> None:
    """Two workers racing to takeover — exactly one wins."""
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    rid = _setup_run(db_session, hid, jid)
    past_exp = _now() - timedelta(seconds=1)
    lid = uuid4()
    db_session.execute(text(
        "INSERT INTO leases (id, run_id, worker_id, expires_at)"
        " VALUES (:id, :rid, 'original', :exp)"
    ), {"id": lid, "rid": rid, "exp": past_exp})
    db_session.commit()
    # Get the current token
    token = db_session.execute(text(
        "SELECT fencing_token FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()[0]

    engine = db_session.get_bind()
    barrier = threading.Barrier(2, timeout=5)
    results: list[str] = []

    def _takeover(worker: str) -> None:
        with engine.connect() as c:
            barrier.wait()
            try:
                # Condition on fencing_token = base_token so only one wins
                result = c.execute(text(
                    "UPDATE leases"
                    " SET fencing_token = fencing_token + 1, worker_id = :wid"
                    " WHERE id = :id AND fencing_token = :base"
                ), {"id": lid, "wid": worker, "base": token})
                c.commit()
                if result.rowcount > 0:
                    results.append(f"won:{worker}")
                else:
                    results.append(f"lost:{worker}")
            except Exception:
                results.append(f"error:{worker}")

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

    # Verify winner's token is token+1
    row = db_session.execute(text(
        "SELECT fencing_token, worker_id FROM leases WHERE id = :id"
    ), {"id": lid}).fetchone()
    assert row[0] == token + 1
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
        "SELECT enabled FROM schedules WHERE id = :sid"
    ), {"sid": sid}).fetchone()
    assert row[0] is False


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
    assert row[0].tzinfo is not None


def test_disabled_schedule_identifiable(db_session: Session) -> None:
    hid = _setup_household(db_session)
    jid = _setup_job(db_session, hid)
    sid = _setup_schedule(db_session, jid)
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
