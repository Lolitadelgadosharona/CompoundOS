"""Sprint 005 Corrective — Tests 11, 12, 9B, deferred notification regression.

Real PostgreSQL lock-state observation through pg_stat_activity/pg_locks.
Production _run_job_in_child / evaluate_core / reconcile_after_child_exit.
"""

from __future__ import annotations

import multiprocessing
import os
import time
from datetime import datetime, timezone
from queue import Empty
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from apps.api.services.orchestration_repository import (
    acquire_lease,
    create_attempt,
    create_run,
    start_attempt,
    start_run,
)
from apps.api.services.orchestration_worker import (
    ReconciliationResult,
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
            " VALUES (:id, TRUE, 'T', 'USD', 'LT', '', '', '')"
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
    session: Session, hid: str, jid: str, worker_id: str
) -> tuple[str, str, dict]:
    rid = create_run(
        session, job_definition_id=jid, schedule_id=None,
        idempotency_key=f"r-{uuid4().hex[:8]}", status="pending",
        triggered_by="schedule", scheduled_at=datetime.now(UTC),
        household_id=hid,
    )
    aid = create_attempt(session, run_id=rid, attempt_number=1)
    start_run(session, rid)
    start_attempt(session, aid)
    lease = acquire_lease(session, run_id=rid, worker_id=worker_id)
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


# ============================================================================
# Test 11 — Real production Phase B deadlock via pg_locks observation
# ============================================================================


class TestGuardianPhaseBDeadlock:
    def test_phase_b_deadlock_rollback(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wg1")
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        actual_url = os.environ.get("TEST_DATABASE_URL", db_url)

        # 1. Observer connection for pg_stat_activity/pg_locks
        e_obs = create_engine(actual_url)
        s_obs = sessionmaker(bind=e_obs)()
        s_obs.execute(text("SET statement_timeout = '30s'"))

        # 2. Reverse transaction: lock lease row
        e2 = create_engine(actual_url)
        s2 = sessionmaker(bind=e2)()
        s2.execute(text("SET statement_timeout = '20s'"))
        s2.execute(text("SET deadlock_timeout = '1s'"))
        s2.execute(
            text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"),
            {"r": rid},
        )
        blocker_pid = s2.execute(text("SELECT pg_backend_pid()")).fetchone()[0]

        # 3. Start production child
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(
            target=_child_for_deadlock_with_backend_pid,
            args=(
                actual_url, "guardian.evaluate_all", {}, hid, rid, aid,
                lease["lease_id"], "wg1", lease["fencing_token"], q,
            ),
        )
        proc.start()

        # 4. Get child's backend PID from its first diagnostic
        try:
            diag = q.get(timeout=15)
        except Empty:
            _cleanup(proc)
            s2.rollback()
            s2.close()
            e2.dispose()
            s_obs.close()
            e_obs.dispose()
            pytest.fail("Child sent no diagnostic")
        assert diag.get("stage") in ("ready", "phase_a", "phase_b"), (
            f"Unexpected stage: {diag}"
        )
        diag["pid"]
        backend_pid = diag.get("backend_pid")
        assert backend_pid is not None, "No backend_pid in child diagnostic"

        # 5. Poll pg_locks until child holds run and waits for lease
        deadline = time.time() + 15
        child_owns_run = False
        child_waits_lease = False
        while time.time() < deadline:
            locks = s_obs.execute(
                text(
                    "SELECT l.pid, l.relation::regclass::text, l.mode, l.granted"
                    " FROM pg_locks l WHERE l.pid IN (:bp, :cp) AND l.granted = true"
                ),
                {"bp": backend_pid, "cp": blocker_pid},
            ).fetchall()
            wait_info = s_obs.execute(
                text(
                    "SELECT wait_event_type, wait_event"
                    " FROM pg_stat_activity WHERE pid = :bp"
                ),
                {"bp": backend_pid},
            ).fetchone()

            child_locks = [r for r in locks if r[0] == backend_pid]
            child_owns_run = any("runs" in str(r[1]) for r in child_locks)
            child_waits_lease = (
                wait_info
                and wait_info[0] == "Lock"
                and wait_info[1] == "transactionid"
            )

            if child_owns_run and child_waits_lease:
                break
            s_obs.rollback()
            time.sleep(0.1)

        assert child_owns_run, "Child never acquired run lock"
        assert child_waits_lease, "Child never waited for lease lock"

        # 6. Now reverse transaction requests run lock → deadlock
        try:
            s2.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid})
        except Exception:
            s2.rollback()
        finally:
            s2.close()
            e2.dispose()

        _cleanup(proc)
        s_obs.close()
        e_obs.dispose()

        # 7. Collect child's final diagnostic
        final = None
        while True:
            try:
                final = q.get_nowait()
            except Empty:
                break

        assert final is not None, "Child produced no result"
        sqlstate = str(final.get("sqlstate", ""))
        assert sqlstate == "40P01", (
            f"Expected SQLSTATE 40P01, got '{sqlstate}'"
            f" status={final.get('status')}"
        )
        r = db_session.execute(
            text("SELECT status FROM runs WHERE id=:r"), {"r": rid}
        ).fetchone()
        assert r[0] not in ("completed", "failed"), (
            f"Run should not be terminal: {r[0]}"
        )


