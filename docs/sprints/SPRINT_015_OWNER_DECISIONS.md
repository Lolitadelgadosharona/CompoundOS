# Sprint 015 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 014: COMPLETE
> Sprint 015: DESIGN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 8 decisions required before any implementation.

---

## Slice A — Real Investment Case Validation

### OD-15-1 — First Validation Symbols

**Question:** Which symbols should be used for the first real validation runs?

**Options:**
- A) AAPL, MSFT, GOOGL, BRK.B, JNJ — large-cap, well-understood, diverse sectors
- B) 2-3 symbols only — faster iteration
- C) Owner picks from their actual holdings

**Recommendation:** **A — 5 large-cap symbols.** Diverse sectors (tech, finance, healthcare) give the best cross-section for validating all 6 AI perspectives. Well-understood stocks have ample public data for evidence collection.

---

### OD-15-2 — Evaluation Criteria

**Question:** How do we determine whether an AI-generated memo is "good"?

**Quality dimensions:**
- Thesis clarity: is the argument coherent and well-structured?
- Evidence quality: are sources cited and relevant?
- Risk completeness: are bear case and risks adequately covered?
- Actionability: can an Owner make a decision from this memo?
- Confidence calibration: does the confidence score match conviction?

---

### OD-15-3 — Memo Acceptance Criteria

**Question:** What threshold must a memo meet to be presented to the Owner?

**Options:**
- A) All memos presented — Owner filters (transparency)
- B) Confidence ≥ 50 only (quality gate)
- C) All 6 perspectives must succeed (completeness gate)

**Recommendation:** **A — Present all memos.** The Owner is the final filter. AI should not hide its work. Low-confidence memos are labeled as such but still visible.

---

## Slice B — Dashboard Data Integration

### OD-15-4 — Real Data Sources

**Question:** Where does the dashboard get its data?

**Options:**
- A) Direct DB queries — dashboard reads from PostgreSQL directly
- B) API endpoints — dashboard calls existing FastAPI routes
- C) Hybrid — some DB queries, some API calls

**Recommendation:** **B — API endpoints.** Keeps dashboard thin. Reuses existing service layer. Consistent with Single Source of Truth principle. Dashboard is presentation-only.

---

### OD-15-5 — Refresh Frequency

**Question:** How often should dashboard data refresh?

**Options:**
- A) Page load (static render, manual refresh)
- B) Auto-refresh every 30 seconds (HTMX polling)
- C) WebSocket push (real-time updates)

**Recommendation:** **A — Page load with manual refresh.** Solo-Owner use case doesn't need real-time. HTMX already handles partial updates. Research status can poll on research page only.

---

## Slice C — Async Pipeline Execution

### OD-15-6 — Pipeline Execution Model

**Question:** How should the research pipeline execute asynchronously?

**Options:**
- A) FastAPI BackgroundTasks (simple, same process, no new infra)
- B) Redis queue + separate worker (durable, retry-able)
- C) Thread pool (simple but fragile)

**Recommendation:** **A — FastAPI BackgroundTasks.** Sufficient for V1 solo-Owner use. No new infrastructure. Pipeline completes in <2 minutes (6 LLM calls + data fetch). If we outgrow this, migrate to B in Sprint 016.

---

### OD-15-7 — Pipeline Progress States

**Question:** What progress states should the dashboard display?

**States:**
- pending — request created, not yet executing
- collecting_evidence — fetching market data
- running_perspectives — LLM calls in progress
- generating_memo — synthesizing perspectives
- calculating_confidence — scoring
- complete — memo ready
- failed — pipeline error

---

## Slice D — Personal Workflow Automation

### OD-15-8 — Scheduled Research

**Question:** Which symbols should be auto-researched on a schedule?

**Options:**
- A) Top 5 holdings — research every 90 days
- B) All holdings — research every 30 days
- C) Owner manually triggers only — no automation

**Recommendation:** **C — Manual only for V1.** Automation adds complexity without proven value. Owner triggers research when they want it. Revisit in Sprint 016 after validation.

### OD-15-9 — Notification Channels

**Question:** How should the Owner be notified of completed research?

**Options:**
- A) Dashboard badge only (in-app)
- B) Email notification on completion
- C) Both dashboard + email

**Recommendation:** **A — Dashboard badge.** Email requires SMTP config and adds complexity. Dashboard is the primary interface. Owner checks it at their convenience.

---

## Summary

| ID | Slice | Topic | Recommendation |
|---|---|---|---|
| OD-15-1 | A | Validation symbols | 5 large-cap: AAPL, MSFT, GOOGL, BRK.B, JNJ |
| OD-15-2 | A | Evaluation criteria | Clarity, evidence, risk, actionability, calibration |
| OD-15-3 | A | Memo gate | Present all memos, Owner filters |
| OD-15-4 | B | Data sources | API endpoints (thin dashboard) |
| OD-15-5 | B | Refresh | Page load with manual refresh |
| OD-15-6 | C | Execution model | FastAPI BackgroundTasks |
| OD-15-7 | C | Progress states | 7 states: pending → collecting → running → generating → scoring → complete/failed |
| OD-15-8 | D | Scheduled runs | Manual only for V1 |
| OD-15-9 | D | Notifications | Dashboard badge only |

---

## Architecture Preservation

All Sprint 013-014 governance boundaries remain:
- AI advisory only
- Owner final authority
- No trading
- No broker integration
- PermissionGate authoritative
- All LLM calls through GovernedLLMExecutor
