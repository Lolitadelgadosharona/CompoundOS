# Master Plan

## Long-term Goal

Build CompoundOS as a trustworthy, explainable operating system for family office and wealth management workflows, beginning with a documented and testable foundation.

## Milestones

- Milestone 1: Foundation and governance scaffold
- Milestone 2: Core platform services and health monitoring
- Milestone 3: Decision support workflows and review interfaces

## Current Sprint

- Sprint 001: Project Foundation
- Status: Done
- Scope: final foundation verification, frontend health test, and Docker-based
  local development configuration
- Sprint 002: In Progress
- Completed work: Implementation Slice 1 — Household and Persistence Foundation
- Completed work: Implementation Slice 2A — Investment Policy Persistence and
  Immutability Foundation
- Slice 2 Technical Design: Approved
- Current implementation authorization: Slice 2C — Investment Policy Frontend Workflow
- Slice 2A: Done
- Slice 2B: Investment Policy Backend Workflow and API / Done
- Slice 2C: Implementation complete / Review
- Slice 3: Not authorized / Not Started

## Planning

- Sprint 002 selected direction: Household Investment Policy + Decision Journal.
- Planning pull request #4 completed independent planning review and is approved
  for merge.
- Sprint 002 Slice 1 planning and implementation are complete; later
  implementation slices remain unauthorized.
- Sprint 002 Slice 2 technical design is authorized for planning and review only.
- Slice 2A implementation was separately authorized on 2026-07-14.
- Slice 2B implementation was separately authorized on 2026-07-14.
- Slice 2C implementation was separately authorized on 2026-07-14.
- Slice 3 remains unauthorized.

## Backlog

- Complete Docker runtime verification in a Docker-enabled environment
- Align `NEXT_PUBLIC_API_URL` with the Docker build-time public environment model
- Split Python runtime and development dependencies before production hardening
- Design AuditEvent pagination before introducing higher-volume event sources
- Strengthen Policy persistence schema and trigger regression coverage for all
  allocation unique constraints and index predicates, combined seal-plus-content
  mutation, repeated Superseded mutation, and multi-row forbidden statements
- In a separate maintenance change, add Alembic `path_separator = os` and rerun
  offline and real PostgreSQL migration validation
- Decide and enforce whether `POST /api/policies` must distinguish an omitted body
  from explicit JSON `null`; currently `null` is accepted as the optional empty request
- Complete browser-path validation with the full Docker runtime stack
- Decide whether to migrate `frontend/` to `apps/web/`
- Add backend domain modules
- Introduce data persistence and orchestration
- Add Guardian monitoring workflows
- Add AI Investment Committee workflows
- Add notification escalation capabilities

## In Progress

- Sprint 002 remains In Progress.
- Slice 2A is Done after independent review and approval for merge.
- Slice 2B is Done after independent review and approval for merge.
- Slice 2C implementation is complete and is in Review.
- Slice 3 remains unauthorized and Not Started.

## Review

- Planning PR #4 initial review requested documentation changes.
- Required planning changes were addressed.
- Final planning review conclusion: APPROVE.
- Planning PR #4 approved for merge.
- Sprint 002 Slice 1 initial review conclusion: REQUEST CHANGES.
- Review finding M-1 was resolved with an explicit real PostgreSQL CI gate that
  cannot silently skip in required mode.
- Review finding M-2 was resolved with matching named PostgreSQL and Pydantic
  safety constraints.
- Review finding M-3 was resolved by separating mutation success from audit
  refresh failure and providing a GET-only retry.
- Sprint 002 Slice 1 final independent review conclusion: APPROVE WITH
  NON-BLOCKING FOLLOW-UP.
- Pull request #5 approved for merge.
- Sprint 002 Slice 2 technical design reviewed.
- Owner decisions OD-1 through OD-6 resolved on 2026-07-14.
- The AuditEvent deterministic database insertion-ordering requirement was
  resolved in the design with a database-generated sequence number; it is not a
  claim about concurrent transaction commit order.
- Sprint 002 Slice 2 Technical Design final independent review conclusion:
  APPROVE.
