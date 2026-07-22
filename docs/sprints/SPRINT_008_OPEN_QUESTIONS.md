# Sprint 008 — Open Questions

> **STATUS: ALL 8 RESOLVED — OWNER DECIDED (2026-07-22)**
>
> All questions resolved. Implementation is NOT AUTHORIZED.
> Each Slice requires separate Owner authorization after Technical Design Gate.

---

## OD-8-1: Sprint 008 Direction

**Question**: Which candidate direction should Sprint 008 pursue?

| Option | Description |
|--------|-------------|
| A | Notification Source Wiring + Daily Operations — wire all 4 pending notification sources, add daily Guardian/Backup schedules |
| B | Personal V1 Completion — Daily Dashboard + Portfolio Valuation |
| C | Quality & Stability — Hardening, Docker, Backlog Cleanup |
| D | Combined A+B (reduced scope) — source wiring + simple dashboard, defer valuation |

> **RESOLVED: Option A — Notification Source Wiring + Daily Operations (2026-07-22)**
>
> Rationale: Lowest risk, highest ROI on Sprint 007 investment. Notification templates already exist for all 5 sources. Wire-up makes Sprint 007 deliver value for 5 sources instead of 1.

---

## OD-8-2: Daily Schedule Scope

**Question**: Should daily Guardian evaluation and backup schedules be included in Sprint 008?

| Option | Description |
|--------|-------------|
| A | Include daily Guardian evaluation schedule and daily backup schedule (default disabled) |
| B | Defer daily schedules; Sprint 008 only wires notification sources |
| C | Include backup schedule only; defer Guardian schedule |

> **RESOLVED: Option A — Include both, default disabled (2026-07-22)**
>
> Rationale: Source wiring without automation means notifications only fire on manual triggers. Daily schedules make wired sources produce real events. Default-disabled preserves explicit opt-in. Owner must explicitly set execution_time, timezone, and enable.

---

## OD-8-3: Source Wiring Completeness

**Question**: Which notification sources should be wired in Sprint 008?

| Option | Description |
|--------|-------------|
| A | Wire all 4 pending sources: guardian, committee, automation, backup |
| B | Wire guardian + backup only; defer committee + automation |
| C | Wire guardian only; defer others |
| D | Wire all 4 + add any Owner-requested additional sources |

> **RESOLVED: Option A — Wire all 4 pending sources (2026-07-22)**
>
> Rationale: Templates exist for all 4. Dispatch pipeline is tested. Wire-up is mechanical — each source adds a `dispatch_notification()` call at a well-defined point. Wiring a source ≠ default notification; existing enabled_sources/enabled_severities still gate actual delivery.

---

## OD-8-4: Severity Assignments

**Question**: What severity should each wired source use?

| Source | Event | Options |
|--------|-------|---------|
| guardian | threshold_breach | info / **warning** / critical |
| committee | session_complete | **info** / warning |
| automation | run_failed | info / **warning** / critical |
| backup | backup_complete | **info** / warning |
| backup | backup_failed | info / **warning** / critical |

> **RESOLVED (2026-07-22):**
> - guardian threshold_breach: **warning**
> - committee session_complete: **info**
> - automation run_failed: **warning**
> - backup completed: **info**
> - backup failed: **warning**
>
> Rationale: Critical reserved for health degradation (already wired). Guardian breach is warning (actionable, not system-down). Committee completion is informational. No new critical mappings added. Guardian thresholds and breach criteria unchanged.

---

## OD-8-5: Committee Notification Scope

**Question**: Wire committee notification now (manual sessions) or defer until committee has automatic runs?

| Option | Description |
|--------|-------------|
| A | Wire now — dispatch on manual session completion. Useful when Owner manually runs committee and wants notification when done |
| B | Defer until Committee has scheduled/automatic runs |

> **RESOLVED: Option A — Wire now for manual sessions (2026-07-22)**
>
> Rationale: Even manual sessions can take minutes (LLM call). A notification when complete lets the Owner do other work. No additional infrastructure needed. No automatic committee runs or investment decisions.

---

## OD-8-6: Transaction Boundary Strategy

**Question**: What happens if notification dispatch fails inside a business transaction?

| Option | Description |
|--------|-------------|
| A | Fire-and-forget: dispatch after business commit. Notification failure never rolls back business |
| B | Same-transaction: dispatch inside business transaction. Notification failure rolls back both |
| C | Two-phase: business commits first, then independent notification transaction. Notification failure never rolls back business. Dispatch result persisted per Sprint 007 delivery truth. |

> **RESOLVED: Option C — Independent post-commit notification transaction (2026-07-22)**
>
> Specification:
> 1. Business operation completes and commits in its own transaction.
> 2. After business commit, a separate notification transaction calls `dispatch_notification()`.
> 3. Notification failure must not roll back Guardian, Committee, Automation, or Backup results.
> 4. Dispatch result is persisted (delivered/unavailable/failed/suppressed) per Sprint 007 delivery truth.
> 5. No untracked background tasks.
>
> Reference: `run_all_checks()` in Sprint 007 demonstrates this isolation boundary — health components evaluated, overall status computed, then notification dispatched. Health response is independent of notification success.

---

## OD-8-7: Dashboard Inclusion

**Question**: Should Sprint 008 include any dashboard/aggregation work?

| Option | Description |
|--------|-------------|
| A | No dashboard work. Pure source wiring + schedules |
| B | Minimal status card on /notifications page |
| C | Full /dashboard page |

> **RESOLVED: Option A — No dashboard (2026-07-22)**
>
> Rationale: Keep Sprint 008 focused. Dashboard is independently valuable but adds scope (new endpoints, new frontend page). Source wiring alone significantly improves daily usability via notifications.

---

## OD-8-8: Sprint Decomposition

**Question**: How should Sprint 008 be decomposed?

| Option | Description |
|--------|-------------|
| A | Three slices: A (Guardian+Backup wiring), B (Committee+Automation wiring), C (Daily schedules + UI) |
| B | Two slices: A (all backend wiring + schedules), B (Frontend) |
| C | Single slice: all in one PR |

> **RESOLVED: Option A — Three slices (2026-07-22)**
>
> - Slice A (R2): Guardian + Backup source wiring
> - Slice B (R2): Committee + Automation source wiring
> - Slice C (R1): Daily schedules + schedule UI in /automation workspace
>
> Each slice requires separate explicit Owner authorization.
> Implementation NOT AUTHORIZED until Technical Design Gate approved.

---

## Implementation Boundary

All 8 Owner Decisions resolved (2026-07-22).

Next: Technical Design Gate.

Sprint 008 implementation: NOT AUTHORIZED.
No Slice is authorized until Technical Design Gate is approved and individual Slice authorization is granted.
