"""Sprint 008 Slice B — Committee + Automation notification acceptance tests.

Real PostgreSQL, real production entry points, exact assertions.
"""
# ruff: noqa: E501

import json
from datetime import datetime, time, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from apps.api.services.notification_service import (
    NOTIFICATION_TEMPLATES,
    compute_fingerprint,
    list_events,
    update_preferences,
)

pytestmark = pytest.mark.postgres

# Fixed timestamp for deterministic dedup and delivery tests
_FIXED_NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)

# Sentinels injected into proposal/provider/error — must NOT appear in notification body
_SECRET_PROPOSAL = "SECRET_PROPOSAL_xyz_001"
_SECRET_PROVIDER = "SECRET_PROVIDER_abc_002"
_SECRET_ERROR = "SECRET_ERROR_def_003"


def _patch_dispatch_for_deterministic_delivery():
    """Context manager: wrap dispatch_notification with FakeAdapter + fixed now."""
    from apps.api.services import notification_service as ns_mod
    from tests.test_notifications import FakeAdapter

    original = ns_mod.dispatch_notification

    def wrapped(*args, **kwargs):
        kwargs.setdefault("adapter", FakeAdapter())
        kwargs.setdefault("now", _FIXED_NOW)
        return original(*args, **kwargs)

    return patch.object(ns_mod, "dispatch_notification", wrapped)


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
        """run_committee() dispatches session_complete with deterministic delivery."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        before = len(list_events(db_session))
        with _patch_dispatch_for_deterministic_delivery():
            _run_to_completion(db_session, cs)
        events = list_events(db_session)
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "committee"
        assert ev.event_type == "session_complete"
        assert ev.severity == "info"
        # Deterministic: FakeAdapter always delivers
        assert ev.delivery_status == "delivered"
        assert ev.suppressed_reason is None
        # Fingerprint bound to session_id
        expected_fp = compute_fingerprint(
            "committee", "session_complete", "info", hid, str(cs.id),
        )
        assert ev.fingerprint == expected_fp
        # Template title/body
        assert ev.title == "Committee Session Complete"
        assert ev.body == "AI Committee session finished. Review the Committee workspace."
        # Sentinels must NOT leak into notification
        assert _SECRET_PROPOSAL.lower() not in ev.title.lower()
        assert _SECRET_PROPOSAL.lower() not in ev.body.lower()
        assert _SECRET_PROVIDER.lower() not in ev.title.lower()
        assert _SECRET_PROVIDER.lower() not in ev.body.lower()

    def test_failed_session_no_notification(
        self, db_session: Session,
    ) -> None:
        """Failed committee session: event count unchanged."""
        from apps.api.services.committee_orchestration import _fail_session
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        before = len(list_events(db_session))
        _fail_session(db_session, cs, "test failure")
        assert len(list_events(db_session)) == before

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
        """Committee report + session persist when SessionLocal raises."""
        _enable_all(db_session)
        hid = _hid(db_session)
        cs = _create_queued_session(db_session, hid)
        with patch(
            "apps.api.database.SessionLocal",
            side_effect=RuntimeError("notification unavailable"),
        ):
            _run_to_completion(db_session, cs)
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
        """Worker failed run dispatches run_failed with deterministic delivery."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={
            "status": "failed", "error": _SECRET_ERROR,
        })
        before = len(list_events(db_session))
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        with _patch_dispatch_for_deterministic_delivery():
            worker._maybe_notify_automation_worker(result)
        events = list_events(db_session)
        assert len(events) == before + 1
        ev = events[0]
        assert ev.source == "automation"
        assert ev.event_type == "run_failed"
        assert ev.severity == "warning"
        assert ev.delivery_status == "delivered"
        assert ev.suppressed_reason is None
        # Fingerprint bound to actual persisted run_id
        run_id = result["run_id"]
        expected_fp = compute_fingerprint(
            "automation", "run_failed", "warning", hid, run_id,
        )
        assert ev.fingerprint == expected_fp
        assert ev.title == "Automation Run Failed"
        assert ev.body == "An automation run has failed. Review automation logs."
        # Executor error sentinel must NOT leak
        assert _SECRET_ERROR.lower() not in ev.title.lower()
        assert _SECRET_ERROR.lower() not in ev.body.lower()

    def test_failed_returns_exact_key_set(
        self, db_session: Session,
    ) -> None:
        """_execute_scheduled returns {run_id, household_id, finalize_status}."""
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
        """Completed run: event count unchanged."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "completed"})
        before = len(list_events(db_session))
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        assert result is None
        worker._maybe_notify_automation_worker(result)
        assert len(list_events(db_session)) == before

    def test_aborted_no_notification(
        self, db_session: Session,
    ) -> None:
        """Aborted run: event count unchanged."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "terminated"})
        before = len(list_events(db_session))
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        assert result is None
        worker._maybe_notify_automation_worker(result)
        assert len(list_events(db_session)) == before

    def test_run_attempt_lease_persist_after_failure(
        self, db_session: Session,
    ) -> None:
        """Run, attempt, lease all reach terminal state after failed run."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        worker._maybe_notify_automation_worker(result)
        from sqlalchemy import text
        run_id = UUID(result["run_id"])
        run = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": run_id}).fetchone()
        assert run is not None and run[0] == "failed"
        attempt = db_session.execute(text(
            "SELECT status, attempt_number FROM attempts WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert attempt is not None
        assert attempt[0] == "failed"
        assert attempt[1] >= 1
        lease = db_session.execute(text(
            "SELECT released_at FROM leases WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert lease is not None and lease[0] is not None

    def test_business_state_survives_notification_failure(
        self, db_session: Session,
    ) -> None:
        """Run/attempt/lease persist even when SessionLocal raises."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        with patch(
            "apps.api.database.SessionLocal",
            side_effect=RuntimeError("notification unavailable"),
        ):
            worker._maybe_notify_automation_worker(result)
        from sqlalchemy import text
        run_id = UUID(result["run_id"])
        run = db_session.execute(text(
            "SELECT status FROM runs WHERE id = :rid"
        ), {"rid": run_id}).fetchone()
        assert run is not None and run[0] == "failed"
        attempt = db_session.execute(text(
            "SELECT status FROM attempts WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert attempt is not None and attempt[0] == "failed"
        lease = db_session.execute(text(
            "SELECT released_at FROM leases WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert lease is not None and lease[0] is not None

    def test_notification_does_not_create_automation_run(
        self, db_session: Session,
    ) -> None:
        """run_failed notification does not create additional runs."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        from sqlalchemy import text
        before = db_session.execute(text(
            "SELECT COUNT(*) FROM runs"
        )).scalar()
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        worker._maybe_notify_automation_worker(result)
        after = db_session.execute(text(
            "SELECT COUNT(*) FROM runs"
        )).scalar()
        assert after == before + 1

    def test_stale_token_fenced_no_notification(
        self, db_session: Session,
    ) -> None:
        """Stale token via real finalize_run: wrong token → returns 0, result None."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        before = len(list_events(db_session))
        # Wrap real finalize_run: inject a deliberately wrong fencing_token
        # so the real PostgreSQL UPDATE returns rowcount 0
        from apps.api.services import orchestration_worker as ow_mod
        original = ow_mod.finalize_run

        def fenced_finalize(*args, **kwargs):
            kwargs["fencing_token"] = 999999  # guaranteed wrong
            return original(*args, **kwargs)

        with patch.object(ow_mod, "finalize_run", fenced_finalize):
            result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        assert result is None
        worker._maybe_notify_automation_worker(result)
        assert len(list_events(db_session)) == before
        # Run/attempt/lease reflect fencing: attempt failed, run not finalized
        from sqlalchemy import text
        run_row = db_session.execute(text(
            "SELECT id, status FROM runs WHERE schedule_id = :sid"
            " ORDER BY scheduled_at DESC LIMIT 1"
        ), {"sid": sid}).fetchone()
        assert run_row is not None
        run_id = run_row[0]
        # Run stays 'started' — never finalized by stale-token path
        attempt = db_session.execute(text(
            "SELECT status FROM attempts WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert attempt is not None and attempt[0] == "failed"
        lease = db_session.execute(text(
            "SELECT released_at FROM leases WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert lease is not None

    def test_non_final_status_no_notification(
        self, db_session: Session,
    ) -> None:
        """Non-final outcome with real persisted run: no notification created."""
        _enable_all(db_session)
        hid = _hid(db_session)
        sid = _create_schedule(db_session, hid, "guardian.evaluate_all")
        info = _schedule_info(db_session, sid)
        worker = _make_worker(db_session, result={"status": "failed"})
        # Execute a real failed run to get a valid persisted run_id
        result = worker._execute_scheduled(db_session, info)
        db_session.commit()
        assert result is not None
        run_id = result["run_id"]
        household_id = result["household_id"]
        # Now dispatch with non-final status using the real persisted identity
        before = len(list_events(db_session))
        worker._maybe_notify_automation_worker({
            "run_id": run_id,
            "household_id": household_id,
            "finalize_status": "pending",
        })
        assert len(list_events(db_session)) == before


class TestDedupForSliceB:
    def test_same_entity_dedup_with_exact_fingerprint(
        self, db_session: Session,
    ) -> None:
        """Same entity_id twice → first delivered, second dedup-suppressed."""
        _enable_all(db_session)
        from apps.api.services.notification_service import dispatch_notification
        from tests.test_notifications import FakeAdapter
        hid = _hid(db_session)
        sid = str(uuid4())
        expected_fp = compute_fingerprint(
            "committee", "session_complete", "info", hid, sid,
        )
        dispatch_notification(
            db_session, source="committee", event_type="session_complete",
            severity="info", household_id=hid, entity_id=sid,
            adapter=FakeAdapter(), now=_FIXED_NOW,
        )
        events1 = list_events(db_session)
        assert events1[0].delivery_status == "delivered"
        assert events1[0].suppressed_reason is None
        assert events1[0].fingerprint == expected_fp
        dispatch_notification(
            db_session, source="committee", event_type="session_complete",
            severity="info", household_id=hid, entity_id=sid,
            adapter=FakeAdapter(), now=_FIXED_NOW,
        )
        events = list_events(db_session)
        assert events[0].delivery_status == "suppressed"
        assert events[0].suppressed_reason == "dedup"
        assert events[0].fingerprint == expected_fp
        assert events[1].fingerprint == expected_fp

    def test_different_entities_different_fingerprints(
        self, db_session: Session,
    ) -> None:
        """Different entity_ids → different fingerprints, both delivered."""
        _enable_all(db_session)
        from apps.api.services.notification_service import dispatch_notification
        from tests.test_notifications import FakeAdapter
        hid = _hid(db_session)
        eid1, eid2 = str(uuid4()), str(uuid4())
        fp1 = compute_fingerprint("automation", "run_failed", "warning", hid, eid1)
        fp2 = compute_fingerprint("automation", "run_failed", "warning", hid, eid2)
        assert fp1 != fp2
        dispatch_notification(
            db_session, source="automation", event_type="run_failed",
            severity="warning", household_id=hid, entity_id=eid1,
            adapter=FakeAdapter(), now=_FIXED_NOW,
        )
        dispatch_notification(
            db_session, source="automation", event_type="run_failed",
            severity="warning", household_id=hid, entity_id=eid2,
            adapter=FakeAdapter(), now=_FIXED_NOW,
        )
        events = list_events(db_session)
        assert events[0].fingerprint == fp2
        assert events[1].fingerprint == fp1
        assert events[0].delivery_status == "delivered"
        assert events[1].delivery_status == "delivered"
        assert events[0].suppressed_reason is None
        assert events[1].suppressed_reason is None


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
        "index_passive_investing": "Passive index exposure reduces single-stock risk. """ + _SECRET_PROVIDER + """",
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
        " VALUES (:id, :hid, 'Test Session', :proposal, 'queued')"
    ), {"id": sid, "hid": hid, "proposal": _SECRET_PROPOSAL + " Evaluate allocation."})
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
    from apps.api.services.orchestration_worker import OrchestrationWorker
    db_url = session.get_bind().url.render_as_string(hide_password=False)
    return OrchestrationWorker(
        db_url, worker_id="test-worker-slice-b",
        executor=FakeJobExecutor(result=result),
    )


class FakeJobExecutor:
    def __init__(self, result=None):
        self._result = result or {}

    def execute(self, **kwargs):
        return dict(self._result)


def _run_to_completion(session, cs) -> None:
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
