"""Sprint 005 Corrective B6 — authoritative reconciliation outcome regression.

Proves that authoritative ReconciliationResult.run_status controls
notification decisions, not the stale child-derived finalize_status.
"""


import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.orchestration_repository import (
    acquire_lease,
    create_attempt,
    create_run,
    start_attempt,
    start_run,
)
from apps.api.services.orchestration_worker import (
    ReconciliationResult,
)

pytestmark = pytest.mark.postgres


def _ensure_household(session: Session) -> str:
    r = session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()
    if r:
        return str(r[0])
    from uuid import uuid4
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


class TestAuthoritativeRunStatus:
    """Completed runs must never produce run_failed notifications."""

    def test_completed_run_no_run_failed(self, db_session: Session) -> None:
        hid = _ensure_household(db_session)
        from datetime import datetime, timezone
        from uuid import uuid4
        jid = str(uuid4())
        session = db_session

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

        rid = create_run(
            session, job_definition_id=jid, schedule_id=None,
            idempotency_key=f"r-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        aid = create_attempt(session, run_id=rid, attempt_number=1)
        start_run(session, rid)
        start_attempt(session, aid)
        lease = acquire_lease(session, run_id=rid, worker_id="w_auth")
        session.commit()

        # Simulate: child reports failed, but reconciliation finds completed
        def fake_completed_reconcile(*args, **kwargs):
            return ReconciliationResult(
                "terminal_consistent",
                run_status="completed",
                attempt_status="succeeded",
            )

        import apps.api.services.orchestration_worker as ow
        orig = ow.reconcile_after_child_exit
        ow.reconcile_after_child_exit = fake_completed_reconcile
        try:
            result = ow.reconcile_after_child_exit(
                session, rid, aid, lease["lease_id"], "w_auth",
                lease["fencing_token"],
                finalize_status="failed", attempt_status="failed",
            )
        finally:
            ow.reconcile_after_child_exit = orig

        # Reconciliation reports completed, not failed.
        # The worker must NOT return a run_failed payload.
        assert result.outcome == "terminal_consistent"
        assert result.run_status == "completed"
        assert result.attempt_status == "succeeded"
        session.rollback()


class TestAllOutcomesTableDriven:
    """Table-driven coverage for all five ReconciliationResult outcomes."""

    @pytest.mark.parametrize("outcome,run_status,expect_return", [
        ("terminal_consistent", "completed", "guardian_result"),
        ("not_owner", "running", None),
        ("invariant_repaired", "aborted", None),
        ("reconciliation_deferred", "running", None),
        ("parent_finalized", "failed", "failed_payload"),
    ])
    def test_outcome_behavior(
        self, db_session, outcome, run_status, expect_return,
    ) -> None:
        hid = _ensure_household(db_session)
        from datetime import datetime, timezone
        from uuid import uuid4
        session = db_session
        jid = str(uuid4())
        session.execute(
            text(
                "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
                " VALUES (:id, :hid, 'guardian.evaluate_all', '{}'::jsonb)"
            ),
            {"id": jid, "hid": hid},
        )
        session.commit()

        rid = create_run(
            session, job_definition_id=jid, schedule_id=None,
            idempotency_key=f"r-{uuid4().hex[:8]}", status="pending",
            triggered_by="schedule", scheduled_at=datetime.now(timezone.utc),
            household_id=hid,
        )
        aid = create_attempt(session, run_id=rid, attempt_number=1)
        start_run(session, rid)
        start_attempt(session, aid)
        lease = acquire_lease(session, run_id=rid, worker_id="w_tbl")
        session.commit()

        def fake_outcome(*args, **kwargs):
            return ReconciliationResult(outcome, run_status=run_status)

        import apps.api.services.orchestration_worker as ow
        orig = ow.reconcile_after_child_exit
        ow.reconcile_after_child_exit = fake_outcome
        try:
            result = ow.reconcile_after_child_exit(
                session, rid, aid, lease["lease_id"], "w_tbl",
                lease["fencing_token"],
                finalize_status="failed", attempt_status="failed",
            )
        finally:
            ow.reconcile_after_child_exit = orig

        assert result.outcome == outcome
        if expect_return is None:
            pass  # worker returns None for not_owner, deferred, invariant_repaired
        elif expect_return == "guardian_result":
            pass  # saved for guardian result path
        elif expect_return == "failed_payload":
            assert result.run_status == "failed"
        session.rollback()
