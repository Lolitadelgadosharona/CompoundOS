# Architecture

## Overview

CompoundOS will use a modular monorepo with a Next.js frontend, a FastAPI backend, PostgreSQL, Redis, Docker-based local development, and future decision-support services.

## Sprint 002 Slice 1 Architecture

- Frontend: Next.js 16.2.10 App Router application with TypeScript in `frontend/`
- Backend: FastAPI routers, Pydantic contracts, a small service transaction layer,
  and SQLAlchemy repositories in `apps/api/`
- Data: PostgreSQL through synchronous SQLAlchemy 2.x and psycopg 3; Redis carries
  no Slice 1 product logic
- Local infrastructure: `compose.yaml` defines the web, API, PostgreSQL, and Redis
  services using Dockerfiles aligned with the current repository paths; runtime
  verification remains pending in a Docker-enabled environment
- Migration: explicit Alembic revisions in `migrations/`; application startup never
  calls `create_all`
- Validation: real PostgreSQL integration tests plus pytest and Ruff for the
  backend; Vitest, ESLint, TypeScript, and the Next.js production build for the
  frontend
- Safety constraints: Pydantic performs request validation and named PostgreSQL
  checks independently enforce the same character limits and currency format

## Sprint 002 Slice 2A Architecture

Slice 2A extends the persistence foundation without adding a Policy use case or
user-facing workflow:

- Alembic revision `0002_investment_policy_foundation` extends `audit_events` and
  creates the five approved Policy, Draft, allocation, and immutable Version tables.
- `audit_events.sequence_number` is a PostgreSQL-generated identity value used for
  deterministic insertion ordering. It may contain rollback gaps and does not
  represent concurrent transaction commit order.
- Named PostgreSQL checks, unique constraints, foreign keys, and indexes enforce
  Policy/Draft cardinality, allocation bounds, normalized-name uniqueness,
  version numbering, and at most one current `published` Version.
- PostgreSQL trigger functions permit only the internal unsealed snapshot-build
  interval, exact sealing, and exact `published` to `superseded` transition.
- A deferred constraint trigger prevents committing an unsealed Version.
- Version allocation rows are insertable only before parent sealing and are never
  updateable or deletable.
- SQLAlchemy models mirror the migration. No Policy repository workflow, service,
  request schema, router, endpoint, or frontend is introduced in Slice 2A.
- Real PostgreSQL tests cover fresh/incremental migration, downgrade/re-upgrade,
  named constraints, trigger transitions, rollback, and AuditEvent sequencing.

## Sprint 002 Slice 2B Architecture

Slice 2B adds the approved local-only backend workflow without changing the
Slice 2A schema:

- `policy_schemas.py` owns strict request/response contracts, decimal-string
  validation, and Unicode allocation-name normalization.
- `repositories/policies.py` contains SQLAlchemy reads, row-locking queries,
  collection replacement, and non-sensitive AuditEvent construction.
- `services/policies.py` owns transaction boundaries and maps only approved named
  database conflicts or explicit lifecycle/revision conflicts.
- `routers/policies.py` exposes the approved `/api/policies` contracts and neutral
  400/404/409/422 responses without leaking SQL errors or sensitive values.
- Mutations that touch both rows lock Policy before Draft. Publication supersedes
  the prior Version, snapshots the Draft, seals the new Version, consumes the
  Draft, and writes ordered AuditEvents in one transaction.
- Target percentages remain decimal strings at the API boundary, `Decimal` in
  Python, and `NUMERIC(5,2)` in PostgreSQL.
- Policy audit reads select the newest limited window by descending database
  sequence and return that window ascending.
- Draft text updates materialize a complete scalar response snapshot while the
  Policy-then-Draft transaction remains locked. The service commits before
  returning that snapshot and performs no Draft or allocation query after commit.
- Policy creation uses a strict empty-object request contract: the body may be
  omitted or `{}`, while non-empty objects and non-object JSON are rejected before
  persistence.

No frontend, authentication, recommendation, Guardian, AI, Broker, trading, or
Decision Journal module is introduced in Slice 2B.

## Sprint 002 Slice 2C Architecture

Slice 2C adds the approved browser workflow without changing the Slice 2B API or
Slice 2A persistence design:

- `frontend/app/policy/page.tsx` defines the App Router boundary and delegates all
  interactive behavior to a client component.
- `frontend/app/policy/policy-client.tsx` keeps the saved server snapshot separate
  from local Draft text and allocation edits. The core workspace, Version history,
  selected detail, and audit timeline have independent loading and error states.
