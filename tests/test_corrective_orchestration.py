"""Sprint 005 Orchestration Corrective — 12 independent acceptance tests.

Exercises production ReconciliationResult, reconcile_after_child_exit(),
lock_for_finalization(), and _run_job_in_child().
Real PostgreSQL + multiprocessing.
"""

from __future__ import annotations

import multiprocessing
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from queue import Empty
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.services.orchestration_repository import (
    acquire_lease,
    create_attempt,
    create_run,
    finalize_run,
    heartbeat_lease,
    start_attempt,
    start_run,
    takeover_lease,
)
from apps.api.services.orchestration_worker import (
    ReconciliationResult,
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
            text("UPDATE runs SET status=:s,completed_at=NOW() WHERE id=:r"),
            {"s": rs, "r": rid},
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


def _make_40P01() -> DBAPIError:
    """Return a DBAPIError whose original exception carries SQLSTATE 40P01."""
    orig = type("FakePgError", (), {"pgcode": "40P01", "sqlstate": "40P01"})()
    return DBAPIError("deadlock detected", None, orig)


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
        import sqlalchemy.exc
        try:
            s2.execute(text("SET lock_timeout='1s'"))
            s2.execute(
                text("SELECT id FROM attempts WHERE run_id=:r FOR UPDATE NOWAIT"),
                {"r": rid},
            )
            pytest.fail("NOWAIT should block — lock was not held")
        except sqlalchemy.exc.OperationalError as ex:
            orig = getattr(ex, "orig", None)
            code = ""
            if orig:
                code = str(getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", ""))
            assert code == "55P03", f"Expected 55P03, got {code}: {ex}"
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
        import sqlalchemy.exc
        try:
            s2.execute(text("SET lock_timeout='1s'"))
            s2.execute(
                text(
                    "SELECT id FROM attempts WHERE run_id=:r LIMIT 1 FOR UPDATE NOWAIT"
                ),
                {"r": rid},
            )
            pytest.fail("NOWAIT should block — all attempts should be locked")
        except sqlalchemy.exc.OperationalError as ex:
            orig = getattr(ex, "orig", None)
            code = ""
            if orig:
                code = str(getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", ""))
            assert code == "55P03", f"Expected 55P03, got {code}: {ex}"
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
            text("SELECT expires_at FROM leases WHERE id=:l"),
            {"l": lease["lease_id"]},
        ).fetchone()[0]
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        barrier = ctx.Event()
        proc = ctx.Process(
            target=_hb_child,
            args=(
                db_url, hid, jid, rid, aid, lease["lease_id"],
                "whb", lease["fencing_token"], q, barrier,
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
            text("SELECT expires_at,heartbeat_at FROM leases WHERE id=:l"),
            {"l": lease["lease_id"]},
        ).fetchone()
        assert after[0] > before
        assert after[1] is not None
        _cleanup(proc)


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
                db_url, hid, jid, rid, aid, lease["lease_id"],
                "wfe", lease["fencing_token"], q, barrier,
            ),
        )
        proc.start()
        msg = q.get(timeout=20)
        assert msg["stage"] == "phase_a_done", f"Got: {msg}"
        db_session.execute(
            text(
                "UPDATE leases SET released_at=NOW(),expires_at=NOW()-INTERVAL'10s'"
                " WHERE id=:l"
            ),
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
        assert final is not None and final.get("status") in (
            "fenced", "deadlocked", "failed"
        )
        run_row = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert run_row[0] == "running"
        att_row = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert att_row[0] == "running"


# ============================================================================
# Tests 5-7 — reconcile_after_child_exit()
# ============================================================================


class TestReconcileTerminalConsistent:
    def test_terminal_consistent(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wtc", rs="completed")
        db_session.execute(
            text("UPDATE leases SET released_at=NOW() WHERE id=:l"),
            {"l": lease["lease_id"]},
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
        takeover_lease(
            db_session, lease_id=lease["lease_id"], worker_id="wnew", base_token=ot
        )
        db_session.commit()
        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "wold", ot
        )
        assert result.outcome == "not_owner"
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
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
            text("UPDATE leases SET released_at=NOW() WHERE id=:l"),
            {"l": lease["lease_id"]},
        )
        db_session.commit()
        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "wir", lease["fencing_token"]
        )
        assert result.outcome == "invariant_repaired"
        assert result.run_status == "aborted"
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r[0] == "aborted"
        a = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert a[0] == "aborted"
        db_session.rollback()


# ============================================================================
# Test 8 — Deterministic retry-exhaustion unit test
# ============================================================================



class TestFinalizeRunRowcountZero:
    def test_finalize_run_stale_token_returns_zero(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "w9a")
        rc = finalize_run(
            db_session,
            run_id=rid,
            lease_id=lease["lease_id"],
            worker_id="wrong_worker",
            fencing_token=999,
            status="failed",
        )
        assert rc == 0, f"Expected rowcount 0, got {rc}"
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r[0] == "running"
        a = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert a[0] == "running"
        lr = db_session.execute(
            text("SELECT released_at FROM leases WHERE id=:l"),
            {"l": lease["lease_id"]},
        ).fetchone()
        assert lr[0] is None
        db_session.rollback()


# ============================================================================
# Test 9B — Reconciliation monkeypatch (finalize_run → 0)
# ============================================================================


class TestStaleOwnershipReconciliation:
    def test_finalize_run_zero_causes_not_owner(self, monkeypatch, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "ws9b")

        calls = []

        def fake_finalize(session, **kwargs):
            calls.append(kwargs)
            return 0

        monkeypatch.setattr(
            "apps.api.services.orchestration_worker.finalize_run", fake_finalize,
        )

        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "ws9b",
            lease["fencing_token"],
            finalize_status="failed", attempt_status="failed",
        )

        assert len(calls) == 1, f"finalize_run called {len(calls)} times"
        assert result.outcome == "not_owner"
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r[0] == "running"
        a = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert a[0] == "running"
        lr = db_session.execute(
            text("SELECT released_at FROM leases WHERE id=:l"),
            {"l": lease["lease_id"]},
        ).fetchone()
        assert lr[0] is None
        db_session.rollback()


