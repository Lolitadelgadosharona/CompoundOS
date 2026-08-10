# Sprint 011 — Technical Design
# AI Investment Committee Intelligence Engine

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 010: COMPLETE (all 4 slices merged)
> Sprint 011: DESIGN ONLY
>
> This document defines the technical architecture for transforming the
> Committee infrastructure (Sprint 006) into an AI-powered investment
> research and recommendation engine.

---

## 1. Problem Statement

The Committee infrastructure (Sprint 006 + 010-A) provides sessions,
evidence storage, reports, and a bridge from investment ideas. But
evidence collection is manual, analysis is unstructured, and the
Owner must do their own research before requesting Committee review.

Sprint 011 automates the research pipeline: when the Owner requests
Committee review for an investment idea, the system automatically:

1. Gathers relevant evidence (market data, fundamentals, policy status)
2. Runs multi-perspective AI analysis (Value, Growth, Risk, Macro, Policy)
3. Generates a structured Investment Memo with citations
4. Computes a confidence score for the recommendation
5. Presents findings to the Owner for decision

---

## 2. Existing Foundation

### 2.1 Reused Systems (Read/Write)

| System | Sprint | Tables | Usage in Sprint 011 |
|---|---|---|---|
| Committee sessions | 006 | `committee_sessions` | Target session for AI analysis |
| Evidence pipeline | 006 | `committee_evidence_items` | Stores gathered evidence |
| Committee reports | 006 | `committee_reports` | Stores generated memo text |
| Committee outcomes | 006 | `committee_outcomes` | Stores AI recommendation |
| Committee bridge | 010-A | `committee_review_requests` | Owner trigger → AI execution |
| Investment ideas | 009-C | `investment_ideas` | Source of analysis request |
| Policy rules | 009-B | `policy_rules` | Policy compliance context |
| Guardian events | 010-B | `guardian_events` | Risk context for analysis |
| Portfolio positions | 009-A | `positions`, `accounts`, `assets` | Current allocation context |

### 2.2 What Sprint 011 Adds

| Component | Type | Purpose |
|---|---|---|
| `research_requests` | New table | Tracks AI research executions |
| `research_memory` | New table | Cached company profiles, sector analyses |
| Evidence source types | Extended CHECK | `ai_value`, `ai_growth`, `ai_risk`, `ai_macro`, `ai_policy` |
| `market_data_cache` | New table | Cached external market data |
| Report content type | Extended CHECK | `investment_memo` report type |
| Outcome type | Extended CHECK | `ai_recommendation` outcome type |

---

## 3. Module Architecture

### 3.1 Execution Flow

```
Owner creates Investment Idea
        │
        ▼
POST /api/ideas/{id}/request-review   ← Existing (Slice A)
        │
        ▼
CommitteeReviewRequest created        ← Existing (Slice A)
        │
        ▼
POST /api/research/execute             ← NEW (Sprint 011)
        │
        ▼
ResearchRequest created                ← NEW
        │
  ┌─────┼─────────────────────────────┐
  │     ▼                             │
  │ Phase 1: Evidence Collection      │
  │ ┌─────────────────────────────┐   │
  │ │ Market data (Alpha Vantage) │   │
  │ │ Policy compliance context   │   │
  │ │ Guardian risk posture       │   │
  │ │ Portfolio context           │   │
  │ │ Historical outcomes         │   │
  │ └─────────┬───────────────────┘   │
  │           ▼                       │
  │ Evidence stored in               │
  │ committee_evidence_items +        │
  │ market_data_cache                 │
  │           │                       │
  │           ▼                       │
  │ Phase 2: Multi-Perspective        │
  │          Analysis                 │
  │ ┌─────────────────────────────┐   │
  │ │ Value Investor  → LLM      │   │
  │ │ Growth Investor → LLM      │   │
  │ │ Risk Manager    → LLM      │   │
  │ │ Macro Strategist→ LLM      │   │
  │ │ Policy Guardian → LLM      │   │
  │ └─────────┬───────────────────┘   │
  │           ▼                       │
  │ Analysis stored in                │
  │ committee_reports (JSONB)         │
  │           │                       │
  │           ▼                       │
  │ Phase 3: Memo Generation          │
  │ ┌─────────────────────────────┐   │
  │ │ Synthesize 5 analyses →    │   │
  │ │ Structured Investment Memo │   │
  │ └─────────┬───────────────────┘   │
  │           ▼                       │
  │ Memo stored in committee_reports  │
  │           │                       │
  │           ▼                       │
  │ Phase 4: Confidence Scoring       │
  │ ┌─────────────────────────────┐   │
  │ │ 6-dimension scoring model  │   │
  │ │ → confidence: score/level  │   │
  │ └─────────┬───────────────────┘   │
  │           ▼                       │
  │ Outcome stored in                 │
  │ committee_outcomes                │
  │           │                       │
  │           ▼                       │
  │ ResearchRequest → completed       │
  └───────────────────────────────────┘
        │
        ▼
Owner reviews Investment Memo
        │
        ▼
Owner decision (Accept/Reject/Override)
```

