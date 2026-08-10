# Sprint 013 — Technical Design
# First Real Investment Intelligence

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 012: COMPLETE (Slices A-D all done)
> Sprint 013: DESIGN ONLY
>
> Sprint 013 is the first sprint to connect CompoundOS to real LLM and market
> data providers. Every prior sprint built infrastructure. Sprint 013 delivers
> the first end-to-end AI investment analysis with real data and real models.

---

## 1. Objective

Deliver the first fully-automated AI investment research workflow that:
1. Fetches real market data from an external provider
2. Executes LLM perspective analysis with a real model
3. Generates a structured investment memo
4. Preserves full provenance and audit trail
5. Never exceeds its advisory mandate

---

## 2. Real LLM Provider Architecture

### 2.1 Provider Interface (exists — Slice C)

The `MarketDataProvider` Protocol from Sprint 012-C is reused. Sprint 013
adds concrete implementations.

### 2.2 Provider Implementations

| Provider | Implementation | Model | Purpose |
|---|---|---|---|
| OpenAI | `OpenAIProvider` | gpt-4o | Macro analysis, Portfolio Construction |
| Anthropic | `ClaudeProvider` | claude-sonnet-4 | Value, Growth, Risk, Policy perspectives |
| Google | `GeminiProvider` | gemini-2.5-pro | Synthesis/committee memo generation |

### 2.3 Model Routing Strategy

Map perspectives to models (from Sprint 012-B):

| Perspective | Model | Rationale |
|---|---|---|
| Value | claude-sonnet-4 | Strong financial reasoning |
| Growth | claude-sonnet-4 | Consistent with Value perspective |
| Risk | claude-sonnet-4 | Risk analysis benefits from structured reasoning |
| Macro | gpt-4o | Broad economic synthesis |
| Policy | claude-sonnet-4 | Rule-based alignment checking |
| Portfolio Fit | gpt-4o | Numerical allocation reasoning |
| Synthesis/Memo | gemini-2.5-pro | Long-context document synthesis |

### 2.4 Credential Isolation

**No API keys in code. No credentials in configuration files.**

```
API Key Storage:
  Environment variables only:
    OPENAI_API_KEY
    ANTHROPIC_API_KEY
    GEMINI_API_KEY

  Loaded at provider init, never logged.
  Never stored in database.
  Never transmitted in API responses.
```

### 2.5 Failure Handling

| Failure | Strategy |
|---|---|
| Provider timeout (30s) | Retry 3× with exponential backoff (1s/4s/16s) |
| Rate limit (429) | Respect Retry-After header; max 3 retries |
| Auth failure (401/403) | Fail fast — do not retry. Log error. |
| Server error (5xx) | Retry 3×. After 3 → mark perspective failed |
| Model unavailable | Fall back to next model in tier (configured) |

---

## 3. Market Intelligence Provider Architecture

### 3.1 Provider Strategy

Sprint 013 implements ONE real market data provider: **Alpha Vantage**.
Future sprints add Bloomberg, Refinitiv, Yahoo Finance as needed.

### 3.2 Alpha Vantage Provider

```python
class AlphaVantageProvider:
    """Concrete MarketDataProvider using Alpha Vantage free tier."""

    def __init__(self, api_key: str):
        self.api_key = api_key  # From AV_API_KEY env var
        self.base_url = "https://www.alphavantage.co/query"

    def get_overview(self, symbol: str) -> MarketOverview:
        # ENDPOINT: OVERVIEW
        # Returns: Symbol, Name, Description, Sector, MarketCap, PERatio, etc.

    def get_financials(self, symbol: str) -> FinancialData:
        # ENDPOINT: INCOME_STATEMENT (annual)
        # Returns: Revenue, NetIncome, OperatingIncome, etc.

    def get_price_history(self, symbol: str, days: int) -> list[PricePoint]:
        # ENDPOINT: TIME_SERIES_DAILY
        # Returns: Open, High, Low, Close, Volume per day
```

### 3.3 Provenance

Every Alpha Vantage response carries the mandatory `ProvenanceEnvelope`
(6 fields from Sprint 012-C):

| Field | Value |
|---|---|
| source | "alpha_vantage" |
| provider | "Alpha Vantage API" |
| source_timestamp | `LatestQuarter` from response |
| retrieved_at | datetime.utcnow() |
| data_quality_status | VALID (or FAILED on error) |
| provider_version | AV API version from header |

### 3.4 Rate Limiting

Alpha Vantage free tier: **25 requests/day**.
Implies: 1 research run = ~6 requests (overview + 5 financial endpoints).
Max ~4 research runs/day. Sufficient for V1.

---

## 4. Research Execution Upgrade

### 4.1 Current Pipeline (Sprint 012-B)

```
POST /api/research/start
        │
        ▼
EvidenceCollector (internal only)
        │
        ▼
PerspectiveExecutor (mock LLM)
        │
        ▼
Memo generator (mock synthesis)
```

### 4.2 Sprint 013 Pipeline

