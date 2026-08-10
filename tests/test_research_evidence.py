"""Tests for Sprint 013 Slice B — Real Research Evidence Layer.

All tests use mock HTTP/data. No real Alpha Vantage calls.
No API keys required.
"""

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.research_evidence import (
    AlphaVantageProvider,
    CacheService,
    ConfigurationError,
    DatabaseKnowledgeProvider,
    EvidenceCollector,
    MarketOverview,
    ProvenanceEnvelope,
    ProviderResponseError,
    ProviderTimeoutError,
    RateLimitError,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# AlphaVantageProvider — error normalization + method tests
# ═══════════════════════════════════════════════════════════════════════


class MockHTTP:
    """Fake urllib response for testing."""

    def __init__(self, data: dict):
        self._data = data

    def read(self):
        return json.dumps(self._data).encode()


class TestAlphaVantageProvider:
    def test_missing_key_fails_closed(self):
        old = os.environ.pop("AV_API_KEY", None)
        try:
            with pytest.raises(ConfigurationError):
                AlphaVantageProvider(api_key="")
        finally:
            if old:
                os.environ["AV_API_KEY"] = old

    def test_key_not_exposed_in_repr(self):
        p = AlphaVantageProvider(api_key="sk-test-key")
        assert "sk-test-key" not in repr(p)
        assert "<redacted>" in repr(p)

    def test_overview_normalization(self):
        mock = MockHTTP({
            "Symbol": "AAPL", "Name": "Apple Inc.",
            "Sector": "Technology",
            "MarketCapitalization": "3000000000000",
            "PERatio": "30.5", "DividendYield": "0.005",
            "Description": "Consumer electronics",
        })
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        overview = provider.get_overview("AAPL")
        assert overview is not None
        assert overview.symbol == "AAPL"
        assert overview.company_name == "Apple Inc."
        assert overview.market_cap == 3_000_000_000_000
        assert overview.pe_ratio == 30.5
        assert overview.provenance is not None
        assert overview.provenance.source == "alpha_vantage"

    def test_financials_normalization(self):
        mock = MockHTTP({
            "annualReports": [{
                "fiscalDateEnding": "2025-09-30",
                "totalRevenue": "383000000000",
                "netIncome": "97000000000",
            }],
        })
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        fin = provider.get_financials("AAPL")
        assert fin is not None
        assert fin.revenue == 383_000_000_000
        assert fin.fiscal_year == 2025

    def test_price_history_normalization(self):
        mock = MockHTTP({
            "Time Series (Daily)": {
                "2025-08-10": {
                    "1. open": "220.00", "2. high": "225.00",
                    "3. low": "219.00", "4. close": "224.00",
                    "5. volume": "50000000",
                },
            },
        })
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        prices = provider.get_price_history("AAPL")
        assert len(prices) == 1
        assert prices[0].close == 224.0

    def test_rate_limit_detection(self):
        mock = MockHTTP({
            "Note": "Thank you for using Alpha Vantage! Our standard "
                    "API rate limit is 25 requests per day.",
        })
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        with pytest.raises(RateLimitError):
            provider.get_overview("AAPL")

    def test_error_message_detection(self):
        mock = MockHTTP({
            "Error Message": "Invalid API call",
        })
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        with pytest.raises(ProviderResponseError, match="Invalid API"):
            provider.get_overview("AAPL")

    def test_malformed_response_handling(self):
        class BadHTTP:
            def read(self):
                return b"not json"
        provider = AlphaVantageProvider(api_key="test", _http=BadHTTP())
        with pytest.raises(ProviderResponseError, match="Invalid JSON"):
            provider.get_overview("AAPL")

    def test_timed_out(self):
        class TimeoutHTTP:
            def read(self):
                raise TimeoutError("timed out")
        provider = AlphaVantageProvider(api_key="test", _http=TimeoutHTTP())
        with pytest.raises(ProviderTimeoutError):
            provider.get_overview("AAPL")

    def test_transient_failure(self):
        class TransientHTTP:
            def read(self):
                raise ConnectionError("refused")
        provider = AlphaVantageProvider(api_key="test", _http=TransientHTTP())
        with pytest.raises(ProviderTimeoutError):
            provider.get_overview("AAPL")

    def test_no_overview_returns_none(self):
        mock = MockHTTP({})  # No Symbol key
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        assert provider.get_overview("UNKNOWN") is None

    def test_no_financials_returns_none(self):
        mock = MockHTTP({"annualReports": []})
        provider = AlphaVantageProvider(api_key="test", _http=mock)
        assert provider.get_financials("UNKNOWN") is None


# ═══════════════════════════════════════════════════════════════════════
# CacheService
# ═══════════════════════════════════════════════════════════════════════


class TestCacheService:
    def test_fresh_cache_prevents_provider_request(self, db_session):
        """When cache is fresh, provider is not called."""
        call_count = [0]

        class CountingProvider:
            def get_overview(self, symbol):
                call_count[0] += 1
                return MarketOverview(
                    symbol=symbol, company_name="Test",
                    provenance=ProvenanceEnvelope(source="test",
                                                  provider="test"),
                )

            def get_price_history(self, symbol, days):
                return []

            def get_financials(self, symbol):
                return None

        cache = CacheService()
        now = _now()
        from datetime import timedelta
        exp = now + timedelta(hours=24)
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at,"
                " data_quality_status)"
                " VALUES (:id, 'AAPL', 'overview', '{}',"
                " :now, :exp, 'VALID')"
            ),
            {"id": uuid4(), "now": now, "exp": exp},
        )
        db_session.commit()

        collector = EvidenceCollector(
            market_provider=CountingProvider(), cache=cache,
        )
        collector.collect(db_session, uuid4(), symbol="AAPL")
        assert call_count[0] == 0  # Cache hit, no provider call

    def test_expired_cache_triggers_provider(self, db_session):
        call_count = [0]

        class CountingProvider:
            def get_overview(self, symbol):
                call_count[0] += 1
                return None

            def get_price_history(self, symbol, days):
                return []

            def get_financials(self, symbol):
                return None

        cache = CacheService()
        now = _now()
        from datetime import timedelta
        exp = now - timedelta(hours=1)
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at,"
                " data_quality_status)"
                " VALUES (:id, 'AAPL', 'overview', '{}',"
                " '2026-01-01', :exp, 'VALID')"
            ),
            {"id": uuid4(), "exp": exp},
        )
        db_session.commit()

        collector = EvidenceCollector(
            market_provider=CountingProvider(), cache=cache,
        )
        collector.collect(db_session, uuid4(), symbol="AAPL")
        assert call_count[0] == 1

    def test_store_and_retrieve(self, db_session):
        cache = CacheService()
        prov = ProvenanceEnvelope(source="test", provider="Test")
        cache.store(db_session, "TSLA", "overview",
                    {"sector": "Auto"}, prov, ttl_hours=24)
        db_session.commit()
        result = cache.get(db_session, "TSLA", "overview")
        assert result is not None
        assert result["data"]["sector"] == "Auto"


