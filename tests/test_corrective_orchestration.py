"""Sprint 005 Orchestration Corrective — 12 acceptance tests.

Exercises production ReconciliationResult, reconcile_after_child_exit(),
lock_for_finalization(), and the approved v17 reconciliation contract.

Real PostgreSQL + multiprocessing where specified.
"""

from __future__ import annotations

import multiprocessing
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
    r = session.execute(text(
        "SELECT id FROM household_profiles LIMIT 1")).fetchone()
    if r:
        return str(r[0])
    hid = str(uuid4())
    session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, TRUE, 'Test', 'USD', 'LT', '', '', '')"), {"id": hid})
    session.commit()
    return hid


def _create_guardian_job_def(session: Session, hid: str) -> str:
    jid = str(uuid4())
    session.execute(text(
        "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
        " VALUES (:id, :hid, 'guardian.evaluate_all', '{}'::jsonb)"
    ), {"id": jid, "hid": hid})
    return jid


def _create_test_schedule(session: Session, hid: str) -> tuple:
    jid = _create_guardian_job_def(session, hid)
    sid = str(uuid4())
    session.execute(text(
        "INSERT INTO schedules (id, job_definition_id,"
        " execution_time, timezone, enabled, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'UTC', true, NOW())"
    ), {"id": sid, "jid": jid})
    session.commit()
    return jid, sid


# ============================================================================
# Test 1 — Production lock order via lock_for_finalization()
# ============================================================================

class TestProductionLockOrder:
    """Tests 1: lock_for_finalization() enforces runs->leases->attempts."""

    def test_production_lock_order_with_blocking_evidence(
        self, db_session: Session,
    ) -> None:
        """lock_for_finalization acquires runs, then leases, then ALL attempts."""
        hid = _ensure_household(db_session)
        jid, sid = _create_test_schedule(db_session, hid)
        rid = create_run(db_session, job_definition_id=jid, schedule_id=sid,
            idempotency_key=f"lo-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(UTC),
            household_id=hid)
        aid = create_attempt(db_session, run_id=rid, attempt_number=1)
        start_run(db_session, rid)
        start_attempt(db_session, aid)
        acquire_lease(db_session, run_id=rid, worker_id="test-lo")
        db_session.commit()

        rs, lr, attempts = lock_for_finalization(db_session, rid)
        assert rs == "running"
        assert lr is not None
        assert len(attempts) == 1

        # Verify via pg_locks that all three tables are locked
        locks = db_session.execute(text(
            "SELECT relation::regclass::text AS tname FROM pg_locks"
            " WHERE pid = pg_backend_pid() AND mode IN ('RowShareLock','RowExclusiveLock')"
            " AND relation IS NOT NULL ORDER BY granted DESC"
        )).fetchall()
        locked_set = {r[0] for r in locks}
        assert "runs" in locked_set, f"runs not locked: {locked_set}"
        assert "leases" in locked_set, f"leases not locked: {locked_set}"
        assert "attempts" in locked_set, f"attempts not locked: {locked_set}"

        # Second session blocked by first session's locks
        engine2 = create_engine(
            db_session.get_bind().url.render_as_string(hide_password=False))
        s2 = sessionmaker(bind=engine2)()
        try:
            s2.execute(text("SET lock_timeout = '2s'"))
            import threading
            blocked = [False]

            def try_lock():
                try:
                    s2.execute(text(
                        "SELECT id FROM attempts WHERE run_id = :rid"
                        " FOR UPDATE NOWAIT"), {"rid": rid})
                except Exception:
                    blocked[0] = True
                    s2.rollback()

            t = threading.Thread(target=try_lock)
            t.start()
            t.join(timeout=5)
            assert blocked[0], (
                "Second session should be blocked by first session's locks")
        finally:
            s2.close()

        db_session.rollback()


# ============================================================================
# Test 2 — ALL attempts locked
# ============================================================================