- Pull request #6 approved for merge.
- Merging the design pull request does not authorize Slice 2 implementation.
- Sprint 002 Slice 2A persistence and immutability foundation completed
  independent Review.
- Slice 2A contains migration, ORM mapping, database constraints, immutable
  snapshot triggers, AuditEvent insertion sequencing, and real PostgreSQL tests.
- Slice 2A adds no Policy service, repository workflow, API, or frontend.
- Sprint 002 Slice 2A final independent review conclusion: APPROVE WITH
  NON-BLOCKING FOLLOW-UP.
- The review found zero BLOCKER, HIGH, MEDIUM, or LOW findings and recorded two
  non-blocking maintenance follow-ups in the Backlog.
- Pull request #7 approved for merge.
- Sprint 002 remains In Progress; Slice 2B, Slice 2C, and Slice 3 are not
  authorized and Not Started.
- Sprint 002 Slice 2B backend workflow and API is in Review.
- Slice 2B contains strict Policy contracts, repository queries, atomic service
  transactions, locking, immutable publication orchestration, version reads, and
  Policy-filtered AuditEvent reads.
- Slice 2B adds no frontend, recommendation, Guardian, AI, Broker, trading,
  authentication, Slice 2C, or Slice 3 behavior.
- Sprint 002 Slice 2B independent review conclusion: REQUEST CHANGES, with two
  MEDIUM findings (post-commit PATCH response snapshot race and blocking test
  coverage) and one LOW finding (non-empty Policy-create bodies were ignored).
- M-1 is addressed by constructing the complete Draft response snapshot while
  the Policy-then-Draft transaction is still locked, then returning only the
  scalar DTO after a successful commit with no post-commit query.
- M-2 is addressed with deterministic independent-session concurrency tests,
  transaction-stage rollback tests, audit-window and ownership filtering tests,
  complete Policy text boundaries, exact publish totals, and error/session reuse
  coverage against real PostgreSQL.
- L-1 is partially resolved: an omitted body and `{}` follow the contract, while
  non-empty objects, scalars, and arrays return 422 without creating Policy state.
  Explicit JSON `null` is still treated as an omitted body and returns 201; this
  remaining LOW issue is a non-blocking Backlog follow-up.
- Sprint 002 Slice 2B final incremental review conclusion: APPROVE WITH
  NON-BLOCKING FOLLOW-UP.
- Pull request #8 approved for merge.
- Slice 2B completes the Policy backend workflow and API only; it does not include
  the Policy frontend or a complete Policy user experience.
- Sprint 002 Slice 2C Investment Policy frontend implementation is in Review.
- Slice 2C provides the local-only `/policy` workflow for the sole Household and
  Policy: explicit Draft text and allocation saves, mechanical publication review,
  immutable Published and history reads, Policy audit reads, Draft creation, and
  confirmed Draft discard.
- The frontend preserves decimal percentage strings and computes displayed totals
  by parsing them into integer hundredths; it provides no recommendation,
  suitability, score, rebalancing, or automated decision behavior.
- Policy mutation success and audit refresh failure remain separate outcomes;
  audit retry performs only the audit GET and never replays a mutation.
- PR #9 independent review conclusion was REQUEST CHANGES. M-1 through M-4 are
  addressed by independent core/history/audit resource states, workspace-level
  text and allocation dirty tracking with a publication gate, explicit protected
  reload confirmation, and generation-guarded AuditEvent refreshes.
- L-1 through L-6 are addressed by generation- and cursor-guarded history reads,
  case-preserving allocation display normalization, Unicode code-point limits,
  distinct safe network/server errors, an explicit current Published summary
  beside a Draft, and row-specific accessible allocation controls.
- Slice 2C remains in Review and PR #9 remains Draft pending independent
  incremental review. These fixes do not constitute approval or completion.
- Slice 2C adds no backend behavior, migration, dependency, authentication,
  Decision Journal, Guardian, AI, Broker, market, holding, recommendation, or
  trading behavior.
- Slice 3 remains unauthorized and Not Started.

## Done

