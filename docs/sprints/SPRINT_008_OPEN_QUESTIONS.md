# Sprint 008 — Open Questions

> **STATUS: ALL OPEN — OWNER DECISIONS REQUIRED**
>
> Each question blocks implementation until resolved.
> No question is pre-resolved. All answers require explicit Owner approval.

---

## OD-8-1: Sprint 008 Direction

**Question**: Which candidate direction should Sprint 008 pursue?

| Option | Description |
|--------|-------------|
| A | Notification Source Wiring + Daily Operations — wire all 4 pending notification sources, add daily Guardian/Backup schedules |
| B | Personal V1 Completion — Daily Dashboard + Portfolio Valuation |
| C | Quality & Stability — Hardening, Docker, Backlog Cleanup |
| D | Combined A+B (reduced scope) — source wiring + simple dashboard, defer valuation |

**Recommended**: Option A — Notification Source Wiring + Daily Operations.

**Rationale**: Lowest risk, highest ROI on Sprint 007 investment. No new schema. No external dependencies. Directly addresses the #1 gap: 4 of 5 notification sources are silent.

**Blocked if unresolved**: All implementation. Sprint direction is the root decision.

---

## OD-8-2: Daily Schedule Scope

**Question**: Should daily Guardian evaluation and backup schedules be included in Sprint 008?

| Option | Description |
|--------|-------------|
| A | Include daily Guardian evaluation schedule (default disabled) and daily backup schedule (default disabled) |
| B | Defer daily schedules to a future sprint; Sprint 008 only wires notification sources |
| C | Include backup schedule only; defer Guardian schedule |

**Recommended**: Option A — include both schedules, default disabled.

**Rationale**: Notification source wiring without automation means notifications only fire on manual triggers. Daily schedules make the wired sources actually produce events. Default-disabled preserves explicit opt-in.

**Blocked if unresolved**: Backend scope in Slice B.

---

## OD-8-3: Source Wiring Completeness

**Question**: Which notification sources should be wired in Sprint 008?

| Option | Description |
|--------|-------------|
| A | Wire all 4 pending sources: guardian, committee, automation, backup |
| B | Wire guardian + backup only; defer committee + automation |
| C | Wire guardian only (highest-value first); defer others |
| D | Wire all 4 + add any Owner-requested additional sources |

**Recommended**: Option A — wire all 4 pending sources.

**Rationale**: Templates exist for all 4. The dispatch pipeline is tested. Wire-up is mechanical — each source adds a `dispatch_notification()` call at a well-defined completion/failure point. Partial wiring creates an inconsistent experience.

**Blocked if unresolved**: Which service files to modify.

---

## OD-8-4: Severity Assignments

**Question**: What severity should each wired source use for its primary notification?

| Source | Event | Candidate Severities |
|--------|-------|---------------------|
| guardian | threshold_breach | warning / critical |
| committee | session_complete | info |
| automation | run_failed | warning / critical |
| backup | backup_complete | info |
| backup | backup_failed | warning / critical |

**Recommended**: guardian=warning, committee=info, automation=warning, backup_complete=info, backup_failed=warning.

**Rationale**: Critical should be reserved for health degradation (already wired). Guardian breach is warning (actionable, not system-down). Committee completion is informational.

**Blocked if unresolved**: Template severity values in NOTIFICATION_TEMPLATES.

---

## OD-8-5: Committee Notification Scope

**Question**: The AI Committee is currently manual-only (no auto-trigger, no auto-run). Should committee notification wiring wait until the committee can run automatically, or wire now for manual sessions?

| Option | Description |
|--------|-------------|
| A | Wire now — dispatch on manual session completion. Useful when Owner manually runs committee and wants notification when done |
| B | Defer until Committee has scheduled/automatic runs. Manual sessions don't need notifications |

**Recommended**: Option A — wire now for manual sessions.

**Rationale**: Even manual sessions can take minutes (LLM call). A notification when complete lets the Owner do other work. No additional infrastructure needed.

**Blocked if unresolved**: Whether to include committee in Slice B.

---

## OD-8-6: Transaction Boundary Strategy

**Question**: Guardian evaluation and backup both run inside transactions. If notification dispatch fails, what should happen?

| Option | Description |
|--------|-------------|
| A | Fire-and-forget: always dispatch after the business transaction commits. Notification failure never rolls back the business operation |
| B | Same-transaction: dispatch inside the business transaction. Notification failure rolls back both |
| C | Two-phase: commit business first, then dispatch in separate transaction. If dispatch fails, log but don't roll back |

**Recommended**: Option A — fire-and-forget after business transaction commit.

**Rationale**: This is the pattern already used by run_all_checks (health dispatch). Notification is an ancillary concern — backup data and Guardian evaluations must not be lost because osascript wasn't available.

**Blocked if unresolved**: Implementation pattern for each source.

---

## OD-8-7: Dashboard Inclusion

**Question**: Should Sprint 008 include any dashboard/aggregation work alongside source wiring?

| Option | Description |
|--------|-------------|
| A | No dashboard work. Pure source wiring sprint |
| B | Minimal: add a "System Status" card to the existing /notifications page — shows last Guardian evaluation, last backup, health summary |
| C | Full /dashboard page with portfolio summary, Guardian status, health, notifications |

**Recommended**: Option A — no dashboard work. Keep Sprint 008 focused on source wiring.

**Rationale**: Dashboard is independently valuable but adds scope (new endpoints, new frontend page). Can be its own sprint. Source wiring alone significantly improves daily usability via notifications.

**Blocked if unresolved**: Frontend scope in Slice C.

---

## OD-8-8: Sprint 008 Decomposition

**Question**: How should Sprint 008 be decomposed into slices?

| Option | Description |
|--------|-------------|
| A | Standard 3-slice: A (DB+migration if needed + Guardian+Backup wiring), B (Committee+Automation wiring + schedules), C (Frontend) |
| B | 2-slice: A (all backend wiring + schedules), B (Frontend) |
| C | Single slice: all source wiring + minimal frontend in one PR |

**Recommended**: Option B — 2 slices (backend then frontend).

**Rationale**: No migration expected. Backend work is mechanical wire-up across 4 services + schedule creation. Frontend is minimal (schedule enable/disable UI). 3 slices would over-decompose.

**Blocked if unresolved**: Branch and PR structure.

---

## Implementation Boundary

All 8 Owner Decisions must be resolved before any implementation begins.

After resolution:
1. Update SPRINT_008_PROPOSAL.md with resolved decisions
2. Create detailed Technical Design for the chosen direction
3. Each Slice requires separate explicit Owner authorization

Sprint 008 implementation: NOT AUTHORIZED.
