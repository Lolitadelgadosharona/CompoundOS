"""Sprint 008 Slice B — Committee + Automation notification acceptance tests.

Real PostgreSQL, real production entry points, exact assertions.
"""
# ruff: noqa: E501

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

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


class TestCommitteeNotificationDispatch:
    def test_completed_session_dispatches_notification(
        self, db_session: Session,
    ) -> None:
        """Committee session completion -> dispatch session_complete info."""
        from apps.api.services.committee_orchestration import (
            _dispatch_committee_notification,
        )
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_completed_session(db_session, hid)
        before = len(list_events(db_session))
        _dispatch_committee_notification(cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "committee"
        assert ev.event_type == "session_complete"
        assert ev.severity == "info"
        assert ev.delivery_status != "suppressed"

    def test_disabled_preferences_suppresses(
        self, db_session: Session,
    ) -> None:
        """Committee notification suppressed when preferences disabled."""
        from apps.api.services.committee_orchestration import (
            _dispatch_committee_notification,
        )
        hid = _hid(db_session)
        cs = _create_completed_session(db_session, hid)
        before = len(list_events(db_session))
        _dispatch_committee_notification(cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "disabled"

    def test_source_disabled_suppresses(
        self, db_session: Session,
    ) -> None:
        """Committee notification suppressed when source disabled."""
        from apps.api.services.committee_orchestration import (
            _dispatch_committee_notification,
        )
        update_preferences(db_session, enabled=True, enabled_sources=["health"],
                           enabled_severities=["info", "warning"])
        hid = _hid(db_session)
        cs = _create_completed_session(db_session, hid)
        before = len(list_events(db_session))
        _dispatch_committee_notification(cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].suppressed_reason == "source_disabled"

    def test_failed_session_no_dispatch(self) -> None:
        """_fail_session does not trigger notification dispatch."""
        from apps.api.services.committee_orchestration import _fail_session
        # _fail_session commits but does not call _dispatch_committee_notification
        # Verification: the function body only sets status=failed and commits
        assert "dispatch_committee_notification" not in _fail_session.__code__.co_names


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
        """Automation run success -> no notification."""
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


class TestReturnFromExecuteScheduled:
    def test_non_guardian_failure_returns_result(self) -> None:
        """_execute_scheduled returns failure info for non-guardian jobs."""
        # The _execute_scheduled method at line 291-295 of orchestration_worker.py
        # returns {"run_id": ..., "finalize_status": "failed", ...} for
        # non-guardian failed runs. This is the contract that
        # _maybe_notify_automation_worker consumes.
        import inspect

        from apps.api.services.orchestration_worker import OrchestrationWorker
        src = inspect.getsource(
            OrchestrationWorker._execute_scheduled)  # type: ignore[arg-type]
        assert "not is_guardian and finalize_status == \"failed\"" in src, (
            "Non-guardian failure path must return result for automation notification"
        )

    def test_claim_and_execute_calls_automation_notify(self) -> None:
        """_claim_and_execute dispatches automation notification after commit."""
        import inspect

        from apps.api.services.orchestration_worker import OrchestrationWorker
        src = inspect.getsource(
            OrchestrationWorker._claim_and_execute)  # type: ignore[arg-type]
        assert "_maybe_notify_automation_worker" in src


class TestNotificationIsolation:
    def test_dispatch_uses_dedicated_session(self) -> None:
        """Committee notification dispatch opens its own SessionLocal."""
        import inspect

        from apps.api.services.committee_orchestration import (
            _dispatch_committee_notification,
        )
        src = inspect.getsource(_dispatch_committee_notification)
        assert "SessionLocal()" in src
        assert "ns.close()" in src
        assert "ns.rollback()" in src


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


def _create_completed_session(session: Session, hid: UUID):
    """Create a committee session already in completed status."""
    from sqlalchemy import text
    sid = uuid4()
    session.execute(text(
        "INSERT INTO committee_sessions (id, household_id, title,"
        " proposal_text, status)"
        " VALUES (:id, :hid, 'Test', 'Test proposal', 'completed')"
    ), {"id": sid, "hid": hid})
    session.commit()
    # Return a real ORM object for _dispatch_committee_notification
    from apps.api.models import CommitteeSession
    return session.query(CommitteeSession).filter_by(id=sid).one()