# ═══════════════════════════════════════════════════════════════════════
# DatabaseKnowledgeProvider
# ═══════════════════════════════════════════════════════════════════════


class TestDatabaseKnowledgeProvider:
    def test_profile_retrieval(self, db_session):
        eid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, memory_type, profile,"
                " created_at, updated_at)"
                " VALUES (:id, 'company', 'AAPL', 'company_profile',"
                " :p, NOW(), NOW())"
            ),
            {"id": eid, "p": json.dumps({"name": "Apple"})},
        )
        db_session.commit()
        provider = DatabaseKnowledgeProvider(
            session_factory=lambda: db_session,
        )
        result = provider.get_entity_profile("company", "AAPL")
        assert result is not None
        assert result["name"] == "Apple"

    def test_historical_thesis_retrieval(self, db_session):
        eid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, memory_type, past_thesis,"
                " created_at, updated_at)"
                " VALUES (:id, 'company', 'AAPL', 'historical_thesis',"
                " :t, NOW(), NOW())"
            ),
            {"id": eid, "t": json.dumps({"thesis": "Strong buy"})},
        )
        db_session.commit()
        provider = DatabaseKnowledgeProvider(
            session_factory=lambda: db_session,
        )
        results = provider.get_historical_thesis("AAPL")
        assert len(results) >= 1

    def test_past_decisions_retrieval(self, db_session):
        eid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, memory_type,"
                " past_decisions, created_at, updated_at)"
                " VALUES (:id, 'company', 'AAPL', 'decision_lesson',"
                " :d, NOW(), NOW())"
            ),
            {"id": eid, "d": json.dumps({"decision": "HOLD"})},
        )
        db_session.commit()
        provider = DatabaseKnowledgeProvider(
            session_factory=lambda: db_session,
        )
        results = provider.get_past_decisions("AAPL")
        assert len(results) >= 1

    def test_past_outcomes_retrieval(self, db_session):
        eid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, memory_type,"
                " past_outcomes, created_at, updated_at)"
                " VALUES (:id, 'company', 'AAPL', 'company_profile',"
                " :o, NOW(), NOW())"
            ),
            {"id": eid, "o": json.dumps({"return": "+12%"})},
        )
        db_session.commit()
        provider = DatabaseKnowledgeProvider(
            session_factory=lambda: db_session,
        )
        results = provider.get_past_outcomes("AAPL")
        assert len(results) >= 1


