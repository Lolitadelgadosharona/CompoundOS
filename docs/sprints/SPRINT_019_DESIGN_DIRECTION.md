# Sprint 019 — Design Direction
# Investment Operating System

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 018: COMPLETE
> Sprint 019: DESIGN ONLY

---

## Objective

After nine sprints building the AI family office (012-018),
Sprint 019 elevates CompoundOS from a collection of capabilities
into a cohesive investment operating system. The focus shifts
from individual features to workflows, from single analyses
to ongoing processes, and from tools to routines.

---

## Slice A — Portfolio Review Workflow

### Goal
Establish a regular portfolio review cadence. Instead of ad-hoc
research, the system should guide the Owner through structured
reviews on a schedule.

### Tasks
- Monthly portfolio review checklist
- Quarterly deep-dive agenda
- Annual strategy review template
- Review scheduling with reminders (dashboard badges)
- Review notes and action items tracking

### Example
Monthly review answers: "Are we on track? Any concentration issues?
Any positions that need research? Any policy violations?"

---

## Slice B — Risk Monitoring

### Goal
Proactively monitor risk rather than just reporting it reactively.

### Capabilities
- Risk dashboard: concentration, drawdown, beta, correlation
- Policy violation alerts (existing Guardian integration)
- Stress scenario modeling ("What if S&P 500 drops 20%?")
- Position-level risk contribution
- Currency risk where applicable

### Constraints
- Monitoring only — no automated rebalancing
- Alerts inform, never execute
- Scenarios for context, not prediction

---

## Slice C — Capital Allocation Assistant

### Goal
Help the Owner decide where to deploy new capital or what to sell
when cash is needed.

### Tasks
- "Where should I invest $X?" — ranks existing research by confidence
- "What should I sell if I need $X?" — tax-aware, allocation-aware
- Cash deployment prioritization
- Rebalancing suggestions (informational only)
- Opportunity cost analysis

### Constraints
- Suggestions only — Owner executes through their broker
- No tax advice (disclaimers)
- No automated execution

---

## Slice D — Family Office Reporting

### Goal
Generate professional reports the Owner can use for their own records
or share with their family/advisors.

### Reports
- Monthly portfolio summary (1-page PDF)
- Quarterly performance report (returns, benchmarks, attribution)
- Annual review (full-year analysis, strategy assessment)
- Tax preparation support (realized gains/losses, wash sale flags)
- Custom date range reports

### Format
- PDF generation (Jinja2 → HTML → wkhtmltopdf)
- Dashboard viewable versions
- Exportable data (CSV for external tools)

---

## Constraints

- No broker integration
- No trading
- No autonomous investment execution
- AI advisory only
- Owner remains final authority
- All guidance is informational, not fiduciary

---

## Owner Decisions Required

6-8 decisions covering:
- Review cadence: monthly, quarterly, or both?
- Risk thresholds for alerts
- Capital allocation: which criteria to prioritize
- Report formats and frequency
- Whether to include tax-related features
- Stress scenario defaults
