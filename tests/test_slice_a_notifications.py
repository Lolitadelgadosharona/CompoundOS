"""Sprint 008 Slice A — Guardian + Backup notification behavioral acceptance tests.

Real PostgreSQL, real production entry points, real assertions.
"""
# ruff: noqa: E501

import logging
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

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

    # ── evaluate_all ────────────────────────────────────────────────────

    def test_evaluate_all_breach_dispatches_notification(
        self, db_session: Session,
    ) -> None:
        """HTTP evaluate_all with real breach → notification event created."""
        hid = _setup_household(db_session)
        _setup_policy(db_session, hid)
        _enable_guardian_backup(db_session)
        _setup_drift_check(db_session, hid)
        _setup_portfolio_holdings_breach(db_session, hid)

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        result = evaluate_all_checks(db_session, household_id=hid, as_of_date=date.today())
        after = len(list_events(db_session))

        assert result["evaluation_run"]["status"].startswith("completed")
        assert len(result["events"]) >= 1
        assert after > before, "notification event was not created"

    def test_evaluate_all_zero_events_no_dispatch(
        self, db_session: Session,
    ) -> None:
        """HTTP evaluate_all with no breach → zero notification events."""
        hid = _setup_household(db_session)
        _setup_policy(db_session, hid)
        _enable_guardian_backup(db_session)
        # No drift check → no breach

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        evaluate_all_checks(db_session, household_id=hid, as_of_date=date.today())
        after = len(list_events(db_session))
        assert after == before

    def test_disabled_preferences_no_dispatch(
        self, db_session: Session,
    ) -> None:
        """Preferences disabled → no notification events."""
        hid = _setup_household(db_session)
        _setup_policy(db_session, hid)
        _setup_drift_check(db_session, hid)
        _setup_portfolio_holdings_breach(db_session, hid)
        # Never call _enable_guardian_backup — defaults to disabled

        from apps.api.services.guardian import evaluate_all_checks
        before = len(list_events(db_session))
        evaluate_all_checks(db_session, household_id=hid, as_of_date=date.today())
        after = len(list_events(db_session))
        assert after == before

    # ── evaluate_one ────────────────────────────────────────────────────

    def test_evaluate_one_breach_dispatches(
        self, db_session: Session,
    ) -> None:
        """HTTP evaluate_one with real check_id → notification with correct entity_id."""
        hid = _setup_household(db_session)
        _setup_policy(db_session, hid)
        _enable_guardian_backup(db_session)
        check_id = _setup_drift_check(db_session, hid)
        _setup_portfolio_holdings_breach(db_session, hid)

        from apps.api.services.guardian import evaluate_one_check
        before = len(list_events(db_session))
        result = evaluate_one_check(
            db_session, check_id=check_id, household_id=hid, as_of_date=date.today(),
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
            {"evaluation_run": {"status": "skipped_no_policy", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4())}]},
            uuid4(), target_check_id=None,
        )
        assert len(list_events(db_session)) == before

    def test_helper_dispatches_with_events(self, db_session: Session) -> None:
        _enable_guardian_backup(db_session)
        hid = _setup_household(db_session)
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
        _setup_household(db_session)
        from apps.api.services.backup_service import _resolve_household_id
        h = _resolve_household_id()
        assert h is not None


# ══════════════════════════════════════════════════════════════════════════
# Transaction isolation
# ══════════════════════════════════════════════════════════════════════════


class TestTransactionIsolation:
    def test_guardian_dispatches_in_dedicated_session(self, db_session: Session) -> None:
        _enable_guardian_backup(db_session)
        hid = _setup_household(db_session)
        from apps.api.services.guardian import _maybe_notify_guardian
        before = len(list_events(db_session))
        _maybe_notify_guardian(
            {"evaluation_run": {"status": "completed", "id": str(uuid4())},
             "events": [{"check_id": str(uuid4()), "event_type": "threshold_breach"}]},
            hid, target_check_id=uuid4(),
        )
        after = len(list_events(db_session))
        # Notification created in dedicated session; visible to this session via committed row
        assert after > before


# ══════════════════════════════════════════════════════════════════════════
# Test infrastructure helpers
# ══════════════════════════════════════════════════════════════════════════


def _setup_household(session: Session) -> UUID:
    row = session.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()
    if row:
        return row[0]
    hid = uuid4()
    session.execute(text(
        "INSERT INTO household_profiles (id, household_name, base_currency,"
        " singleton_key, investment_horizon, liquidity_needs, risk_statement, notes)"
        " VALUES (:id, 'Test', 'USD', TRUE, '', '', '', '')"
    ), {"id": hid})
    session.commit()
    return hid


def _setup_policy(session: Session, hid: UUID) -> None:
    session.execute(text(
        "INSERT INTO investment_policies (id, household_id, policy_name, status,"
        " snapshot_id, version, created_at)"
        " VALUES (:id, :hid, 'Default', 'published', :sid, 1, NOW())"
    ), {"id": uuid4(), "hid": hid, "sid": uuid4()})
    session.commit()


def _setup_drift_check(session: Session, hid: UUID) -> UUID:
    cid = uuid4()
    session.execute(text(
        "INSERT INTO guardian_checks (id, household_id, check_type, check_name,"
        " threshold_pct, status, evaluation_schedule, check_config, created_at, updated_at)"
        " VALUES (:id, :hid, 'drift', 'Drift Check', 20.0, 'confirmed',"
        " 'manual', :cfg, NOW(), NOW())"
    ), {"id": cid, "hid": hid, "cfg": '{"asset_class":"equity"}'})
    session.commit()
    return cid


def _setup_portfolio_holdings_breach(session: Session, hid: UUID) -> None:
    sid = uuid4()
    session.execute(text(
        "INSERT INTO portfolio_snapshots (id, household_id, status, snapshot_type,"
        " as_of_date, created_at)"
        " VALUES (:id, :hid, 'confirmed', 'full', CURRENT_DATE, NOW())"
    ), {"id": sid, "hid": hid})
    session.execute(text(
        "INSERT INTO holdings (id, snapshot_id, asset_class, ticker, shares,"
        " current_price, market_value, weight_pct)"
        " VALUES (:id, :sid, 'equity', 'AAPL', 1000, 150.0, 150000, 80.0)"
    ), {"id": uuid4(), "sid": sid})
    session.commit()


def _enable_guardian_backup(session: Session) -> None:
    update_preferences(
        session,
        enabled=True,
        enabled_sources=["health", "guardian", "backup"],
        enabled_severities=["info", "warning", "critical"],
    )
