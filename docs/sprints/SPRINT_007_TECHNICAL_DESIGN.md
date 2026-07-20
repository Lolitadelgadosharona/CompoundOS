# Sprint 007 — Technical Design Gate

> **STATUS: OWNER DECIDED — 15/15 Resolved (2026-07-20). Implementation Not Authorized.**
>
> All 15 Owner Decisions are resolved.  This document reflects those decisions.
> Sprint 007 implementation is NOT AUTHORIZED.  Each Slice requires separate
> explicit Owner authorization after the Technical Design Gate merges.

---

## 1. Executive Summary

Sprint 007 is the last planned sprint on the current roadmap.  After Sprints
001–006, CompoundOS has a complete Foundation: Household, Policy, Portfolio
Snapshots, Guardian Monitoring, Automation (Worker + Schedules), Decision
Journal, and AI Investment Committee.  Personal V1 is approximately **55%
complete**.

Sprint 007 closes the gap between development prototype and usable personal
tool by adding **backup, export, recovery, health monitoring, and selective
local notification**.  The guiding principle: data safety is foundational —
no feature matters if the Owner's data can be permanently lost.

The Owner has resolved all 15 Owner Decisions: Sprint 007 is **Personal V1
Hardening + selective local Notification**, with external services (Market
Data, Family Goals, cloud backup, SaaS, external notifications) explicitly
deferred to V2.

---

## 2. Baseline

| Item | Value |
|------|-------|
| Main SHA | 4090e85b49f3c17d488c6eff4f1e8cea40a4e3a3 |
| Sprints 001–006 | Done |
| Migrations | 0012 (head) |
| PG tests | 491 passed, 0 failed |
| Non-PG tests | 136 passed |
| Frontend tests | 242 passed, shuffled |
| Personal V1 | ~55% |
| Sprint 007 | Technical Design Gate — Owner Decided |
| Product boundary | Personal-use-only, local-first, Owner-confirmed |

---

## 3. Resolved Scope (Owner Decided)

### What's In

**Slice A — Backup, Restore & Export (R2)**

- PostgreSQL backup: custom-format dump (`pg_dump --format=custom`) to
  Owner-selected local directory
- Manifest file per backup: timestamp, SHA256, file size, migration head
- SHA256 integrity hash computed on every backup
- `pg_restore` check on every backup output (manifest validation)
- Periodic restore verification to one-shot `_test` database
- Full PG suite (491 tests) for release gates and restore drills
- Retention: 7 daily + 4 weekly + 12 monthly.  **Last healthy backup
  must never be deleted**, even if retention calculation would do so.
- Explicit opt-in macOS launchd agent for automated daily backup, plus
  manual CLI for on-demand backup
- Data export: JSON + CSV for all Owner-facing entities (Household,
  Policy, Portfolio, Decisions, Committee Sessions)
- Server-side export files auto-deleted after 24h

**Slice B — Health Dashboard & Credential Management (R2)**

- `/health` frontend page with component-level read-only status
- Health checks: database connectivity, migration head, schema anomalies,
  provider reachability, Keychain status, disk free space
- Degraded states: each component can be healthy, degraded, or down
- Startup health enforcement: API/Worker fails closed on DB or schema
  anomalies.  Frontend degrades to read-only mode.
- Credential health: Keychain availability check, provider connectivity test

**Slice C — Lightweight Notification (R1)**

- macOS Notification Center delivery (via `osascript`)
- Internal persisted notification store (event history)
- Event types: Guardian threshold breach, Committee run complete,
  Automation run failure, Backup complete, Health degradation
- Deduplication: persisted fingerprint per event type + source entity ID,
  configurable window (default 24h)
- Quiet hours: default 22:00–08:00 (Owner-configurable).  Critical health
  events may bypass but must still deduplicate.
- No external notification services (email, SMS, push, webhook) — all
  deferred to V2

### What's NOT In (Per OD-7-13)

- Market Data ingestion → V2
- Family Goals & Reporting → V2
- External notifications (email, SMS, push) → V2
- Cloud backup → V2
- SaaS, multi-tenant, billing, public signup → V2
- Any external service not already approved in Sprints 001–006

---

