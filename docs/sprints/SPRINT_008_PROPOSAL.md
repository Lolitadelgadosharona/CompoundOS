# Sprint 008 — Proposal

> **STATUS: OWNER DECIDED — TECHNICAL DESIGN GATE PENDING**
>
> All 8 Owner Decisions resolved (2026-07-22).
> Implementation is NOT AUTHORIZED.
> Each Slice requires separate explicit Owner authorization after Technical Design Gate.

---

## 1. Baseline

| Item | Value |
|------|-------|
| Main HEAD | 2f4f12569ae702fcbcc9a0bb01b199d68fe26327 |
| PR #66 closeout | 2f4f125 (2026-07-22) |
| Migration head | 0016_notification_integrity |
| PG tests | 552 passed, 0 failed, 0 skipped |
| Non-PG tests | 134 passed, 2 expected skipped |
| Frontend tests | 251 passed (14 test files) |
| Main CI | 29888368096 (3/3 success) |
| Sprints 001–007 | Done |
| Sprint 008 implementation | NOT AUTHORIZED |

---

## 2. Approved Direction — Candidate A

**Notification Source Wiring + Daily Operations**

Selected by Owner per OD-8-1. All 8 Owner Decisions resolved.

---

## 3. Owner Decisions — Resolved

| ID | Decision | Resolution |
|----|----------|-----------|
| OD-8-1 | Sprint direction | **A**: Notification Source Wiring + Daily Operations |
| OD-8-2 | Daily schedule scope | **A**: Include Guardian daily evaluation + Backup daily schedule. Both default disabled. Owner must explicitly set execution time, timezone, and enable. |
| OD-8-3 | Source wiring completeness | **A**: Wire guardian, committee, automation, backup — all 4 pending sources. Wiring ≠ default notification; existing enabled_sources/enabled_severities still gate actual delivery. |
| OD-8-4 | Severity assignments | guardian threshold_breach: **warning**; committee session_complete: **info**; automation run_failed: **warning**; backup completed: **info**; backup failed: **warning**. No critical mappings added. |
| OD-8-5 | Committee notification scope | **A**: Wire now for manual sessions. Committee session completion produces info notification. No automatic committee runs or investment decisions. |
| OD-8-6 | Transaction boundary strategy | **C**: Business operation commits first, then independent notification transaction. Notification failure must not roll back Guardian, Committee, Automation, or Backup results. Dispatch result persisted per Sprint 007 delivery truth. No untracked background tasks. run_all_checks() serves as the existing reference boundary for isolation of business results from notification failure. |
| OD-8-7 | Dashboard inclusion | **A**: No dashboard, aggregation endpoint, or portfolio valuation in Sprint 008. |
| OD-8-8 | Sprint decomposition | **A** — Three slices: Slice A (Guardian + Backup wiring), Slice B (Committee + Automation wiring), Slice C (Daily schedules + schedule UI). Each slice requires separate Owner authorization. |

---

## 4. Current State — What Sprint 001–007 Delivered

### 4.1 Complete Capabilities

| Domain | What's Built |
|--------|-------------|
| Household | Single-household profile, audit timeline |
| Investment Policy | Draft/edit/publish lifecycle, immutable versions, allocations |
| Decision Journal | Drafts, confirmed snapshots, corrections, audit |
| Portfolio | Snapshots with holdings, confirm/discard, immutable history |
| Guardian Monitoring | Breach, category exposure, staleness checks; manual trigger |
| Automation | Worker, schedules, leases, fencing; manual trigger |
| AI Committee | Evidence pipeline, DeepSeek adapter, 7 perspectives, 9 API routes |
| Backup/Export | pg_dump→age, JSON/CSV export, 7+4+12 retention, restore verification |
| Health Dashboard | 10 components, 5-state model, mutation gate, 3 endpoints |
| Notification | Explicit opt-in, macOS adapter, structured templates, household dedup |
| Safe Autopilot | Self-driving infrastructure, blind review, CI monitoring |

### 4.2 Notification Source Status

| Source | Templates Defined | Wired? |
|--------|-------------------|--------|
| health | YES | **YES** — via run_all_checks |
| guardian | YES | NO — pending Slice A |
| committee | YES | NO — pending Slice B |
| automation | YES | NO — pending Slice B |
| backup | YES | NO — pending Slice A |

### 4.3 Daily-Use Gaps

1. No scheduled Guardian evaluation (manual trigger only)
2. No scheduled backup (launchd exists but not via automation)
3. 4 of 5 notification sources silent
4. No portfolio valuation updates
5. No daily dashboard
6. Docker runtime unverified

---

## 5. Sprint 008 Scope

### 5.1 Source Wiring (All Slices)

Wire each source at its natural completion/failure point:

- **Guardian**: After evaluation completes and events are persisted. If any threshold breach events were created → dispatch warning notification.
- **Backup**: After backup pipeline completes or fails → dispatch info (completed) or warning (failed).
- **Committee**: After session run completes → dispatch info notification.
- **Automation**: After run attempt fails → dispatch warning notification.

### 5.2 Transaction Boundary (per OD-8-6)

