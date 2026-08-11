# Sprint 016 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 015: COMPLETE
> Sprint 016: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — First Real Investment Case Runs

### OD-16-1 — Validation Universe

**Question:** Which symbols should be included in the first real
validation runs?

**Options:**
- A) AAPL, MSFT, GOOGL, BRK.B, JNJ (Sprint 015 list — proven, diverse)
- B) Add 2-3 more symbols (V, COST, UNH) for broader coverage
- C) Owner's actual holdings only

**Recommendation:** **A — Sprint 015 list.** Already defined, diverse
sectors (tech, finance, healthcare), well-understood for quality
comparison. Add more in Sprint 017 after validating the pipeline.

---

### OD-16-2 — Research Frequency

**Question:** How often should real research runs execute?

**Options:**
- A) One batch of 5 runs, then manual thereafter
- B) Weekly batch for the 5 validation symbols (Monday morning)
- C) On-demand — Owner triggers each run individually

**Recommendation:** **A — One batch initially.** Validate the pipeline
first. Don't automate frequency until we're confident in output quality.
Owner can trigger individual re-runs after initial validation.

---

### OD-16-3 — Owner Feedback Capture

**Question:** How should the Owner provide feedback on AI-generated memos?

**Dimensions:**
- Agree/disagree with thesis (1-5)
- Evidence sufficient (yes/no)
- Confidence appropriate (too high / correct / too low)
- Would act on this (yes/no/maybe)
- Free-text notes

**Recommendation:** Simple 4-question feedback form on /memo/{id} page.
Stored as feedback JSON on the memo or a linked table. Minimal friction —
Owner should spend <30 seconds per memo.

---

## Slice B — Learning Loop Activation

### OD-16-4 — Outcome Review Timing

**Question:** When should the system check investment outcomes?

**Options:**
- A) 30 days — fastest feedback loop
- B) 90 days — more meaningful for long-term investments
- C) Both — schedule 30d check-in, 90d formal review

**Recommendation:** **C — Both.** 30d check-in for early signal (was
the direction correct?), 90d formal review for meaningful outcome
assessment. Sprint 012 interval design already supports this.

---

### OD-16-5 — Prediction Accuracy Calculation

**Question:** How is prediction accuracy measured?

**Method:**
- Compare AI confidence score (0-100) vs. actual return (%)
- Example: AI said 75% confidence BUY. Stock returned +15% in 90d.
  Was the direction correct? (yes → accuracy confirmed)
- Aggregate across all reviewed decisions

**Recommendation:** Simple direction accuracy (% of times AI was
directionally correct) + confidence error (|confidence - normalized return|).
No complex Sharpe/CAPM for V1.

---

## Slice C — Data Quality Improvement

### OD-16-6 — Data Freshness Policy

**Question:** When is market data considered stale?

**Per Sprint 013 decisions (OD-13-4):**
- Price: 6 hours
- Company overview: 7 days
- Financial statements: 90 days
- News: 24 hours

**Recommendation:** **Keep Sprint 013 freshness rules.** They were
owner-approved and are appropriate for a family office. Add a "data age"
badge on /research page showing the age of cached data.

---

### OD-16-7 — Missing Data Treatment

**Question:** What happens when Alpha Vantage returns incomplete data?

**Options:**
- A) Flag as "incomplete" and reduce confidence (current behavior)
- B) Retry with different endpoint (e.g., GLOBAL_QUOTE if OVERVIEW fails)
- C) Skip the run entirely — don't generate a memo without full data

**Recommendation:** **A — Flag and reduce confidence.** Already
implemented in Sprint 013-B (graceful degradation). AI should still
provide analysis with what it has, but clearly label missing data.
Never fabricate.

---

## Slice D — Daily Operating View

### OD-16-8 — Daily Dashboard Priorities

**Question:** What information should the daily operating view
prioritize?

**Priority order (recommended):**
1. Pending owner decisions (count + top 2 by confidence)
2. Latest research completions (last 3 runs)
3. Portfolio snapshot (allocation, concentration warnings)
4. Guardian alerts (policy violations)
5. Learning loop (scheduled reviews due this week)
6. Market context (S&P 500, sector performance — cached)

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-16-1 | A | Validation universe | Sprint 015 list (AAPL, MSFT, GOOGL, BRK.B, JNJ) |
| OD-16-2 | A | Research frequency | One batch, then manual |
| OD-16-3 | A | Owner feedback | 4-question form, <30s per memo |
| OD-16-4 | B | Outcome timing | 30d check-in + 90d formal review |
| OD-16-5 | B | Accuracy calc | Direction accuracy + confidence error |
| OD-16-6 | C | Data freshness | Keep Sprint 013 rules (6h/7d/90d/24h) |
| OD-16-7 | C | Missing data | Flag + reduce confidence |
| OD-16-8 | D | Dashboard priorities | Decisions > Research > Portfolio > Guardian > Learning |

---

## Architecture Preservation

All Sprint 013-015 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
