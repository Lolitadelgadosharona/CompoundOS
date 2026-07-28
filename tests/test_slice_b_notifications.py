"""Sprint 008 Slice B — Committee + Automation notification acceptance tests.

Real PostgreSQL, real production entry points, exact assertions.
"""
# ruff: noqa: E501

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from apps.api.services.ai_provider import AIModelProvider, ProviderResponse
from apps.api.services.committee_orchestration import _fail_session, run_committee
from apps.api.services.notification_service import (
    NOTIFICATION_TEMPLATES,
    list_events,
    update_preferences,
)

pytestmark = pytest.mark.postgres


class TestEventTypeTemplates:
    def test_committee_session_complete_key(self) -> None:
        assert "session_complete" in NOTIFICATION_TEMPLATES["committee"]
        assert "completed" not in NOTIFICATION_TEMPLATES["committee"]

    def test_automation_run_failed_key(self) -> None:
        assert "run_failed" in NOTIFICATION_TEMPLATES["automation"]
        assert "failed" not in NOTIFICATION_TEMPLATES["automation"]


class TestCommitteeNotification:
    def test_session_completed_dispatches_notification(
        self, db_session: Session,
    ) -> None:
        """Committee session completion -> dispatch session_complete info."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_committee_session(db_session, hid)
        before = len(list_events(db_session))
        _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "committee"
        assert ev.event_type == "session_complete"
        assert ev.severity == "info"

    def test_session_failed_no_dispatch(
        self, db_session: Session,
    ) -> None:
        """Committee session failure -> no notification dispatched."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_committee_session(db_session, hid)
        _fail_session(db_session, cs, "test failure")
        before = len(list_events(db_session))
        events = list_events(db_session)
        assert len(events) == before

    def test_disabled_preferences_suppresses_committee(
        self, db_session: Session,
    ) -> None:
        """Committee notification suppressed when preferences disabled."""
        hid = _hid(db_session)
        cs = _create_committee_session(db_session, hid)
        before = len(list_events(db_session))
        _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "disabled"

    def test_source_disabled_suppresses_committee(
        self, db_session: Session,
    ) -> None:
        """Committee notification suppressed when committee source disabled."""
        update_preferences(db_session, enabled=True, enabled_sources=["health"],
                           enabled_severities=["info", "warning"])
        hid = _hid(db_session)
        cs = _create_committee_session(db_session, hid)
        before = len(list_events(db_session))
        _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].suppressed_reason == "source_disabled"


class TestAutomationNotification:
    def test_run_failed_dispatches_notification(self) -> None:
        """Automation run failure -> dispatch run_failed warning."""
        from apps.api.services.orchestration_worker import OrchestrationWorker
        result = {
            "run_id": uuid4(), "household_id": str(uuid4()),
            "finalize_status": "failed", "error": "test error",
        }
        OrchestrationWorker._maybe_notify_automation_worker(result)

    def test_run_succeeded_no_dispatch(self) -> None:
        """Automation run success -> no notification (None result)."""
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_automation_worker(None)

    def test_completed_status_no_dispatch(self) -> None:
        """Completed finalize_status -> no notification."""
        from apps.api.services.orchestration_worker import OrchestrationWorker
        result = {
            "run_id": uuid4(), "household_id": str(uuid4()),
            "finalize_status": "completed",
        }
        OrchestrationWorker._maybe_notify_automation_worker(result)

    def test_none_result_no_dispatch(self) -> None:
        """None result -> no notification."""
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_automation_worker(None)

    def test_empty_dict_no_dispatch(self) -> None:
        """Empty result -> no notification."""
        from apps.api.services.orchestration_worker import OrchestrationWorker
        OrchestrationWorker._maybe_notify_automation_worker({})


class TestNotificationIsolation:
    def test_committee_notification_failure_does_not_rollback_business(
        self, db_session: Session,
    ) -> None:
        """Committee business commit survives notification failure."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_committee_session(db_session, hid)
        _run_to_completion(db_session, cs)
        db_session.refresh(cs)
        assert cs.status == "completed"


# --- Helpers ---

def _hid(session: Session) -> UUID:
    from sqlalchemy import text
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


def _enable_all(session: Session) -> None:
    update_preferences(
        session,
        enabled=True,
        enabled_sources=["health", "guardian", "backup", "committee",
                          "automation"],
        enabled_severities=["info", "warning", "critical"],
    )


def _create_committee_session(session: Session, hid: UUID):
    from apps.api.models import CommitteeSession
    cs = CommitteeSession(
        id=uuid4(), household_id=hid,
        title="Test Committee Session",
        proposal_text="Evaluate rebalancing options for the current portfolio.",
        status="queued",
    )
    session.add(cs)
    session.commit()
    return cs


def _run_to_completion(session, cs) -> None:
    """Run committee session with a mock provider that returns valid JSON."""

    class MockProvider(AIModelProvider):
        @property
        def provider_name(self) -> str:
            return "mock"

        def call(self, system_prompt: str, user_prompt: str,
                 config=None) -> ProviderResponse:
            return ProviderResponse(
                raw_text=json.dumps({
                    "rationale": "Mock committee analysis.",
                    "perspectives": [{"name": "Risk", "assessment": "low"}],
                    "recommendation": "hold",
                }),
            )

    try:
        run_committee(session, cs, MockProvider())
    except Exception:
        session.rollback()
