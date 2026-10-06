"""Synthetic V1 safety and full-workflow tests; all DB writes use isolated _test DB."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services import launch_investment as svc
from apps.api.services.contribution_engine import contribution_plan
from apps.api.services.instrument_resolver import (
    AmbiguousInstrument,
    Instrument,
    InstrumentUnavailable,
    canonical_asset,
    identity_dimensions,
    ledger_identity,
    query_from_question,
    resolve_query,
)
from apps.api.services.launch_providers import FXObservation, PriceObservation, YahooPublicProvider
from apps.api.services.valuation import RecommendationUnavailable, load_valuation, value_rows


class SyntheticProvider:
    name = "synthetic"
    test_only = True
    """Test-only provider, deliberately not exported by production factories."""

    def search(self, query):
        if query.lower() == "ambiguous":
            return [self.identify("VTI"), self.identify("VOO")]
        if query.lower() in {"bad", "asdf qwerty zxcv", "what is the meaning of life"}:
            return []
        aliases = {
            "nvidia": "NVDA",
            "apple": "AAPL",
            "microsoft": "MSFT",
            "tesla": "TSLA",
            "amazon": "AMZN",
            "google": "GOOGL",
            "meta": "META",
        }
        return [self.identify(aliases.get(query.lower(), query.upper()))]

    def identify(self, pid):
        symbol = pid.replace("-", ".")
        return Instrument(symbol, "Synthetic " + symbol, "TEST", "ETF", "USD", "synthetic", pid)

    def price(self, i):
        return PriceObservation(
            i.provider_id,
            D(100),
            "USD",
            datetime.now(timezone.utc),
            "synthetic",
            "OBSERVED",
            identity_dimensions(i),
        )

    def fx(self, a, b):
        return FXObservation(
            a,
            b,
            D(1) / 7,
            datetime.now(timezone.utc),
            "synthetic",
            identity={"from_currency": a, "to_currency": b, "provider_id": a + b + "=X"},
        )


@pytest.fixture
def provider():
    return SyntheticProvider()


@pytest.mark.parametrize("symbol", ["VTI", "QQQM", "SGOV", "AVUV", "SOMEETF", "BRK.B"])
def test_dynamic_arbitrary_etf_and_class_share(symbol, provider):
    assert resolve_query(symbol, provider).symbol == symbol
    assert query_from_question("Should I buy $" + symbol + "?") == symbol


def test_ambiguous_search_requires_selection(provider):
    with pytest.raises(AmbiguousInstrument) as e:
        resolve_query("ambiguous", provider)
    assert len(e.value.candidates) == 2


def test_invalid_and_outage(provider, monkeypatch):
    with pytest.raises(InstrumentUnavailable):
        resolve_query("bad", provider)
    with pytest.raises(InstrumentUnavailable):
        query_from_question("")
    monkeypatch.setattr(
        "httpx.get",
        lambda *a, **k: (_ for _ in ()).throw(__import__("httpx").ConnectError("outage")),
    )
    with pytest.raises(InstrumentUnavailable):
        YahooPublicProvider().search("VTI")


def test_contribution_first_overweight_gets_zero_conservation():
    plan = contribution_plan(
        {"vti": 45000, "qqq": 36000, "vxus": 9000, "sgov": 10000},
        {"vti": 50, "qqq": 30, "vxus": 10, "sgov": 10},
        D(10000) / 7,
        100000,
    )
    buys = {r["asset_id"]: D(r["buy_amount"]) for r in plan["rows"]}
    assert buys["qqq"] == 0 and buys["vti"] > buys["vxus"] > 0
    assert sum(buys.values()) + D(plan["retained_cash"]) == D(plan["new_capital"])
    assert next(r for r in plan["rows"] if r["asset_id"] == "vti")["absolute_drift"] == "-5.00"


def test_initial_cash_is_not_double_counted_and_floor():
    p = contribution_plan({}, {"a": 50, "b": 50}, 100000, 100000, 10, existing_cash=True)
    assert p["post_value"] == "100000" and sum(D(r["buy_amount"]) for r in p["rows"]) == 90000
    assert p["retained_cash"] == "10000.00"
    with pytest.raises(ValueError):
        contribution_plan({}, {"a": 100}, 100001, 100000, existing_cash=True)


@pytest.mark.parametrize("kind", ["price", "fx"])
@pytest.mark.parametrize("defect", ["missing", "stale", "invalid", "future", "simulation"])
def test_observation_quality_fails_closed(kind, defect):
    now = datetime.now(timezone.utc)
    obs = (
        PriceObservation("VTI", D(100), "USD", now, "synthetic", "OBSERVED")
        if kind == "price"
        else FXObservation("CNY", "USD", D(".14"), now, "synthetic")
    )
    if defect == "missing":
        obs = replace(obs, provider="")
    if defect == "stale":
        obs = replace(obs, as_of=now - timedelta(hours=25))
    if defect == "future":
        obs = replace(obs, as_of=now + timedelta(seconds=1))
    if defect == "invalid":
        obs = replace(obs, **({"price": D(0)} if kind == "price" else {"rate": D(0)}))
    if defect == "simulation":
        obs = replace(obs, quality="SIMULATION")
    with pytest.raises(RecommendationUnavailable):
        svc.check_observation(obs, now)


@pytest.fixture
def setup(db_session, provider, monkeypatch, request):
    from apps.api.services import launch_providers

    for name in ["get_instrument_provider", "get_market_provider", "get_fx_provider"]:
        monkeypatch.setattr(launch_providers, name, lambda: provider)
        monkeypatch.setattr(svc, name, lambda: provider)
    from apps.api.models import (
        FxRate,
        HouseholdProfile,
        InvestmentPolicy,
        InvestmentPolicyVersion,
        PolicyRule,
    )
    from apps.api.services.portfolio_reality import add_account, add_cash

    h = HouseholdProfile(id=uuid4(), household_name="SYNTHETIC ONLY", base_currency="USD")
    db_session.add(h)
    db_session.flush()
    p = InvestmentPolicy(id=uuid4(), household_id=h.id)
    db_session.add(p)
    db_session.flush()
    now = datetime.now(timezone.utc)
    v = InvestmentPolicyVersion(
        id=uuid4(),
        policy_id=p.id,
        version_number=1,
        status="published",
        objectives="test",
        time_horizon="long",
        liquidity="test",
        diversification="test",
        contribution_policy="monthly",
        rebalancing_policy="contribution first",
        prohibited_assets="[]",
        leverage_policy="No leverage",
        decision_process="Owner",
        notes="",
        published_at=now,
    )
    db_session.add(v)
    db_session.flush()
    # Explicit TEST policy, not a change to any Owner Policy or default Guardian threshold.
    max_position = getattr(request, "param", {}).get("max_position", "60")
    for typ, value in [
        ("max_single_position_pct", max_position),
        ("max_sector_concentration_pct", "100"),
    ]:
        db_session.add(
            PolicyRule(
                id=uuid4(),
                version_id=v.id,
                rule_type=typ,
                rule_value=value,
                severity="critical",
                enabled=True,
                sort_order=0,
            )
        )
    db_session.flush()
    v.sealed_at = now
    db_session.commit()
    account = add_account(
        db_session, name="Test", account_type="brokerage", capital_bucket="CORE", currency="USD"
    )
    aid = UUID(account["id"])
    add_cash(db_session, account_id=aid, currency="USD", amount=D(100000))
    assets = []
    for symbol in ["VTI", "QQQ"]:
        assets.append(canonical_asset(db_session, provider.identify(symbol)))
    db_session.add(
        FxRate(
            from_currency="CNY",
            to_currency="USD",
            rate=D(".14"),
            rate_source="synthetic",
            identity={"from_currency": "CNY", "to_currency": "USD", "provider_id": "CNYUSD=X"},
            quality="OBSERVED",
            observed_at=now,
        )
    )
    db_session.commit()
    settings = {
        "base_currency": "USD",
        "monthly_currency": "CNY",
        "monthly_amount": "10000",
        "initial_capital": "100000",
        "targets": [
            {
                "asset_id": str(a.id),
                "weight": "50",
                "leverage_status": "unleveraged",
                "equity_exposure_pct": "100",
            }
            for a in assets
        ],
    }
    svc.configure(db_session, h.id, settings)
    for a in assets:
        db_session.execute(
            text(
                (
                    "INSERT INTO "
                    "market_observations(id,asset_id,price,currency,as_of,provider,quality,identity)"
                    " VALUES(:i,:a,100,'USD',:t,'synthetic','OBSERVED',CAST(:identity AS jsonb))"
                )
            ),
            {
                "i": uuid4(),
                "a": a.id,
                "t": now,
                "identity": json.dumps(identity_dimensions(provider.identify(a.symbol))),
            },
        )
    db_session.commit()
    return h.id, aid, assets, v.id


@pytest.mark.postgres
def test_cny_to_usd_and_evidence_deterministic(db_session, setup):
    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid)
    assert D(candidate["evidence"]["plan"]["new_capital"]) == D(1400)
    assert candidate["evidence"]["recommendation_ready"]
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    facts = db_session.execute(
        text("SELECT structured_facts FROM committee_evidence_items WHERE session_id=:i"),
        {"i": UUID(preview["committee_session_id"])},
    ).scalar()
    assert facts == candidate["evidence"]
    assert facts["classification"] == "FACT"
    assert facts["fx"]["inputs"][0]["fx_source"] == "synthetic"


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["price", "fx"])
def test_missing_data_prevents_candidate(db_session, setup, kind):
    hid, _, assets, _ = setup
    # TRUNCATE only the isolated synthetic DB; immutable evidence cannot be erased individually.
    table = "market_observations" if kind == "price" else "fx_rates"
    db_session.execute(text("TRUNCATE " + table + " CASCADE"))
    db_session.commit()
    with pytest.raises(RecommendationUnavailable):
        svc.make_candidate(db_session, hid)
    assert db_session.execute(text("SELECT count(*) FROM contribution_candidates")).scalar() == 0


@pytest.mark.postgres
def test_guardian_rejection_and_policy_no_bypass(db_session, setup, monkeypatch):
    hid, _, _, _ = setup
    monkeypatch.setattr(svc.gi, "has_active_critical_event", lambda *args: True)
    c = svc.make_candidate(db_session, hid)
    assert c["evidence"]["guardian"]["status"] == "BLOCKED"
    with pytest.raises(RecommendationUnavailable):
        svc.preview_committee(db_session, hid, UUID(c["id"]))


@pytest.mark.postgres
def test_published_policy_rule_block(db_session, setup, monkeypatch):
    hid, _, _, _ = setup
    original = svc.policy_inputs
    monkeypatch.setattr(svc, "policy_inputs", lambda s, v: (original(s, v)[0], ["VTI"], []))
    c = svc.make_candidate(db_session, hid)
    assert c["evidence"]["policy"]["status"] == "BLOCKED"
    with pytest.raises(RecommendationUnavailable):
        svc.approve(db_session, hid, UUID(c["id"]))


@pytest.mark.postgres
def test_approval_journal_audit_manual_only(db_session, setup):
    from apps.api.models import CommitteeSession
    from apps.api.services.ai_provider import FakeProvider
    from apps.api.services.committee_orchestration import run_committee
    from tests.test_committee_provider import _valid_report

    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid)
    preview = svc.preview_committee(db_session, hid, UUID(candidate["id"]))
    with pytest.raises(RecommendationUnavailable):
        svc.approve(db_session, hid, UUID(candidate["id"]))
    report = _valid_report()
    report["policy_alignment"] = "Consistent with provided evidence"
    report["recommended_direction"] = "aligned_with_policy"
    report["confidence"] = "medium"
    cs = db_session.get(CommitteeSession, UUID(preview["committee_session_id"]))
    from apps.api.services.committee_evidence_registry import evidence_registry

    registry = evidence_registry(cs)
    eid = next(iter(registry))
    report["evidence_citations"] = [
        {
            "evidence_id": eid,
            "citation_ref": registry[eid]["citation_ref"],
            "claim": registry[eid]["claim"],
        }
    ]
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
    assert json.loads(snapshot) == candidate["evidence"]["plan"]
    assert (
        db_session.execute(
            text("SELECT count(*) FROM audit_events WHERE action='contribution.manual.approved'")
        ).scalar()
        == 1
    )
    assert db_session.execute(text("SELECT count(*) FROM transactions")).scalar() == 0


@pytest.mark.postgres
def test_edited_journal_generic_confirm_cannot_bypass(db_session, setup):
    from apps.api.decision_schemas import ConfirmDecisionRequest, UpdateDecisionDraftRequest
    from apps.api.services.decisions import confirm_draft, read_draft, update_draft

    hid, _, _, _ = setup
    c = svc.make_candidate(db_session, hid)
    p = svc.preview_committee(db_session, hid, UUID(c["id"]))
    did = UUID(p["decision_id"])
    draft = read_draft(db_session, did)
    draft = update_draft(
        db_session,
        did,
        UpdateDecisionDraftRequest(
            expected_revision=draft.revision, evidence_or_sources="owner edited"
        ),
    )
    with pytest.raises(RecommendationUnavailable):
        confirm_draft(
            db_session,
            did,
            ConfirmDecisionRequest(expected_revision=draft.revision, confirmation=True),
        )


@pytest.mark.postgres
def test_rejection_cannot_be_approved(db_session, setup, api_client):
    hid, _, _, _ = setup
    c = svc.make_candidate(db_session, hid)
    r = api_client.post("/api/investment/candidates/" + c["id"] + "/reject")
    assert r.status_code == 200
    with pytest.raises(RecommendationUnavailable):
        svc.validate_candidate(db_session, hid, UUID(c["id"]))


@pytest.mark.postgres
def test_identity_and_native_ledger_history_preserved(db_session, setup, provider):
    hid, account, assets, _ = setup
    first = assets[0]
    assert canonical_asset(db_session, provider.identify(first.symbol)).id == first.id
    assert (
        ledger_identity(
            db_session, first.symbol, exchange=first.exchange, currency=first.currency
        ).id
        == first.id
    )
    svc.make_candidate(db_session, hid, funding="initial")
    assert load_valuation(db_session, hid).total() == 100000


@pytest.mark.postgres
def test_configuration_change_invalidates_candidate(db_session, setup):
    hid, _, _, _ = setup
    c = svc.make_candidate(db_session, hid)
    config = dict(svc.configuration(db_session, hid)["settings"])
    config["monthly_amount"] = "20000"
    svc.configure(db_session, hid, config)
    with pytest.raises(RecommendationUnavailable):
        svc.validate_candidate(db_session, hid, UUID(c["id"]))


def test_reported_value_cannot_hide_invalid_price():
    now = datetime.now(timezone.utc)
    v = value_rows(
        "USD",
        [
            {
                "id": "x",
                "market_value": 100,
                "market_value_currency": "USD",
                "market_price": 0,
                "market_price_currency": "USD",
                "observed_at": now,
                "quantity": 1,
            }
        ],
        [],
        [],
        now,
    )
    assert not v.recommendation_ready and v.total() is None


def test_gbp_unit_quote_and_inverse_fx():
    now = datetime.now(timezone.utc)
    v = value_rows(
        "USD",
        [
            {
                "id": "UK",
                "quantity": D(10),
                "market_price": D(1234),
                "market_price_currency": "GBp",
                "market_price_as_of": now,
                "source": "synthetic",
            }
        ],
        [],
        [
            {
                "from_currency": "USD",
                "to_currency": "GBP",
                "rate": D(".8"),
                "observed_at": now,
                "rate_source": "synthetic",
            }
        ],
        now,
    )
    assert v.total() == D("154.25") and v.entries[0]["price_unit_multiplier"] == "0.01"


@pytest.mark.postgres
def test_two_accounts_same_canonical_asset_guardian_aggregates(db_session, setup):
    from apps.api.repositories.portfolio_foundation import create_position
    from apps.api.services.portfolio_reality import add_account

    hid, account, assets, vid = setup
    second = UUID(
        add_account(
            db_session,
            name="Other",
            account_type="brokerage",
            capital_bucket="CORE",
            currency="USD",
        )["id"]
    )
    now = datetime.now(timezone.utc)
    for a in [account, second]:
        create_position(
            db_session,
            account_id=a,
            asset_id=assets[0].id,
            quantity=D(2),
            quantity_source="provider_reported",
            avg_cost=D(50),
            avg_cost_currency="USD",
            market_price=D(100),
            market_price_currency="USD",
            observed_at=now,
            source="csv",
        )
    db_session.commit()
    v = load_valuation(db_session, hid)
    results = svc.gi.evaluate_single_position_concentration(db_session, hid, str(vid), valuation=v)
    assert len(results) == 1 and results[0].actual_value == 100


@pytest.mark.postgres
def test_unobserved_import_value_cannot_create_trusted_candidate(db_session, setup):
    from apps.api.repositories.portfolio_foundation import create_asset, create_position

    hid, account, _, _ = setup
    a = create_asset(
        db_session, symbol="OLD", name="Unverified", asset_type="ETF", currency="USD", exchange=None
    )
    create_position(
        db_session,
        account_id=account,
        asset_id=a.id,
        quantity=D(1),
        quantity_source="provider_reported",
        avg_cost=D(100),
        avg_cost_currency="USD",
        market_price=D(100),
        market_price_currency="USD",
        market_value=D(100),
        market_value_currency="USD",
        observed_at=datetime.now(timezone.utc),
        source="csv",
    )
    db_session.commit()
    with pytest.raises(RecommendationUnavailable, match="Observed price|DEGRADED"):
        svc.make_candidate(db_session, hid)


@pytest.mark.postgres
def test_production_rejects_synthetic_evidence(db_session, setup, monkeypatch):
    hid, _, _, _ = setup
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RecommendationUnavailable):
        svc.make_candidate(db_session, hid)


@pytest.mark.postgres
def test_generic_committee_route_cannot_bypass_contribution_validation(db_session, setup):
    from apps.api.models import CommitteeSession
    from apps.api.services.ai_provider import FakeProvider
    from apps.api.services.committee_orchestration import run_committee

    hid, _, _, _ = setup
    c = svc.make_candidate(db_session, hid)
    p = svc.preview_committee(db_session, hid, UUID(c["id"]))
    cs = db_session.get(CommitteeSession, UUID(p["committee_session_id"]))
    cs.status = "queued"
    db_session.commit()
    with pytest.raises(ValueError, match="exact deterministic evidence"):
        run_committee(db_session, cs, FakeProvider(response_text="{}"))


@pytest.mark.postgres
def test_model_cannot_invent_quantitative_facts(db_session, setup):
    from apps.api.models import CommitteeSession
    from apps.api.services.ai_provider import FakeProvider
    from apps.api.services.committee_orchestration import run_committee
    from tests.test_committee_provider import _valid_report

    hid, _, _, _ = setup
    c = svc.make_candidate(db_session, hid)
    p = svc.preview_committee(db_session, hid, UUID(c["id"]))
    cs = db_session.get(CommitteeSession, UUID(p["committee_session_id"]))
    cs.status = "queued"
    db_session.commit()
    report = _valid_report(cs)
    report["confidence"] = "high"
    report["policy_alignment"] = "FX is 9.99"
    report["recommended_direction"] = "aligned_with_policy"
    with pytest.raises(ValueError, match="Numerical financial facts"):
        run_committee(
            db_session,
            cs,
            FakeProvider(response_text=json.dumps(report)),
            prompt_version="contribution-v1.1",
        )
    assert db_session.execute(text("SELECT count(*) FROM committee_reports")).scalar() == 0


@pytest.mark.postgres
def test_populated_evidence_cannot_be_downgraded(db_session, setup, postgres_engine):
    from alembic import command
    from alembic.config import Config

    hid, _, _, _ = setup
    svc.make_candidate(db_session, hid)
    db_session.rollback()
    cfg = Config("alembic.ini")
    cfg.attributes["connection"] = postgres_engine
    with pytest.raises(RuntimeError, match="Preserve"):
        command.downgrade(cfg, "0034_research_run_status")
    assert db_session.execute(text("SELECT count(*) FROM contribution_candidates")).scalar() == 1


def test_fx_subcent_remainder_is_retained_exactly():
    capital = D(10000) / 7
    p = contribution_plan({}, {"a": 50, "b": 50}, capital, 100000)
    assert sum(D(r["buy_amount"]) for r in p["rows"]) + D(p["retained_cash"]) == capital
    assert D(p["post_value"]) == D(100000) + capital


@pytest.mark.postgres
def test_unverified_product_leverage_blocks_not_guessed(db_session, setup):
    hid, _, _, _ = setup
    config = dict(svc.configuration(db_session, hid)["settings"])
    config["targets"] = [{**t, "leverage_status": "unknown"} for t in config["targets"]]
    svc.configure(db_session, hid, config)
    c = svc.make_candidate(db_session, hid)
    assert not c["evidence"]["recommendation_ready"]
    assert any("leverage" in f for f in c["evidence"]["policy"]["findings"])


@pytest.mark.postgres
def test_default_guardian_warning_threshold_is_preserved(db_session, setup):
    hid, _, _, _ = setup
    # Use existing evaluator with explicit synthetic threshold defaults; no policy data mutation.
    from unittest.mock import patch

    from apps.api.services.guardian_intelligence import EvalResult

    with patch.object(
        svc.gi,
        "evaluate_sector_concentration",
        return_value=[EvalResult(exceeded=True, detail="Unclassified above existing default")],
    ):
        original = svc.policy_inputs
        with patch.object(
            svc,
            "policy_inputs",
            side_effect=lambda s, v: ({**original(s, v)[0], "_severity": {}}, [], []),
        ):
            c = svc.make_candidate(db_session, hid)
    assert (
        c["evidence"]["guardian"]["status"] == "WARNING" and c["evidence"]["recommendation_ready"]
    )


def test_exact_symbol_cannot_become_similar_product(provider):
    class SimilarProduct:
        def search(self, query):
            return [provider.identify("BRKC")]

    with pytest.raises(AmbiguousInstrument):
        resolve_query("BRK.B", SimilarProduct())


def test_yahoo_class_share_fallback_requires_verified_exchange(monkeypatch):
    provider = YahooPublicProvider()
    monkeypatch.setattr(
        provider, "_get", lambda *args: {"quotes": [{"symbol": "BRKC", "quoteType": "ETF"}]}
    )
    monkeypatch.setattr(
        provider,
        "identify",
        lambda pid: Instrument("BRK.B", "Class B", "NYQ", "STOCK", "USD", "yahoo_public", pid),
    )
    assert resolve_query("BRK.B", provider).provider_id == "BRK-B"
    monkeypatch.setattr(
        provider,
        "identify",
        lambda pid: Instrument("BRK.B", "Other", "OTHER", "STOCK", "USD", "yahoo_public", pid),
    )
    with pytest.raises(InstrumentUnavailable):
        provider.search("BRK.B")


def test_production_public_data_requires_access_authorization(monkeypatch):
    from apps.api.services.launch_providers import get_market_provider

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("COMPOUNDOS_YAHOO_ACCESS_AUTHORIZED", raising=False)
    with pytest.raises(InstrumentUnavailable, match="not authorized"):
        get_market_provider()
