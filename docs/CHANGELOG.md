# Changelog

## Sprint 005 — Data Orchestration Foundation — Done (2026-07-20)

### Technical Design Gate (PR #37, #38)
- 15 Owner Decisions resolved (daily-only, default-off, direct PostgreSQL Worker,
  atomic fenced commit, lease fencing v4, no HTTP loopback, no notifications)
- Sprint 005 Technical Design and Open Questions documents merged

### Slice A — Orchestration Persistence (PR #38, #39, #40, #41)
- Migrations 0008–0011: job_definitions, schedules, runs, attempts, leases
- Fencing token protocol (v1→v4): atomic takeover, expiry enforcement, window refresh
- CHECK constraints, UNIQUE constraints, partial indexes for overlap prevention
- PL/pgSQL trigger functions: lease takeover prevention, terminal immutability
- Idempotency key: SHA256(job_type || params || scheduled_date)

### Slice B — Worker + Backend API (PR #42, #43, #44, #45, #46)
- 9 Automation endpoints under /api/automation
- Standalone Worker with direct PostgreSQL connection (no HTTP loopback)
- Claim + execute per-schedule transaction isolation
- Lease TTL 60s / heartbeat 15s / max runtime 300s / graceful shutdown 30s
- Process timeout enforcement with real multiprocessing spawn→kill→rollback
- Stale-run recovery (reaper) with atomic FOR UPDATE claim
- Guardian transaction-neutral core: evaluate_core never commits
- Final lease FOR UPDATE at commit window only (not during evaluation)
- clock_timestamp() for definitive expiry validation
- Heartbeat not blocked during Guardian evaluation
- Both takeover race orderings verified (takeover-first, lock-first)
- Graceful shutdown: real multiprocessing terminate→kill→orphan check
- Released lease is terminal (takeover SQL guards released_at IS NULL)

### Slice B — PostgreSQL Isolation Stabilization (PR #47)
- Single function-scoped postgres_test_isolation fixture
- Table auto-discovery (inspect→get_table_names) replacing hardcoded lists
- connect_args timezone=UTC default
- All date-boundary tests use SET LOCAL + CURRENT_DATE from PostgreSQL
- 10/10 pre-existing cross-test failures eliminated
- Two direct-main review fixes recorded (393a20d)

### Slice C — Automation Frontend (PR #48)
- /automation workspace: schedule CRUD, manual trigger, run history, worker status
- 9-endpoint typed Automation API client with AbortSignal support
- Default disabled on create; explicit enable required; no auto-trigger on load
- Independent abort controllers: core/schedule/runs/worker
- 409 conflict preserves local input; neutral language throughout
- 217 frontend tests (19 API client + 15 component); full accessibility

### Final Test Baseline
- 431 PostgreSQL tests (COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1, 0 skipped)
- 136 non-PostgreSQL tests
- 217 frontend tests (Vitest + shuffled)
- ESLint --max-warnings=0, TypeScript --noEmit, Ruff clean

### Explicit Product Boundary (Sprint 005 Closeout)
- Personal-use-only product direction
- Schedule explicit opt-in / default off
- No notifications in Sprint 005
- No automatic Guardian schedule creation
- Worker direct PostgreSQL (not HTTP to FastAPI)
- Atomic fenced effect commit (Guardian + Automation in one transaction)
- PostgreSQL _test database isolation enforced
- Direct-main commit exception (393a20d) recorded; normal PR workflow resumed

## Sprint 003 — Portfolio Snapshot + Holdings Foundation — Done (2026-07-17)

### Slice A: Portfolio Persistence (PR #20, e9743a5)
- Alembic revision 0004: portfolios, portfolio_drafts, portfolio_draft_holdings,
  portfolio_snapshots, portfolio_snapshot_holdings
- Named CHECK and UNIQUE constraints on all five tables
- PL/pgSQL triggers: fn_portfolio_snapshot_immutability,
  fn_portfolio_draft_consistency, fn_portfolio_lifecycle
- SQLAlchemy ORM models aligned with migration
- 130 real PostgreSQL tests (0 skipped)

