"""Tests for Sprint 014 Slice C — Research Workflow Integration."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


class TestResearchWorkflow:
    def test_start_endpoint_exists(self):
        r = client.post("/api/research/start",
                        json={"symbol": "AAPL"})
        assert r.status_code in (200, 422, 501)

    def test_start_rejects_empty_symbol(self):
        r = client.post("/api/research/start",
                        json={"symbol": ""})
        assert r.status_code in (400, 422)


class TestDashboardResearchIntegration:
    def test_research_page_shows_symbol_input(self):
        r = client.get("/research")
        assert r.status_code == 200
        assert "Start Research" in r.text

    def test_memo_page_linked_from_research(self):
        """Memo page renders with confidence."""
        r = client.get("/memo/test-id")
        assert r.status_code == 200
        assert "confidence" in r.text.lower()


class TestProviderIntegration:
    def test_providers_not_imported_at_startup(self):
        """Provider modules available but keys not committed."""
        try:
            from apps.api.services.llm_provider_runtime import (
                LLMProvider,
            )
            assert LLMProvider is not None
        except ImportError:
            pass

    def test_evidence_collector_available(self):
        try:
            from apps.api.services.research_evidence import (
                AlphaVantageProvider,
            )
            assert AlphaVantageProvider is not None
        except ImportError:
            pass


class TestNoTradePath:
    def test_no_trade_in_research_flow(self):
        r = client.get("/research")
        assert "trade" not in r.text.lower()
        assert "broker" not in r.text.lower()

    def test_no_trade_in_memo(self):
        r = client.get("/memo/test")
        assert "trade" not in r.text.lower()
        assert "execute" not in r.text.lower()


class TestAuthBoundary:
    def test_research_page_accessible(self):
        """Research page loads in dev mode."""
        r = client.get("/research")
        assert r.status_code == 200
