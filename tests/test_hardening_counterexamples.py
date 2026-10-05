# ruff: noqa: F811
"""Same inputs as the independent Owner audit, with safe outcomes asserted."""

import json
from uuid import UUID

import pytest
from sqlalchemy import text

from apps.api.decision_schemas import DiscardDecisionRequest
from apps.api.models import CommitteeSession
from apps.api.services import launch_investment as svc
from apps.api.services.ai_provider import FakeProvider
from apps.api.services.committee_orchestration import run_committee
from apps.api.services.decisions import discard_draft
from tests.test_committee_provider import _valid_report
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup

pytestmark = pytest.mark.postgres


def test_same_linked_discard_preserves_immutable_history(db_session, setup):
    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid)
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    did = UUID(preview["decision_id"])
    revision = db_session.execute(
        text("SELECT revision FROM decision_drafts WHERE decision_id=:i"), {"i": did}
    ).scalar()
    discard_draft(db_session, did, DiscardDecisionRequest(expected_revision=revision))
    db_session.commit()
    assert (
        db_session.execute(
            text("SELECT count(*) FROM contribution_decisions WHERE decision_id=:i"), {"i": did}
        ).scalar()
        == 1
    )
    with pytest.raises(ValueError, match="rejected"):
        svc.approve(db_session, hid, UUID(candidate["id"]))


def test_same_malformed_marker_no_uuid_cast_failure(db_session, setup):
    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid)
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    db_session.execute(
        text("UPDATE decision_drafts SET evidence_or_sources=:s WHERE decision_id=:i"),
        {"s": "research_run_id=" + "-" * 36, "i": UUID(preview["decision_id"])},
    )
    db_session.commit()
    assert (
        db_session.execute(
            text("SELECT evidence_or_sources FROM decision_drafts WHERE decision_id=:i"),
            {"i": UUID(preview["decision_id"])},
        ).scalar()
        == "research_run_id=" + "-" * 36
    )


def test_same_empty_citations_never_authorize(db_session, setup):
    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid)
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    cs = db_session.get(CommitteeSession, UUID(preview["committee_session_id"]))
    cs.status = "queued"
    db_session.commit()
    report = _valid_report()
    report.update(
        policy_alignment="Aligned with published policy",
        confidence="high",
        recommended_direction="aligned_with_policy",
        evidence_citations=[{}],
    )
    with pytest.raises(ValueError, match="Citation"):
        run_committee(
            db_session,
            cs,
            FakeProvider(response_text=json.dumps(report)),
            prompt_version="contribution-v1.1",
            max_retries=0,
        )
    assert cs.status == "failed"
    with pytest.raises(ValueError, match="Committee"):
        svc.approve(db_session, hid, UUID(candidate["id"]))


def test_research_wrapper_cannot_bypass_completed_committee(db_session, setup):
    from apps.api.services.dashboard_research import DashboardResearchService

    hid, _, assets, _ = setup
    request = DashboardResearchService.create_request(db_session, "VTI", hid, asset_id=assets[0].id)
    with pytest.raises(ValueError, match="Validated research Committee"):
        svc.require_research_committee(db_session, UUID(request["run_id"]))


def test_future_observation_cannot_fall_back_to_older_trusted_quote(db_session, setup, provider):
    from datetime import datetime, timedelta, timezone

    from apps.api.services.instrument_resolver import identity_dimensions

    hid, _, assets, _ = setup
    db_session.execute(
        text(
            "INSERT INTO market_observations"
            "(id,asset_id,price,currency,as_of,provider,quality,identity) "
            "VALUES(gen_random_uuid(),:a,100,'USD',:t,'synthetic','OBSERVED',"
            "CAST(:identity AS jsonb))"
        ),
        {
            "a": assets[0].id,
            "t": datetime.now(timezone.utc) + timedelta(hours=1),
            "identity": json.dumps(identity_dimensions(provider.identify("VTI"))),
        },
    )
    db_session.commit()
    with pytest.raises(ValueError, match="stale target price"):
        svc.make_candidate(db_session, hid)


def test_duplicate_run_claim_prevents_second_provider_call(db_session, setup, postgres_engine):
    from sqlalchemy.orm import Session

    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid)
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    cs = db_session.get(CommitteeSession, UUID(preview["committee_session_id"]))
    cs.status = "queued"
    db_session.commit()
    calls = []

    class CountProvider(FakeProvider):
        def call(self, *args, **kwargs):
            calls.append(True)
            return super().call(*args, **kwargs)

    report = _valid_report(cs)
    report["confidence"] = "high"
    provider = CountProvider(response_text=json.dumps(report))
    with Session(postgres_engine) as second:
        stale = second.get(CommitteeSession, cs.id)
        run_committee(db_session, cs, provider, prompt_version="contribution-v1.1")
        with pytest.raises(ValueError, match="duplicate provider call"):
            run_committee(second, stale, provider, prompt_version="contribution-v1.1")
        second.rollback()
    assert len(calls) == 1


def test_exact_combined_provider_collision_from_owner_audit(db_session, setup, provider):
    from dataclasses import replace

    from apps.api.services.instrument_resolver import InstrumentUnavailable, canonical_asset

    _, _, assets, _ = setup
    collision = replace(provider.identify("VTI"), symbol="NOTVTI", currency="EUR", exchange="OTHER")
    with pytest.raises(InstrumentUnavailable, match="IDENTITY_MISMATCH"):
        canonical_asset(db_session, collision)
    assert canonical_asset(db_session, provider.identify("VTI")).id == assets[0].id
