# Sprint 014 — Design Direction
# CompoundOS V1 Usability Phase

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 013: COMPLETE (all 4 slices done)
> Sprint 014: DESIGN ONLY

---

## Objective

Sprint 014 transitions CompoundOS from a working AI-research prototype
to a genuine V1 product usable by the Owner on a daily basis. Sprint 013
proved AI can produce structured investment memos with governed LLM
calls and provenance. Sprint 014 makes that capability accessible,
deployable, and contextualized within the Owner's actual portfolio.

---

## Slice A — Production Foundation

### Scope
Transform CompoundOS from a local-only FastAPI service into a deployed
production system the Owner can access from anywhere.

### Key Decisions

| Decision | Recommendation |
|---|---|
| VPS provider | Hetzner CX22 or similar (~$5/mo) — single VM is sufficient for a solo-Owner system |
| OS | Ubuntu 22.04 LTS (matches macOS Python 3.9 toolchain) |
| PostgreSQL | Managed (Supabase free tier) or self-hosted on the same VM |
| Deployment | Docker Compose — single docker-compose.yml with API + DB |
| HTTPS | Caddy reverse proxy with auto-LetsEncrypt |
| Secrets | `.env` file, never committed; future: Doppler/Hashicorp Vault |
| Backup | pg_dump cron to local + S3-compatible (Backblaze B2 ~$0.005/GB) |
| Monitoring | Healthcheck endpoint + UptimeRobot (free) |
| Error tracking | Sentry free tier |

### What makes this "V1"
- The Owner can access CompoundOS from any browser
- The API is protected by HTTPS
- Data is backed up daily
- Failures are visible (not silent)

---

## Slice B — Owner Dashboard

### Scope
A minimal web UI for the Owner to interact with CompoundOS without
using the terminal or reading raw JSON.

### Pages

1. **Home / Portfolio Overview**
   - Current holdings (read-only from existing data)
   - Last research run status
   - Pending committee decisions

2. **Research Queue**
   - "New Research Request" button
   - Symbol input (e.g., "AAPL")
   - Status: queued / running / complete
   - Last N research runs with status

3. **Investment Memo View**
   - Full 11-section memo rendered as readable HTML
   - Confidence score visualization
   - Committee votes summary
   - Owner decision buttons: APPROVE / REJECT / MODIFY

4. **Committee Decisions**
   - All decisions sorted by date
   - Filter by: pending / approved / rejected
   - Learning loop: scheduled reviews, outcomes

5. **Learning Dashboard**
   - Prediction accuracy over time
   - Perspective performance (which perspectives were right)
   - Knowledge memory entries by entity

### Tech Stack
- **Frontend**: Plain HTML + HTMX (no SPA framework needed for solo-Owner use)
- **Templating**: Jinja2 (already in FastAPI)
- **CSS**: Pico.css or simple CSS (dark theme preferred)

---

## Slice C — First Real Investment Workflow

### Scope
Execute the complete research-to-decision workflow with real external
data for the first time. Sprint 013 built the engine; Slice C starts it.

### Workflow

```
Owner enters symbol (e.g., "AAPL") in dashboard
        ↓
POST /api/research/start {"symbol": "AAPL"}
        ↓
AlphaVantageProvider.fetch() ← real market data
        ↓
DatabaseKnowledgeProvider.query() ← historical context
        ↓
6 AI perspectives execute (governed LLM calls)
        ↓
MemoGenerator synthesizes 11-section memo
        ↓
ConfidenceEngine scores (deterministic)
        ↓
Memo displayed in dashboard
        ↓
Owner reviews → APPROVE / REJECT / MODIFY
        ↓
Decision recorded → review scheduled
```

### Requirements
- The workflow must complete from symbol input to memo display
- All LLM calls must go through GovernedLLMExecutor
- All market data must carry provenance
- Owner must see the full provenance chain

---

## Slice D — Portfolio Intelligence

### Scope
Contextualize individual research within the Owner's actual portfolio.
An investment in AAPL means something different if already holding
$100K of tech vs. starting fresh.

### Features

1. **Holdings Context**
   - When researching AAPL, show current position (shares, cost basis)
   - Highlight concentration risk (e.g., "Tech is 60% of portfolio")

2. **Allocation**
   - Current allocation by sector/asset class
   - Proposed allocation after investment
   - Rebalancing suggestions (AI-generated, Owner-reviewed)

3. **Concentration**
   - Single-stock concentration > threshold → flag
   - Sector concentration > threshold → flag
   - Geographic concentration (if data available)

4. **Correlation**
   - Simple 2-stock correlation matrix
   - Portfolio-level beta estimate
   - "If you add AAPL, portfolio beta changes from X to Y"

5. **Position Impact Sizing**
   - "Adding $X of AAPL = Y% of portfolio"
   - "This changes your allocation from A to B"
   - Guardian evaluation: does this comply with policy?

### Constraints
- Read-only portfolio data (no trading)
- AI suggests, Owner decides
- No broker connection for real-time values (use cached market data)

---

## Owner Decisions Required

See `docs/sprints/SPRINT_014_OWNER_DECISIONS.md`.

Estimated decisions: 6-8 covering:
- Deployment target (VPS provider)
- Dashboard technology (HTMX/Pico.css vs React/etc)
- Whether to use real market data in V1 (vs continued mock)
- Portfolio data source (manual entry vs broker import)
- UI authentication method
- Backup strategy
- Monitoring threshold preferences
- First real investment symbol

---

## Architecture Preservation

All Sprint 013 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
