# Sprint 011 — Technical Design (Revised)
# AI Investment Committee Intelligence Engine

> **STATUS: DESIGN PHASE — APPROVED WITH IMPROVEMENTS — NOT AUTHORIZED**
>
> Design review: APPROVE WITH DESIGN IMPROVEMENTS (revised 2026-08-10)
> Sprint 010: COMPLETE (all 4 slices merged)
> Sprint 011: DESIGN PHASE ONLY
>
> Revision notes:
> - Added Research Run layer (request → run → perspective → memo)
> - Upgraded Research Memory → Investment Knowledge Memory
> - Added Portfolio Construction perspective (6 total)
> - Renamed POST /api/research/execute → /api/research/request
> - Added structured InvestmentMemo schema

---

## 1. Execution Architecture

### 1.1 Layer Model

```
Owner creates Investment Idea
        │
        ▼
POST /api/ideas/{id}/request-review   ← Existing (Sprint 010-A)
        │
        ▼
CommitteeReviewRequest created
        │
        ▼
POST /api/research/request             ← NEW — Owner requests research
        │
        ▼
ResearchRequest created                ← ONE request
        │
        ├── research_run (run 1)       ← ONE OR MORE runs
        │   ├── perspective_analysis (Value)
        │   ├── perspective_analysis (Growth)
        │   ├── perspective_analysis (Risk)
        │   ├── perspective_analysis (Macro)
        │   ├── perspective_analysis (Policy)
        │   └── perspective_analysis (Portfolio Fit)
        │   └── investment_memo (synthesis)
        │
        └── research_run (run 2)       ← Owner can re-request
            └── ...                       with different parameters
```

**Reasoning**: One research request may have multiple runs (e.g. Owner
re-requests with updated market data, or re-runs after portfolio changes).
Each run produces a complete set of analyses and a memo.

### 1.2 Schema

```
research_requests
├── id (UUID PK)
├── review_request_id (FK → committee_review_requests, RESTRICT)
├── investment_idea_id (FK → investment_ideas, SET NULL)
├── status (TEXT: 'pending','running','completed','failed')
├── parameters (JSONB, nullable)       — model selection, custom prompts
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)

research_runs
├── id (UUID PK)
├── request_id (FK → research_requests, RESTRICT)
├── run_number (INTEGER)               — 1, 2, 3... per request
├── status (TEXT: 'pending','collecting_evidence','analyzing',
│              'generating_memo','completed','failed')
├── started_at (TIMESTAMPTZ)
├── completed_at (TIMESTAMPTZ, nullable)
├── error_message (TEXT, nullable)
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)

perspective_analyses
├── id (UUID PK)
├── run_id (FK → research_runs, RESTRICT)
├── evidence_item_id (FK → committee_evidence_items, SET NULL)
├── perspective (TEXT)                 — 'value','growth','risk','macro',
│                                        'policy','portfolio_fit'
├── model (TEXT)                       — 'anthropic/claude-sonnet-4' etc.
├── prompt_version (INTEGER)           — prompt template version
├── analysis (JSONB, NOT NULL)         — structured LLM output
├── conviction_score (INTEGER)         — 1-10
├── started_at (TIMESTAMPTZ)
├── completed_at (TIMESTAMPTZ, nullable)
├── created_at (TIMESTAMPTZ)

investment_memos
├── id (UUID PK)
├── run_id (FK → research_runs, RESTRICT)
├── committee_report_id (FK → committee_reports, SET NULL)
├── synthesis_model (TEXT)             — model used for synthesis
├── memo (JSONB, NOT NULL)             — InvestmentMemo schema
├── confidence_score (INTEGER)         — 0-100
├── confidence_level (TEXT)            — 'HIGH','MEDIUM','LOW'
├── recommendation (TEXT)              — 'BUY','HOLD','PASS'
├── generated_at (TIMESTAMPTZ)
├── created_at (TIMESTAMPTZ)

investment_knowledge_memory
├── id (UUID PK)
├── entity_type (TEXT)                 — 'company','sector','macro_indicator'
├── entity_key (TEXT, NOT NULL)        — normalized identifier
├── profile (JSONB, NOT NULL)          — structured knowledge
├── past_thesis (JSONB, nullable)      — previous investment theses
├── past_evidence (JSONB, nullable)    — historical evidence collected
├── past_decisions (JSONB, nullable)   — decision history
├── past_outcomes (JSONB, nullable)    — prediction vs actual outcome
├── prediction_accuracy (JSONB, nullable) — accuracy metrics over time
├── source (TEXT)                      — 'ai_generated','market_data','owner'
├── version (INTEGER)                  — increments on update
├── created_at (TIMESTAMPTZ)
├── updated_at (TIMESTAMPTZ)

market_data_cache
├── id (UUID PK)
├── symbol (TEXT, NOT NULL)
├── data_type (TEXT)
├── data (JSONB, NOT NULL)
├── source (TEXT, NOT NULL)            — provider identifier
├── source_timestamp (TIMESTAMPTZ)     — when provider says data is from
├── fetched_at (TIMESTAMPTZ)           — when we retrieved it
├── expires_at (TIMESTAMPTZ)
├── created_at (TIMESTAMPTZ)
```

