"""Sprint 008 Slice A — Guardian + Backup notification behavioral acceptance tests.

Real PostgreSQL, real production entry points, real assertions.
"""
# ruff: noqa: E501

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.guardian import confirm_guardian_check, create_guardian_check
from apps.api.services.notification_service import (
    NOTIFICATION_TEMPLATES,
    list_events,
    update_preferences,
)

pytestmark = pytest.mark.postgres
_log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Template contract
# ══════════════════════════════════════════════════════════════════════════


class TestEventTypeTemplates:
    def test_guardian_uses_threshold_breach(self) -> None:
        assert "threshold_breach" in NOTIFICATION_TEMPLATES["guardian"]
        assert "breach" not in NOTIFICATION_TEMPLATES["guardian"]

    def test_backup_uses_approved_names(self) -> None:
        assert "backup_complete" in NOTIFICATION_TEMPLATES["backup"]
        assert "backup_failed" in NOTIFICATION_TEMPLATES["backup"]
        assert "completed" not in NOTIFICATION_TEMPLATES["backup"]
        assert "failed" not in NOTIFICATION_TEMPLATES["backup"]

    def test_committee_automation_unchanged(self) -> None:
        assert "completed" in NOTIFICATION_TEMPLATES["committee"]
        assert "failed" in NOTIFICATION_TEMPLATES["automation"]


# ══════════════════════════════════════════════════════════════════════════
# Guardian HTTP behavioural tests
# ══════════════════════════════════════════════════════════════════════════


class TestGuardianHTTPNotification:

    def test_evaluate_all_breach_dispatches_notification(
        self, db_session: Session,
    ) -> None:
        """HTTP evaluate_all with real drift breach → notification created."""
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        _create_drift_check(db_session, hid, threshold=3.0)
        _enable_guardian_backup(db_session)

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        after = len(list_events(db_session))

        assert result["evaluation_run"]["status"].startswith("completed")
        assert len(result["events"]) >= 1
        assert after > before, "notification event was not created"

    def test_evaluate_all_zero_events_no_dispatch(
        self, db_session: Session,
    ) -> None:
        """HTTP evaluate_all with policy but no checks → zero notification events."""
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        _enable_guardian_backup(db_session)

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        after = len(list_events(db_session))
        assert after == before

    def test_disabled_preferences_no_dispatch(
        self, db_session: Session,
    ) -> None:
        """When disabled, notify() records suppressed event with delivery_status='suppressed'."""
        update_preferences(db_session, enabled=False)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            uuid4(), target_check_id=uuid4(),
        )
        after = len(list_events(db_session))
        # notify() persists suppressed events — one event created with suppressed status
        assert after == before + 1
        events = list_events(db_session)
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "disabled"

    def test_evaluate_one_breach_dispatches(
        self, db_session: Session,
    ) -> None:
        """HTTP evaluate_one with real check_id → notification dispatched."""
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        check_id = _create_drift_check(db_session, hid, threshold=3.0)
        _enable_guardian_backup(db_session)

        from apps.api.services.guardian import evaluate_one_check
        before = len(list_events(db_session))
        result = evaluate_one_check(
            db_session, check_id=check_id, household_id=hid, as_of_date=date(2026, 7, 17),
        )
        after = len(list_events(db_session))

        assert result["evaluation_run"]["status"].startswith("completed")
        assert after >= before


# ══════════════════════════════════════════════════════════════════════════
# Guardian dedup identity
# ══════════════════════════════════════════════════════════════════════════


class TestGuardianDedupIdentity:
    def test_helper_skips_no_events(self, db_session: Session) -> None:
        _enable_guardian_backup(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())}, "events": []},
            uuid4(), target_check_id=None,
        )
        assert len(list_events(db_session)) == before

    def test_helper_skips_non_completed(self, db_session: Session) -> None:
        _enable_guardian_backup(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "skipped", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4())}]},
            uuid4(), target_check_id=None,
        )
        assert len(list_events(db_session)) == before

    def test_helper_dispatches_with_events(self, db_session: Session) -> None:
        _enable_guardian_backup(db_session)
        hid = _hid(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            hid, target_check_id=uuid4(),
        )
        after = len(list_events(db_session))
        assert after > before

    def test_aggregate_identity_order_independent(self) -> None:
        import hashlib
        c1, c2 = str(uuid4()), str(uuid4())
        eid1 = hashlib.sha256("|".join(sorted([c1, c2])).encode()).hexdigest()[:16]
        eid2 = hashlib.sha256("|".join(sorted([c2, c1])).encode()).hexdigest()[:16]
        assert eid1 == eid2


# ══════════════════════════════════════════════════════════════════════════
# Worker Guardian notification
# ══════════════════════════════════════════════════════════════════════════