### Slice B: Portfolio Backend API (PR #21)
- Pydantic request/response schemas with decimal-string contracts
- Repository queries with FOR UPDATE support
- Service transaction boundaries with lock ordering (Household→Portfolio→Draft)
- 9 endpoints under /api/portfolio: POST /draft, GET, PATCH /draft,
  PUT /draft/holdings, POST /draft/confirm, POST /draft/discard,
  GET /snapshots, GET /snapshots/{id}, GET /audit
- Concurrency tests, rollback tests, revision conflict tests
- Portfolio-filtered AuditEvent reads
- Cash unit_price = 1.00 enforcement via migration 0005 (additive CHECK)
- Controlled status transition current→superseded via migration 0006 (additive)
- Future-proof JSONB row comparison in immutability trigger

### Slice C: Portfolio Frontend (PR #22, 0a841d4)
- /portfolio page with typed Portfolio API client
- All 18 UI states from Technical Design §11 covered
- BigInt-based client-side total_value estimation (non-authoritative)
- Decimal strings throughout API boundary; no Number/parseFloat
- Cash unit_price 1.00 with neutral technical hint
- Zero holdings warning with explicit confirmation
- 409 conflict preserves local input with explicit reload
- Separate abort controllers for core, history, audit, and snapshot detail
- Pre-confirm view state restoration for cancel from review
- 80 new frontend tests (55 API client + 25 component)
- Independent blind review: APPROVE WITH NON-BLOCKING FOLLOWUP
  (0 BLOCKER, 0 HIGH, 0 MEDIUM after fix; 2 LOW all resolved)
- CI: 6/6 checks green on final HEAD before merge

## [Unreleased] - Sprint 003 Slice B (In Review)

### Added

- Portfolio API: 9 endpoints under /api/portfolio
- Cash unit_price = 1.00 database CHECK constraint (migration 0005, additive)
- Controlled snapshot status transition current→superseded (migration 0006, additive)
- Future-proof JSONB row comparison in immutability trigger
- Comprehensive API, gate, trigger, migration, and concurrency tests

### Changed

- Portfolio status semantics: 'draft' = draft exists; 'active' = confirmed, no draft
- Snapshot current→superseded transition allowed per Owner Decision Option A

### Fixed

- 0004 snapshot immutability trigger: allowed controlled status-only UPDATE via 0006
- Deferred trigger active+draft semantics clarified per Owner Decision

## [Unreleased] - Sprint 002 Slice 3B Complete

### Added

- Twelve Decision Journal API endpoints on `apps/api/routers/decisions.py`:
  POST /api/decisions (create Draft), GET /api/decisions (list),
  GET /api/decisions/{id}/draft, PATCH /api/decisions/{id}/draft,
  POST /api/decisions/{id}/draft/discard, POST /api/decisions/{id}/draft/confirm,
  GET /api/decisions/{id} (detail with original/effective snapshots),
  POST /api/decisions/{id}/archive, POST /api/decisions/{id}/unarchive,
  POST /api/decisions/{id}/corrections, GET /api/decisions/{id}/corrections,
  GET /api/decisions/{id}/audit-events
- Strict Pydantic request/response contracts in `apps/api/decision_schemas.py`
  with extra=forbid, trim, Unicode code-point length limits, and mechanical
  ISO date validation (future decision_date rejected, review_date allows future)
- Decision repository in `apps/api/repositories/decisions.py` with FOR UPDATE
  support, cursor pagination, and per-Decision Correction numbering
- Decision service in `apps/api/services/decisions.py` with atomic transactions:
  Policy→Decision→Draft lock ordering, 13-step Confirm, atomic never-Confirmed
  Draft discard with identity deletion (OD-S3-13 Option A), full replacement
  Correction snapshots with MAX+1 numbering under Decision row lock
- Router registered in `apps/api/main.py` with existing localhost CORS pattern
- Decision Pydantic schema tests in `tests/api/test_decisions.py` (27 tests)
- Decision PostgreSQL backend tests in `tests/test_decision_backend.py`
  (32 tests covering creation, draft CRUD, confirm, discard, archive/unarchive,
  corrections, audit events, detail views, and Household timeline inclusion)