## 4. Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Disk failure → data loss | **CRITICAL** | Automated local backup with retention + integrity verification |
| Corrupt backup → silent failure | **CRITICAL** | SHA256 hash + manifest + pg_restore check on every backup. Restore to `_test` DB verifies integrity. |
| Accidental deletion of last backup | **CRITICAL** | Retention policy **forbids** deleting last healthy backup, regardless of calculation |
| Backup destination unavailable | **HIGH** | Startup health check detects unavailable destination. Backup fails closed (no silent skip). |
| Disk full → backup fails, old backups removed | **HIGH** | Pre-backup disk-space check. Retention protects last healthy backup. Clear failure reporting. |
| Encryption key lost → backups unrecoverable | **HIGH** | Private recovery key stored in Keychain. Owner required to maintain offline copy. Fail closed if encryption not configured. |
| Cloud-sync directory chosen as backup dest → data leaked | **HIGH** | Cloud-sync destinations forbidden by default. Health check detects iCloud/Dropbox/OneDrive paths. |
| Unencrypted backup → data exposed on compromised machine | **HIGH** | Backup encryption via `age` with Owner-provided recipient. Fail closed if not configured. |
| Schema migration corrupts backup compatibility | **MEDIUM** | Each backup manifest records migration head. Restore to `_test` database before accepting. |
| Notification overload → Owner ignores | **LOW** | Deduplication + quiet hours. Critical events can bypass quiet hours but deduplicate. |
| Export file retained beyond 24h | **LOW** | Server-side cleanup timer. Frontend shows remaining lifetime. |

---

## 5. Backup State Machine

```
           ┌──────────┐
           │  idle     │
           └────┬──────┘
                │ trigger (manual or launchd)
                ▼
           ┌──────────┐
           │  preflight │─── disk check, dest available, encryption configured
           └────┬──────┘
                │ pass              fail ──► status=failed, error logged
                ▼
           ┌──────────┐
           │  running   │─── pg_dump --format=custom, compute SHA256
           └────┬──────┘
                │ success           error ──► status=failed, partial file removed
                ▼
           ┌──────────┐
           │ verifying  │─── manifest validation + pg_restore check
           └────┬──────┘
                │ pass              fail ──► status=failed, dump file marked suspect
                ▼
           ┌──────────┐
           │ completed  │─── manifest written, retention enforced, SHA256 stored
           └──────────┘
```

### Retention Enforcement

After each successful backup, retention is applied:

1. Scan all backups for the current destination directory
2. Categorize: daily (last 7), weekly (last 4 Sundays), monthly (last 12 1st-of-month)
3. **Guard: if deletion would remove the last healthy backup, refuse.**
4. Delete any backup not in any category
5. Log deletions (audit record)

### Encryption (OD-7-15)

Before backup:

1. Check that `age` binary is available
2. Check that `COMPOUNDOS_BACKUP_AGE_RECIPIENT` is configured
3. If either missing → **fail closed** (no unencrypted backup)
4. pg_dump pipes to `age --encrypt -r $RECIPIENT`
5. Recovery key checked: Keychain entry exists AND Owner has offline copy documented
6. Destination directory validated: not under any known cloud-sync path

---

## 6. Health States

| Component | Healthy | Degraded | Down | Degraded Behavior |
|-----------|---------|----------|------|-------------------|
| Database | Connected, migration head correct | N/A | Not reachable | API returns 503. Frontend read-only. |
| Migration | Head matches expected | Migration behind | Unknown | API returns 503. |
| Schema | All expected tables present | Extra/unknown tables | Tables missing | API returns 503. |
| Provider | Reachable, responds to health ping | Slow (>5s) | Unreachable | Committee unavailable. Other functions normal. |
| Keychain | Available, committee credential found | Available, no credential | Unavailable | API health shows warning. |
| Disk | >20% free | 10-20% free | <10% free | Backup blocked below threshold. |
| Backup destination | Available + writable | N/A | Unavailable | Backup blocked. |

### Startup Enforcement (OD-7-9)

On API/Worker startup:

1. Connect to database → if fail, **exit with error** (fail closed)
2. Check migration head → if mismatch, **exit with error**
3. Verify expected tables → if missing, **exit with error**
4. Check disk free space → if <10%, log warning but start
5. Check backup destination → if unavailable, log warning but start
6. Frontend: if API unavailable, show degraded read-only banner

---

## 7. Notification Dedup & Payload Contract

### Event Fingerprint

Each notification event is identified by:

```
fingerprint = SHA256(event_type + ":" + source_entity_id)
```

### Dedup Logic

1. On event fire, compute fingerprint
2. Query `notification_events` for same fingerprint with `delivered_at` within
   dedup window (default 24h, OD-7-10)
3. If found: **suppress** (do not deliver duplicate)
4. If not found: deliver, persist, store fingerprint