- Sprint 001: Project Foundation
- Sprint 001.1: Repository Hardening
- Repository structure created
- Basic health endpoints implemented
- Initial documentation scaffold added
- Backend and frontend validation commands added
- Production frontend dependency audit completed with no known vulnerabilities
- CompoundOS repository isolated from unrelated parent-directory files
- npm, Node.js, TypeScript, and Next.js version decisions documented
- ADR 0001 accepted for the frontend framework and package manager
- Sprint 001 Git identity corrected using the approved repository-local identity
- Intended empty GitHub repository verified
- Pull request #1 squash-merged into `main` as
  `b3801c64fa09856d491317b0ebda45007c210ae0`
- GitHub Actions backend and frontend checks passed for push and pull request events
- Frontend health endpoint automated test added and included in CI
- Docker Compose and Dockerfiles added with static YAML, context, path, and command
  consistency validation
- Pull request #3 squash-merged into `main` as
  `e117a4d936872342dee2baa7012c76816a708d81`
- Sprint 002 Slice 1: Household and Persistence Foundation
- HouseholdProfile vertical create, read, update, and audit workflow
- PostgreSQL persistence managed through explicit Alembic migration
- Database-enforced singleton HouseholdProfile constraint
- Atomic HouseholdProfile and AuditEvent writes
- Local-only Household UI with independent audit refresh recovery
- Real PostgreSQL CI gate with required-mode skip prevention
- Sprint 002 Slice 2A: Investment Policy Persistence and Immutability Foundation
- Immutable Policy, Draft, allocation, and Version persistence schema
- Database-enforced immutable Version sealing and supersession transitions
- Database-generated AuditEvent insertion sequencing
- Real PostgreSQL migration, constraint, trigger, rollback, and sequencing tests
- Slice 2A completed without a Policy service, repository workflow, API, or frontend
- Sprint 002 Slice 2B: Investment Policy Backend Workflow and API
- Strict Policy request/response contracts and repository-backed reads
- Atomic Draft lifecycle, publication, rollback, concurrency, and AuditEvent workflows
- Immutable Policy Version history and Policy-filtered audit API
- Transaction-scoped PATCH response snapshots without post-commit database reads
- Slice 2B completed without a Policy frontend or complete Policy user experience

## Decision Log

- 2026-07-11: Use a minimal monorepo with FastAPI and Next.js placeholders for Sprint 001.
- 2026-07-11: Avoid implementing investment logic, trading, brokers, or autonomous agents in this sprint.
- 2026-07-11: Defer Docker Compose until it can be validated in a Docker-enabled environment.
- 2026-07-12: Isolate CompoundOS in a dedicated repository directory while preserving Sprint 001 history.
- 2026-07-12: Standardize on Node.js 22, npm 10, TypeScript, and Next.js 16.2.10.
- 2026-07-12: Retain `frontend/` alongside `apps/api/` for Sprint 001.1; evaluate `apps/web/` later.
- 2026-07-12: Complete Sprint 001.1 after local validation and GitHub Actions passed.
- 2026-07-12: Finalize Sprint 001 and Sprint 001.1 through pull request #1 using a
  squash merge (`b3801c64fa09856d491317b0ebda45007c210ae0`).
- 2026-07-12: Keep Sprint 002 Not Started; the next approved action is planning only.
- 2026-07-12: Reopen Sprint 001 in Review to add the approved Docker development
  configuration and frontend health test without beginning Sprint 002.
- 2026-07-12: Record Docker runtime verification as pending; do not claim container
  validation until Docker is available.
- 2026-07-12: Sprint 001 independent code review passed with the conclusion
  APPROVE WITH NON-BLOCKING FOLLOW-UP.
- 2026-07-12: Treat Docker runtime verification as a non-blocking follow-up and
  retain it in the Backlog.
- 2026-07-12: Approve pull request #3 for merge; Sprint 002 remains Not Started.
- 2026-07-13: Sprint 002 planning authorized.
- 2026-07-13: Planning does not authorize Sprint 002 implementation.
- 2026-07-13: Selected Sprint 002 candidate A, Household Investment Policy +
  Decision Journal.