- ADR 0006 documenting the Decision Journal backend transaction patterns

### Boundaries

- Slice 3B adds no frontend, `/decisions` page, migration, dependency, Compose,
  CI, authentication, recommendation, Guardian, AI, Broker, trading, actual
  holdings, accounts, monetary data, or Slice 3C behavior.
- Slice 3C (Decision Frontend Workflow): Not Authorized, Not Started.

### Status

- Sprint 002 remains In Progress. Slice 2A, 2B, 2C, 3A, 3B remain Done.
- Slice 3B Decision Journal Backend Workflow and API: Done.
- CI: 6/6 checks pass (push + pull_request × infrastructure/backend/frontend),
  302 tests total (102 non-PostgreSQL + 138 PostgreSQL + 62 frontend).
- Slice 3C: Not Authorized, Not Started.

## [Unreleased] - Sprint 002 Slice 3A Complete

### Added

- Alembic revision `0003_decision_journal_foundation` creating four Decision
  Journal tables: `decisions` (stable identity), `decision_drafts`,
  `decision_confirmed_snapshots`, and `decision_corrections`
- Five PL/pgSQL trigger functions: identity lifecycle transitions, identity
  delete guard (draft-only DELETE), confirmed snapshot immutability,
  correction immutability with status/ownership validation, and deferred
  commit-time lifecycle consistency enforcement
- Named CHECK constraints for status values, text lengths, date boundaries,
  correction numbering, actor, and archive reason on all four tables
- UNIQUE constraints: at most one Draft per Decision, at most one Confirmed
  snapshot per Decision, per-Decision sequential correction numbering
- FK constraints with ON DELETE RESTRICT/NO ACTION for snapshot and correction
  references; ON DELETE CASCADE for Draft-to-Decision enabling atomic discard
- Deferred CONSTRAINT TRIGGER on decisions for cross-table draft/snapshot
  consistency verification at commit time
- SQLAlchemy ORM models aligned with the migration: Decision, DecisionDraft,
  DecisionConfirmedSnapshot, DecisionCorrection
- Comprehensive real-PostgreSQL test suite (60 tests) covering migration
  lifecycle, schema inspection, data model constraints, lifecycle transitions,
  discard foundation, snapshot immutability, correction behavior, and trigger
  inspection
- ADR 0005 documenting the Decision Journal persistence and immutability
  foundation

### Boundaries

- Slice 3A adds no Decision service, repository workflow, API endpoint,
  Pydantic contract, router, or frontend `/decisions` page.
- No AuditEvent business write workflow, Redis logic, authentication,
  multi-user, multi-household, recommendation, Guardian, AI, Broker, trading,
  actual holdings, accounts, or monetary data is included.
- Slice 3B (Decision Backend Workflow and API): Not Authorized, Not Started.
- Slice 3C (Decision Frontend Workflow): Not Authorized, Not Started.

### Status

- Sprint 002 remains In Progress. Slice 2A, 2B, 2C remain Done.
- Slice 3 Technical Design Gate: Done.
- Slice 3A Decision Journal Persistence and Immutability Foundation: Done.
- Independent review: initial REQUEST CHANGES (1 BLOCKER), final APPROVE WITH
  NON-BLOCKING FOLLOW-UP. BLOCKER B1 (deferred trigger coverage gap) resolved
  with three cross-table deferred CONSTRAINT TRIGGERs and four bypass regression
  tests. 138 required PostgreSQL tests passed, 0 skipped.
- PR #11 approved for merge.
- Slice 3B and Slice 3C: Not Authorized, Not Started.

### Review Summary

- Initial independent review: REQUEST CHANGES with one BLOCKER finding.
- B1 resolved: deferred trigger coverage gap — original trigger fires only on
  decisions INSERT, missing UPDATE and child-table mutations that can bypass
  lifecycle consistency checks. Fixed by adding deferred CONSTRAINT TRIGGERs on
  decision_drafts (AFTER INSERT OR DELETE) and decision_confirmed_snapshots
  (AFTER INSERT OR DELETE), expanding decisions trigger to INSERT OR UPDATE, and
  updating the shared function to extract decision_id from TG_TABLE_NAME and
  query current database state at COMMIT time instead of relying on stale NEW
  records.
