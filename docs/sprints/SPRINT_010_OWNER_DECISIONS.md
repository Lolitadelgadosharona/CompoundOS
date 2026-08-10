# Sprint 010 — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 010 Design: APPROVED (3e1b73a)
> 5 decisions require Owner review before implementation begins.
>
> Once decisions are recorded, implementation proceeds in order:
> Slice A → Slice B → Slice C → Slice D.

---

## OD-10-1: Dashboard Computation Strategy

### Question
Should the Wealth Dashboard compute portfolio metrics on every load, or should
results be cached?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Compute live** | Every GET /api/dashboard runs fresh SQL aggregates against current portfolio data | Always accurate; no cache invalidation; simple implementation | May be slow on very large portfolios (100+ positions) |
| **B: Cache with TTL** | Compute results; cache for N minutes; refresh on next load after expiry | Fast response for repeated loads; reduced DB load | Stale data risk; cache invalidation complexity; must bust cache on import |

### Architecture Impact
- Option A: No schema changes. Dashboard service calls repository queries directly.
- Option B: Requires cache layer (in-memory dict or Redis). Must wire cache invalidation into import pipeline and Guardian evaluation.

### Recommendation
**Option A — Compute live.** For a family-office portfolio (typically <100
positions), PostgreSQL aggregate queries are sub-millisecond. Cache
invalidation is a common source of bugs. If performance becomes an issue,
add caching later as a non-breaking optimization.

### Owner Decision
- [ ] APPROVE — Option A (Compute live)
- [ ] APPROVE — Option B (Cache with TTL)
- [ ] OTHER (specify): _______________

---

## OD-10-2: Post-Decision Review Scheduling

### Question
Should post-decision reviews (30d, 90d, 1yr) be mandatory for every confirmed
decision, or optional at the Owner's discretion?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Optional** | Owner chooses whether to schedule reviews when confirming a decision | Respects Owner autonomy; no forced process | Some decisions may never be reviewed; learning loop incomplete |
| **B: Mandatory** | Every confirmed decision automatically schedules 30d, 90d, 1yr reviews | Complete learning loop; system ensures nothing falls through | May feel bureaucratic; Owner may ignore scheduled reviews anyway |
| **C: Tiered** | Decisions above a configurable threshold (e.g. >5% of portfolio) get mandatory reviews; smaller decisions are optional | Balanced approach; important decisions tracked, small ones flexible | Adds complexity; threshold must be configured |

### Architecture Impact
- Option A: review_30d/90d/1yr columns are nullable; scheduling via optional POST
- Option B: columns NOT NULL; auto-populated on decision confirmation
- Option C: same as B but gated on allocation_pct threshold check

### Recommendation
**Option A — Optional.** CompoundOS is an Owner-driven system. Mandatory
processes that aren't respected become noise. The system should offer reviews
as a tool, not an obligation. The learning loop remains available for every
decision; the Owner decides which ones merit formal review.

### Owner Decision
- [ ] APPROVE — Option A (Optional)
- [ ] APPROVE — Option B (Mandatory)
- [ ] APPROVE — Option C (Tiered)
- [ ] OTHER (specify): _______________

---

## OD-10-3: API Key Authentication

### Question
Should Sprint 010 implement API key authentication for OWNER_MUTATION
endpoints, or defer to a dedicated security sprint?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Implement in Slice D** | Add API key middleware in Sprint 010 Slice D; all mutation endpoints gated | Security boundary in place early; paves way for broker connectors | Adds ~150 lines to an already-full sprint; all tests need API key header |
| **B: Defer to Sprint 011** | Document auth design in Sprint 010; implement as Sprint 011 Slice A | Sprint 010 stays focused on intelligence features; no test overhead | Security gap persists; no defense against unauthorized mutations until Sprint 011 |
| **C: Minimal — one endpoint** | Add API key to import endpoints only (highest risk — CSV ingestion) | Protects data ingestion; smaller scope (~50 lines) | Inconsistent auth coverage; other mutation endpoints unprotected |

### Architecture Impact
- Option A: New middleware file; env var COMPOUNDOS_API_KEY; all test fixtures
  updated to include X-API-Key header; ruff/compliance checks on key presence
- Option B: Auth docs only; no code changes
- Option C: Auth on import router only; pattern established for later expansion

### Recommendation
**Option A — Implement in Slice D.** Slice D is the Security + Notifications
slice. API key auth is its primary deliverable. A single env-var API key is
trivially implementable (~50 lines of middleware + test header fixture).
This closes SEC-002 before any real financial data enters the system.
The compoundos-development skill already documents this as SEC-002.

