# Sprint 007 — Technical Design Gate

> **STATUS: Owner Decisions Required — Implementation Not Authorized**
>
> This document presents candidate analysis, technical comparisons, and
> Owner Decisions for Sprint 007.  No implementation is authorized.
> Each Slice requires separate explicit Owner authorization post-design-gate.

---

## 1. Executive Summary

Sprint 007 is the last planned sprint on the current roadmap.  After Sprints
001–006, CompoundOS has a complete Foundation: Household, Policy, Portfolio
Snapshots, Guardian Monitoring, Automation (Worker + Schedules), Decision
Journal, and AI Investment Committee with evidence pipeline, provider
abstraction, and seven-perspective analysis.

Personal V1 is approximately **55% complete**.

Sprint 007 must close the gap between the current development system and a
usable personal tool.  The critical question: what is the minimum set of
capabilities that makes CompoundOS genuinely useful to the Owner on their
local machine?

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
| Sprint 007 | Not Authorized / Not Started |
| Product boundary | Personal-use-only, local-first, Owner-confirmed |

### Sprint 007 in the Original Roadmap

The MASTER_PLAN backlog references two items relevant to Sprint 007:
- "Add notification escalation capabilities"
- "Complete Docker runtime verification in a Docker-enabled environment"

The VISION document lists as deferred:
- "Identify which future data sources will be supported"

No other explicit Sprint 007 scope exists in the current docs.

---

## 3. Candidate Comparison

Four candidates evaluated on equal footing.  None is a straw man.

### Candidate A: Market Data & External Evidence Ingestion

**Goal:** Provide the AI Investment Committee with verifiable external data —
prices, indices, exchange rates, macro indicators — so that Macroeconomic
Context and Risk perspectives have real evidence beyond "insufficient."

**Scope:**
- Provider abstraction for market data sources (free tier first)
- Ingestion pipeline: fetch → validate → timestamp → hash → store
- Evidence integration with Sprint 006 evidence contract
- Freshness tracking, stale thresholds
- Failure isolation when providers are unavailable

**What it enables:**
- Committee Macro section has real data instead of "insufficient"
- Risk assessment has market context
- Future: portfolio valuation, performance tracking

**Concerns:**
- External provider dependency (API limits, cost, reliability)
- Data licensing — free tiers may prohibit personal-use attribution
- Privacy — even anonymized queries leak investment interest
- Sprint 006 OD-6-15 explicitly deferred external market data
- Complex failure modes: stale data vs. no data

| Dimension | Rating |
|-----------|--------|
| Owner value | ★★★★ — meaningful context for Committee |
| Personal V1 completion | ★★★ — adds data, not capability |
| Data/privacy risk | HIGH — external queries leak intent |
| External dependency | Provider APIs, licenses |
| Cost | Variable — free tiers exist, premium tiers costly |
| Testability | Medium — needs mock provider |
| Local-first | Low — external service required |
| Reuses Sprints 001–006 | Evidence contract (006), Committee (006) |
| Essential for V1 | No — deferred by OD-6-15 |

### Candidate B: Family Goals & Personal Reporting

**Goal:** Let the Owner define long-term family goals (education, retirement,
charitable giving, cash reserves), link them to Policy allocations, and
generate periodic reports showing progress.

**Scope:**
- Goal entity: name, type, target amount, time horizon, priority
- Goal buckets: current allocation, projected growth, gap analysis
- Monthly/quarterly reports: summary of Policy, Portfolio, Guardian, Decisions
- PDF/HTML export for personal review

**What it enables:**
- Purpose-driven investing: goals, not just allocations
- Long-term tracking: are we on track?
- Reports for personal financial review

**Concerns:**
- Projections require assumptions (growth rates, inflation) — risk of
  appearing to promise outcomes
- Gap analysis borders on financial advice — needs strict neutral language
- Two new domains (Goals + Reports)
- Reporting is a consumer, not a producer — needs everything else working first

| Dimension | Rating |
|-----------|--------|
| Owner value | ★★★★ — purpose and visibility |
| Personal V1 completion | ★★★ — adds goals, not infrastructure |
| Explainability | Medium — projections are assumption-laden |
| External dependency | None (V1) |
| Testability | High — deterministic calculations |
| Local-first | High — all local |
| Reuses Sprints 001–006 | Policy, Portfolio, Decisions |
| Essential for V1 | No — deferred to V2 |

### Candidate C: Notification & Escalation

**Goal:** Add local notification capability for Guardian threshold breaches,
Committee report completion, Automation run failures, and other events the
Owner should be aware of.

