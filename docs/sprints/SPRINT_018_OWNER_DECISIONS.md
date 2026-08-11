# Sprint 018 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 017: COMPLETE
> Sprint 018: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Bond Intelligence

### OD-18-1 — Supported Bond Instruments

**Question:** Which types of fixed income should Sprint 018 support?

**Options:**
- A) Treasury ETFs only (TLT, SHY, IEF) — simplest, good data
- B) Treasury ETFs + corporate bond ETFs (LQD, HYG)
- C) Individual bonds (requires CUSIP-level data — impractical for V1)

**Recommendation:** **A — Treasury ETFs.** TLT (20+ year), IEF
(7-10 year), SHY (1-3 year). Well-understood, highly liquid,
abundant public data. Corporate bonds add credit risk complexity
without proportional value for a family office V1.

---

### OD-18-2 — Yield Data Source

**Question:** Where does bond yield data come from?

**Options:**
- A) Alpha Vantage (already configured, same API)
- B) FRED API (free, authoritative, but separate integration)
- C) Cached/manual entry

**Recommendation:** **A — Alpha Vantage.** We already have the API
key and provider abstraction. TREASURY_YIELD endpoint covers the
instruments we need. No new integration.

---

### OD-18-3 — Duration Calculation

**Question:** How is interest rate risk communicated?

**Method:**
- For ETFs: use published effective duration (available from fund
  provider, e.g., TLT ~16 years, SHY ~2 years)
- Display as: "A 1% rate increase would reduce this position by
  approximately X%"
- No complex convexity or key rate duration for V1

---

## Slice B — Advanced Portfolio Analytics

### OD-18-4 — Metrics Included

**Question:** Which analytics metrics should be calculated?

**Core metrics (recommended):**
- Sharpe ratio (excess return / volatility, using 3-month T-bill as
  risk-free rate)
- Maximum drawdown (peak-to-trough over trailing 1 year)
- Correlation matrix (pairwise stock correlations)
- Portfolio beta (vs. S&P 500, trailing 1 year)
- Rolling returns (1m, 3m, 6m, 1y, YTD)

**Deferred (complex, marginal value for V1):**
- Sortino ratio, Calmar ratio, value-at-risk, Monte Carlo simulation

---

### OD-18-5 — Historical Window

**Question:** What lookback period for analytics calculations?

**Options:**
- A) 1 year (responsive, current market regime)
- B) 3 years (smoother, includes more market cycles)
- C) Since inception (if data available)

**Recommendation:** **A — 1 year for most metrics, 3 years for**
**benchmark comparison.** Most family offices think in annual terms.
3-year benchmark provides context without over-weighting historical
regimes.

---

## Slice C — Investment Committee Enhancement

### OD-18-6 — Committee Brief Format

**Question:** What should the pre-decision committee brief contain?

**Format (recommended):**
```
COMMITTEE BRIEF — {Symbol} — {Date}
-----------------------------------
Recommendation: BUY | HOLD | PASS
Confidence: XX%
Quality Score: X/10 — {Label}

PERSPECTIVE VOTES:
  Value: BUY | Growth: HOLD | Risk: BUY | Macro: HOLD |
  Policy: BUY | Portfolio Fit: HOLD

KEY FACTS:
  - [3-5 bullet points from evidence]

RISKS:
  - [Top 3 risks from memo]

OWNER ACTION REQUIRED:
  ☐ APPROVE    ☐ REJECT    ☐ MODIFY
```

---

### OD-18-7 — Dissent Recording

**Question:** How should perspective disagreements be captured?

**Rule:** If any perspectives vote differently from the majority,
record as a dissenting opinion. Example: "Value and Risk vote BUY,
but Macro votes HOLD due to rate environment."

**Display:** Shown in the committee brief under "Dissenting
Opinions" section.

---

## Slice D — Benchmark and Performance

### OD-18-8 — Benchmarks

**Question:** What should CompoundOS compare portfolio performance
against?

**Options:**
- A) S&P 500 only (simple, well-understood)
- B) S&P 500 + 60/40 portfolio (60% SPY, 40% AGG)
- C) Custom Owner-defined benchmark

**Recommendation:** **B — S&P 500 + 60/40.** The 60/40 is the
standard balanced portfolio benchmark. Comparing against both a
pure equity and a balanced benchmark gives the Owner context for
their risk tolerance.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-18-1 | A | Bond instruments | Treasury ETFs (TLT, IEF, SHY) |
| OD-18-2 | A | Yield source | Alpha Vantage (existing) |
| OD-18-3 | A | Duration | Published effective duration |
| OD-18-4 | B | Metrics | Sharpe, drawdown, correlation, beta, returns |
| OD-18-5 | B | Lookback | 1 year / 3 year |
| OD-18-6 | C | Brief format | Structured 1-page template |
| OD-18-7 | C | Dissents | Flag perspective disagreements |
| OD-18-8 | D | Benchmarks | S&P 500 + 60/40 portfolio |

---

## Architecture Preservation

All Sprint 012-017 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
