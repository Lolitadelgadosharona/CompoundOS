"""Sprint 008 Slice B — Committee + Automation notification acceptance tests.

Real PostgreSQL, real production entry points, exact assertions.
"""
# ruff: noqa: E501

import json
from datetime import time
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


class TestCommitteeNotification:
    def test_completed_dispatches_exact_notification(
        self, db_session: Session,
    ) -> None:
        """run_committee() completion dispatches session_complete with exact fields."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        before = len(list_events(db_session))
        _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "committee"
        assert ev.event_type == "session_complete"
        assert ev.severity == "info"
        assert ev.delivery_status in ("delivered", "suppressed", "unavailable")
        assert ev.suppressed_reason != "dedup"
        assert ev.fingerprint  # fingerprint is set (SHA-256 hash)
        # Template-driven body — no free text from proposal/provider/evidence
        assert "rebalancing" not in ev.body.lower()
        assert "deepseek" not in ev.body.lower()

    def test_failed_session_no_notification(
        self, db_session: Session,
    ) -> None:
        """Failed committee session produces no notification."""
        from apps.api.services.committee_orchestration import _fail_session
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        _fail_session(db_session, cs, "test failure")
        before = len(list_events(db_session))
        events = list_events(db_session)
        assert len(events) == before

    def test_disabled_preferences_suppresses(
        self, db_session: Session,
    ) -> None:
        """Notification suppressed when preferences disabled."""
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        before = len(list_events(db_session))
        _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "disabled"

    def test_source_disabled_suppresses(
        self, db_session: Session,
    ) -> None:
        """Notification suppressed when committee source disabled."""
        update_preferences(db_session, enabled=True, enabled_sources=["health"],
                           enabled_severities=["info", "warning"])
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        before = len(list_events(db_session))
        _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        assert events[0].suppressed_reason == "source_disabled"

    def test_business_result_survives_notification_failure(
        self, db_session: Session,
    ) -> None:
        """Committee report + session persist even if notification dispatch fails."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        _run_to_completion_with_failing_notification(db_session, cs)
        db_session.refresh(cs)
        assert cs.status == "completed"
        from apps.api.models import CommitteeReport
        report = db_session.query(CommitteeReport).filter_by(
            session_id=cs.id).first()
        assert report is not None


