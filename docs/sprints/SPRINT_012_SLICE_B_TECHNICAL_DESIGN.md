# Sprint 012 Slice B — Technical Design
# Research Execution Pipeline

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 012 Slice A (LLM Runtime): DONE — merged as 59d137e (PR #90)
> Sprint 012 Slice B: DESIGN ONLY

---

## 1. Objective

Slice A built the LLM runtime infrastructure (prompt_templates, llm_execution_log).
Slice B builds the **execution pipeline** that orchestrates a complete
research run from request to completed memo.

---

## 2. State Machine

### 2.1 Run States

```
                    ┌─────────────────────────┐
                    │     pending              │
                    │  (run created, not yet   │
                    │   started)               │
                    └──────────┬──────────────┘
                               │ POST /api/research/start
                               ▼
                    ┌─────────────────────────┐
                    │  collecting_evidence     │
                    │  ├─ market data cache    │
                    │  ├─ policy context       │
                    │  ├─ guardian status      │
                    │  └─ portfolio context    │
                    └──────────┬──────────────┘
                               │ evidence collected
                               ▼
                    ┌─────────────────────────┐
                    │  analyzing               │
                    │  ├─ Value perspective    │┐
                    │  ├─ Growth perspective   │┤
                    │  ├─ Risk perspective     │┤ parallel
                    │  ├─ Macro perspective    │┤ LLM calls
                    │  ├─ Policy perspective   │┤
                    │  └─ Portfolio Fit        │┘
                    └──────────┬──────────────┘
                               │ all perspectives complete
                               ▼
                    ┌─────────────────────────┐
                    │  generating_memo         │
                    │  Synthesis LLM call      │
                    └──────────┬──────────────┘
                               │ memo generated
                               ▼
                    ┌─────────────────────────┐
                    │  completed               │
                    │  Confidence score        │
                    │  Recommendation recorded │
                    └─────────────────────────┘
```

### 2.2 Error States

```
Any state ──► failed
                ├─ error_message set
                ├─ partial results preserved
                └─ completed_at = now()
```

### 2.3 Recoverability

A `failed` run cannot be resumed. The Owner must request a new research
run via POST /api/research/request which increments `run_number`.

---

## 3. Execution Phases

### 3.1 Phase 1: Evidence Collection

| Step | Source | Store As |
|---|---|---|
| Fetch company overview | market_data_cache or external API | committee_evidence_item |
| Fetch financial statements | market_data_cache | committee_evidence_item |
| Load policy context | policy_rules, policy_capital_buckets | committee_evidence_item |
| Load guardian status | guardian_events | committee_evidence_item |
| Load portfolio context | positions, accounts, assets | committee_evidence_item |

**Failure handling**: If any evidence source fails (except external API),
continue with partial evidence. Evidence quality recorded. If external
API is unavailable, mark as `FAILED` and notify.

### 3.2 Phase 2: Parallel Perspective Execution

| # | Perspective | Model | Prompt Template | Budget |
|---|---|---|---|---|
| 1 | Value | claude-sonnet-4 | prompt_templates(value) | 4000 tokens |
| 2 | Growth | claude-sonnet-4 | prompt_templates(growth) | 4000 tokens |
| 3 | Risk | claude-sonnet-4 | prompt_templates(risk) | 4000 tokens |
| 4 | Macro | gpt-4o | prompt_templates(macro) | 4000 tokens |
| 5 | Policy | claude-sonnet-4 | prompt_templates(policy) | 4000 tokens |
| 6 | Portfolio Fit | gpt-4o | prompt_templates(portfolio_fit) | 4000 tokens |

**Parallel execution**: All 6 perspectives run concurrently via
`concurrent.futures.ThreadPoolExecutor` with max_workers=6.

**Per-perspective flow**:
```
1. Load prompt template (active + matching perspective)
2. Build prompt context (evidence items + portfolio data)
3. Execute LLM call (via LLMProvider)
4. Validate response JSON schema
5. Store perspective_analyses row
6. Log llm_execution_log entry
```

**Partial completion**: If 3/6 perspectives complete and 3 fail,
the successful analyses are preserved. The run proceeds to memo
generation only if all 6 complete.

### 3.3 Phase 3: Memo Generation

**Synthesis prompt**: Loads `prompt_templates(perspective='synthesis')`,
passes all 6 `perspective_analyses` as context, generates Investment Memo
per the 11-section schema from Sprint 011 TD.

**Output**: `investment_memos` row with:
- `memo` (JSONB) — all 11 sections
- `synthesis_model` — model used
- `generated_at` — timestamp

### 3.4 Phase 4: Confidence Calculation

Scoring formula (from Sprint 011 TD):

| Dimension | Weight | Source |
|---|---|---|
| Evidence quality | 25% | Evidence count × source diversity |
| Thesis clarity | 20% | LLM self-assessment (value + growth consensus) |
| Risk completeness | 20% | Risk Manager perspective score |
| Policy alignment | 15% | Policy Guardian assessment |
| Data freshness | 10% | Cache age check |
| Historical precedent | 10% | knowledge_memory past outcomes |

**Output**: `confidence_score` (0-100), `confidence_level` (HIGH/MEDIUM/LOW),
`recommendation` (BUY/HOLD/PASS) — all stored in `investment_memos`.

---

## 4. Async Worker Architecture

### 4.1 Worker Model

```
POST /api/research/start
        │
        ▼
┌───────────────────┐
│  API Layer        │  Creates research_run (status=pending)
│  POST handler     │  Enqueues job
│  ─────────────    │  Returns run_id immediately
│  return run_id    │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  Job Queue         │  research_run_id
│  (in-process)      │
└───────┬───────────┘
        │
        ▼
┌───────────────────┐
│  Research Worker   │  Executes phases 1-4 sequentially
│  ─────────────     │  Updates run status at each phase
│  Phase 1 → 2 → 3  │  Writes perspective_analyses rows
│  Phase 4 → done   │  Writes investment_memos row
│                    │  Logs llm_execution_log entries
└───────────────────┘
```

### 4.2 Worker Implementation

Sprint 012 uses an **in-process worker** (FastAPI background task)
rather than external message queue:

```python
@router.post("/api/research/start")
def start_research(request_id: UUID):
    run = create_run(request_id)
    background_tasks.add_task(execute_research_run, run.id)
    return {"run_id": run.id, "status": "pending"}
```

**Rationale**: Single-Owner system; no queue infrastructure needed.
Can migrate to external queue (Redis/RabbitMQ) in future sprints if
concurrent research needs arise.

### 4.3 Worker Lifecycle

| Phase | Status | Duration (est.) |
|---|---|---|
| Created | pending | <1ms |
| Evidence collection | collecting_evidence | 5-30s (API calls) |
| Perspective analysis | analyzing | 30-60s (6 parallel LLM) |
| Memo generation | generating_memo | 10-30s (synthesis LLM) |
| Complete | completed | N/A |
| Failed | failed | N/A |

**Total**: ~1-2 minutes per research run.

### 4.4 Worker Error Handling

| Error | Retry | Max | Action |
|---|---|---|---|
| LLM timeout | Yes (exp backoff) | 3 | After 3 failures → mark perspective failed |
| LLM rate limit (429) | Yes (respect Retry-After) | 3 | After 3 → mark perspective failed |
| LLM server error (5xx) | Yes (exp backoff) | 3 | After 3 → mark perspective failed |
| LLM validation failure | Yes (re-prompt) | 1 | After 1 → mark perspective failed |
| Evidence API failure | No | 0 | Continue with available evidence |
| Memo synthesis failure | No | 0 | Mark run failed |

---

## 5. Integration with Existing Tables

| Phase | Reads | Writes |
|---|---|---|
| Evidence collection | market_data_cache, investment_knowledge_memory, positions, accounts, policy_rules, guardian_events | committee_evidence_items (via existing evidence pipeline) |
| Perspective execution | prompt_templates, evidence items | perspective_analyses, llm_execution_log |
| Memo generation | perspective_analyses, prompt_templates | investment_memos, llm_execution_log |
| Confidence | investment_memos, perspective_analyses, evidence items | investment_memos (update score) |

---

## 6. API Design

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/research/start | OWNER_MUTATION | Start research execution |
| GET | /api/research/{id}/progress | READ | Current phase and perspective status |
| GET | /api/research/runs/{run_id}/results | READ | Complete results (memo + analyses) |

---

## 7. Database Impact

No new tables or columns. Slice B is a service/orchestration layer
that operates on existing tables from Sprints 009-012A.

---

## 8. AI Authority

| Action | Auto | Owner | Never |
|---|---|---|---|
| Execute research pipeline | ✓ | | |
| Collect market data | ✓ | | |
| Run LLM perspectives | ✓ | | |
| Generate memo | ✓ | | |
| Calculate confidence | ✓ | | |
| Start new research | | ✓ | |
| Approve investment | | ✓ | |
| Modify policy | | | ✓ |
| Execute trade | | | ✓ |

---

## 9. Estimate

| Component | Lines | Tests |
|---|---|---|
| Research executor service | ~200 | 6 |
| Worker task + background | ~80 | 3 |
| Progress/results API | ~60 | 2 |
| Confidence calculator | ~60 | 3 |
| **Total** | **~400** | **~14** |

---

## 10. Owner Decisions

See `docs/sprints/SPRINT_012_SLICE_B_OWNER_DECISIONS.md` (5 pending).
