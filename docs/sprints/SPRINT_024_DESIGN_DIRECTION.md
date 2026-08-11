# Sprint 024 — Design Direction (Revised)
# Real Operation Validation Sprint

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 023: COMPLETE
> Sprint 024: DESIGN ONLY
>
> **Strategic change:** Sprint 024 shifts from feature-building to
> real-world validation. After 14 sprints and 330 tests, the system
> must prove itself with actual household data and real decisions.

---

## Objective

CompoundOS has reached V2.3 capability: research intelligence,
investment committee, decision journal, outcome learning, knowledge
graph, and household wealth layer. Sprint 024 does NOT add features.
It validates every existing capability with real data, real decisions,
and real outcomes.

The question Sprint 024 answers: **"Does CompoundOS actually work?"**

---

## Slice A — Real Household Setup

### Goal
Set up CompoundOS with the Owner's actual financial data.

### Tasks
1. Import real portfolio holdings (CSV or manual entry)
2. Configure household snapshot (investments, cash, real estate, debt)
3. Set up emergency fund tracking with actual expense data
4. Verify all calculations match expected values
5. Document any data quality issues discovered

### Success criteria
- Net worth calculation verified (±1% vs. Owner's records)
- Portfolio allocation matches brokerage statement
- Emergency fund status correctly displayed

---

## Slice B — Real Investment Decision Workflow

### Goal
Execute the complete investment workflow with a real symbol.

### Tasks
1. Owner selects a symbol they're genuinely considering
2. System collects real market data (Alpha Vantage)
3. 6 AI perspectives execute with real LLM calls
4. Investment memo generated with confidence score
5. Committee review with structured brief
6. Owner makes a decision (approve/reject/modify)
7. Decision journaled with provenance

### Success criteria
- All 7 steps complete without errors
- AI memo rated by Owner (quality feedback)
- Decision recorded with full provenance chain
- End-to-end latency measured and documented

---

## Slice C — AI Calibration Validation

### Goal
Validate that AI confidence scores correlate with Owner assessment.

### Tasks
1. Run 3-5 research cycles on different symbols
2. Compare AI confidence vs. Owner's own conviction
3. Review evidence quality: are citations accurate?
4. Check for hallucination: any fabricated facts?
5. Document calibration gaps and prompt tuning needs

### Success criteria
- AI confidence within ±15 of Owner's assessment
- No hallucinated evidence in any memo
- Quality scores accurately reflect memo quality
- Calibration report reflects real data

---

## Slice D — Daily Wealth Operating Routine

### Goal
Establish the daily/weekly/monthly routine the Owner will follow.

### Tasks
1. Define morning routine: check dashboard, review alerts
2. Define weekly review: calibration report, pending decisions
3. Define monthly close: snapshot, allocation review, benchmark
4. Document the complete operating cadence
5. Identify any workflow gaps or friction points

### Success criteria
- Owner can complete daily check in <5 minutes
- Weekly review takes <15 minutes
- Monthly close produces a meaningful report
- No "I don't know what to do next" moments

---

## Deliverables (not code)

1. **Validation Report:** what worked, what didn't, what needs tuning
2. **Data Quality Log:** any Alpha Vantage issues, stale data, errors
3. **AI Quality Assessment:** Owner's rating of memo quality
4. **Operating Routine:** documented daily/weekly/monthly cadence
5. **Backlog for Sprint 025:** issues discovered during validation

---

## What Sprint 024 Does NOT Do

- Add new features
- Create new API endpoints
- Add new database tables
- Change existing architecture
- Deploy to production

---

## Constraints

- AI advisory only
- Owner final authority
- No broker
- No trading
- No autonomous investment execution
- No public deployment without auth approval
- All LLM calls through GovernedLLMExecutor
