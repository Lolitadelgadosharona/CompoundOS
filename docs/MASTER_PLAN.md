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
- Current implementation authorization: none
- Slice 2: Technical Design / Not Started
- Slice 2 implementation: Not authorized
- Slice 3: Not authorized

## Planning

- Sprint 002 selected direction: Household Investment Policy + Decision Journal.
- Planning pull request #4 completed independent planning review and is approved
  for merge.
- Sprint 002 Slice 1 planning and implementation are complete; later
  implementation slices remain unauthorized.
- Sprint 002 Slice 2 technical design is authorized for planning and review only.
- Slice 2 technical design does not authorize implementation.

## Backlog

- Complete Docker runtime verification in a Docker-enabled environment
- Align `NEXT_PUBLIC_API_URL` with the Docker build-time public environment model
- Split Python runtime and development dependencies before production hardening
- Design AuditEvent pagination before introducing higher-volume event sources
- Complete browser-path validation with the full Docker runtime stack
- Decide whether to migrate `frontend/` to `apps/web/`
- Add backend domain modules
- Introduce data persistence and orchestration
- Add Guardian monitoring workflows
- Add AI Investment Committee workflows
- Add notification escalation capabilities

## In Progress

- Sprint 002 remains In Progress; no further implementation slice is authorized.

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
- Sprint 002 remains In Progress; Slice 2 is not authorized.

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