- 2026-07-13: Approved the single-household, local-only, no-authentication boundary.
- 2026-07-13: Approved user-entered target allocation percentages while prohibiting
  actual holdings, accounts, and monetary data.
- 2026-07-13: Confirmed no AI, Guardian, broker integration, recommendations, or
  trading in Sprint 002.
- 2026-07-13: Planning approval does not yet authorize implementation.
- 2026-07-13: Standardized policy lifecycle as Draft → Published → Superseded.
- 2026-07-13: Standardized journal lifecycle as Draft → Confirmed → Archived with
  appended DecisionCorrection records outside the lifecycle state machine.
- 2026-07-13: Required a database-enforced or transaction-safe constraint allowing
  at most one total HouseholdProfile.
- 2026-07-13: Required localhost-only host port bindings for the local MVP.
- 2026-07-13: Required real PostgreSQL integration and transaction rollback tests.
- 2026-07-13: Approved provisional local-MVP non-advisory copy.
- 2026-07-13: Approved the temporary local-MVP retention and reset boundary.
- 2026-07-13: Confirmed production compliance, authentication, export, backup, and
  encryption remain deferred.
- 2026-07-13: Planning PR #4 must merge before any separate Sprint 002
  implementation approval; Sprint 002 remains Not Started.
- 2026-07-13: Corrected the policy publish contract to publish an
  InvestmentPolicyDraft.
- 2026-07-13: Confirmed DecisionCorrection is an append-only correction record,
  not a journal lifecycle state.
- 2026-07-13: Confirmed Sprint 002 permits at most one total HouseholdProfile and
  defines no household archive or inactive lifecycle.
- 2026-07-13: Planning PR #4 final independent review passed.
- 2026-07-13: Planning PR #4 approved for merge.
- 2026-07-13: Planning merge does not authorize Sprint 002 implementation.
- 2026-07-13: Sprint 002 Slice 1 implementation authorized.
- 2026-07-13: Slice 1 scope is limited to HouseholdProfile, PostgreSQL,
  AuditEvent, and the household UI.
- 2026-07-13: Later Sprint 002 slices remain unauthorized.
- 2026-07-13: Sprint 002 Slice 1 independent review requested changes for the
  PostgreSQL CI gate, database safety constraints, and post-mutation audit refresh UX.
- 2026-07-13: Preserve local PostgreSQL-test skipping when no database is
  configured, but prohibit skips when the CompoundOS CI gate is enabled.
- 2026-07-13: Mirror approved input-safety limits in Pydantic and named PostgreSQL
  constraints; these technical limits are not investment rules.
- 2026-07-13: Treat a successful household mutation and a failed audit refresh as
  separate outcomes, and retry only the audit GET.
- 2026-07-13: Slice 1 remains in Review and Slice 2 remains unauthorized.
- 2026-07-13: Sprint 002 Slice 1 final independent review passed with the
  conclusion APPROVE WITH NON-BLOCKING FOLLOW-UP.
- 2026-07-13: Review finding M-1 is resolved by the required real PostgreSQL CI gate.
- 2026-07-13: Review finding M-2 is resolved by named database safety constraints.
- 2026-07-13: Review finding M-3 is resolved by independent audit refresh UX and
  GET-only retry behavior.
- 2026-07-13: Pull request #5 is approved for merge.
- 2026-07-13: Sprint 002 remains In Progress; Slice 2 remains unauthorized and
  Not Started.
- 2026-07-14: Sprint 002 Slice 2 technical design authorized.
- 2026-07-14: Technical design does not authorize Slice 2 implementation; Slice 2
  remains Not Started and Slice 3 remains unauthorized.
- 2026-07-14: Approved three required publication fields: `objectives`,
  `time_horizon`, and `decision_process`; the other seven policy categories may
  remain empty.
- 2026-07-14: Approved `NUMERIC(5,2)` storage and the decimal-string API contract
  for target percentages, with no silent rounding.
- 2026-07-14: Approved PostgreSQL immutability triggers with strict Version sealing
  and supersession transitions and deferred commit-time sealing enforcement.
- 2026-07-14: Approved atomic replacement of the complete Draft allocation
  collection with optimistic revision control.
