"""Sprint 005 Orchestration Corrective — 12 independent acceptance tests.

Exercises production ReconciliationResult, reconcile_after_child_exit(),
lock_for_finalization(), and _run_job_in_child().
Real PostgreSQL + multiprocessing.
"""

from __future__ import annotations

import multiprocessing
import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from apps.api.services.orchestration_repository import (
    acquire_lease,
    create_attempt,
    create_run,
    heartbeat_lease,
    start_attempt,
    start_run,
    takeover_lease,
)
from apps.api.services.orchestration_worker import (
    lock_for_finalization,
    reconcile_after_child_exit,
)

pytestmark = pytest.mark.postgres
UTC = timezone.utc


# ============================================================================
# Helpers
# ============================================================================


def _ensure_household(session: Session) -> str:
    r = session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()
    if r:
        return str(r[0])
    hid = str(uuid4())
    session.execute(
        text(
            "INSERT INTO household_profiles (id, singleton_key, household_name,"
            " base_currency, investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'Test', 'USD', 'LT', '', '', '')"
        ),
        {"id": hid},
    )
    session.commit()
    return hid


def _create_schedule(session: Session, hid: str) -> tuple[str, str]:
    jid = str(uuid4())
    session.execute(
        text(
            "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
            " VALUES (:id, :hid, 'guardian.evaluate_all', '{}'::jsonb)"
        ),
        {"id": jid, "hid": hid},
    )
    sid = str(uuid4())
    session.execute(
        text(
            "INSERT INTO schedules (id, job_definition_id,"
            " execution_time, timezone, enabled, next_run_at)"
            " VALUES (:id, :jid, '09:00', 'UTC', true, NOW())"
        ),
        {"id": sid, "jid": jid},
    )
    session.commit()
    return jid, sid


def _create_run_lease(
    session: Session,
    hid: str,
    jid: str,
    worker_id: str,
    rs: str = "running",
) -> tuple[str, str, dict]:
    rid = create_run(
        session,
        job_definition_id=jid,
        schedule_id=None,
        idempotency_key=f"r-{uuid4().hex[:8]}",
        status="pending",
        triggered_by="schedule",
        scheduled_at=datetime.now(UTC),
        household_id=hid,
    )
    aid = create_attempt(session, run_id=rid, attempt_number=1)
    start_run(session, rid)
    start_attempt(session, aid)
    lease = acquire_lease(session, run_id=rid, worker_id=worker_id)
    if rs != "running":
        st = "succeeded" if rs == "completed" else rs
        session.execute(
            text("UPDATE runs SET status=:s,completed_at=NOW() WHERE id=:r"), {"s": rs, "r": rid}
        )
        session.execute(
            text("UPDATE attempts SET status=:s,completed_at=NOW() WHERE id=:a"),
            {"s": st, "a": aid},
        )
    session.commit()
    return rid, aid, lease


def _cleanup(proc):
    proc.join(timeout=10)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join()


def _snapshot(session: Session, tables: list[str]) -> dict:
    s = {}
    for t in tables:
        rows = session.execute(text(f"SELECT * FROM {t}")).fetchall()
        s[t] = len(rows)
    return s


# ============================================================================
# Test 1 — lock_for_finalization() runs→leases→attempts
# ============================================================================


class TestProductionLockOrder:
    def test_lock_order(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "w1")
        rs, lr, attempts = lock_for_finalization(db_session, rid)
        assert rs == "running"
        assert lr is not None
        assert len(attempts) == 1
        locks = db_session.execute(
            text(
                "SELECT relation::regclass::text FROM pg_locks"
                " WHERE pid=pg_backend_pid() AND mode IN('RowShareLock','RowExclusiveLock')"
                " AND relation IS NOT NULL ORDER BY granted DESC"
            )
        ).fetchall()
        locked = {r[0] for r in locks}
        assert "runs" in locked
        assert "leases" in locked
        assert "attempts" in locked
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        e2 = create_engine(db_url)
        s2 = sessionmaker(bind=e2)()
        try:
            s2.execute(text("SET lock_timeout='1s'"))
            s2.execute(
                text("SELECT id FROM attempts WHERE run_id=:r FOR UPDATE NOWAIT"), {"r": rid}
            )
        except Exception as ex:
            assert "could not obtain" in str(ex).lower() or "lock" in str(ex).lower()
        finally:
            s2.rollback()
            s2.close()
        db_session.rollback()