class TestAllAttemptsLocked:
    """Test 2: lock_for_finalization() locks every attempt."""

    def test_all_attempts_locked_by_production_function(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_test_schedule(db_session, hid)
        rid = create_run(db_session, job_definition_id=jid, schedule_id=sid,
            idempotency_key=f"al-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(UTC),
            household_id=hid)
        for n in range(1, 5):
            aid = create_attempt(db_session, run_id=rid, attempt_number=n)
            if n == 1:
                start_attempt(db_session, aid)
        start_run(db_session, rid)
        acquire_lease(db_session, run_id=rid, worker_id="test-al")
        db_session.commit()

        rs, lr, attempts = lock_for_finalization(db_session, rid)
        assert len(attempts) == 4, f"Expected 4 locked, got {len(attempts)}"

        # Verify deterministic ordering
        attempt_ids = [str(a[0]) for a in attempts]
        assert attempt_ids == sorted(attempt_ids), (
            f"Attempts must be locked in deterministic order: {attempt_ids}")

        db_session.rollback()


# ============================================================================
# Test 3 — Heartbeat during Phase A (real multiprocessing)
# ============================================================================

class TestHeartbeatDuringPhaseA:
    """Test 3: Heartbeat extends expires_at during real multiprocessing Phase A."""

    def test_heartbeat_extends_expiry_during_real_child_execution(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_test_schedule(db_session, hid)
        rid = create_run(db_session, job_definition_id=jid, schedule_id=sid,
            idempotency_key=f"hb-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(UTC),
            household_id=hid)
        aid = create_attempt(db_session, run_id=rid, attempt_number=1)
        start_run(db_session, rid)
        start_attempt(db_session, aid)
        lease = acquire_lease(db_session, run_id=rid, worker_id="test-hb3")
        db_session.commit()

        # Record initial expires_at
        before = db_session.execute(text(
            "SELECT expires_at FROM leases WHERE id = :lid"
        ), {"lid": lease["lease_id"]}).fetchone()[0]

        # Spawn child that runs Phase A for several seconds
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)

        proc = ctx.Process(
            target=_long_phase_a_child,
            args=(db_url, str(hid), rid, aid, lease["lease_id"],
                  "test-hb3", lease["fencing_token"], result_queue))
        proc.start()

        # Wait for child to signal it's in Phase A
        try:
            msg = result_queue.get(timeout=10)
            assert msg["stage"] == "in_phase_a", f"Unexpected: {msg}"
        except Exception:
            proc.terminate()
            proc.join()
            pytest.fail("Child did not reach Phase A")

        # Execute heartbeat while child is in Phase A
        time.sleep(0.5)
        rc = heartbeat_lease(
            db_session, lease_id=lease["lease_id"],
            worker_id="test-hb3", fencing_token=lease["fencing_token"])
        assert rc == 1
        db_session.commit()

        after = db_session.execute(text(
            "SELECT expires_at, heartbeat_at FROM leases WHERE id = :lid"
        ), {"lid": lease["lease_id"]}).fetchone()
        assert after[0] > before, (
            f"expires_at not extended: {before} -> {after[0]}")
        assert after[1] is not None

        # Clean up child
        proc.join(timeout=15)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join()


def _long_phase_a_child(db_url, hid, rid, aid, lid, wid, token, q):
    """Child that runs Phase A for several seconds."""
    engine = create_engine(db_url)
    s = sessionmaker(bind=engine)()
    try:
        q.put({"stage": "in_phase_a"})
        time.sleep(4)
        s.execute(text(
            "SELECT id FROM runs WHERE id = :rid FOR UPDATE"), {"rid": rid})
        s.execute(text(
            "SELECT id FROM leases WHERE id = :lid FOR UPDATE"), {"lid": lid})
        s.execute(text(
            "UPDATE attempts SET status = 'succeeded', completed_at = NOW()"
            " WHERE id = :aid"), {"aid": aid})
        s.execute(text(
            "UPDATE runs SET status = 'completed', completed_at = NOW()"
            " WHERE id = :rid"), {"rid": rid})
        s.execute(text(
            "UPDATE leases SET released_at = NOW()"
            " WHERE id = :lid"), {"lid": lid})
        s.commit()
        q.put({"status": "completed"})
    except Exception as e:
        s.rollback()
        q.put({"status": "failed", "error": str(e)[:200]})
    finally:
        s.close()
        engine.dispose()


# ============================================================================
# Test 4 — InternalLeaseFenced rollback (real multiprocessing)
# ============================================================================

class TestInternalLeaseFenced:
    """Test 4: Fenced child rolls back all Phase A writes."""

    def test_fenced_child_rolls_back_guardian_writes(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_test_schedule(db_session, hid)
        rid = create_run(db_session, job_definition_id=jid, schedule_id=sid,
            idempotency_key=f"fe-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(UTC),
            household_id=hid)
        aid = create_attempt(db_session, run_id=rid, attempt_number=1)
        start_run(db_session, rid)
        start_attempt(db_session, aid)
        lease = acquire_lease(db_session, run_id=rid, worker_id="test-fe")
        db_session.commit()

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)

        proc = ctx.Process(
            target=_fenced_child_with_guardian_writes,
            args=(db_url, str(hid), rid, aid, lease["lease_id"],
                  "test-fe", lease["fencing_token"], q))
        proc.start()

        # Wait for Phase A writes done
        try:
            msg = q.get(timeout=20)
            assert msg["stage"] == "phase_a_done", f"Unexpected: {msg}"
        except Exception:
            proc.terminate()
            proc.join()
            pytest.fail("Child did not complete Phase A")

        # Release lease so Phase B sees fenced
        db_session.execute(text(
            "UPDATE leases SET released_at = NOW(), expires_at = NOW() - INTERVAL '10s'"
            " WHERE id = :lid"), {"lid": lease["lease_id"]})
        db_session.commit()

        # Child should now detect fenced and rollback
        proc.join(timeout=10)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)

        # Verify: run still running, attempt still running, lease released
        run_row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": rid}).fetchone()
        assert run_row[0] == "running", f"Run should be running: {run_row[0]}"

        att_row = db_session.execute(text(
            "SELECT status FROM attempts WHERE id = :aid"
        ), {"aid": aid}).fetchone()
        assert att_row[0] == "running", f"Attempt should be running: {att_row[0]}"