### Owner Decision
- [ ] APPROVE — Option A (Implement in Slice D)
- [ ] APPROVE — Option B (Defer to Sprint 011)
- [ ] APPROVE — Option C (Import endpoints only)
- [ ] OTHER (specify): _______________

---

## OD-10-4: Committee Review Trigger

### Question
Should submitting an Investment Idea for review automatically create a
Committee session, or should the Owner manually trigger the Committee?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Manual trigger** | Owner explicitly clicks "Request Committee Review"; system creates session | Deliberate decision process; Owner controls timing; no surprise AI activity | Extra step; Owner must remember to trigger |
| **B: Auto-trigger** | Idea status→under_review automatically creates Committee session + evidence | Streamlined workflow; no forgotten reviews | AI runs without explicit Owner action; may create sessions the Owner didn't intend |
| **C: Prompt** | Idea→under_review prompts Owner "Request Committee Review?" with one-click confirm | Middle ground; Owner in control but friction minimized | Additional UI state; requires frontend (not in Sprint 010) |

### Architecture Impact
- Option A: POST /api/ideas/{id}/request-review endpoint (OWNER_MUTATION)
- Option B: Database trigger or service hook on status transition; no Owner
  endpoint needed
- Option C: Requires frontend modal/confirmation; not implementable in
  backend-only Sprint 010

### Recommendation
**Option A — Manual trigger.** CompoundOS is designed for deliberate
decision-making. Auto-triggering AI analysis without explicit Owner
action violates the principle that AI remains advisory and
Owner-initiated. The extra step is intentional friction — it ensures
the Owner consciously requests AI assistance.

### Owner Decision
- [ ] APPROVE — Option A (Manual trigger)
- [ ] APPROVE — Option B (Auto-trigger)
- [ ] APPROVE — Option C (Prompt)
- [ ] OTHER (specify): _______________

---

## OD-10-5: Notification Escalation Channels

### Question
Should Sprint 010 implement email notification delivery, or define the
escalation architecture only (no implementation)?

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| **A: Design only** | Define escalation_rules table and architecture; no email/SMS implementation | Keeps Sprint 010 focused; no external service dependencies | Notifications are in-app only until future sprint |
| **B: Email only** | Implement SMTP email delivery for critical Guardian alerts | Real notification for time-sensitive risks | Requires SMTP config; credential management; email templating; ~300 extra lines |
| **C: Email + SMS design** | Design both channels, implement neither | Full architecture documented; no implementation risk | Same as Option A but with more design artifacts |

### Architecture Impact
- Option A: schema for notification_escalation_rules (design artifact); no
  delivery code
- Option B: SMTP integration; email templates; delivery status tracking;
  credential storage (COMPOUNDOS_SMTP_* env vars)
- Option C: same as A with additional SMS schema notes

### Recommendation
**Option A — Design only.** Sprint 010 already has substantial scope across
4 slices. Email delivery adds credential management, templating, error
handling, and testing complexity. The existing in-app notification system
(Sprint 007/008) is sufficient for V1. Define the escalation architecture
now so the schema is ready when delivery channels are implemented.

### Owner Decision
- [ ] APPROVE — Option A (Design only)
- [ ] APPROVE — Option B (Email implementation)
- [ ] APPROVE — Option C (Both design, neither implemented)
- [ ] OTHER (specify): _______________

---

## Decision Summary

| ID | Topic | Recommendation | Owner Decision |
|---|---|---|---|
| OD-10-1 | Dashboard strategy | Compute live (A) | |
| OD-10-2 | Review scheduling | Optional (A) | |
| OD-10-3 | API key auth | Implement in Slice D (A) | |
| OD-10-4 | Committee trigger | Manual trigger (A) | |
| OD-10-5 | Notification escalation | Design only (A) | |

---

## Post-Decision Process

1. Owner marks each decision above (checkbox or specify OTHER).
2. Agent updates this document with final decisions.
3. Agent updates `docs/MASTER_PLAN.md` with recorded decisions.
4. Implementation begins in decision order (Slice A first).
5. Decisions can be revisited at any time — this is a living document.

---

## AI Authority Reminder

None of the above decisions change the AI authority boundary:

- AI analyzes, summarizes, recommends — NEVER approves, executes, or moves money.
- Owner remains the sole authority for all financial decisions.
- Sprint 010 does not introduce trading, broker connections, or credentials.