**Scope:**
- Notification rule engine: event type → severity → delivery
- Local delivery: Hermes terminal message, macOS notification center
- Quiet hours configuration
- Deduplication (same event, same period)
- Event history and acknowledgment

**What it enables:**
- Owner knows when Guardian detects drift without checking manually
- Committee run completion notification after long provider calls
- Automation failures surface immediately

**Concerns:**
- Currently one consumer (Guardian). Committee runs are manual.
- Without external delivery (email/SMS/push), notifications are only useful
  when the Owner is at their Mac
- macOS Notification Center API is simple but platform-locked

| Dimension | Rating |
|-----------|--------|
| Owner value | ★★★ — passive awareness |
| Personal V1 completion | ★★ — nice-to-have, not core |
| Data/privacy risk | Low — local only |
| External dependency | None (local macOS) |
| Cost | None |
| Testability | Medium — platform-specific |
| Local-first | High |
| Reuses Sprints 001–006 | Guardian (004), Automation (005), Committee (006) |
| Essential for V1 | No — quality of life, not functional |

### Candidate D: Personal V1 Hardening & Operational Readiness

**Goal:** Make CompoundOS a reliable, maintainable personal tool.  Add backup,
export, health monitoring, credential management UX, and disaster recovery
so the Owner's data is never at risk.

**Scope:**
- PostgreSQL backup/restore (pg_dump + pg_restore, automated)
- Data export: CSV/JSON for all Owner-facing entities
- Health dashboard: DB connectivity, migration status, disk usage, provider reachability
- Credential health: Keychain status, provider connectivity test
- Startup health check with clear failure reporting
- Graceful degradation when services are unavailable
- Versioned backup retention policy
- Disaster recovery documentation

**What it enables:**
- Owner trust: data is safe, recoverable, exportable
- Operational confidence: health status visible at a glance
- Foundation for any future V2 features

**Concerns:**
- Backup scripts need scheduling (cron or Hermes cron)
- Export format decisions (CSV schema stability)
- Health dashboard is a new frontend page
- Not "sexy" — no new AI, no new analysis, no new user workflows

| Dimension | Rating |
|-----------|--------|
| Owner value | ★★★★★ — data safety is foundational trust |
| Personal V1 completion | ★★★★★ — the system isn't "done" without this |
| Data/privacy risk | Low — all local, export is Owner-initiated |
| External dependency | None |
| Cost | None |
| Explainability | High — deterministic operations |
| Local-first | High — entirely local |
| Reuses Sprints 001–006 | All (backup touches everything) |
| Essential for V1 | **YES** — operational integrity is a requirement |
| Can be deferred to V2? | No — deferred backup = data at risk |

---

## 4. Recommendation

**Primary: Candidate D (Personal V1 Hardening).**
**Secondary element: Candidate C (Notification) — selective, lightweight.**

### Rationale

1. **Data safety is non-negotiable.**  After 6 sprints of building features,
   the system has zero backup, zero export, and zero operational health
   monitoring.  Every day the Owner enters data into CompoundOS, that data is
   at risk of loss.  Backup is not a feature — it's a requirement.

2. **Personal V1 without hardening is incomplete.**  The current system is a
   development prototype.  It runs via `uvicorn --reload` and `npm run dev`.
   Hardenening transforms it into something the Owner can rely on.

3. **Hardening unblocks all future work.**  Every Sprint 007 candidate and
   every V2 feature benefits from backup, export, and health monitoring.

4. **Notification is the smallest, highest-value add.**  A lightweight
   notification system for Guardian events and Committee completions adds
   immediate quality of life with minimal complexity.  It can ship as a
   secondary slice within the hardening sprint.

5. **Market data and Family Goals are deferred to V2.**  Market data was
   explicitly deferred by OD-6-15.  Family Goals are a major new domain
   that needs its own Technical Design Gate and should follow operational
   maturity.

### Cost of Not Choosing

| Candidate | Cost of deferral |
|-----------|-----------------|
| A (Market Data) | Committee Macro section remains "insufficient."  Mildly frustrating but not blocking.  OD-6-15 already accounted for this. |
| B (Family Goals) | No goal tracking.  Owner uses external tool.  Can be added in V2. |
| C (Notification) | Owner must manually check Guardian/Automation.  Mild inconvenience. |
| D (Hardening) | **Data at risk of permanent loss with no recovery path.**  Unacceptable for a system storing financial information. |

---

