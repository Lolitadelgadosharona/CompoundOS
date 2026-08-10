# Sprint 011 — Design Direction
# AI Investment Committee Intelligence Engine

> **STATUS: DESIGN PREPARATION — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 010: COMPLETE (all 4 slices merged)
> Sprint 011: DESIGN DIRECTION ONLY
>
> This document defines the proposed focus, capabilities, and constraints
> for Sprint 011. No implementation decisions are made here — this is a
> strategic direction document to guide Owner decision-making.

---

## 1. Sprint 011 Objective

Move CompoundOS from **committee infrastructure** (sessions, evidence
items, reports — built in Sprint 006) to **AI-assisted investment research**
— where the AI Committee actively gathers evidence, analyzes investments,
produces structured research, and makes advisory recommendations.

**This is NOT:**
- Autonomous trading or execution
- AI making investment decisions
- External broker integration

**This IS:**
- AI-driven research and analysis
- Evidence gathering and synthesis
- Structured investment memo generation
- Multi-perspective committee reasoning
- Confidence-scored recommendations
- Owner review and override workflow

---

## 2. Proposed Capabilities

### 2.1 Evidence Gathering Engine

The Committee needs evidence to make informed recommendations. Sprint 011
would automate evidence collection:

| Evidence Type | Data Source | Automation |
|---|---|---|
| Company fundamentals | Market data API | Fetch key metrics (P/E, revenue, market cap) |
| Sector analysis | Market data API | Sector performance, trends |
| Macro context | Economic data | Rates, inflation, indices |
| Policy compliance | Internal (policy_rules) | Check proposed idea against active policy |
| Guardian status | Internal (guardian_events) | Current risk posture |
| Historical performance | Internal (positions) | Related positions, past outcomes |
| News/sentiment | News API | Recent headlines, sentiment scores |
| Competitor comparison | Market data API | Peer analysis |

### 2.2 Multi-Perspective Committee Reasoning

Simulate different investment committee "members" each with different
analytical perspectives:

| Perspective | Focus | Questions |
|---|---|---|
| Value Investor | Fundamentals, intrinsic value | "Is this fairly priced? What's the margin of safety?" |
| Growth Investor | Revenue growth, TAM | "What's the growth trajectory? Market size?" |
| Risk Manager | Downside, correlation | "What's the worst case? How does it affect portfolio?" |
| Macro Strategist | Economic context | "Is this the right time? What's the macro backdrop?" |
| Policy Guardian | Compliance, constraints | "Does this fit our policy? Bucket exposure?" |

Each perspective produces a structured analysis with evidence citations.

### 2.3 Structured Investment Memo Generation

AI synthesizes committee analysis into a formal investment memo:

```
INVESTMENT MEMO: [Idea Title]
═══════════════════════════════
1. EXECUTIVE SUMMARY
   - Recommendation (BUY/HOLD/PASS)
   - Confidence score
   - Key thesis in 3 sentences

2. COMPANY/FUND ANALYSIS
   - Business overview
   - Financial health (key metrics)
   - Competitive position

3. INVESTMENT THESIS
   - Why this investment now?
   - Expected return (timeline)
   - Catalyst events

4. RISK ANALYSIS
   - Key risks (ranked by severity)
   - Portfolio impact (concentration, correlation)
   - Worst-case scenario

5. POLICY COMPLIANCE
   - Bucket allocation check
   - Rule compliance
   - Guardian status

6. COMMITTEE DELIBERATION
   - Multi-perspective summary
   - Disagreements noted
   - Consensus/recommendation

7. APPENDICES
   - Data sources
   - Evidence items
   - Calculation methods
```

### 2.4 Confidence Scoring Engine

Move beyond manual confidence levels (LOW/MEDIUM/HIGH in `investment_ideas`)
to a scored model:

| Dimension | Weight | Data Source |
|---|---|---|
| Thesis clarity | 20% | AI assessment |
| Evidence quality | 25% | Evidence count + source quality |
| Risk assessment completeness | 20% | Guardian + risk analysis |
| Policy alignment | 15% | Policy compliance check |
| Historical context | 10% | Past similar decisions |
| Timeliness | 10% | Data freshness |

Composite score → confidence level:
- ≥ 80% → HIGH
- 50-79% → MEDIUM
- < 50% → LOW

### 2.5 Research Memory System

Persist AI-generated research across sessions:

| Memory Type | Storage | Purpose |
|---|---|---|
| Company profiles | Structured JSON | Reusable across ideas for same company |
| Sector analyses | Structured JSON | Reusable for multiple ideas |
| Past decision outcomes | decision_reviews | Learning from history |
| Committee deliberation logs | Committee session data | Audit trail of reasoning |

---

## 3. Owner Review Workflow (Preserved)

```
1. Owner creates Investment Idea
       ↓
2. Owner requests Committee Review
       ↓
3. AI gathers evidence (automated)
       ↓
4. AI produces multi-perspective analysis
       ↓
5. AI generates structured Investment Memo
       ↓
6. Owner reviews memo
       ↓
7. Owner can:
   - Accept recommendation → create Decision
   - Request additional analysis → re-run
   - Override recommendation → create Decision with rationale
   - Reject → archive idea
       ↓
8. Decision recorded with full audit trail
```

---

## 4. Architecture Principles (Unchanged)

| Principle | Enforcement |
|---|---|
| AI advisory only | AI produces analysis + recommendations; Owner decides |
| Owner final authority | All decisions require Owner confirmation |
| No autonomous trading | No trade/order/execution code paths |
| No broker integration | This sprint; deferred to SEC-001 gate |
| Immutable history | Audit trail for all AI analysis |
| Evidence-backed | Every recommendation cites specific evidence |

---

## 5. Dependencies

### 5.1 Internal Dependencies (Satisfied)

| System | Sprint | Status |
|---|---|---|
| Investment ideas | 009-C | DONE |
| Committee sessions/evidence/reports | 006 | DONE |
| Committee bridge | 010-A | DONE |
| Policy rules | 009-B | DONE |
| Guardian events | 004 + 010-B | DONE |
| Dashboard | 010-C | DONE |
| Auth/audit | 010-D | DONE |

### 5.2 External Dependencies (Not Yet Available)

| Dependency | Purpose | Priority |
|---|---|---|
| Market data API | Company fundamentals, prices, sector data | CRITICAL |
| Economic data API | Macro indicators, rates | HIGH |
| News API | Sentiment, headlines | MEDIUM |
| LLM provider | AI analysis engine | CRITICAL |

Dependencies that are NOT available yet MUST be resolved before
implementation begins.

---

## 6. Implementation Slices (Proposed)

| Slice | Focus | Complexity |
|---|---|---|
| A | Evidence gathering engine + market data connector | HIGH |
| B | Multi-perspective reasoning + memo generation | HIGH |
| C | Confidence scoring + research memory | MEDIUM |
| D | Owner review workflow + integration | MEDIUM |

---

## 7. What Sprint 011 Does NOT Include

- Broker account connectivity
- Trading or order execution
- Automatic investment decisions
- Real-time market monitoring (deferred)
- Frontend research UI (separate sprint)
- External notification delivery (deferred per OD-10-5)

---

## 8. Owner Decisions Required

See `docs/sprints/SPRINT_011_OWNER_DECISIONS.md` for the complete list
of decisions required before Sprint 011 implementation can begin.
