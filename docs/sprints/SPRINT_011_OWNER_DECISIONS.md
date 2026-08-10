# Sprint 011 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 010: COMPLETE
> Sprint 011: DESIGN PREPARATION — NOT AUTHORIZED FOR IMPLEMENTATION
>
> These decisions must be resolved before Sprint 011 implementation begins.

---

## OD-11-1: Sprint 011 Primary Focus

### Question
What should be the primary objective of Sprint 011?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: AI Committee Intelligence | Evidence gathering, multi-perspective reasoning, memo generation | Directly advances core AI mission; builds on Sprint 006/010-A | Requires external APIs; high complexity |
| B: Portfolio Operations | Broker connectors, real-time positions, automated import | Practical value; makes system usable with real data | SEC-001 blocker (private repo needed first) |
| C: Frontend Implementation | Dashboard UI, decision workflow, portfolio views | Visual product; Owner can interact with system | Backend-dependent; large scope |
| D: Production Hardening | HTTPS, deployment, monitoring, backup verification | Makes system production-ready | Defers AI capabilities further |

### Recommendation
**Option A — AI Committee Intelligence.** Sprint 010 built the foundation
(committee infrastructure, Guardian intelligence, dashboard). Sprint 011
should complete the AI intelligence layer while the architecture momentum
is strong. Broker connectivity is blocked on SEC-001 (private repo).

### Owner Decision
- [ ] APPROVE — Option A (AI Committee Intelligence)
- [ ] APPROVE — Option B (Portfolio Operations)
- [ ] APPROVE — Option C (Frontend Implementation)
- [ ] APPROVE — Option D (Production Hardening)
- [ ] OTHER (specify): _______________

---

## OD-11-2: AI Research Autonomy Level

### Question
How autonomously should AI conduct investment research?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Owner-triggered only | AI analyzes only when Owner explicitly requests via Committee bridge | Maximum control; matches OD-10-4 | Requires Owner initiation for every analysis |
| B: Scheduled research | AI runs periodic analysis on watchlist ideas | Proactive; catches opportunities | May produce noise on unchanging ideas |
| C: Event-triggered | AI analyzes when market data changes significantly (price moves, news) | Responsive; timely | Complex trigger logic; dependency on market data |

### Recommendation
**Option A — Owner-triggered only.** Extends the existing manual trigger
model (OD-10-4). Owner retains complete control over when AI analysis is
initiated. Scheduled and event-triggered analysis can be added in future
sprints as the market data infrastructure matures.

### Owner Decision
- [ ] APPROVE — Option A (Owner-triggered only)
- [ ] APPROVE — Option B (Scheduled research)
- [ ] APPROVE — Option C (Event-triggered)
- [ ] OTHER (specify): _______________

---

## OD-11-3: External Market Data Source

### Question
Which external market data provider should CompoundOS integrate with?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Alpha Vantage | Free tier available; fundamentals + prices | Low cost; well-documented API | Rate limits; data quality varies |
| B: Yahoo Finance (yfinance) | Free; comprehensive; no API key needed | Easiest to start; broad coverage | Unofficial; terms of service gray area |
| C: Polygon.io | Professional API; real-time data | Reliable; enterprise-grade | Requires paid plan for full access |
| D: Defer to future sprint | No external data in Sprint 011 | Keeps scope bounded | AI analysis limited to internal data only |

### Recommendation
**Option A — Alpha Vantage.** Provides a free tier with sufficient data
for V1 research. Well-documented REST API with fundamentals, prices, and
FX rates. Can be upgraded to paid tier later. The API key model aligns
with the existing X-API-Key auth pattern.

### Owner Decision
- [ ] APPROVE — Option A (Alpha Vantage)
- [ ] APPROVE — Option B (Yahoo Finance)
- [ ] APPROVE — Option C (Polygon.io)
- [ ] APPROVE — Option D (Defer)
- [ ] OTHER (specify): _______________

---

## OD-11-4: LLM Provider Strategy

### Question
Which LLM provider should power the AI Committee analysis?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: OpenRouter | Multi-model gateway; Claude, GPT, Gemini | Model flexibility; no lock-in; pay-per-use | Adds intermediary layer |
| B: Anthropic direct | Claude API directly | Strong reasoning; long context | Single provider lock-in |
| C: OpenAI direct | GPT-4 API directly | Large ecosystem; well-supported | Single provider lock-in |
| D: Local model | Run open-source LLM locally | No API costs; data privacy | Hardware requirements; lower quality |

