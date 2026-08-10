"""Provider abstraction layer — Sprint 012 Slice C.

Protocol-based interfaces. No SDK coupling. No external API clients.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

# ═══════════════════════════════════════════════════════════════════════════
# Evidence provenance envelope — mandatory per OD-12-C-4
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ProvenanceEnvelope:
    """Mandatory provenance for every evidence artifact."""
    source: str              # "alpha_vantage", "knowledge_memory", etc.
    provider: str            # "Alpha Vantage API v2"
    source_timestamp: Optional[datetime]  # When provider says data is from
    retrieved_at: datetime   # When CompoundOS fetched it
    data_quality_status: str  # VALID/STALE/FAILED/SUSPECT
    provider_version: str    # "v2.0"


# ═══════════════════════════════════════════════════════════════════════════
# Provider data models
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class MarketOverview:
    symbol: str
    company_name: str
    sector: str
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    description: str = ""
    provenance: Optional[ProvenanceEnvelope] = None


@dataclass
class PricePoint:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class FinancialData:
    symbol: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    free_cash_flow: Optional[float] = None
    total_debt: Optional[float] = None
    fiscal_year: int = 2026
    provenance: Optional[ProvenanceEnvelope] = None


@dataclass
class CompanyProfile:
    symbol: str
    company_name: str
    sector: str
    industry: str
    description: str = ""
    employees: Optional[int] = None
    founded: Optional[int] = None
    provenance: Optional[ProvenanceEnvelope] = None


@dataclass
class Document:
    id: str
    title: str
    content: str
    source: str
    published_at: Optional[datetime] = None
    provenance: Optional[ProvenanceEnvelope] = None


# ═══════════════════════════════════════════════════════════════════════════
# Provider protocols
# ═══════════════════════════════════════════════════════════════════════════


class MarketDataProvider(Protocol):
    """External market data source (Alpha Vantage in Sprint 013+)."""

    def get_overview(self, symbol: str) -> Optional[MarketOverview]:
        ...

    def get_price_history(
        self, symbol: str, days: int,
    ) -> list[PricePoint]:
        ...

    def get_financials(self, symbol: str) -> Optional[FinancialData]:
        ...


class CompanyDataProvider(Protocol):
    """Company profile and fundamental data."""

    def get_profile(self, symbol: str) -> Optional[CompanyProfile]:
        ...


class KnowledgeProvider(Protocol):
    """Internal knowledge memory retrieval."""

    def get_entity_profile(
        self, entity_type: str, entity_key: str,
    ) -> Optional[dict]:
        ...

    def get_historical_thesis(self, entity_key: str) -> list[dict]:
        ...

    def get_past_decisions(self, entity_key: str) -> list[dict]:
        ...

    def get_past_outcomes(self, entity_key: str) -> list[dict]:
        ...


class DocumentProvider(Protocol):
    """Future: news, filings, research reports."""

    def search(self, query: str, limit: int = 5) -> list[Document]:
        ...
