# Sprint 017 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 016: COMPLETE
> Sprint 017: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Research Memory Evolution

### OD-17-1 — Memory Structure

**Question:** How should past research be organized for retrieval?

**Options:**
- A) Per-entity — all AAPL memos in one indexed collection
- B) Per-topic — memos grouped by investment theme (tech, value, growth)
- C) Timeline — chronological feed of all past analyses

**Recommendation:** **A — Per-entity with topic tags.** Primary lookup
by symbol. Secondary filtering by topic tags (AI, regulatory, earnings).
Matches how the Owner thinks about investments: "show me everything on AAPL."

---

### OD-17-2 — Thesis Versioning

**Question:** Should past theses be treated as immutable history or
living documents?

**Options:**
- A) Immutable — each memo is a snapshot, never updated
- B) Versioned — the latest memo supersedes, but history is preserved
- C) Overwrite — only the latest analysis matters

**Recommendation:** **A — Immutable.** Each memo is a time-stamped
snapshot of what the AI thought at that moment. This preserves
provenance and enables accuracy tracking. The "latest" analysis is
simply the most recent memo for that symbol.

---

### OD-17-3 — Knowledge Update Rules

**Question:** When an outcome is known, how should the knowledge
memory be updated?

**Method:**
- Record outcome (return, direction, review date)
- Update prediction accuracy metrics
- Flag the original memo as "reviewed" with outcome
- Do NOT retroactively modify the memo content
- New analysis may reference past outcomes

**Recommendation:** Append-only. Never modify historical memos.
Knowledge memory grows with each outcome.

---

## Slice B — Multi-Asset Intelligence

### OD-17-4 — Supported Asset Classes

**Question:** Which asset classes should Sprint 017 support beyond
equities?

**Options:**
- A) ETFs only (simplest — treat like a stock with underlying analysis)
- B) ETFs + bonds (broader — adds fixed income)
- C) ETFs + bonds + cash + REITs (full multi-asset)

**Recommendation:** **A — ETFs first.** ETFs are the highest-impact
addition with the lowest complexity. A VOO analysis looks at the
underlying S&P 500 composition. Bonds and cash can follow in
Sprint 018.

---

### OD-17-5 — ETF Handling

**Question:** How should ETF analysis differ from stock analysis?

**Differences:**
- Underlying composition analysis (top 10 holdings)
- Expense ratio impact
- Tracking error vs. index
- Sector exposure derived from holdings

**Same as stock:**
- 11-section memo structure
- 6-perspective analysis
- Confidence scoring
- Owner review workflow

---

## Slice C — Macro Intelligence

### OD-17-6 — Macro Indicators

**Question:** Which macro indicators should be tracked?

**Core indicators (recommended):**
- Federal Funds Rate
- 10-Year Treasury Yield
- 2Y/10Y Spread (recession signal)
- S&P 500 YTD return
- VIX (volatility index)
- Sector performance (relative strength)

**Refresh:** Daily or weekly, cached from free sources (FRED, Yahoo
Finance). No real-time trading data.

---

### OD-17-7 — Context vs. Prediction Boundary

**Question:** Should macro context influence the AI's recommendation?

**Rule:** Macro context provides **context**, not **prediction**.
- AI can say: "With rates at 5.25%, growth stocks face headwinds."
- AI CANNOT say: "The Fed will cut rates next quarter, so buy tech."
- Macro is factual background, not forward-looking speculation.

**Enforcement:** System prompt explicitly instructs the LLM to
present macro facts as context, not as predictions.

---

## Slice D — Research Quality Scoring

### OD-17-8 — Quality Score Dimensions

**Question:** What dimensions should the automated quality score cover?

**Dimensions and weights (recommended):**

| Dimension | Weight | What it measures |
|---|---|---|
| Completeness | 25% | Are all 11 memo sections populated? |
| Evidence quality | 25% | How many cited sources? Are they within freshness windows? |
| Balance | 20% | Is bear case proportional to bull case? |
| Confidence alignment | 15% | Does conviction match evidence depth? |
| Clarity | 15% | Is the thesis well-structured? (LLM-evaluated) |

**Display:**
- 8-10: Green "Strong Analysis"
- 5-7: Yellow "Adequate"
- 1-4: Red "Needs Improvement"

**Gate:** Quality scores are informational only. The Owner decides
whether to act. No automatic filtering of low-scoring memos.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-17-1 | A | Memory structure | Per-entity with topic tags |
| OD-17-2 | A | Thesis versioning | Immutable snapshots |
| OD-17-3 | A | Knowledge updates | Append-only, never modify history |
| OD-17-4 | B | Asset classes | ETFs first |
| OD-17-5 | B | ETF handling | Underlying analysis + same memo structure |
| OD-17-6 | C | Macro indicators | 6 core indicators (rates, yields, VIX, sectors) |
| OD-17-7 | C | Context boundary | Facts only, no prediction |
| OD-17-8 | D | Quality scoring | 5 dimensions, informational only |

---

## Architecture Preservation

All Sprint 012-016 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