## 5. Recommended Scope: Personal V1 Hardening + Lightweight Notification

### Slice A: Backup, Export & Recovery (R2)

- PostgreSQL backup: pg_dump to timestamped files, retention policy
- PostgreSQL restore: pg_restore with verification
- Data export: CSV/JSON for Household, Policy, Portfolio, Decisions, Committee
- Export schema stability (CSV headers, JSON structure)
- Hermes cron job for automated daily backup
- Disaster recovery procedure (documented)
- Backup integrity verification (restore to `_test` database, run PG suite)
- Export integrity verification (roundtrip import validation tests)

### Slice B: Health Dashboard & Credential Management (R2)

- Health endpoint expansion: DB, migration, provider reachability
- /health frontend page: status cards, last check timestamps
- Credential health: Keychain status, provider connectivity test
- Graceful degradation: what works when components fail
- Dependency health (Python, Node, PostgreSQL, Keychain)
- Startup health check (blocking if critical components down)

### Slice C: Lightweight Notification (R1)

- macOS Notification Center integration (osascript)
- Event types: Guardian threshold breach, Committee run complete,
  Automation run failed, Backup complete
- Deduplication: same event type within configurable window
- Quiet hours: Owner-configurable time windows
- Notification history: last N events, acknowledgment
- Hermes terminal integration (existing MESSAGE delivery)

---

## 6. Architecture Alternatives (Candidate D as Primary)

### Approach 1: Minimal Shell Scripts

Backup = shell script calling pg_dump.  Health = shell script checking psql.
Export = shell script running SELECT queries.  All invoked manually or via
Hermes cron.

| Pros | Cons |
|------|------|
| Simplest possible | No frontend, no UX |
| No new Python/TS code | Not integrated into CompoundOS app |
| Quickest to implement | No health dashboard |
| Easy to test via subprocess | Fragile — shell script edge cases |

### Approach 2: Backend Services + Health API + Simple Frontend  ☆ RECOMMENDED

Backup/export/health as Python services with API endpoints.  Health dashboard
as a new `/health` frontend page.  Backup triggered via Hermes cron or manual
button.  Export via download endpoints.

| Pros | Cons |
|------|------|
| Integrated with CompoundOS | More code than Approach 1 |
| Frontend health dashboard | New `/health` page |
| API-driven: testable, auditable | Service layer complexity |
| Reuses existing patterns (models, services, routers) | |
| Backup integrity verified via test suite | |

### Approach 3: External Tool Dependencies

Use pgAdmin or DBeaver for backup.  Use macOS Time Machine for file backup.
No CompoundOS code changes needed.

| Pros | Cons |
|------|------|
| Zero CompoundOS code | Not integrated |
| Proven, mature tools | Owner must learn external tools |
| No maintenance burden | No automated scheduling |
| | No health integration |
| | Backup restoration is manual and error-prone |

### Recommendation: Approach 2

Approach 2 is the right balance: integrated into CompoundOS (consistent UX),
API-driven (testable), automated (cron), but not over-engineered.  The
backup/export services are simple deterministic operations — no LLM, no
external providers.

---

## 7. Domain Model

### Backup Record

```
backup_records:
  id: UUID (PK)
  backup_type: enum (full, incremental)
  file_path: TEXT
  file_size_bytes: BIGINT
  started_at: TIMESTAMPTZ
  completed_at: TIMESTAMPTZ (nullable)
  status: enum (running, completed, failed)
  integrity_verified: BOOL
  retention_policy: TEXT
  created_at: TIMESTAMPTZ
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
```

### Notification Event

```
notification_events:
  id: UUID (PK)
  event_type: enum (guardian_breach, committee_complete, automation_failed, backup_complete)
  source_entity_id: UUID (nullable)
  severity: enum (info, warning, critical)
  title: TEXT
  body: TEXT
  delivered_at: TIMESTAMPTZ
  acknowledged_at: TIMESTAMPTZ (nullable)
  dedup_key: TEXT (event_type + source_entity_id + window)
```

### Health Check Result (in-memory, not persisted)

```
HealthStatus:
  database: { connected: bool, migration_head: str, latency_ms: int }
  provider: { name: str, reachable: bool, error: str|null }
  keychain: { available: bool, provider_credential_count: int }
  disk: { path: str, free_bytes: int, total_bytes: int }
  backend: { version: str, uptime_seconds: int }
```

---

## 8. API Contract (future Slice B authorization)

If notification is approved, these endpoints would be added:

```
GET    /api/health/full              — Full health status
GET    /api/health/provider          — Provider connectivity check
POST   /api/backup                   — Trigger backup
GET    /api/backup/records           — List backup records
GET    /api/backup/records/{id}      — Backup detail
POST   /api/export                   — Trigger export (body: entity_type, format)
GET    /api/export/tasks             — List export tasks
GET    /api/export/tasks/{id}        — Export task detail + download link
GET    /api/notifications            — List recent notifications
POST   /api/notifications/acknowledge — Acknowledge notification
```

---

## 9. Safety Boundaries (all designs)

Sprint 007 continues all existing boundaries:

1. No autonomous trading, order generation, or asset transfer.
2. No automatic Policy, Portfolio, Decision, or Guardian rule modification.
3. Owner explicitly confirms all state-mutating operations.
4. External data (if market data approved) must carry source, timestamp,
   freshness, confidence, and content hash.
5. Model training knowledge must never be presented as real-time evidence.
6. Predictions must never be presented as guarantees.
7. Unnecessary sensitive raw data must not be stored.
8. Credentials must never enter database, logs, or Git.
9. All destructive tests only run against `_test` databases.
10. Backup/restore design must include integrity verification.
11. No SaaS, multi-tenant, billing, public signup, commercial admin,
    or customer support.

---

## 10. Backup/Restore Design

### Backup Flow

1. Owner triggers backup (manual or cron)
2. `pg_dump --format=custom` to timestamped file in `~/.compoundos/backups/`
3. SHA256 hash computed and stored
4. Backup record created (status=running)
5. On completion: status=completed, file_size recorded
6. Retention: keep last 7 daily + last 4 weekly + last 12 monthly
7. Older backups auto-pruned

### Restore Flow

1. Owner selects backup file
2. Restore to `compoundos_restore_test` database (NOT production)
3. Run full PG test suite against restored database
4. If 491/0: Owner confirms production restore
5. `pg_restore` to `compoundos` production database
6. Verify: run PG tests against production database
7. Log restore event

### Export Design

1. Owner selects entity type + format
2. Backend queries entity with household filter
3. Writes to timestamped file in `~/.compoundos/exports/`
4. Download link returned to frontend
5. Files expire after 24 hours (privacy)

---

## 11. Migration Strategy

If the recommended scope (Hardening + Notification) is approved, migration
0013 would add:
- `backup_records` table
- `export_tasks` table
- `notification_events` table
- Named constraints and indexes

All additive.  No modification to 0001–0012.

---

## 12. Testing Strategy

### Backup/Restore Tests

- pg_dump produces valid custom-format backup
- pg_restore to test database succeeds
- Restored database passes all 491 PG tests
- Backup record status transitions (running → completed/failed)
- Retention policy enforcement
- Integrity hash verification

### Export Tests

- CSV/JSON export for each entity type produces valid output
- Row counts match source database
- Schema stability: same test data produces identical CSV
- Export task lifecycle

### Health Tests

- Health endpoint returns correct status for each component
- Provider unreachable → health shows degraded
- Database unreachable → health shows critical
- Keychain missing credential → health shows warning

### Notification Tests

- macOS notification center delivery (mocked in CI)
- Deduplication window enforcement
- Quiet hours respect
- Acknowledgment flow
- Event history pagination

---

## 13. Slice Boundaries

| Slice | Scope | Owner Authorization |
|-------|-------|---------------------|
| Slice A | Backup, Export, Recovery | Separate |
| Slice B | Health Dashboard, Credential UX | Separate |
| Slice C | Lightweight Notification | Separate |

Each slice:
- Is independently testable and mergeable
- Does not depend on later slices
- Can be deferred without breaking earlier slices

---

## 14. Acceptance Criteria

### Slice A
- Backup runs successfully on command and via cron
- Restore to test database succeeds with 491/0 PG tests
- Export produces valid CSV/JSON for all 5 entity types
- 7/4/12 backup retention policy enforced
- Disaster recovery procedure documented

### Slice B
- /health page shows all component statuses
- Provider connectivity test works (fake provider in CI)
- Health degrades gracefully when components unavailable
- Startup health check blocks if critical components down

### Slice C
- Notification fired on Guardian breach events
- Notification fired on Committee run completion
- Notification fired on Automation run failure
- Deduplication prevents duplicate notifications within window
- Quiet hours respected
- Notification history visible

---

## 15. Owner Decisions

