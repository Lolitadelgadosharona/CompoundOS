# Sprint 013 Slice B — Technical Design
# Real Research Evidence Layer

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 013 Slice A (Real LLM Runtime): DONE (82bb43e, PR #94)
> Sprint 013 Slice B: DESIGN ONLY

---

## 1. Objective

Slice A proved CompoundOS can execute governed real LLM calls. Slice B
adds **real evidence** — connecting Alpha Vantage for market data and
wiring the knowledge memory for historical context. The research pipeline
will finally have real data flowing through it.

**Acceptance criteria**: A research run collects real market data from
Alpha Vantage, loads historical knowledge from internal memory, packages
both into a provenance-tracked evidence bundle, and feeds them into
the existing perspective execution pipeline.

---

## 2. Market Data Integration

### 2.1 AlphaVantageProvider

Implements `MarketDataProvider` Protocol from Sprint 012-C:

```python
class AlphaVantageProvider(MarketDataProvider):
    def __init__(self, api_key: str):
        self._key = api_key          # From AV_API_KEY env var
        self._base = "https://www.alphavantage.co/query"

    def get_overview(self, symbol: str) -> Optional[MarketOverview]: ...
    def get_price_history(self, symbol: str, days: int) -> list[PricePoint]: ...
    def get_financials(self, symbol: str) -> Optional[FinancialData]: ...
```

### 2.2 API Endpoints Used

| Method | AV Endpoint | Returns |
|---|---|---|
| `get_overview` | `OVERVIEW` | Symbol, Name, Description, Sector, MarketCap, PERatio, DividendYield |
| `get_financials` | `INCOME_STATEMENT` + `BALANCE_SHEET` + `CASH_FLOW` | Revenue, NetIncome, OperatingIncome, TotalAssets, TotalDebt |
| `get_price_history` | `TIME_SERIES_DAILY` | 100 daily OHLCV points |

### 2.3 Rate Limit Handling

Alpha Vantage free tier: **25 requests/day**. Rate limit exceeded →
HTTP 200 with `"Note": "Thank you for using Alpha Vantage! ... API
rate limit is 25 requests per day"` — no HTTP 429.

Detection strategy:
```python
def _handle_response(self, data: dict) -> None:
    if "Note" in data and "rate limit" in str(data["Note"]).lower():
        raise RateLimitError("Alpha Vantage daily limit reached")
```

### 2.4 Provenance

Every AV response wrapped in `ProvenanceEnvelope`:

| Field | Value |
|---|---|
| source | "alpha_vantage" |
| provider | "Alpha Vantage API" |
| source_timestamp | `LatestQuarter` from response |
| retrieved_at | datetime.utcnow() |
| data_quality_status | VALID (or FAILED on error) |
| provider_version | "v1.0" |

### 2.5 Credential Isolation

- Key from `AV_API_KEY` environment variable only
- `__init__` raises `ConfigurationError` if empty
- `__repr__` redacts: `"AlphaVantageProvider(api_key=<redacted>)"`

---

## 3. Company Data Integration

### 3.1 Overview + Fundamentals

`AlphaVantageProvider.get_overview()` returns `MarketOverview`:
- company_name, sector, market_cap, pe_ratio, dividend_yield, description

`AlphaVantageProvider.get_financials()` returns `FinancialData`:
- revenue, net_income, free_cash_flow, total_debt, fiscal_year

### 3.2 Data Freshness Rules (from OD-13-4)

| Data Type | TTL | Cache TTL |
|---|---|---|
| Price history | 6 hours | Stored in market_data_cache |
| Company overview | 7 days | Stored in market_data_cache |
| Income statement | 90 days | Stored in market_data_cache |
| Balance sheet | 90 days | Stored in market_data_cache |
| Cash flow | 90 days | Stored in market_data_cache |

Cache-before-provider: `CacheService` (Sprint 012-C) checks
`market_data_cache` before calling Alpha Vantage.

### 3.3 Source Attribution

Every `MarketOverview` and `FinancialData` carries `provenance:
ProvenanceEnvelope` with full source traceability.

---

## 4. Knowledge Memory Integration

### 4.1 KnowledgeProvider Implementation

Implements `KnowledgeProvider` Protocol from Sprint 012-C:

```python
class DatabaseKnowledgeProvider(KnowledgeProvider):
    def __init__(self, session_factory: Callable[[], Session]): ...

    def get_entity_profile(self, entity_type, entity_key) -> Optional[dict]:
        # SELECT profile FROM investment_knowledge_memory
        # WHERE entity_type = :et AND entity_key = :ek
        # AND memory_type = 'company_profile'

    def get_historical_thesis(self, entity_key) -> list[dict]:
        # SELECT past_thesis FROM investment_knowledge_memory
        # WHERE entity_key = :ek AND memory_type = 'historical_thesis'

    def get_past_decisions(self, entity_key) -> list[dict]:
        # SELECT past_decisions FROM investment_knowledge_memory

    def get_past_outcomes(self, entity_key) -> list[dict]:
        # SELECT past_outcomes FROM investment_knowledge_memory
```

### 4.2 Integration Flow

```
Research Pipeline starts run
        │
        ▼
EvidenceCollector.collect(session, household_id, symbol="AAPL")
        │
        ├── _load_portfolio()        — positions, accounts
        ├── _load_policy()            — policy_capital_buckets (deferred)
        ├── _load_guardian()          — guardian_events
        │
        ├── market_provider.get_overview("AAPL")     ← Alpha Vantage
        ├── market_provider.get_financials("AAPL")   ← Alpha Vantage
        └── knowledge_provider.get_entity_profile("company", "AAPL")
            knowledge_provider.get_historical_thesis("AAPL")
            knowledge_provider.get_past_decisions("AAPL")
            knowledge_provider.get_past_outcomes("AAPL")
```

### 4.3 Memory Updates

After a research run completes, the research pipeline (Slice D) will
feed results back into `investment_knowledge_memory`:
- Store the thesis and evidence
- Update after decision review completes
- Track prediction accuracy over time

This update path is NOT in Slice B scope.

---

## 5. Evidence Pipeline

### 5.1 Enhanced Flow

```
POST /api/research/start
        │
        ▼
ResearchPipeline._execute()
        │
        ▼
EvidenceCollector.collect(session, hid, symbol)
        │
   ┌────┼────────────────────┐
   ▼    ▼                    ▼
Internal              External API          Knowledge Memory
(portfolio,           (Alpha Vantage)       (Database)
 guardian)
   │    │                    │
   │    ▼                    ▼
   │  ProvenanceEnvelope   Direct DB read
   │    │                    │
   └────┼────────────────────┘
        ▼
   EvidenceBundle
   ├── portfolio_context
   ├── guardian_status
   ├── market_data (overview, financials, prices)
   ├── knowledge_memory (profile, thesis, decisions, outcomes)
   ├── missing_sources (logged on provider failure)
   └── provenance (list of ProvenanceEnvelope)
        │
        ▼
   PerspectiveExecutor.execute_all(evidence, ...)
```

### 5.2 EvidenceBundle Extension

```python
@dataclass
class EvidenceBundle:
    market_data: dict
    portfolio_context: dict
    policy_context: dict
    guardian_status: dict
    knowledge_memory: dict
    missing_sources: list[str]
    provenance: list[ProvenanceEnvelope]
```

### 5.3 CommitteeEvidenceItem Integration

External market data flows to `committee_evidence_items` for
immutable audit trail:

```python
# After evidence collection:
session.execute(text(
    "INSERT INTO committee_evidence_items"
    " (id, review_request_id, source_type, content, source_url,"
    " retrieved_at, source_timestamp, data_quality)"
    " VALUES (:id, :rrid, 'market_data', :content, :url,"
    " :retrieved, :source_ts, :quality)"
))
```

---

## 6. Data Quality

### 6.1 Quality Classification

| Status | Trigger | Confidence Impact |
|---|---|---|
| VALID | Successfully fetched, within TTL | None |
| STALE | In cache but TTL expired | Reduce evidence_quality by 25% |
| FAILED | Provider unreachable, no cached data | Record in missing_sources |
| SUSPECT | Provider returned unexpected format | Reduce evidence_quality by 50% |

### 6.2 Missing Data Handling

Provider unavailable:
- Log `missing_sources: ["market_data"]` in EvidenceBundle
- Continue with portfolio + guardian + knowledge data
- PerspectiveExecutor receives partial evidence
- ConfidenceEngine reduces evidence_quality score
- **Never fabricate data**

### 6.3 Confidence Impact

`ConfidenceEngine.calculate()` (Sprint 012-B) already accepts
`evidence: EvidenceBundle`. With real evidence:
- `evidence_quality` dimension (25% weight) is informed by actual
  source count, diversity, and freshness
- Missing market data → evidence_quality = 0
- Stale data → evidence_quality reduced proportionally

---

## 7. Database Impact

No new tables. Slice B uses existing:
- `market_data_cache` — caches Alpha Vantage responses
- `investment_knowledge_memory` — reads historical context
- `committee_evidence_items` — stores immutable evidence snapshots

---

## 8. API Impact

No new API endpoints. The existing `POST /api/research/start`
(Sprint 012-B) triggers the enhanced evidence collection.

---

## 9. Dependencies

Alpha Vantage does NOT require a Python SDK — it's a simple REST API.
Slice B adds no new package dependencies. Uses `requests` (already
available) or `httpx`.

---

## 10. Security

| Constraint | Enforcement |
|---|---|
| No API keys in code | `AV_API_KEY` env var only |
| No keys in database | Never stored |
| No keys in logs | Never logged |
| No broker integration | No broker code paths |
| No trading | No trade code paths |
| AI advisory only | PermissionGate (Sprint 012-D) |

---

## 11. Test Strategy

### 11.1 Mock Alpha Vantage

All tests use an `httpx` mock or a fake provider — never live AV API:

```python
class MockAlphaVantageProvider(MarketDataProvider):
    def get_overview(self, symbol):
        return MarketOverview(
            symbol=symbol, company_name=f"{symbol} Inc.",
            sector="Technology", market_cap=1_000_000,
            pe_ratio=25.0, provenance=...
        )
```

### 11.2 Test Coverage

| Test Area | Count |
|---|---|
| AlphaVantageProvider (mock HTTP) | 6 |
| DatabaseKnowledgeProvider | 4 |
| EvidenceCollector with real providers | 4 |
| Cache integration | 3 |
| Provenance | 3 |
| Graceful degradation | 3 |
| AI authority | 1 |
| **Total** | **~24** |

### 11.3 CI Safety

- No `AV_API_KEY` in CI environment
- All tests use mock providers
- No external HTTP calls

---

## 12. Estimate

| Component | Lines | Tests |
|---|---|---|
| AlphaVantageProvider | ~150 | 6 |
| DatabaseKnowledgeProvider | ~80 | 4 |
| EvidenceCollector V2 integration | ~60 | 4 |
| Cache + committee_evidence integration | ~50 | 3 |
| Provenance | ~30 | 3 |
| Graceful degradation | ~30 | 3 |
| Authority | ~10 | 1 |
| **Total** | **~410** | **~24** |

---

## 13. Owner Decisions

**No new Owner Decisions required.** Slice B is fully gated on
Sprint 013 Owner Decisions (all 8 approved):
- OD-13-3: Alpha Vantage V1 provider
- OD-13-4: Data freshness rules
- OD-13-6: Citation/provenance requirements
- OD-13-8: Graceful degradation

All architectural decisions for Slice B are resolved by prior
Owner approvals and the existing provider protocol design from
Sprint 012-C.