### 3.2 Module A — Research Request Engine

#### 3.2.1 Schema

```
research_requests
├── id (UUID PK)
├── review_request_id (FK → committee_review_requests, RESTRICT)
├── investment_idea_id (FK → investment_ideas, SET NULL)
├── status (TEXT: 'pending','collecting_evidence','analyzing','generating_memo','completed','failed')
├── started_at (TIMESTAMPTZ)
├── completed_at (TIMESTAMPTZ, nullable)
├── error_message (TEXT, nullable)
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)
```

**Constraints**:
- `ck_research_requests_status`: CHECK status IN (...)
- FK: review_request_id → committee_review_requests RESTRICT (review cannot be deleted while research active)

#### 3.2.2 API

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/research/execute | OWNER_MUTATION | Start research for a review request |
| GET | /api/research/{id}/status | READ | Check research progress |
| GET | /api/research/{id}/results | READ | Get complete research results |

### 3.3 Module B — Evidence Collection Layer

#### 3.3.1 Evidence Sources

| Source Type | Data Provider | Cached? | What it gathers |
|---|---|---|---|
| `market_data` | Alpha Vantage | Yes (market_data_cache) | Price, P/E, market cap, revenue, sector |
| `policy_context` | Internal (policy_rules) | No | Policy compliance check |
| `guardian_context` | Internal (guardian_events) | No | Current risk posture |
| `portfolio_context` | Internal (positions) | No | Current allocation |
| `historical_context` | Internal (decision_reviews) | No | Past similar decisions |

#### 3.3.2 Market Data Cache Schema

```
market_data_cache
├── id (UUID PK)
├── symbol (TEXT, NOT NULL)          — normalized uppercase
├── data_type (TEXT)                 — 'overview','income_statement','balance_sheet','sector_performance'
├── data (JSONB, NOT NULL)
├── fetched_at (TIMESTAMPTZ)
├── expires_at (TIMESTAMPTZ)         — 24h for price, 7d for fundamentals
├── created_at (TIMESTAMPTZ)
```

**Constraints**:
- `ck_market_data_cache_type`: CHECK data_type IN (...)
- `uq_market_data_cache_symbol_type`: UNIQUE(symbol, data_type)
- Index on `expires_at` for cache cleanup

#### 3.3.3 Evidence Storage

Extended `committee_evidence_items.source_type` CHECK with 5 new types:

| New Source Type | What it stores |
|---|---|
| `ai_value` | Value perspective analysis |
| `ai_growth` | Growth perspective analysis |
| `ai_risk` | Risk perspective analysis |
| `ai_macro` | Macro perspective analysis |
| `ai_policy` | Policy perspective analysis |

Each evidence item links to its committee session and carries:
- `source_title`: "Value Analysis: AAPL"
- `structured_facts`: JSONB with analysis output
- `citation_ref`: "Alpha Vantage + LLM analysis"
- `provenance`: "ai_generated"
- `confidence`: "HIGH" / "MEDIUM" / "LOW"
- `freshness`: timestamp

### 3.4 Module C — Research Memory

#### 3.4.1 Schema

```
research_memory
├── id (UUID PK)
├── entity_type (TEXT)              — 'company','sector','macro_indicator'
├── entity_key (TEXT, NOT NULL)     — normalized identifier
├── profile (JSONB, NOT NULL)       — structured knowledge
├── source (TEXT)                   — 'ai_generated','market_data','owner'
├── version (INTEGER)               — increments on update
├── created_at (TIMESTAMPTZ)
├── updated_at (TIMESTAMPTZ)
```

**Constraints**:
- `ck_research_memory_entity_type`: CHECK entity_type IN ('company','sector','macro_indicator')
- `uq_research_memory_entity`: UNIQUE(entity_type, entity_key)

#### 3.4.2 Usage

1. Before calling external API, check `research_memory` for cached profile
2. If profile exists and is fresh → use it (saves API call)
3. If profile is stale or missing → fetch + store
4. AI analysis also reads from research_memory for company context

### 3.5 Module D — Multi-Perspective Committee Reasoning

#### 3.5.1 Perspective Definitions

Each perspective is an LLM prompt with specific instructions:

| Perspective | System Prompt Focus | Input Context |
|---|---|---|
| Value Investor | Intrinsic value, margin of safety, DCF, book value | Fundamentals, P/E, P/B, FCF |
| Growth Investor | Revenue growth, TAM, competitive moat, innovation | Revenue trend, market share, R&D |
| Risk Manager | Downside scenarios, correlation, concentration, liquidity | Volatility, beta, portfolio impact |
| Macro Strategist | Interest rates, inflation, sector cycles, geopolitics | Macro data, sector trends, currency |
| Policy Guardian | Bucket compliance, rule adherence, exploration limits | Policy rules, current allocation |