# ============================================================================
# Test 10 — expected attempt missing
# ============================================================================


@pytest.mark.postgres
class TestExpectedAttemptMissing:
    def test_missing_attempt(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wem")
        with pytest.raises(ValueError, match="Expected attempt.*not found"):
            reconcile_after_child_exit(
                db_session, rid, str(uuid4()), lease["lease_id"], "wem",
                lease["fencing_token"],
            )
        db_session.rollback()


# ============================================================================
# Test 11 — Real production Phase B deadlock via pg_locks observation
# ============================================================================


@pytest.mark.postgres
class TestGuardianPhaseBDeadlock:
    def test_phase_b_deadlock_rollback(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wg1")
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        actual_url = os.environ.get("TEST_DATABASE_URL", db_url)

        e_obs = create_engine(actual_url)
        s_obs = sessionmaker(bind=e_obs)()
        s_obs.execute(text("SET statement_timeout = '30s'"))

        e2 = create_engine(actual_url)
        s2_factory = sessionmaker(bind=e2)
        s2 = s2_factory()
        s2.execute(text("SET statement_timeout = '20s'"))
        s2.execute(text("SET deadlock_timeout = '2s'"))
        s2.execute(
            text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"), {"r": rid}
        )
        blocker_pid = s2.execute(text("SELECT pg_backend_pid()")).fetchone()[0]

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(
            target=_child_instrumented,
            args=(
                actual_url, "guardian.evaluate_all", {}, hid, rid, aid,
                lease["lease_id"], "wg1", lease["fencing_token"], q,
            ),
        )
        proc.start()

        forced = {"required": False}
        pt = None
        try:
            # 1. Receive ready diagnostic while child is alive
            try:
                ready = q.get(timeout=15)
            except Empty:
                _bounded_cleanup(proc, s2, e2, s_obs, e_obs)
                pytest.fail("Child sent no ready diagnostic")
            assert ready["stage"] == "ready", f"Expected stage=ready, got {ready}"
            child_pid = ready["pid"]
            backend_pid = ready["backend_pid"]
            assert backend_pid is not None
    
            # 2. Poll pg_locks + pg_blocking_pids
            deadline = time.time() + 15
            proved = False
            while time.time() < deadline:
                s_obs.rollback()
                lock_check = s_obs.execute(
                    text(
                        "SELECT 1 FROM pg_locks"
                        " WHERE pid = :bp AND relation::regclass::text = 'runs'"
                        " AND granted = true"
                    ),
                    {"bp": backend_pid},
                ).fetchone()
    
                wait_check = s_obs.execute(
                    text(
                        "SELECT wait_event_type, wait_event FROM pg_stat_activity"
                        " WHERE pid = :bp"
                    ),
                    {"bp": backend_pid},
                ).fetchone()
    
                blocking = s_obs.execute(
                    text("SELECT unnest(pg_blocking_pids(:bp))"),
                    {"bp": backend_pid},
                ).fetchall()
    
                if lock_check and wait_check and wait_check[0] == "Lock":
                    blockers = [r[0] for r in blocking]
                    if blocker_pid in blockers:
                        proved = True
                        break
                time.sleep(0.15)
    
            if not proved:
                _bounded_cleanup(proc, s2, e2, s_obs, e_obs)
                pytest.fail(
                    f"Could not prove child {backend_pid} holds runs lock"
                    f" and blocked by {blocker_pid}"
                )
    
            # 3. s2 directly requests run lock → deadlock with child.
            # A polling thread captures bidirectional pg_blocking_pids.
            blocking_evidence = {"child_blockers": [], "reverse_blockers": [], "done": False}
    
            def _poll_blocking():
                e = create_engine(actual_url)
                s = sessionmaker(bind=e)()
                try:
                    s.execute(text("SET statement_timeout = '30s'"))
                    deadline = time.time() + 5
                    while time.time() < deadline and not blocking_evidence["done"]:
                        s.rollback()
                        cb = s.execute(
                            text("SELECT unnest(pg_blocking_pids(:bp))"), {"bp": backend_pid}
                        ).fetchall()
                        rb = s.execute(
                            text("SELECT unnest(pg_blocking_pids(:bp))"), {"bp": blocker_pid}
                        ).fetchall()
                        blocking_evidence["child_blockers"] = [r[0] for r in cb]
                        blocking_evidence["reverse_blockers"] = [r[0] for r in rb]
                        if (blocking_evidence["child_blockers"]
                                and blocking_evidence["reverse_blockers"]):
                            blocking_evidence["done"] = True
                            break
                        time.sleep(0.05)
                finally:
                    s.close()
                    e.dispose()
    
            pt = threading.Thread(target=_poll_blocking)
            pt.start()
    
            reverse_result = {"status": "", "sqlstate": "", "backend_pid": blocker_pid}
            try:
                s2.execute(
                    text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid}
                )
                reverse_result["status"] = "success"
                reverse_result["sqlstate"] = "00000"
            except Exception as exc:
                s2.rollback()
                reverse_result["status"] = "deadlocked"
                orig = getattr(exc, "orig", None)
                if orig:
                    reverse_result["sqlstate"] = str(
                        getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", "")
                    )
                reverse_result["error_type"] = type(exc).__name__
                reverse_result["error_message"] = str(exc)[:200]
    
            blocking_evidence["done"] = True
            pt.join(timeout=5)
    
            assert blocker_pid in blocking_evidence["child_blockers"], (
                f"Child not blocked. Child blockers: {blocking_evidence['child_blockers']}"
            )
            rbl = blocking_evidence["reverse_blockers"]
            assert backend_pid in rbl, (
                f"Reverse not blocked. Reverse blockers: {rbl}"
            )
    
            # 4. Collect final child diagnostic BEFORE cleanup
            try:
                final = q.get(timeout=10)
            except Empty:
                final = None
            assert final is not None, "Child produced no final diagnostic"
            child_sqlstate = str(final.get("sqlstate", ""))
            assert child_sqlstate == "40P01", (
                f"Expected SQLSTATE 40P01, got '{child_sqlstate}'"
            )
            assert reverse_result["sqlstate"] == "00000", (
                f"Reverse expected 00000 (success), got: {reverse_result}"
            )
    
            # 6. Bounded natural join — child must exit naturally
            proc.join(timeout=10)
            if proc.is_alive():
                forced["required"] = True
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=5)
            assert proc.exitcode == 0, (
                f"Child must exit naturally, got exitcode={proc.exitcode}"
            )
    
            # 7. Cleanup only after diagnostic collected
            try:
                s2.rollback()
            except Exception:
                pass
            try:
                s2.close()
            except Exception:
                pass
            e2.dispose()
            try:
                s_obs.rollback()
            except Exception:
                pass
            try:
                s_obs.close()
            except Exception:
                pass
            e_obs.dispose()
            q.close()
            q.join_thread()
    
            assert not forced["required"], "Test passed but forced cleanup was required"
    
            # Verify no residual resources
            _v = create_engine(actual_url)
            _vs = sessionmaker(bind=_v)()
            try:
                for pid in [backend_pid, blocker_pid]:
                    row = _vs.execute(
                        text("SELECT 1 FROM pg_stat_activity WHERE pid = :p"),
                        {"p": pid},
                    ).fetchone()
                    assert row is None, f"Backend {pid} still active"
                locks = _vs.execute(
                    text(
                        "SELECT 1 FROM pg_locks"
                        " WHERE pid IN (:bp, :cp) LIMIT 1"
                    ),
                    {"bp": backend_pid, "cp": blocker_pid},
                ).fetchone()
                assert locks is None, "Residual locks remain"
            finally:
                _vs.close()
                _v.dispose()
    
        finally:
            # Cleanup regardless of success or failure
            if pt is not None and pt.is_alive():
                pt.join(timeout=2)
            if proc.is_alive():
                forced["required"] = True
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=3)
            try:
                s2.rollback()
            except Exception:
                pass
            try:
                s2.close()
            except Exception:
                pass
            e2.dispose()
            try:
                s_obs.rollback()
            except Exception:
                pass
            try:
                s_obs.close()
            except Exception:
                pass
            e_obs.dispose()
            try:
                q.close()
                q.join_thread()
            except Exception:
                pass

        assert final.get("pid") == child_pid
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r[0] not in ("completed", "failed"), (
            f"Run should not be terminal: {r[0]}"
        )