For each wired source:
1. Business operation completes and commits in its own transaction.
2. After business commit, a separate notification transaction calls `dispatch_notification()`.
3. Notification failure never rolls back the business operation.
4. Dispatch result is persisted (delivered/unavailable/failed/suppressed) per Sprint 007 delivery truth.
5. No untracked background tasks or async fire-and-forget. Every dispatch has a persisted NotificationEvent.

Reference: `run_all_checks()` in Sprint 007 already demonstrates this boundary — health component evaluation completes, overall status computed, then (and only then) notification dispatched. Notification failure cannot break health response.

### 5.3 Daily Schedules (Slice C)

- Guardian daily evaluation schedule: default **disabled**.
- Backup daily schedule: default **disabled**.
- Owner must explicitly set execution_time, timezone, and enable.
- Reuses Sprint 005 approved daily schedule model (job_definitions → schedules → runs).

**Schedule product boundaries (Technical Design Gate must define):**
- Missed-run / catch-up semantics (skip, run-late, or queue)
- next_run_at calculation after restart
- Interaction with existing lease/fencing/idempotency
- Same-day re-run vs. notification dedup (24h window)

### 5.4 Non-Scope

- No dashboard, aggregation, or portfolio valuation (OD-8-7)
- No automatic schedule enabling (OD-8-2)
- No Guardian threshold changes
- No investment rule changes
- No automatic trading
- No external notifications (V2)
- No market data (V2)
- No cloud backup (V2)

---

## 6. Database Impact

### 6.1 Job Type Allowlist

Migration 0008 (orchestration_foundation) has a PL/pgSQL trigger:

```sql
IF NEW.job_type NOT IN ('guardian.evaluate_all', 'guardian.evaluate_one') THEN
    RAISE EXCEPTION ... 'orchestration_job_type_not_allowed'
```

Daily Guardian evaluation already fits within existing types (`guardian.evaluate_all`). Backup daily requires a new job type (`backup.daily`) not in the allowlist.

**Evidence**: `migrations/versions/0008_orchestration_foundation.py` line 53.

### 6.2 Migration Assessment

| Change | Migration Needed? |
|--------|-------------------|
| Notification source wiring (4 services) | **No** — notification_events already supports all sources via CHECK constraints |
| Guardian daily schedule | **No** — `guardian.evaluate_all` already in job_type allowlist |
| Backup daily schedule | **Likely yes** — `backup.daily` not in trigger allowlist. Requires CREATE OR REPLACE FUNCTION to expand job_type list |
| Notification dispatch calls | **No** — dispatch_notification() uses existing notification_events table |

**Final determination deferred to Technical Design Gate.** The migration column count and exact approach (additive trigger replacement with CREATE OR REPLACE FUNCTION per established pattern) will be specified in the Technical Design.

---

## 7. Slice Structure

### Slice A — Guardian + Backup Source Wiring (R2)

- Guardian evaluation: after events persisted → if any threshold breach → dispatch warning via independent notification transaction
- Backup pipeline: after completion/failure → dispatch info/warning via independent notification transaction
- Contract tests: verify notification dispatched at correct boundary, business result independent of notification success/failure
- Verify notification failure does not roll back business operations
- Migration: none expected (notification_events schema is complete)

### Slice B — Committee + Automation Source Wiring (R2)

- Committee orchestrator: after session run completes → dispatch info notification
- Automation worker: after run attempt fails → dispatch warning notification
- Contract tests: verify notification on manual session completion, run failure
- Same transaction boundary pattern as Slice A
- Migration: none expected

### Slice C — Daily Schedules + Schedule UI (R1)

- Guardian daily evaluation schedule: create (default disabled)
- Backup daily schedule: create (default disabled)
- Schedule enable/disable UI in existing /automation workspace
- Owner sets execution_time and timezone per Sprint 005 schedule model
- Migration: likely needed for backup.daily job_type allowlist expansion
- Technical Design Gate must resolve: missed-run semantics, next_run_at on restart, dedup interaction

### Authorization

Each slice requires separate explicit Owner authorization.
Implementation is NOT AUTHORIZED until Technical Design Gate is approved and slices are individually authorized.

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Notification failure rolls back business transaction | Low | HIGH | Independent post-commit notification transaction (OD-8-6). Test with real transaction boundaries. |
| Guardian threshold noise → notification spam | Low | MEDIUM | 24h dedup window + severity escalation already in Sprint 007 |
| Daily schedules create unwanted automation | Low | MEDIUM | Default disabled; explicit opt-in per schedule; no auto-enable |
| job_type allowlist blocks backup schedule | Medium | MEDIUM | CREATE OR REPLACE FUNCTION per established pattern; resolved in Technical Design |
| Missed-run behavior undefined | Medium | LOW | Deferred to Technical Design Gate; not a blocking risk for implementation |

---

## 9. Explicit Non-Goals

- No external notifications (email, SMS, push) → V2
- No Market Data integration → V2
- No Cloud backup → V2
- No Family Goals & Reporting → V2
- No dashboard, aggregation, or portfolio valuation
- No investment rule changes
- No Guardian threshold changes
- No automatic trading
- No new credentials or external services
- No automatic schedule or notification enabling