#### 3.5.2 LLM Integration

```
OpenRouter API
├── POST /api/v1/chat/completions
├── Model selection per perspective:
│   ├── Value: anthropic/claude-sonnet-4
│   ├── Growth: anthropic/claude-sonnet-4
│   ├── Risk: anthropic/claude-sonnet-4
│   ├── Macro: openai/gpt-4o
│   └── Policy: anthropic/claude-sonnet-4
├── Budget: max_tokens=2000 per perspective
├── Temperature: 0.3 (analytical, not creative)
└── Structured output: JSON with sections
```

**Analysis JSON schema (per perspective)**:
```json
{
  "perspective": "value_investor",
  "model": "anthropic/claude-sonnet-4",
  "score": 7,              // 1-10 conviction score
  "thesis": "string",       // 2-3 sentence thesis
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "key_assumptions": ["..."],
  "data_points": [          // citations
    {"metric": "P/E ratio", "value": "22.5", "source": "Alpha Vantage"},
    {"metric": "Revenue", "value": "$383B", "source": "Alpha Vantage"}
  ],
  "risks": ["...", "..."] ,
  "recommendation": "BUY",  // BUY, HOLD, PASS
  "confidence": "MEDIUM",   // HIGH, MEDIUM, LOW
  "rationale": "string"
}
```

#### 3.5.3 Committee Integration

Analysis output is stored as `committee_evidence_items` with source_type
matching the perspective (e.g., `ai_value`, `ai_growth`). The `structured_facts`
column holds the full JSON output.

### 3.6 Module E — Investment Memo Generator

#### 3.6.1 Process

1. Collect all 5 perspective analyses from `committee_evidence_items`
2. Run a synthesis LLM call (models: anthropic/claude-sonnet-4):
   ```
   Prompt: "Synthesize the following 5 investment analyses into a formal
   Investment Memo. Preserve disagreements. Cite specific data. Format
   as structured sections."
   Input: 5 JSON analysis objects
   Output: Markdown-formatted Investment Memo
   ```
3. Store memo in `committee_reports` (new content_type: `investment_memo`)
4. Store synthesis metadata as `committee_evidence_items` (source_type: `ai_synthesis`)

#### 3.6.2 Memo Sections

```
1. Executive Summary
2. Company/Fund Analysis
3. Investment Thesis
4. Risk Analysis
5. Policy Compliance Assessment
6. Committee Deliberation (multi-perspective summary)
7. Recommendation
8. Confidence Score
```

### 3.7 Module F — Confidence Scoring

#### 3.7.1 Scoring Model

| Dimension | Weight | Source |
|---|---|---|
| Thesis clarity | 20% | LLM self-assessment |
| Evidence quality | 25% | Evidence count × source diversity |
| Risk completeness | 20% | Risk Manager perspective score |
| Policy alignment | 15% | Policy Guardian assessment |
| Market data freshness | 10% | cache age check |
| Historical precedent | 10% | Past similar decisions outcomes |

**Composite score (0-100) → Level**:
- ≥ 80 → HIGH
- 50–79 → MEDIUM
- < 50 → LOW

#### 3.7.2 Storage

Confidence score stored in `committee_outcomes` as structured data:
```json
{
  "outcome_type": "ai_recommendation",
  "recommendation": "BUY",
  "confidence_score": 72,
  "confidence_level": "MEDIUM",
  "score_breakdown": {
    "thesis_clarity": 14,
    "evidence_quality": 18,
    "risk_completeness": 15,
    "policy_alignment": 12,
    "market_data_freshness": 8,
    "historical_precedent": 5
  },
  "synthesized_by": "anthropic/claude-sonnet-4",
  "generated_at": "2026-08-10T12:00:00Z"
}
```

---

## 4. AI Authority Boundaries

### 4.1 AI CAN

| Action | Method |
|---|---|
| Collect evidence from external APIs | HTTP GET (Alpha Vantage, OpenRouter) |
| Summarize market data | LLM prompt |
| Analyze investment from multiple perspectives | 5 × LLM calls |
| Generate investment memo | Synthesis LLM call |
| Suggest recommendation (BUY/HOLD/PASS) | LLM output |
| Compute confidence score | Deterministic formula |
| Store analysis in evidence items | DB INSERT |
| Read portfolio/policy/guardian data | DB SELECT |

### 4.2 AI CANNOT