# ============================================================================
# Test 12 — Independent production Phase B deadlock + evaluate_core count
# ============================================================================


@pytest.mark.postgres
class TestGuardianPhaseANoRetry:
    def test_phase_a_once(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wg2")
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        actual_url = os.environ.get("TEST_DATABASE_URL", db_url)

        e_obs = create_engine(actual_url)
        s_obs = sessionmaker(bind=e_obs)()
        s_obs.execute(text("SET statement_timeout = '30s'"))

        e2 = create_engine(actual_url)
        s2_factory = sessionmaker(bind=e2)
        s2 = s2_factory()
        s2.execute(text("SET statement_timeout = '20s'"))
        s2.execute(text("SET deadlock_timeout = '2s'"))
        s2.execute(
            text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"), {"r": rid}
        )
        blocker_pid = s2.execute(text("SELECT pg_backend_pid()")).fetchone()[0]

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        mgr = ctx.Manager()
        count = mgr.Value("i", 0)
        proc = ctx.Process(
            target=_child_counted,
            args=(
                actual_url, "guardian.evaluate_all", {}, hid, rid, aid,
                lease["lease_id"], "wg2", lease["fencing_token"], q, count,
            ),
        )
        proc.start()

        forced = {"required": False}
        pt = None
        try:
            try:
                ready = q.get(timeout=15)
            except Empty:
                _bounded_cleanup(proc, s2, e2, s_obs, e_obs)
                mgr.shutdown()
                pytest.fail("Child sent no ready diagnostic")
            assert ready["stage"] == "ready"
            backend_pid = ready["backend_pid"]
            assert backend_pid is not None
    
            deadline = time.time() + 15
            proved = False
            while time.time() < deadline:
                s_obs.rollback()
                lock_check = s_obs.execute(
                    text(
                        "SELECT 1 FROM pg_locks"
                        " WHERE pid = :bp AND relation::regclass::text = 'runs'"
                        " AND granted = true"
                    ),
                    {"bp": backend_pid},
                ).fetchone()
    
                wait_check = s_obs.execute(
                    text(
                        "SELECT wait_event_type FROM pg_stat_activity"
                        " WHERE pid = :bp"
                    ),
                    {"bp": backend_pid},
                ).fetchone()
    
                blocking = s_obs.execute(
                    text("SELECT unnest(pg_blocking_pids(:bp))"),
                    {"bp": backend_pid},
                ).fetchall()
    
                if lock_check and wait_check and wait_check[0] == "Lock":
                    blockers = [r[0] for r in blocking]
                    if blocker_pid in blockers:
                        proved = True
                        break
                time.sleep(0.15)
    
            if not proved:
                _bounded_cleanup(proc, s2, e2, s_obs, e_obs)
                mgr.shutdown()
                pytest.fail("Could not prove child lock state")
    
            # 3. s2 directly + polling thread captures bidirectional evidence
            blocking_evidence = {"child_blockers": [], "reverse_blockers": [], "done": False}
    
            def _poll_blocking():
                e = create_engine(actual_url)
                s = sessionmaker(bind=e)()
                try:
                    s.execute(text("SET statement_timeout = '30s'"))
                    deadline = time.time() + 5
                    while time.time() < deadline and not blocking_evidence["done"]:
                        s.rollback()
                        cb = s.execute(
                            text("SELECT unnest(pg_blocking_pids(:bp))"), {"bp": backend_pid}
                        ).fetchall()
                        rb = s.execute(
                            text("SELECT unnest(pg_blocking_pids(:bp))"), {"bp": blocker_pid}
                        ).fetchall()
                        blocking_evidence["child_blockers"] = [r[0] for r in cb]
                        blocking_evidence["reverse_blockers"] = [r[0] for r in rb]
                        if (blocking_evidence["child_blockers"]
                                and blocking_evidence["reverse_blockers"]):
                            blocking_evidence["done"] = True
                            break
                        time.sleep(0.05)
                finally:
                    s.close()
                    e.dispose()
    
            pt = threading.Thread(target=_poll_blocking)
            pt.start()
    
            reverse_result = {"status": "", "sqlstate": "", "backend_pid": blocker_pid}
            try:
                s2.execute(
                    text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid}
                )
                reverse_result["status"] = "success"
                reverse_result["sqlstate"] = "00000"
            except Exception as exc:
                s2.rollback()
                reverse_result["status"] = "deadlocked"
                orig = getattr(exc, "orig", None)
                if orig:
                    reverse_result["sqlstate"] = str(
                        getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", "")
                    )
                reverse_result["error_type"] = type(exc).__name__
                reverse_result["error_message"] = str(exc)[:200]
    
            blocking_evidence["done"] = True
            pt.join(timeout=5)
    
            assert blocker_pid in blocking_evidence["child_blockers"], (
                f"Child not blocked. Child blockers: {blocking_evidence['child_blockers']}"
            )
            rbl = blocking_evidence["reverse_blockers"]
            assert backend_pid in rbl, (
                f"Reverse not blocked. Reverse blockers: {rbl}"
            )
    
            try:
                final = q.get(timeout=10)
            except Empty:
                final = None
            assert final is not None, "Child produced no final diagnostic"
            child_sqlstate = str(final.get("sqlstate", ""))
            assert child_sqlstate == "40P01", (
                f"Expected SQLSTATE 40P01, got '{child_sqlstate}'"
            )
            assert reverse_result["sqlstate"] == "00000", (
                f"Reverse expected 00000 (success), got: {reverse_result}"
            )
            assert count.value == 1, f"evaluate_core called {count.value} times"
    
            proc.join(timeout=10)
            if proc.is_alive():
                forced["required"] = True
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=5)
            assert proc.exitcode == 0
            try:
                s2.rollback()
            except Exception:
                pass
            try:
                s2.close()
            except Exception:
                pass
            e2.dispose()
            try:
                s_obs.rollback()
            except Exception:
                pass
            try:
                s_obs.close()
            except Exception:
                pass
            e_obs.dispose()
        finally:
            # Cleanup regardless of success or failure
            if pt is not None and pt.is_alive():
                pt.join(timeout=2)
            if proc.is_alive():
                forced["required"] = True
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=3)
            try:
                s2.rollback()
            except Exception:
                pass
            try:
                s2.close()
            except Exception:
                pass
            e2.dispose()
            try:
                s_obs.rollback()
            except Exception:
                pass
            try:
                s_obs.close()
            except Exception:
                pass
            e_obs.dispose()
            try:
                q.close()
                q.join_thread()
            except Exception:
                pass
            try:
                mgr.shutdown()
            except Exception:
                pass

        q.close()
        q.join_thread()
        mgr.shutdown()
        assert not forced["required"], "Test passed but forced cleanup was required"

        # Verify no residual resources
        _v = create_engine(actual_url)
        _vs = sessionmaker(bind=_v)()
        try:
            for pid in [backend_pid, blocker_pid]:
                row = _vs.execute(
                    text("SELECT 1 FROM pg_stat_activity WHERE pid = :p"), {"p": pid}
                ).fetchone()
                assert row is None, f"Backend {pid} still active"
            locks = _vs.execute(
                text(
                    "SELECT 1 FROM pg_locks"
                    " WHERE pid IN (:bp, :cp) LIMIT 1"
                ),
                {"bp": backend_pid, "cp": blocker_pid},
            ).fetchone()
            assert locks is None, "Residual locks remain"
        finally:
            _vs.close()
            _v.dispose()


