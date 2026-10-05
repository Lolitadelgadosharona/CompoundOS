"""Explicit test adapter and canonical research provenance for persistence regressions."""

from dataclasses import asdict
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from apps.api.services.instrument_resolver import Instrument, canonical_asset, identity_dimensions


def seed_research_instrument(session, monkeypatch):
    from apps.api.services import launch_providers

    adapter = type(
        "ResearchTestAdapter",
        (),
        {"name": "synthetic", "provider_name": "synthetic", "test_only": True},
    )()
    for name in ["get_instrument_provider", "get_market_provider", "get_fx_provider"]:
        monkeypatch.setattr(launch_providers, name, lambda: adapter)
    instrument = Instrument("AAPL", "SYNTHETIC Apple", "TEST", "STOCK", "USD", "synthetic", "AAPL")
    asset = canonical_asset(session, instrument)
    session.execute(
        text(
            "INSERT INTO market_observations"
            "(id,asset_id,price,currency,as_of,provider,quality,identity) "
            "VALUES(:i,:a,100,'USD',:t,'synthetic','OBSERVED',CAST(:identity AS jsonb))"
        ),
        {
            "i": uuid4(),
            "a": asset.id,
            "t": datetime.now(timezone.utc),
            "identity": __import__("json").dumps(identity_dimensions(instrument)),
        },
    )
    session.info["research_test_identity"] = {
        "symbol": "AAPL",
        "asset_id": str(asset.id),
        "instrument": asdict(instrument),
    }
    session.commit()


def bind_test_research_requests(session):
    if "research_test_identity" not in session.info:
        return
    import json

    session.execute(
        text("UPDATE research_requests SET parameters=CAST(:p AS jsonb)"),
        {"p": json.dumps(session.info["research_test_identity"])},
    )
    session.commit()


def prepare_test_research_committee(session):
    """Completed test-provider review with actual context registry; not real-provider evidence."""
    import hashlib
    import json

    from apps.api.models import CommitteeEvidenceItem
    from apps.api.services.ai_provider import FakeProvider
    from apps.api.services.committee_orchestration import create_committee_session, run_committee
    from tests.test_committee_provider import _valid_report

    hid = session.execute(text("SELECT id FROM household_profiles")).scalar()
    for rid in session.execute(text("SELECT run_id FROM investment_memos")).scalars():
        cs = create_committee_session(
            session, hid, "Synthetic research validation", "Review supplied research"
        )
        from apps.api.services.launch_investment import research_review_context

        facts = {
            "run_id": str(rid),
            "source": "simulation",
            "review_context": research_review_context(session, rid),
        }
        cs.evidence_items.append(
            CommitteeEvidenceItem(
                id=uuid4(),
                session_id=cs.id,
                source_type="decision",
                source_title="Synthetic research",
                structured_facts=facts,
                content_hash=hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest(),
                provenance="compoundos_internal",
                as_of=datetime.now(timezone.utc),
                freshness="1",
                confidence="medium",
                citation_ref="test:research:" + str(rid),
            )
        )
        session.flush()
        cs.status = "queued"
        session.commit()
        run_committee(session, cs, FakeProvider(response_text=json.dumps(_valid_report(cs))))
        session.commit()


def publish_evaluable_test_policy(session):
    from apps.api.policy_schemas import (
        CreatePolicyDraftRequest,
        PolicyDraftUpdate,
        PublishPolicyDraftRequest,
    )
    from apps.api.services.policies import create_new_draft, publish_draft, update_draft_text

    session.commit()
    current_id = session.execute(
        text(
            "SELECT id FROM investment_policy_versions "
            "WHERE status='published' ORDER BY version_number DESC LIMIT 1"
        )
    ).scalar()
    session.commit()
    draft, _ = create_new_draft(session, CreatePolicyDraftRequest(source_version_id=current_id))
    updated = update_draft_text(
        session,
        PolicyDraftUpdate(
            expected_revision=draft.revision,
            prohibited_assets="[]",
            leverage_policy="no leverage",
            notes="Synthetic evaluable test policy; prior setup history retained",
        ),
    )
    publish_draft(
        session, PublishPolicyDraftRequest(expected_revision=updated.revision, confirmation=True)
    )