| Action | Enforcement |
|---|---|
| Approve investment | Owner must click "Accept Recommendation" |
| Modify policy | Policy table triggers block AI-originated mutations |
| Execute trade | No trade/order code path exists |
| Change allocation | No portfolio mutation from AI |
| Create decisions automatically | Decision creation requires Owner POST |
| Modify audit log | Audit log immutability trigger |

### 4.3 Boundary Enforcement

| Layer | Mechanism |
|---|---|
| API | AI endpoints classify as SYSTEM_INTERNAL; Owner endpoints OWNER_MUTATION |
| Database | Trigger/CHECK: requested_by ≠ 'ai_agent' in committee_review_requests |
| Service | AI service layer never calls Owner mutation endpoints |
| Audit | All AI actions logged as system.action with actor_role='ai' |

---

## 5. Database Impact

### 5.1 Migration: 0026_ai_research_engine

| Change | Table | Detail |
|---|---|---|
| CREATE | `research_requests` | Tracks AI research execution |
| CREATE | `research_memory` | Cached company/sector profiles |
| CREATE | `market_data_cache` | Cached external market data |
| Extend CHECK | `committee_evidence_items` | +5 AI source types |
| Extend CHECK | `committee_reports` | + investment_memo content_type |
| Extend CHECK | `committee_outcomes` | + ai_recommendation outcome_type |

**Additive only. Fully reversible.**

### 5.2 No External Credential Storage

API keys for Alpha Vantage and OpenRouter are stored in environment
variables only:
- `ALPHA_VANTAGE_API_KEY`
- `OPENROUTER_API_KEY`

No credentials in database, code, or migration.

---

## 6. API Design

### 6.1 New Endpoints

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/research/execute | OWNER_MUTATION | Start AI research for a review request |
| GET | /api/research/{id}/status | READ | Check research progress |
| GET | /api/research/{id}/memo | READ | Get generated investment memo |
| GET | /api/research/{id}/analyses | READ | Get individual perspective analyses |
| GET | /api/research/{id}/confidence | READ | Get confidence score breakdown |

### 6.2 Extended Endpoints

| Method | Path | Change |
|---|---|---|
| GET | /api/ideas/{id}/reviews | Include research status |

---

## 7. Implementation Slices

| Slice | Focus | Complexity | Key Files |
|---|---|---|---|
| A | Research Request Engine + Evidence Collection | MEDIUM | research_requests, market_data_cache, evidence extension |
| B | Multi-Perspective Analysis + LLM Integration | HIGH | LLM client, 5 perspective prompts, structured output |
| C | Memo Generator + Confidence Scoring | MEDIUM | Synthesis prompt, scoring formula |
| D | Research Memory + Caching | LOW | research_memory, cache invalidation |

---

## 8. Test Strategy

### 8.1 Slice A (~8 tests)

- Migration: research_requests, market_data_cache, CHECK extensions
- Research request creation and status lifecycle
- Evidence source types extended

### 8.2 Slice B (~8 tests)

- Mock LLM: perspective analysis returns valid JSON
- 5 perspectives produce distinct output
- Evidence items created with correct source_type
- Error handling: LLM timeout, invalid response

### 8.3 Slice C (~6 tests)

- Memo synthesis from 5 analyses
- Confidence score computation
- Committee outcome stored

### 8.4 Slice D (~4 tests)

- Research memory cache hit/miss
- Market data cache expiry
- Cache cleanup

### 8.5 Total: ~26 tests

---

## 9. Estimated Scope

| Component | Lines | Tests |
|---|---|---|
| Migration | ~120 | 3 |
| Models | ~80 | 0 |
| Research service | ~250 | 8 |
| LLM client | ~150 | 8 |
| Memo generator | ~100 | 6 |
| Scoring engine | ~80 | 0 (covered by memo tests) |
| Memory service | ~80 | 4 |
| Router + schemas | ~80 | 0 |
| HEAD_REVISION sweep | ~15 files | 0 |
| Approved tables | +3 entries | 0 |
| **Total** | **~940 lines** | **~26 tests** |

---

## 10. Owner Decisions (Confirmed from Design Direction)

| ID | Decision | Status |
|---|---|---|
| OD-11-1 | Sprint 011 focus: AI Committee Intelligence | Pending |
| OD-11-2 | Research autonomy: Owner-triggered only | Pending |
| OD-11-3 | Market data source: Alpha Vantage | Pending |
| OD-11-4 | LLM provider: OpenRouter | Pending |
| OD-11-5 | Evidence storage: Extend committee_evidence_items | Pending |
| OD-11-6 | Research memory: Company profile cache | Pending |
| OD-11-7 | Reasoning scope: 5 perspectives | Pending |

---

## 11. Absolute Exclusions

- No broker integration
- No trading or order execution
- No automatic investment decisions
- No policy modification by AI
- No credential storage in database
- No external notification delivery
- No frontend implementation
