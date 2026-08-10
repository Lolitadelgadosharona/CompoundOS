# Sprint 012 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 011: COMPLETE
> Sprint 012: DESIGN DIRECTION ONLY
>
> 6 decisions required before implementation.

---

## OD-12-1: LLM Provider Authorization

### Question
Should Sprint 012 implement real LLM API calls or use mock providers?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Real OpenRouter | Connect to OpenRouter API, make real LLM calls | Functional AI from day one; validates the pipeline end-to-end | Requires API key; costs money per test run |
| B: Mock with real interface | Implement `LLMProvider` Protocol with mock backend; swap to real later | Tests are free; validates architecture without API dependency | Doesn't prove real LLM integration works |
| C: Hybrid | Mock by default, real with env flag | Test in CI uses mock; manual testing uses real | Extra complexity |

### Recommendation
**Option C — Hybrid.** CI tests use mock providers (zero cost, deterministic).
Owner can set `COMPOUNDOS_LLM_MODE=live` to test with real OpenRouter.
This validates the architecture while keeping CI costs at zero.

### Owner Decision
- [ ] APPROVE — Option A (Real OpenRouter)
- [ ] APPROVE — Option B (Mock with real interface)
- [ ] APPROVE — Option C (Hybrid: mock CI + live dev)
- [ ] OTHER: _______________

---

## OD-12-2: Research Execution Concurrency

### Question
Should perspective LLM calls run sequentially or in parallel?

### Options

| Option | Description |
|---|---|
| A: Sequential | Run 6 perspectives one after another |
| B: Parallel | Run all 6 perspectives concurrently |
| C: Configurable | Owner chooses per request |

### Recommendation
**Option B — Parallel.** 6 perspectives × 30s each = 3 minutes sequential
vs 30 seconds parallel. The perspectives are independent LLM calls with
no shared state. Parallel execution with `concurrent.futures` or `asyncio`
is straightforward and dramatically improves user experience.

### Owner Decision
- [ ] APPROVE — Option A (Sequential)
- [ ] APPROVE — Option B (Parallel)
- [ ] APPROVE — Option C (Configurable)
- [ ] OTHER: _______________

---

## OD-12-3: LLM Execution Logging Detail

### Question
How detailed should the LLM execution log be?

### Options

| Option | Description |
|---|---|
| A: Minimal | perspective, model, status, duration only |
| B: Standard | + tokens_in, tokens_out, cost_estimate, prompt_version |
| C: Full | + full prompt, full response, retry details |

### Recommendation
**Option B — Standard.** Tokens, cost, and prompt version are essential
for cost tracking and debugging. Full prompt/response logging (Option C)
adds significant storage and may include sensitive financial data.

### Owner Decision
- [ ] APPROVE — Option A (Minimal)
- [ ] APPROVE — Option B (Standard)
- [ ] APPROVE — Option C (Full)
- [ ] OTHER: _______________

---

## OD-12-4: Token Budget Per Perspective

### Question
What should be the max token budget per LLM perspective call?

### Options

| Option | Description |
|---|---|
| A: 2000 tokens | Compact; forces concise analysis |
| B: 4000 tokens | Room for detailed analysis with citations |
| C: 8000 tokens | Maximum depth; higher cost |

### Recommendation
**Option B — 4000 tokens.** 2000 is tight for structured JSON analysis
with evidence citations. 4000 gives sufficient room without excessive cost.
At $15/M output, a 4000-token analysis costs ~$0.06 per perspective.

### Owner Decision
- [ ] APPROVE — Option A (2000 tokens)
- [ ] APPROVE — Option B (4000 tokens)
- [ ] APPROVE — Option C (8000 tokens)
- [ ] OTHER: _______________

---

## OD-12-5: Prompt Template Governance

### Question
Who can create and modify prompt templates?

### Options

| Option | Description |
|---|---|
| A: Owner only | Owner creates/edits prompts via API |
| B: Developer-managed | Prompts in migration files, version-controlled |
| C: AI-suggested | AI proposes prompt improvements; Owner approves |

### Recommendation
**Option A — Owner only.** Investment analysis prompts directly influence
recommendation quality. Owner should control prompt content. Prompts are
stored in DB for runtime access, but creation/modification requires
Owner authorization.

### Owner Decision
- [ ] APPROVE — Option A (Owner only)
- [ ] APPROVE — Option B (Developer-managed)
- [ ] APPROVE — Option C (AI-suggested)
- [ ] OTHER: _______________

---

## OD-12-6: Research Failure Handling

### Question
What happens when a research run fails mid-execution?

### Options

| Option | Description |
|---|---|
| A: Fail fast | Stop immediately; mark as failed; partial results discarded |
| B: Partial results preserved | Perspectives that completed are kept; only failed ones are null |
| C: Retry then fail | Retry failed perspectives × 3; if still failing, preserve partial |

### Recommendation
**Option B — Partial results preserved.** A failed Macro perspective
shouldn't discard completed Value, Growth, and Risk analyses. The Owner
can review partial results and decide whether to re-run.

### Owner Decision
- [ ] APPROVE — Option A (Fail fast)
- [ ] APPROVE — Option B (Partial results)
- [ ] APPROVE — Option C (Retry then fail)
- [ ] OTHER: _______________

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-1 | LLM authorization | Hybrid (mock CI + live dev) |
| OD-12-2 | Execution concurrency | Parallel |
| OD-12-3 | Logging detail | Standard (tokens, cost, version) |
| OD-12-4 | Token budget | 4000 per perspective |
| OD-12-5 | Prompt governance | Owner only |
| OD-12-6 | Failure handling | Partial results preserved |
