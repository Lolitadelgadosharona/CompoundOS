"""PE-003B.1 tests — Capital Allocation dashboard."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services import portfolio_reality
from apps.api.services.capital_allocation import capital_allocation

pytestmark = pytest.mark.postgres


def _setup_household(db_session):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement,"
        " notes, created_at, updated_at)"
        " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l', 'm', '', NOW(), NOW())"
        " ON CONFLICT (singleton_key) DO NOTHING"
    ), {"id": hh})
    db_session.commit()
    return hh


def _seed_policy(db_session):
    from apps.api.policy_schemas import PersonalPolicySetupRequest
    from apps.api.services.policies import setup_personal_policy

    setup_personal_policy(db_session, PersonalPolicySetupRequest(
        investment_goal="Long term wealth compounding",
        risk_preference="Growth",
        investment_horizon="10+ years",
        max_single_position_pct=15,
        min_cash_pct=10,
        principles="Focus on quality businesses",
    ))


def _seed_buckets(db_session):
    from apps.api.repositories.policy_enrichment import create_version_bucket
    from apps.api.services.policies import read_current_published

    version, _ = read_current_published(db_session)
    create_version_bucket(db_session, version.id, bucket_name="CORE",
                          target_pct=Decimal("90"), min_pct=Decimal("80"),
                          max_pct=Decimal("95"), sort_order=0)
    create_version_bucket(db_session, version.id, bucket_name="EXPLORATION",
                          target_pct=Decimal("10"), min_pct=Decimal("0"),
                          max_pct=Decimal("15"), sort_order=1)
    db_session.commit()


class TestCapitalAllocationPage:
    def test_page_renders(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/capital-allocation")
        assert r.status_code == 200
        assert "Capital Allocation" in r.text

    def test_empty_policy_graceful(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/capital-allocation")
        assert r.status_code == 200
        assert "No published Investment Policy" in r.text

    def test_no_secrets(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/capital-allocation")
        lower = r.text.lower()
        for secret in ("password", "token", "api_key", "sk-ss-v1"):
            assert secret not in lower


class TestCalculation:
    def test_capital_allocation_drift(self, db_session):
        _setup_household(db_session)
        _seed_policy(db_session)
        _seed_buckets(db_session)

        # Reality: CORE = 9000, EXPLORATION = 1000 (total 10000)
        core = portfolio_reality.add_account(
            db_session, name="Core", account_type="brokerage",
            capital_bucket="CORE", currency="USD",
        )
        portfolio_reality.add_holding(
            db_session, account_id=core["id"], symbol="NVDA",
            asset_type="STOCK", quantity="100", avg_cost="90",
        )
        explore = portfolio_reality.add_account(
            db_session, name="Explore", account_type="brokerage",
            capital_bucket="EXPLORATION", currency="USD",
        )
        portfolio_reality.add_holding(
            db_session, account_id=explore["id"], symbol="AAPL",
            asset_type="STOCK", quantity="10", avg_cost="100",
        )

        data = capital_allocation(db_session)
        assert data["policy_status"] == "published"

        core_b = [b for b in data["buckets"] if b["name"] == "CORE"][0]
        assert core_b["target_pct"] == 90.0
        assert core_b["current_pct"] == 90.0
        assert core_b["drift_pct"] == 0.0
        assert core_b["min_pct"] == 80.0
        assert core_b["max_pct"] == 95.0

        explore_b = [b for b in data["buckets"]
                     if b["name"] == "EXPLORATION"][0]
        assert explore_b["target_pct"] == 10.0
        assert explore_b["current_pct"] == 10.0
        assert explore_b["drift_pct"] == 0.0

    def test_no_buckets_graceful(self, db_session):
        _setup_household(db_session)
        _seed_policy(db_session)  # policy published, no buckets
        data = capital_allocation(db_session)
        assert data["policy_status"] == "no_buckets"
        assert data["buckets"] == []
