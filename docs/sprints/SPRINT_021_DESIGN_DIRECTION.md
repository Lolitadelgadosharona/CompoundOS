# Sprint 021 — Design Direction
# Real Operation & Calibration Phase

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 020: COMPLETE
> Sprint 021: DESIGN ONLY

---

## Objective

After eleven sprints and 290 tests, CompoundOS is production-ready.
Sprint 021 is the real-world validation sprint: deploy with actual
portfolio data, run real research cycles, track real decisions, and
compound knowledge from outcomes. This is where the system proves
its value to the Owner.

---

## Slice A — Real Portfolio Validation

### Goal
Import the Owner's actual portfolio and validate all analytics.

### Tasks
- CSV import for real holdings (Sprint 014-D portfolio intelligence)
- Verify allocation calculations against known values
- Run benchmark comparison with actual portfolio data
- Validate stress scenarios against real positions
- Identify any calculation discrepancies

### Deliverable
Validation report: "Calculations match expected values"

---

## Slice B — Decision Accuracy Expansion

### Goal
Expand the learning loop with real owner decisions.

### Tasks
- Record actual decisions (BUY/HOLD/PASS with dates)
- Schedule outcome reviews for past decisions
- Compare AI predictions vs. actual returns
- Update prediction accuracy metrics
- Identify which perspectives are most/least accurate

### Deliverable
Accuracy report per perspective with recommendations

---

## Slice C — Workflow Automation

### Goal
Automate routine tasks that the Owner currently triggers manually.

### Tasks
- Scheduled portfolio snapshot (weekly CSV export)
- Automated cache warming for top 5 symbols
- Recurring research prompts: "Review AAPL every 90 days"
- Automated accuracy reports (monthly)
- Dashboard notification on new research completion

### Constraints
- No trading automation
- No autonomous investment decisions
- Owner must opt-in to each automation

---

## Slice D — Knowledge Compounding

### Goal
Make each research run smarter by learning from all previous runs.

### Tasks
- Cross-reference current research with past memos
- Flag contradictions: "Previous analysis said X, now saying Y"
- Track thesis accuracy over time
- Build entity knowledge graph (AAPL → supply chain → sector → macro)
- Pre-populate evidence from past runs

### Example
"Last research on AAPL (Feb 2026): Predicted 15% upside. Actual: +22%.
Current analysis builds on this proven track record."

---

## Constraints

- AI advisory only
- Owner final authority
- No broker
- No trading
- No autonomous investment execution

---

## Owner Decisions Required

6-8 decisions covering:
- Which CSV data to import first
- Which past decisions to review
- Automation opt-in scope
- Knowledge compounding depth
- Validation acceptance criteria
