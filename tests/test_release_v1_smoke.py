# ruff: noqa: F811
"""Release acceptance: explicit synthetic evidence, isolated DB, no broker calls."""

import json
from decimal import Decimal as D
from io import BytesIO
from uuid import UUID

import pytest
from sqlalchemy import text

from apps.api.models import CommitteeSession
from apps.api.services import launch_investment as svc
from apps.api.services.ai_provider import DeepSeekProvider, FakeProvider, ProviderConfig
from apps.api.services.committee_evidence_registry import evidence_registry
from apps.api.services.committee_orchestration import run_committee
from apps.api.services.instrument_resolver import canonical_asset, resolve_query
from tests.test_committee_provider import _valid_report
from tests.test_hardening_owner_scenario import (
    test_owner_four_instruments_initial_monthly as run_owner_scenario,
)
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup


def test_supported_deepseek_model_config_and_nonthinking_payload(monkeypatch):
    monkeypatch.setenv("COMPOUNDOS_DEEPSEEK_MODEL", "deepseek-v4-pro")
    captured = {}

    def request(req, timeout):
        captured.update(json.loads(req.data))
        return BytesIO(
            json.dumps(
                {
                    "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    "model": "verified-response-model-test-only",
                }
            ).encode()
        )

    monkeypatch.setattr("urllib.request.urlopen", request)
    response = DeepSeekProvider(api_key="synthetic-test-only").call("JSON only", "JSON evidence")
    assert captured["model"] == "deepseek-v4-pro"
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["response_format"] == {"type": "json_object"}
    assert response.model == "verified-response-model-test-only"
    monkeypatch.delenv("COMPOUNDOS_DEEPSEEK_MODEL")
    assert ProviderConfig().model == "deepseek-flash"


@pytest.mark.postgres
def test_owner_release_workflow_search_to_journal_manual(db_session, setup, provider):
    hid, _, assets, _ = setup
    for symbol in ["VTI", "QQQ", "VXUS", "SGOV"]:
        instrument = resolve_query(symbol, provider)
        selected = canonical_asset(db_session, instrument)
        assert selected.symbol == symbol
    # Reuse the independently verified exact Owner-scenario input before Committee.
    run_owner_scenario(db_session, setup, provider)
    candidate = svc.make_candidate(db_session, hid)
    evidence = candidate["evidence"]
    assert evidence["recommendation_ready"]
    assert D(evidence["plan"]["portfolio_value"]) == 100000
    assert D(evidence["plan"]["new_capital"]) == 1400
    assert len(evidence["plan"]["rows"]) == 4
    assert (
        sum(D(r["buy_amount"]) for r in evidence["plan"]["rows"])
        + D(evidence["plan"]["retained_cash"])
        == 1400
    )
    assert evidence["policy"]["status"] != "BLOCKED"
    assert evidence["guardian"]["status"] != "BLOCKED"
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    with pytest.raises(ValueError):
        svc.approve(db_session, hid, UUID(candidate["id"]))
    cs = db_session.get(CommitteeSession, UUID(preview["committee_session_id"]))
    registry = evidence_registry(cs)
    eid = next(iter(registry))
    report = _valid_report()
    report.update(
        policy_alignment="Consistent with supplied evidence",
        confidence="medium",
        recommended_direction="aligned_with_policy",
        evidence_citations=[
            {
                "evidence_id": eid,
                "citation_ref": registry[eid]["citation_ref"],
                "claim": registry[eid]["claim"],
            }
        ],
    )
    cs.status = "queued"
    db_session.commit()
    run_committee(
        db_session,
        cs,
        FakeProvider(response_text=json.dumps(report)),
        prompt_version="contribution-v1.1",
    )
    result = svc.approve(db_session, hid, UUID(candidate["id"]))
    assert result["execution"] == "MANUAL"
    snapshot = db_session.execute(
        text("SELECT rationale FROM decision_confirmed_snapshots WHERE decision_id=:i"),
        {"i": UUID(result["decision_id"])},
    ).scalar()
    assert json.loads(snapshot) == evidence["plan"]
    assert (
        db_session.execute(
            text("SELECT count(*) FROM audit_events WHERE action='contribution.manual.approved'")
        ).scalar()
        == 1
    )
    assert db_session.execute(text("SELECT count(*) FROM transactions")).scalar() == 0
    print(
        "INTEGRATION VERIFIED: synthetic search, identity, portfolio, FX, contribution, "
        "Policy, Guardian, Committee, Owner approval, Journal, AuditEvent, manual plan; "
        "zero transactions. REAL PROVIDER NOT VERIFIED."
    )