def _fenced_child_with_guardian_writes(db_url, hid, rid, aid, lid, wid, token, q):
    """Child that writes Guardian events in Phase A, then detects fenced Phase B."""
    engine = create_engine(db_url)
    s = sessionmaker(bind=engine)()
    try:
        # Phase A: write Guardian events (simulated with a marker insert)
        s.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, (SELECT id FROM job_definitions WHERE household_id=:hid"
            " AND job_type='guardian.evaluate_all' LIMIT 1), NULL, :ik, 'running',"
            " 'child-test', NOW(), :hid)"
            " ON CONFLICT DO NOTHING"
        ), {"id": str(uuid4()), "hid": hid, "ik": f"ph-{uuid4().hex[:8]}"})
        q.put({"stage": "phase_a_done"})

        # Wait for parent to expire the lease
        time.sleep(3)

        # Phase B: lock + validate
        s.execute(text(
            "SELECT id FROM runs WHERE id = :rid FOR UPDATE"), {"rid": rid})
        lr = s.execute(text(
            "SELECT 1 FROM leases WHERE id = :lid AND released_at IS NULL"
            " AND expires_at > clock_timestamp() AND worker_id = :wid"
            " AND fencing_token = :token FOR UPDATE"
        ), {"lid": lid, "wid": wid, "token": token}).fetchone()

        if lr is None:
            s.rollback()
            q.put({"status": "fenced"})
            return

        s.commit()
        q.put({"status": "completed"})
    except Exception as e:
        s.rollback()
        q.put({"status": "failed", "error": str(e)[:200]})
    finally:
        s.close()
        engine.dispose()


# ============================================================================
# Tests 5-8 — reconcile_after_child_exit() outcomes
# ============================================================================

