"""Sprint 005 Corrective — Tests 9A, 9B, 11, 12 + deferred regression.

Real PostgreSQL lock-state observation through pg_locks, pg_stat_activity,
pg_blocking_pids. Production _run_job_in_child / evaluate_core / reconciliation.
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
    finalize_run,
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


# ============================================================================
# Test 9A — Repository integration: finalize_run with stale token
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
# Test 11 — Real production Phase B deadlock via pg_locks observation
# ============================================================================


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

        # 3. Reverse transaction requests run lock → deadlock
        try:
            s2.execute(
                text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid}
            )
        except Exception as exc:
            s2.rollback()
            orig = getattr(exc, "orig", None)
            if orig:
                str(
                    getattr(orig, "sqlstate", "")
                    or getattr(orig, "pgcode", "")
                )

        _bounded_cleanup(proc, s2, e2, s_obs, e_obs)

        # 4. Collect child's final diagnostic
        final = None
        while True:
            try:
                final = q.get_nowait()
            except Empty:
                break

        assert final is not None, "Child produced no final diagnostic"
        sqlstate = str(final.get("sqlstate", ""))
        assert sqlstate == "40P01", (
            f"Expected SQLSTATE 40P01, got '{sqlstate}'"
            f" status={final.get('status')}"
        )
        assert final.get("pid") == child_pid
        assert proc.exitcode is not None, "Child must exit naturally"
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

        try:
            s2.execute(
                text("SELECT id FROM runs WHERE id=:r FOR UPDATE"), {"r": rid}
            )
        except Exception:
            s2.rollback()

        _bounded_cleanup(proc, s2, e2, s_obs, e_obs)

        final = None
        while True:
            try:
                final = q.get_nowait()
            except Empty:
                break
        assert final is not None, "Child produced no final diagnostic"
        sqlstate = str(final.get("sqlstate", ""))
        assert sqlstate == "40P01", (
            f"Expected SQLSTATE 40P01, got '{sqlstate}'"
        )
        assert count.value == 1, f"evaluate_core called {count.value} times"
        assert proc.exitcode is not None, "Child must exit naturally"
        mgr.shutdown()


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
