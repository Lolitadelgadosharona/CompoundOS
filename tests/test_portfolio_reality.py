"""PE-003A tests — Portfolio Reality foundation."""

from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.portfolio_foundation_schemas import (
    VALID_POSITION_SOURCES,
    VALID_SOURCE_TYPES,
)

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
    return db_session.execute(text(
        "SELECT id FROM household_profiles WHERE singleton_key = TRUE"
    )).fetchone()[0]


def _create_account(api_client, name="Schwab", account_type="brokerage",
                    bucket="CORE", currency="USD"):
    r = api_client.post("/api/portfolio/accounts", json={
        "name": name, "account_type": account_type,
        "capital_bucket": bucket, "currency": currency,
    })
    assert r.status_code == 201
    return r.json()["id"]


class TestPortfolioPage:
    def test_portfolio_page_renders(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/portfolio")
        assert r.status_code == 200
        assert "Wealth Summary" in r.text
        assert "Accounts" in r.text
        assert "Holdings" in r.text
        assert "Cash" in r.text

    def test_empty_portfolio_graceful(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/portfolio")
        assert r.status_code == 200
        assert "Not configured" in r.text
        assert "No accounts yet" in r.text
        assert "No holdings yet" in r.text

    def test_no_secrets_exposed(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.get("/portfolio")
        assert r.status_code == 200
        lower = r.text.lower()
        for secret in ("password", "token", "api_key", "secret", "sk-ss-v1"):
            assert secret not in lower


class TestAccountCreation:
    def test_create_account(self, api_client, db_session):
        _setup_household(db_session)
        r = api_client.post("/api/portfolio/accounts", json={
            "name": "Fidelity Brokerage", "account_type": "brokerage",
            "capital_bucket": "CORE", "currency": "USD",
        })
        assert r.status_code == 201
        assert r.json()["name"] == "Fidelity Brokerage"
        assert r.json()["capital_bucket"] == "CORE"
        r2 = api_client.get("/api/portfolio/accounts")
        names = [a["name"] for a in r2.json()["accounts"]]
        assert "Fidelity Brokerage" in names


class TestHoldingCreation:
    def test_create_holding(self, api_client, db_session):
        _setup_household(db_session)
        account_id = _create_account(api_client)
        r = api_client.post("/api/portfolio/holdings", json={
            "account_id": account_id, "symbol": "NVDA", "asset_type": "STOCK",
            "quantity": "100", "avg_cost": "120.50",
        })
        assert r.status_code == 201
        body = r.json()
        assert body["symbol"] == "NVDA"
        assert body["source"] == "manual"
        r2 = api_client.get("/api/portfolio/holdings")
        assert any(h["symbol"] == "NVDA" for h in r2.json()["holdings"])

    def test_holding_source_is_manual(self, api_client, db_session):
        _setup_household(db_session)
        account_id = _create_account(api_client)
        api_client.post("/api/portfolio/holdings", json={
            "account_id": account_id, "symbol": "AAPL", "asset_type": "STOCK",
            "quantity": "10", "avg_cost": "150",
        })
        row = db_session.execute(text(
            "SELECT source FROM positions WHERE is_latest = TRUE"
        )).fetchone()
        assert row[0] == "manual"


class TestCashCreation:
    def test_create_cash(self, api_client, db_session):
        _setup_household(db_session)
        account_id = _create_account(api_client, account_type="bank",
                                     bucket="CASH_RESERVE")
        r = api_client.post("/api/portfolio/cash", json={
            "account_id": account_id, "currency": "USD", "amount": "50000",
        })
        assert r.status_code == 201
        assert r.json()["source"] == "manual"
        r2 = api_client.get("/api/portfolio/cash")
        assert any(c["currency"] == "USD" for c in r2.json()["cash"])

    def test_cash_cny(self, api_client, db_session):
        _setup_household(db_session)
        account_id = _create_account(api_client, account_type="bank",
                                     bucket="CASH_RESERVE", currency="CNY")
        r = api_client.post("/api/portfolio/cash", json={
            "account_id": account_id, "currency": "CNY", "amount": "100000",
        })
        assert r.status_code == 201
        assert r.json()["currency"] == "CNY"


class TestWealthSummary:
    def test_wealth_summary_aggregates(self, api_client, db_session):
        _setup_household(db_session)
        account_id = _create_account(api_client)
        api_client.post("/api/portfolio/holdings", json={
            "account_id": account_id, "symbol": "NVDA", "asset_type": "STOCK",
            "quantity": "100", "avg_cost": "120",
        })
        api_client.post("/api/portfolio/cash", json={
            "account_id": account_id, "currency": "USD", "amount": "1000",
        })
        summary = api_client.get("/api/portfolio/wealth").json()
        assert summary["net_worth"] == "13000.00"   # 12000 + 1000
        assert summary["stocks"] == "12000.00"
        assert summary["cash"] == "1000.00"


class TestFutureBrokerCompatibility:
    def test_broker_sources_reserved(self):
        # Schema already reserves broker sources for future sync.
        assert "interactive_brokers" in VALID_POSITION_SOURCES
        assert "schwab" in VALID_POSITION_SOURCES
        assert "broker" in VALID_SOURCE_TYPES