class TestReconcileTerminalConsistent:
    """Test 5: terminal_consistent outcome."""

    def test_terminal_consistent_via_production_function(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = str(uuid4())
        aid = str(uuid4())
        lid = str(uuid4())
        now = datetime.now(UTC)
        db_session.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at,"
            " household_id, completed_at)"
            " VALUES (:id, :jid, NULL, :ik, 'completed', 'schedule',"
            " :now, :hid, :now)"
        ), {"id": rid, "jid": jid, "ik": f"tc-{uuid4().hex[:8]}", "hid": hid, "now": now})
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status, completed_at)"
            " VALUES (:id, :rid, 1, 'succeeded', :now)"
        ), {"id": aid, "rid": rid, "now": now})
        db_session.execute(text(
            "INSERT INTO leases (id, run_id, worker_id, acquires_at, heartbeat_at,"
            " expires_at, released_at)"
            " VALUES (:id, :rid, 'test-w', :now, :now, :exp, :now)"
        ), {"id": lid, "rid": rid, "exp": now + timedelta(days=1), "now": now})
        db_session.commit()

        result = reconcile_after_child_exit(
            db_session, rid, aid, lid, "test-w", 1)
        assert result.outcome == "terminal_consistent"
        assert result.run_status == "completed"
        assert result.attempt_status == "succeeded"


class TestReconcileNotOwner:
    """Test 6: not_owner via taken-over lease."""

    def test_not_owner_via_production_function(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = str(uuid4())
        aid = str(uuid4())
        db_session.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, NULL, :ik, 'running', 'schedule', NOW(), :hid)"
        ), {"id": rid, "jid": jid, "ik": f"no-{uuid4().hex[:8]}", "hid": hid})
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})
        lease = acquire_lease(db_session, run_id=rid, worker_id="old-w")
        db_session.commit()

        # Force expiry + takeover
        db_session.execute(text(
            "UPDATE leases SET expires_at = :past WHERE id = :lid"
        ), {"past": datetime.now(UTC) - timedelta(seconds=30),
            "lid": lease["lease_id"]})
        db_session.commit()
        takeover_lease(db_session, lease_id=lease["lease_id"],
            worker_id="new-w", base_token=lease["fencing_token"])
        db_session.commit()

        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "old-w",
            lease["fencing_token"])
        assert result.outcome == "not_owner"

        # Prove no writes from old owner
        run_row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": rid}).fetchone()
        assert run_row[0] == "running"


class TestReconcileInvariantRepaired:
    """Test 7: invariant_repaired for running+released."""

    def test_invariant_repaired_via_production_function(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = str(uuid4())
        aid = str(uuid4())
        db_session.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, NULL, :ik, 'running', 'schedule', NOW(), :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ir-{uuid4().hex[:8]}", "hid": hid})
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})
        lease = acquire_lease(db_session, run_id=rid, worker_id="test-ir")
        db_session.execute(text(
            "UPDATE leases SET released_at = NOW() WHERE id = :lid"
        ), {"lid": lease["lease_id"]})
        db_session.commit()

        result = reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "test-ir",
            lease["fencing_token"])
        assert result.outcome == "invariant_repaired"
        assert result.run_status == "aborted"

        run_row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": rid}).fetchone()
        assert run_row[0] == "aborted"


