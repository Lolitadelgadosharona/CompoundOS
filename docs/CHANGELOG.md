# Changelog

## [Unreleased] - Sprint 002 Slice 2C Review

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
- Slice 2C implementation is complete and is in Review; this is not a
  production-readiness claim or completion of Sprint 002.
- PR #9 remains Draft after its initial REQUEST CHANGES review. M-1 through M-4
  and L-1 through L-6 have been addressed and await independent incremental review.
- Sprint 002 remains In Progress.

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