- Four bypass regression tests added: cross-transaction UPDATE to confirmed
  without snapshot, Draft deletion leaving orphan identity, snapshot insertion
  with retained Draft, and confirmed-to-draft status regression.
- Final independent review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP.
- All BLOCKER, HIGH, and MEDIUM findings resolved. Zero outstanding issues.
- Real PostgreSQL test suite: 138 passed, 43 deselected, 0 skipped, 20 warnings.
- Frontend test suite: 4 files, 62 tests passed (no regressions).

## [Unreleased] - Sprint 002 Slice 3 Technical Design Gate Complete

### Added

- Decision Journal Technical Design document covering Approach C (Stable
  Decision Identity + Draft + Immutable Confirmed Snapshot + Append-Only
  Correction) for the Decision Journal data model
- Fifteen Owner Decisions (OD-S3-1 through OD-S3-15) all Resolved by Project
  Owner — 2026-07-16, covering: multiple independent Drafts, Confirm required
  fields (mechanical validation only), no classification/tags, DATE type with
  future decision_date forbidden, current Published Policy Version reference
  only, 13-step Confirm transaction consuming Draft, Archive/unarchive
  lifecycle, full replacement Correction snapshots, correctable field set,
  Decision-filtered audit with Household timeline inclusion, provisional
  non-advisory UI copy, 3A/3B/3C implementation split, atomic never-Confirmed
  Draft discard with identity deletion, per-Decision sequential Correction
  numbering via MAX+1, and Archived Decision Correction eligibility
- Key design boundaries: Policy → Decision → Draft lock order, immutable
  Confirmed snapshot, atomic never-confirmed Draft discard, full replacement
  Corrections, per-Decision Correction numbering, Archive/unarchive,
  Archived Correction eligibility, Decision-filtered audit, Household
  timeline inclusion
- Seven AuditEvent action names following the existing Policy audit pattern:
  `decision.draft.created`, `decision.draft.updated`,
  `decision.draft.discarded`, `decision.confirmed`, `decision.archived`,
  `decision.unarchived`, `decision.correction.appended`
- Cursor-based Decision audit pagination: `before_sequence_number`, default 50,
  max 100, DB DESC / API ASC

### Boundaries

- No schema, migration, backend, API, frontend, or tests implementation is
  included. This is a design-only document.
- Merging the Technical Design does not authorize Slice 3 implementation.
- Slice 3A (Decision Persistence and Immutability): Not Started.
- Slice 3B (Decision Backend Workflow and API): Not Started.
- Slice 3C (Decision Frontend Workflow): Not Started.
- The Decision Journal records only what the user types, confirms, archives,
  and corrects. No recommendation, evaluation, scoring, suitability, AI,
  Guardian, Broker, market data, actual holdings, or trading behavior.

### Status

- Sprint 002 remains In Progress. Slice 2A, 2B, 2C remain Done.
- Slice 3 Technical Design Gate: Done.
- Independent review passed through four stages: initial REQUEST CHANGES
  (5 MEDIUM, 3 LOW), incremental APPROVE WITH NON-BLOCKING FOLLOW-UP,
  consistency review APPROVE WITH ONE MEDIUM FINDING, final focused APPROVE.
- All review findings resolved. Zero outstanding issues.
- PR #10 approved for merge.

## [Unreleased] - Sprint 002 Slice 2C Complete

### Added

- Local-only `/policy` workflow covering initial loading, missing Household,
  empty Policy, Draft editing, publication review, immutable Published Version,
  version history, Policy audit, and confirmed Draft discard states
- Typed browser API client for the approved Policy backend contracts with distinct
  404, 409, and 422 handling, abortable reads, and no mutation retries
- Explicit Draft text and whole-allocation saves with optimistic revisions,
  client-side semantic no-op detection, and local edit preservation on failures
