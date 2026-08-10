# Sprint 012 — Owner Decisions

> **STATUS: DESIGN COMPLETE — ALL SLICES DESIGNED**
>
> Sprint 011: COMPLETE (Slices A-D all implemented)
> Sprint 012 Slice A: DONE (59d137e) · Slice B: DONE (b5444ac) · Slice C: DONE (1d73f84) · Slice D: DESIGN APPROVED
>
> 5 Slice C decisions + 4 Slice D decisions = 9 total. All resolved.
> All decisions preserve: AI advisory-only, no trading, no broker, no credentials.

---

## OD-12-1: Prompt Template Lifecycle

### Question
What lifecycle should prompt templates follow?

### Options

| Option | Lifecycle | Description |
|---|---|---|
| A: Versioned | draft → active → deprecated | Prompts are versioned; each perspective references a specific version. Draft prompts can be tested before activation. Deprecated prompts remain for audit but are not selectable for new runs. |
| B: Single active | one active per perspective | Only one prompt per perspective at a time. Changing it overwrites. Simpler but no rollback or audit of prompt evolution. |
| C: Git-managed | prompts in migration files | Prompts live in Alembic migrations or seed files, not in DB. Versioned via git history. Less flexible for runtime experimentation. |

### Architecture Impact
Option A requires `prompt_templates` table with `status` column and
CHECK constraint on lifecycle states. Each `perspective_analyses` row
links to a specific prompt version for audit.

### Recommendation
**Option A — Versioned lifecycle.** Investment analysis prompts are as
critical as code. They need versioning, testing, and rollback capability.
The versioned lifecycle matches the policy version pattern already in
CompoundOS (draft → sealed → superseded).

### Owner Decision
- [ ] APPROVE — Option A (Versioned: draft → active → deprecated)
- [ ] APPROVE — Option B (Single active per perspective)
- [ ] APPROVE — Option C (Git-managed in migrations)
- [ ] OTHER: _______________

---

## OD-12-2: LLM Model Routing Strategy

### Question
How should LLM model selection be managed?

### Options

| Option | Description |
|---|---|
| A: Single model | One model for all perspectives (e.g. Claude Sonnet 4 for everything) |
| B: Fixed routing per perspective | Each perspective has a designated model. Value→Claude, Macro→GPT-4o, etc. Configured in DB, changeable by Owner. |
| C: Multi-model with A/B | Each perspective can route to one of several fallback models. If primary fails, try secondary. |

### Architecture Impact
Option B requires `prompt_templates` table with `default_model` column
per perspective. Option C adds `fallback_models` array.

### Recommendation
**Option B — Fixed routing per perspective.** Different models have
different strengths (Claude for analytical reasoning, GPT-4o for broad
knowledge). Fixed routing gives predictable quality per perspective while
allowing Owner to experiment by changing the configured model.

### Owner Decision
- [ ] APPROVE — Option A (Single model)
- [ ] APPROVE — Option B (Fixed routing per perspective)
- [ ] APPROVE — Option C (Multi-model with fallback)
- [ ] OTHER: _______________

---

## OD-12-3: LLM Execution Logging Detail Level

### Question
How detailed should the LLM execution audit log be?

### Options

| Option | Fields | Cost |
|---|---|---|
| A: Minimal | run_id, perspective, model, status, duration_ms | Lowest storage |
| B: Standard | + tokens_in, tokens_out, cost_estimate, prompt_version, retry_count | Medium |
| C: Audit-grade | + full prompt (sanitized), response summary, structured validation errors | Highest |

### Architecture Impact
All options require `llm_execution_log` table. Option C adds larger
text columns for prompt/response storage.

### Recommendation
**Option B — Standard.** Tokens, cost, prompt version, and retry count
are essential for cost tracking and debugging. Full prompt logging (C)
adds significant storage and may include sensitive financial context.
Prompt content is already versioned in `prompt_templates`.

### Owner Decision
- [ ] APPROVE — Option A (Minimal: status + duration)
- [ ] APPROVE — Option B (Standard: + tokens, cost, version, retries)
- [ ] APPROVE — Option C (Audit-grade: + prompt + response)
- [ ] OTHER: _______________

---

## OD-12-4: Research Pipeline Execution Model

### Question
Should research execution be synchronous or asynchronous?

### Options

| Option | Description |
|---|---|
| A: Synchronous | POST /api/research/start blocks until all perspectives + memo complete (2-5 minutes). Returns final result in HTTP response. |
| B: Asynchronous worker | POST returns immediately. Background worker executes research. Owner polls GET /api/research/{id}/progress or receives notification on completion. |
| C: Hybrid async with webhook | Same as B, plus optional webhook/notification on completion. |

### Architecture Impact
Option A is simpler (no worker infrastructure) but ties up HTTP connections
for minutes. Option B requires a background execution model (similar to
existing CompoundOS automation worker pattern). Option C adds notification
wiring (existing infrastructure from Sprint 007/008).