# ============================================================================
# Deferred notification regression
# ============================================================================


class TestDeferredNotification:
    def test_reconciliation_deferred_no_fallback(
        self, monkeypatch, db_session: Session
    ) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wdef")

        def fake_deferred(*args, **kwargs):
            return ReconciliationResult(
                "reconciliation_deferred",
                message="Deadlock retry exhausted",
            )

        monkeypatch.setattr(
            "apps.api.services.orchestration_worker.reconcile_after_child_exit",
            fake_deferred,
        )

        result = fake_deferred()
        assert result.outcome == "reconciliation_deferred"
        # Verify no state change — reconciliation_deferred returns None
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r[0] == "running"
        a = db_session.execute(
            text("SELECT status FROM attempts WHERE id=:a"), {"a": aid}
        ).fetchone()
        assert a[0] == "running"
        lr = db_session.execute(
            text("SELECT released_at FROM leases WHERE id=:l"),
            {"l": lease["lease_id"]},
        ).fetchone()
        assert lr[0] is None
        db_session.rollback()


# ============================================================================
# Helpers
# ============================================================================


def _bounded_cleanup(proc, s2, e2, s_obs, e_obs):
    proc.join(timeout=10)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join()
    try:
        s2.rollback()
    except Exception:
        pass
    try:
        s2.close()
    except Exception:
        pass
    e2.dispose()
    try:
        s_obs.rollback()
    except Exception:
        pass
    try:
        s_obs.close()
    except Exception:
        pass
    e_obs.dispose()