### Recommendation
**Option A — OpenRouter.** Provides access to multiple models through a single
API. Allows the Committee to use different models for different perspectives
(e.g., Claude for deep analysis, GPT for summarization). No provider lock-in.
The API key model aligns with existing X-API-Key auth.

### Owner Decision
- [ ] APPROVE — Option A (OpenRouter)
- [ ] APPROVE — Option B (Anthropic direct)
- [ ] APPROVE — Option C (OpenAI direct)
- [ ] APPROVE — Option D (Local model)
- [ ] OTHER (specify): _______________

---

## OD-11-5: Evidence Storage Model

### Question
How should AI-generated research evidence be stored?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Extend committee_evidence_items | Use existing table with new source types | Reuses existing schema; unified evidence model | Evidence items table may grow large |
| B: New research_evidence table | Separate table for AI-generated analysis | Clean separation; optimized for research data | Schema proliferation; another table to maintain |
| C: JSONB in committee_reports | Store analysis as structured JSON in existing report field | Simple; no new tables | Difficult to query structured data; report field becomes dumping ground |

### Recommendation
**Option A — Extend committee_evidence_items.** The existing evidence
pipeline (Sprint 006) already supports 9 source types. Adding AI-generated
research as new source types preserves the unified evidence model and
enables cross-referencing. The evidence items table is designed for growth.

### Owner Decision
- [ ] APPROVE — Option A (Extend committee_evidence_items)
- [ ] APPROVE — Option B (New research_evidence table)
- [ ] APPROVE — Option C (JSONB in committee_reports)
- [ ] OTHER (specify): _______________

---

## OD-11-6: Research Memory Strategy

### Question
How should AI-generated research be persisted across sessions?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Company profile cache | Cache per-company fundamentals in structured table | Reusable across ideas; reduces API calls | Cache staleness management needed |
| B: Session-only research | Research lives only within committee session | Simple; no staleness issues | Redundant API calls for repeated analysis |
| C: Full research archive | All analysis permanently stored with versioning | Complete audit trail; historical reference | Storage growth; complexity |

### Recommendation
**Option A — Company profile cache.** Caching fundamental data (financials,
metrics, sector info) makes sense because it changes slowly and is reusable.
Session-specific analysis (thesis, risk assessment) remains within the
committee session. This balances efficiency with simplicity.

### Owner Decision
- [ ] APPROVE — Option A (Company profile cache)
- [ ] APPROVE — Option B (Session-only)
- [ ] APPROVE — Option C (Full archive)
- [ ] OTHER (specify): _______________

---

## OD-11-7: Multi-Perspective Reasoning Scope

### Question
How many committee perspectives should Sprint 011 implement?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: 3 perspectives | Value, Growth, Risk — essential trio | Focused; implementable in one sprint | May miss macro/regulatory angles |
| B: 5 perspectives | Value, Growth, Risk, Macro, Policy | Comprehensive coverage | More LLM calls per analysis; higher cost |
| C: Configurable | Owner selects which perspectives to run | Flexible; pay for what you use | More complex UI/service layer |

### Recommendation
**Option B — 5 perspectives.** The perspectives defined in the design
direction cover the essential dimensions of investment analysis. Each
perspective generates valuable, distinct insights. Since analysis is
Owner-triggered (not automated), cost is controlled by usage frequency.

### Owner Decision
- [ ] APPROVE — Option A (3 perspectives)
- [ ] APPROVE — Option B (5 perspectives)
- [ ] APPROVE — Option C (Configurable)
- [ ] OTHER (specify): _______________

---

## Decision Summary

| ID | Topic | Recommendation | Owner Decision |
|---|---|---|---|
| OD-11-1 | Sprint 011 focus | AI Committee Intelligence (A) | |
| OD-11-2 | AI research autonomy | Owner-triggered only (A) | |
| OD-11-3 | Market data source | Alpha Vantage (A) | |
| OD-11-4 | LLM provider | OpenRouter (A) | |
| OD-11-5 | Evidence storage | Extend committee_evidence_items (A) | |
| OD-11-6 | Research memory | Company profile cache (A) | |
| OD-11-7 | Reasoning scope | 5 perspectives (B) | |

---

## Post-Decision Process

1. Owner marks each decision.
2. Agent updates this document with final decisions.
3. Agent creates Sprint 011 Technical Design.
4. Implementation begins after design approval.

---

## AI Authority Reminder

None of these decisions expand AI authority:
- AI analyzes and recommends — never decides
- Owner triggers all analysis
- No autonomous trading or execution
- No policy modification by AI
- Owner remains the sole decision-maker