```
POST /api/research/start
        │
        ▼
AlphaVantageProvider.fetch_evidence()
        ├── get_overview(symbol)
        ├── get_financials(symbol)     ← REAL market data
        └── get_price_history(symbol)
        │
        ▼
EvidenceCollector.collect()
        ├── Portfolio data (internal)
        ├── Policy data (internal)
        ├── Guardian data (internal)
        ├── Knowledge memory (internal)
        └── Market data (Alpha Vantage)  ← REAL
        │
        ▼
PerspectiveExecutor.execute_all()
        ├── Value       → Claude
        ├── Growth      → Claude
        ├── Risk        → Claude         ← REAL LLM calls
        ├── Macro       → GPT-4o
        ├── Policy      → Claude
        └── Portfolio   → GPT-4o
        │
        ▼
PromptGovernor.validate()               ← Hard enforcement
        │
        ▼
Memo generator → Gemini                 ← REAL synthesis
        │
        ▼
ConfidenceEngine.calculate()
        │
        ▼
Completed (stored in investment_memos)
```

### 4.3 Citation Integration

Every LLM-generated claim MUST cite its evidence source:

```
Memo section "bull_case":
  "Strong revenue growth of 15% YoY" [source: income_statement, FY2025]

Memo section "risks":
  "High P/E ratio of 35x vs sector average 22x" [source: overview]
```

Citations link back to `committee_evidence_items` for full audit trail.

---

## 5. First Real Investment Workflow

### 5.1 End-to-End Flow

```
1. Owner identifies opportunity
        │
        ▼
2. Creates investment idea (existing POST /api/ideas)
        │
        ▼
3. Requests committee review (existing)
        │
        ▼
4. Starts AI research (POST /api/research/start)       ← Sprint 012-B
        │
        ▼
5. AI fetches market data (Alpha Vantage)               ← Sprint 013 NEW
        │
        ▼
6. AI executes 6 LLM perspectives (Claude + GPT-4o)    ← Sprint 013 NEW
        │
        ▼
7. AI generates memo (Gemini)                           ← Sprint 013 NEW
        │
        ▼
8. Owner reviews memo in Dashboard
        │
        ▼
9. Owner makes decision (existing POST /api/decisions)
        │
        ▼
10. Decision logged in Journal → Learning Loop
```

### 5.2 Time Estimate

| Phase | Time |
|---|---|
| Market data fetch | 5-10 seconds |
| 6 parallel LLM calls | 30-60 seconds |
| Memo synthesis | 10-20 seconds |
| **Total** | **~1 minute** |

### 5.3 Cost Estimate (per run)

| Component | Cost |
|---|---|
| Alpha Vantage | Free tier (25 req/day) |
| Claude (4 calls × ~2K tokens) | ~$0.03 |
| GPT-4o (2 calls × ~2K tokens) | ~$0.01 |
| Gemini (1 call × ~4K tokens) | ~$0.02 |
| **Total** | **~$0.06/run** |

---

## 6. Cost Governance

### 6.1 Token Limits (per run)

| Model | Max Input | Max Output |
|---|---|---|
| claude-sonnet-4 | 4000 | 2000 |
| gpt-4o | 4000 | 2000 |
| gemini-2.5-pro | 8000 | 4000 |

### 6.2 Budget Tracking

Already implemented via `CostTracker` (Sprint 012-D):
- Log-only in V1
- Per-run cost recorded in `llm_execution_log`
- Future: per-day/per-month thresholds via notification_events

### 6.3 Model Selection Governance

Model routing is configured, not hardcoded:
- `prompt_templates.default_model` = per-perspective model
- Active prompt version controls which model is used
- Changing models = new prompt version, Owner-approved

---

## 7. Database Impact

No new tables. Sprint 013 adds:
- Provider implementations (service layer only)
- Enhanced PerspectiveExecutor with real LLM calls
- Enhanced EvidenceCollector with Alpha Vantage integration

All existing tables (research_requests, research_runs,
perspective_analyses, investment_memos, llm_execution_log,
market_data_cache) are reused.

---

## 8. API Impact

No new API endpoints. The existing POST /api/research/start triggers
the upgraded pipeline. Same 3 endpoints from Sprint 012-B.

---

## 9. Security

| Constraint | Enforcement |
|---|---|
| No API keys in code | Environment variables only |
| No keys in database | Never stored or logged |
| No keys in responses | Stripped from all API output |
| No broker integration | No broker code paths |
| No trading | No trade execution |
| AI advisory only | PermissionGate (Sprint 012-D) |

---

## 10. Estimate

| Component | Lines | Tests |
|---|---|---|
| Alpha Vantage provider | ~150 | 6 |
| OpenAI provider | ~80 | 4 |
| Claude provider | ~80 | 4 |
| Gemini provider | ~80 | 4 |
| Enhanced pipeline | ~60 | 4 |
| Citation integration | ~50 | 3 |
| **Total** | **~500** | **~25** |

---

## 11. Owner Decisions

See `docs/sprints/SPRINT_013_OWNER_DECISIONS.md` (8 pending).