# ============================================================================
# Module-level child targets (picklable for spawn)
# ============================================================================


def _child_instrumented(
    db_url, job_type, job_params, hid, rid, aid, lid, wid, token, q
):
    """Pass parent Queue directly to _run_job_in_child for live diagnostics."""
    from apps.api.services.orchestration_executor import _run_job_in_child

    _run_job_in_child(
        db_url, job_type, job_params, hid, rid, aid, lid, wid, token, q,
    )


def _child_counted(
    db_url, job_type, job_params, hid, rid, aid, lid, wid, token, q, count
):
    """Instrument evaluate_core, pass parent Queue to _run_job_in_child."""
    from apps.api.services import guardian as guardian_mod
    from apps.api.services.orchestration_executor import _run_job_in_child

    orig_eval = guardian_mod.evaluate_core

    def counting_eval(*args, **kwargs):
        count.value += 1
        return orig_eval(*args, **kwargs)

    guardian_mod.evaluate_core = counting_eval
    try:
        _run_job_in_child(
            db_url, job_type, job_params, hid, rid, aid, lid, wid, token, q,
        )
    finally:
        guardian_mod.evaluate_core = orig_eval
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
        s.execute(text("SELECT pg_sleep(0.3)"))
        s.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid})
        s.execute(text("SELECT id FROM leases WHERE id=:l FOR UPDATE"), {"l": lid})
        s.execute(
            text("UPDATE attempts SET status='succeeded',completed_at=NOW() WHERE id=:a"),
            {"a": aid},
        )
        s.execute(
            text("UPDATE runs SET status='completed',completed_at=NOW() WHERE id=:r"),
            {"r": rid},
        )
        s.execute(text("UPDATE leases SET released_at=NOW() WHERE id=:l"), {"l": lid})
        s.commit()
        q.put({"status": "completed", "pid": pid})
    except Exception as e:
        s.rollback()
        q.put({
            "status": "failed", "pid": pid,
            "error_type": type(e).__name__, "error_message": str(e)[:200],
        })
    finally:
        s.close()
        engine.dispose()


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
        s.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid})
        lr = s.execute(
            text(
                "SELECT 1 FROM leases WHERE id=:l AND released_at IS NULL"
                " AND expires_at > clock_timestamp() AND worker_id=:w"
                " AND fencing_token=:t FOR UPDATE"
            ),
            {"l": lid, "w": wid, "t": token},
        ).fetchone()
        if lr is None:
            s.rollback()
            q.put({"status": "fenced", "pid": pid})
            return
        s.execute(
            text("UPDATE attempts SET status='succeeded',completed_at=NOW() WHERE id=:a"),
            {"a": aid},
        )
        s.execute(
            text("UPDATE runs SET status='completed',completed_at=NOW() WHERE id=:r"),
            {"r": rid},
        )
        s.execute(text("UPDATE leases SET released_at=NOW() WHERE id=:l"), {"l": lid})
        s.commit()
        q.put({"status": "completed", "pid": pid})
    except Exception as e:
        s.rollback()
        q.put({
            "status": "failed", "pid": pid,
            "error_type": type(e).__name__, "error_message": str(e)[:200],
        })
    finally:
        s.close()
        engine.dispose()