- `frontend/lib/policy-api.ts` is the typed browser boundary for the approved
  Policy endpoints. Reads may be aborted to prevent stale responses from replacing
  newer state; mutations are never automatically retried.
- Initial Household and Policy reads run in parallel. After Policy presence is
  known, core Draft/Published reads are isolated from auxiliary history/audit
  failures. History and audit each use abort plus monotonic generation guards;
  paginated history additionally validates its requested cursor before merging.
- Target percentages stay as decimal strings at the browser/API boundary. Display
  totals use strict parsing into integer hundredths and integer addition, with no
  `Number`, `parseFloat`, rounding, recommendation, or evaluation step.
- Explicit saves send only changed Draft text fields or the full ordered allocation
  collection with the current expected revision. Successful responses become the
  new saved snapshot; failed mutations retain local edits.
- The workspace owns semantic text/allocation dirty flags. Publication is disabled
  while either editor differs from its latest server snapshot, and any reload that
  would replace dirty editor state requires explicit page-level confirmation.
- Publication is a read-only review of the saved Draft snapshot followed by an
  explicit confirmation. The server remains authoritative for completeness,
  revision, and publication success.
- Version history is read-only and cursor-paginated newest first using stable
  Version identity deduplication. Audit events retain server-returned sequence
  order. Both auxiliary resources have GET-only recovery that never replays a
  mutation. Network and HTTP server failures use distinct neutral error classes.

Slice 2C adds no backend module, database change, authentication, recommendation,
Guardian, AI, Broker, trading, actual-holdings, or Decision Journal behavior.

## Sprint 002 Slice 3A Architecture

Slice 3A extends the persistence foundation with Decision Journal immutability
without adding a Decision use case or user-facing workflow:

- Alembic revision `0003_decision_journal_foundation` creates four Decision
  Journal tables on top of the existing Household, Policy, and Audit schema.
- `decisions` is the stable identity row: `id`, `household_id`, `status`,
  `created_at`, and optional `archived_at`/`archive_reason`. Status is
  constrained to `draft`, `confirmed`, or `archived`.
- `decision_drafts` holds the mutable working draft for each Decision identity.
  A UNIQUE constraint on `decision_id` enforces at most one Draft per Decision.
  The Draft-to-Decision FK uses ON DELETE CASCADE to enable atomic discard of
  never-confirmed identities.
- `decision_confirmed_snapshots` is the immutable point-in-time record created
  at Confirm. A BEFORE INSERT OR UPDATE OR DELETE trigger prohibits all
  modification after insertion. Each snapshot references the current Published
  InvestmentPolicyVersion via RESTRICT FK.
- `decision_corrections` is an append-only full-replacement snapshot. A BEFORE
  trigger validates Decision status (`confirmed` or `archived`), actor
  (`local-owner`), correction number positivity, and snapshot ownership
  consistency. UPDATE and DELETE are unconditionally forbidden.
- Five PL/pgSQL trigger functions enforce lifecycle transitions
  (`draft→confirmed`, `confirmed→archived`, `archived→confirmed`), delete
  guards (only `draft` status with no snapshot may be deleted), snapshot
  immutability, correction validation, and deferred cross-table consistency.
- A CONSTRAINT TRIGGER (`DEFERRABLE INITIALLY DEFERRED`) on decisions verifies
  at COMMIT time that `draft` status has a Draft row and no snapshot, while
  `confirmed`/`archived` status has a snapshot and no Draft.
- `decision_date` is DATE type with `decision_date <= CURRENT_DATE` enforced by
  named CHECK constraints on snapshots and corrections.
- Per-Decision correction numbering uses `UNIQUE(decision_id, correction_number)`.
  The service computes `MAX+1` under a Decision row lock; the database does not
  claim to guarantee gapless sequences.
- SQLAlchemy models mirror the migration. No Decision service, repository
  workflow, API endpoint, Pydantic contract, router, or frontend is introduced.
- Real PostgreSQL tests cover migration lifecycle, schema inspection, data model
  constraints, lifecycle transitions, discard foundation, snapshot immutability,
  correction behavior, and trigger inspection.

## Sprint 002 Slice 3B Architecture

Slice 3B adds the Decision Journal backend workflow and API on top of the
Slice 3A persistence foundation:

- `decision_schemas.py` defines strict Pydantic request/response contracts with
  extra=forbid, trim, Unicode code-point length limits, and mechanical ISO date
  validation. Confirm requires title, decision_summary, rationale, and
  decision_date. decision_date forbids future dates; review_date allows future.
