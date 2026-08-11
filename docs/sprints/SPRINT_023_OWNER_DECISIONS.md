# Sprint 023 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 022: COMPLETE
> Sprint 023: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Live Household Operation

### OD-23-1 — Net Worth Data Model

**Question:** What components make up the household net worth view?

**Components (recommended):**
- Investment portfolio (from CSV import, Sprint 021-A)
- Cash accounts (checking, savings, money market)
- Real estate (primary residence — manual value)
- Debt (mortgage, loans — manual entry)
- Other assets (private equity, collectibles — optional)

**Update frequency:** Monthly (first of month) or manual.

**Recommendation:** Start with investments + cash + real estate.
Debt tracking adds complexity without proportional value for V1.

---

### OD-23-2 — Cash Flow Tracking

**Question:** Should cash flow be tracked?

**Scope:**
- Income (salary, dividends, interest — manual monthly entry)
- Expenses (broad categories: housing, food, transportation, etc.)
- Savings rate (income - expenses / income)

**Recommendation:** **Manual monthly entry.** Connect to real
accounts later when Owner wants that complexity. V1: simple
monthly snapshot.

---

### OD-23-3 — Emergency Fund Calculation

**Question:** How is emergency fund adequacy measured?

**Method:**
- Monthly expenses × 6 = recommended emergency fund
- Compare cash + money market balances to target
- Status: green (≥6 months), yellow (3-6 months), red (<3 months)

**Recommendation:** Simple multiplier approach. No complex
Monte Carlo simulation for V1.

---

## Slice B — AI Calibration Improvement

### OD-23-4 — Calibration Report Content

**Question:** What should the weekly calibration report contain?

**Sections (recommended):**
1. Overall accuracy trend (rolling 12-week direction accuracy)
2. Per-perspective breakdown (Value vs. Risk vs. Growth accuracy)
3. Confidence calibration scatter (predicted vs. actual return)
4. Highlight: biggest miss and biggest hit this week
5. Recommendations: perspectives needing prompt tuning

**Frequency: Weekly digest, displayed on /learning dashboard.**

---

### OD-23-5 — Perspective Weighting

**Question:** Should more accurate perspectives get higher weight?

**Options:**
- A) Equal weighting (all 6 perspectives contribute equally)
- B) Accuracy-weighted (more accurate perspectives influence more)
- C) Owner-adjustable (slider to weight perspectives)

**Recommendation:** **A — Equal weighting for now.** Accuracy-weighted
voting risks positive feedback loops. Track accuracy, inform the
Owner, but don't automatically adjust weights until we have 50+
outcomes to base decisions on.

---

## Slice C — Investor Behavior Layer

### OD-23-6 — Behavior Signals

**Question:** What behavioral patterns should be tracked?

**Signals (recommended):**
- Action bias: % of BUY recommendations approved
- Decision latency: average days from research to decision
- Sector preference: which sectors are approved most/least
- Regret rate: decisions later reversed or regretted
- Confidence correlation: Owner confidence vs. AI confidence

**Privacy:** All behavior data is private to the Owner. Displayed
as informational insights — never judgmental.

---

### OD-23-7 — Privacy Boundary

**Question:** What behavior data should NEVER be tracked?

**Off-limits:**
- No psychological profiling
- No personality assessments
- No comparison to other investors
- No data shared externally
- No behavior-based automated actions

**Rule:** Insights are for the Owner's self-awareness, not for
the system to modify its behavior.

---

## Slice D — Long-Term Wealth Planning

### OD-23-8 — Planning Scope

**Question:** What long-term planning tools should be included?

**Tools (recommended, priority order):**
1. Retirement projection (compound growth, withdrawal rate)
2. College funding calculator (future cost, 529 basics)
3. Estate planning checklist (informational only)
4. Charitable giving optimizer (DAF basics, QCD eligibility)

**Constraints:** All educational. No specific recommendations.
Not financial advice. Owner consults their own professionals.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-23-1 | A | Net worth | Investments + cash + real estate; monthly |
| OD-23-2 | A | Cash flow | Manual monthly entry |
| OD-23-3 | A | Emergency fund | 6× expenses; green/yellow/red |
| OD-23-4 | B | Calibration | Weekly: accuracy trend, perspectives, highlights |
| OD-23-5 | B | Weighting | Equal until 50+ outcomes |
| OD-23-6 | C | Behavior | Action bias, latency, sector, regret, correlation |
| OD-23-7 | C | Privacy | No profiling, no sharing, no automated actions |
| OD-23-8 | D | Planning | Retirement, college, estate, charitable (educational) |

---

## Architecture Preservation

All Sprint 012-022 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- Behavior insights informational only
- Planning tools educational, not fiduciary