### 1.4 Market Data Provenance

`market_data_cache` is a **cache, not a source of truth**. Every data
point must preserve its origin chain:

```
External Provider (Alpha Vantage)
        │ source='alpha_vantage'
        │ source_timestamp='2026-08-10T14:30:00Z'
        ▼
market_data_cache (local cache)
        │ fetched_at='2026-08-10T14:31:22Z'
        │ expires_at='2026-08-11T14:31:22Z'
        ▼
Evidence Collection (reads from cache or fetches fresh)
        │ creates committee_evidence_item
        │   provenance='ai_generated'
        │   source_title='Market Data: AAPL Overview'
        │   citation_ref='Alpha Vantage API, retrieved 2026-08-10'
        ▼
Research Run (consumes evidence)
```

**Provenance fields on market_data_cache**:

| Field | Purpose |
|---|---|
| `source` | Provider identifier — 'alpha_vantage' |
| `source_timestamp` | Provider's timestamp for the data |
| `fetched_at` | When CompoundOS retrieved it |
| `expires_at` | When cache entry should be refreshed |

**Rules**:
- ALWAYS prefer `source_timestamp` from provider over `fetched_at`
- If provider doesn't supply a timestamp, use `fetched_at`
- Cache staleness is determined by `expires_at`, not `source_timestamp`
- Evidence items cite the provider, not the cache

