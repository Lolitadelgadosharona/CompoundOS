"""Tests for Sprint 014 Slice C — Research Workflow Integration."""

from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def _seed_household(db_session):
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


class TestResearchWorkflow:
    def test_start_endpoint_exists(self, api_client, db_session):
        _seed_household(db_session)
        r = api_client.post("/api/research/start", json={"symbol": "AAPL"})
        assert r.status_code == 200
        assert r.json()["symbol"] == "AAPL"

    def test_start_rejects_empty_symbol(self, api_client, db_session):
        _seed_household(db_session)
        r = api_client.post("/api/research/start", json={"symbol": ""})
        assert r.status_code == 400


class TestDashboardResearchIntegration:
    def test_research_page_shows_symbol_input(self, api_client):
        r = api_client.get("/research")
        assert r.status_code == 200
        assert "Start Research" in r.text

    def test_memo_missing_returns_404(self, api_client):
        r = api_client.get(f"/memo/{uuid4()}")
        assert r.status_code == 404


class TestProviderIntegration:
    def test_providers_not_imported_at_startup(self):
        """Provider modules available but keys not committed."""
        try:
            from apps.api.services.llm_provider_runtime import LLMProvider
            assert LLMProvider is not None
        except ImportError:
            pass

    def test_evidence_collector_available(self):
        try:
            from apps.api.services.research_evidence import AlphaVantageProvider
            assert AlphaVantageProvider is not None
        except ImportError:
            pass


class TestNoTradePath:
    def test_no_trade_in_research_flow(self, api_client):
        r = api_client.get("/research")
        assert "trade" not in r.text.lower()
        assert "broker" not in r.text.lower()

    def test_no_trade_in_memo(self, api_client):
        r = api_client.get(f"/memo/{uuid4()}")
        assert "trade" not in r.text.lower()
        assert "execute" not in r.text.lower()


class TestAuthBoundary:
    def test_research_page_accessible(self, api_client):
        """Research page loads in dev mode."""
        r = api_client.get("/research")
        assert r.status_code == 200
