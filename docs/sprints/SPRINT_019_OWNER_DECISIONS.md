# Sprint 019 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 018: COMPLETE
> Sprint 019: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Portfolio Review Workflow

### OD-19-1 — Review Cadence

**Question:** How often should formal portfolio reviews be scheduled?

**Options:**
- A) Monthly checklist + quarterly deep-dive
- B) Quarterly only (lower overhead)
- C) Monthly for holdings, quarterly for strategy, annual for goals

**Recommendation:** **C — Three-tier cadence.** Monthly: holdings
review (concentration, recent research, alerts). Quarterly: strategy
review (allocation, performance, benchmarks). Annual: goals review
(wealth targets, risk tolerance, policy updates).

---

### OD-19-2 — Monthly Report Structure

**Question:** What should the monthly portfolio review contain?

**Sections (recommended):**
- Portfolio snapshot (value, allocation, top 5 holdings)
- Recent activity (research runs, decisions made)
- Concentration warnings (positions >20%, sectors >40%)
- Guardian alerts (policy violations, upcoming reviews)
- Performance (1-month return vs. benchmarks)
- Action items (decisions needed, research pending)

---

### OD-19-3 — Decision History Integration

**Question:** How should past decisions appear in reviews?

**Method:**
- Link each holding to its most recent investment memo
- Show decision outcome if available (direction correct Yes/No)
- Flag holdings with no recent research (stale >90 days)
- Display Owner feedback ratings where available

---

## Slice B — Risk Monitoring

### OD-19-4 — Stress Scenarios

**Question:** Which stress scenarios should be modeled?

**Core scenarios (recommended):**
- S&P 500 drops 20% (2022-style correction)
- Rates rise 200 bps (bond portfolio impact)
- Tech sector underperforms by 30% (concentration impact)
- Recession scenario (S&P -30%, bonds +5%, cash stable)

**Display:** Impact on portfolio value, allocation shift, which
holdings are most affected. Informational only — no automated
response.

---

### OD-19-5 — Alert Thresholds

**Question:** At what thresholds should the system alert the Owner?

**Thresholds (recommended):**
- Single position >25% of portfolio (critical)
- Single sector >50% of portfolio (warning)
- Portfolio beta >1.5 (aggressive)
- Max drawdown >15% from peak (attention)
- No research on position in >90 days (stale)

---

## Slice C — Capital Allocation Assistant

### OD-19-6 — Deployment Guidance Format

**Question:** How should the system suggest capital deployment?

**Format (recommended):**
```
CAPITAL DEPLOYMENT — $X AVAILABLE
----------------------------------
Top recommendations by confidence:
1. AAPL — Confidence 75% — Current weight 12% → Target 15%
2. GOOGL — Confidence 68% — Current weight 8% → Target 10%
3. No action — Hold cash at 4.5% SHY yield

Why: current allocation underweights tech vs. policy target.
Portfolio would remain within concentration limits.
```

**Constraints:** Suggestions only. Owner executes through their broker.

---

### OD-19-7 — Owner Approval Boundary

**Question:** What actions require Owner explicit approval?

**Always requires Owner:**
- Any capital movement (buy or sell decision)
- Policy target changes
- Adding new positions

**System can auto-suggest:**
- Rebalancing opportunities
- Tax-loss harvesting candidates
- Cash deployment priorities

**Never autonomous:**
- Trade execution
- Money movement
- Policy modification

---

## Slice D — Family Office Reporting

### OD-19-8 — Report Formats

**Question:** Which report formats should be generated?

**Options:**
- A) PDF only (professional, printable)
- B) Dashboard view only (interactive, always current)
- C) Dashboard + PDF on demand

**Recommendation:** **C — Dashboard + PDF on demand.** Dashboard
for daily use (always current, interactive). PDF generation for
quarterly reviews and record-keeping (Jinja2 → HTML → wkhtmltopdf).

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-19-1 | A | Review cadence | Monthly holdings + quarterly strategy + annual goals |
| OD-19-2 | A | Monthly report | Snapshot, activity, warnings, performance, actions |
| OD-19-3 | A | Decision history | Linked memos, outcomes, stale flags, feedback |
| OD-19-4 | B | Stress scenarios | 4 core: correction, rates, sector, recession |
| OD-19-5 | B | Alert thresholds | 25% position, 50% sector, 1.5 beta, 15% drawdown |
| OD-19-6 | C | Deployment format | Ranked by confidence, allocation-aware, cash alternative |
| OD-19-7 | C | Approval boundary | Owner approves all capital movements |
| OD-19-8 | D | Report formats | Dashboard daily, PDF on demand |

---

## Architecture Preservation

All Sprint 012-018 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