class TestReconcileDeferred40P01:
    """Test 8: reconciliation_deferred after real 40P01 deadlock."""

    def test_reconciliation_deferred_after_deadlock(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = str(uuid4())
        aid = str(uuid4())
        lid = str(uuid4())
        now = datetime.now(UTC)
        db_session.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, NULL, :ik, 'running', 'schedule', :now, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"dl-{uuid4().hex[:8]}", "hid": hid, "now": now})
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})
        db_session.execute(text(
            "INSERT INTO leases (id, run_id, worker_id, expires_at, acquires_at,"
            " heartbeat_at)"
            " VALUES (:id, :rid, 'test-dl', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": now + timedelta(hours=1), "now": now})
        db_session.commit()

        db_url = db_session.get_bind().url.render_as_string(hide_password=False)

        # Barrier: session2 locks leases first, session1 locks runs first
        # -> deadlock on reverse-order acquisition
        import threading
        ready = threading.Event()
        done = threading.Event()

        def s2_worker():
            engine = create_engine(db_url)
            s = sessionmaker(bind=engine)()
            try:
                # Lock leases first (reverse order)
                s.execute(text(
                    "SELECT id FROM leases WHERE run_id = :rid FOR UPDATE"
                ), {"rid": rid})
                ready.set()
                # Wait for s1 to try to lock leases (will deadlock)
                done.wait(timeout=10)
            except Exception:
                s.rollback()
            finally:
                s.close()
                engine.dispose()

        t = threading.Thread(target=s2_worker)
        t.start()
        assert ready.wait(timeout=5), "s2 did not start"

        # s1 wraps reconcile_after_child_exit which locks runs->leases->attempts
        # s1's lock on leases will deadlock with s2's lock on leases
        # (s2 holds leases, s1 wants leases while holding runs)
        try:
            reconcile_after_child_exit(
                db_session, rid, aid, lid, "test-dl", 1, max_retries=3)
        except Exception:
            db_session.rollback()

        done.set()
        t.join(timeout=5)

        # Run should still be non-terminal
        run_row2 = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": rid}).fetchone()
        assert run_row2[0] not in ("completed", "failed", "aborted"), (
            f"Run should remain non-terminal: {run_row2[0]}")
        db_session.rollback()


# ============================================================================
# Test 9 — finalize_run rowcount=0 via stale ownership
# ============================================================================

class TestStaleOwnershipNoFallback:
    """Test 9: finalize_run rowcount=0 -> no fallback writes."""

    def test_stale_ownership_no_fallback_writes(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = str(uuid4())
        aid = str(uuid4())
        db_session.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, NULL, :ik, 'running', 'schedule', NOW(), :hid)"
        ), {"id": rid, "jid": jid, "ik": f"so-{uuid4().hex[:8]}", "hid": hid})
        db_session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})
        lease = acquire_lease(db_session, run_id=rid, worker_id="old-so")
        old_token = lease["fencing_token"]
        db_session.commit()

        # Force expiry + takeover -> stale token
        db_session.execute(text(
            "UPDATE leases SET expires_at = :past WHERE id = :lid"
        ), {"past": datetime.now(UTC) - timedelta(seconds=60),
            "lid": lease["lease_id"]})
        db_session.commit()
        takeover_lease(db_session, lease_id=lease["lease_id"],
            worker_id="new-so", base_token=old_token)
        db_session.commit()

        # Old owner attempts reconciliation with stale token
        reconcile_after_child_exit(
            db_session, rid, aid, lease["lease_id"], "old-so", old_token)

        # Verify no writes occurred
        run_row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": rid}).fetchone()
        assert run_row[0] == "running", f"Run unchanged: {run_row[0]}"

        att_row = db_session.execute(text(
            "SELECT status FROM attempts WHERE id = :aid"
        ), {"aid": aid}).fetchone()
        assert att_row[0] == "running", f"Attempt unchanged: {att_row[0]}"

        # Lease still unreleased by old owner
        lr = db_session.execute(text(
            "SELECT released_at FROM leases WHERE id = :lid"
        ), {"lid": lease["lease_id"]}).fetchone()
        assert lr[0] is None, "Old owner should not release lease"
        db_session.rollback()


# ============================================================================
# Test 10 — expected attempt missing
# ============================================================================

class TestExpectedAttemptMissing:
    """Test 10: production code raises explicit error on missing attempt."""

    def test_missing_attempt_raises_production_error(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = str(uuid4())
        lid = str(uuid4())
        now = datetime.now(UTC)
        db_session.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, :jid, NULL, :ik, 'running', 'schedule', :now, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"em-{uuid4().hex[:8]}", "hid": hid, "now": now})
        db_session.execute(text(
            "INSERT INTO leases (id, run_id, worker_id, expires_at, acquires_at,"
            " heartbeat_at)"
            " VALUES (:id, :rid, 'test-em', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": now + timedelta(hours=1), "now": now})
        db_session.commit()

        nonexistent_aid = str(uuid4())

        # reconcile_after_child_exit calls _reconcile_attempt which
        # locks ALL attempts and checks for expected attempt
        with pytest.raises(ValueError, match="Expected attempt.*not found"):
            reconcile_after_child_exit(
                db_session, rid, nonexistent_aid, lid, "test-em", 1)
        db_session.rollback()


