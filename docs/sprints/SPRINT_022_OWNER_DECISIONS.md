# Sprint 022 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 021: COMPLETE
> Sprint 022: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Investment Knowledge Graph

### OD-22-1 — Entity Types

**Question:** What entities should the knowledge graph track?

**Entity types (recommended):**
- Companies (AAPL, MSFT, GOOGL)
- ETFs (VOO, QQQ, TLT)
- Sectors (Technology, Healthcare, Financials)
- Themes (AI, Cloud, Electric Vehicles)
- Memos (individual research outputs)
- Decisions (owner actions on memos)
- Sources (Alpha Vantage, SEC filings, earnings calls)

**Recommendation:** Start with companies + sectors + memos + decisions.
Build out to ETFs and themes in subsequent sprints. Don't over-engineer
the first graph.

---

### OD-22-2 — Relationship Types

**Question:** What relationships should be modeled?

**Edge types (recommended):**
- `BELONGS_TO` — company → sector
- `ANALYZED_IN` — company → memo
- `LED_TO` — memo → decision
- `SUPERSEDES` — memo v1 → memo v2 (new analysis on same symbol)
- `CONTRADICTS` — memo A contradicts memo B
- `CORRELATES_WITH` — company A correlates with company B
- `HOLDS` — ETF → underlying company

**Recommendation:** Start with 4 core edges (BELONGS_TO, ANALYZED_IN,
LED_TO, SUPERSEDES). Add more as the graph proves valuable.

---

### OD-22-3 — Knowledge Update Rules

**Question:** How does the graph stay current?

**Method:**
- Append-only — new memos and decisions add nodes and edges
- Never modify historical nodes
- Superseded memos remain in the graph (for provenance)
- Contradiction edges are added, old edges are preserved

**Recommendation:** Immutable history with versioning. Every analysis is
a time-stamped snapshot in the graph.

---

## Slice B — Advanced AI Committee

### OD-22-4 — Model Assignment

**Question:** Which models should handle which perspectives?

**Assignment (recommended):**
- Value → Claude (strong analytical reasoning)
- Growth → GPT-4o (broad knowledge, trend awareness)
- Risk → Claude (careful, conservative)
- Macro → GPT-4o (current events, economic context)
- Policy → Claude (rule-following, structured)
- Portfolio Fit → Gemini (alternative perspective for diversity)

**Rationale:** Multi-model diversity reduces single-model bias. If Claude
and GPT-4o disagree, the Owner benefits from both perspectives.

---

### OD-22-5 — Divergence Handling

**Question:** What happens when models disagree significantly?

**Threshold:** Confidence difference >20 points between models.

**Response:**
- Flag as "model divergence" in the memo
- Include both perspectives with their respective confidence scores
- Committee synthesis note: "Value (Claude/75) and Growth (GPT-4o/55)
  disagree significantly on this thesis."
- Owner decides which analysis to trust more

---

## Slice C — Portfolio Monitoring

### OD-22-6 — Monitoring Triggers

**Question:** What events should trigger the Owner's attention?

**Triggers (recommended):**
- Price movement >5% in a single day (held position)
- Earnings report within 7 days (held position)
- Dividend announcement (held position)
- Sector rotation signal (tech → energy shift)
- News sentiment spike (positive or negative, held position)
- Research staleness >90 days (held position, no recent memo)

---

### OD-22-7 — Alert Priority

**Question:** How should alerts be prioritized?

**Priority levels (recommended):**
- **Critical:** Price >10% movement, thesis-invalidating news
- **High:** Earnings within 7 days, research >90 days stale
- **Medium:** Dividend announcement, sector rotation
- **Low:** General news, market commentary

**Display:** Dashboard badge with count by priority level.

---

## Slice D — Family Office Layer

### OD-22-8 — Multi-Portfolio Structure

**Question:** How should multiple portfolios be organized?

**Structure (recommended):**
- Default: "Main Portfolio" (taxable brokerage)
- Optional: "Retirement" (IRA), "Trust" (irrevocable trust)
- Consolidated view across all portfolios
- Per-portfolio: holdings, allocation, performance, research

**Tax lots:** Track purchase date + cost basis per position for
tax-aware selling guidance. Informational only — not tax advice.

**Advisor role:** Read-only access to portfolios + research. Cannot
approve decisions, modify policies, or execute actions.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-22-1 | A | Entity types | Companies, sectors, memos, decisions |
| OD-22-2 | A | Relationships | BELONGS_TO, ANALYZED_IN, LED_TO, SUPERSEDES |
| OD-22-3 | A | Updates | Append-only, immutable history |
| OD-22-4 | B | Model assignment | Claude/Value+Risk+Policy, GPT-4o/Growth+Macro, Gemini/Fit |
| OD-22-5 | B | Divergence | Flag >20pt spread, show both perspectives |
| OD-22-6 | C | Triggers | Price, earnings, dividends, sector, news, staleness |
| OD-22-7 | C | Priority | Critical/High/Medium/Low |
| OD-22-8 | D | Multi-portfolio | Default + optional IRA/Trust, advisor read-only |

---

## Architecture Preservation

All Sprint 012-021 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
- Alerts inform, never execute
