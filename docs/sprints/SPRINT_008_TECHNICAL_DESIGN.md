# Sprint 008 — Technical Design

> **STATUS: TECHNICAL DESIGN — OWNER APPROVAL REQUIRED**
>
> IMPLEMENTATION NOT AUTHORIZED
> ALL SLICES NOT AUTHORIZED (require individual Owner authorization post-gate)

---

## 1. Baseline

| Item | Value |
|------|-------|
| Main HEAD | 9d5faebea4a3538b838b071d23340deb57fa5b35 |
| Planning PR | #67 (MERGED, 2026-07-22) |
| Direction | Candidate A — Notification Source Wiring + Daily Operations |
| Owner Decisions | 8/8 resolved |
| Migration head | 0016_notification_integrity |
| PG 552 / non-PG 134+2 / frontend 251 |

---

## 2. Source Code Analysis — Exact Trigger Points

### 2.1 Guardian

**File**: `apps/api/services/guardian.py`

`evaluate_all_checks()` (line 381):
```python
def evaluate_all_checks(session, *, household_id, as_of_date) -> dict:
    result = _evaluate_core(session, household_id=household_id, as_of_date=as_of_date)
    session.commit()        # ← line 391: business commit
    return result
```

`evaluate_one_check()` (line 395): same pattern, commit at line 407.

**Notification trigger point**: AFTER `session.commit()` (line 391/407). The result dict contains `{"evaluation_run": {..., "status": "completed"}, "events": [...]}`. If `len(events) > 0`, threshold breach events were persisted. Guardian events use the `guardian_events` table with `event_type` column.

**Dedup identity**: `sha256("v2:{household_id}:guardian:threshold_breach:warning:")`. Guardian evaluates-on-demand; repeated same-day evaluations with same breach findings should dedup within 24h window.

**Non-trigger**: session=None (router error), check not found (CheckNotFoundError), evaluation status not "completed".

### 2.2 Committee

**File**: `apps/api/services/committee_orchestration.py`

Session completion at line 220-225:
```python
report = _persist_report(...)
committee_session.status = "completed"
session.commit()          # ← line 225: business commit
```

**Notification trigger point**: AFTER `session.commit()` at line 225. The method `run_session()` orchestrates: evidence → privacy preview check → provider call → validate → persist report → set completed → commit.

**Dedup identity**: `sha256("v2:{household_id}:committee:session_complete:info:{session_id}")`. Each session has a unique UUID; same session cannot complete twice.

**Non-trigger**: session status != "completed", session failed (_fail_session at line 346), privacy preview not confirmed.

### 2.3 Backup

**File**: `apps/api/services/backup_service.py`

Success path (line 120-125):
```python
record.status = "completed"
record.completed_at = datetime.now(timezone.utc)
session.commit()          # ← line 124: business commit
return record
```

Failure path (line 127-132):
```python
record.status = "failed"
record.completed_at = datetime.now(timezone.utc)
session.commit()          # ← line 131: business commit
return record
```

**Notification trigger points**: AFTER `session.commit()` at line 124 (success) or 131 (failure). The record's `status` field carries the outcome.

**Dedup identity**:
- Success: `sha256("v2:{household_id}:backup:backup_complete:info:{record_id}")`
- Failure: `sha256("v2:{household_id}:backup:backup_failed:warning:{record_id}")`

**Non-trigger**: pre-flight failures (line 91-94), backup not started.

### 2.4 Automation

**File**: `apps/api/services/orchestration_executor.py`

`RealJobExecutor.execute()` (line 225): spawns child process, monitors via `result_queue`. On failure returns `{"status": "failed", ...}`. The worker (`orchestration_worker.py`) receives this, marks the run attempt failed, and commits.

`FakeJobExecutor.execute()` (line 295): returns `{"status": "failed", ...}` for simulated failures.

**Notification trigger point**: In the worker, after the run attempt status is updated to "failed" and the transaction committed. The worker processes results from the executor and persists them.

**Dedup identity**: `sha256("v2:{household_id}:automation:run_failed:warning:{run_id}:{attempt_number}")`. Includes attempt number to distinguish retries.

**Recursive protection**: The notification dispatch itself must never be scheduled as an automation job. The `run_failed` notification dispatches for automation jobs only — never for notification-system jobs. No `notification.*` job type exists or will be created.

**Non-trigger**: run succeeded, run is pending/running, run retried (new attempt — dedup may apply), lease lost (not a run failure).