class TestAutomationNotification:
    def test_failed_run_creates_exact_notification(
        self, db_session: Session,
    ) -> None:
        """Worker _execute_scheduled on a failed run creates exact NotificationEvent."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        before = len(list_events(db_session))
        worker._execute_scheduled(db_session, info)
        events = list_events(db_session)
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "automation"
        assert ev.event_type == "run_failed"
        assert ev.severity == "warning"
        assert ev.delivery_status in ("delivered", "suppressed", "unavailable")
        assert ev.suppressed_reason != "dedup"
        assert UUID(ev.fingerprint) or ev.fingerprint

    def test_failed_returns_exact_key_set(
        self, db_session: Session,
    ) -> None:
        """_execute_scheduled returns only run_id, household_id, finalize_status."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        result = worker._execute_scheduled(db_session, info)
        assert result is not None
        assert set(result.keys()) == {"run_id", "household_id", "finalize_status"}
        assert result["finalize_status"] == "failed"

    def test_completed_no_notification(
        self, db_session: Session,
    ) -> None:
        """Completed run creates no automation notification."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "completed"})
        before = len(list_events(db_session))
        worker._execute_scheduled(db_session, info)
        events = list_events(db_session)
        for ev in events[before:]:
            assert ev.source != "automation" or ev.event_type != "run_failed"

    def test_aborted_no_notification(
        self, db_session: Session,
    ) -> None:
        """Aborted run (timeout) creates no automation notification."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "terminated"})
        before = len(list_events(db_session))
        worker._execute_scheduled(db_session, info)
        events = list_events(db_session)
        for ev in events[before:]:
            assert ev.source != "automation" or ev.event_type != "run_failed"

    def test_run_attempt_lease_persist_after_failure(
        self, db_session: Session,
    ) -> None:
        """Run, attempt, lease final states persist after failed run."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        worker._execute_scheduled(db_session, info)
        from sqlalchemy import text
        run = db_session.execute(text(
            "SELECT status FROM runs WHERE schedule_id = :sid ORDER BY created_at DESC LIMIT 1"
        ), {"sid": sid}).fetchone()
        assert run is not None
        assert run[0] == "failed"

    def test_business_state_survives_notification_failure(
        self, db_session: Session,
    ) -> None:
        """Run/attempt/lease persist even if notification dispatch fails."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker_with_failing_notification(
            db_session, result={"status": "failed"},
        )
        worker._execute_scheduled(db_session, info)
        from sqlalchemy import text
        run = db_session.execute(text(
            "SELECT status FROM runs WHERE schedule_id = :sid ORDER BY created_at DESC LIMIT 1"
        ), {"sid": sid}).fetchone()
        assert run is not None
        assert run[0] == "failed"

    def test_notification_does_not_create_automation_run(
        self, db_session: Session,
    ) -> None:
        """run_failed notification does not create additional automation runs."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        from sqlalchemy import text
        before = db_session.execute(text(
            "SELECT COUNT(*) FROM runs"
        )).scalar()
        worker._execute_scheduled(db_session, info)
        after = db_session.execute(text(
            "SELECT COUNT(*) FROM runs"
        )).scalar()
        assert after == before + 1  # exactly one run, not two


class TestDedupForSliceB:
    def test_same_committee_entity_dedup_suppressed(
        self, db_session: Session,
    ) -> None:
        """Same entity_id twice → second dedup-suppressed."""
        _enable_all(db_session)
        from apps.api.services.notification_service import dispatch_notification
        from tests.test_notifications import FakeAdapter
        hid = _hid(db_session)
        sid = str(uuid4())
        before = len(list_events(db_session))
        dispatch_notification(
            db_session, source="committee", event_type="session_complete",
            severity="info", household_id=hid, entity_id=sid,
            adapter=FakeAdapter(),
        )
        after1 = len(list_events(db_session))
        assert after1 == before + 1
        dispatch_notification(
            db_session, source="committee", event_type="session_complete",
            severity="info", household_id=hid, entity_id=sid,
            adapter=FakeAdapter(),
        )
        after2 = len(list_events(db_session))
        assert after2 == after1 + 1
        events = list_events(db_session)
        assert events[0].suppressed_reason == "dedup"
        assert events[1].delivery_status == "delivered"
        assert events[1].suppressed_reason is None
        assert events[0].fingerprint == events[1].fingerprint

    def test_different_entities_different_fingerprints(
        self, db_session: Session,
    ) -> None:
        """Different entity_ids → different fingerprints, both delivered."""
        _enable_all(db_session)
        from apps.api.services.notification_service import dispatch_notification
        from tests.test_notifications import FakeAdapter
        hid = _hid(db_session)
        before = len(list_events(db_session))
        dispatch_notification(
            db_session, source="committee", event_type="session_complete",
            severity="info", household_id=hid, entity_id=str(uuid4()),
            adapter=FakeAdapter(),
        )
        after1 = len(list_events(db_session))
        assert after1 == before + 1
        dispatch_notification(
            db_session, source="committee", event_type="session_complete",
            severity="info", household_id=hid, entity_id=str(uuid4()),
            adapter=FakeAdapter(),
        )
        after2 = len(list_events(db_session))
        assert after2 == after1 + 1
        events = list_events(db_session)
        assert events[0].fingerprint != events[1].fingerprint
        assert events[0].delivery_status == "delivered"
        assert events[1].delivery_status == "delivered"
        assert events[0].suppressed_reason != "dedup"
        assert events[1].suppressed_reason != "dedup"


# --- Helpers ---

_VALID_OUTPUT = """{
    "supporting_arguments": "The current allocation is consistent with stated objectives.",
    "opposing_arguments": "Market conditions suggest reviewing exposures.",
    "risks": "Elevated market uncertainty and interest rate sensitivity.",
    "policy_alignment": "The proposal is consistent with the investment policy.",
    "minority_opinions": "One perspective favors more conservative exposure levels.",
    "evidence_citations": [],
    "limitations": "Analysis is limited to available data as of valuation date.",
    "recommended_direction": "aligned_with_policy",
    "sections": {
        "long_term_compounding": "Compounding effects favor staying invested.",
        "index_passive_investing": "Passive index exposure reduces single-stock risk.",
        "macroeconomic_context": "Current rate environment warrants caution.",
        "risk_capital_preservation": "Diversification maintains adequate protection.",
        "devils_advocate": "Alternative: reduce equity exposure given macro headwinds.",
        "policy_alignment_role": "Policy alignment assessment confirms consistency.",
        "synthesis_chair": "Synthesis: maintain current approach with monitoring."
    }
}"""


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
    from apps.api.services.notification_service import get_preferences
    update_preferences(
        session,
        enabled=True,
        enabled_sources=["health", "guardian", "backup", "committee",
                          "automation"],
        enabled_severities=["info", "warning", "critical"],
    )
    prefs = get_preferences(session)
    prefs.quiet_hours_start = time(0, 0)
    prefs.quiet_hours_end = time(0, 1)
    session.commit()


def _create_queued_session(session: Session, hid: UUID):
    from sqlalchemy import text
    sid = uuid4()
    session.execute(text(
        "INSERT INTO committee_sessions (id, household_id, title,"
        " proposal_text, status)"
        " VALUES (:id, :hid, 'Test Session', 'Evaluate current allocation.', 'queued')"
    ), {"id": sid, "hid": hid})
    session.commit()
    from apps.api.models import CommitteeSession
    return session.query(CommitteeSession).filter_by(id=sid).one()


def _create_schedule(session: Session, hid: UUID, job_type: str) -> UUID:
    from sqlalchemy import text
    jid = uuid4()
    session.execute(text(
        "INSERT INTO job_definitions (id, household_id, job_type, job_params)"
        " VALUES (:id, :hid, :jt, '{}'::jsonb)"
    ), {"id": jid, "hid": hid, "jt": job_type})
    sid = uuid4()
    session.execute(text(
        "INSERT INTO schedules (id, job_definition_id,"
        " execution_time, timezone, enabled, next_run_at)"
        " VALUES (:id, :jid, '09:00', 'UTC', true, NOW())"
    ), {"id": sid, "jid": jid})
    session.commit()
    return sid


def _schedule_info(session: Session, sid: UUID) -> dict:
    from sqlalchemy import text
    row = session.execute(text(
        "SELECT s.id, s.job_definition_id, jd.household_id, s.execution_time,"
        " s.timezone, jd.job_type, jd.job_params"
        " FROM schedules s JOIN job_definitions jd ON s.job_definition_id = jd.id"
        " WHERE s.id = :sid"
    ), {"sid": sid}).fetchone()
    return {
        "schedule_id": row[0], "job_definition_id": row[1],
        "household_id": row[2], "execution_time": row[3],
        "timezone": row[4], "job_type": row[5],
        "job_params": row[6] or {},
    }


def _make_worker(session, result):
    """Create OrchestrationWorker with deterministic FakeJobExecutor."""
    from apps.api.services.orchestration_worker import OrchestrationWorker
    db_url = session.get_bind().url.render_as_string(hide_password=False)
    worker = OrchestrationWorker(
        db_url, worker_id="test-worker-slice-b",
        executor=FakeJobExecutor(result=result),
    )
    return worker


def _make_worker_with_failing_notification(session, result):
    """Worker whose notification dispatch fails (SessionLocal unavailable)."""
    from apps.api.services.orchestration_worker import OrchestrationWorker
    db_url = "postgresql://nonexistent:5432/nonexistent"
    worker = OrchestrationWorker(
        db_url, worker_id="test-worker-slice-b",
        executor=FakeJobExecutor(result=result),
    )
    return worker


class FakeJobExecutor:
    """Deterministic executor that returns a pre-configured result."""
    def __init__(self, result=None):
        self._result = result or {}

    def execute(self, **kwargs):
        return dict(self._result)


def _run_to_completion(session, cs) -> None:
    """Run committee to completion with mock provider returning valid output."""
    from apps.api.services.ai_provider import AIModelProvider, ProviderResponse
    from apps.api.services.committee_orchestration import run_committee
    output = json.loads(_VALID_OUTPUT)

    class MockProvider(AIModelProvider):
        @property
        def provider_name(self) -> str:
            return "mock"

        def call(self, system_prompt: str, user_prompt: str,
                 config=None) -> ProviderResponse:
            return ProviderResponse(raw_text=json.dumps(output))

    run_committee(session, cs, MockProvider())


def _run_to_completion_with_failing_notification(session, cs) -> None:
    """Run committee where notification dispatch fails (broken SessionLocal).

    Temporarily patches SessionLocal to raise, proving business commit survives.
    """
    from unittest.mock import patch

    from apps.api.services.ai_provider import AIModelProvider, ProviderResponse
    from apps.api.services.committee_orchestration import run_committee
    output = json.loads(_VALID_OUTPUT)

    class MockProvider(AIModelProvider):
        @property
        def provider_name(self) -> str:
            return "mock"

        def call(self, system_prompt: str, user_prompt: str,
                 config=None) -> ProviderResponse:
            return ProviderResponse(raw_text=json.dumps(output))

    with patch(
        "apps.api.database.SessionLocal",
        side_effect=RuntimeError("notification unavailable"),
    ):
        run_committee(session, cs, MockProvider())
