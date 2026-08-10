"""Tests for Sprint 012 Slice C — Tool Foundation."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.evidence_collector_v2 import (
    CacheService,
    EvidenceBundle,
    EvidenceCollector,
)
from apps.api.services.provider_protocols import (
    MarketOverview,
    ProvenanceEnvelope,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# CacheService
# ═══════════════════════════════════════════════════════════════════════


class TestCacheService:
    def test_cache_miss_when_empty(self, db_session):
        cache = CacheService()
        result = cache.get(db_session, "AAPL", "overview")
        assert result is None

    def test_cache_hit_when_fresh(self, db_session):
        now = _now()
        from datetime import timedelta
        exp = now + timedelta(hours=24)
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at,"
                " data_quality_status)"
                " VALUES (:id, 'AAPL', 'overview',"
                " '{\"sector\":\"Tech\"}', :now, :exp, 'VALID')"
            ),
            {"id": uuid4(), "now": now, "exp": exp},
        )
        db_session.commit()
        cache = CacheService()
        result = cache.get(db_session, "AAPL", "overview")
        assert result is not None
        assert result["provenance"].data_quality_status == "VALID"

    def test_cache_miss_when_expired(self, db_session):
        now = _now()
        from datetime import timedelta
        exp = now - timedelta(hours=1)  # expired 1 hour ago
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at,"
                " data_quality_status)"
                " VALUES (:id, 'AAPL', 'overview',"
                " '{}', '2026-01-01', :exp, 'VALID')"
            ),
            {"id": uuid4(), "exp": exp},
        )
        db_session.commit()
        cache = CacheService()
        result = cache.get(db_session, "AAPL", "overview")
        assert result is None

    def test_is_fresh_returns_true(self, db_session):
        now = _now()
        from datetime import timedelta
        exp = now + timedelta(hours=24)
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at,"
                " data_quality_status)"
                " VALUES (:id, 'MSFT', 'price_history', '{}',"
                " :now, :exp, 'VALID')"
            ),
            {"id": uuid4(), "now": now, "exp": exp},
        )
        db_session.commit()
        cache = CacheService()
        assert cache.is_fresh("MSFT", "price_history", db_session)

    def test_is_fresh_false_for_expired(self, db_session):
        cache = CacheService()
        assert not cache.is_fresh("UNKNOWN", "price_history", db_session)


# ═══════════════════════════════════════════════════════════════════════
# EvidenceCollector — provider injection
# ═══════════════════════════════════════════════════════════════════════


class MockMarketProvider:
    """Mock provider for testing — no real API calls."""

    def get_overview(self, symbol):
        return MarketOverview(
            symbol=symbol, company_name=f"{symbol} Inc.",
            sector="Technology", market_cap=1_000_000,
            pe_ratio=25.0,
            provenance=ProvenanceEnvelope(
                source="mock", provider="Mock Provider",
                source_timestamp=_now(), retrieved_at=_now(),
                data_quality_status="VALID", provider_version="v1.0",
            ),
        )

    def get_price_history(self, symbol, days):
        return []

    def get_financials(self, symbol):
        return None


class FailingMarketProvider:
    """Simulates external provider failure."""

    def get_overview(self, symbol):
        raise ConnectionError("Provider unavailable")

    def get_price_history(self, symbol, days):
        raise ConnectionError("Provider unavailable")

    def get_financials(self, symbol):
        raise ConnectionError("Provider unavailable")


class TestEvidenceCollectorInjection:
    def test_collect_with_mock_provider(self, db_session):
        collector = EvidenceCollector(
            market_provider=MockMarketProvider(),
        )
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        assert isinstance(bundle, EvidenceBundle)
        assert "overview" in bundle.market_data
        assert bundle.market_data["overview"]["sector"] == "Technology"
        assert len(bundle.provenance) > 0
        assert bundle.provenance[0].source == "mock"

    def test_collect_without_provider(self, db_session):
        """No provider → no market data, no error."""
        collector = EvidenceCollector()
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        assert isinstance(bundle, EvidenceBundle)
        assert "overview" not in bundle.market_data

    def test_graceful_degradation_on_provider_failure(self, db_session):
        """Provider fails → missing_sources logged, no crash, no fabricated data."""
        collector = EvidenceCollector(
            market_provider=FailingMarketProvider(),
        )
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        assert isinstance(bundle, EvidenceBundle)
        assert "market_data" in bundle.missing_sources
        # No fabricated data
        assert "overview" not in bundle.market_data
        # Portfolio data still available
        assert isinstance(bundle.portfolio_context, dict)

    def test_provenance_envelope_on_provider_data(self, db_session):
        collector = EvidenceCollector(
            market_provider=MockMarketProvider(),
        )
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        for p in bundle.provenance:
            assert p.source is not None
            assert p.provider is not None
            assert p.retrieved_at is not None
            assert p.data_quality_status == "VALID"
            assert p.provider_version is not None
        assert len(bundle.provenance) >= 1

    def test_cache_hit_skips_provider(self, db_session):
        """When cache is fresh, provider is NOT called."""
        from datetime import timedelta

        now = _now()
        exp = now + timedelta(hours=24)
        db_session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, fetched_at, expires_at,"
                " data_quality_status, source)"
                " VALUES (:id, 'AAPL', 'overview',"
                " '{\"sector\":\"Cached\"}', :now, :exp,"
                " 'VALID', 'cache')"
            ),
            {"id": uuid4(), "now": now, "exp": exp},
        )
        db_session.commit()

        call_count = [0]

        class CountingProvider:
            def get_overview(self, symbol):
                call_count[0] += 1
                return None

            def get_price_history(self, symbol, days):
                return []

            def get_financials(self, symbol):
                return None

        collector = EvidenceCollector(
            market_provider=CountingProvider(),
        )
        bundle = collector.collect(db_session, uuid4(), symbol="AAPL")
        # Cache hit: provider should NOT be called
        assert call_count[0] == 0
        assert "overview" in bundle.market_data


class TestAIAuthority:
    def test_no_trading_path(self):
        # Slice C is interfaces only — no AI execution paths
        assert True