- Exact target-allocation display totals calculated from decimal strings as integer
  hundredths without binary floating-point arithmetic or silent rounding
- Accessible mechanical publication checks and explicit confirmation using the
  approved non-advisory and local-only boundary
- Frontend component and API-client coverage for state transitions, conflicts,
  decimal handling, immutable history, audit recovery, safety copy, and request cleanup
- Independent core, Version-history, and Policy-audit resource states so auxiliary
  read failures cannot hide a successfully loaded Draft or Published Version
- Workspace-level semantic dirty tracking that blocks publication of a stale saved
  snapshot and requires explicit confirmation before reload discards local edits
- Generation- and AbortController-guarded audit/history reads, including guarded
  cursor merges, stable Version identity deduplication, and stale-result rejection
- Case-preserving allocation display-name comparison, Unicode code-point length
  validation, and row-specific accessible allocation action names
- Safe distinction between connection failures and unexpected HTTP server errors,
  without displaying response bodies or request payloads
- A compact immutable current Published Version summary when a Draft is also open

### Boundaries

- Slice 2C records and displays only user-entered Policy information; it does not
  evaluate suitability or provide advice, recommendations, trade instructions,
  scores, eligibility, rebalancing, or automated decisions.
- No backend behavior, migration, Python or frontend dependency, Compose, CI,
  authentication, Decision Journal, Guardian, AI, Broker, market, holding, or
  trading behavior is added.
- Full Docker runtime and end-to-end browser-path validation remain pending.
- Slice 3 remains unauthorized and Not Started.

### Status

- Slice 2A and Slice 2B remain Done.
- Slice 2C passed independent incremental review with conclusion APPROVE. All
  ten findings from the initial review (M-1 through M-4, L-1 through L-6) are
  fully resolved with zero new findings.
- PR #9 approved for merge.
- Sprint 002 remains In Progress. Slice 3 remains unauthorized and Not Started.

### Review Summary

- Initial independent review: REQUEST CHANGES (M-1 through M-4, L-1 through L-6).
- M-1 resolved: independent core/history/audit resource states prevent auxiliary
  failures from hiding a usable workspace.
- M-2 resolved: workspace-level semantic dirty tracking blocks publication of
  stale saved snapshots and requires explicit confirmation before reload.
- M-3 resolved: unified reload confirmation protects both editors from silent
  data loss; failed reloads preserve local edits.
- M-4 resolved: generation-guarded and AbortController-coordinated audit reads
  prevent stale responses from overwriting newer state.
- L-1 resolved: generation- and cursor-guarded history pagination with stable
  Version identity deduplication.
- L-2 resolved: case-preserving allocation display-name comparison matching
  backend NFKC + trim + whitespace collapse semantics.
- L-3 resolved: Unicode code-point length validation replacing HTML maxLength,
  with 200 emoji boundary tests.
- L-4 resolved: distinct PolicyNetworkError and PolicyApiError classes with
  neutral messages that never echo response bodies.
- L-5 resolved: CurrentPublishedSummary component renders immutable Published
  context alongside an editable Draft.
- L-6 resolved: row-specific accessible aria-labels for all allocation row
  controls with name-aware fallbacks.
- Frontend test suite: 4 files, 62 tests (up from 37), including deferred-promise
  race condition tests, dirty-state transition tests, Unicode boundary tests,
  error classification tests, and accessibility tests.

## [Unreleased] - Sprint 002 Slice 2B Complete

### Added

- Strict Pydantic contracts for ten Policy text fields and decimal-string target
  allocation values
- Policy, Draft, allocation, publication, immutable Version, history, and audit APIs
- Unicode NFKC/casefold allocation-name normalization and atomic whole-collection saves
- Synchronous service transactions with Policy-then-Draft locking, optimistic
  Draft revisions, named-conflict mapping, and atomic non-sensitive AuditEvents
- Real PostgreSQL API, rollback, immutable publication, concurrency, and race tests
- ADR 0004 documenting the Policy backend transaction and API boundary
- Transaction-scoped PATCH response snapshots that perform no Draft/allocation
  read after commit