---

## 3. Notification Transaction Design

### 3.1 Pattern (All Sources)

```
┌─────────────────────────────────────────┐
│ 1. Business operation                    │
│    - Guardian: _evaluate_core()          │
│    - Committee: _persist_report()        │
│    - Backup: _do_dump_and_encrypt()      │
│    - Automation: child process result    │
│                                          │
│ 2. session.commit() ← business tx ends   │
├─────────────────────────────────────────┤
│ 3. Independent notification transaction  │
│    with session.begin():                 │
│      dispatch_notification(             │
│        session, source, event_type,      │
│        severity, household_id=...,      │
│        entity_id=..., context=...        │
│      )                                   │
│    - dispatch call commit/rollback       │
│    - Any exception caught and logged    │
│    - Business result unaffected          │
└─────────────────────────────────────────┘
```

### 3.2 Error Handling

| Scenario | Behavior |
|----------|----------|
| dispatch_notification succeeds | notification event persisted; delivery_status per adapter result |
| dispatch_notification raises | caught, logged; business operation already committed |
| adapter unavailable | delivery_status="unavailable"; no macOS notification |
| adapter fails | delivery_status="failed"; no rollback |
| preferences disabled | suppressed_reason="disabled"; event persisted |
| dedup hit | suppressed_reason="dedup"; event persisted |
| quiet hours | suppressed_reason="quiet_hours"; event persisted |

### 3.3 No Background Tasks

Every notification dispatch is a synchronous call with a real session and explicit commit/rollback. No `asyncio.create_task`, no `threading.Thread`, no unobserved fire-and-forget.

The existing `run_all_checks()` in Sprint 007 serves as the reference implementation:
- Health components evaluated, overall computed
- After result assembled, `dispatch_notification()` called with session
- Exception caught, logged, health response unaffected

### 3.4 Logging

Each source logs dispatch outcome at INFO level:
- Success: `"Notification dispatched: {source}/{event_type}/{severity}"`
- Suppressed: `"Notification suppressed: {reason}"`
- Error: `"Notification dispatch error: {exc}"`  (never includes business data)

---

## 4. Event Mapping

| Source | event_type | severity | Trigger |
|--------|-----------|----------|---------|
| guardian | threshold_breach | warning | evaluate_all/one completes with events > 0 |
| committee | session_complete | info | run_session completes successfully |
| automation | run_failed | warning | run attempt status becomes "failed" |
| backup | backup_complete | info | run_backup returns status="completed" |
| backup | backup_failed | warning | run_backup returns status="failed" |

No critical mappings. No new event types. Per OD-8-4.

---

## 5. Dedup Design

Each notification dispatch uses `compute_fingerprint()` (Sprint 007, v2):

```
v2:{household_id}:{source}:{event_type}:{severity}:{entity_id}
```

| Source | entity_id | Notes |
|--------|-----------|-------|
| guardian | (none) | Global scope; same breach on same day deduped |
| committee | session_id | Each session is unique; no accidental cross-session dedup |
| automation | run_id:attempt | Each attempt is unique; retries not deduped against original |
| backup | record_id | Each backup run is unique |

24h dedup window with advisory lock (`pg_advisory_xact_lock(42)`). Severity escalation bypass preserved from Sprint 007.

---

## 6. Automation Recursive Protection

Automation runs `guardian.evaluate_all` or `guardian.evaluate_one`. If guardian evaluation fails (e.g., no household), the run is marked "failed" — this triggers `run_failed` notification.

**No recursive loop**: the notification dispatch is a synchronous call to `dispatch_notification()` with source="automation". It creates a notification_event row but does NOT create a new automation run. There is no `notification.*` job type. The automation worker only executes job_types in the allowed list.

**Worker notification dispatch**: The worker (orchestration_worker.py) processes `_run_job_in_child()` → receives result → marks attempt failed → commits → then dispatches notification. This is in the worker process, outside the child process lifecycle.

---

## 7. Schedule Technical Design

### 7.1 Guardian Daily Evaluation Schedule

- **job_type**: `guardian.evaluate_all` (already in DB trigger allowlist and service `ALLOWED_JOB_TYPES`)
- **job_params**: `{}` (no parameters — guardian.evaluate_all accepts none per orchestration_scheduling.py line 56)
- **Schedule model**: daily, execution_time, timezone per Sprint 005
- **Default**: disabled
- **Owner action**: create schedule, set time/timezone, enable

