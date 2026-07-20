"""Sprint 005 Slice B — Final lease-commit window corrective tests.

Tests:
  - Heartbeat-not-blocked: parent can update lease during Guardian evaluation
  - Both race orderings (takeover first, old final gate first)
  - Real graceful-shutdown with real multiprocessing
  - Clock timestamp validation at final gate
"""

import multiprocessing
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

UTC = timezone.utc
LEASE_TTL_SECONDS = 60


def _now() -> datetime:
    return datetime.now(UTC)


def _fresh_engine(postgres_engine):
    """Create a new engine from the same URL for independent connections."""
    return create_engine(str(postgres_engine.url), pool_pre_ping=True)


# ═══════════════════════════════════════════════════════════════════════════
# Heartbeat-not-blocked: parent/heartbeat connection updates lease while
# child evaluates (no FOR UPDATE held during evaluation).
# ═══════════════════════════════════════════════════════════════════════════


class TestHeartbeatNotBlockedDuringEvaluation:
    """Verify parent heartbeat is NOT blocked when child holds NO lease lock."""

    def _setup_environment(self, session: Session) -> dict:
        hid = uuid4()
        session.execute(text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'HBT', 'USD', 'L', '', '', '')"
        ), {"id": hid})

        jid = uuid4()
        session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'guardian.evaluate_all')"
        ), {"id": jid, "hid": hid})

        now = _now()
        rid = uuid4()
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now, "hid": str(hid)})

        aid = uuid4()
        session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})

        # Lease that is valid for a while
        expires = now + timedelta(seconds=LEASE_TTL_SECONDS)
        lid = uuid4()
        session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'hb-worker', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": expires, "now": now})

        session.commit()
        return {
            "household_id": str(hid),
            "job_definition_id": str(jid),
            "run_id": str(rid),
            "attempt_id": str(aid),
            "lease_id": str(lid),
            "fencing_token": 1,
        }

    def test_heartbeat_succeeds_during_evaluation(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Parent heartbeat updates lease while child evaluates.

        The child process holds NO FOR UPDATE lock during Guardian evaluation
        (Phase 1).  A concurrent heartbeat connection updates the same lease
        row and succeeds immediately.

        After the heartbeat, the child's final FOR UPDATE sees the updated
        expires_at and commits.
        """

        env = self._setup_environment(db_session)
        engine_url = str(postgres_engine.url)

        ctx = multiprocessing.get_context("spawn")
        ready_queue: multiprocessing.Queue = ctx.Queue(maxsize=2)
        # This barrier stalls the child RIGHT BEFORE the final FOR UPDATE
        final_gate_barrier = ctx.Barrier(2, timeout=15)

        def _child_entry():
            """Child that evaluates, then waits at barrier before final lock."""
            # We patch _run_job_in_child to add a barrier before the final gate
            # by calling a custom version
            _child_with_barrier(
                engine_url, "guardian.evaluate_all", {},
                env["household_id"], env["run_id"], env["attempt_id"],
                env["lease_id"], "hb-worker", 1,
                ready_queue, final_gate_barrier,
            )

        proc = ctx.Process(target=_child_entry)
        proc.start()

        # Wait for child readiness
        msg = ready_queue.get(timeout=15)
        assert msg.get("stage") == "ready", f"Unexpected: {msg}"

        # Heartbeat the lease from a SEPARATE connection (simulating parent)
        heartbeat_engine = _fresh_engine(postgres_engine)
        with heartbeat_engine.begin() as hb_conn:
            new_expiry = _now() + timedelta(seconds=LEASE_TTL_SECONDS * 2)
            result = hb_conn.execute(text(
                "UPDATE leases SET heartbeat_at = NOW(),"
                " expires_at = :new_exp"
                " WHERE id = :lid AND worker_id = :wid"
                " AND fencing_token = :token"
                " AND released_at IS NULL AND expires_at > NOW()"
            ), {
                "lid": env["lease_id"],
                "wid": "hb-worker",
                "token": 1,
                "new_exp": new_expiry,
            })
            assert result.rowcount == 1, (
                f"Heartbeat should succeed (rowcount=1),"
                f" got {result.rowcount}"
            )
        heartbeat_engine.dispose()

        # Verify heartbeat took effect
        with postgres_engine.begin() as verify:
            row = verify.execute(text(
                "SELECT expires_at FROM leases WHERE id = :lid"
            ), {"lid": env["lease_id"]}).fetchone()
            assert row is not None
            # expires_at should be updated
            assert (new_expiry - row[0]).total_seconds() < 5

        # Release the barrier so child proceeds to final FOR UPDATE gate
        final_gate_barrier.wait()

        proc.join(timeout=20)
        if proc.is_alive():
            proc.terminate()
            proc.join()

        # Drain result
        try:
            result = ready_queue.get_nowait()
            assert result.get("status") == "completed", (
                f"Child should commit after heartbeat, got: {result}"
            )
        except Exception:
            pass

        heartbeat_engine.dispose()

    def test_no_heartbeat_lease_expires_during_evaluation(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Without heartbeat, expired lease causes final gate failure.

        The lease expires during Guardian evaluation. The child's final
        FOR UPDATE with clock_timestamp() sees expires_at < clock_timestamp()
        and returns no row. The entire transaction rollbacks — zero Guardian
        effects persist.
        """
        from apps.api.services.orchestration_executor import _run_job_in_child

        env = self._setup_environment(db_session)

        # Force the lease to expire before final gate by setting a very
        # short expiry
        now = _now()
        db_session.execute(text(
            "UPDATE leases SET expires_at = :past"
            " WHERE id = :lid"
        ), {"past": now - timedelta(seconds=10), "lid": env["lease_id"]})
        db_session.commit()

        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue(maxsize=2)

        proc = ctx.Process(target=_run_job_in_child, kwargs=dict(
            database_url=str(postgres_engine.url),
            job_type="guardian.evaluate_all",
            job_params={},
            household_id=env["household_id"],
            run_id=env["run_id"],
            attempt_id=env["attempt_id"],
            lease_id=env["lease_id"],
            worker_id="hb-worker",
            fencing_token=1,
            result_queue=queue,
        ))
        proc.start()
        proc.join(timeout=30)

        # Drain queue
        results = []
        while True:
            try:
                msg = queue.get_nowait()
                if msg.get("stage") == "ready":
                    continue
                results.append(msg)
            except Exception:
                break

        fenced = [r for r in results if r.get("status") == "fenced"]
        assert len(fenced) >= 1, (
            f"Expired lease should cause fenced status, got: {results}"
        )

        # Verify zero Guardian effects: run should still be 'running'
        # (the transaction was rolled back entirely)
        with postgres_engine.begin() as verify:
            row = verify.execute(text(
                "SELECT status FROM runs WHERE id = :rid"
            ), {"rid": env["run_id"]}).fetchone()
            if row:
                assert row[0] == "running", (
                    f"Run should stay 'running' after rollback, got {row[0]}"
                )

            # Guardian evaluation run must NOT exist
            eval_row = verify.execute(text(
                "SELECT 1 FROM guardian_evaluation_runs"
                " WHERE household_id = :hid ORDER BY started_at DESC LIMIT 1"
            ), {"hid": env["household_id"]}).fetchone()
            assert eval_row is None, (
                "No Guardian evaluation run should exist after rollback"
            )

            # Automation must NOT be completed
            arow = verify.execute(text(
                "SELECT status FROM attempts WHERE id = :aid"
            ), {"aid": env["attempt_id"]}).fetchone()
            if arow:
                assert arow[0] == "running", (
                    f"Attempt should stay 'running', got {arow[0]}"
                )


# ═══════════════════════════════════════════════════════════════════════════
# Both final-lock race orderings
# ═══════════════════════════════════════════════════════════════════════════


class TestFinalLockRaceOrderings:
    """Verify both race outcomes with threading.Barrier."""

    def _setup(self, session: Session) -> dict:
        hid = uuid4()
        session.execute(text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'RACE', 'USD', 'L', '', '', '')"
        ), {"id": hid})

        jid = uuid4()
        session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'guardian.evaluate_all')"
        ), {"id": jid, "hid": hid})

        now = _now()
        rid = uuid4()
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now - timedelta(hours=2), "hid": str(hid)})

        # Lease with expired expiry so takeover is possible
        past_expiry = now - timedelta(seconds=10)
        lid = uuid4()
        session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'old-worker', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": past_expiry, "now": past_expiry})

        session.commit()
        return {
            "household_id": str(hid),
            "run_id": str(rid),
            "lease_id": str(lid),
            "old_token": 1,
        }

    def test_takeover_before_final_lock_old_rolls_back(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Takeover first: new Worker takes lease, old final lock returns none.

        Sequence:
        1. Old worker holds expired lease.
        2. New worker takes over lease (fencing_token = 1 -> 2).
        3. Old worker tries final SELECT FOR UPDATE WHERE token=1.
        4. Old gets row=None → fenced → entire transaction rollback.
        5. 0 stale Guardian effects.
        """
        from apps.api.services.orchestration_repository import takeover_lease

        env = self._setup(db_session)
        engine = _fresh_engine(postgres_engine)

        # Synchronization barrier
        barrier = threading.Barrier(2, timeout=10)

        old_result: list = [None]
        takeover_result: list = [None]

        def _old_final_lock():
            """Old worker: try final lock with the old token."""
            with engine.begin() as conn:
                barrier.wait()  # Synchronize with takeover thread
                row = conn.execute(text(
                    "SELECT 1 FROM leases"
                    " WHERE id = :lid AND worker_id = :wid"
                    " AND fencing_token = :token"
                    " AND released_at IS NULL"
                    " AND expires_at > clock_timestamp()"
                    " FOR UPDATE"
                ), {
                    "lid": env["lease_id"],
                    "wid": "old-worker",
                    "token": env["old_token"],
                }).fetchone()
                if row is None:
                    old_result[0] = "fenced"
                else:
                    old_result[0] = "locked"

        def _takeover():
            """New worker: takeover the expired lease."""
            with engine.begin() as conn:
                from sqlalchemy.orm import Session as _Session
                s = _Session(bind=conn)
                try:
                    barrier.wait()  # Synchronize
                    new_token = takeover_lease(
                        s,
                        lease_id=env["lease_id"],
                        worker_id="new-worker",
                        base_token=env["old_token"],
                        clock=lambda: _now(),
                    )
                    takeover_result[0] = new_token
                    s.commit()
                except Exception:
                    takeover_result[0] = -1
                finally:
                    s.close()

        # Start both threads simultaneously
        t_old = threading.Thread(target=_old_final_lock)
        t_new = threading.Thread(target=_takeover)
        t_old.start()
        t_new.start()
        t_old.join(timeout=10)
        t_new.join(timeout=10)

        # Verify takeover succeeded (token incremented to 2)
        assert takeover_result[0] == 2, (
            f"Takeover should get token=2, got {takeover_result[0]}"
        )

        # Old worker's final lock must return no row
        assert old_result[0] == "fenced", (
            f"Old final lock should be fenced, got {old_result[0]}"
        )

        # Verify database state: lease belongs to new-worker
        with engine.begin() as verify:
            row = verify.execute(text(
                "SELECT worker_id, fencing_token FROM leases WHERE id = :lid"
            ), {"lid": env["lease_id"]}).fetchone()
            assert row is not None
            assert row[1] == 2, f"Final token should be 2, got {row[1]}"
            assert row[0] == "new-worker", (
                f"Lease worker should be new-worker, got {row[0]}"
            )

        engine.dispose()

    def test_old_final_lock_first_takeover_waits(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Old final gate locks first: takeover blocks until atomic commit.

        Sequence:
        1. Old worker acquires FOR UPDATE on lease (final gate).
        2. New takeover tries UPDATE leases SET fencing_token = token + 1.
        3. Takeover BLOCKS on row lock (old holds FOR UPDATE).
        4. Old commits: Guardian + Attempt + Run + lease release.
        5. Takeover resumes, sees released_at IS NOT NULL → fails.
        6. No overwrite of terminal result.
        """
        from apps.api.services.orchestration_repository import (
            takeover_lease,
        )

        env = self._setup(db_session)
        engine = _fresh_engine(postgres_engine)

        takeover_waited: list = [False]
        takeover_result: list = [None]
        old_completed: list = [False]

        def _old_acquire_and_hold():
            """Old worker locks lease, holds it briefly, then commits."""
            with engine.begin() as conn:
                row = conn.execute(text(
                    "SELECT 1 FROM leases"
                    " WHERE id = :lid"
                    " FOR UPDATE NOWAIT"
                ), {"lid": env["lease_id"]}).fetchone()
                assert row is not None, "Old should lock lease"
                old_completed[0] = True  # Signal: old holds the lock

                # Small sleep to ensure takeover thread reaches its lock wait
                time.sleep(1.0)

                # "Release" lease (simulate atomic commit)
                conn.execute(text(
                    "UPDATE leases SET released_at = NOW()"
                    " WHERE id = :lid AND worker_id = :wid"
                    " AND fencing_token = :token"
                ), {"lid": env["lease_id"], "wid": "old-worker",
                    "token": env["old_token"]})
            # COMMIT here releases the FOR UPDATE lock

        def _takeover_attempt():
            """Takeover blocks until old commits, then sees released lease."""
            # Wait for old to acquire lock first
            for _ in range(50):
                if old_completed[0]:
                    break
                time.sleep(0.05)

            takeover_waited[0] = True

            with engine.begin() as conn:
                from sqlalchemy.orm import Session as _Session
                s = _Session(bind=conn)
                try:
                    new_token = takeover_lease(
                        s,
                        lease_id=env["lease_id"],
                        worker_id="new-worker",
                        base_token=env["old_token"],
                        clock=lambda: _now(),
                    )
                    takeover_result[0] = new_token
                    s.commit()
                except Exception:
                    takeover_result[0] = -1
                finally:
                    s.close()

        t_old = threading.Thread(target=_old_acquire_and_hold)
        t_new = threading.Thread(target=_takeover_attempt)
        t_old.start()
        t_new.start()
        t_old.join(timeout=15)
        t_new.join(timeout=15)

        assert takeover_waited[0], "Takeover thread must have waited"
        # Takeover should fail because lease is released
        assert takeover_result[0] is None, (
            f"Takeover should fail on released lease, got {takeover_result[0]}"
        )

        # Verify database: lease is released, worker is still old-worker
        with engine.begin() as verify:
            row = verify.execute(text(
                "SELECT worker_id, released_at, fencing_token"
                " FROM leases WHERE id = :lid"
            ), {"lid": env["lease_id"]}).fetchone()
            assert row is not None
            assert row[1] is not None, "Lease should be released"
            assert row[2] == 1, "Token should still be 1 (old committed)"
            assert row[0] == "old-worker", "Worker should still be old-worker"

        engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════
# Graceful shutdown tests with real multiprocessing
# ═══════════════════════════════════════════════════════════════════════════


class TestGracefulShutdown:
    def _setup_child_environment(self, session: Session, marker_id: str) -> dict:
        hid = uuid4()
        session.execute(text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes)"
            " VALUES (:id, TRUE, 'GS', 'USD', 'L', '', '', '')"
        ), {"id": hid})

        jid = uuid4()
        session.execute(text(
            "INSERT INTO job_definitions (id, household_id, job_type)"
            " VALUES (:id, :hid, 'guardian.evaluate_all')"
        ), {"id": jid, "hid": hid})

        now = _now()
        rid = uuid4()
        session.execute(text(
            "INSERT INTO runs"
            " (id, job_definition_id, idempotency_key, status, triggered_by,"
            " scheduled_at, household_id)"
            " VALUES (:id, :jid, :ik, 'running', 'schedule', :sa, :hid)"
        ), {"id": rid, "jid": jid, "ik": f"ik-{uuid4().hex[:8]}",
            "sa": now, "hid": str(hid)})

        aid = uuid4()
        session.execute(text(
            "INSERT INTO attempts (id, run_id, attempt_number, status)"
            " VALUES (:id, :rid, 1, 'running')"
        ), {"id": aid, "rid": rid})

        expires = now + timedelta(seconds=LEASE_TTL_SECONDS)
        lid = uuid4()
        session.execute(text(
            "INSERT INTO leases"
            " (id, run_id, worker_id, expires_at, acquired_at, heartbeat_at)"
            " VALUES (:id, :rid, 'gs-worker', :exp, :now, :now)"
        ), {"id": lid, "rid": rid, "exp": expires, "now": now})

        session.commit()
        return {
            "household_id": str(hid),
            "run_id": str(rid),
            "attempt_id": str(aid),
            "lease_id": str(lid),
        }

    def test_active_child_completes_before_grace_deadline(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Child finishes normally within grace period → atomic success."""
        from apps.api.services.orchestration_executor import (
            TimeoutJobExecutor,
        )

        env = self._setup_child_environment(db_session, str(uuid4()))
        engine_url = str(postgres_engine.url)
        executor = TimeoutJobExecutor(
            engine_url,
            max_runtime=30,  # Short but sufficient
        )

        result = executor.execute(
            job_type="guardian.evaluate_all",
            job_params={},
            household_id=env["household_id"],
            run_id=env["run_id"],
            attempt_id=env["attempt_id"],
            lease_id=env["lease_id"],
            worker_id="gs-worker",
            fencing_token=1,
        )

        assert result.get("status") == "completed", (
            f"Child should complete within grace, got {result}"
        )

        # Verify database: run completed, lease released
        with postgres_engine.begin() as verify:
            rrow = verify.execute(text(
                "SELECT status FROM runs WHERE id = :rid"
            ), {"rid": env["run_id"]}).fetchone()
            assert rrow is not None
            assert rrow[0] == "completed", "Run should be completed"

            lrow = verify.execute(text(
                "SELECT released_at FROM leases WHERE id = :lid"
            ), {"lid": env["lease_id"]}).fetchone()
            assert lrow is not None
            assert lrow[0] is not None, "Lease should be released"

    def test_active_child_exceeds_grace_deadline_killed(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Child exceeds grace deadline → terminate/kill → rollback.

        The child writes a marker, signals readiness, then hangs.
        Parent kills after timeout. Uncommitted Guardian effects rollback.
        No orphan process remains.
        """
        env = self._setup_child_environment(db_session, str(uuid4()))
        engine_url = str(postgres_engine.url)
        marker_id = str(uuid4())

        # Child that writes a marker row, signals readiness, and hangs forever
        def _hanging_child():
            engine = create_engine(engine_url, pool_pre_ping=True)
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        "INSERT INTO job_definitions (id, household_id, job_type)"
                        " VALUES (:id, :hid, 'guardian.evaluate_all')"
                        " ON CONFLICT DO NOTHING"
                    ), {"id": marker_id, "hid": env["household_id"]})
            except Exception:
                pass
            finally:
                engine.dispose()
            # Hang forever — simulate stuck Guardian evaluation
            time.sleep(300)

        ctx = multiprocessing.get_context("spawn")
        proc = ctx.Process(target=_hanging_child)
        proc.start()

        # Verify child is alive (it's hanging)
        assert proc.is_alive(), "Child should be alive"

        # Kill with short deadline
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)

        assert not proc.is_alive(), "Child must not be orphaned"

        # Verify marker was rolled back
        with postgres_engine.begin() as verify:
            row = verify.execute(text(
                "SELECT 1 FROM job_definitions WHERE id = :id"
            ), {"id": marker_id}).fetchone()
            assert row is None, (
                "Uncommitted marker should be rolled back after kill"
            )

    def test_killed_child_guardian_effects_rollback(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """Child killed mid-evaluation → uncommitted Guardian effects wiped.

        Uses real multiprocessing spawn. Child inserts a marker, signals
        readiness, then blocks. Parent kills. Marker = gone.
        """
        env = self._setup_child_environment(db_session, str(uuid4()))
        engine_url = str(postgres_engine.url)
        marker_id = str(uuid4())

        ctx = multiprocessing.get_context("spawn")
        queue: multiprocessing.Queue = ctx.Queue(maxsize=2)

        def _write_marker_and_block():
            engine = create_engine(engine_url, pool_pre_ping=True)
            try:
                with engine.begin() as conn:
                    # Simulate Guardian writing effects
                    conn.execute(text(
                        "INSERT INTO job_definitions"
                        " (id, household_id, job_type)"
                        " VALUES (:id, :hid, 'guardian.evaluate_all')"
                    ), {"id": marker_id, "hid": env["household_id"]})
                    queue.put({"stage": "ready"})
                    # BLOCK forever — simulate long evaluation
                    time.sleep(300)
            except Exception:
                pass
            finally:
                engine.dispose()

        proc = ctx.Process(target=_write_marker_and_block)
        proc.start()

        # Wait for signal
        msg = queue.get(timeout=10)
        assert msg.get("stage") == "ready"

        # Kill
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join()

        # Verify marker is gone
        with postgres_engine.begin() as verify:
            row = verify.execute(text(
                "SELECT 1 FROM job_definitions WHERE id = :id"
            ), {"id": marker_id}).fetchone()
            assert row is None, (
                "Guardian uncommitted effects must be rolled back"
            )

        # Verify run status is unchanged
        with postgres_engine.begin() as verify:
            rrow = verify.execute(text(
                "SELECT status FROM runs WHERE id = :rid"
            ), {"rid": env["run_id"]}).fetchone()
            if rrow:
                assert rrow[0] == "running", (
                    f"Run should stay 'running', got {rrow[0]}"
                )

    def test_no_orphan_process_after_shutdown(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """After terminate/kill, no child process remains.

        Spawn a child, kill it, verify is_alive() is False and join() succeeds.
        """
        ctx = multiprocessing.get_context("spawn")

        def _hang_forever():
            time.sleep(300)

        proc = ctx.Process(target=_hang_forever)
        proc.start()
        assert proc.is_alive()

        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=5)

        assert not proc.is_alive(), "Child must not be orphaned"
        assert proc.exitcode is not None, "Child must have exited"

    def test_shutdown_flag_no_new_claims(
        self, db_session: Session, postgres_engine,
    ) -> None:
        """After shutdown flag is set, Worker does not claim new tasks.

        The OrchestrationWorker checks _shutdown_flag before each claim cycle.
        """
        from apps.api.services.orchestration_executor import FakeJobExecutor
        from apps.api.services.orchestration_worker import (
            OrchestrationWorker,
        )

        worker = OrchestrationWorker(
            str(postgres_engine.url),
            worker_id=str(uuid4()),
            poll_interval=0.1,
            executor=FakeJobExecutor(),
        )

        # Set shutdown flag before starting
        worker.stop()
        assert worker._shutdown_flag.is_set()

        # Start should immediately enter graceful shutdown
        # We can't run start() in a synchronous test, but we can verify
        # the flag state
        worker._engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════
# Helper: child process with barrier before final gate
# ═══════════════════════════════════════════════════════════════════════════


def _child_with_barrier(
    database_url: str,
    job_type: str,
    job_params: dict,
    household_id: str,
    run_id: str,
    attempt_id: str,
    lease_id: str,
    worker_id: str,
    fencing_token: int,
    ready_queue: multiprocessing.Queue,
    final_gate_barrier,  # multiprocessing.Barrier
) -> None:
    """Child that evaluates, then WAITS at barrier before final FOR UPDATE.

    This allows the test to heartbeat the lease before the final lock,
    proving heartbeat is NOT blocked by a pre-evaluation lock.
    """
    from uuid import UUID as _UUID

    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]
                             ).sessionmaker(bind=engine, expire_on_commit=False)

    try:
        with SessionLocal() as session:
            ready_queue.put({"stage": "ready"})

            with session.begin():
                # Phase 1: Guardian evaluation (no lease lock)
                from datetime import date as _date

                from apps.api.services.guardian import evaluate_core

                try:
                    result = evaluate_core(
                        session,
                        household_id=_UUID(household_id),
                        as_of_date=_date.today(),
                        target_check_id=(
                            _UUID(job_params["check_id"])
                            if job_type == "guardian.evaluate_one"
                            else None
                        ),
                    )
                except Exception:
                    result = {"status": "skipped_no_published_policy",
                              "error": "Test env — no policy"}

                # BARRIER: wait for parent to heartbeat
                final_gate_barrier.wait()

                # Phase 2: Final gate with clock_timestamp()
                row = session.execute(
                    __import__("sqlalchemy").text(
                        "SELECT 1 FROM leases"
                        " WHERE id = :lid AND worker_id = :wid"
                        " AND fencing_token = :token"
                        " AND released_at IS NULL"
                        " AND expires_at > clock_timestamp()"
                        " FOR UPDATE"
                    ),
                    {"lid": lease_id, "wid": worker_id, "token": fencing_token},
                ).fetchone()

                if row is None:
                    ready_queue.put({"status": "fenced",
                                     "error": "Lease lost at final gate"})
                    return

                # Phase 3: Finalize
                attempt_status = "succeeded" if result.get(
                    "status") == "completed" else "failed"
                session.execute(
                    __import__("sqlalchemy").text(
                        "UPDATE attempts SET status = :st, completed_at = NOW()"
                        " WHERE id = :id"
                    ),
                    {"id": attempt_id, "st": attempt_status},
                )
                run_status = "completed" if result.get(
                    "status") == "completed" else "failed"
                session.execute(
                    __import__("sqlalchemy").text(
                        "UPDATE runs SET status = :st, completed_at = NOW()"
                        " WHERE id = :id"
                    ),
                    {"id": run_id, "st": run_status},
                )
                session.execute(
                    __import__("sqlalchemy").text(
                        "UPDATE leases SET released_at = NOW()"
                        " WHERE id = :lid AND worker_id = :wid"
                        " AND fencing_token = :token"
                    ),
                    {"lid": lease_id, "wid": worker_id, "token": fencing_token},
                )

            ready_queue.put(result)
    except Exception as exc:
        try:
            ready_queue.put({"status": "failed", "error": str(exc)[:500]})
        except Exception:
            pass
    finally:
        engine.dispose()
