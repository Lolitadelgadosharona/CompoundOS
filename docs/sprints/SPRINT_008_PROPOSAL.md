# Sprint 008 — Proposal

> **STATUS: PLANNING — IMPLEMENTATION NOT AUTHORIZED**
>
> This document proposes candidate directions for Sprint 008.
> All Open Questions require Owner resolution.
> Implementation is NOT AUTHORIZED until each Slice receives explicit Owner approval.

---

## 1. Baseline

| Item | Value |
|------|-------|
| Main HEAD | 2f4f12569ae702fcbcc9a0bb01b199d68fe26327 |
| PR #66 squash merge | 2f4f125 (2026-07-22) |
| Migration head | 0016_notification_integrity |
| PG tests | 552 passed, 0 failed, 0 skipped |
| Non-PG tests | 134 passed, 2 expected skipped |
| Frontend tests | 251 passed (14 test files) |
| Main CI | 29888368096 (3/3 success) |
| Sprints 001–007 | Done |
| Sprint 008 implementation | NOT AUTHORIZED |

---

## 2. Current State — What Sprint 001–007 Delivered

### 2.1 Complete Capabilities

| Domain | What's Built |
|--------|-------------|
| Household | Single-household profile, audit timeline |
| Investment Policy | Draft/edit/publish lifecycle, immutable versions, allocations |
| Decision Journal | Drafts, confirmed snapshots, corrections, audit |
| Portfolio | Snapshots with holdings, confirm/discard, immutable history |
| Guardian Monitoring | Breach, category exposure, staleness checks; manual trigger |
| Automation | Worker, schedules, leases, fencing, manual trigger |
| AI Committee | Evidence pipeline, DeepSeek adapter, 7 perspectives, 9 API routes |
| Backup/Export | pg_dump→age, JSON/CSV export, 7+4+12 retention, restore verification |
| Health Dashboard | 10 components, 5-state model, mutation gate, 3 endpoints |
| Notification | Explicit opt-in, macOS adapter, structured templates, household dedup |
| Safe Autopilot | Self-driving infrastructure, blind review, CI monitoring |

### 2.2 Capabilities Defined But Not Wired

| Source | Templates Defined | Actually Delivers Notifications? |
|--------|-------------------|----------------------------------|
| health | YES | **YES** — wired via run_all_checks |
| guardian | YES | NO — service never calls dispatch_notification |
| committee | YES | NO — orchestrator never dispatches |
| automation | YES | NO — worker never dispatches |
| backup | YES | NO — no dispatch integration |

### 2.3 Daily-Use Gaps

1. **No scheduled Guardian evaluation**: Guardian has manual trigger only. No automated daily monitoring.
2. **No automated Committee runs**: Committee is manual-only. No scheduled session creation.
3. **No portfolio valuation updates**: Snapshots capture allocations only. No price/value tracking.
4. **No daily dashboard**: No single page summarizing all systems at a glance.
5. **Docker runtime unverified**: Compose stack never tested end-to-end.
6. **No notification source wiring beyond health**: 4 of 5 defined sources deliver zero notifications.

### 2.4 Technical Debt & Backlog

| Item | Priority |
|------|----------|
| Docker runtime verification | Medium |
| AuditEvent pagination | Low (current volume is small) |
| Policy schema regression coverage | Medium |
| Alembic path_separator standardization | Low |
| Policy POST null vs. omitted body | Low |
| Policy Backlog tightening (non-blocking) | Low |
| Test isolation hardening (info_schema coverage) | Low |
| Frontend path validation | Medium |

---

## 3. Candidate Directions

### CANDIDATE A: Notification Source Wiring + Daily Operations

**User problem**: CompoundOS has monitoring (Guardian), automation (Worker), committee, and backup — but none of them tell the Owner when something happens. The system is silent.

**User value**: The Owner can rely on CompoundOS for daily awareness. Guardian breaches, committee completions, backup failures, and automation errors produce macOS notifications. Daily schedules automate Guardian evaluation and backup.

**Why now**: The notification infrastructure (Sprint 007) was built specifically for this. Templates already exist. Health is already wired — extending to the remaining 4 sources is the natural next step. Without source wiring, Sprint 007 notification delivers value only for health degradation.

**Scope**:
- Wire guardian → dispatch_notification() on threshold breach detection
- Wire committee → dispatch_notification() on session completion
- Wire automation → dispatch_notification() on run failure
- Wire backup → dispatch_notification() on backup completion/failure
- Create daily Guardian evaluation schedule (default disabled)
- Create daily backup schedule (default disabled)
- Test each wired source end-to-end

