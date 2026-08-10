# Sprint 011 — Owner Decisions (Revised)

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 011 Design: APPROVED WITH IMPROVEMENTS (revised 2026-08-10)
> 12 decisions require Owner review before implementation begins.

---

## OD-11-1: Sprint 011 Primary Focus

### Question
What should be the primary objective of Sprint 011?

### Options: A: AI Committee Intelligence / B: Portfolio Ops / C: Frontend / D: Production

### Recommendation
**Option A — AI Committee Intelligence.** Sprint 010 built the foundation
for AI-assisted investing. Sprint 011 should complete the intelligence layer.

### Owner Decision
- [ ] APPROVE — Option A (AI Committee Intelligence)
- [ ] APPROVE — Option B (Portfolio Operations)
- [ ] APPROVE — Option C (Frontend Implementation)
- [ ] APPROVE — Option D (Production Hardening)
- [ ] OTHER: _______________

---

## OD-11-2: AI Research Autonomy Level

### Question
How autonomously should AI conduct investment research?

### Options: A: Owner-triggered only / B: Scheduled / C: Event-triggered

### Recommendation
**Option A — Owner-triggered only.** Extends the manual trigger model
(OD-10-4). Owner controls when AI analysis runs.

### Owner Decision
- [ ] APPROVE — Option A (Owner-triggered)
- [ ] APPROVE — Option B (Scheduled)
- [ ] APPROVE — Option C (Event-triggered)
- [ ] OTHER: _______________

---

## OD-11-3: External Market Data Source

### Question
Which market data provider should CompoundOS use?

### Options: A: Alpha Vantage / B: Yahoo Finance / C: Polygon.io / D: Defer

### Recommendation
**Option A — Alpha Vantage.** Free tier sufficient for V1 research.

### Owner Decision
- [ ] APPROVE — Option A (Alpha Vantage)
- [ ] APPROVE — Option B (Yahoo Finance)
- [ ] APPROVE — Option C (Polygon.io)
- [ ] APPROVE — Option D (Defer)
- [ ] OTHER: _______________

---

## OD-11-4: LLM Provider Strategy

### Question
Which LLM provider should power AI Committee analysis?

### Options: A: OpenRouter / B: Anthropic direct / C: OpenAI direct / D: Local

### Recommendation
**Option A — OpenRouter.** Multi-model, no lock-in. Different models for
different perspectives.

### Owner Decision
- [ ] APPROVE — Option A (OpenRouter)
- [ ] APPROVE — Option B (Anthropic direct)
- [ ] APPROVE — Option C (OpenAI direct)
- [ ] APPROVE — Option D (Local model)
- [ ] OTHER: _______________

---

## OD-11-5: Evidence Storage Model

### Question
How should AI-generated research evidence be stored?

### Options: A: Extend committee_evidence_items / B: New table / C: JSONB in reports

### Recommendation
**Option A — Extend committee_evidence_items.** Unified evidence model.

### Owner Decision
- [ ] APPROVE — Option A (Extend committee_evidence_items)
- [ ] APPROVE — Option B (New table)
- [ ] APPROVE — Option C (JSONB in reports)
- [ ] OTHER: _______________

---

## OD-11-6: Investment Knowledge Memory Strategy

### Question
How should accumulated investment knowledge be stored and reused?

### Options

| Option | Description |
|---|---|
| A: Company profile + history | Cache fundamentals + past thesis + past decisions + past outcomes + prediction accuracy |
| B: Company profile only | Cache fundamentals only; no historical context |
| C: Session-only | No persistent memory; re-fetch every time |

### Recommendation
**Option A — Full knowledge memory.** The value of the system grows over
time as it accumulates knowledge about companies, past decisions, and
outcome accuracy. This enables the Learning Loop to close the feedback
cycle between predictions and outcomes.

### Owner Decision
- [ ] APPROVE — Option A (Company profile + history)
- [ ] APPROVE — Option B (Company profile only)
- [ ] APPROVE — Option C (Session-only)
- [ ] OTHER: _______________

---

## OD-11-7: Multi-Perspective Reasoning Scope

### Question
How many committee perspectives should Sprint 011 implement?

### Options: A: 3 / B: 5 / C: 6 / D: Configurable

### Recommendation
**Option C — 6 perspectives.** Includes the new Portfolio Construction
perspective per design review. Portfolio fit is essential for CompoundOS's
household-level analysis.

### Owner Decision
- [ ] APPROVE — Option A (3: Value, Growth, Risk)
- [ ] APPROVE — Option B (5: + Macro, Policy)
- [ ] APPROVE — Option C (6: + Portfolio Fit)
- [ ] APPROVE — Option D (Configurable)
- [ ] OTHER: _______________

---

## OD-11-8: Research Run Retention

### Question
How long should research runs and their analyses be retained?

### Options