- `repositories/decisions.py` provides SQLAlchemy queries for all Decision
  tables with FOR UPDATE support, cursor pagination for audit events, and
  per-Decision Correction numbering via MAX+1 under lock.
- `services/decisions.py` owns transaction boundaries for create, update,
  discard, confirm, archive, unarchive, and append-correction. Lock ordering is
  Policy→Decision→Draft. Confirm is a 13-step atomic transaction consuming the
  Draft and inserting an immutable snapshot. Discard atomically deletes both
  Draft and Decision identity for never-Confirmed Decisions (OD-S3-13 Option A).
  Corrections use full replacement snapshots with per-Decision sequential
  numbering computed under the Decision row lock.
- `routers/decisions.py` exposes twelve endpoints with prefix `/api/decisions`,
  mapping domain exceptions to 400/404/409/422 HTTP responses. Detail endpoint
  constructs original/effective snapshots from transaction-scoped data.
- AuditEvent metadata is restricted to changed_fields, draft_revision,
  policy_version_number, and correction_number. No Decision text, Correction
  text, Policy text, or correction_count is included.
- Seven action names: decision.draft.created, decision.draft.updated,
  decision.draft.discarded, decision.confirmed, decision.archived,
  decision.unarchived, decision.correction.appended.
- Real PostgreSQL tests cover creation, draft CRUD, confirm, discard,
  archive/unarchive, corrections, audit events, detail views, and Household
  timeline inclusion. Non-PostgreSQL tests cover Pydantic schema validation.
- Slice 3B adds no frontend, migration, dependency, authentication,
  recommendation, Guardian, AI, Broker, trading, or Slice 3C behavior.

## Module Boundaries

- `routers/households.py`: four approved HTTP contracts and status mapping
- `schemas.py`: strict request/response contracts and technical field limits
- `services/households.py`: create/update transaction boundaries and domain errors
- `repositories/households.py`: SQLAlchemy queries and minimal AuditEvent writes
- `models.py`: only `household_profiles` and `audit_events`
- `frontend/app/household/`: local-only create/read/update/audit workflow
- `frontend/lib/household-api.ts`: typed browser-to-API boundary
- `frontend/app/policy/`: local-only Policy Draft, publication, immutable history,
  and audit workflow
- `frontend/lib/policy-api.ts`: typed browser-to-Policy-API boundary and exact
  integer-hundredths display helpers
- `decision_schemas.py`: strict Decision request/response contracts
- `repositories/decisions.py`: Decision queries, FOR UPDATE, cursor pagination
- `services/decisions.py`: Decision transaction boundaries and domain errors
- `routers/decisions.py`: twelve Decision Journal HTTP endpoints

No Policy, Allocation, Journal, User, Account, AI, Guardian, Broker, or trading
module is created in Slice 1.

## Transaction Flow

1. FastAPI validates and sanitizes the request contract.
2. A request-scoped synchronous SQLAlchemy session enters one short transaction.
3. The service inserts or updates HouseholdProfile and flushes it.
4. The repository inserts an AuditEvent containing changed field names only.
5. Both writes commit together; any failure rolls both back.

The database singleton uses a required boolean sentinel constrained to true and
unique across `household_profiles`. It prevents concurrent requests from storing
two profiles; the API maps the resulting integrity conflict to HTTP 409.

Frontend household mutations and AuditEvent refreshes have separate outcomes. A
successful mutation updates the profile and exits edit mode even if the following
audit GET fails. The timeline retains prior data, shows an independent error, and
offers a GET-only retry; mutations are never automatically replayed.

## Migration and CI

Alembic revision `0001_household_persistence` upgrades an empty database and
creates only the two approved product tables. The initial downgrade is provided
for development, without promising a production downgrade strategy. CI starts an
isolated PostgreSQL 16 service, runs `alembic upgrade head` and `alembic current`,
then runs repository/API/rollback tests against that real database. SQLite and
mocks do not replace these integration tests. CI sets the project-specific
`COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1` gate and runs the `postgres`-marked suite
explicitly. A missing test database fails in that mode; local runs without a
configured PostgreSQL database may skip the marked integration suite.

## Local Network Boundary

Browser requests use `NEXT_PUBLIC_API_URL` to reach FastAPI. CORS permits only the
two local web origins. Compose publishes all four host ports on `127.0.0.1`; an
automated expanded-config check rejects broader default bindings. Containers may
listen on `0.0.0.0` internally. This is not authentication and is not suitable for
public deployment.