```

**Constraints**:
- `ck_research_requests_status`: CHECK status IN (...)
- `ck_research_runs_status`: CHECK status IN (...)
- `ck_perspective_analyses_perspective`: CHECK perspective IN (...)
- `ck_investment_memos_confidence`: CHECK confidence_level IN ('HIGH','MEDIUM','LOW')
- `ck_investment_memos_recommendation`: CHECK recommendation IN ('BUY','HOLD','PASS')
- `uq_research_runs_number`: UNIQUE(request_id, run_number)
- `uq_knowledge_memory_entity`: UNIQUE(entity_type, entity_key)
- `uq_market_data_cache_symbol_type`: UNIQUE(symbol, data_type)

**Immutability**: `perspective_analyses` and `investment_memos` are immutable
after completion — no UPDATE allowed (BEFORE UPDATE trigger). They record
what the AI actually produced at that point in time.

### 1.3 Provenance

Every AI-generated artifact carries provenance:

| Artifact | Provenance Fields |
|---|---|
| perspective_analyses | model, prompt_version, started_at, completed_at |
| investment_memos | synthesis_model, generated_at, confidence_score |
| committee_evidence_items | source_type ('ai_value', etc.), provenance='ai_generated' |
| investment_knowledge_memory | source, version, updated_at |

---

## 2. Multi-Perspective Reasoning (6 Perspectives)

### 2.1 Why 6?

Added **Portfolio Construction / Portfolio Fit** perspective per design
review. CompoundOS evaluates household portfolio impact — not isolated
securities. This perspective answers: "How does this investment fit into
the existing portfolio?"

### 2.2 Perspective Definitions

| # | Perspective | Core Question |
|---|---|---|
| 1 | Value Investor | "Is this fairly priced? What's intrinsic value?" |
| 2 | Growth Investor | "What's the growth trajectory? Market opportunity?" |
| 3 | Risk Manager | "What's the worst case? Correlation impact?" |
| 4 | Macro Strategist | "Is this the right time? Macro backdrop?" |
| 5 | Policy Guardian | "Does this fit our policy? Bucket compliance?" |
| 6 | Portfolio Constructor | "How does this affect portfolio construction? Diversification? Factor exposure? Rebalancing impact?" |

### 2.3 Portfolio Constructor Focus Areas

| Area | Analysis |
|---|---|
| Factor exposure | Value, Momentum, Quality, Size, Low Vol |
| Correlation impact | How does adding this change portfolio correlation? |
| Diversification benefit | Does this add new exposure or concentrate existing? |
| Risk contribution | Marginal risk contribution (variance, CVaR) |
| Rebalancing impact | What would need to be sold to make room? |
| Capacity/sizing | Appropriate position size given liquidity and portfolio |

### 2.4 LLM Integration

```
OpenRouter API
├── POST /api/v1/chat/completions
├── Model routing per perspective:
│   ├── Value:         anthropic/claude-sonnet-4
│   ├── Growth:        anthropic/claude-sonnet-4
│   ├── Risk:          anthropic/claude-sonnet-4
│   ├── Macro:         openai/gpt-4o (broader training data)
│   ├── Policy:        anthropic/claude-sonnet-4 (structured output)
│   └── Portfolio Fit: openai/gpt-4o (quantitative + qualitative)
├── Synthesis:         anthropic/claude-sonnet-4 (6 → 1 memo)
└── Budget: max_tokens=2000 per perspective, 4000 for synthesis
```

---

## 3. Investment Memo Schema

### 3.1 Structured Schema

```python
class InvestmentMemo(BaseModel):
    # ── Recommendation ──
    recommendation: str          # 'BUY','HOLD','PASS'
    confidence_score: int       # 0-100
    confidence_level: str       # 'HIGH','MEDIUM','LOW'

    # ── Thesis ──
    thesis: str                 # Core investment thesis (2-3 sentences)
    thesis_strength: str        # 'strong','moderate','speculative'

    # ── Evidence ──
    evidence_summary: EvidenceSummary

    # ── Multi-Scenario ──
    bull_case: ScenarioAnalysis
    bear_case: ScenarioAnalysis

    # ── Risks ──
    risks: list[RiskAssessment]

    # ── Valuation ──
    valuation: ValuationSummary

    # ── Portfolio Impact ──
    portfolio_impact: PortfolioImpactSummary

    # ── Guardian Status ──
    guardian_impact: GuardianImpactSummary

    # ── Committee ──
    committee_summary: CommitteeDeliberation

    # ── Sprint 011 Final Review additions ──
    decision_context: DecisionContext
    invalidation_conditions: InvalidationConditions


class EvidenceSummary(BaseModel):
    sources_count: int
    key_metrics: list[KeyMetric]
    data_freshness: str         # 'fresh','stale','incomplete'

class ScenarioAnalysis(BaseModel):
    narrative: str              # Scenario description
    probability: str            # 'high','medium','low'
    estimated_return: str       # e.g. "+15%"
    key_assumptions: list[str]

class RiskAssessment(BaseModel):
    risk: str                   # Risk description
    severity: str               # 'critical','high','medium','low'
    mitigation: str             # How to manage this risk

class ValuationSummary(BaseModel):
    methodology: str            # 'DCF','comparable','historical','mixed'
    intrinsic_value: str | None
    current_price: str | None
    margin_of_safety: str | None  # e.g. "25%"

class PortfolioImpactSummary(BaseModel):
    new_allocation_pct: str
    current_allocation_pct: str
    diversification_benefit: str
    correlation_impact: str
    rebalancing_needed: bool

class GuardianImpactSummary(BaseModel):
    bucket_after: str           # e.g. "CORE: 72% → 65%"
    compliant: bool
    new_risks: list[str]