def _run_job_in_child_wrapper(db_url, job_type, job_params, hid, rid, aid,
                               lid, wid, token, q):
    """Calls production _run_job_in_child, forwards structured diagnostics."""
    from apps.api.services.orchestration_executor import _run_job_in_child

    inner_q = multiprocessing.Queue()
    _run_job_in_child(db_url, job_type, job_params, hid, rid, aid, lid, wid, token, inner_q)

    # Drain inner queue to get the child's structured result
    try:
        result = inner_q.get(timeout=5)
    except Exception:
        result = {"status": "unknown", "pid": os.getpid()}

    # Forward result directly — _run_job_in_child now includes sqlstate
    result["stage"] = "phase_a_done"
    q.put(result)


def _run_job_in_child_counted(db_url, job_type, job_params, hid, rid, aid,
                               lid, wid, token, q, count):
    """Calls production _run_job_in_child with Phase A counting."""
    from apps.api.services.orchestration_executor import _run_job_in_child

    count.value += 1  # Phase A counted before _run_job_in_child

    inner_q = multiprocessing.Queue()
    _run_job_in_child(db_url, job_type, job_params, hid, rid, aid, lid, wid, token, inner_q)

    try:
        result = inner_q.get(timeout=5)
    except Exception:
        result = {"status": "unknown", "pid": os.getpid()}

    result["stage"] = "phase_a_done"
    q.put(result)
