# Sprint 015 — Design Direction
# Real Usage Validation & Refinement

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 014: COMPLETE
> Sprint 015: DESIGN ONLY

---

## Objective

After two sprints of intensive capability building (013: real AI + data,
014: deployment + dashboard), Sprint 015 focuses on making CompoundOS
genuinely usable in daily family office operations. The theme is
**validation, refinement, and polish** — not new architecture.

---

## Slice A — Real Investment Case Validation

### Goal
Execute the complete workflow with real data and real LLM calls for
multiple symbols. Validate that the pipeline produces useful,
actionable investment memos.

### Tasks
- Execute 5-10 real research runs (AAPL, MSFT, GOOGL, BRK.B, JNJ, etc.)
- Compare AI-generated thesis vs. market consensus
- Validate confidence scores against actual outcomes (paper trading)
- Tune perspective prompts based on real output quality
- Document prompt engineering lessons learned

### Deliverable
`docs/validation/SPRINT_015_REAL_CASE_VALIDATION.md`

---

## Slice B — Dashboard Data Integration

### Goal
Wire the dashboard to real database queries instead of static mock data.

### Tasks
- Dashboard: query actual portfolio holdings from DB
- Research: list real research runs with status
- Memo: load actual memo from investment_memos table
- Decisions: query decisions table for pending + history
- Learning: calculate accuracy from decision_reviews data

### Deliverable
Dashboard pages displaying real data

---

## Slice C — Async Pipeline Execution

### Goal
Make the research pipeline truly asynchronous so the Owner can
submit a symbol and see progress updates without blocking.

### Tasks
- Research pipeline runs in FastAPI background task
- Research run status updated: pending → running → complete/failed
- Dashboard polls GET /api/research/{id}/status
- Progress indicators in UI (spinner, step-by-step)
- Error handling visible in dashboard (not silent 500s)

### Deliverable
Non-blocking research workflow with progress UI

---

## Slice D — Personal Workflow Automation

### Goal
Add lightweight workflow automation that fits a family office: scheduled
research runs, periodic portfolio reviews, and automated alerts.

### Tasks
- Daily portfolio snapshot (CSV export backup)
- Scheduled research runs (cron: review AAPL every 90 days)
- Guardian alert review (check policy compliance weekly)
- Email/notification on memo completion
- Learning loop: auto-schedule outcome reviews

### Constraints
- No trading automation
- No broker integration
- All automation is advisory only
- Owner must approve any action

---

## Owner Decisions Required

6-8 decisions covering:
- How many real research runs before declaring pipeline "validated"
- Whether to keep Alpha Vantage free tier or upgrade
- Dashboard data refresh frequency
- Async pipeline: background tasks vs. separate worker process
- Notification channel (email, dashboard, or both)
- Scheduled research: which symbols and how often

---

## Architecture Preservation

- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
