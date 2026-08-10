# Sprint 012 — Design Direction
# AI Runtime + Research Execution Engine

> **STATUS: DESIGN DIRECTION — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 011: COMPLETE (Slices A-D all implemented)
> Sprint 012: DESIGN DIRECTION ONLY
>
> Sprint 011 built the data foundation for AI research. Sprint 012
> defines the runtime that executes it.

---

## 1. Sprint 012 Objective

Sprint 011 created the storage layer for AI research artifacts:
`research_requests`, `research_runs`, `perspective_analyses`,
`investment_memos`. Sprint 012 brings these to life by building the
**runtime** that orchestrates LLM calls, evidence collection, memo
generation, and confidence scoring.

**This is the engine that makes AI research happen.**

---

## 2. LLM Runtime Layer

### 2.1 Model Routing

| Concept | Design |
|---|---|
| Provider abstraction | Single `LLMProvider` Protocol with `generate(prompt, model, params) → LLMResponse` |
| Model registry | Configuration-driven mapping: perspective → model |
| Default routing | Value/Growth/Risk/Policy → Claude Sonnet 4, Macro/Portfolio → GPT-4o |
| Override | `research_requests.parameters` can specify per-run model overrides |
| API key | Environment variable `OPENROUTER_API_KEY` — never in DB |

### 2.2 Prompt Version Management

| Concept | Design |
|---|---|
| Prompt storage | `prompt_templates` table: perspective, version, system_prompt, user_prompt_template |
| Version tracking | `perspective_analyses.prompt_version` references the prompt template used |
| Migration | Prompts are data, not code — stored in DB, version-controlled |
| Upgrades | New prompt version → new analysis runs use it; old runs preserved |

### 2.3 Execution Tracking

| Concept | Design |
|---|---|
| Per-call tracking | `llm_execution_log` table: request_id, run_id, perspective, model, prompt_version, tokens_in, tokens_out, cost_estimate, duration_ms, status (success/failure/timeout) |
| Error handling | Retry with exponential backoff (max 3); 429 rate limit → wait + retry; 5xx → retry; 4xx → fail permanently |
| Timeout | 60s per LLM call; global run timeout 10 minutes |

### 2.4 Token + Cost Tracking

| Concept | Design |
|---|---|
| Token counting | `tokens_in`, `tokens_out` from API response headers |
| Cost estimation | Model-specific pricing: Claude Sonnet $3/$15 per M input/output, GPT-4o $2.50/$10 |
| Budget guard | Optional `max_tokens` per perspective (default 2000); max cost estimate logged before execution |

### 2.5 Evaluation Framework

| Concept | Design |
|---|---|
| Schema validation | Every LLM response validated against expected JSON schema |
| Quality gates | Empty analysis → fail; missing required fields → fail; confidence_score out of range → fail |
| Fallback | Validation failure → log, increment retry counter, re-prompt with error context |
| Human escalation | 3 consecutive failures → mark research_run as `failed`, notify Owner |

---

## 3. Research Execution Pipeline

### 3.1 State Machine

```
ResearchRequest (status: pending)
        │
        ▼ POST /api/research/start (Owner action)
        │
ResearchRun (status: collecting_evidence)
        │
        ├── Fetch market data (Alpha Vantage) ──► evidence items
        ├── Load policy context ────────────────► evidence items
        ├── Load guardian status ───────────────► evidence items
        ├── Load portfolio context ─────────────► evidence items
        │
        ▼ status → analyzing
        │
        ├── Value perspective ──────► LLM call → perspective_analyses
        ├── Growth perspective ─────► LLM call → perspective_analyses
        ├── Risk perspective ───────► LLM call → perspective_analyses
        ├── Macro perspective ──────► LLM call → perspective_analyses
        ├── Policy perspective ─────► LLM call → perspective_analyses
        └── Portfolio Fit ──────────► LLM call → perspective_analyses
        │
        ▼ status → generating_memo
        │
        Synthesis LLM call ──────► investment_memo
        │
        ▼ status → completed
```

### 3.2 Concurrency Model

- **Sequential by default**: Evidence → Perspectives → Memo (dependencies exist)
- **Parallel within phase**: All 6 perspectives can run concurrently (independent LLM calls)
- **Atomic**: If any perspective fails, the run status = `failed` with error detail
- **Idempotent**: Re-running creates a new `research_run` with incremented `run_number`

---

## 4. Tool Architecture (Future)

### 4.1 Provider Interface

```python
class MarketDataProvider(Protocol):
    def get_overview(self, symbol: str) -> dict: ...
    def get_financials(self, symbol: str) -> dict: ...
    def get_sector_performance(self, sector: str) -> dict: ...

class KnowledgeMemoryProvider(Protocol):
    def get_entity_profile(self, entity_type: str, entity_key: str) -> dict | None: ...
    def get_historical_thesis(self, entity_key: str) -> list[dict]: ...
    def get_past_outcomes(self, entity_key: str) -> list[dict]: ...
```

**No external API integration in Sprint 012.** These interfaces define the
contract for Sprint 013+ provider implementations.

---

## 5. Governance

### 5.1 What AI Can Execute Automatically

| Action | Auto | Requires |
|---|---|---|
| Fetch market data (Alpha Vantage) | Yes | API key in env |
| Load internal data (policy, guardian, portfolio) | Yes | DB access |
| Run perspective LLM calls | Yes | OpenRouter API key |
| Generate investment memo | Yes | Completed perspectives |
| Calculate confidence score | Yes | Completed memo |
| Create investment_ideas | No | Owner POST |
| Request committee review | No | Owner POST |
| Approve investment | No | Owner POST |
| Modify policy | No | Never |
| Execute trades | No | Never |

### 5.2 Audit Requirements

All LLM execution must be auditable:
- Every LLM call logged in `llm_execution_log`
- Prompt version tracked per perspective
- Model version recorded
- Tokens + cost recorded
- Error details preserved for failed calls

---

## 6. Database Impact (Proposed)

### 6.1 New Tables

| Table | Purpose |
|---|---|
| `prompt_templates` | Version-controlled prompt templates per perspective |
| `llm_execution_log` | Per-call execution tracking (tokens, cost, latency) |

### 6.2 Migration Estimate

Additive, reversible. No existing table modifications.

---

## 7. API Design (Proposed)

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/research/start | OWNER_MUTATION | Start research execution for a request |
| GET | /api/research/{id}/progress | READ | Real-time progress (phase, perspectives complete) |
| GET | /api/research/runs/{run_id}/log | READ | LLM execution log for a run |
| GET | /api/research/runs/{run_id}/cost | READ | Token usage + cost estimate |

---

## 8. What Sprint 012 Does NOT Include

- Real Alpha Vantage API integration (provider interface only)
- Real OpenRouter API calls (provider interface + mock testing)
- Autonomous research triggering (Owner must initiate)
- Research scheduling or automation
- Frontend UI for research progress

---

## 9. Implementation Slices (Proposed)

| Slice | Focus | Complexity |
|---|---|---|
| A | LLM Runtime (provider, execution log, prompt templates) | HIGH |
| B | Research Pipeline (orchestration, state machine) | HIGH |
| C | Tool Architecture (provider interfaces, evidence gathering) | MEDIUM |
| D | Governance (audit, cost tracking, validation) | MEDIUM |

---

## 10. Owner Decisions Required

See `docs/sprints/SPRINT_012_OWNER_DECISIONS.md`.