### Quiet Hours Bypass (OD-7-6)

- Default quiet hours: 22:00–08:00 local time (Owner-configurable)
- During quiet hours: non-critical events are persisted but not delivered
- **Exception**: critical health events (DB down, disk <10%) may bypass
  quiet hours but **must still deduplicate**

### Redacted Payload

Notification payloads displayed to the Owner must:
- Include event type, source entity ID, timestamp
- Include severity (info / warning / critical)
- **Never** include raw financial data, account numbers, portfolio values,
  policy text, or provider responses
- Summarize: e.g., "Guardian check 'equity_allocation' exceeded threshold."

---

## 8. Backup vs. Export — Distinct Concepts

| Aspect | Backup | Export |
|--------|--------|--------|
| Purpose | Disaster recovery | Data portability / analysis |
| Format | PostgreSQL custom dump (binary) | JSON + CSV |
| Encryption | Required (age) | Required if contains financial data |
| Retention | 7+4+12 pyramid | 24h auto-delete |
| Restore target | `_test` DB for verification | N/A (human-readable) |
| Automation | launchd agent + manual CLI | Manual only (Owner-initiated) |
| Integrity | SHA256 + manifest + pg_restore check | File written, hash logged |
| Scope | Entire database | Per-entity-type exports |

---

## 9. Safe Restore Policy (OD-7-8)

### Routine Verification

Every backup undergoes:
1. SHA256 hash match against manifest
2. `pg_restore --list` manifest validation
3. `pg_restore` to one-shot `compoundos_restore_test` database
4. Simple table-row-count verification

### Periodic Drill

At release gates and periodically:
- 1. Full PG suite (491 tests) against restored `_test` database
- 2. If 491/0: restore verified
- 3. If failures: backup flagged, Owner notified

### Break-Glass Restore (Future, Not Automated)

- Non-`_test` restore (i.e., to `compoundos` production database) is a
  **manual break-glass procedure only**.
- Never automated.  Never triggered by health checks.  Never scripted.
- Requires explicit Owner initiation with confirmation dialog.
- Restore procedure will be documented (procedure, not code) as part of
  Slice A deliverable.

---

## 10. Key Loss, Corruption, and Failure Modes

### Encryption Key Loss

- Private recovery key stored in macOS Keychain under
  `compoundos-backup-recovery-key`
- Owner **must** maintain an offline copy (seed phrase, printed QR,
  hardware key) — documented in setup guide
- On startup: health check verifies key exists in Keychain
- If key lost and no offline copy: **all backups are unrecoverable**
  (by design — encryption without key management is security theater)

### Corrupt Dump

- SHA256 mismatch → backup marked `failed`, dump file moved to
  suspect directory (not deleted — for forensic analysis)
- Manifest check failure → same treatment
- Restore verification failure → same treatment
- Alert: health dashboard shows recent backup status

### Disk Full

- Pre-backup check: `os.statvfs` for destination directory
- If free space < 2× current database size: block backup, log warning
- Health dashboard shows disk usage with warning thresholds
- Retention cleanup runs after successful backup only — if backup fails,
  retention is not applied (don't delete old backups when new one can't
  be created)

### Destination Unavailable

- Health check: `os.access(dest, os.W_OK)` on startup and before each
  backup
- If unavailable: backup blocked, health dashboard shows degraded
- Persistence: destination path configured by Owner, stored in CompoundOS
  configuration (not in database — must be available before DB startup)

---

## 11. Domain Model

### Backup Record

```
backup_records:
  id: UUID (PK)
  backup_type: enum (full) — always full in V1
  file_path: TEXT
  file_size_bytes: BIGINT
  sha256: TEXT
  manifest: JSON (timestamp, migration_head, pg_version, tables_count)
  encryption: enum (age) — always age in V1
  age_recipient: TEXT (public key fingerprint)
  started_at: TIMESTAMPTZ
  completed_at: TIMESTAMPTZ (nullable until done)
  status: enum (preflight, running, verifying, completed, failed)
  retention_category: enum (daily, weekly, monthly, locked) — locked = last healthy
  restore_verified: BOOL (result of periodic drill)
  error_detail: TEXT (nullable)
```

### Export Task

```
export_tasks:
  id: UUID (PK)
  entity_type: enum (household, policy, portfolio, decisions, committee_sessions)
  format: enum (csv, json)
  file_path: TEXT
  started_at: TIMESTAMPTZ
  completed_at: TIMESTAMPTZ
  status: enum (running, completed, failed)
  row_count: INTEGER
  expires_at: TIMESTAMPTZ (started_at + 24h)
```

