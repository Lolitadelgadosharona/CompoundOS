# ruff: noqa: F811
import json
from decimal import Decimal as D
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.routers.launch_v1 import Holding, holding
from apps.api.services import launch_investment as svc
from apps.api.services.instrument_resolver import canonical_asset, identity_dimensions
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup


@pytest.mark.postgres
def test_owner_four_instruments_initial_monthly(db_session, setup, provider):
    hid, account, assets, pid = setup
    for sym in ["VXUS", "SGOV"]:
        a = canonical_asset(db_session, provider.identify(sym))
        assets.append(a)
        db_session.execute(
            text(
                "INSERT INTO market_observations"
                "(id,asset_id,price,currency,as_of,provider,quality,identity) "
                "VALUES(:i,:a,100,'USD',NOW(),'synthetic','OBSERVED',CAST(:identity AS jsonb))"
            ),
            {
                "i": uuid4(),
                "a": a.id,
                "identity": json.dumps(identity_dimensions(provider.identify(sym))),
            },
        )
    db_session.commit()
    settings = dict(svc.configuration(db_session, hid)["settings"])
    settings["targets"] = [
        dict(
            asset_id=str(a.id),
            weight=str(w),
            leverage_status="unleveraged",
            equity_exposure_pct="100",
        )
        for a, w in zip(assets, [50, 30, 10, 10])
    ]
    svc.configure(db_session, hid, settings)
    initial = svc.make_candidate(db_session, hid, funding="initial")["evidence"]
    assert initial["recommendation_ready"]
    assert D(initial["plan"]["post_value"]) == 100000
    assert sum(D(r["buy_amount"]) for r in initial["plan"]["rows"]) == 100000
    # Synthetic execution ledger for second case only; no actual Owner data touched.
    for a, value in zip(assets, [45000, 36000, 9000, 10000]):
        holding(
            Holding(
                account_id=account,
                asset_id=a.id,
                quantity=D(value) / 100,
                avg_cost=100,
                cost_currency="USD",
            ),
            db_session,
        )
    db_session.execute(
        text("UPDATE cash_balances SET amount=0 WHERE account_id=:a AND is_latest"), {"a": account}
    )
    db_session.commit()
    monthly = svc.make_candidate(db_session, hid)["evidence"]
    plan = monthly["plan"]
    assert monthly["recommendation_ready"]
    assert D(plan["portfolio_value"]) == 100000
    assert D(plan["new_capital"]) == 1400
    assert sum(D(r["buy_amount"]) for r in plan["rows"]) + D(plan["retained_cash"]) == 1400
    assert next(D(r["buy_amount"]) for r in plan["rows"] if r["symbol"] == "QQQ") == 0
    assert plan["execution"] == "MANUAL"
    print(
        "VERIFIED SYNTHETIC four-instrument initial 100000; CNY10000 at .14=1400; "
        "no QQQ sale; conservation. Explicit test policy max-position60, not Owner rule change."
    )


@pytest.mark.postgres
@pytest.mark.parametrize("setup", [{"max_position": "20"}], indirect=True)
def test_owner_example_does_not_override_published_twenty_percent_rule(db_session, setup):
    hid, _, _, _ = setup
    candidate = svc.make_candidate(db_session, hid, funding="initial")
    assert not candidate["evidence"]["recommendation_ready"]
    assert any(
        f["check"] == "concentration" and f["severity"] == "critical"
        for f in candidate["evidence"]["guardian"]["findings"]
    )
    with pytest.raises(ValueError):
        svc.preview_committee(db_session, hid, UUID(candidate["id"]))