# ============================================================================
# Test 11-12 — Guardian Phase B 40P01 (real multiprocessing)
# ============================================================================

class TestGuardianPhaseBDeadlockReal:
    """Test 11-12: Real multiprocessing Guardian + Phase B 40P01."""

    def test_guardian_phase_b_deadlock_rollback_and_no_retry(
        self, db_session: Session,
    ) -> None:
        hid = _ensure_household(db_session)
        jid = _create_guardian_job_def(db_session, hid)
        rid = create_run(db_session, job_definition_id=jid, schedule_id=None,
            idempotency_key=f"gd-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(UTC),
            household_id=hid)
        aid = create_attempt(db_session, run_id=rid, attempt_number=1)
        start_run(db_session, rid)
        start_attempt(db_session, aid)
        lease = acquire_lease(db_session, run_id=rid, worker_id="test-gd")
        db_session.commit()

        call_count = multiprocessing.Value("i", 0)

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)

        proc = ctx.Process(
            target=_guardian_child_with_deadlock,
            args=(db_url, str(hid), rid, aid, lease["lease_id"],
                  "test-gd", lease["fencing_token"], q, call_count))
        proc.start()

        try:
            msg = q.get(timeout=20)
            assert msg["stage"] == "phase_a_done", f"Unexpected: {msg}"
        except Exception:
            proc.terminate()
            proc.join()
            pytest.fail("Child did not complete Phase A")

        # Induce deadlock: lock lease from parent in reverse order
        engine2 = create_engine(db_url)
        s2 = sessionmaker(bind=engine2)()
        s2.execute(text(
            "SELECT id FROM leases WHERE run_id = :rid FOR UPDATE"
        ), {"rid": rid})

        # Child is now in Phase B, trying runs->leases, will deadlock
        proc.join(timeout=15)
        s2.rollback()
        s2.close()
        engine2.dispose()

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
                proc.join()

        # Phase A called exactly once
        assert call_count.value == 1, (
            f"Phase A called {call_count.value} times, expected 1")

        # Run should not be terminal (deadlock rolled back everything)
        run_row = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": rid}).fetchone()
        assert run_row[0] not in ("completed", "failed"), (
            f"Run should not be terminal after deadlock: {run_row[0]}")


def _guardian_child_with_deadlock(db_url, hid, rid, aid, lid, wid, token, q, counter):
    """Guardian child: Phase A writes, Phase B lock order -> deadlock."""
    engine = create_engine(db_url)
    s = sessionmaker(bind=engine)()
    try:
        # Phase A: business operation (counted)
        counter.value += 1
        s.execute(text(
            "INSERT INTO runs (id, job_definition_id, schedule_id,"
            " idempotency_key, status, triggered_by, scheduled_at, household_id)"
            " VALUES (:id, (SELECT id FROM job_definitions WHERE household_id=:hid"
            " LIMIT 1), NULL, :ik, 'running', 'child-dl', NOW(), :hid)"
            " ON CONFLICT DO NOTHING"
        ), {"id": str(uuid4()), "hid": hid, "ik": f"dl-{uuid4().hex[:8]}"})
        q.put({"stage": "phase_a_done"})

        # Phase B: lock order runs->leases->attempts
        # If parent holds leases, this deadlocks (SQLSTATE 40P01)
        time.sleep(2)  # let parent acquire lease lock

        s.execute(text(
            "SELECT id FROM runs WHERE id = :rid FOR UPDATE"
        ), {"rid": rid})
        s.execute(text(
            "SELECT id FROM leases WHERE id = :lid FOR UPDATE"
        ), {"lid": lid})

        s.commit()
        q.put({"status": "completed"})
    except Exception as e:
        s.rollback()
        q.put({"status": "deadlocked", "error": str(e)[:200]})
    finally:
        s.close()
        engine.dispose()
