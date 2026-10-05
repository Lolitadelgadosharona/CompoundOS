# ruff: noqa: F811
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services import launch_investment as svc
from apps.api.services.committee_evidence_registry import evidence_registry
from apps.api.services.effective_policy import bucket_findings
from apps.api.services.provider_output_validator import validate_provider_output
from apps.api.services.valuation import value_rows
from tests.test_committee_provider import _valid_report
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup

NOW = datetime.now(timezone.utc)


@pytest.mark.parametrize(
    "change",
    [
        dict(source="simulation"),
        dict(identity_verified=False),
        dict(quote_identity_verified=False),
        dict(quote_quality="REPORTED"),
        dict(market_price=None),
        dict(market_price_as_of=NOW + timedelta(seconds=1)),
        dict(market_price_as_of=NOW - timedelta(hours=25)),
        dict(market_price=Decimal("NaN")),
    ],
)
def test_untrusted_required_position_never_ready(change, monkeypatch):
    monkeypatch.setattr(
        "apps.api.services.valuation.trusted_source", lambda s: s == "verified-test"
    )
    row = dict(
        id="p",
        quantity=1,
        market_price=Decimal(100),
        market_price_currency="USD",
        market_price_as_of=NOW,
        source="verified-test",
        identity_verified=True,
        quote_identity_verified=True,
        quote_quality="OBSERVED",
    )
    row.update(change)
    assert not value_rows("USD", [row], [], [], NOW).recommendation_ready


def test_trusted_position_ready_and_missing_fx_blocked(monkeypatch):
    monkeypatch.setattr(
        "apps.api.services.valuation.trusted_source", lambda s: s == "verified-test"
    )
    row = dict(
        id="p",
        quantity=1,
        market_price=100,
        market_price_currency="USD",
        market_price_as_of=NOW,
        source="verified-test",
        identity_verified=True,
        quote_identity_verified=True,
        quote_quality="OBSERVED",
    )
    assert value_rows("USD", [row], [], [], NOW).recommendation_ready
    row["market_price_currency"] = "EUR"
    assert not value_rows("USD", [row], [], [], NOW).recommendation_ready


def test_published_bucket_bounds_and_missing_bucket():
    bucket = [dict(bucket_name="CORE", min_pct=Decimal(0), max_pct=Decimal(0))]
    row = dict(kind="position", capital_bucket="CORE", base_value=Decimal(100))
    assert bucket_findings([row], bucket)
    assert not bucket_findings([row], [dict(bucket[0], max_pct=Decimal(100))])
    del row["capital_bucket"]
    assert bucket_findings([row], bucket)


@pytest.mark.postgres
def test_published_core_zero_blocks_same_audit_candidate(db_session, setup):
    h, _, _, version = setup
    db_session.execute(text("ALTER TABLE policy_capital_buckets DISABLE TRIGGER USER"))
    db_session.execute(
        text(
            "INSERT INTO policy_capital_buckets"
            "(id,version_id,bucket_name,target_pct,min_pct,max_pct) "
            "VALUES(:id,:v,'CORE',0,0,0)"
        ),
        {"id": uuid4(), "v": version},
    )
    db_session.execute(text("ALTER TABLE policy_capital_buckets ENABLE TRIGGER USER"))
    db_session.commit()
    result = svc.evaluate(db_session, h, svc.configuration(db_session, h))
    assert not result["recommendation_ready"]
    assert any("Bucket CORE" in x for x in result["policy"]["findings"])


def test_registry_context_and_simulation_label():
    sid = uuid4()
    facts = {"source": "simulation"}
    item = SimpleNamespace(
        id=uuid4(),
        session_id=sid,
        source_type="external",
        citation_ref="test:evidence",
        provenance={"source": "test"},
        as_of=NOW,
        structured_facts=facts,
        content_hash=hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest(),
    )
    cs = SimpleNamespace(id=sid, evidence_items=[item])
    registry = evidence_registry(cs)
    ref = registry[str(item.id)]
    assert ref["mode"] == "SIMULATED" and "[simulated]" in ref["claim"]
    report = _valid_report()
    report["recommended_direction"] = "aligned_with_policy"
    report["evidence_citations"] = [
        dict(evidence_id=str(item.id), citation_ref=ref["citation_ref"], claim=ref["claim"])
    ]
    assert validate_provider_output(report, set(registry), registry).passed
    report["evidence_citations"][0]["claim"] = "Live verified fact"
    assert not validate_provider_output(report, set(registry), registry).passed
    item.session_id = uuid4()
    with pytest.raises(ValueError, match="context"):
        evidence_registry(cs)


@pytest.mark.parametrize(
    "citation",
    [
        {},
        {"evidence_id": "invented"},
        {"evidence_id": "invented", "citation_ref": "x", "claim": "x"},
    ],
)
def test_malformed_or_unknown_citation_rejected(citation):
    report = _valid_report()
    report["recommended_direction"] = "aligned_with_policy"
    report["evidence_citations"] = [citation]
    assert not validate_provider_output(report, set()).passed


@pytest.mark.postgres
def test_legacy_setup_limit_is_not_silently_omitted(db_session, setup):
    from types import SimpleNamespace

    hid, _, _, _ = setup
    original = svc.policy(db_session, hid)
    version = SimpleNamespace(
        id=original.id,
        prohibited_assets=original.prohibited_assets,
        leverage_policy=original.leverage_policy,
        notes=json.dumps({"max_single_position_pct": 20}),
    )
    _, _, blockers = svc.policy_inputs(db_session, version)
    assert any("LEGACY_POLICY_LIMIT_RECONCILIATION_REQUIRED" in b for b in blockers)
    version.notes = json.dumps({"max_single_position_pct": 60})
    assert not svc.policy_inputs(db_session, version)[2]