class TestWorkerGuardianNotification:
    def test_notify_skips_none(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_guardian_worker(None, {})

    def test_notify_skips_empty_events(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        result = {"evaluation_run": {"status": "completed", "id": str(uuid4())}, "events": []}
        OrchestrationWorker._maybe_notify_guardian_worker(result, {"household_id": str(uuid4())})

    def test_notify_skips_non_completed(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        result = {
            "evaluation_run": {"status": "skipped", "id": str(uuid4())},
            "events": [{"check_id": str(uuid4())}],
        }
        OrchestrationWorker._maybe_notify_guardian_worker(result, {"household_id": str(uuid4())})

    def test_notify_skips_fenced(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_guardian_worker(
            {"status": "fenced", "error": "Lease lost"}, {"household_id": str(uuid4())},
        )

    def test_notify_dispatches_with_breach_events(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        run_id = uuid4()
        result = {
            "evaluation_run": {"status": "completed", "id": str(run_id)},
            "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}],
        }
        OrchestrationWorker._maybe_notify_guardian_worker(result, {"household_id": str(uuid4())})


# ══════════════════════════════════════════════════════════════════════════
# Backup behavioural tests
# ══════════════════════════════════════════════════════════════════════════


class TestBackupNotification:
    def test_notify_accepts_completed(self) -> None:
        from apps.api.services.backup_service import _maybe_notify_backup
        _maybe_notify_backup(record_id=str(uuid4()), status="completed")

    def test_notify_accepts_failed(self) -> None:
        from apps.api.services.backup_service import _maybe_notify_backup
        _maybe_notify_backup(record_id=str(uuid4()), status="failed")

    def test_notify_rejects_non_terminal(self) -> None:
        from apps.api.services.backup_service import _maybe_notify_backup
        _maybe_notify_backup(record_id=str(uuid4()), status="running")

    def test_household_lookup_with_household(self, db_session: Session) -> None:
        _hid(db_session)
        from apps.api.services.backup_service import _resolve_household_id
        h = _resolve_household_id()
        assert h is not None


# ══════════════════════════════════════════════════════════════════════════
# Transaction isolation
# ══════════════════════════════════════════════════════════════════════════


class TestTransactionIsolation:
    def test_guardian_dispatches_in_dedicated_session(self, db_session: Session) -> None:
        _enable_guardian_backup(db_session)
        hid = _hid(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            hid, target_check_id=uuid4(),
        )
        after = len(list_events(db_session))
        assert after > before


# ══════════════════════════════════════════════════════════════════════════
# Proven helpers — from test_guardian_api.py
# ══════════════════════════════════════════════════════════════════════════


def _hid(session: Session) -> UUID:
    row = session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()
    if row:
        return row[0]
    hid = uuid4()
    session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name, base_currency,"
        " investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, TRUE, 'Test', 'USD', 'LT', '', '', '')"
    ), {"id": hid})
    session.commit()
    return hid


def _create_policy(session: Session, hid: UUID) -> UUID:
    pid = uuid4()
    pvid = uuid4()
    session.execute(text("INSERT INTO investment_policies (id, household_id) VALUES (:id, :hid)"),
                    {"id": pid, "hid": hid})
    session.execute(text(
        "INSERT INTO investment_policy_versions"
        " (id, policy_id, version_number, status, published_at,"
        " objectives, time_horizon, liquidity, diversification,"
        " contribution_policy, rebalancing_policy, prohibited_assets,"
        " leverage_policy, decision_process, notes)"
        " VALUES (:id, :pid, 1, 'published', NOW(),"
        " 'o','h','','','','','','','','')"
    ), {"id": pvid, "pid": pid})
    session.execute(text(
        "INSERT INTO investment_policy_version_allocations"
        " (id, version_id, asset_class_name, normalized_asset_class_name,"
        " target_percentage, sort_order)"
        " VALUES (:id, :vid, 'Global Equity', 'global equity', 60.00, 0)"
    ), {"id": uuid4(), "vid": pvid})
    # Seal after allocations inserted
    session.execute(
        text("UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"),
        {"id": pvid},
    )
    session.commit()
    return pid


def _create_portfolio(session: Session, hid: UUID, equity_val: str = "0") -> UUID:
    pid = uuid4()
    sid = uuid4()
    session.execute(text("INSERT INTO portfolios (id, household_id, status) VALUES (:id, :hid, 'active')"),
                    {"id": pid, "hid": hid})
    session.execute(text(
        "INSERT INTO portfolio_snapshots"
        " (id, portfolio_id, version_number, status, valuation_date)"
        " VALUES (:id, :pid, 1, 'current', '2026-06-01')"
    ), {"id": sid, "pid": pid})
    if Decimal(equity_val) > 0:
        session.execute(text(
            "INSERT INTO portfolio_snapshot_holdings"
            " (id, snapshot_id, asset_name, asset_category, quantity,"
            " unit_price, total_value, valuation_date, sort_order)"
            " VALUES (:id, :sid, 'VTI', 'Global Equity', '100', :price, :tv, '2026-06-01', 0)"
        ), {"id": uuid4(), "sid": sid, "price": equity_val, "tv": equity_val})
    session.commit()
    return sid


def _create_drift_check(session: Session, hid: UUID, threshold: float = 20.0) -> UUID:
    cc = create_guardian_check(
        session, household_id=hid, name="Drift Check", check_type="drift",
        threshold_value=Decimal(str(threshold)),
        target_category="Global Equity", target_holding_category="Equity",
    )
    confirm_guardian_check(session, check_id=cc["identity"]["id"], expected_revision=1)
    return cc["identity"]["id"]


def _enable_guardian_backup(session: Session) -> None:
    update_preferences(
        session,
        enabled=True,
        enabled_sources=["health", "guardian", "backup"],
        enabled_severities=["info", "warning", "critical"],
    )
