"""Real Research Evidence Layer — Sprint 013 Slice B.

AlphaVantageProvider (real market data), DatabaseKnowledgeProvider
(memory retrieval), error normalization, cache integration,
immutable evidence snapshots, graceful degradation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

# ═══════════════════════════════════════════════════════════════════════════
# CompoundOS-owned error categories — no raw provider exceptions leak
# ═══════════════════════════════════════════════════════════════════════════


class ConfigurationError(Exception):
    """Authentication/configuration failure (missing key)."""


class ProviderTimeoutError(Exception):
    """Timeout or network transient failure."""


class RateLimitError(Exception):
    """Provider rate limit exceeded."""


class ProviderResponseError(Exception):
    """Malformed or semantically invalid provider response."""


# ═══════════════════════════════════════════════════════════════════════════
# Data models
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ProvenanceEnvelope:
    source: str
    provider: str
    source_timestamp: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    data_quality_status: str = "VALID"
    provider_version: str = "v1.0"


@dataclass
class PricePoint:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class MarketOverview:
    symbol: str
    company_name: str = ""
    sector: str = ""
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    description: str = ""
    provenance: Optional[ProvenanceEnvelope] = None


@dataclass
class FinancialData:
    symbol: str
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    free_cash_flow: Optional[float] = None
    total_debt: Optional[float] = None
    fiscal_year: Optional[int] = None
    provenance: Optional[ProvenanceEnvelope] = None


@dataclass
class EvidenceBundle:
    market_data: dict = field(default_factory=dict)
    portfolio_context: dict = field(default_factory=dict)
    policy_context: dict = field(default_factory=dict)
    guardian_status: dict = field(default_factory=dict)
    knowledge_memory: dict = field(default_factory=dict)
    missing_sources: list[str] = field(default_factory=list)
    provenance: list[ProvenanceEnvelope] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# MarketDataProvider Protocol (aligned with Sprint 012-C)
# ═══════════════════════════════════════════════════════════════════════════


class MarketDataProvider(Protocol):
    def get_overview(self, symbol: str) -> Optional[MarketOverview]: ...
    def get_price_history(self, symbol: str, days: int) -> list[PricePoint]: ...
    def get_financials(self, symbol: str) -> Optional[FinancialData]: ...


class KnowledgeProvider(Protocol):
    def get_entity_profile(self, entity_type: str,
                           entity_key: str) -> Optional[dict]: ...
    def get_historical_thesis(self, entity_key: str) -> list[dict]: ...
    def get_past_decisions(self, entity_key: str) -> list[dict]: ...
    def get_past_outcomes(self, entity_key: str) -> list[dict]: ...


# ═══════════════════════════════════════════════════════════════════════════
# AlphaVantageProvider — real market data via REST API (no SDK coupling)
# ═══════════════════════════════════════════════════════════════════════════


class AlphaVantageProvider:
    """Alpha Vantage free tier. Plain HTTP, no SDK.

    Environment: AV_API_KEY. Fail closed if missing.
    """

    BASE = "https://www.alphavantage.co/query"
    TIMEOUT = 15

    def __init__(self, api_key: Optional[str] = None,
                 _http: Optional[object] = None):
        key = api_key or os.environ.get("AV_API_KEY", "")
        if not key:
            raise ConfigurationError("AV_API_KEY is required")
        self._key = key
        self._http = _http

    def _get(self, params: dict) -> dict:
        import urllib.parse
        import urllib.request
        params["apikey"] = self._key
        url = self.BASE + "?" + urllib.parse.urlencode(params)
        try:
            if self._http:
                return json.loads(self._http.read().decode())
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except json.JSONDecodeError:
            raise ProviderResponseError("Invalid JSON from Alpha Vantage")
        except (ProviderResponseError, ProviderTimeoutError,
                RateLimitError):
            raise
        except Exception as e:
            msg = str(e)
            if "timed out" in msg.lower():
                raise ProviderTimeoutError(
                    f"Alpha Vantage timeout: {msg[:80]}",
                )
            raise ProviderTimeoutError(
                f"Alpha Vantage request failed: {msg[:80]}",
            )

    def _check_response(self, data: dict) -> None:
        if "Note" in data:
            note = str(data["Note"]).lower()
            if "rate limit" in note or "api call frequency" in note:
                raise RateLimitError("Alpha Vantage daily limit reached")
        if "Error Message" in data:
            raise ProviderResponseError(
                f"Alpha Vantage error: {data['Error Message'][:200]}",
            )

    def get_overview(self, symbol: str) -> Optional[MarketOverview]:
        data = self._get({"function": "OVERVIEW", "symbol": symbol})
        self._check_response(data)
        if not data or "Symbol" not in data:
            return None
        now = datetime.now(timezone.utc)
        return MarketOverview(
            symbol=data.get("Symbol", symbol),
            company_name=data.get("Name", ""),
            sector=data.get("Sector", ""),
            market_cap=_float(data, "MarketCapitalization"),
            pe_ratio=_float(data, "PERatio"),
            dividend_yield=_float(data, "DividendYield"),
            description=data.get("Description", ""),
            provenance=ProvenanceEnvelope(
                source="alpha_vantage", provider="Alpha Vantage API",
                source_timestamp=now, retrieved_at=now,
            ),
        )

    def get_price_history(self, symbol: str,
                          days: int = 100) -> list[PricePoint]:
        data = self._get({
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol, "outputsize": "compact",
        })
        self._check_response(data)
        series = data.get("Time Series (Daily)", {})
        if not series:
            return []
        results = []
        for date_str, values in sorted(series.items(),
                                       reverse=True)[:days]:
            try:
                results.append(PricePoint(
                    date=datetime.strptime(date_str, "%Y-%m-%d"),
                    open=float(values["1. open"]),
                    high=float(values["2. high"]),
                    low=float(values["3. low"]),
                    close=float(values["4. close"]),
                    volume=int(values["5. volume"]),
                ))
            except (KeyError, ValueError):
                continue
        return results

    def get_financials(self, symbol: str) -> Optional[FinancialData]:
        data = self._get({
            "function": "INCOME_STATEMENT", "symbol": symbol,
        })
        self._check_response(data)
        reports = data.get("annualReports", [])
        if not reports:
            return None
        latest = reports[0]
        now = datetime.now(timezone.utc)
        return FinancialData(
            symbol=symbol,
            revenue=_float(latest, "totalRevenue"),
            net_income=_float(latest, "netIncome"),
            free_cash_flow=None,  # Requires separate CASH_FLOW call
            total_debt=None,      # Requires separate BALANCE_SHEET call
            fiscal_year=_int(latest, "fiscalDateEnding", 4),
            provenance=ProvenanceEnvelope(
                source="alpha_vantage", provider="Alpha Vantage API",
                source_timestamp=now, retrieved_at=now,
            ),
        )

    def __repr__(self) -> str:
        return "AlphaVantageProvider(api_key=<redacted>)"


def _float(data: dict, key: str) -> Optional[float]:
    try:
        v = data.get(key)
        return float(v) if v and v != "None" else None
    except (ValueError, TypeError):
        return None


def _int(data: dict, key: str, chars: int = 4) -> Optional[int]:
    try:
        v = data.get(key, "")
        return int(str(v)[:chars]) if v else None
    except (ValueError, TypeError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# DatabaseKnowledgeProvider — reads investment_knowledge_memory
# ═══════════════════════════════════════════════════════════════════════════


class DatabaseKnowledgeProvider:
    """Reads from investment_knowledge_memory. Read only.

    AI must not mutate prediction_accuracy or historical records.
    """

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    def get_entity_profile(self, entity_type: str,
                           entity_key: str) -> Optional[dict]:
        with self._session_factory() as s:
            row = s.execute(
                text(
                    "SELECT profile FROM investment_knowledge_memory"
                    " WHERE entity_type = :et AND entity_key = :ek"
                    " AND memory_type = 'company_profile'"
                    " ORDER BY updated_at DESC LIMIT 1"
                ),
                {"et": entity_type, "ek": entity_key},
            ).fetchone()
            return row[0] if row else None

    def get_historical_thesis(self, entity_key: str) -> list[dict]:
        with self._session_factory() as s:
            rows = s.execute(
                text(
                    "SELECT past_thesis FROM investment_knowledge_memory"
                    " WHERE entity_key = :ek"
                    " AND memory_type = 'historical_thesis'"
                    " ORDER BY updated_at DESC LIMIT 5"
                ),
                {"ek": entity_key},
            ).fetchall()
            return [r[0] for r in rows if r[0]]

    def get_past_decisions(self, entity_key: str) -> list[dict]:
        with self._session_factory() as s:
            rows = s.execute(
                text(
                    "SELECT past_decisions FROM investment_knowledge_memory"
                    " WHERE entity_key = :ek"
                    " AND memory_type = 'decision_lesson'"
                    " ORDER BY updated_at DESC LIMIT 5"
                ),
                {"ek": entity_key},
            ).fetchall()
            return [r[0] for r in rows if r[0]]

    def get_past_outcomes(self, entity_key: str) -> list[dict]:
        with self._session_factory() as s:
            rows = s.execute(
                text(
                    "SELECT past_outcomes FROM investment_knowledge_memory"
                    " WHERE entity_key = :ek"
                    " ORDER BY updated_at DESC LIMIT 5"
                ),
                {"ek": entity_key},
            ).fetchall()
            return [r[0] for r in rows if r[0]]


# ═══════════════════════════════════════════════════════════════════════════
# Cache abstraction for market_data_cache
# ═══════════════════════════════════════════════════════════════════════════


class CacheService:
    """TTL-based cache via market_data_cache. Refreshable/disposable."""

    TTL_HOURS = {
        "price_history": 6,
        "overview": 168,
        "fundamentals": 720,
        "income_statement": 2160,
    }

    def get(self, session: Session, symbol: str,
            data_type: str) -> Optional[dict]:
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
        return {"data": row[0],
                "provenance": ProvenanceEnvelope(
                    source=row[1] or "cache",
                    provider=row[1] or "cache",
                    source_timestamp=row[2],
                    retrieved_at=row[3] or datetime.now(timezone.utc),
                    data_quality_status=row[4] or "VALID",
                )}

    def is_fresh(self, session: Session, symbol: str,
                 data_type: str) -> bool:
        ttl = self.TTL_HOURS.get(data_type, 24)
        row = session.execute(
            text(
                "SELECT 1 FROM market_data_cache"
                " WHERE symbol = :sym AND data_type = :dt"
                " AND fetched_at > NOW() - make_interval(hours => :ttl)"
            ),
            {"sym": symbol, "dt": data_type, "ttl": ttl},
        ).fetchone()
        return row is not None

    def store(self, session: Session, symbol: str, data_type: str,
              data: dict, provenance: ProvenanceEnvelope,
              ttl_hours: int = 168) -> None:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires = now + timedelta(hours=ttl_hours)
        session.execute(
            text(
                "INSERT INTO market_data_cache"
                " (id, symbol, data_type, data, source,"
                " source_timestamp, fetched_at, expires_at,"
                " data_quality_status)"
                " VALUES (:id, :sym, :dt, :data, :src,"
                " :sts, :now, :exp, :dqs)"
                " ON CONFLICT (symbol, data_type) DO UPDATE SET"
                " data = EXCLUDED.data,"
                " source = EXCLUDED.source,"
                " source_timestamp = EXCLUDED.source_timestamp,"
                " fetched_at = EXCLUDED.fetched_at,"
                " expires_at = EXCLUDED.expires_at,"
                " data_quality_status = EXCLUDED.data_quality_status"
            ),
            {
                "id": uuid4(), "sym": symbol, "dt": data_type,
                "data": json.dumps(data), "src": provenance.source,
                "sts": provenance.source_timestamp or now,
                "now": now, "exp": expires,
                "dqs": provenance.data_quality_status,
            },
        )


# ═══════════════════════════════════════════════════════════════════════════
# EvidenceCollector — integrates real providers
# ═══════════════════════════════════════════════════════════════════════════


class EvidenceCollector:
    """Collects evidence from internal DB, Alpha Vantage, and knowledge
    memory. Graceful degradation on external failure."""

    def __init__(
        self,
        market_provider: Optional[MarketDataProvider] = None,
        knowledge_provider: Optional[KnowledgeProvider] = None,
        cache: Optional[CacheService] = None,
    ):
        self.market = market_provider
        self.knowledge = knowledge_provider
        self.cache = cache or CacheService()

    def collect(self, session: Session, household_id: UUID,
                symbol: Optional[str] = None) -> EvidenceBundle:
        bundle = EvidenceBundle()
        bundle.portfolio_context = self._load_portfolio(session,
                                                        household_id)
        bundle.guardian_status = self._load_guardian(session,
                                                     household_id)

        if symbol:
            self._collect_market(session, symbol, bundle)
            self._collect_knowledge(symbol, bundle)

        return bundle

    def _collect_market(self, session: Session, symbol: str,
                        bundle: EvidenceBundle) -> None:
        if not self.market:
            return

        # Overview
        try:
            if not self.cache.is_fresh(session, symbol, "overview"):
                overview = self.market.get_overview(symbol)
                if overview and overview.provenance:
                    self.cache.store(session, symbol, "overview",
                                     {"sector": overview.sector,
                                      "company_name": overview.company_name},
                                     overview.provenance,
                                     ttl_hours=168)
                    bundle.market_data["overview"] = {
                        "sector": overview.sector,
                        "company_name": overview.company_name,
                        "market_cap": overview.market_cap,
                        "pe_ratio": overview.pe_ratio,
                    }
                    bundle.provenance.append(overview.provenance)
            else:
                cached = self.cache.get(session, symbol, "overview")
                if cached:
                    bundle.market_data["overview"] = cached["data"]
                    bundle.provenance.append(cached["provenance"])
                    return
        except (ProviderTimeoutError, RateLimitError,
                ProviderResponseError) as e:
            bundle.missing_sources.append(
                f"market_overview:{type(e).__name__}",
            )

        # Financials
        try:
            financials = self.market.get_financials(symbol)
            if financials and financials.provenance:
                bundle.market_data["financials"] = {
                    "revenue": financials.revenue,
                    "net_income": financials.net_income,
                    "fiscal_year": financials.fiscal_year,
                }
                bundle.provenance.append(financials.provenance)
        except (ProviderTimeoutError, RateLimitError,
                ProviderResponseError):
            bundle.missing_sources.append("market_financials")

    def _collect_knowledge(self, symbol: str,
                           bundle: EvidenceBundle) -> None:
        if not self.knowledge:
            return
        try:
            profile = self.knowledge.get_entity_profile("company", symbol)
            if profile:
                bundle.knowledge_memory["profile"] = profile
        except Exception:
            bundle.missing_sources.append("knowledge_profile")

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
            text("SELECT COUNT(*) FROM guardian_events"
                 " WHERE household_id = :hid"),
            {"hid": household_id},
        ).scalar()
        return {"active_events": row or 0}


# ═══════════════════════════════════════════════════════════════════════════
# Evidence snapshot — immutable research-time record
# ═══════════════════════════════════════════════════════════════════════════


class EvidenceSnapshot:
    """Persist evidence used by a ResearchRun into committee_evidence_items.
    Once attached, cache refreshes MUST NOT mutate the snapshot."""

    @staticmethod
    def snapshot(session: Session, session_id: UUID,
                 bundle: EvidenceBundle) -> int:
        """Store evidence bundle as committee_evidence_items rows.
        Returns count of rows inserted."""
        count = 0
        now = datetime.now(timezone.utc)

        # Market overview
        if "overview" in bundle.market_data:
            session.execute(
                text(
                    "INSERT INTO committee_evidence_items"
                    " (id, session_id, source_type, content,"
                    " retrieved_at, data_quality)"
                    " VALUES (:id, :sid, 'market_data', :content,"
                    " :now, :dq)"
                ),
                {
                    "id": uuid4(), "sid": session_id,
                    "content": json.dumps(bundle.market_data["overview"]),
                    "now": now, "dq": "VALID",
                },
            )
            count += 1

        # Financials
        if "financials" in bundle.market_data:
            session.execute(
                text(
                    "INSERT INTO committee_evidence_items"
                    " (id, session_id, source_type, content,"
                    " retrieved_at, data_quality)"
                    " VALUES (:id, :sid, 'financial_data', :content,"
                    " :now, :dq)"
                ),
                {
                    "id": uuid4(), "sid": session_id,
                    "content": json.dumps(bundle.market_data["financials"]),
                    "now": now, "dq": "VALID",
                },
            )
            count += 1

        return count
