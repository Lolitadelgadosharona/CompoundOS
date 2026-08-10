"""Enhanced Evidence Collector — Sprint 012 Slice C.

Provider injection, TTL cache abstraction, provenance envelope,
graceful degradation on external provider failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.provider_protocols import (
    CompanyDataProvider,
    KnowledgeProvider,
    MarketDataProvider,
    ProvenanceEnvelope,
)


@dataclass
class EvidenceBundle:
    """Collected evidence for a research run."""
    market_data: dict = field(default_factory=dict)
    portfolio_context: dict = field(default_factory=dict)
    policy_context: dict = field(default_factory=dict)
    guardian_status: dict = field(default_factory=dict)
    knowledge_memory: dict = field(default_factory=dict)
    missing_sources: list[str] = field(default_factory=list)
    provenance: list[ProvenanceEnvelope] = field(default_factory=list)


class CacheService:
    """TTL-based cache lookup via market_data_cache table."""

    # Per data_type freshness rules (OD-12-C-3)
    TTL_HOURS = {
        "price_history": 6,
        "news": 24,
        "overview": 168,           # 7 days
        "fundamentals": 720,       # 30 days
        "sector_performance": 720,
        "income_statement": 2160,  # 90 days
        "balance_sheet": 2160,
        "cash_flow": 2160,
    }

    def get(self, session: Session, symbol: str,
            data_type: str) -> Optional[dict]:
        """Look up cached data. Returns None if stale or missing."""
        row = session.execute(
            text(
                "SELECT data, source, source_timestamp, fetched_at,"
                " data_quality_status"
                " FROM market_data_cache"
                " WHERE symbol = :sym AND data_type = :dt"
                " AND expires_at > NOW()"
            ),
            {"sym": symbol, "dt": data_type},
        ).fetchone()
        if row is None:
            return None

        return {
            "data": row[0],
            "provenance": ProvenanceEnvelope(
                source=row[1] or "unknown",
                provider=row[1] or "unknown",
                source_timestamp=row[2],
                retrieved_at=row[3] or datetime.now(timezone.utc),
                data_quality_status=row[4] or "VALID",
                provider_version="v1.0",
            ),
        }

    def is_fresh(self, symbol: str, data_type: str,
                 session: Session) -> bool:
        """Check if cached data is within TTL."""
        ttl_hours = self.TTL_HOURS.get(data_type, 24)
        row = session.execute(
            text(
                "SELECT 1 FROM market_data_cache"
                " WHERE symbol = :sym AND data_type = :dt"
                " AND fetched_at > NOW() - make_interval(hours => :ttl)"
            ),
            {"sym": symbol, "dt": data_type, "ttl": ttl_hours},
        ).fetchone()
        return row is not None


class EvidenceCollector:
    """Enhanced collector with provider injection and graceful degradation."""

    def __init__(
        self,
        market_provider: Optional[MarketDataProvider] = None,
        company_provider: Optional[CompanyDataProvider] = None,
        knowledge_provider: Optional[KnowledgeProvider] = None,
        cache: Optional[CacheService] = None,
    ):
        self.market = market_provider
        self.company = company_provider
        self.knowledge = knowledge_provider
        self.cache = cache or CacheService()

    def collect(self, session: Session, household_id: UUID,
                symbol: Optional[str] = None) -> EvidenceBundle:
        bundle = EvidenceBundle()

        # Internal sources — always available
        bundle.portfolio_context = self._load_portfolio(session, household_id)
        bundle.policy_context = {}
        bundle.guardian_status = self._load_guardian(session, household_id)

        # External sources — graceful degradation
        if symbol:
            self._collect_market(session, symbol, bundle)
            self._collect_knowledge(session, symbol, bundle)

        return bundle

    def _collect_market(self, session: Session, symbol: str,
                        bundle: EvidenceBundle) -> None:
        """Collect market data. Cache hit → use. Cache miss → provider.
        Provider unavailable → graceful degradation (no fabrication).
        """
        if self.cache.is_fresh(symbol, "overview", session):
            cached = self.cache.get(session, symbol, "overview")
            if cached:
                bundle.market_data["overview"] = cached["data"]
                bundle.provenance.append(cached["provenance"])
                return

        if self.market:
            try:
                overview = self.market.get_overview(symbol)
                if overview and overview.provenance:
                    bundle.market_data["overview"] = {
                        "symbol": overview.symbol,
                        "company_name": overview.company_name,
                        "sector": overview.sector,
                        "market_cap": overview.market_cap,
                    }
                    bundle.provenance.append(overview.provenance)
            except Exception:
                bundle.missing_sources.append("market_data")

    def _collect_knowledge(self, session: Session, symbol: str,
                           bundle: EvidenceBundle) -> None:
        """Collect from knowledge memory. Internal — no failure possible."""
        if self.knowledge:
            try:
                profile = self.knowledge.get_entity_profile(
                    "company", symbol,
                )
                if profile:
                    bundle.knowledge_memory["profile"] = profile

                thesis = self.knowledge.get_historical_thesis(symbol)
                if thesis:
                    bundle.knowledge_memory["past_thesis"] = thesis

                decisions = self.knowledge.get_past_decisions(symbol)
                if decisions:
                    bundle.knowledge_memory["past_decisions"] = decisions

                outcomes = self.knowledge.get_past_outcomes(symbol)
                if outcomes:
                    bundle.knowledge_memory["past_outcomes"] = outcomes

            except Exception:
                bundle.missing_sources.append("knowledge_memory")

    def _load_portfolio(self, session: Session,
                        household_id: UUID) -> dict:
        rows = session.execute(
            text(
                "SELECT a.symbol, p.market_value, a.currency"
                " FROM positions p JOIN assets a ON p.asset_id = a.id"
                " JOIN accounts ac ON p.account_id = ac.id"
                " JOIN portfolios pf ON ac.portfolio_id = pf.id"
                " WHERE pf.household_id = :hid AND p.is_latest = TRUE"
            ),
            {"hid": household_id},
        ).fetchall()
        total = sum(r[1] for r in rows if r[1]) if rows else 0
        return {
            "total_value": str(total),
            "positions": [
                {"symbol": r[0], "value": str(r[1]), "currency": r[2]}
                for r in rows
            ],
        }

    def _load_guardian(self, session: Session,
                       household_id: UUID) -> dict:
        row = session.execute(
            text(
                "SELECT COUNT(*) FROM guardian_events"
                " WHERE household_id = :hid"
            ),
            {"hid": household_id},
        ).scalar()
        return {"active_events": row or 0}