### Notification Event

```
notification_events:
  id: UUID (PK)
  event_type: enum (guardian_breach, committee_complete, automation_failed,
                    backup_complete, health_degraded)
  severity: enum (info, warning, critical)
  source_entity_id: UUID (nullable)
  fingerprint: TEXT (UNIQUE constraint on fingerprint + delivered_at window)
  title: TEXT
  body: TEXT (redacted — never contains financial data)
  delivered_to_macos: BOOL
  delivered_at: TIMESTAMPTZ
  acknowledged_at: TIMESTAMPTZ (nullable)
  quiet_hours_bypass: BOOL
```

### Health Check Result (in-memory + cached, not persisted)

```
HealthStatus (computed on request):
  database: { connected: bool, migration_head: str, latency_ms: int }
  schema: { expected_tables: int, actual_tables: int, anomalies: [str] }
  provider: { name: str, reachable: bool, latency_ms: int, error: str|null }
  keychain: { available: bool, credential_count: int }
  backup_destination: { path: str, available: bool, writable: bool, free_bytes: int }
  disk: { free_bytes: int, total_bytes: int, free_percent: float }
  backup_status: { last_success: str|null, last_attempt: str|null, total_count: int }
  overall: enum (healthy, degraded, down)
```

---

## 12. API Contract (Future Slice B authorization)

When Slice B is authorized:

```
GET    /api/health/full              — Full health status object
GET    /api/health/component/{name}  — Single component status
POST   /api/backup                   — Trigger manual backup
GET    /api/backup/records           — List backup records (paginated)
GET    /api/backup/records/{id}      — Backup detail + manifest
POST   /api/export                   — Trigger export (body: entity_type, format)
GET    /api/export/tasks             — List export tasks
GET    /api/export/tasks/{id}        — Export detail + download link
GET    /api/notifications            — List recent notifications (paginated)
POST   /api/notifications/{id}/acknowledge — Acknowledge
GET    /api/notifications/config      — Get quiet hours + dedup config
PATCH  /api/notifications/config      — Update quiet hours + dedup config
```

All endpoints enforce household isolation.  Pagination uses `limit`/`offset`.

---

## 13. Safety Boundaries (All Designs)

Sprint 007 continues all existing CompoundOS boundaries:

1. No autonomous trading, order generation, or asset transfer.
2. No automatic Policy, Portfolio, Decision, or Guardian rule modification.
3. Owner explicitly confirms all state-mutating operations.
4. Backup encryption is mandatory — fail closed if not configured.
5. Cloud-sync backup destinations are forbidden by default.
6. Non-`_test` database restore is manual break-glass only — never automated.
7. Credentials and recovery keys never enter database, logs, or Git.
8. All destructive tests only run against `_test` databases.
9. No SaaS, multi-tenant, billing, public signup, commercial admin,
   or customer support.
10. No external notification services in V1.
11. Notifications never contain raw financial data.

---

## 14. Migration Strategy

If Slice A is authorized, migration 0013 would add:
- `backup_records` table
- `export_tasks` table
- `notification_events` table
- Named constraints, indexes, and CHECK constraints

All additive.  No modification to 0001–0012.  All tables follow existing
patterns: UUID PKs, TIMESTAMPTZ timestamps, CHECK constraints for enums,
household isolation context.

---

## 15. Testing Strategy

### Backup Tests

- pg_dump produces valid custom-format backup
- SHA256 computed and stored correctly
- Manifest contains all required fields
- pg_restore check succeeds on valid dump
- pg_restore check fails on corrupt dump
- Encrypted backup with age produces valid ciphertext
- Encryption fail-closed when recipient not configured
- Retention: 7+4+12 enforced, last healthy never deleted
- Destination unavailable → backup fails (does not silently skip)
- Disk full → backup blocked
- Cloud-sync path detected → backup blocked
- Restore to `_test` DB succeeds
- Full PG suite passes on restored DB
- launchd agent install/uninstall verified (macOS only, CI skipped)

### Export Tests

- CSV/JSON for each entity type produces valid output
- Row counts match source
- Schema stability: same data → identical CSV/JSON
- Files deleted after 24h

### Health Tests

- All components report correct status in each state
- Provider unreachable → health shows degraded
- Database unreachable → health shows down, API 503
- Startup fails closed on DB/schema anomaly
- Startup succeeds with warnings on disk/backup-dest issues