class CommitteeDeliberation(BaseModel):
    consensus: str              # Summary of agreement
    disagreements: list[str]    # Where perspectives diverged
    perspectives: dict[str, PerspectiveVote]

class PerspectiveVote(BaseModel):
    vote: str
    conviction: int
    rationale: str


class DecisionContext(BaseModel):
    """Why this research was requested — context for future review."""
    reason: str           # 'portfolio_allocation','market_event','valuation_review',
                          # 'policy_consideration','new_opportunity','periodic_review'
    description: str      # Human-readable explanation of the trigger
    portfolio_snapshot: str | None  # Snapshot of key metrics at time of research
    triggered_by: str     # 'owner','scheduled','guardian_event'


class InvalidationConditions(BaseModel):
    """Conditions that would invalidate the investment thesis.

    Used by the Learning Loop at 30d/90d/1yr review checkpoints
    to determine whether the original thesis still holds.
    """
    conditions: list[InvalidationCondition]
    monitoring_frequency: str  # 'monthly','quarterly','annually'


class InvalidationCondition(BaseModel):
    condition: str        # e.g. "Revenue growth < 5% YoY"
    metric: str           # e.g. "revenue_growth"
    threshold: str        # e.g. "<5%"
    current_value: str | None  # Value at time of memo
    category: str         # 'financial','market','regulatory','valuation','operational'
```

### 3.2 Reuse Targets

| Consumer | Uses |
|---|---|
| Dashboard | Recommendation + confidence embedded in idea view |
| Decision Journal | Memo attached to confirmed decision via evidence ref; decision_context explains trigger |
| Learning Loop | prediction_accuracy from recommendation vs outcome; invalidation_conditions checked at 30d/90d/1yr reviews |
| Future reviews | Re-run research with same decision_context; compare invalidation_conditions against current data |

---

## 4. API Design (Revised)

### 4.1 Endpoints

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/research/request | OWNER_MUTATION | Owner requests AI research for a review |
| GET | /api/research/{req_id} | READ | Research request status |
| GET | /api/research/{req_id}/runs | READ | List all runs for this request |
| GET | /api/research/runs/{run_id} | READ | Run detail with analyses |
| GET | /api/research/runs/{run_id}/memo | READ | Get investment memo |
| GET | /api/research/runs/{run_id}/analyses | READ | Get individual perspective analyses |
| GET | /api/research/runs/{run_id}/confidence | READ | Get confidence breakdown |
| POST | /api/research/runs/{run_id}/rerun | OWNER_MUTATION | Re-run research with same parameters |

**Renamed**: `POST /api/research/execute` → `POST /api/research/request`
per design review. AI must never appear to execute investment actions.

---

## 5. AI Authority (Unchanged + Reinforced)

| Action | AI CAN | Owner ONLY |
|---|---|---|
| Request research | ✗ | ✓ (AI triggered by Owner request only) |
| Collect market data | ✓ | — |
| Run perspective analysis | ✓ | — |
| Generate investment memo | ✓ | — |
| Compute confidence score | ✓ | — |
| Approve investment | ✗ | ✓ |
| Modify policy | ✗ | ✓ |
| Execute trade | ✗ | ✓ |
| Create decisions | ✗ | ✓ |

---

## 6. Implementation Slices

| Slice | Focus | Key Tables | Tests |
|---|---|---|---|
| A | Research Request + Run layer | research_requests, research_runs | 6 |
| B | Evidence collection + market data | market_data_cache, evidence CHECKs | 6 |
| C | Multi-perspective analysis + LLM | perspective_analyses, LLM client | 8 |
| D | Memo generation + knowledge memory | investment_memos, investment_knowledge_memory | 6 |
| **Total** | | 6 tables | **~26 tests** |

---

## 7. Owner Decisions (Updated)

See `docs/sprints/SPRINT_011_OWNER_DECISIONS.md` for complete list
including new decisions for:
- Research run retention policy
- Investment knowledge memory retention
- Perspective model selection
- LLM routing strategy
- Evidence freshness rules
