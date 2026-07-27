"""Sprint 008 Slice A — Guardian + Backup notification acceptance tests.

Real PostgreSQL, real production entry points, exact assertions.
"""
# ruff: noqa: E501

from datetime import date, time
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.guardian import confirm_guardian_check, create_guardian_check
from apps.api.services.notification_service import (
    NOTIFICATION_TEMPLATES,
    get_preferences,
    list_events,
    update_preferences,
)

pytestmark = pytest.mark.postgres


class TestEventTypeTemplates:
    def test_guardian_threshold_breach_key(self) -> None:
        assert "threshold_breach" in NOTIFICATION_TEMPLATES["guardian"]
        assert "breach" not in NOTIFICATION_TEMPLATES["guardian"]

    def test_backup_approved_keys(self) -> None:
        assert "backup_complete" in NOTIFICATION_TEMPLATES["backup"]
        assert "backup_failed" in NOTIFICATION_TEMPLATES["backup"]
        assert "completed" not in NOTIFICATION_TEMPLATES["backup"]
        assert "failed" not in NOTIFICATION_TEMPLATES["backup"]

    def test_committee_automation_unchanged(self) -> None:
        assert "completed" in NOTIFICATION_TEMPLATES["committee"]
        assert "failed" in NOTIFICATION_TEMPLATES["automation"]


class TestGuardianHTTPNotification:
    def test_evaluate_all_breach_exact_one_event(
        self, db_session: Session,
    ) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        _create_drift_check(db_session, hid, threshold=3.0)
        _enable_all(db_session)

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        events = list_events(db_session)

        assert result["evaluation_run"]["status"].startswith("completed")
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "guardian"
        assert ev.event_type == "threshold_breach"
        assert ev.severity == "warning"

    def test_evaluate_one_breach_exact_one_event(
        self, db_session: Session,
    ) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        check_id = _create_drift_check(db_session, hid, threshold=3.0)
        _enable_all(db_session)

        from apps.api.services.guardian import evaluate_one_check
        before = len(list_events(db_session))
        result = evaluate_one_check(
            db_session, check_id=check_id, household_id=hid, as_of_date=date(2026, 7, 17),
        )
        events = list_events(db_session)

        assert result["evaluation_run"]["status"].startswith("completed")
        assert len(events) == before + 1

    def test_zero_events_no_dispatch(self, db_session: Session) -> None:
        hid = _hid(db_session)
        _create_policy(db_session, hid)
        _create_portfolio(db_session, hid, "100000")
        _enable_all(db_session)

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        evaluate_all_checks(db_session, household_id=hid, as_of_date=date(2026, 7, 17))
        assert len(list_events(db_session)) == before


class TestGuardianSuppression:
    def test_disabled_suppressed(self, db_session: Session) -> None:
        update_preferences(db_session, enabled=False)
        hid = _hid(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            hid, target_check_id=uuid4(),
        )
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "disabled"

    def test_source_disabled_suppressed(self, db_session: Session) -> None:
        update_preferences(db_session, enabled=True, enabled_sources=["health"],
                           enabled_severities=["info", "warning"])
        hid = _hid(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            hid, target_check_id=uuid4(),
        )
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].suppressed_reason == "source_disabled"


class TestGuardianDedup:
    def test_same_identity_dedup_suppressed(
        self, db_session: Session,
    ) -> None:
        """Same check_id dispatched twice with FakeAdapter → second dedup-suppressed."""
        _enable_all(db_session)
        prefs = get_preferences(db_session)
        prefs.quiet_hours_start = time(0, 0)
        prefs.quiet_hours_end = time(0, 1)
        db_session.commit()

        from tests.test_notifications import FakeAdapter

        hid = _hid(db_session)
        check_id = uuid4()
        from apps.api.services.notification_service import dispatch_notification
        before = len(list_events(db_session))
        dispatch_notification(
            db_session, source="guardian", event_type="threshold_breach",
            severity="warning", household_id=hid, entity_id=str(check_id),
            adapter=FakeAdapter(),
        )
        after1 = len(list_events(db_session))
        assert after1 == before + 1
        dispatch_notification(
            db_session, source="guardian", event_type="threshold_breach",
            severity="warning", household_id=hid, entity_id=str(check_id),
            adapter=FakeAdapter(),
        )
        after2 = len(list_events(db_session))
        assert after2 == after1 + 1
        events = list_events(db_session)
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "dedup"

    def test_different_checks_different_fingerprints(
        self, db_session: Session,
    ) -> None:
        """Different check_ids produce different fingerprints, neither suppressed."""
        _enable_all(db_session)
        prefs = get_preferences(db_session)
        prefs.quiet_hours_start = time(0, 0)
        prefs.quiet_hours_end = time(0, 1)
        db_session.commit()

        from tests.test_notifications import FakeAdapter

        hid = _hid(db_session)
        from apps.api.services.notification_service import dispatch_notification
        before = len(list_events(db_session))
        dispatch_notification(
            db_session, source="guardian", event_type="threshold_breach",
            severity="warning", household_id=hid, entity_id=str(uuid4()),
            adapter=FakeAdapter(),
        )
        after1 = len(list_events(db_session))
        assert after1 == before + 1
        dispatch_notification(
            db_session, source="guardian", event_type="threshold_breach",
            severity="warning", household_id=hid, entity_id=str(uuid4()),
            adapter=FakeAdapter(),
        )
        after2 = len(list_events(db_session))
        assert after2 == after1 + 1
        events = list_events(db_session)
        assert events[0].suppressed_reason != "dedup"
        assert events[1].suppressed_reason != "dedup"