| Option | Description |
|---|---|
| A: Indefinite | Keep all runs permanently — full research history |
| B: Latest only | Keep only the most recent run per request; delete older |
| C: Configurable | Retention period per research request type |

### Recommendation
**Option A — Indefinite.** Research runs are immutable historical records
of AI analysis at a point in time. They serve as an audit trail for
investment decisions. Storage cost is minimal (JSONB blobs).

### Owner Decision
- [ ] APPROVE — Option A (Indefinite)
- [ ] APPROVE — Option B (Latest only)
- [ ] APPROVE — Option C (Configurable)
- [ ] OTHER: _______________

---

## OD-11-9: Investment Knowledge Memory Retention

### Question
How long should investment knowledge be retained?

### Options

| Option | Description |
|---|---|
| A: Indefinite | Knowledge accumulates forever; grows with system |
| B: Staleness-based | Expire profiles not accessed in N days |
| C: Manual cleanup | Owner decides when to archive |

### Recommendation
**Option A — Indefinite.** Knowledge compounds. A company analysis from
6 months ago is still valuable context. The knowledge_memory table grows
slowly (one row per company/sector/macro indicator).

### Owner Decision
- [ ] APPROVE — Option A (Indefinite)
- [ ] APPROVE — Option B (Staleness-based)
- [ ] APPROVE — Option C (Manual cleanup)
- [ ] OTHER: _______________

---

## OD-11-10: Perspective Model Selection

### Question
Should each perspective use a fixed model or be configurable?

### Options

| Option | Description |
|---|---|
| A: Fixed per perspective | Value→Claude, Growth→Claude, Risk→Claude, Macro→GPT-4o, Policy→Claude, Portfolio→GPT-4o |
| B: Configurable per run | Owner can override model for any perspective |
| C: Best available | System picks cheapest available model meeting quality threshold |

### Recommendation
**Option A — Fixed with configurable override.** Sensible defaults per
perspective based on model strengths, but allow override via
`research_requests.parameters` JSONB for experimentation.

### Owner Decision
- [ ] APPROVE — Option A (Fixed per perspective)
- [ ] APPROVE — Option B (Configurable per run)
- [ ] APPROVE — Option C (Best available)
- [ ] OTHER: _______________

---

## OD-11-11: LLM Routing Strategy

### Question
How should LLM calls be routed through OpenRouter?

### Options

| Option | Description |
|---|---|
| A: Direct model selection | Explicit model per perspective (claude-sonnet-4, gpt-4o) |
| B: Capability-based routing | Route by capability (reasoning→Claude, breadth→GPT) |
| C: Cost-optimized routing | Use cheapest model per capability tier |

### Recommendation
**Option A — Direct model selection.** For investment research, model
quality matters more than cost. Explicit selection ensures the Owner
knows exactly which model produced each analysis. Cost tracking per
run is straightforward.

### Owner Decision
- [ ] APPROVE — Option A (Direct model selection)
- [ ] APPROVE — Option B (Capability-based routing)
- [ ] APPROVE — Option C (Cost-optimized routing)
- [ ] OTHER: _______________

---

## OD-11-12: Evidence Freshness Rules

### Question
How fresh must market data be before re-fetching?

### Options

| Option | Description |
|---|---|
| A: Aggressive | Prices: 1h / Fundamentals: 24h / Sector: 7d |
| B: Moderate | Prices: 6h / Fundamentals: 7d / Sector: 30d |
| C: Conservative | Prices: 24h / Fundamentals: 30d / Sector: 90d |

### Recommendation
**Option B — Moderate.** Balances data freshness with API call volume.
For a family office making occasional investment decisions (not daily
trading), 6-hour price data and weekly fundamentals are sufficient.
Alpha Vantage free tier supports this cadence.

### Owner Decision
- [ ] APPROVE — Option A (Aggressive: 1h/24h/7d)
- [ ] APPROVE — Option B (Moderate: 6h/7d/30d)
- [ ] APPROVE — Option C (Conservative: 24h/30d/90d)
- [ ] OTHER: _______________

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-11-1 | Sprint 011 focus | AI Committee Intelligence (A) |
| OD-11-2 | Research autonomy | Owner-triggered only (A) |
| OD-11-3 | Market data | Alpha Vantage (A) |
| OD-11-4 | LLM provider | OpenRouter (A) |
| OD-11-5 | Evidence storage | Extend committee_evidence_items (A) |
| OD-11-6 | Knowledge memory | Company profile + history (A) |
| OD-11-7 | Perspectives | 6 including Portfolio Fit (C) |
| OD-11-8 | Run retention | Indefinite (A) |
| OD-11-9 | Memory retention | Indefinite (A) |
| OD-11-10 | Model selection | Fixed per perspective (A) |
| OD-11-11 | LLM routing | Direct model selection (A) |
| OD-11-12 | Evidence freshness | Moderate: 6h/7d/30d (B) |
