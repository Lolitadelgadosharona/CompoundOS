# Sprint 008 — Technical Design

> **STATUS: TECHNICAL DESIGN — OWNER APPROVED (2026-07-22, corrected 2026-07-22)**
>
> Approved baseline HEAD: cbbadbb958b9881ad9fe02358afd28fed8a043a5
>
> **Manual-trigger correction (2026-07-22):** Manual-trigger Guardian runs (schedule_id=NULL) are NOT claimed by the worker. The worker only claims due schedules via claim_due_schedules(). This path is removed from Slice A scope and recorded as future backlog. See §3.1.
>
> IMPLEMENTATION STATUS:
> - Technical Design: OWNER APPROVED (2026-07-22, corrected 2026-07-22)
> - Slice A: Done (PR #69, merged aa444aa)
> - Slice B: Done (PR #73, merged a7a01ca)
> - Slice C: Authorized / In Progress
>
> TD-8-1: **Owner Resolved** — Option A with schedule-local timezone definition

---

## 1. Baseline

| Item | Value |
|------|-------|
| Main HEAD | 9d5faebea4a3538b838b071d23340deb57fa5b35 |
| Planning PR | #67 (MERGED, 2026-07-22) |
| Owner Decisions | 8/8 resolved + TD-8-1 resolved |
| Migration head | 0016_notification_integrity |
| PG 552 / non-PG 134+2 / frontend 251 |

---

## 2. Transaction Ownership — Corrected Design

### 2.1 Actual Code Evidence

`notification_service.py` — `notify()` owns its transaction:
- Line 148: `session.commit()` (disabled path)
- Line 197: `session.commit()` (source_disabled)
- Line 211: `session.commit()` (severity_disabled)
- Line 245: `session.commit()` (dedup suppressed)
- Line 258: `session.commit()` (quiet_hours suppressed)
- Line 282: `session.commit()` (delivery complete)
- Line 298: `session.commit()` (acknowledge)

`get_preferences()` at line 61: `session.commit()`.

`dispatch_notification()` → calls `notify()` which internally commits.

### 2.2 Conflict

Wrapping `dispatch_notification()` with `session.begin()` conflicts because `notify()` internally calls `session.commit()`. The context manager would see a closed transaction and raise on exit.

### 2.3 Design: Dedicated Notification Session

All four sources shall use this pattern:

```python
from apps.api.database import SessionLocal

# After business transaction committed with business_session.commit()

notification_session = SessionLocal()
try:
    dispatch_notification(
        notification_session,
        source=..., event_type=..., severity=...,
        household_id=..., entity_id=..., context=...,
    )
    # dispatch_notification → notify() internally commits notification_session
except Exception:
    notification_session.rollback()
    # Log safely — no business data
finally:
    notification_session.close()
```

**Properties**:
- Business session and notification session are independent
- `dispatch_notification()` owns the notification transaction — calls `session.commit()` internally
- Notification failure → rollback + close; business result unaffected
- Adapter failure → delivery_status="failed" persisted in notification transaction
- No `session.begin()` wrapper around dispatch — dispatch owns its commit
- No background tasks. No async fire-and-forget.
- `SessionLocal` creates a new engine-bound session from the same pool as the application

**Compatibility**: This pattern does not require refactoring `notify()` or `get_preferences()`. Existing health dispatch (`run_all_checks`) uses the health session directly — no change needed there since health owns that session lifecycle.

---

## 3. Source Trigger Points — Complete Path Coverage

### 3.1 Guardian — All Evaluation Paths

Guardian has two execution paths in Slice A:

| Path | Entry Point | Session Owner |
|------|------------|---------------|
| HTTP manual | `evaluate_all_checks()` / `evaluate_one_check()` (guardian.py:381/395) | HTTP router → service |
| Worker scheduled | `_run_job_in_child()` → `evaluate_core()` (orchestration_executor.py:124) | Worker child process → parent |

**Design**: Notification dispatch must happen in the PARENT worker process for scheduled evaluations, and in the HTTP service layer for HTTP evaluations. The trigger condition is identical: after business commit, if evaluation produced new Guardian events > 0.

**Manual-trigger runs (NOT in Slice A)**: Manual-trigger Guardian runs are created via `manual_trigger_run()` (orchestration.py:252) with `schedule_id=NULL` and `triggered_by="manual"`. The worker (`OrchestrationWorker._claim_and_execute()`) only claims due schedules via `claim_due_schedules()` — manual runs with NULL schedule_id are never claimed. Manual-trigger run claim/execution is a future backlog item requiring independent Technical Design and Owner authorization. It is NOT part of Sprint 008 Slice A, B, or C.

**Worker path** (orchestration_executor.py:116-195):
1. Child process runs `evaluate_core()` inside `with session.begin()` at line 116
2. Guardian events persisted in that transaction
3. Lease validated, attempt/run status set, lease released
4. `session.begin()` commits atomically at line 195 scope exit
5. **After commit**: worker parent process receives result via `result_queue`
6. Worker inspects result: if `evaluation_run.status` starts with "completed" and `len(events) > 0`
7. Worker creates dedicated notification session and dispatches

**HTTP path** (guardian.py:381-408):
1. `evaluate_all_checks()` / `evaluate_one_check()` call `_evaluate_core()`
2. `session.commit()` at line 391/407
3. **After commit**: if result has `events` list with `len > 0`
4. Router creates dedicated notification session and dispatches

**Key invariant**: Both paths only dispatch when:
- Evaluation actually completed (not skipped/fenced/errored)
- New Guardian events were created (len > 0)
- Guardian events are the `guardian_events` table rows with `event_type` column

**Household_id resolution**: `_evaluate_core()` receives `household_id` as parameter. Worker passes it from job_definition. Result dict returns evaluation_run with events. Worker has access to `household_id` from job definition.

### 3.2 Committee — Manual Session Completion

**File**: `committee_orchestration.py:220-225`

Session completion sets `status="completed"` and calls `session.commit()` at line 225.

**Trigger**: After commit, if `committee_session.status == "completed"`, create dedicated notification session and dispatch.

**Non-trigger**: session failed (_fail_session at line 346), privacy preview not confirmed, session still running.

### 3.3 Backup — All Completion Paths (Corrected)

**File**: `backup_service.py:76-132`

All paths that create a committed `BackupRecord` trigger notification:

| Path | Line | status | event_type |
|------|------|--------|-----------|
| Destination preflight failure | 91-94 | "failed" | backup_failed |
| Encryption/dump success | 120-125 | "completed" | backup_complete |
| Exception during pipeline | 127-132 | "failed" | backup_failed |

Every path calls `session.commit()` before returning. Trigger after commit with the record's status.

**Household_id resolution**: `BackupRecord` currently has no `household_id` column. The singleton Household model means there is exactly one household. Design: query `SELECT id FROM household_profiles LIMIT 1` in the notification dispatch block. If no household exists, log warning and skip notification (should not happen in operational state).

### 3.4 Automation — Final Run Failure Only (Corrected)

**File**: `orchestration_executor.py:178-187`

The run status is set to "failed" at line 182-187 only when the evaluation result indicates failure. This happens once per run, inside the final commit window.

**Trigger**: Worker parent process, after the child completes, if `run_status == "failed"`:
1. Worker marks run completed/failed and commits
2. Worker creates dedicated notification session
3. Worker dispatches `run_failed` notification

**Non-trigger**:
- Intermediate attempt retries (run still pending)
- Lease lost / fenced (run not marked failed — transaction rolled back)
- Run succeeded
- Stale fencing token

**Entity_id**: `run_id` only (not `run_id:attempt`). Each run can only reach "failed" once. No need for attempt_number in dedup identity.

**Recursive protection**: Notification dispatch is synchronous in worker process. No `notification.*` job type exists. `ALLOWED_JOB_TYPES` contains only guardian types. Notification failure does not create automation runs.

---

## 4. Event Type Reconciliation

| Approved Name | Current Template Key | Implementation Action |
|--------------|---------------------|----------------------|
| guardian/threshold_breach | guardian/breach | Rename key to `threshold_breach` in NOTIFICATION_TEMPLATES |
| committee/session_complete | committee/completed | Rename key to `session_complete` |
| automation/run_failed | automation/failed | Rename key to `run_failed` |
| backup/backup_complete | backup/completed | Rename key to `backup_complete` |
| backup/backup_failed | backup/failed | Rename key to `backup_failed` |

`notification_events.event_type` has no database CHECK constraint — renaming requires no migration. Implementation updates `NOTIFICATION_TEMPLATES` dict keys and all `dispatch_notification()` call sites. No aliases retained.

---

## 5. Dedup Identity Design

### 5.1 Guardian — Corrected

**Problem**: Previous design used empty entity_id, causing all guardian breaches in the same household to share one fingerprint.

**Design**: Use stable breach identity derived from check_ids:

- `evaluate_one`: entity_id = `check_id` of the evaluated check
- `evaluate_all`: entity_id = sorted concatenation of check_ids that produced new events, hashed

```python
# evaluate_all: aggregate identity
breached_check_ids = sorted(set(e["check_id"] for e in result["events"]))
entity_id = hashlib.sha256("|".join(breached_check_ids).encode()).hexdigest()[:16]
```

**Dedup semantics**: Same check producing breach on same day → suppressed. Different checks producing breaches → separate fingerprints, both delivered. This correctly prevents cross-check dedup while allowing same-check dedup.

**Relationship to Guardian ON CONFLICT**: Guardian uses `ON CONFLICT DO NOTHING` with partial unique indexes (uq_events_drift, uq_events_staleness). The database already prevents duplicate events for the same check. Notification dedup is a separate layer — same Guardian check evaluated twice in 24h produces the same database event (DO NOTHING) and then the same notification fingerprint (dedup suppressed).

### 5.2 Other Sources

| Source | entity_id | Rationale |
|--------|-----------|-----------|
| committee | session_id | Each session is a unique UUID |
| automation | run_id | Run can only reach failed once |
| backup | record_id | Each backup record is a unique UUID |

---

## 6. Schedule Design

### 6.1 TD-8-1 — Resolved (Owner Decision)

**Missed-run semantics**:
- Schedule re-enabled BEFORE execution_time on the same day: wait until the scheduled time
- Schedule re-enabled AFTER execution_time on the same day: if no run exists for this schedule's local date, immediately enter due state (catch-up)
- Worker/service restored after execution_time: same catch-up semantics
- "Today" is determined by the schedule's configured IANA timezone, NOT `UTC now.date()`
- DST gap: execute at next valid local time
- DST overlap: execute once at first occurrence
- One scheduled run per schedule per local date (enforced by idempotency)

### 6.2 Corrected Idempotency Design

**Current code** (orchestration_scheduling.py:171-182):
```python
def compute_idempotency_key(job_type, job_params, scheduled_date):
    payload = f"{job_type}{params_str}||{scheduled_date.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()
```

**Problems**:
1. `scheduled_date` from `now.date()` (UTC) — not schedule's local date
2. No `schedule_id` — different schedules with same job_type+params+date collide
3. No `household_id` — cross-household collision possible (theoretical in single-tenant)

**Database evidence**: `uq_runs_idempotency_key` (UNIQUE constraint, migration 0008 line 178). Duplicate insert raises IntegrityError.

**Design (for Slice C)**:
- Existing idempotency keys remain compatible (same formula)
- Worker resolves schedule's local date from schedule timezone BEFORE computing key
- Schedule_id included in key to prevent cross-schedule collision
- `compute_idempotency_key()` modified to accept optional `schedule_id` — this is Slice C application code, not migration

```python
def compute_idempotency_key(job_type, job_params, scheduled_date, *, schedule_id=None):
    sid = f"||sid={schedule_id}" if schedule_id else ""
    payload = f"{job_type}{params_str}{sid}||{scheduled_date.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()
```

**Duplicate key handling — ON CONFLICT (only approved approach)**:

PostgreSQL IntegrityError aborts the current transaction. Catching IntegrityError and continuing is not possible. The only approved design is `INSERT ... ON CONFLICT (idempotency_key) DO NOTHING RETURNING id` within the same outer transaction that locks the schedule.

```sql
-- Within the schedule processing transaction:
INSERT INTO runs (id, schedule_id, job_definition_id, idempotency_key,
                  status, triggered_by, scheduled_at, created_at)
VALUES (:id, :sid, :jid, :ikey, 'pending', 'schedule', :now, :now)
ON CONFLICT (idempotency_key) DO NOTHING
RETURNING id
```

- If `RETURNING id` returns a row: run was created. Advance `next_run_at`. Commit.
- If `RETURNING id` returns no row: a run for this schedule+date already exists. Do not create a second run. Still advance `next_run_at`. Commit.
- Run creation (or duplicate confirmation) and `next_run_at` advance are atomic — both in same transaction.
- Any database error rolls back the entire transaction. Schedule remains due, allowing safe retry.
- Concurrent workers are protected by: schedule claim/row lock, `uq_runs_idempotency_key` UNIQUE constraint, and lease/fencing.

**Test plan**:
- Duplicate insert does not leave failed transaction
- Duplicate run: `next_run_at` still advances
- Run creation or `next_run_at` advance failure → full rollback, schedule remains due
- Two concurrent workers claiming same schedule → exactly one scheduled run
- After rollback, schedule can be safely re-claimed

**Rejected alternative**: SAVEPOINT (`session.begin_nested()`) was evaluated but rejected. If ON CONFLICT is found infeasible during implementation (e.g., ORM limitation), stop and return to Technical Design Gate — do not silently switch to SAVEPOINT.

**Schedule_id inclusion evidence**: `runs.schedule_id` column exists (FK to schedules, nullable). Worker already has access to `schedule_id` when creating runs.

**Owner Question**: Should manually triggered Guardian runs count as "today's daily run" for schedule dedup? If yes, the schedule's idempotency key for that date would collide with a manual run, preventing the scheduled run. Recommended: keep separate — manual runs use different triggered_by value and don't affect schedule idempotency. No new Owner Question needed — this is consistent with Sprint 005 manual trigger design.

---

## 7. Migration Conclusion

| Item | Needs Migration? | Evidence |
|------|-----------------|----------|
| Guardian wiring (all paths) | No | notification_events CHECK allows all sources |
| Committee wiring | No | Same |
| Automation wiring | No | Same |
| Backup wiring | No | Same |
| Guardian daily schedule | No | guardian.evaluate_all in DB trigger + service allowlist |
| Backup daily schedule | **Yes — 0017** | backup.daily not in trigger (0008:53) or ALLOWED_JOB_TYPES |
| Schedule idempotency (schedule_id, local date) | No (Slice C application code) | uq_runs_idempotency_key exists; schedule_id column exists |
| Event type renaming | No | event_type has no CHECK constraint |
| compute_idempotency_key() change | No (Slice C application code) | Python function, no schema change |
| ALLOWED_JOB_TYPES expansion | No (Slice C application code) | Python constant, no schema change |

Migration 0017 scope:

Database function to replace (from migration 0008, lines 48-58):
- `public.fn_job_definition_allowlist() RETURNS trigger LANGUAGE plpgsql`
- Trigger: `trg_job_definition_allowlist` BEFORE INSERT OR UPDATE ON job_definitions
- Current allowlist: `'guardian.evaluate_all', 'guardian.evaluate_one'`

Migration 0017 uses `CREATE OR REPLACE FUNCTION public.fn_job_definition_allowlist()` (same function — the trigger will automatically call the new version). Upgrade adds `'backup.daily'` to the allowlist. Downgrade restores original allowlist.

Migration 0017 does NOT modify:
- Python functions, constants, `compute_idempotency_key()`, or `ALLOWED_JOB_TYPES`
- Those are Slice C application code — no schema change required

---

## 8. Three-Slice Design

### Slice A — Guardian + Backup Source Wiring (R2)

**Scope**: Notification dispatch after Guardian evaluation (HTTP manual + worker scheduled) and after Backup completion (all paths including preflight failure).

**Guardian design**:
- HTTP path: after `session.commit()` at guardian.py:391/407, if events > 0, dedicated notification session dispatches `threshold_breach` warning
- Worker scheduled path: child runs evaluate_core → parent receives result → after child committed, dispatches `threshold_breach` warning via `_maybe_notify_guardian_worker()`
- Manual-trigger Guardian runs: NOT in Slice A scope (see §3.1)

**Backup design**:
- After `session.commit()` at backup_service.py:94/124/131, dedicated notification session dispatches based on record.status

**Non-scope**: No schedule creation. No migration. No Committee/Automation.

### Slice B — Committee + Automation Source Wiring (R2)

**Committee**: After session completed commit, dedicated notification session dispatches `session_complete` info.

**Automation**: Worker parent process, after run failed committed, dedicated notification session dispatches `run_failed` warning.

**Non-scope**: No schedule creation. No migration. No Guardian/Backup.

### Slice C — Daily Schedules + Schedule UI (R1)

**Migration 0017**: job_type allowlist expansion.

**Guardian daily schedule**: job_type `guardian.evaluate_all`, default disabled.

**Backup daily schedule**: job_type `backup.daily`, default disabled.

**Schedule UI**: enable/disable + time/timezone in /automation workspace.

**Non-scope**: No auto-enable. No auto-selection of time/timezone.

### Inter-Slice Independence

- Slice A: no dependency on B or C. Works with HTTP and existing worker.
- Slice B: no dependency on A or C.
- Slice C: no dependency on A or B (but notification value increases when wired).

---

## 9. Test Design

### Slice A Tests

| Test | Path |
|------|------|
| Guardian HTTP evaluate_all with breach → dispatch delivered | HTTP |
| Guardian HTTP evaluate_one with breach → dispatch delivered | HTTP |
| Guardian evaluate_all with 0 events → no dispatch | HTTP |
| Guardian worker scheduled with breach → dispatch delivered | Worker |
| Guardian disabled prefs → suppressed | Both |
| Guardian source disabled → suppressed | Both |
| Guardian different checks produce different fingerprints | Dedup |
| Guardian same check same day → dedup suppressed | Dedup |
| Backup completed → dispatch backup_complete info | Backup |
| Backup preflight failure → dispatch backup_failed warning | Backup |
| Backup pipeline failure → dispatch backup_failed warning | Backup |
| Backup disabled → suppressed | Backup |
| Notification tx failure after business commit → business unaffected | Isolation |

### Slice B Tests

| Test | Path |
|------|------|
| Committee session completed → dispatch session_complete info | Committee |
| Committee session failed → no dispatch | Committee |
| Automation run failed (final) → dispatch run_failed warning | Automation |
| Automation run succeeded → no dispatch | Automation |
| Automation attempt retry while pending → no dispatch | Automation |
| Automation notification does not create automation run | Recursion |
| Notification tx failure after business commit → business unaffected | Isolation |

### Slice C Tests

| Test | Path |
|------|------|
| Migration 0017 upgrade/downgrade/re-upgrade | Migration |
| Guardian daily schedule created disabled | Schedule |
| Backup daily schedule created disabled | Schedule |
| Schedule re-enabled before execution_time → wait | TD-8-1 |
| Schedule re-enabled after execution_time → catch-up (if not run today) | TD-8-1 |
| Schedule local date uses IANA timezone, not UTC | TD-8-1 |
| DST gap → next valid time | TD-8-1 |
| DST overlap → execute once | TD-8-1 |
| Duplicate idempotency key → next_run_at advances | Idempotency |
| backup.daily accepted after migration | Migration |
| UI: schedule enable/disable in /automation | Frontend |

---

## 10. Non-Goals

- No external notifications (email, SMS, push) → V2
- No Market Data integration → V2
- No Cloud backup → V2
- No Family Goals & Reporting → V2
- No dashboard, aggregation, or portfolio valuation
- No investment rule changes
- No Guardian threshold or breach criteria changes
- No automatic trading
- No automatic schedule or notification enabling
- No new credentials or external services
- No `notification.*` job type (recursive protection)
- No manual-trigger run claim/execution (future backlog — requires independent Technical Design)
