# Sprint 017 — Design Direction
# Intelligence Expansion

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 016: COMPLETE
> Sprint 017: DESIGN ONLY

---

## Objective

After six sprints of building the core AI family office (012-016),
Sprint 017 expands CompoundOS's intelligence capabilities. The
system can now analyze individual stocks and make recommendations.
Sprint 017 adds multi-asset intelligence, macro context, research
memory, and automated quality scoring.

---

## Slice A — Research Memory Evolution

### Goal
Make each research run smarter by learning from all previous runs.
If we analyzed AAPL six months ago, the next analysis should build
on that — not start from scratch.

### Tasks
- Index all past memos by entity and topic
- When researching a symbol, retrieve relevant past analyses
- Include "what we said last time" in evidence bundle
- Track whether past predictions were correct
- Use this context to improve current analysis

### Example
"Last research on AAPL (Feb 2026): predicted 15% upside. Actual: +22%.
AI services revenue grew faster than anticipated. Current analysis
should factor in stronger services momentum."

---

## Slice B — Multi-Asset Intelligence

### Goal
Expand beyond equities. The Owner holds ETFs, bonds, and possibly
cash alternatives. The AI should analyze these with the same rigor.

### Asset types
- ETFs (VOO, QQQ, sector funds)
- Bonds (TLT, corporate, muni)
- Cash equivalents (SGOV, money market)
- REITs (if applicable)

### Adjustments
- ETFs: analyze underlying composition (top holdings)
- Bonds: yield analysis, duration risk, credit quality
- Cash: opportunity cost, inflation impact

---

## Slice C — Macro Intelligence

### Goal
Provide macroeconomic context for investment decisions. Single-stock
analysis is incomplete without understanding the broader environment.

### Data sources (cached)
- Federal Reserve: interest rates, dot plot
- Treasury yields: 2y/10y spread
- Sector performance: relative strength
- VIX: market fear gauge
- Earnings season: aggregate beats/misses

### Integration
Macro context appears as an additional perspective (replacing or
alongside the "macro" perspective in the 6-perspective analysis).

---

## Slice D — Research Quality Scoring

### Goal
Automatically rate AI memo quality using structured criteria so the
Owner can quickly distinguish strong from weak analyses.

### Quality dimensions (automated)
- **Completeness:** are all 11 sections populated?
- **Freshness:** is evidence data within freshness windows?
- **Confidence alignment:** does conviction match evidence depth?
- **Citation density:** how many evidence sources are cited?
- **Balance:** is the bear case proportional to the bull case?

### Display
Quality score (1-10) shown at the top of each memo, color-coded:
- 8-10: Green "Strong Analysis"
- 5-7: Yellow "Adequate"
- 1-4: Red "Needs Improvement"

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
- Which past memos to index (all vs. recent only)
- Multi-asset: which types to support first
- Macro data sources and freshness
- Quality scoring thresholds
- Should quality score gate memo presentation?
- Memory evolution: incremental vs. batch learning