| ID | Question | Option A | Option B | Option C | Recommendation | Rationale | Trade-off | Blocks |
|----|----------|----------|----------|----------|----------------|-----------|-----------|--------|
| OD-7-1 | Sprint 007 scope | Hardening + Notification | Hardening only | Market Data | **A: Hardening + Notification** | Data safety is critical. Notification adds immediate value with minimal scope. Market data was deferred by OD-6-15. | Option B leaves no user-visible improvement. Option C reverses OD-6-15. | All Slice authorization |
| OD-7-2 | Backup automation | Hermes cron (daily) | Manual only | External cron/launchd | **A: Hermes cron** | Integrated with existing infrastructure. Same scheduling as Guarduan checks. | Manual backup is forgettable. External cron adds ops burden. | Slice A |
| OD-7-3 | Backup retention | 7 daily + 4 weekly + 12 monthly | Keep last 30 only | Keep everything | **A: 7+4+12** | Standard retention pyramid. Balances disk usage with recovery granularity. | Option B loses older references. Option C fills disk. | Slice A |
| OD-7-4 | Export formats | CSV + JSON | CSV only | JSON only | **A: CSV + JSON** | CSV for spreadsheet analysis, JSON for programmatic use. | Slightly more code. | Slice A |
| OD-7-5 | Notification delivery | macOS Notification Center | Hermes terminal only | Both | **A: macOS Notification Center** | Native OS integration for personal Mac. Low complexity. | Terminal-only requires active session. | Slice C |
| OD-7-6 | Notification quiet hours | Owner-configurable | None (always deliver) | Fixed 22:00–07:00 | **A: Owner-configurable** | Respects Owner's schedule. Generic defaults aren't personal. | Requires config UI. | Slice C |
| OD-7-7 | Health dashboard granularity | Component-level (DB, provider, disk) | Binary healthy/degraded | Full metrics (CPU, memory, latency) | **A: Component-level** | Actionable information without monitoring-platform complexity. | Option B hides useful detail. Option C over-engineers. | Slice B |
| OD-7-8 | Restore verification | Run full PG suite | Schema check only | No verification | **A: Run full PG suite** | 491 tests provides strong confidence. Schema check doesn't verify data integrity. | Longer restore time (~30s vs ~2s). | Slice A |
| OD-7-9 | Startup health check | Block if DB down, warn otherwise | Warn for all failures | Skip startup check | **A: Block if DB down, warn otherwise** | Database is required. Provider/other issues can degrade gracefully. | Startup blocks on DB failure. | Slice B |
| OD-7-10 | Notification dedup window | Owner-configurable (5m–24h) | Fixed 1 hour | No dedup | **A: Owner-configurable** | Different events need different windows. Committee runs are infrequent; Guardian checks may be frequent. | Configuration complexity. | Slice C |
| OD-7-11 | Export file retention | 24 hours then auto-delete | Keep until Owner deletes | No retention (download only) | **A: 24 hours** | Privacy: export files contain financial data. Auto-deletion prevents accumulation. | Owner must re-export. | Slice A |
| OD-7-12 | Personal V1 completion definition | All Sprints 001–007 Done + 0 data loss risk + backup/export working | All features Done regardless of ops | Leave undefined | **A: All Done + 0 data loss risk** | A system isn't "done" if data isn't safe. Operational readiness is part of the definition. | None — this is the standard. | Sprint 007 scope |
| OD-7-13 | Deferred to V2 | Market Data (from OD-6-15), Family Goals, Multi-user, SaaS, Mobile, Public API | Include Market Data in Sprint 007 | Include Family Goals | **A: Defer to V2** | OD-6-15 was explicit. Focus Sprint 007 on Personal V1 completion. | V2 timeline unspecified. | Sprint 007 scope |
| OD-7-14 | Slice ordering | Backup/Export first (Slice A), then Health (Slice B), then Notification (Slice C) | Notification first | Health first | **A: Backup/Export first** | Data safety is highest priority. Health and notification are meaningless if data is at risk. | Notification comes last. | Slice authorization order |

---

## 16. Implementation Authorization Boundary

- This document authorizes **only** the Technical Design Gate.
- Merging this document's PR does **not** authorize any Sprint 007
  implementation.
- Each Slice (A, B, C) requires separate explicit Owner authorization.
- No backend, frontend, migration, or test changes are permitted based on
  this document alone.
- Sprint 007 implementation is blocked until all 14 Owner Decisions are
  explicitly resolved by the Owner.

---

## 17. Review Status

- Technical Design: Pending Owner Decisions
- Independent review: Not yet dispatched (Draft PR)
- Owner Decisions: 0/14 resolved