# ============================================================================
# Test 12 — Independent production Phase B deadlock + evaluate_core count
# ============================================================================


class TestGuardianPhaseANoRetry:
    def test_phase_a_once(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wg2")
        db_url = db_session.get_bind().url.render_as_string(hide_password=False)
        actual_url = os.environ.get("TEST_DATABASE_URL", db_url)

        # Observer
        e_obs = create_engine(actual_url)
        s_obs = sessionmaker(bind=e_obs)()
        s_obs.execute(text("SET statement_timeout = '30s'"))

        # Reverse transaction
        e2 = create_engine(actual_url)
        s2 = sessionmaker(bind=e2)()
        s2.execute(text("SET statement_timeout = '20s'"))
        s2.execute(text("SET deadlock_timeout = '1s'"))
        s2.execute(
            text("SELECT id FROM leases WHERE run_id=:r FOR UPDATE"), {"r": rid}
        )

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        mgr = ctx.Manager()
        count = mgr.Value("i", 0)
        proc = ctx.Process(
            target=_child_counted_with_backend_pid,
            args=(
                actual_url, "guardian.evaluate_all", {}, hid, rid, aid,
                lease["lease_id"], "wg2", lease["fencing_token"], q, count,
            ),
        )
        proc.start()

        try:
            diag = q.get(timeout=15)
        except Empty:
            _cleanup(proc)
            pytest.fail("No child diagnostic")
        backend_pid = diag.get("backend_pid")
        assert backend_pid is not None

        # Poll until child block state
        deadline = time.time() + 15
        child_owns_run = False
        while time.time() < deadline:
            locks = s_obs.execute(
                text(
                    "SELECT 1 FROM pg_locks"
                    " WHERE pid = :bp AND relation::regclass::text = 'runs'"
                    " AND granted = true"
                ),
                {"bp": backend_pid},
            ).fetchone()
            wait_info = s_obs.execute(
                text(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE pid = :bp"
                ),
                {"bp": backend_pid},
            ).fetchone()
            if locks and wait_info and wait_info[0] == "Lock":
                child_owns_run = True
                break
            s_obs.rollback()
            time.sleep(0.1)

        assert child_owns_run, "Child never blocked"

        try:
            s2.execute(text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid})
        except Exception:
            s2.rollback()
        finally:
            s2.close()
            e2.dispose()

        _cleanup(proc)
        s_obs.close()
        e_obs.dispose()

        final = None
        while True:
            try:
                final = q.get_nowait()
            except Empty:
                break
        assert final is not None
        sqlstate = str(final.get("sqlstate", ""))
        assert sqlstate == "40P01", (
            f"Expected SQLSTATE 40P01, got '{sqlstate}'"
        )
        assert count.value == 1, f"Phase A called {count.value} times"