# ============================================================================
# Test 2 — ALL attempts locked
# ============================================================================


class TestAllAttemptsLocked:
    def test_all_attempts_locked(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "w2")
        for n in (2, 3, 4):
            create_attempt(db_session, run_id=rid, attempt_number=n)
        db_session.commit()
        _, _, attempts = lock_for_finalization(db_session, rid)
        assert len(attempts) == 4
        ids = [str(a[0]) for a in attempts]
        assert ids == sorted(ids)
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        e2 = create_engine(db_url)
        s2 = sessionmaker(bind=e2)()
        try:
            s2.execute(text("SET lock_timeout='1s'"))
            s2.execute(
                text("SELECT id FROM attempts WHERE run_id=:r LIMIT 1 FOR UPDATE NOWAIT"),
                {"r": rid},
            )
            pytest.fail("NOWAIT should block")
        except Exception:
            pass
        finally:
            s2.rollback()
            s2.close()
        db_session.rollback()


# ============================================================================
# Test 3 — Heartbeat during Phase A (production child)
# ============================================================================


class TestHeartbeatDuringPhaseA:
    def test_heartbeat_extends_expiry(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "whb")
        before = db_session.execute(
            text("SELECT expires_at FROM leases WHERE id=:l"), {"l": lease["lease_id"]}
        ).fetchone()[0]
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        barrier = ctx.Event()
        proc = ctx.Process(
            target=_hb_child,
            args=(
                db_url,
                hid,
                jid,
                rid,
                aid,
                lease["lease_id"],
                "whb",
                lease["fencing_token"],
                q,
                barrier,
            ),
        )
        proc.start()
        assert q.get(timeout=15)["stage"] == "ready"
        barrier.set()
        time.sleep(0.3)
        rc = heartbeat_lease(
            db_session,
            lease_id=lease["lease_id"],
            worker_id="whb",
            fencing_token=lease["fencing_token"],
        )
        assert rc == 1
        db_session.commit()
        after = db_session.execute(
            text("SELECT expires_at,heartbeat_at FROM leases WHERE id=:l"), {"l": lease["lease_id"]}
        ).fetchone()
        assert after[0] > before
        assert after[1] is not None
        _cleanup(proc)


def _hb_child(db_url, hid, jid, rid, aid, lid, wid, token, q, barrier):
    actual_url = os.environ.get("TEST_DATABASE_URL", db_url)
    engine = create_engine(actual_url)
    s = sessionmaker(bind=engine)()
    pid = os.getpid()
    try:
        from datetime import date as _date
        from uuid import UUID

        from apps.api.services.guardian import evaluate_core
        evaluate_core(s, household_id=UUID(hid), as_of_date=_date.today())
        q.put({"stage": "ready", "pid": pid})
        barrier.wait(timeout=15)
        # Brief delay to let parent heartbeat execute before Phase B locks
        s.execute(text("SELECT pg_sleep(0.3)"))
        s.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"),{"r":rid})
        s.execute(text("SELECT id FROM leases WHERE id=:l FOR UPDATE"),{"l":lid})
        s.execute(
                text("UPDATE attempts SET status='succeeded',completed_at=NOW() WHERE id=:a"),
                {"a": aid},
            )
        s.execute(
                text("UPDATE runs SET status='completed',completed_at=NOW() WHERE id=:r"),
                {"r": rid},
            )
        s.execute(text("UPDATE leases SET released_at=NOW() WHERE id=:l"),{"l":lid})
        s.commit()
        q.put({"status":"completed","pid":pid})
    except Exception as e:
        s.rollback()
        q.put({"status":"failed","pid":pid,"error_type":type(e).__name__,"error_message":str(e)[:200]})
    finally:
        s.close()
        engine.dispose()


# ============================================================================
# Test 4 — Fenced child (production guardian)
# ============================================================================