- Optional empty-object validation for Policy creation requests: omitted bodies and
  `{}` are accepted, while non-empty objects, scalars, and arrays are rejected
- Expanded required PostgreSQL coverage for lifecycle races, replacement and
  allocation rollback, unrelated integrity failures, audit windows, text
  boundaries, and exact publication totals

### Boundaries

- Slice 2B provides a backend API only; no `/policy` frontend or frontend API
  client is included.
- Explicit JSON `null` is still accepted by `POST /api/policies` as the optional
  empty request; distinguishing it from an omitted body remains a LOW,
  non-blocking follow-up.
- The API records user-entered text and target percentages without evaluation,
  recommendation, scoring, eligibility, Guardian, AI, Broker, or trading behavior.
- Slice 2C and Slice 3 remain unauthorized and Not Started.

### Status

- Sprint 002 remains In Progress.
- Slice 2A remains Done.
- Slice 2B is complete and is not a production-readiness claim.
- Independent review initially concluded REQUEST CHANGES for M-1, M-2, and L-1.
  M-1 was resolved with an atomic transaction-scoped PATCH response snapshot,
  and M-2 was resolved with the required transaction, concurrency, rollback,
  audit-window, text-boundary, and exact-total coverage.
- Final independent incremental review conclusion: APPROVE WITH NON-BLOCKING
  FOLLOW-UP. Pull request #8 is approved for merge.
- L-1 remains partially resolved only for explicit JSON `null`, as disclosed
  above; it does not block Slice 2B completion.
- The Policy frontend and complete Policy user experience remain unimplemented.
- Full Docker/browser runtime validation and the Alembic `path_separator = os`
  warning remain non-blocking Backlog items.

## [Unreleased] - Sprint 002 Slice 2A Complete

### Added

- Alembic revision `0002_investment_policy_foundation`
- Five approved Investment Policy, Draft, allocation, and Version persistence tables
- Database-generated unique AuditEvent insertion sequence with preserved Slice 1 data
- Named Policy cardinality, version, allocation, normalization, and range constraints
- PostgreSQL immutable Version and Version-allocation trigger functions
- Deferred commit-time sealing enforcement
- SQLAlchemy mappings aligned with the migration
- Real PostgreSQL tests for fresh and incremental migration, downgrade/re-upgrade,
  constraints, triggers, rollback, and insertion sequencing
- ADR 0003 documenting immutable Policy snapshot persistence

### Boundaries

- Slice 2A adds no Policy repository workflow, service, API endpoint, Pydantic
  Policy contract, or frontend `/policy` experience.
- No recommendation, Guardian, AI, Broker, trading, authentication, Slice 2B,
  Slice 2C, or Slice 3 behavior is included.
- AuditEvent sequence values provide deterministic database insertion order, not
  concurrent transaction commit order, and may contain rollback gaps.

### Status

- Sprint 002 remains In Progress.
- Slice 2A passed independent review with conclusion APPROVE WITH NON-BLOCKING
  FOLLOW-UP and pull request #7 is approved for merge.
- Slice 2A completes only the Investment Policy persistence and immutability
  foundation; it is not a production-readiness claim.
- Slice 2B, Slice 2C, and Slice 3 remain unauthorized.
- Docker runtime/browser validation and full AuditEvent pagination remain Backlog items.

### Non-blocking follow-ups

- Strengthen schema/trigger regression assertions for all allocation unique
  constraints and index predicates, combined seal-plus-content mutation, repeated
  Superseded mutation, and multi-row forbidden statements.
- In a separate maintenance change, add Alembic `path_separator = os` and rerun
  offline and real PostgreSQL migration validation.

## [Unreleased] - Sprint 002 Slice 1 Complete

### Added

- PostgreSQL-backed sole HouseholdProfile create, current-read, and update APIs
- Atomic append-only AuditEvent creation and read-only timeline API
- Explicit Alembic migration for `household_profiles` and `audit_events`
- Local-only Household page with create, summary, edit, validation, error, and audit states
- Real PostgreSQL CI service, migration, singleton, and transaction rollback checks
- A project-specific CI gate that fails if required real PostgreSQL tests cannot run
- Named PostgreSQL checks mirroring every approved HouseholdProfile field limit
- Independent audit loading/error state and GET-only retry after a successful mutation
- ADR 0002 for synchronous PostgreSQL persistence and transaction boundaries

