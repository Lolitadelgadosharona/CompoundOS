# Sprint 022 — Design Direction
# Scale & Intelligence Enhancement

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 021: COMPLETE
> Sprint 022: DESIGN ONLY

---

## Objective

After twelve sprints and 304 tests, CompoundOS is a mature AI family
office. Sprint 022 enhances the intelligence layer: a knowledge graph
connecting entities, an advanced committee with multi-model debate,
expanded portfolio monitoring, and a family office management layer.

---

## Slice A — Investment Knowledge Graph

### Goal
Go beyond per-entity memory to a connected graph of relationships.

### Entities
- Companies (AAPL) → suppliers (TSMC) → sectors (tech) → ETFs (QQQ)
- Memos → decisions → outcomes → accuracy
- Theses → evidence → sources → freshness

### Tasks
- Link companies by supply chain, sector, market cap, geography
- When researching AAPL, surface related TSMC and QQQ context
- Track thesis evolution: "AAPL thesis v1 → v2 → v3 over 18 months"
- Cross-entity insights: "Tech sector sentiment is shifting"

---

## Slice B — Advanced AI Committee

### Goal
Multi-model debate: run the same analysis through different models
and compare outputs.

### Concept
- Claude analyzes value, GPT-4o analyzes growth, Gemini analyzes macro
- Compare confidence scores, identify disagreements
- Surface when models strongly disagree (divergence >20 points)
- Model performance tracking: which model is most accurate?

### Deliverable
Comparison dashboard: model vs. model on same symbol

---

## Slice C — Portfolio Monitoring Expansion

### Goal
Real-time monitoring without real-time trading.

### Additions
- Price alerts: "AAPL moved >5% today"
- Earnings calendar: upcoming reports for held positions
- Dividend tracking: upcoming payments
- News sentiment aggregation (cached, delayed)
- Sector rotation signals

### Constraints
Alerts only. No automated response.

---

## Slice D — Family Office Layer

### Goal
Multi-entity support for real family office operations.

### Additions
- Multiple portfolios (trust, IRA, taxable)
- Consolidated view across all portfolios
- Tax-lot tracking (Specific ID method)
- Document storage (statements, tax forms)
- Multi-user access (Owner + advisor view)

### Constraints
- Read-only for advisor role
- No money movement
- No tax advice (informational only)

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
- Knowledge graph depth and scope
- Multi-model execution budget (cost implications)
- Alert configuration and thresholds
- Multi-portfolio structure
- Advisor access model