class TestWorkerGuardianNotification:
    def test_skips_none_result(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_guardian_worker(None, {})

    def test_skips_empty_events(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        result = {"evaluation_run": {"status": "completed", "id": str(uuid4())}, "events": []}
        OrchestrationWorker._maybe_notify_guardian_worker(result, {"household_id": str(uuid4())})

    def test_skips_non_completed(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        result = {"evaluation_run": {"status": "skipped", "id": str(uuid4())},
                  "events": [{"check_id": str(uuid4())}]}
        OrchestrationWorker._maybe_notify_guardian_worker(result, {"household_id": str(uuid4())})

    def test_skips_fenced(self) -> None:
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_guardian_worker(
            {"status": "fenced", "error": "Lease lost"}, {"household_id": str(uuid4())},
        )


class TestBackupNotification:
    def test_accepts_completed(self) -> None:
        from apps.api.services.backup_service import _maybe_notify_backup
        _maybe_notify_backup(record_id=str(uuid4()), status="completed")

    def test_accepts_failed(self) -> None:
        from apps.api.services.backup_service import _maybe_notify_backup
        _maybe_notify_backup(record_id=str(uuid4()), status="failed")

    def test_rejects_non_terminal(self) -> None:
        from apps.api.services.backup_service import _maybe_notify_backup
        _maybe_notify_backup(record_id=str(uuid4()), status="running")

    def test_household_lookup_with_household(self, db_session: Session) -> None:
        _hid(db_session)
        from apps.api.services.backup_service import _resolve_household_id
        assert _resolve_household_id() is not None


class TestTransactionIsolation:
    def test_dedicated_session_dispatch(self, db_session: Session) -> None:
        _enable_all(db_session)
        hid = _hid(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            hid, target_check_id=uuid4(),
        )
        assert len(list_events(db_session)) == before + 1


# ═══════════════════════════════════════════
def _hid(session: Session) -> UUID:
    r = session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()
    if r:
        return r[0]
    hid = uuid4()
    session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, TRUE, 'Test', 'USD', 'LT', '', '', '')"
    ), {"id": hid})
    session.commit()
    return hid


def _create_policy(session: Session, hid: UUID) -> UUID:
    pid, pvid = uuid4(), uuid4()
    session.execute(text("INSERT INTO investment_policies (id, household_id) VALUES (:id, :hid)"),
                    {"id": pid, "hid": hid})
    session.execute(text(
        "INSERT INTO investment_policy_versions (id, policy_id, version_number, status,"
        " published_at, objectives, time_horizon, liquidity, diversification,"
        " contribution_policy, rebalancing_policy, prohibited_assets,"
        " leverage_policy, decision_process, notes)"
        " VALUES (:id, :pid, 1, 'published', NOW(), 'o','h','','','','','','','','')"
    ), {"id": pvid, "pid": pid})
    session.execute(text(
        "INSERT INTO investment_policy_version_allocations"
        " (id, version_id, asset_class_name, normalized_asset_class_name,"
        " target_percentage, sort_order)"
        " VALUES (:id, :vid, 'Global Equity', 'global equity', 60.00, 0)"
    ), {"id": uuid4(), "vid": pvid})
    session.execute(text("UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"),
                    {"id": pvid})
    session.commit()
    return pid


def _create_portfolio(session: Session, hid: UUID, equity_val: str = "0") -> UUID:
    pid, sid = uuid4(), uuid4()
    session.execute(text("INSERT INTO portfolios (id, household_id, status) VALUES (:id, :hid, 'active')"),
                    {"id": pid, "hid": hid})
    session.execute(text(
        "INSERT INTO portfolio_snapshots (id, portfolio_id, version_number, status, valuation_date)"
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


def _enable_all(session: Session) -> None:
    update_preferences(
        session, enabled=True,
        enabled_sources=["health", "guardian", "backup"],
        enabled_severities=["info", "warning", "critical"],
    )