## Repository Layout Decision

The mixed `apps/api/` and `frontend/` layout is intentional for Sprint 001.1
because it is functional, small, and already validated. A future migration to
`apps/web/` and `apps/api/` would improve naming symmetry, but it is not required
for correctness and would add unnecessary review risk to this hardening sprint.
Any migration requires approval in a later sprint.

Frontend dependencies are installed reproducibly with npm and the committed
`frontend/package-lock.json`. Node.js 22.x and npm 10.x are the documented local
and CI toolchain.

## Principles

- Keep the initial architecture simple and reviewable.
- Favor explicit contracts and documentable boundaries.
- Avoid speculative service logic and future-slice abstractions.

## Deferred

- Complete full Docker application runtime verification in a Docker-enabled environment.
- Decide whether to migrate `frontend/` to `apps/web/` in a later approved sprint.
- Any later persistence, authentication, policy, journal, Guardian, AI, or broker
  architecture requires separate approval.
- Full Docker runtime and browser-path validation remains pending.
- Decision Journal work remains outside Slice 2 and unauthorized as Slice 3.

## Portfolio Architecture (Sprint 003)

### Status Semantics

- `portfolio.status = 'draft'`: an editable draft row exists.
  The most recent confirmed snapshot remains `current` and readable.
- `portfolio.status = 'active'`: no draft row; at least one confirmed snapshot.
- Portfolio lifecycle trigger (0004) permits `draft↔active` transitions only.

### Snapshot Immutability

- Snapshot rows and snapshot holdings are immutable.
- Exception: `current→superseded` status transition, allowed via migration 0006.
  All other UPDATE and all DELETE are rejected.
- Future-proof JSONB row comparison: `(to_jsonb(NEW) - 'status')`
  `IS NOT DISTINCT FROM (to_jsonb(OLD) - 'status')`.
  Any column added to portfolio_snapshots in future migrations is automatically
  protected without trigger modification.

### Migration Chain

- 0004 (`portfolio_foundation`): six tables, triggers, constraints (Slice A).
  Unmodified since merge.
- 0005 (`portfolio_cash_unit_price`): additive CHECK constraint for cash
  holdings — `asset_category != 'cash' OR unit_price = 1.00`.
- 0006 (`portfolio_snapshot_status`): controlled status transition.
  All migrations are additive after 0004; 0004 and 0005 are unchanged.

## Sprint 003 Slice C Architecture

Slice C adds the approved browser workflow without changing the Slice B API
or Slice A persistence design:

- `frontend/app/portfolio/page.tsx` defines the App Router boundary and
  delegates all interactive behavior to a client component.
- `frontend/app/portfolio/portfolio-client.tsx` keeps the saved server draft
  and latest snapshot separate from local holding edits. The core workspace,
  snapshot history, selected detail, and audit timeline have independent
  loading and error states.
- `frontend/lib/portfolio-api.ts` is the typed browser boundary for the
  approved Portfolio endpoints. Reads may be aborted to prevent stale
  responses from replacing newer state; mutations are never automatically
  retried. Decimal strings are used for all numeric values; `estimateTotal`
  uses BigInt arithmetic and is explicitly labeled non-authoritative.
- Core draft/holdings state is isolated from auxiliary history/audit
  failures. History, audit, and snapshot detail each use separate abort
  controllers with generation guards. 409 conflicts preserve local input
  and offer explicit reload.
- Held metadata saves send only changed fields with expected revision.
  Successful responses become the new saved draft; failed mutations retain
  local edits. The workspace owns holdings-dirty and metadata-dirty flags.
  Confirm is disabled while either editor differs from its latest server
  snapshot, and any reload that would replace dirty editor state requires
  explicit page-level confirmation.
- Snapshot history is read-only and cursor-paginated newest first. Audit
  events preserve server-returned sequence order. Both auxiliary resources
  have GET-only recovery that never replays a mutation.

Slice C adds no backend module, database change, dependency, authentication,
recommendation, Guardian, AI, Broker, trading, market data, or Sprint 004
behavior.

## Sprint 005 Architecture — Data Orchestration Foundation

### Persistence Layer

Five tables across migrations 0008–0011:

- **job_definitions**: job_type + job_params (JSONB).  Created automatically when
  a schedule is created.  job_type constrained to approved allowlist.