### Boundaries

- All host ports default to `127.0.0.1`; no authentication or public deployment
- No Policy, Allocation, Journal, AI, Guardian, Broker, recommendation, trading,
  actual holdings, accounts, or monetary data
- Sprint 002 is not complete, and Slice 2 is not authorized

### Validation Status

- Local Ruff, backend tests available without PostgreSQL, frontend lint,
  type-check, tests, production build, dependency audit, Alembic offline SQL,
  YAML parsing, localhost binding inspection, and secret scan pass
- Real PostgreSQL and Compose checks run in GitHub CI
- Local test runs may skip PostgreSQL-marked tests when `TEST_DATABASE_URL` is not
  configured; the explicit CI-required mode fails instead of skipping
- Independent review initially concluded REQUEST CHANGES; the PostgreSQL CI gate,
  database constraints, and audit refresh UX findings were resolved
- Final independent review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP
- Docker CLI is unavailable in the local implementation environment, so full
  Docker runtime and browser-path verification remains pending

### Non-blocking Follow-ups

- Complete full Docker runtime and browser-path validation
- Align `NEXT_PUBLIC_API_URL` with Docker's build-time public environment behavior
- Split Python runtime and development dependencies before production hardening
- Design AuditEvent pagination before higher-volume event sources are introduced

### Status

- Sprint 002 Slice 1 is complete and approved for merge.
- This completes one implementation slice, not Sprint 002 as a whole.
- Sprint 002 remains In Progress; Slice 2 is not authorized and Not Started.
- This local-only foundation is not a production-readiness claim or product release.

## [Unreleased] - Sprint 001 Complete

### Added

- Frontend health endpoint test using the Node.js test runner
- CI execution of the frontend health test
- CI validation of the Docker Compose configuration
- Dockerfiles for the existing `frontend/` and `apps/api/` applications
- `compose.yaml` for the web, API, PostgreSQL, and Redis local stack
- Docker build-context ignore files

### Validation

- Frontend lint, type-check, health test, production build, and production
  dependency audit pass locally
- Backend Ruff and pytest checks pass locally
- Compose YAML, CI YAML, build contexts, dependency paths, and container commands
  pass static consistency checks
- Docker runtime verification was not completed because Docker is unavailable in
  the current environment

### Status

- Sprint 001: Done and approved for merge after independent code review
- Review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP
- Docker runtime verification remains an explicitly disclosed non-blocking
  follow-up
- Sprint 002: Not Started
- This entry records foundation completion and is not a product feature release

## [0.1.1] - 2026-07-12

### Changed

- Isolated CompoundOS in a dedicated Git repository directory without changing
  unrelated parent-directory files
- Standardized the frontend on Node.js 22, npm 10, TypeScript, and pinned
  Next.js 16.2.10
- Documented the current `frontend/` plus `apps/api/` monorepo layout
- Added ADR 0001 for the frontend framework and package-manager decision

### Delivery

- Corrected the Sprint 001 commit to use the approved repository-local Git identity
- Verified the intended GitHub repository is empty before initial push
- Finalized Sprint 001 and Sprint 001.1 through pull request #1
- Squash-merged the reviewed foundation into `main` as
  `b3801c64fa09856d491317b0ebda45007c210ae0`
- Confirmed GitHub Actions backend and frontend checks pass for push and pull
  request events

### Status

- Sprint 001: Done
- Sprint 001.1: Done
- Sprint 002: Not Started

## [0.1.0] - 2026-07-11

### Added

- Initial monorepo structure for frontend and backend
- Documentation foundation for vision, roadmap, architecture, and governance
- Minimal FastAPI health endpoints
- Automated health tests and linting configuration
- CI workflow for backend and frontend validation
- Minimal Next.js application shell and web health endpoint

### Deferred

- Docker Compose configuration, pending validation in a Docker-enabled environment
