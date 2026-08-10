# Sprint 012 Slice C — Technical Design
# Tool Interface Foundation

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 012 Slice A (LLM Runtime): DONE (59d137e)
> Sprint 012 Slice B (Pipeline): DONE (b5444ac)
> Sprint 012 Slice C: DESIGN ONLY

---

## 1. Objective

Slice C defines clean provider abstraction interfaces that decouple the
research pipeline from specific data sources. This enables future growth:

- Today: mock providers (testing only)
- Sprint 013: real Alpha Vantage provider
- Sprint 014+: additional providers (Bloomberg, Refinitiv, etc.)

No real providers are implemented in Slice C. Only the interface
contracts and their integration points with the existing pipeline.

---

## 2. Provider Abstractions

### 2.1 MarketDataProvider

```python
class MarketDataProvider(Protocol):
    """External market data source. Alpha Vantage in Sprint 013."""

    def get_overview(self, symbol: str) -> MarketOverview | None: ...
    def get_financials(self, symbol: str) -> FinancialData | None: ...
    def get_price_history(
        self, symbol: str, days: int,
    ) -> list[PricePoint]: ...
    def get_sector_performance(
        self, sector: str,
    ) -> SectorPerformance | None: ...


@dataclass
class MarketOverview:
    symbol: str
    company_name: str
    sector: str
    market_cap: Decimal | None
    pe_ratio: Decimal | None
    dividend_yield: Decimal | None
    description: str


@dataclass
class FinancialData:
    symbol: str
    revenue: Decimal | None
    net_income: Decimal | None
    free_cash_flow: Decimal | None
    total_debt: Decimal | None
    fiscal_year: int
```

**Provenance**: Every response carries `source="alpha_vantage"`,
`retrieved_at`, and `source_timestamp` from the provider.

### 2.2 CompanyDataProvider

```python
class CompanyDataProvider(Protocol):
    """Company profile and fundamental data."""

    def get_profile(self, symbol: str) -> CompanyProfile | None: ...
    def get_competitors(self, symbol: str) -> list[str]: ...
    def get_earnings_calendar(
        self, symbol: str,
    ) -> list[EarningsEvent]: ...
```

### 2.3 KnowledgeProvider

```python
class KnowledgeProvider(Protocol):
    """Internal knowledge memory retrieval."""

    def get_entity_profile(
        self, entity_type: str, entity_key: str,
    ) -> dict | None: ...
    def get_historical_thesis(self, entity_key: str) -> list[dict]: ...
    def get_past_decisions(self, entity_key: str) -> list[dict]: ...
    def get_past_outcomes(self, entity_key: str) -> list[dict]: ...
    def get_prediction_accuracy(
        self, entity_key: str,
    ) -> dict | None: ...
```

### 2.4 DocumentProvider

```python
class DocumentProvider(Protocol):
    """Future: news, filings, research reports."""

    def search(self, query: str, limit: int = 5) -> list[Document]: ...
    def get_filing(self, symbol: str, form_type: str) -> Document | None: ...
```

---

## 3. Evidence Integration

### 3.1 Enhanced EvidenceCollector

The existing `EvidenceCollector` (Slice B) is extended to accept
provider injection:

```python
class EvidenceCollector:
    def __init__(
        self,
        market_provider: MarketDataProvider | None = None,
        knowledge_provider: KnowledgeProvider | None = None,
    ):
        self.market = market_provider
        self.knowledge = knowledge_provider

    def collect(self, session: Session, household_id: UUID,
                symbol: str | None = None) -> EvidenceBundle:
        bundle = EvidenceBundle()
        # Internal sources (always available)
        bundle.portfolio_context = self._load_portfolio(session, household_id)
        bundle.policy_context = self._load_policy(session, household_id)
        bundle.guardian_status = self._load_guardian(session, household_id)

        # Optional external sources
        if self.market and symbol:
            bundle.market_data = self._collect_market(symbol)
        if self.knowledge and symbol:
            bundle.knowledge_memory = self._collect_knowledge(symbol)

        return bundle
```

### 3.2 Provenance Requirement

Every evidence artifact from a provider MUST carry:

| Field | Source |
|---|---|
| `source` | Provider identifier (e.g. "alpha_vantage") |
| `retrieved_at` | When CompoundOS fetched it |
| `source_timestamp` | When the provider says the data is from |
| `data_quality_status` | VALID/STALE/FAILED/SUSPECT (from market_data_cache) |

---

## 4. Research Memory Integration

The `KnowledgeProvider` reads from `investment_knowledge_memory` table
(Sprint 011 Slice B) with fields:
- `entity_type` / `entity_key` — lookup key
- `profile` — company/sector profile
- `past_thesis` — historical investment theses
- `past_evidence` — evidence collected in past research
- `past_decisions` — decisions referencing this entity
- `past_outcomes` — outcome data from completed reviews
- `prediction_accuracy` — accuracy metrics

This enables the research pipeline to contextualize new analysis
with historical data — e.g., "Previously we analyzed AAPL in Q1 2026
with a BUY recommendation. 6 months later, the return was +12%."

---

## 5. Caching Strategy

### 5.1 market_data_cache Integration

All MarketDataProvider calls are routed through `market_data_cache`:

```
Pipeline requests data
        │
        ▼
Check market_data_cache (symbol, data_type)
        │
   ┌────┴────┐
   ▼         ▼
 Fresh    Stale/Not Found
   │         │
   │         ▼
   │    Call MarketDataProvider
   │         │
   │         ▼
   │    Store in cache
   │         │
   └────┬────┘
        ▼
   Return to pipeline
```

### 5.2 Freshness Rules

By data_type (from OD-12-12 and Sprint 011 TD):

| data_type | TTL |
|---|---|
| overview | 7 days |
| income_statement | 30 days |
| balance_sheet | 30 days |
| price_history | 6 hours |
| sector_performance | 30 days |

---

## 6. Database Impact

No new tables or columns. Slice C is pure interface/service layer
with no schema changes.

---

## 7. API Impact

No new API endpoints. Provider interfaces are consumed internally
by the ResearchPipeline.

---

## 8. Security

| Constraint | Enforcement |
|---|---|
| No credentials in code | API keys only via environment variables |
| No external calls in Slice C | Providers are Protocol definitions only |
| No broker integration | No broker interfaces defined |
| No trading capability | No trade methods in any interface |

---

## 9. Estimate

| Component | Lines | Tests |
|---|---|---|
| Provider Protocols | ~120 | 0 (type-checked, no logic) |
| Enhanced EvidenceCollector | ~40 | 3 |
| KnowledgeProvider impl | ~80 | 4 |
| Caching integration | ~60 | 3 |
| **Total** | **~300** | **~10** |

---

## 10. Owner Decisions

See `docs/sprints/SPRINT_012_SLICE_C_OWNER_DECISIONS.md` (5 pending).
