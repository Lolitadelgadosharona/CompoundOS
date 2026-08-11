# Sprint 021 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 020: COMPLETE
> Sprint 021: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Real Portfolio Validation

### OD-21-1 — CSV Import Schema

**Question:** What fields are required in the portfolio CSV?

**Required fields (recommended):**
- Symbol (ticker, e.g., AAPL)
- Shares (quantity held)
- Cost Basis (average cost per share)
- Asset Type (stock, etf, bond, cash)

**Optional fields:**
- Account (if multiple accounts)
- Purchase Date (for tax-lot tracking)
- Currency (default: USD)
- Notes (Owner annotations)

**Recommendation:** 4 required fields + 4 optional. Start with the
simplest possible import. Add complexity as the Owner's needs evolve.

---

### OD-21-2 — Calculation Verification

**Question:** How should we validate that portfolio calculations are correct?

**Method:**
- Import CSV → calculate total value, allocation, weights
- Owner provides expected values for top 5 positions
- Compare calculated vs. expected (tolerance: ±1% due to rounding)
- Flag discrepancies >1% for review
- Run benchmark comparison with validated data

**Recommendation:** Owner provides expected total portfolio value.
If calculated value differs by >1%, halt and review.

---

### OD-21-3 — Currency Handling

**Question:** How should non-USD positions be handled?

**Options:**
- A) Convert to USD at current exchange rate (assumed 1.0 for V1)
- B) Flag non-USD positions as "check currency"
- C) Reject non-USD positions in import

**Recommendation:** **B — Flag with "check currency" warning.**
Most Owner positions will be USD. Flagging non-USD avoids silent
errors while not blocking the import.

---

## Slice B — Decision Accuracy Expansion

### OD-21-4 — Outcome Tracking

**Question:** How should past decisions be linked to outcomes?

**Method:**
- Each decision has: symbol, action (BUY/HOLD/PASS), date, confidence
- 30 days later: record price change
- 90 days later: record formal outcome
- Compare AI prediction direction vs. actual direction
- Track which perspectives were correct

**Recommendation:** Link via `decision_reviews` table (existing).
Populate with real data from Owner's records or from Alpha Vantage
historical prices.

---

### OD-21-5 — Accuracy Metrics

**Question:** What accuracy metrics matter most?

**Core metrics (recommended):**
1. Direction accuracy: % of times AI was directionally correct
2. Confidence error: |predicted confidence - normalized return|
3. By perspective: which perspectives are most accurate?
4. By sector: are some sectors predicted better than others?
5. Trend: is accuracy improving over time?

**Display:** Learning dashboard already has accuracy. Sprint 021
wires real data instead of mock values.

---

## Slice C — Workflow Automation

### OD-21-6 — Snapshot Frequency

**Question:** How often should automated portfolio snapshots be taken?

**Options:**
- A) Weekly — good balance of timeliness and overhead
- B) Monthly — aligns with review cadence
- C) On demand only — no automation

**Recommendation:** **B — Monthly.** Aligns with the monthly review
workflow (Sprint 019-A). Snapshot captured first of each month.

---

### OD-21-7 — Research Scheduling

**Question:** Should research be automatically triggered?

**Options:**
- A) Yes — re-research top 5 holdings every 90 days
- B) No — Owner triggers all research manually
- C) Reminder only — "Research AAPL is 90 days stale" flag

**Recommendation:** **C — Reminder only.** Automation adds risk.
The "stale data >90d" flag from Sprint 019-B is sufficient. Owner
decides when to re-research.

---

## Slice D — Knowledge Compounding

### OD-21-8 — Cross-Reference Rules

**Question:** How should past analyses inform current research?

**Method:**
- When researching a symbol, search ResearchMemory (Sprint 017-A)
- If prior memo exists: include "what we said last time" section
- Flag contradictions: "Previous: BUY at 75% confidence. Current:
  HOLD at 60%. Why the change?"
- Track thesis accuracy: "Predicted 15% upside. Actual: +22%."

**Gate:** Cross-references are informational. AI still does fresh
analysis. Past memos provide context, not constraints.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-21-1 | A | CSV schema | 4 required (Symbol, Shares, Cost, Type) + 4 optional |
| OD-21-2 | A | Verification | Owner provides expected total; ±1% tolerance |
| OD-21-3 | A | Currency | Flag non-USD as "check currency" |
| OD-21-4 | B | Outcome tracking | Link via decision_reviews, populate from AV history |
| OD-21-5 | B | Accuracy metrics | Direction, confidence error, by perspective, by sector |
| OD-21-6 | C | Snapshots | Monthly (aligns with review cadence) |
| OD-21-7 | C | Research scheduling | Reminder only — no automatic execution |
| OD-21-8 | D | Cross-references | Informational context; flag contradictions |

---

## Architecture Preservation

All Sprint 012-020 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
- Automation reminders only — no autonomous execution