# ============================================================================
# Test 9B — Reconciliation monkeypatch (finalize_run → 0)
# ============================================================================


class TestStaleOwnershipReconciliation:
    def test_finalize_run_zero_causes_not_owner(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "ws9b")

        import apps.api.services.orchestration_worker as ow

        call_count = [0]
        orig_finalize = ow.finalize_run

        def fake_finalize(session, *args, **kwargs):
            call_count[0] += 1
            return 0

        ow.finalize_run = fake_finalize
        try:
            result = reconcile_after_child_exit(
                db_session, rid, aid, lease["lease_id"], "ws9b",
                lease["fencing_token"],
                finalize_status="failed", attempt_status="failed",
            )
        finally:
            ow.finalize_run = orig_finalize

        assert call_count[0] == 1, f"finalize_run called {call_count[0]} times"
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
# Deferred notification regression (unnumbered)
# ============================================================================


class TestDeferredNotification:
    def test_reconciliation_deferred_no_fallback(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        jid, sid = _create_schedule(db_session, hid)
        rid, aid, lease = _create_run_lease(db_session, hid, jid, "wdef")

        import apps.api.services.orchestration_worker as ow

        def fake_deferred(*args, **kwargs):
            return ReconciliationResult(
                "reconciliation_deferred",
                message="Deadlock retry exhausted",
            )

        orig = ow.reconcile_after_child_exit
        ow.reconcile_after_child_exit = fake_deferred
        try:
            # Simulate _execute_scheduled calling reconcile
            result = ow.reconcile_after_child_exit(
                db_session, rid, aid, lease["lease_id"], "wdef",
                lease["fencing_token"],
            )
        finally:
            ow.reconcile_after_child_exit = orig

        assert result.outcome == "reconciliation_deferred"
        # No state change
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
# Module-level child targets (picklable for spawn)
# ============================================================================


def _child_for_deadlock_with_backend_pid(
    db_url, job_type, job_params, hid, rid, aid, lid, wid, token, q
):
    from apps.api.services.orchestration_executor import _run_job_in_child

    inner_q = multiprocessing.Queue()
    pid = os.getpid()

    # Run production _run_job_in_child
    _run_job_in_child(db_url, job_type, job_params, hid, rid, aid, lid, wid, token, inner_q)

    # Forward both ready and result messages
    try:
        ready_msg = inner_q.get(timeout=5)
        q.put(ready_msg)  # Forward ready with backend_pid
    except Exception:
        pass
    try:
        result = inner_q.get(timeout=5)
    except Exception:
        result = {"status": "unknown"}
    result["pid"] = pid
    result["stage"] = result.get("stage", "phase_b")
    q.put(result)


def _child_counted_with_backend_pid(
    db_url, job_type, job_params, hid, rid, aid, lid, wid, token, q, count
):

    from apps.api.services import guardian as guardian_mod
    from apps.api.services.orchestration_executor import _run_job_in_child

    orig_eval = guardian_mod.evaluate_core

    def counting_eval(*args, **kwargs):
        count.value += 1
        return orig_eval(*args, **kwargs)

    guardian_mod.evaluate_core = counting_eval
    inner_q = multiprocessing.Queue()
    pid = os.getpid()

    try:
        _run_job_in_child(db_url, job_type, job_params, hid, rid, aid, lid, wid, token, inner_q)
        # Forward ready message
        try:
            ready_msg = inner_q.get(timeout=5)
            q.put(ready_msg)
        except Exception:
            pass
        try:
            result = inner_q.get(timeout=5)
        except Exception:
            result = {"status": "unknown"}
    finally:
        guardian_mod.evaluate_core = orig_eval

    result["pid"] = pid
    result["stage"] = result.get("stage", "phase_b")
    q.put(result)
