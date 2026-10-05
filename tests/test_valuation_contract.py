"""Synthetic valuations: no external providers and no real ledger writes."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from apps.api.services.valuation import value_rows

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def position(value=None, ccy="USD", **extra):
    return dict(
        id="p",
        market_value=value,
        market_value_currency=ccy,
        market_price_currency=ccy,
        quantity=D(2),
        observed_at=NOW,
        source="csv",
        **extra,
    )


def cash(amount, ccy):
    return dict(id="cash", amount=D(amount), currency=ccy, observed_at=NOW)


def fx(a, b, rate, **extra):
    return dict(
        from_currency=a,
        to_currency=b,
        rate=D(str(rate)),
        rate_source="synthetic",
        observed_at=extra.get("observed_at", NOW),
    )


def test_usd_cny_eur_conservation_and_weights():
    v = value_rows(
        "USD",
        [position(D(100)), position(D(700), "CNY")],
        [cash(50, "USD"), cash(100, "EUR")],
        [fx("USD", "CNY", 7), fx("EUR", "USD", 1.1)],
        NOW,
    )
    assert v.total() == D(360)
    assert v.total("position") == D(200)
    assert v.total("cash") == D(160)
    assert sum(e["market_value"] / v.total("position") for e in v.positions()) == 1
    assert v.entries[1]["fx_inverse"] is True
    assert not v.recommendation_ready


@pytest.mark.parametrize(
    "rates",
    [
        [],
        [fx("CNY", "USD", 0)],
        [fx("CNY", "USD", -1)],
        [fx("CNY", "USD", 0.14, observed_at=NOW - timedelta(hours=25))],
    ],
)
def test_invalid_fx_never_partial_total(rates):
    v = value_rows("USD", [position(100), position(700, "CNY")], [cash(50, "USD")], rates, NOW)
    assert v.total() is None
    assert v.positions() == []
    assert not v.recommendation_ready
    assert v.status == "INCOMPLETE"


@pytest.mark.parametrize("age", [None, NOW - timedelta(hours=25), NOW + timedelta(seconds=1)])
def test_missing_stale_future_price(age):
    p = position(100)
    p["observed_at"] = age
    v = value_rows("USD", [p], [], [], NOW)
    assert v.total() is None and not v.recommendation_ready


def test_gbp_price_units():
    p = position(None, "GBp", market_price=D(150))
    v = value_rows("USD", [p], [], [fx("GBP", "USD", 1.25)], NOW)
    assert v.total() == D("3.75")
    assert v.entries[0]["unit_multiplier"] == "0.01"


def test_reported_amount_currency_is_authoritative():
    p = position(100, "EUR")
    p["market_price_currency"] = "USD"
    v = value_rows("USD", [p], [], [fx("EUR", "USD", 1.1)], NOW)
    assert v.total() == D(110)


def test_manual_cost_is_labelled_and_blocks_recommendations():
    p = position(100)
    p["source"] = "manual"
    v = value_rows("USD", [p], [], [], NOW)
    assert v.total() == D(100)
    assert v.status == "COST_ESTIMATE" and not v.recommendation_ready


def test_missing_price_never_zero():
    assert value_rows("USD", [position()], [], [], NOW).total() is None


@pytest.mark.postgres
def test_two_positions_two_cash_one_account_no_join_fanout(db_session):
    from apps.api.models import CashBalance, FxRate, Position
    from apps.api.services.dashboard_service import build_dashboard
    from apps.api.services.guardian_intelligence import _load_positions
    from apps.api.services.portfolio_reality import wealth_summary
    from apps.api.services.valuation import load_valuation
    from tests.test_dashboard_learning import _create_household, _setup_position

    hh = _create_household(db_session)
    _setup_position(db_session, hh.id, market_value=D(100))
    _setup_position(db_session, hh.id, market_value=D(1400), currency="CNY")
    positions = db_session.query(Position).all()
    positions[1].account_id = positions[0].account_id
    db_session.add(
        FxRate(
            from_currency="USD",
            to_currency="CNY",
            rate=D(7),
            rate_source="synthetic",
            observed_at=datetime.now(timezone.utc),
        )
    )
    for amount, currency in ((D(10), "USD"), (D(140), "CNY")):
        db_session.add(
            CashBalance(
                account_id=positions[0].account_id,
                amount=amount,
                currency=currency,
                observed_at=datetime.now(timezone.utc),
                source="csv",
                is_latest=True,
            )
        )
    db_session.flush()
    v = load_valuation(db_session, hh.id)
    assert len(v.entries) == 4 and v.total() == D(330)
    summary = wealth_summary(db_session, hh.id)
    dash = build_dashboard(db_session, hh.id)
    assert D(summary["net_worth"].replace(",", "")) == D(dash.net_worth.total_value) == D(330)
    assert D(summary["capital_bucket_summary"][0]["value"].replace(",", "")) == D(330)
    assert sum(p.market_value for p in _load_positions(db_session, hh.id)) == D(300)


def test_unknown_reported_amount_currency_is_not_guessed_from_asset_or_quote():
    p = position(100)
    p["market_value_currency"] = None
    assert value_rows("USD", [p], [], [], NOW).total() is None


@pytest.mark.postgres
@pytest.mark.parametrize("broken", ["missing_fx", "stale_price", "manual_cost"])
def test_quality_blocks_research_approval_and_guardian(db_session, broken):
    from sqlalchemy import text

    from apps.api.models import Position
    from apps.api.services.decision_lifecycle import OwnerDecisionService
    from apps.api.services.guardian import _evaluate_core
    from apps.api.services.guardian_intelligence import evaluate_single_position_concentration
    from apps.api.services.valuation import RecommendationUnavailable
    from tests.test_dashboard_learning import _setup_position
    from tests.test_decision_lifecycle import _setup_full_chain, _setup_household

    hh = _setup_household(db_session)
    idea, run, memo, review = _setup_full_chain(db_session, hh)
    _setup_position(db_session, hh, currency="EUR" if broken == "missing_fx" else "USD")
    p = db_session.query(Position).one()
    if broken == "stale_price":
        p.observed_at -= timedelta(hours=25)
    if broken == "manual_cost":
        p.source = "manual"
    db_session.commit()
    with pytest.raises(RecommendationUnavailable):
        OwnerDecisionService.approve(db_session, idea, memo, review, 75, hh)
    assert (
        db_session.execute(text("SELECT count(*) FROM decision_confirmed_snapshots")).scalar() == 0
    )
    result = _evaluate_core(
        db_session, household_id=hh, as_of_date=datetime.now(timezone.utc).date()
    )
    assert result["evaluation_run"]["status"] == "unavailable"
    assert result["events"] == [] and not result["persisted"]
    results = evaluate_single_position_concentration(db_session, hh, "unused")
    assert results[0].context["evaluation_status"] == "UNAVAILABLE"


@pytest.mark.postgres
def test_guardian_current_ledger_uses_converted_position_denominator(db_session):
    from apps.api.models import FxRate
    from apps.api.services.guardian import _evaluate_core
    from apps.api.services.guardian_intelligence import evaluate_single_position_concentration
    from tests.test_guardian_intelligence import (
        _create_household,
        _setup_policy,
        _setup_portfolio_data,
    )

    hh = _create_household(db_session)
    _, version = _setup_policy(db_session, hh.id)
    _setup_portfolio_data(db_session, hh.id, market_value=D(100))
    _, _, _, foreign = _setup_portfolio_data(db_session, hh.id, market_value=D(700))
    foreign.market_value_currency = "CNY"
    db_session.add(
        FxRate(
            from_currency="USD",
            to_currency="CNY",
            rate=D(7),
            rate_source="synthetic",
            observed_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()
    result = _evaluate_core(
        db_session, household_id=hh.id, as_of_date=datetime.now(timezone.utc).date()
    )
    assert result["source"] == "current_ledger"
    assert D(result["valuation"]["total_value"]) == D(200)
    assert [
        r.actual_value
        for r in evaluate_single_position_concentration(db_session, hh.id, str(version.id))
    ] == [D(50), D(50)]


@pytest.mark.parametrize("price", [0, -1, "NaN", "Infinity"])
def test_invalid_derived_price_is_incomplete(price):
    v = value_rows("USD", [position(None, market_price=D(str(price)))], [], [], NOW)
    assert v.total() is None and not v.recommendation_ready


def test_freshness_boundary_and_future_fx():
    old = NOW - timedelta(hours=24)
    assert not value_rows(
        "USD", [position(700, "CNY")], [], [fx("CNY", "USD", "0.14", observed_at=old)], NOW
    ).recommendation_ready
    assert not value_rows(
        "USD",
        [position(700, "CNY")],
        [],
        [fx("CNY", "USD", "0.14", observed_at=NOW + timedelta(seconds=1))],
        NOW,
    ).recommendation_ready


@pytest.mark.parametrize(
    "base,total", [("USD", "310"), ("CNY", "2170"), ("EUR", "281.8181818181818181818181818")]
)
def test_household_base_currency_is_explicit(base, total):
    v = value_rows(
        base,
        [position(100, "USD"), position(700, "CNY"), position(100, "EUR")],
        [],
        [fx("USD", "CNY", 7), fx("EUR", "USD", "1.1"), fx("EUR", "CNY", "7.7")],
        NOW,
    )
    assert abs(v.total() - D(total)) < D("0.00000001")
