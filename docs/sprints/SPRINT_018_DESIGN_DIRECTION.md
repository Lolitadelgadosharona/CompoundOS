# Sprint 018 — Design Direction
# Portfolio Intelligence Upgrade

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 017: COMPLETE
> Sprint 018: DESIGN ONLY

---

## Objective

After eight sprints building out the AI family office (012-017),
Sprint 018 upgrades the portfolio intelligence layer. CompoundOS
can now analyze individual assets with quality scoring, memory,
and macro context. Sprint 018 adds deeper portfolio analytics,
bond support, committee process enhancement, and benchmark
comparison.

---

## Slice A — Bond Intelligence

### Goal
Extend multi-asset support to include fixed income. The Owner
likely holds bonds (TLT, corporate, muni) that need different
analysis than equities.

### Tasks
- Bond yield analysis (current yield, YTM approximation)
- Duration risk assessment
- Credit quality evaluation (if data available)
- Interest rate sensitivity
- Bond's role in portfolio (diversification, income)

### Constraints
- No real-time bond pricing (use cached/estimated data)
- No credit default swap or derivative analysis
- Advisory only — no trading recommendations

---

## Slice B — Advanced Portfolio Analytics

### Goal
Go beyond basic allocation and concentration. Add metrics that
professional family offices use.

### Metrics
- Sharpe ratio estimation (return / volatility)
- Maximum drawdown (peak-to-trough)
- Correlation matrix (stock-to-stock)
- Portfolio beta (vs S&P 500)
- Rolling returns (1m, 3m, 6m, 1y)

### Display
- New /portfolio/analytics dashboard page
- Visual indicators: green/amber/red for each metric
- Trend arrows for directional changes

---

## Slice C — Investment Committee Enhancement

### Goal
Make the committee review process more structured and useful.

### Enhancements
- Pre-meeting brief: auto-generate agenda from pending decisions
- Voting record: track which perspectives voted which way
- Dissenting opinions: flag when perspectives disagree
- Decision rationale template: structured Owner decision notes
- Committee history: searchable archive of past decisions

---

## Slice D — Benchmark and Performance

### Goal
Answer: "Is the portfolio performing well?"

### Benchmarks
- S&P 500 comparison (total return)
- 60/40 portfolio comparison (standard balanced benchmark)
- Custom benchmark (Owner-defined allocation)

### Tracking
- 1-month, 3-month, 6-month, 1-year, YTD returns
- Relative performance vs. benchmarks
- Attribution: which holdings drove performance?

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
- Bond data sources (estimated vs. real-time)
- Which analytics metrics are highest priority
- Committee meeting frequency and format
- Benchmark selection (which indices to compare)
- Performance reporting frequency
- Whether to include risk-adjusted metrics (Sharpe, Sortino)