**Non-scope**:
- No new notification templates outside approved (source, event_type) pairs
- No external notifications (email/SMS/push)
- No automatic schedule enabling
- No Guardian threshold changes
- No new investment rules

**Impact**:
- Backend: 4 service files modified (guardian, committee, automation, backup)
- Frontend: minor — notification history already exists
- DB: no schema changes (notification_events already supports all sources)
- No new external dependencies

**Risks**:
- Low: templates already defined, dispatch_notification already tested
- Guardian/committee may need transaction boundary awareness (notification must not roll back with caller's transaction)

**Suggested Slices**:
- Slice A (R2): Guardian + Backup source wiring (migration if needed, contract tests)
- Slice B (R2): Committee + Automation source wiring + daily schedules
- Slice C (R1): Frontend — schedule enable/disable for Guardian + Backup

**Estimate**: Small-medium. Mostly wiring existing components together.

**Cost of NOT choosing**: Sprint 007 notification delivers value for only 1 of 5 defined sources. 80% of notification capability remains unused.

---

### CANDIDATE B: Personal V1 Completion — Daily Dashboard + Portfolio Valuation

**User problem**: The Owner can create policies, portfolios, and decisions — but cannot see their financial state at a glance. Portfolio snapshots have no valuation. There is no single-page daily summary.

**User value**: CompoundOS becomes a daily-use tool. The Owner opens one page and sees: current portfolio, recent Guardian status, latest committee report, backup health, and notification history.

**Why now**: All foundational data exists. The portfolio, guardian, committee, automation, and notification systems are built. A dashboard aggregates what's already there.

**Scope**:
- Daily dashboard page (/dashboard) aggregating: portfolio summary, Guardian status, committee summary, health overview, notification history
- Portfolio valuation: manual price entry per holding, total_value computation
- Valuation history: track value over time
- Each dashboard section links to its detail page

**Non-scope**:
- Automated price feeds (market data V2)
- Performance calculations (IRR, TWR)
- Benchmark comparison
- Rebalancing suggestions
- Any trading capability

**Impact**:
- Backend: new aggregation endpoints, valuation service
- Frontend: new /dashboard page, valuation entry
- DB: portfolio_valuations table (migration 0017)
- No new external dependencies

**Risks**:
- Medium: valuation introduces financial computation (ROUND_HALF_EVEN, decimal precision)
- Portfolio value display must remain non-advisory

**Suggested Slices**:
- Slice A (R2): portfolio_valuations migration + valuation service
- Slice B (R2): dashboard aggregation API endpoints
- Slice C (R1): /dashboard frontend + valuation entry UI

**Estimate**: Medium. New schema + significant frontend work.

**Cost of NOT choosing**: The Owner cannot see their financial state without manually opening 5+ separate pages. CompoundOS remains a toolkit, not a dashboard.

---

### CANDIDATE C: Quality & Stability — Hardening Sprint

**User problem**: Technical debt accumulates. Docker never verified. Backlog items pile up. Test isolation has gaps. The platform works but hasn't been stress-tested.

**User value**: CompoundOS becomes demonstrably reliable. Docker verification proves the stack works on any machine. Backlog cleanup reduces future implementation risk.

**Why now**: After 7 sprints of feature delivery, a hardening sprint protects the investment. Clean foundation before Phase 2.

**Scope**:
- Complete Docker runtime verification (compose up, end-to-end smoke test)
- Fix AuditEvent pagination design
- Strengthen Policy schema regression coverage
- Alembic path_separator standardization
- Policy POST null vs omitted body decision
- Frontend path validation with Docker stack
- Test isolation: info_schema coverage hardening
- Verify all CI paths produce identical results locally vs. CI

**Non-scope**:
- No new product features
- No schema changes (unless required by hardening)
- No new endpoints or frontend pages

**Impact**:
- Backend: test improvements, minor fixes
- Frontend: path validation
- Infrastructure: Docker, CI alignment
- No new external dependencies

**Risks**:
- Low: all work is within existing boundaries
- Docker verification may expose hidden issues

**Suggested Structure**: Single-slice hardening sprint (no A/B/C decomposition)

**Estimate**: Small. Primarily testing and configuration.

**Cost of NOT choosing**: Technical debt grows. Docker remains unverified. Backlog items age.

---

### CANDIDATE D: Source Wiring + Daily Dashboard (Combined A+B, Reduced Scope)

**User problem**: The Owner needs both awareness (notifications) and visibility (dashboard). Neither alone makes CompoundOS daily-usable.

**User value**: A single sprint that closes the remaining Personal V1 gap. Notifications fire on real events. Dashboard shows everything at a glance.

**Why now**: This is the last piece of the Personal V1 puzzle. After this, the Owner can use CompoundOS daily: open dashboard, see status, receive notifications when things change.

**Scope** (reduced from full A+B):
- Wire all 4 pending notification sources (guardian, committee, automation, backup)
- Daily dashboard page: portfolio summary + Guardian status + health summary + notification history (3 cards)
- Defer portfolio valuation to future sprint
- Defer daily schedules to future sprint

**Non-scope**:
- Portfolio valuation (price entry, value tracking)
- Daily schedules (Guardian/backup automation)
- External notifications
- Market data
- Trading

**Suggested Slices**:
- Slice A (R2): Notification source wiring (all 4 sources)
- Slice B (R2): Dashboard aggregation API
- Slice C (R1): /dashboard frontend

**Estimate**: Medium. Source wiring is small; dashboard is new frontend work.

**Cost of NOT choosing**: Neither notifications nor dashboard exist. The Owner has 7 sprints of infrastructure with no daily workflow.

---

## 4. Recommendation

**RECOMMENDED — OWNER DECISION REQUIRED**

**Recommendation: Candidate A — Notification Source Wiring + Daily Operations**

**Rationale:**

1. **Closes the highest-value gap with lowest risk.** Sprint 007 built the notification infrastructure explicitly for this purpose. Templates already exist for all 5 sources. Wire-up is mostly adding `dispatch_notification()` calls at natural completion/failure points.

2. **Makes Sprint 007 investment pay off.** The notification system (PR #64 + #65) was a significant effort — explicit opt-in, AppleScript safety, household dedup, advisory locks, privacy previews. Currently it delivers value for only 1 of 5 sources. Wiring the remaining 4 sources multiplies the return on that investment.

3. **Does not require new schema.** No migration needed. notification_events already supports all sources and severities. The CHECK constraints, templates, and dispatch pipeline are already built and tested.

4. **Preserves personal-use boundaries.** No external services, no market data, no new credentials, no V2 scope creep.

5. **Natural next step after Sprint 007.** Sprint 007 closeout explicitly records guardian/committee/automation/backup sources as "templates defined, not yet wired." This is the obvious follow-up.

**Owner decisions required before implementation:**
- Should daily schedules (Guardian evaluation, backup) be part of this sprint or deferred?
- Should any source remain intentionally unwired (e.g., committee if the Owner prefers manual-only)?
- What severity level should each wired source use?

**What Candidate A does NOT solve:**
- No portfolio valuation (deferred)
- No daily dashboard (deferred)
- No Docker verification (backlog)
- No technical debt cleanup (backlog)

---

## 5. Preliminary Slice Structure (Candidate A)

### Slice A — Guardian + Backup Source Wiring (R2)
- Guardian evaluation dispatches notification on threshold breach
- Backup pipeline dispatches on completion/failure
- Contract tests: verify dispatch_notification called at correct points
- Verify notification failure does not roll back Guardian evaluation or backup
- Migration if needed (likely none)

### Slice B — Committee + Automation Source Wiring (R2)
- Committee orchestrator dispatches on session completion
- Automation worker dispatches on run failure
- Daily Guardian evaluation schedule (default disabled)
- Daily backup schedule (default disabled)
- Contract tests

### Slice C — Frontend (R1)
- Minimal: schedule enable/disable UI for new daily schedules
- Notification history already available at /notifications
- No new pages required

---

## 6. Owner Decision Gate

Before any implementation begins, the Owner must resolve all Open Questions documented in `SPRINT_008_OPEN_QUESTIONS.md`.

Key decisions:
- Sprint direction (Candidate A, B, C, D, or Owner-defined alternative)
- Daily schedule scope (include or defer)
- Source wiring scope (all 4 or subset)
- Severity assignments per source
- Whether to include any dashboard work

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Notification failure rolls back caller's transaction | Low | HIGH | Fire-and-forget pattern; test with real transaction boundaries |
| Guardian threshold noise → notification spam | Low | MEDIUM | Dedup window (24h) + severity escalation already in place |
| Daily schedules create unwanted automation | Low | MEDIUM | Default disabled; explicit opt-in per schedule |

---

## 8. Explicit Non-Goals

- No external notifications (email, SMS, push) → V2
- No Market Data integration → V2
- No Cloud backup → V2
- No Family Goals & Reporting → V2
- No portfolio valuation
- No investment rule changes
- No Guardian threshold changes
- No automatic trading
- No new credentials or external services