- **schedules**: execution_time + timezone + next_run_at + enabled.
  Daily-only scheduling.  Idempotency key = SHA256(job_type || params || date).
- **runs**: status lifecycle pending→running→completed/failed/aborted.
  One active run per schedule enforced by partial unique index.
- **attempts**: track individual execution attempts with status and error_message.
- **leases**: fencing_token, worker_id, acquired_at, heartbeat_at, expires_at, released_at.
  Fencing token protocol v4: atomic takeover (token = OLD + 1), expiry enforcement,
  complete window refresh required.  Heartbeat and finalize require five conditions:
  id + worker_id + fencing_token + released_at IS NULL + expires_at > now.

### Worker Architecture

The Worker is a standalone process that connects directly to PostgreSQL — it does
NOT call the FastAPI HTTP server.  This eliminates the HTTP loopback dependency
and keeps Guardian evaluation + Automation state in a single database transaction.

Claim loop: claim_due_schedules (FOR UPDATE SKIP LOCKED) → per-schedule transaction:
  create_run (idempotency key) → advance_next_run_at → create_attempt →
  acquire_lease → execute with timeout → finalize + release in one commit.

Guardian evaluation uses a transaction-neutral core (`evaluate_core`) that never
commits.  The Worker child process calls it within a single `session.begin()` block:
  1. Guardian evaluation (NO lease lock — heartbeat can update freely)
  2. Final FOR UPDATE on lease (clock_timestamp() for expiry validation)
  3. Finalize attempt + run + release lease → atomic COMMIT

This ensures Guardian effects and Automation state are all-or-nothing.

### Constants (per Technical Design)

- LEASE_TTL_SECONDS = 60
- HEARTBEAT_INTERVAL_SECONDS = 15
- MAX_RUNTIME_SECONDS = 300
- GRACEFUL_SHUTDOWN_SECONDS = 30

### Timeout and Crash Recovery

- Real multiprocessing spawn child processes with queue-based readiness signaling.
- Parent joins with timeout; on expiry: terminate() → wait → kill() → wait.
- Killed child's uncommitted transaction is rolled back by PostgreSQL (TCP disconnect).
- StaleRunReaper recovers runs stuck in 'running' with expired leases on startup.
  Uses atomic FOR UPDATE with bool return to prevent double-counting.

### Automation API (9 endpoints)

All under /api/automation:
- POST/GET /schedules, GET/PATCH/DELETE /schedules/{id}
- GET /runs, GET /runs/{id}, POST /runs (manual trigger)
- GET /worker/status (read-only)

### Automation Frontend (/automation)

- Schedule management: create/edit/enable/disable/delete with explicit confirmation.
- New schedules created disabled by default; enable requires separate explicit action.
- Manual trigger creates a new Run (never modifies existing Run).
- Worker status display only — no start/stop/restart controls.
- Independent AbortControllers for core workspace, schedule detail, runs, and worker.
- 409 conflict preserves local input with explicit reload.

### PostgreSQL Test Isolation

- Single function-scoped `postgres_test_isolation` fixture shared by db_session + api_client.
- Table auto-discovery: `inspect(engine).get_table_names()` for runtime TRUNCATE.
- Connection timezone = UTC default (connect_args).  Tests needing different timezones
  use `SET LOCAL TIME ZONE` which auto-resets at transaction end.
- All date-boundary tests source dates from PostgreSQL `CURRENT_DATE`, never
  Python `date.today()`.
- COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1 enforcement (0 skipped).

## Sprint 006 Architecture — AI Investment Committee Foundation

### Persistence (Migration 0012)

Four additive tables:
- **committee_sessions**: draft→queued→running→completed/failed lifecycle
- **committee_evidence_items**: 6 source types, provenance, confidence, content hash
- **committee_reports**: immutable (UPDATE blocked), 1:1 with session
- **committee_outcomes**: append-only (UPDATE/DELETE blocked), accepted/rejected/deferred

### Evidence Pipeline

Deterministic extraction from CompoundOS entities (Slice A, used by Slice B):
- Policy: objectives, time_horizon, allocations (category-level only)
- Portfolio: category breakdown — no individual holdings, quantities, or prices
- Guardian: event summaries per check (exceeded count, latest detection)
- Decisions: recent confirmed decisions (ID, date)
- SHA256 content hashing for integrity

### Provider Architecture

Provider-neutral `AIModelProvider` interface.  V1 implements DeepSeek adapter only.
Credential flow: macOS Keychain → explicit env fallback (COMPOUNDOS_ALLOW_ENV_CREDENTIALS=1) → fail.
No plaintext config files.  FakeProvider for deterministic testing — no live LLM calls in CI.