### Notification Tests

- macOS notification delivery (mocked in CI)
- Dedup: same fingerprint within window → suppressed
- Dedup: different fingerprint → delivered
- Quiet hours: non-critical suppressed during window
- Quiet hours: critical delivered but dedup still applies
- Payload: no financial data in notification body

---

## 16. Slice Boundaries

| Slice | Scope | Status |
|-------|-------|--------|
| Slice A | Backup, Restore, Export, Encryption, DR documentation | NOT AUTHORIZED |
| Slice B | Health Dashboard, Credential Management, Startup enforcement | NOT AUTHORIZED |
| Slice C | Lightweight Notification (macOS + persisted) | NOT AUTHORIZED |

Each slice:
- Is independently testable and mergeable
- Does not depend on later slices
- Can be deferred without breaking earlier slices
- Requires separate explicit Owner authorization

---

## 17. Acceptance Criteria

### Slice A
- Backup runs successfully on launchd schedule and via manual CLI
- Every backup: encrypted with age, SHA256 hash verified, manifest written
- `pg_restore` check passes on every backup
- Periodic restore to `_test` DB succeeds
- Full PG suite (491/0) passes on restored DB in release gate
- Retention enforces 7+4+12 with last-healthy protection
- Export produces valid JSON + CSV for all 5 entity types
- Export files auto-deleted after 24h
- Cloud-sync destination detection blocks backup
- Encryption fail-closed when not configured

### Slice B
- `/health` page shows all component statuses with history
- Component-level granularity (not binary)
- DB/schema anomaly → API fails closed, frontend shows read-only
- Provider unreachable → Committee unavailable, everything else works
- Disk low → backup blocked, health shows warning

### Slice C
- Notification delivered on Guardian breach, Committee completion,
  Automation failure, Backup completion, Health degradation
- Dedup: 24h window per event type + source entity
- Quiet hours: 22:00–08:00 default, critical bypass with dedup
- History view with pagination and acknowledgment
- No financial data in any notification body

---

## 18. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Encryption key lost | Medium | CRITICAL — backups unrecoverable | Keychain + mandatory offline copy + setup guide |
| Corrupt backup not detected | Low | CRITICAL | SHA256 + manifest + pg_restore check + periodic drill |
| Disk full during backup | Medium | HIGH | Pre-flight check, clear error |
| launchd agent fails silently | Medium | MEDIUM | Health dashboard shows last backup time |
| Backup destination on cloud-sync | Medium | HIGH | Detection and blocking |
| Migration incompatibility | Low | MEDIUM | Manifest records migration head. Drill catches. |
| Notification overload | Low | LOW | Dedup + quiet hours |

---

## 19. Owner Decisions

All 15 Owner Decisions are **resolved** as of 2026-07-20.  See
`SPRINT_007_OPEN_QUESTIONS.md` for the complete matrix.

| ID | Decision Summary | Resolution |
|----|-----------------|------------|
| OD-7-1  | Sprint 007 scope | Hardening + selective local Notification |
| OD-7-2  | Backup automation | launchd + manual CLI |
| OD-7-3  | Backup retention | 7+4+12, last healthy never deleted |
| OD-7-4  | Export formats | DR: custom dump. Owner: JSON+CSV |
| OD-7-5  | Notification delivery | macOS + persisted |
| OD-7-6  | Quiet hours | 22:00–08:00, critical bypass with dedup |
| OD-7-7  | Health dashboard | Component-level, read-only |
| OD-7-8  | Restore verification | hash/manifest/pg_restore + periodic PG suite |
| OD-7-9  | Startup enforcement | Fail closed on DB/schema |
| OD-7-10 | Notification dedup | Persisted fingerprint, 24h window |
| OD-7-11 | Export retention | 24h max |
| OD-7-12 | V1 completion | RPO ≤24h, RTO ≤2h, drill success, 0 B/H issues |
| OD-7-13 | Deferred to V2 | Market Data, Family Goals, external notifications, cloud backup, SaaS |
| OD-7-14 | Slice ordering | A (Backup) → B (Health) → C (Notification) |
| OD-7-15 | Backup encryption | age + Keychain + offline copy, fail closed |

---

## 20. Implementation Authorization Boundary

- This document authorizes **only** the Technical Design Gate.
- Merging this document's PR does **not** authorize any Sprint 007
  implementation.
- Each Slice (A, B, C) requires separate explicit Owner authorization.
- No backend, frontend, migration, or test changes are permitted based on
  this document alone.