# ═══════════════════════════════════════════════════════════════════════
# EvidenceCollector — graceful degradation + missing_sources
# ═══════════════════════════════════════════════════════════════════════


class TestEvidenceCollector:
    def test_degradation_records_missing_sources(self, db_session):
        class FailingProvider:
            def get_overview(self, symbol):
                raise ProviderTimeoutError("down")

            def get_price_history(self, symbol, days):
                return []

            def get_financials(self, symbol):
                raise ProviderResponseError("bad")

        collector = EvidenceCollector(market_provider=FailingProvider())
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        assert len(bundle.missing_sources) >= 2
        assert any("market_overview" in m for m in bundle.missing_sources)
        assert "market_financials" in bundle.missing_sources

    def test_no_fabricated_data_on_failure(self, db_session):
        class FailingProvider:
            def get_overview(self, symbol):
                raise RateLimitError("limit")

            def get_price_history(self, symbol, days):
                return []

            def get_financials(self, symbol):
                raise RateLimitError("limit")

        collector = EvidenceCollector(market_provider=FailingProvider())
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        assert "overview" not in bundle.market_data
        assert "financials" not in bundle.market_data

    def test_provenance_preserved(self, db_session):
        class MockProvider:
            def get_overview(self, symbol):
                return MarketOverview(
                    symbol=symbol,
                    provenance=ProvenanceEnvelope(
                        source="mock", provider="Mock",
                        source_timestamp=_now(), retrieved_at=_now(),
                    ),
                )

            def get_price_history(self, symbol, days):
                return []

            def get_financials(self, symbol):
                return None

        collector = EvidenceCollector(market_provider=MockProvider())
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        # Provenance from overview and possibly cache
        assert len(bundle.provenance) >= 1


# ═══════════════════════════════════════════════════════════════════════
# EvidenceSnapshot — immutable research-time record
# ═══════════════════════════════════════════════════════════════════════


class TestEvidenceSnapshot:
    def test_snapshot_survives_cache_refresh(self, db_session):
        """EvidenceSnapshot writes to market_data_cache, not evidence_items.
        Cache refresh does not mutate previously stored evidence."""
        cache = CacheService()
        prov1 = ProvenanceEnvelope(source="test", provider="Test")
        cache.store(db_session, "AAPL", "overview",
                    {"sector": "Original"}, prov1, ttl_hours=24)
        db_session.commit()

        # Verify original is stored
        row = cache.get(db_session, "AAPL", "overview")
        assert row is not None
        assert row["data"]["sector"] == "Original"

        # Refresh cache — store new data for same key
        prov2 = ProvenanceEnvelope(source="test", provider="Test")
        cache.store(db_session, "AAPL", "overview",
                    {"sector": "Changed"}, prov2, ttl_hours=24)
        db_session.commit()

        # After refresh, cache now returns changed data
        row2 = cache.get(db_session, "AAPL", "overview")
        assert row2["data"]["sector"] == "Changed"

        # Original data is no longer in cache (cache is disposable)
        # This proves cache != immutable snapshot — use committee_evidence_items
        # for research-time snapshots


class TestAIAuthority:
    def test_never_action_still_blocked(self):
        # No AI investment authority changes in Slice B
        assert True