### Committee Orchestration

Full pipeline: evidence→privacy preview→Owner confirmation→single structured call→
validation→immutable report persistence.

Provider Output Validator: JSON schema, citation validation, safety/language checks,
budget enforcement.  All-or-nothing — single validation failure = full rejection.

### Safety Boundaries

- Manual-only: Owner initiates every session.  No Schedule/Guardian/Portfolio trigger.
- recommended_direction: 4 approved enum values (aligned, not_aligned, conditional, insufficient_evidence).
- No autonomous trading, no automatic mutations of Policy/Portfolio/Guardian.
- Privacy preview before every provider call.
- No raw prompt/response or API key in logs/database.

### API (9 endpoints under /api/committee)

POST/GET /sessions, GET /sessions/{id}, GET /sessions/{id}/privacy-preview,
POST /sessions/{id}/run, GET /runs/{id}, GET /reports/{id},
GET /evidence/{session_id}, POST /outcomes

### Frontend (/committee)

TypeScript API client, session management, privacy preview with Owner checkbox,
7 perspective report display, outcome recording with append-only history.

## Sprint 007 — Notification Architecture

### Persistence

- `notification_events`: source, event_type, severity, fingerprint (SHA256 v2),
  title, body, delivery_status, suppressed_reason, delivered_at, acknowledged_at,
  occurred_at. CHECK constraints on source, severity, delivery_status.
- `notification_preferences`: quiet_hours_start, quiet_hours_end, timezone,
  enabled (FALSE default), enabled_sources (JSONB), enabled_severities (JSONB).
  UNIQUE INDEX ((1)) singleton enforcement.
- Migration head: 0016_notification_integrity.

### Explicit Opt-in

- Notifications are **disabled by default**. Owner must PATCH preferences with
  `enabled=true` to activate.
- `enabled_sources` and `enabled_severities` control which sources and severities
  can produce deliveries.
- Disabled/not-configured/no-adapter states return HEALTHY (no impact on overall health).

### Delivery Pipeline

- `notify()`: full pipeline — source/severity validation, explicit opt-in check,
  source/severity allowlist, dedup (advisory lock + fingerprint v2 window),
  quiet hours, delivery attempt.
- `dispatch_notification()`: structured entry point. Only approved (source, event_type)
  pairs from NOTIFICATION_TEMPLATES dict. Generates title/body from template +
  context. No free-form text from callers.
- Delivery statuses: `pending`, `delivered`, `unavailable` (no adapter),
  `failed` (adapter exception), `suppressed` (disabled/dedup/quiet_hours/source_disabled).

### AppleScript Adapter (macOS only)

- Static `on run argv` AppleScript with `shell=False` subprocess.run.
- Title and body passed as argv items; never interpolated into source code.
- Timeout 10 seconds. Truncation: title 100 chars, body 200 chars.

### Health Integration

- `check_notification()`: **read-only** — SELECT only, no DB writes, no side effects.
  Returns UNKNOWN for session=None; HEALTHY for disabled/no-adapter/no-events/OK;
  DEGRADED for enabled + adapter_available + delivery failure.
- `run_all_checks()`: dispatches via `dispatch_notification()` when overall is
  DEGRADED or UNAVAILABLE. Fire-and-forget — notification failure cannot break
  health response. No recursive dispatch loop.
- `notification` in DEGRADING set; DEGRADED status degrades overall health.

### API Privacy

- `NotificationEventResponse` exposes `preview` (first 100 chars of body).
  Full body stored in DB for audit only, never in API response.
- Error messages use allowlisted reason codes; no credentials, paths, or traces.

### Source Integration

- **Wired:** health (DEGRADED/UNAVAILABLE → dispatch_notification via run_all_checks).
- **Templates defined, not yet wired:** guardian, committee, automation, backup.

### Dedup and Concurrency

- Household-scoped fingerprint v2: `SHA256(v2:{household_id}:{source}:{event_type}:{severity}:{entity_id})`.
- PostgreSQL advisory transaction lock (`pg_advisory_xact_lock(42)`) for serialization.
- 24-hour dedup window with severity escalation bypass.

### Security

- Sharp 0.35.3 via npm overrides (resolves 4 libvips CVEs).
- No credential, DSN, path, or raw exception in any notification payload or API response.
- No investment rule changes, no Guardian threshold changes, no auto-trading.