### Recommendation
**Option B — Asynchronous worker.** AI research takes 2-5 minutes and
involves 6+ sequential API calls. Synchronous HTTP is inappropriate for
this duration. CompoundOS already has a proven automation worker pattern
(Sprint 005). Research execution follows the same model: POST creates
a run, worker processes it, Owner polls or is notified.

### Owner Decision
- [ ] APPROVE — Option A (Synchronous: blocks until complete)
- [ ] APPROVE — Option B (Asynchronous worker: poll progress)
- [ ] APPROVE — Option C (Hybrid async with notification)
- [ ] OTHER: _______________

---

## OD-12-5: AI Action Permission Matrix

### Question
What actions can the AI Runtime execute automatically vs require Owner approval?

### Proposed Matrix

| Action | Auto | Owner | Never | Notes |
|---|---|---|---|---|
| Fetch market data | ✓ | | | Read from Alpha Vantage cache |
| Load portfolio data | ✓ | | | Internal DB reads |
| Load policy/guardian data | ✓ | | | Internal DB reads |
| Execute LLM perspective calls | ✓ | | | 6 perspectives |
| Generate investment memo | ✓ | | | Synthesis from completed perspectives |
| Calculate confidence score | ✓ | | | Formula from memo + evidence |
| Store completed analysis | ✓ | | | Immutable DB writes |
| Log execution metrics | ✓ | | | Audit trail |
| Create investment idea | | ✓ | | Owner initiates research target |
| Request committee review | | ✓ | | Owner triggers via bridge |
| Approve investment | | ✓ | | Owner confirms recommendation |
| Modify policy | | | ✓ | Never — policy mutation blocked |
| Execute trade | | | ✓ | Never — no trade code paths |
| Connect to broker | | | ✓ | Never — no broker integration |

### Recommendation
**Approve the proposed matrix.** AI Runtime automates research execution
(data gathering, LLM analysis, memo generation, scoring). All
decision-making actions require Owner authorization.

### Owner Decision
- [ ] APPROVE — Proposed permission matrix as documented
- [ ] OTHER (specify modifications): _______________

---

## OD-12-6: Failure and Retry Policy

### Question
How should research execution handle failures?

### Sub-decisions

#### 6a. LLM call failures
What happens when an individual LLM call fails (timeout, 429, 5xx)?

| Option | Description |
|---|---|
| A: Retry × 3 | Exponential backoff (1s, 4s, 16s). Still failing → perspective marked failed. |
| B: Fail immediately | No retries. Perspective marked failed. |
| C: Retry × 5 | More aggressive. Higher latency, better recovery. |

**Recommendation: A — Retry × 3 with exponential backoff.**

#### 6b. Partial run handling
What happens when some perspectives succeed and others fail?

| Option | Description |
|---|---|
| A: Discard all | If any perspective fails, discard all results. |
| B: Partial preservation | Successful perspectives are kept as completed. Failed perspectives are null. Memo generation skipped. Owner reviews partial results. |
| C: Retry all | Re-run all perspectives (including successful ones). |

**Recommendation: B — Partial preservation.** A failed Macro perspective
shouldn't discard completed Value, Growth, and Risk analyses.

#### 6c. Research run timeout
How long before a research run is considered failed?

| Option | Timeout |
|---|---|
| A: 5 minutes | Tight; may fail with slow LLM responses |
| B: 10 minutes | Balanced; allows 6 × ~60s perspectives |
| C: 20 minutes | Generous; handles worst-case |

**Recommendation: B — 10 minutes.**

### Owner Decision
- [ ] APPROVE — Retry × 3 (A) + Partial preservation (B) + 10 min timeout (B)
- [ ] OTHER (specify): _______________

---

## Architecture Requirements Confirmation

All decisions preserve the following non-negotiable principles:

| Principle | Enforcement |
|---|---|
| AI advisory only | AI analyzes + recommends; Owner decides |
| No automatic investment approval | Decision creation requires Owner POST |
| No trading capability | No trade/order execution code paths |
| No broker integration | No broker connectors or API keys |
| No credentials in DB | API keys only in environment variables |

All completed AI artifacts preserve provenance:

| Artifact | Provenance |
|---|---|
| perspective_analyses | model, prompt_version, started_at, completed_at |
| investment_memos | synthesis_model, generated_at |
| llm_execution_log | model, prompt_version, tokens_in, tokens_out, cost_estimate, duration_ms |
| prompt_templates | version, status, created_at, deprecated_at |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-1 | Prompt template lifecycle | Versioned: draft → active → deprecated (A) |
| OD-12-2 | LLM model routing | Fixed routing per perspective (B) |
| OD-12-3 | Execution logging | Standard: tokens, cost, version, retries (B) |
| OD-12-4 | Pipeline execution model | Asynchronous worker (B) |
| OD-12-5 | AI permission matrix | 8 auto actions, 4 Owner-only, 3 never |
| OD-12-6 | Failure/retry policy | Retry × 3 + partial preservation + 10 min timeout |
