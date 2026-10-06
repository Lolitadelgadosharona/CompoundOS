"""Idempotent seed, confined to a newly named preview database. No live migration."""

from datetime import datetime, timezone
from decimal import Decimal as D
from uuid import uuid4

from sqlalchemy import text

from apps.api.database import SessionLocal
from apps.api.models import HouseholdProfile, InvestmentPolicy, InvestmentPolicyVersion, PolicyRule
from apps.api.repositories.portfolio_foundation import create_position
from apps.api.services import launch_investment as svc
from apps.api.services.instrument_resolver import canonical_asset
from apps.api.services.owner_preview import require_preview
from apps.api.services.portfolio_reality import add_account, add_cash
from apps.api.services.preview_providers import DemoProvider


def seed():
    require_preview()
    with SessionLocal() as s:
        # Only preview-local schema supports DEMO enum; production migrations untouched.
        for table in ["market_observations", "fx_rates"]:
            names = (
                s.execute(
                    text(
                        "SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:t) "
                        "AND contype='c' AND pg_get_constraintdef(oid) LIKE '%quality%'"
                    ),
                    {"t": table},
                )
                .scalars()
                .all()
            )
            for name in names:
                s.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT "{name}"'))
            s.execute(
                text(
                    f"ALTER TABLE {table} ADD CONSTRAINT {table}_preview_quality "
                    "CHECK(quality IN ('OBSERVED','DELAYED','DEMO'))"
                )
            )
        s.commit()
        if s.query(HouseholdProfile).count():
            if (
                not s.query(HouseholdProfile)
                .first()
                .household_name.startswith("Owner Preview Household")
            ):
                raise RuntimeError("Refusing non-preview household")
            print("Existing preview data retained; no reseed")
            return
        now = datetime.now(timezone.utc)
        h = HouseholdProfile(
            id=uuid4(),
            household_name="Owner Preview Household — DEMO DATA",
            base_currency="USD",
            notes="SIMULATED. No real investment recommendation; no trades.",
        )
        s.add(h)
        s.flush()
        p = InvestmentPolicy(id=uuid4(), household_id=h.id)
        s.add(p)
        s.flush()
        v = InvestmentPolicyVersion(
            id=uuid4(),
            policy_id=p.id,
            version_number=1,
            status="published",
            objectives="DEMO only",
            time_horizon="long",
            liquidity="DEMO",
            diversification="Existing concentration rule",
            contribution_policy="DEMO monthly",
            rebalancing_policy="contribution first",
            prohibited_assets="[]",
            leverage_policy="No leverage",
            decision_process="Preview Owner",
            notes="DEMO only; existing 20% position rule",
            published_at=now,
        )
        s.add(v)
        s.flush()
        s.add(
            PolicyRule(
                id=uuid4(),
                version_id=v.id,
                rule_type="max_single_position_pct",
                rule_value="20",
                severity="critical",
                enabled=True,
                sort_order=0,
            )
        )
        s.flush()
        v.sealed_at = now
        s.commit()
        aid = add_account(
            s,
            name="DEMO Portfolio — no broker",
            account_type="brokerage",
            capital_bucket="CORE",
            currency="USD",
        )["id"]
        from uuid import UUID

        aid = UUID(aid)
        add_cash(s, account_id=aid, currency="USD", amount=D(0))
        add_cash(s, account_id=aid, currency="CNY", amount=D(10000))
        provider = DemoProvider()
        assets = {}
        for symbol in provider.catalog:
            a = canonical_asset(s, provider.identify(symbol))
            assets[symbol] = a
            if symbol != "BRK.B":
                price = D(provider.catalog[symbol][2])
                create_position(
                    s,
                    account_id=aid,
                    asset_id=a.id,
                    quantity=D(20000) / price,
                    quantity_source="compoundos_derived",
                    avg_cost=price,
                    avg_cost_currency="USD",
                    avg_cost_source="manual",
                    market_price=price,
                    market_price_currency="USD",
                    market_price_as_of=now,
                    source="compoundos_derived",
                    observed_at=now,
                    is_latest=True,
                )
        s.commit()
        svc.configure(
            s,
            h.id,
            {
                "base_currency": "USD",
                "monthly_currency": "CNY",
                "monthly_amount": "10000",
                "initial_capital": "100000",
                "funding_account_id": str(aid),
                "targets": [
                    {
                        "asset_id": str(assets[x].id),
                        "weight": weight,
                        "leverage_status": "unleveraged",
                        "equity_exposure_pct": "0" if x == "SGOV" else "100",
                    }
                    for x, weight in [("VTI", "50"), ("QQQ", "30"), ("VXUS", "10"), ("SGOV", "10")]
                ],
            },
        )
        svc.refresh_data(s, h.id)
        print("DEMO seeded: 100k USD + CNY10k; targets50/30/10/10 expected Policy block")


if __name__ == "__main__":
    seed()