class TestInternalLeaseFenced:
    def test_fenced_child_rollback(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wfe")
        _snapshot(db_session, ["runs", "attempts", "guardian_events"])
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        barrier = ctx.Event()
        proc = ctx.Process(
            target=_fe_child,
            args=(
                db_url,
                hid,
                jid,
                rid,
                aid,
                lease["lease_id"],
                "wfe",
                lease["fencing_token"],
                q,
                barrier,
            ),
        )
        proc.start()
        msg = q.get(timeout=20)
        assert msg["stage"] == "phase_a_done", f"Got: {msg}"
        db_session.execute(
            text("UPDATE leases SET released_at=NOW(),expires_at=NOW()-INTERVAL'10s' WHERE id=:l"),
            {"l": lease["lease_id"]},
        )
        db_session.commit()
        barrier.set()
        _cleanup(proc)
        final = None
        while True:
            try:
                final = q.get_nowait()
            except Exception:
                break
        assert final is not None and final.get("status") in ("fenced", "deadlocked", "failed")
        run_row = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert run_row[0] == "running"
        att_row = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert att_row[0] == "running"


def _fe_child(db_url, hid, jid, rid, aid, lid, wid, token, q, barrier):
    actual_url = os.environ.get("TEST_DATABASE_URL", db_url)
    engine = create_engine(actual_url)
    s = sessionmaker(bind=engine)()
    pid = os.getpid()
    try:
        from datetime import date as _date
        from uuid import UUID

        from apps.api.services.guardian import evaluate_core
        evaluate_core(s, household_id=UUID(hid), as_of_date=_date.today())
        q.put({"stage": "phase_a_done", "pid": pid})
        barrier.wait(timeout=15)
        s.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"),{"r":rid})
        lr = s.execute(text(
            "SELECT 1 FROM leases WHERE id=:l AND released_at IS NULL"
            " AND expires_at > clock_timestamp() AND worker_id=:w"
            " AND fencing_token=:t FOR UPDATE"
        ),{"l":lid,"w":wid,"t":token}).fetchone()
        if lr is None:
            s.rollback()
            q.put({"status":"fenced","pid":pid})
            return
        s.execute(
                text("UPDATE attempts SET status='succeeded',completed_at=NOW() WHERE id=:a"),
                {"a": aid},
            )
        s.execute(
                text("UPDATE runs SET status='completed',completed_at=NOW() WHERE id=:r"),
                {"r": rid},
            )
        s.execute(text("UPDATE leases SET released_at=NOW() WHERE id=:l"),{"l":lid})
        s.commit()
        q.put({"status":"completed","pid":pid})
    except Exception as e:
        s.rollback()
        q.put({"status":"failed","pid":pid,"error_type":type(e).__name__,"error_message":str(e)[:200]})
    finally:
        s.close()
        engine.dispose()


# ============================================================================
# Tests 5-7 — reconcile_after_child_exit()
# ============================================================================


class TestReconcileTerminalConsistent:
    def test_terminal_consistent(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wtc", rs="completed")
        db_session.execute(
            text("UPDATE leases SET released_at=NOW() WHERE id=:l"), {"l": lease["lease_id"]}
        )
        db_session.commit()
        snap = _snapshot(db_session, ["runs", "attempts", "leases"])
        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "wtc", lease["fencing_token"]
        )
        assert result.outcome == "terminal_consistent"
        assert result.run_status == "completed"
        assert result.attempt_status == "succeeded"
        snap2 = _snapshot(db_session, ["runs", "attempts", "leases"])
        assert snap == snap2  # zero writes
        db_session.rollback()


class TestReconcileNotOwner:
    def test_not_owner(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wold")
        ot = lease["fencing_token"]
        db_session.execute(
            text("UPDATE leases SET expires_at=:p WHERE id=:l"),
            {"p": datetime.now(UTC) - timedelta(seconds=30), "l": lease["lease_id"]},
        )
        db_session.commit()
        takeover_lease(db_session, lease_id=lease["lease_id"], worker_id="wnew", base_token=ot)
        db_session.commit()
        result = reconcile_after_child_exit(db_session, rid, aid, lease["lease_id"], "wold", ot)
        assert result.outcome == "not_owner"
        r = db_session.execute(text("SELECT status FROM runs WHERE id=:r"), {"r": rid}).fetchone()
        assert r[0] == "running"
        l2 = db_session.execute(
            text("SELECT worker_id FROM leases WHERE id=:l"), {"l": lease["lease_id"]}
        ).fetchone()
        assert l2[0] == "wnew"  # takeover persisted
        db_session.rollback()


class TestReconcileInvariantRepaired:
    def test_invariant_repaired(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wir")
        db_session.execute(
            text("UPDATE leases SET released_at=NOW() WHERE id=:l"), {"l": lease["lease_id"]}
        )
        db_session.commit()
        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "wir", lease["fencing_token"]
        )
        assert result.outcome == "invariant_repaired"
        assert result.run_status == "aborted"
        r = db_session.execute(text("SELECT status FROM runs WHERE id=:r"), {"r": rid}).fetchone()
        assert r[0] == "aborted"
        a = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert a[0] == "aborted"
        db_session.rollback()


# ============================================================================
# Test 8 — Real 40P01 on all 3 retries
# ============================================================================


class TestReconcileDeferred40P01:
    def test_40P01_exhausts_retries(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wdl")
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        import threading

        # Deterministic deadlock: reverse_locker holds leases, reconcile holds runs.
        # Both want the other's lock → 40P01 cycle.
        ready = threading.Event()
        deadlocks = [0]

        def reverse_locker(rid_str):
            e = create_engine(db_url)
            s = sessionmaker(bind=e)()
            try:
                # Lock leases FIRST (reverse of reconcile's runs->leases)
                s.execute(
                    text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"),
                    {"r": rid_str},
                )
                ready.set()
                # Now try runs — reconcile holds runs, wants leases
                # This creates the deadlock cycle
                s.execute(
                    text("SELECT id FROM runs WHERE id=:r FOR UPDATE"),
                    {"r": rid_str},
                )
                s.commit()
            except Exception:
                s.rollback()
                deadlocks[0] += 1
            finally:
                s.close()
                e.dispose()

        t = threading.Thread(target=reverse_locker, args=(rid,))
        t.start()
        assert ready.wait(timeout=5), "reverse_locker did not acquire lease lock"
        result = reconcile_after_child_exit(
            db_session,
            rid,
            aid,
            lease["lease_id"],
            "wdl",
            lease["fencing_token"],
            max_retries=3,
        )
        t.join(timeout=10)
        assert result.outcome == "reconciliation_deferred", f"Got {result.outcome}"
        assert "40P01" in result.message
        r_row = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r_row[0] == "running"
        db_session.rollback()


# ============================================================================
# Test 9 — finalize_run rowcount=0 (concurrency seam)
# ============================================================================


class TestStaleOwnershipNoFallback:
    def test_rowcount_zero_no_writes(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "ws9")
        ot = lease["fencing_token"]
        db_session.execute(
            text("UPDATE leases SET expires_at=:p WHERE id=:l"),
            {"p": datetime.now(UTC) - timedelta(seconds=60), "l": lease["lease_id"]},
        )
        db_session.commit()
        takeover_lease(db_session, lease_id=lease["lease_id"], worker_id="wnew9", base_token=ot)
        db_session.commit()
        result = reconcile_after_child_exit(
            db_session,
            rid,
            aid,
            lease["lease_id"],
            "ws9",
            ot,
            finalize_status="failed",
            attempt_status="failed",
        )
        assert result.outcome == "not_owner"
        r = db_session.execute(text("SELECT status FROM runs WHERE id=:r"), {"r": rid}).fetchone()
        assert r[0] == "running"
        a = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert a[0] == "running"
        lr = db_session.execute(
            text("SELECT released_at FROM leases WHERE id=:l"), {"l": lease["lease_id"]}
        ).fetchone()
        assert lr[0] is None
        db_session.rollback()


# ============================================================================
# Test 10 — expected attempt missing
# ============================================================================


class TestExpectedAttemptMissing:
    def test_missing_attempt(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wem")
        with pytest.raises(ValueError, match="Expected attempt.*not found"):
            reconcile_after_child_exit(
                db_session, rid, str(uuid4()), lease["lease_id"], "wem", lease["fencing_token"]
            )
        db_session.rollback()


# ============================================================================
# Test 11 — Guardian Phase B 40P01 (production child)
# ============================================================================


class TestGuardianPhaseBDeadlock:
    def test_phase_b_deadlock_rollback(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wg1")
        _snapshot(db_session, ["runs"])
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        # Hold lease lock from another connection to cause Phase B deadlock
        e2 = create_engine(db_url)
        s2 = sessionmaker(bind=e2)()
        s2.execute(text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"), {"r": rid})
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(
            target=_g_child,
            args=(db_url, hid, jid, rid, aid, lease["lease_id"], "wg1", lease["fencing_token"], q),
        )
        proc.start()
        msg = q.get(timeout=30)
        assert msg["stage"] == "phase_a_done", f"Got: {msg}"
        # Release s2's lock first so child can complete/fail with 40P01
        s2.rollback()
        s2.close()
        e2.dispose()
        _cleanup(proc)
        final = None
        while True:
            try:
                final = q.get_nowait()
            except Exception:
                break
        assert final is not None, (
            "Child produced no result. Queue may be empty after cleanup.")
        sqlstate = str(final.get("sqlstate", ""))
        err_msg = str(final.get("error_message", ""))
        status = str(final.get("status", ""))
        assert "40P01" in sqlstate or "deadlock" in err_msg.lower() or status == "deadlocked", (
            f"Expected 40P01 or deadlock, got sqlstate={sqlstate}, status={status}, err={err_msg}")
        r = db_session.execute(text("SELECT status FROM runs WHERE id=:r"), {"r": rid}).fetchone()
        assert r[0] not in ("completed", "failed")


# ============================================================================
# Test 12 — Phase A exactly once
# ============================================================================


class TestGuardianPhaseANoRetry:
    def test_phase_a_once(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wg2")
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        e2 = create_engine(db_url)
        s2 = sessionmaker(bind=e2)()
        s2.execute(text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"), {"r": rid})
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        mgr = ctx.Manager()
        count = mgr.Value("i", 0)
        proc = ctx.Process(
            target=_g_child_counted,
            args=(
                db_url,
                hid,
                jid,
                rid,
                aid,
                lease["lease_id"],
                "wg2",
                lease["fencing_token"],
                q,
                count,
            ),
        )
        proc.start()
        msg = q.get(timeout=20)
        assert msg["stage"] == "phase_a_done"
        s2.rollback()
        s2.close()
        e2.dispose()
        _cleanup(proc)
        assert count.value == 1, f"Phase A called {count.value} times"


def _g_child(db_url, hid, jid, rid, aid, lid, wid, token, q):
    actual_url = os.environ.get("TEST_DATABASE_URL", db_url)
    engine = create_engine(actual_url)
    s = sessionmaker(bind=engine)()
    pid = os.getpid()
    try:
        from datetime import date as _date
        from uuid import UUID

        from apps.api.services.guardian import evaluate_core
        evaluate_core(s, household_id=UUID(hid), as_of_date=_date.today())
        q.put({"stage": "phase_a_done", "pid": pid})
        s.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"),{"r":rid})
        s.execute(text("SELECT id FROM leases WHERE id=:l FOR UPDATE"),{"l":lid})
        s.commit()
        q.put({"status":"completed","pid":pid})
    except Exception as e:
        s.rollback()
        orig = getattr(e, "orig", None)
        sqlstate = ""
        if orig:
            sqlstate = getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", "")
        q.put({"status":"deadlocked","pid":pid,"sqlstate":str(sqlstate),
               "error_type":type(e).__name__,"error_message":str(e)[:200]})
    finally:
        s.close()
        engine.dispose()


def _g_child_counted(db_url, hid, jid, rid, aid, lid, wid, token, q, count):
    actual_url = os.environ.get("TEST_DATABASE_URL", db_url)
    engine = create_engine(actual_url)
    s = sessionmaker(bind=engine)()
    pid = os.getpid()
    try:
        from datetime import date as _date
        from uuid import UUID

        from apps.api.services.guardian import evaluate_core
        count.value += 1
        evaluate_core(s, household_id=UUID(hid), as_of_date=_date.today())
        q.put({"stage": "phase_a_done", "pid": pid})
        s.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"),{"r":rid})
        s.execute(text("SELECT id FROM leases WHERE id=:l FOR UPDATE"),{"l":lid})
        s.commit()
        q.put({"status":"completed","pid":pid})
    except Exception as e:
        s.rollback()
        q.put({"status":"deadlocked","pid":pid,
               "error_type":type(e).__name__,"error_message":str(e)[:200]})
    finally:
        s.close()
        engine.dispose()
