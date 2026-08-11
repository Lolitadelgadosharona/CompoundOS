# Sprint 016 — Design Direction
# Real World Operation & Calibration

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 015: COMPLETE
> Sprint 016: DESIGN ONLY

---

## Objective

Sprint 015 built the framework for real usage. Sprint 016 activates it:
execute actual research runs with real LLM calls and real market data,
activate the learning loop with outcome tracking, improve data quality,
and build a daily operating view that the Owner can rely on.

The theme: **from prototype to daily driver.**

---

## Slice A — First Real Investment Case Runs

### Goal
Execute 5 actual research runs using the full pipeline: real
Alpha Vantage data, real Anthropic/OpenAI LLM calls, governed
execution with provenance. This validates every Sprint 013-015
component in production.

### Tasks
- Run pipeline for AAPL, MSFT, GOOGL, BRK.B, JNJ
- Each run: evidence collection → 6 perspectives → memo → confidence
- Compare AI-generated thesis vs. known market consensus
- Document prompt effectiveness per perspective
- Store results in dashboard-accessible DB tables
- Measure: runtime, cost, output quality

### Deliverable
5 completed memos in investment_memos table, viewable at /memo/{id}

---

## Slice B — Learning Loop Activation

### Goal
Close the loop from prediction to outcome. When a decision has a
known outcome (e.g., AAPL 90 days later), update prediction accuracy
and enrich knowledge memory.

### Tasks
- Activate decision_reviews with real outcome data
- Update prediction_accuracy in investment_knowledge_memory
- Compare predicted confidence vs. actual return
- Identify which perspectives were correct/incorrect
- Display learning metrics on /learning dashboard
- No automated rebalancing or trading

### Deliverable
Live learning dashboard with accuracy metrics from real data

---

## Slice C — Data Quality Improvement

### Goal
Monitor Alpha Vantage data quality, handle rate limits gracefully,
and ensure evidence provenance is preserved.

### Tasks
- Rate limit detection and backoff for Alpha Vantage (5 calls/min)
- Data freshness monitoring: flag stale data
- Automatic cache invalidation on provider errors
- Provider error dashboard: show last N provider failures
- Fallback to cached data with flagged quality
- No fabricated data ever

### Deliverable
Data quality monitoring visible in /research page

---

## Slice D — Daily Operating View

### Goal
A single page that answers: "What should the Owner do today?"

### Content
- Pending decisions (count + summary)
- Latest research runs (status + confidence)
- Portfolio snapshot (allocation, concentration)
- Guardian alerts (policy violations)
- Learning loop (scheduled reviews due)
- Market context (indices, sector performance — cached)

### Deliverable
Enhanced /dashboard page with real-time operational data

---

## Constraints

- No broker integration
- No trading
- No autonomous investment execution
- AI advisory only
- Owner remains final authority
- All LLM calls through GovernedLLMExecutor

---

## Owner Decisions Required

6-8 decisions covering:
- How many real runs before declaring "pipeline validated"
- Whether to use Alpha Vantage premium tier
- Outcome review cadence (30d/90d/1yr — which to implement first?)
- Data freshness thresholds by data type
- Dashboard: what should the "daily view" prioritize?
- Alert configuration: what triggers an Owner notification?