- 2026-07-14: Approved a Policy-filtered audit read while retaining the existing
  HouseholdProfile audit endpoint.
- 2026-07-14: Approved blank/current-Published-only Draft sourcing and rejected
  arbitrary historical or Superseded sources.
- 2026-07-14: Required a database-generated AuditEvent `sequence_number` for
  deterministic insertion ordering of Policy and Household audit reads, without
  treating it as concurrent transaction commit order.
- 2026-07-14: These design decisions do not authorize Slice 2 implementation;
  Slice 2 remains Not Started and Slice 3 remains unauthorized.
- 2026-07-14: Sprint 002 Slice 2 Technical Design final independent review
  conclusion is APPROVE; pull request #6 is approved for merge.
- 2026-07-14: Merging pull request #6 does not authorize Slice 2 implementation;
  Slice 2 remains Not Started and Slice 3 remains unauthorized.
- 2026-07-14: Sprint 002 Slice 2A implementation authorized for Investment Policy
  persistence and immutable database snapshots only.
- 2026-07-14: Slice 2A may add migration, ORM mapping, database helpers, and real
  PostgreSQL tests, but no Policy service, API, or frontend workflow.
- 2026-07-14: Slice 2B, Slice 2C, and Slice 3 remain unauthorized.
- 2026-07-14: Sprint 002 Slice 2A final independent review passed with the
  conclusion APPROVE WITH NON-BLOCKING FOLLOW-UP.
- 2026-07-14: Record stronger Policy persistence schema/trigger regression
  assertions and Alembic `path_separator = os` migration validation as
  non-blocking maintenance Backlog items.
- 2026-07-14: Pull request #7 is approved for merge; Slice 2A is Done while
  Sprint 002 remains In Progress.
- 2026-07-14: Slice 2B, Slice 2C, and Slice 3 remain unauthorized and Not Started.
- 2026-07-14: Sprint 002 Slice 2B implementation authorized for the Investment
  Policy backend workflow and API only.
- 2026-07-14: Slice 2B implements approved decimal-string allocation contracts,
  Policy/Draft lifecycle transactions, immutable publication, version history,
  and Policy-filtered audit reads.
- 2026-07-14: Slice 2B enters Review; Slice 2C and Slice 3 remain unauthorized and
  Not Started.
- 2026-07-14: Slice 2B independent review concluded REQUEST CHANGES for M-1
  response snapshot atomicity, M-2 blocking test coverage, and L-1 strict Policy
  creation body validation.
- 2026-07-14: M-1, M-2, and L-1 review fixes were implemented for independent
  incremental review; pull request #8 remains Draft and is not approved for merge.
- 2026-07-14: Docker/browser runtime validation and the Alembic
  `path_separator = os` warning remain non-blocking Backlog items; Slice 2C and
  Slice 3 remain unauthorized and Not Started.
- 2026-07-14: Slice 2B final incremental review concluded APPROVE WITH
  NON-BLOCKING FOLLOW-UP; M-1 atomic PATCH response snapshots and M-2 blocking
  test coverage are fully resolved.
- 2026-07-14: L-1 is partially resolved: omitted and `{}` Policy-create bodies are
  accepted, non-empty objects/scalars/arrays return 422, and explicit JSON `null`
  remains accepted as a LOW non-blocking follow-up.
- 2026-07-14: Pull request #8 is approved for merge. Slice 2B is Done while Sprint
  002 remains In Progress; Slice 2C and Slice 3 remain unauthorized and Not Started.
- 2026-07-14: Sprint 002 Slice 2C implementation authorized for the local-only
  Investment Policy frontend workflow only; Slice 3 remains unauthorized.
- 2026-07-14: Slice 2C implements `/policy`, a typed Policy API client, explicit
  Draft text and allocation saves, mechanical publication confirmation, immutable
  Published/history views, Policy audit reads, and confirmed Draft discard without
  changing the approved backend contract.
- 2026-07-14: Slice 2C enters Review. Sprint 002 remains In Progress; Slice 3
  remains unauthorized and Not Started.