### 7.2 Backup Daily Schedule

- **job_type**: `backup.daily` (NEW — requires migration and allowlist expansion)
- **job_params**: `{"dest_dir": "...", "age_recipient": "..."}` (backup destination and encryption key required)
- **Schedule model**: daily, execution_time, timezone per Sprint 005
- **Default**: disabled
- **Owner action**: create schedule with params, set time/timezone, enable

### 7.3 Migration Impact for backup.daily

Database trigger (migration 0008, line 53):
```sql
IF NEW.job_type NOT IN ('guardian.evaluate_all', 'guardian.evaluate_one') THEN
    RAISE EXCEPTION ... 'orchestration_job_type_not_allowed'
```

Service allowlist (`orchestration_scheduling.py` line 28):
```python
ALLOWED_JOB_TYPES = frozenset({"guardian.evaluate_all", "guardian.evaluate_one"})
```

Both require expansion. Migration approach: `CREATE OR REPLACE FUNCTION` (established pattern per Pitfall #70-#71). New migration 0017 with:
- `CREATE OR REPLACE FUNCTION fn_job_type_allowlist()` expanding to include `'backup.daily'`
- Update `ALLOWED_JOB_TYPES` in orchestration_scheduling.py
- Downgrade path restores original allowlist

**Conclusion**: Migration needed for backup.daily. Guardian daily requires no migration.

### 7.4 Missed-Run Semantics (Owner Decision Required)

| Scenario | Options |
|----------|---------|
| Schedule disabled, then re-enabled same day | A: Run immediately if past execution_time. B: Wait until next day. C: Run only if within catch-up window. |
| Worker/service down at execution_time | A: Run when worker restarts (catch-up). B: Skip and wait for next schedule. C: Run if within grace period. |
| Same-day re-run (manual trigger + scheduled) | Dedup via idempotency key (Sprint 005: SHA256(job_type\|params\|date)). Only one run per day per schedule. |

**Recommendation**: Option A for both — run immediately if past execution_time and not yet run today. Uses existing Sprint 005 idempotency: same job_type+params+date → one run. See Technical Design Owner Question TD-8-1.

### 7.5 DST and Timezone

- Existing Sprint 005 IANA timezone support applies
- DST gap: if execution_time falls in skipped hour, run at next valid time
- DST overlap: run at first occurrence (standard time)
- next_run_at recomputed after each run using schedule's timezone

---

## 8. Three-Slice Design

### Slice A — Guardian + Backup Source Wiring (R2)

**Scope**:
- Guardian: after evaluate_all/one commit → if events > 0 → dispatch notification in independent tx
- Backup: after run_backup commit → dispatch notification (info for completed, warning for failed) in independent tx
- Contract tests per source
- Transaction boundary verification

**Non-scope**:
- No schedule creation or modification
- No Committee or Automation wiring
- No migration

**Modified modules**: `guardian.py` (evaluate_all_checks, evaluate_one_check), `backup_service.py` (run_backup), `test_guardian.py`, `test_backup.py`

**DB impact**: none (notification_events already supports all sources)

**Risk**: Low. Both sources have clear commit points. Templates exist.

### Slice B — Committee + Automation Source Wiring (R2)

**Scope**:
- Committee: after session completed commit → dispatch notification in independent tx
- Automation: after run attempt marked failed and committed → dispatch notification in independent tx
- Recursive protection verification
- Contract tests per source

**Non-scope**:
- No schedule creation
- No Committee auto-run
- No migration

**Modified modules**: `committee_orchestration.py` (run_session), `orchestration_executor.py` or `orchestration_worker.py` (run failure handling), test files

**DB impact**: none

**Risk**: Medium. Automation worker runs in separate process; notification dispatch must happen in worker context after run persistence. Recursive protection must be verified.

### Slice C — Daily Schedules + Schedule UI (R1)

**Scope**:
- Migration 0017: expand job_type allowlist for backup.daily
- Guardian daily evaluation schedule (default disabled)
- Backup daily schedule (default disabled)
- Schedule UI: enable/disable, time/timezone in /automation workspace
- Schedule API: create guardian and backup schedules
- Contract tests

**Non-scope**:
- No auto-enable
- No auto-selection of execution_time or timezone

**Modified modules**: `orchestration_scheduling.py` (ALLOWED_JOB_TYPES), `orchestration_worker.py` (backup executor), migration, router, frontend

**DB impact**: migration 0017 (CREATE OR REPLACE FUNCTION + allowlist expansion)

**Risk**: Medium. Migration is additive. Backup job params require destination_dir and age_recipient — Owner must provide these.

### Inter-Slice Dependencies

- Slice A: no dependency on B or C
- Slice B: no dependency on A or C
- Slice C: no dependency on A or B (but notification value increases when both are wired)

---

## 9. Test Design

### Slice A Tests

| Category | Test Cases |
|----------|-----------|
| Guardian success | evaluate_all with breach → dispatch → delivery_status delivered |
| Guardian no breach | evaluate_all with 0 events → no dispatch call |
| Guardian disabled | evaluate_all with prefs disabled → suppressed/disabled |
| Guardian source disabled | evaluate_all with guardian not in enabled_sources → suppressed |
| Guardian adapter unavailable | dispatch with no adapter → delivery_status unavailable |
| Guardian tx isolation | notification failure after guardian commit → guardian result unaffected |
| Backup success | run_backup completed → dispatch info → delivery_status delivered |
| Backup failure | run_backup failed → dispatch warning → delivery_status delivered |
| Backup disabled | prefs disabled → suppressed/disabled |
| Backup tx isolation | notification failure after backup commit → backup record unaffected |
| Dedup | same guardian breach twice in 24h → second suppressed |

### Slice B Tests

| Category | Test Cases |
|-----------|-----------|
| Committee success | run_session completed → dispatch info |
| Committee not completed | session failed → no dispatch |
| Committee disabled | prefs disabled → suppressed |
| Automation failed | run attempt failed → dispatch warning |
| Automation succeeded | run succeeded → no dispatch |
| Automation retry | same run+attempt → dedup protection |
| Automation recursion | notification dispatch does not create automation run |
| Tx isolation | notification failure after committee/automation commit → business unaffected |

### Slice C Tests

| Category | Test Cases |
|-----------|-----------|
| Migration | 0017 upgrade/downgrade/re-upgrade cycle |
| Schedule create | guardian daily + backup daily created disabled |
| Schedule enable | Owner PATCH enable → schedule active |
| Schedule default | created disabled → no auto-enable |
| Schedule execution | guardian.evaluate_all triggered on schedule |
| Idempotency | same schedule+date → one run |
| Missed-run | disabled→re-enabled same day → runs once (per TD-8-1) |
| DST | gap/overlap handling |
| job_type allowlist | backup.daily accepted after migration |
| API contract | schedule CRUD works for new job_types |
| UI | schedule enable/disable in /automation |

---

## 10. Technical Design Owner Question

### TD-8-1: Missed-Run Semantics

**Question**: When a disabled daily schedule is re-enabled on the same day (past its execution_time), what should happen?

| Option | Description |
|--------|-------------|
| A | Run immediately if not yet run today. Idempotency key prevents duplicates. |
| B | Skip today. Wait until next scheduled time. |
| C | Run only if within a configurable catch-up window (e.g., 30 min after execution_time). |

**Recommended**: Option A — Run immediately if not yet run today.

**Rationale**: Matches Sprint 005 idempotency model. Same-day re-enable is a deliberate Owner action — the Owner expects the schedule to execute. Idempotency key (SHA256(job_type\|params\|date)) prevents duplicate runs. No new configuration needed.

**Impact**: Implementation in Slice C schedule activation logic. Next_run_at computed as: if today and execution_time has passed and no run exists for today → run now.

**Blocked if unresolved**: Slice C schedule activation behavior.

---

## 11. Migration Summary

| Item | Needs Migration? | Evidence |
|------|-----------------|----------|
| Guardian notification wiring | No | notification_events CHECK allows all sources |
| Committee notification wiring | No | notification_events CHECK allows all sources |
| Automation notification wiring | No | notification_events CHECK allows all sources |
| Backup notification wiring | No | notification_events CHECK allows all sources |
| Guardian daily schedule | No | guardian.evaluate_all in DB trigger + service allowlist |
| Backup daily schedule | **Yes — 0017** | backup.daily NOT in trigger (0008 line 53) or ALLOWED_JOB_TYPES (orchestration_scheduling.py line 28) |

Migration 0017 approach: `CREATE OR REPLACE FUNCTION fn_job_type_allowlist()` expanding to `('guardian.evaluate_all', 'guardian.evaluate_one', 'backup.daily')`. Update `ALLOWED_JOB_TYPES` in service layer. Downgrade restores original allowlist.

---

## 12. Non-Goals

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
