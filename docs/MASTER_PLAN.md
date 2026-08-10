# Master Plan

## Long-term Goal

Build CompoundOS as a trustworthy, explainable operating system for family office and wealth management workflows, beginning with a documented and testable foundation.

## Milestones

- Milestone 1: Foundation and governance scaffold
- Milestone 2: Core platform services and health monitoring
- Milestone 3: Decision support workflows and review interfaces

## Current Sprint

- Sprint 001: Project Foundation — Done
- Sprint 002: Household Investment Policy + Decision Journal — Done
  - Slice 1: Household and Persistence Foundation — Done
  - Slice 2A: Investment Policy Persistence Foundation — Done
  - Slice 2B: Investment Policy Backend Workflow and API — Done
  - Slice 2C: Investment Policy Frontend Workflow — Done
  - Slice 3A: Decision Journal Persistence Foundation — Done
  - Slice 3B: Decision Journal Backend Workflow and API — Done
  - Slice 3C: Decision Journal Frontend — Done
  - Safe Autopilot Foundation — Done
- Sprint 003: Portfolio Snapshot + Holdings Foundation — Done
  - Slice A (Persistence): Done (PR #20, merge e9743a5)
  - Slice B (Backend API): Done (PR #21)
  - Slice C (Frontend): Done (PR #22, merge 0a841d4)
- Sprint 004: Guardian Monitoring Foundation — Done ✓
  - Slice A (Persistence): Done (PR #26, migration 0007)
  - Slice B (Backend API): Done (PR #27, #28, #29, #30, #31)
  - Slice C (Frontend): Done (PR #32, #33, #34, #35)
- Sprint 005: Data Orchestration Foundation — Done ✓
  - Technical Design Gate: Done (PR #37, #38)
  - Slice A — Orchestration Persistence: Done (PR #38, 0008 base; PR #39 hardening; PR #40 lease fencing; PR #41 fencing closure)
  - Slice B — Worker + Backend API: Done (PR #42; PR #43 reliability; PR #44 process integrity; PR #45 atomic commit; PR #46 lease commit window)
  - Slice B — PostgreSQL Isolation Stabilization: Done (PR #47)
  - Slice C — Automation Frontend: Done (PR #48)
  - Migrations 0008–0011: job_definitions, schedules, runs, attempts, leases
  - 9 Automation endpoints, /automation workspace, Worker status
  - 431 PG / 136 non-PG / 217 frontend test baseline
  - Sprint 005 Orchestration Corrective: Done (2026-08-09)
    - PR #75 squash-merged as 16aa86b853a20afc532a5f3144c2f8eb539ef0da
    - Independent review: 0 BLOCKER / 0 HIGH / 2 MEDIUM / 4 LOW
    - Reviewed HEAD: 8551acf4e306315d07703bba86ca92204ec7dd9e
    - Post-merge CI 31318099840: backend SUCCESS (608 PG, 138 non-PG)
    - Fixes: fenced rollback, pre-spawn commit, heartbeat expiry extension,
      authoritative reconciliation, lock ordering (runs→leases→ALL attempts),
      rowcount=0 no-fallback
    - 3 new test modules: test_corrective_orchestration (1285 lines),
      test_retry_exhaustion, test_reconciliation_outcomes
    - Follow-up backlog: OM-001
- Sprint 006: AI Investment Committee Foundation — Done ✓
  - Technical Design Gate: Done (PR #50)
  - Slice A — Persistence + Evidence Contracts: Done (PR #51, migration 0012)
  - Slice B — Provider + Validator + Orchestration + API: Done (PR #53, 9 endpoints)
  - Slice C — Committee Frontend: Done (PR #54, /committee workspace)
  - 15 Owner Decisions all resolved and implemented
  - 491 PG / 136 non-PG / 242 frontend test baseline
- Sprint 007: Personal V1 Hardening + Notification — Done ✓
  - Technical Design Gate: Done (15/15 Owner Decisions resolved)
  - Slice A — Backup, Export & Recovery: Done (PR #60 base, PR #61 lint, PR #62 integrity, PR #63 review)
  - Slice B — Health Dashboard, Credential UX: Done (PR #60, #61, #62, #63)
  - Slice C — Lightweight Local Notification: Done (PR #64 foundation, PR #65 integrity corrective)
  - Migration 0014 (health_integrity), 0015 (notification_foundation), 0016 (notification_integrity)
  - Notification: explicit opt-in (disabled by default), 4 API routes, structured templates, household-scoped dedup, macOS AppleScript argv adapter, body privacy preview
  - Health service wired as notification source (DEGRADED/UNAVAILABLE → dispatch)
  - Guardian and Backup notification sources wired (Sprint 008 Slice A)
  - Committee and Automation notification sources wired (Sprint 008 Slice B, Draft PR #73)
  - PG 571 / non-PG 134+2 / frontend 251 test baseline
  - Closeout PR #66: squash merge 2f4f12569ae702fcbcc9a0bb01b199d68fe26327
  - Main CI run 29888368096: 3/3 success
- SM-001 (Security Maintenance): Done — PR #71 (30e9253) merged as
  2adbf07ffc9d9a277a32cf527081ff55531ed6f7 (2026-07-27). Upgraded
  next 16.2.10→16.2.12, eslint-config-next→16.2.12, postcss 8.5.10→8.5.18.
  npm audit --omit=dev: 0 vulnerabilities. Resolved 11 CVEs (9 Next.js +
  2 PostCSS).
- Sprint 008: Done — Slice A Done (2026-07-28); Slice B Done (2026-08-01); Slice C Done (2026-08-09)
  - Direction: Notification Source Wiring + Daily Operations (Candidate A)
  - Proposal: docs/sprints/SPRINT_008_PROPOSAL.md
  - Open Questions: docs/sprints/SPRINT_008_OPEN_QUESTIONS.md (8/8 resolved)
  - Technical Design: docs/sprints/SPRINT_008_TECHNICAL_DESIGN.md (Owner Approved, 2026-07-22)
  - Slice A — Guardian + Backup Notification Source Wiring: **Done**
    - PR #69 (0171a12) squash-merged as aa444aa9b602fbef2bd8a6608bc7847eea1fa10d
    - Main CI 30322128439: 3/3 SUCCESS
    - Review: 0 BLOCKER / 0 HIGH / 0 MEDIUM / 0 LOW
    - Guardian: HTTP manual + worker scheduled notification dispatch
    - Backup: all completion/failure paths dispatch
    - Dedicated notification sessions per Technical Design
    - Deterministic FakeAdapter dedup tests with explicit assertions
  - Slice B — Committee + Automation Notification Source Wiring: **Done** (2026-08-01)
    - PR #73 squash-merged as a7a01ca1552ad43618177ceac9580643fd6c8d48
    - Main CI 30415134394: 3/3 SUCCESS
    - Independent Review: 0 BLOCKER / 0 HIGH / 0 MEDIUM / 0 LOW
    - Committee: dispatch session_complete info after run_committee() completion
    - Automation: dispatch run_failed warning from worker after terminal run failure
    - Dedicated notification sessions per Technical Design §3.2, §3.4
  - Slice C — Daily Schedules + Schedule UI: **Done** (2026-08-09)
    - PR #74 squash-merged as 49e3a2258d6f9063c28e7133eee5f60734f5e2b7
    - Independent review: APPROVE WITH NON-BLOCKING FOLLOW-UP (0 BLOCKER, 1 HIGH fixed, 3 MEDIUM, 2 LOW)
    - Migration 0017: CREATE OR REPLACE FUNCTION expanding job_type allowlist
    - Guardian daily schedule: default disabled, guardian.evaluate_all
    - Backup daily schedule: default disabled, backup.daily
    - Idempotency: schedule_id + schedule-local date + ON CONFLICT DO NOTHING
    - Schedule UI: enable/disable + time/timezone in /automation workspace
    - COS-008-C-HARDEN: fail-closed execution dispatch
      - backup.daily execution: NOT YET IMPLEMENTED (raises _JobTypeExecutionNotSupported)
      - Unknown job types: fail closed — never silently fall through to Guardian
    - 18 tests: 12 original + 6 COS-008-C-HARDEN regression
    - Remaining follow-ups: M1 DELETE, M2 lazy seed, M3 clock, L1 allowlist drift, TECH-001 frontend audit
- Sprint 009: Wealth Intelligence Foundation — IN PROGRESS
  - Technical Design: docs/sprints/SPRINT_009_TECHNICAL_DESIGN.md
  - Architecture Design APPROVED (Owner authorization for Slice A implementation)
  - Scope: Asset identity, multi-currency positions, transactions, investment ideas,
    versioned policy enrichment (buckets/rules), AI authority matrix, read-only
    connector architecture
  - Slices: A (Core Portfolio Schema), B (Policy Enrichment), C (Ideas + Decision Bridge),
    D (Manual Import + Data Source Foundation)
  - Slice A: DONE — merged as 9f0ed00 (PR #78)
    - Migration 0018_portfolio_foundation
    - Tables: assets, positions, cash_balances, transactions, fx_rates, data_sources
    - Account extension: account_type, capital_bucket, currency, provider, provider_account_id
    - 50 PostgreSQL integration tests covering all constraints and provenance
    - Provenance: source + source_record_id + observed_at + imported_at on every datum
    - Import idempotency: partial unique indexes on (source, source_record_id)
  - Follow-ups (COS-009-A-FU):
    - H1: Transaction immutability trigger before first financial connector
    - M1: Atomic position upsert contract
    - L1: cash_balances imported_at naming consistency
    - L3: transactions(executed_at) index when volume warrants
  - 7 Owner Decisions pending (OD-9-1 through OD-9-7)
  - 5 proposed ADRs (0007–0011)
  - NO broker integrations. NO credentials. NO trading.
  - Slice B: DONE — merged as 4a7312c (PR #79)
    - Migration 0019_policy_enrichment
    - Tables: policy_capital_buckets, policy_rules
    - Version immutability: BEFORE UPDATE/DELETE triggers on version rows
    - 35 PostgreSQL integration tests covering constraints and triggers
    - No hardcoded allocations — policy remains configurable
    - Guardian compatibility: schema supports future drift detection
  - Slice C: DONE — merged as f87e4e8 (PR #80)
    - Migration 0020_investment_idea_bridge
    - Tables: investment_ideas, idea_status_history
    - Decision bridge: decision_drafts + confirmed_snapshots gain investment_idea_id FK
    - 27 PostgreSQL integration tests
    - Follow-ups: COS-009-C-FU-M1 (lifecycle transition enforcement), FU-L1 (soft-delete), FU-L2 (unused ALLOWED_TRANSITIONS)
  - Slice D: DONE — merged as 61e7a8c (PR #81)
    - Migration 0021_manual_import_foundation: assets.confidence + transaction immutability
    - CSV import pipeline: parse → validate → resolve → store
    - Asset resolution: ISIN → (symbol,exchange,currency) → create unverified
    - Import idempotency: upsert positions/balances, skip duplicate transactions
    - Provider interfaces: AccountImporter, PositionImporter, TransactionImporter, BalanceImporter
    - 30 PostgreSQL integration tests
    - Follow-ups: COS-009-D-FU-L1 (atomic position upsert), FU-L2 (extend immutability fields), SEC-002 (global auth)
  - Sprint 009: COMPLETE — Slices A, B, C, D all done
  - Sprint 010: DESIGN COMPLETE — Owner Decisions Resolved
    - Design document: docs/sprints/SPRINT_010_TECHNICAL_DESIGN.md
    - Owner decisions: docs/sprints/SPRINT_010_OWNER_DECISIONS.md (OD-10-1 through OD-10-5 — all resolved)
    - 4 slices: Committee Bridge, Guardian Intelligence, Dashboard+Learning, Security+Notifications
    - Slice A: DONE — merged as 972bf24 (PR #82)
      - Migration 0022_committee_bridge: committee_review_requests + evidence types
      - Bridge: investment_ideas → committee_sessions via Owner-controlled workflow
      - 18 PostgreSQL integration tests
    - Slice B: DONE — merged as 414e38f (PR #83)
      - Migration 0023_guardian_intelligence: extended check_type CHECK (+5 types)
      - guardian_intelligence.py: 5 evaluation functions + BLOCK_RECOMMENDATION
      - 20 PostgreSQL integration tests
      - Design doc: docs/sprints/SPRINT_010_SLICE_B_TECHNICAL_DESIGN.md
    - Slice C: DONE — merged as 558dbac (PR #84)
      - Migration 0024_dashboard_learning: decision_reviews + snapshot columns
      - Dashboard API: GET /api/dashboard (net worth, allocation, compliance, risks)
      - Learning Loop: decision_reviews, is_high_impact(), review completion
      - 10 PostgreSQL integration tests
      - Follow-ups: COS-010-C-FU-M1/L1/L2/L3
    ### Follow-ups (Non-blocking)
    - COS-010-C-FU-M1: Replace dynamic sqlalchemy imports in dashboard router
    - COS-010-C-FU-L1: Avoid duplicate position loading in dashboard service
    - COS-010-C-FU-L2: Add review completion 409 boundary test
    - COS-010-C-FU-L3: Add positive high-impact review scheduling test
    - Slice D: DONE — merged as ba5054b (PR #85)
      - Migration 0025_auth_and_audit: owner_api_keys, audit_log, notification_escalation_rules
      - Auth: Global X-API-Key middleware, environment-based bypass, key CRUD
      - Audit: Immutable audit_log, 4 event types, key lifecycle logging
      - 22 PostgreSQL integration tests
      - Sprint 010: COMPLETE (all 4 slices merged)

### Sprint 011: DESIGN REVISED — APPROVED WITH IMPROVEMENTS
- Technical Design (Revised): docs/sprints/SPRINT_011_TECHNICAL_DESIGN.md
- Design Direction: docs/sprints/SPRINT_011_DESIGN_DIRECTION.md
- Owner Decisions: docs/sprints/SPRINT_011_OWNER_DECISIONS.md (12 pending)
- Architecture: Research Request → Run → Perspective → Memo layers
- 6 tables: research_requests, research_runs, perspective_analyses,
  investment_memos, investment_knowledge_memory, market_data_cache
- 6 AI perspectives including Portfolio Construction
- Investment Memo schema with 9 structured sections
- Slice A: DONE — merged as 355637d (PR #86)
  - Migration 0026_research_foundation: research_requests + research_runs
  - API: POST /api/research/request + GET /status + GET /runs
  - Run immutability trigger (err 55000)
  - 10 PostgreSQL integration tests
  - Slice B: DONE — merged as a9099d5 (PR #87)
  - Slice C: IN PROGRESS (PR #88)
    - Migration 0029_perspective_analyses: 6 perspectives, immutability trigger

- **SM-001 Authorized (2026-07-27):** Security-maintenance Sprint authorized by Owner.

### Sprint 012: IN PROGRESS
- Slice A: DONE — merged as 59d137e (PR #90)
  - LLM Runtime: prompt_templates + llm_execution_log
- Slice B: DONE — merged as b5444ac (PR #91)
  - Research Pipeline: WorkerQueue, EvidenceCollector, PerspectiveExecutor,
    ConfidenceEngine, ResearchPipeline orchestrator
- Slice C: DESIGN COMPLETE — Awaiting Owner Approval
  - Provider interfaces, caching strategy, freshness rules, provenance, graceful degradation

## Backlog

- COS-009-D Follow-ups (from Slice D independent review):
  - COS-009-D-FU-L1: Atomic position import upsert — call supersede_latest_positions on re-import.
  - COS-009-D-FU-L2: Extend transaction immutability trigger to cover price_currency and fee_currency.
  - SEC-002: Global authentication layer — all mutation endpoints need OWNER authorization.
- COS-009-C Follow-ups (from Slice C independent review):
  - COS-009-C-FU-M1: Enforce investment idea lifecycle transitions before API exposure (ALLOWED_TRANSITIONS defined but not enforced at DB or repo level).
  - COS-009-C-FU-L1: Consider archive instead of delete for investment ideas (Owner product decision).
  - COS-009-C-FU-L2: Remove or integrate unused ALLOWED_TRANSITIONS dict in schemas.
- OM-001 — Orchestration corrective review cleanup (MEDIUM/LOW follow-ups from Sprint 005 Corrective independent review):
  - M1: Remove or document the unused `clock` parameter in `validate_lease_for_commit()` — `clock_timestamp()` is authoritative.
  - M2: Update deferred notification test to exercise monkeypatched production call path.
  - L1-L4: Clean up repeated `os` imports, pool_pre_ping in one-shot engine, StaleRunReaper lock-order docs, ReconciliationResult formatting.
- SEC-001 — Make CompoundOS private before real financial account integration.
  - Repository is currently PUBLIC.
  - Must be completed before any real broker/bank credential or personal financial-account integration is authorized.
  - Do not put actual secrets into documentation.
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
- Sprint 002 Slice 2C: Investment Policy Frontend Workflow
- Local-only `/policy` page with typed Policy API client, explicit Draft text and
  allocation saves, mechanical publication review with dirty-state gate, immutable
  Published and version history views, Policy audit timeline, Draft creation, and
  confirmed Draft discard
- Independent core/auxiliary resource isolation, generation-guarded audit and
  history coordination, Unicode code-point allocation limits, and row-specific
  accessible control names
- Frontend test suite expanded from 37 to 62 tests covering async coordination,
  dirty-state transitions, deferred-promise race conditions, and accessibility
- Sprint 002 Slice 3A: Decision Journal Persistence and Immutability Foundation
- Alembic revision `0003_decision_journal_foundation` creating four Decision
  Journal tables with five PL/pgSQL trigger functions
- Three deferred CONSTRAINT TRIGGERs on decisions (INSERT/UPDATE),
  decision_drafts (INSERT/DELETE), and decision_confirmed_snapshots
  (INSERT/DELETE) for cross-table lifecycle consistency at COMMIT time
- Shared deferred trigger function queries current database state at COMMIT
  instead of relying on stale NEW records, preventing bypass via child-table
  mutations and cross-transaction updates
- Named CHECK constraints, UNIQUE constraints, and FK RESTRICT/NO ACTION on
  all four tables for status, text, date, correction numbering, and ownership
- SQLAlchemy ORM models aligned with migration: Decision, DecisionDraft,
  DecisionConfirmedSnapshot, DecisionCorrection
- 138 real PostgreSQL tests passed (0 skipped) covering migration lifecycle,
  schema, constraints, lifecycle transitions, immutability, corrections,
  deferred consistency, and bypass regression
- Slice 3A completed without a Decision service, API, frontend, or Slice 3B/3C
  behavior
- Sprint 002 Safe Autopilot Foundation: Self-driving infrastructure for automated
  task execution, review, and CI monitoring via Hermes and Qoder CLI agents.
  Includes main CLI (install/start/stop/restart/status/logs/doctor/dry-run/
  enqueue/unblock), worker with isolated git worktrees, launchd-based supervisor
  with crash recovery, blind code reviewer, CI monitor, structured task schema
  with approval/risk gates, and 34 automated tests. Qoder CLI v1.0.47 detected
  as headless-capable but currently verified_healthy=false (TLS/auth failure).
  Hermes v0.17.0 is the always-available default worker. Codex not installed
  (circuit breaker open). Auto-merge globally disabled pending independent
  security review. PR #13 squash-merged after two rounds of independent blind
  review with all BLOCKER/HIGH/MEDIUM findings resolved.
- Sprint 003: Portfolio Snapshot + Holdings Foundation — Done.
- Sprint 003 Slice A: Portfolio Persistence (PR #20, e9743a5) — Alembic
  revision 0004 with five tables, named constraints, PL/pgSQL triggers,
  ORM models, 130 real PostgreSQL tests.
- Sprint 003 Slice B: Portfolio Backend API (PR #21) — Pydantic schemas,
  decimal-string contracts, repository queries, service transactions,
  all /api/portfolio endpoints.
- Sprint 003 Slice C: Portfolio Frontend (PR #22, 0a841d4) — /portfolio
  page with typed API client, draft editor, snapshot history and detail,
  audit timeline, 80 new frontend tests (55 API + 25 component), BigInt-based
  client-side estimation, separate abort controllers for core/history/audit.

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
- 2026-07-15: PR #9 initial independent review concluded REQUEST CHANGES (M-1
  through M-4, L-1 through L-6).
- 2026-07-15: All ten review findings (M-1 through M-4, L-1 through L-6) resolved
  in fix commit c732569.
- 2026-07-15: PR #9 final independent incremental review concluded APPROVE with
  zero new findings.
- 2026-07-15: Pull request #9 approved for merge and squash-merged into main.
- 2026-07-15: Sprint 002 Slice 3 Technical Design Gate authorized. The design
  covers Decision Journal data model, lifecycle, API, UI, immutability,
  concurrency, audit, and open decisions. No implementation is authorized.
- 2026-07-15: Technical design recommends Approach C (Stable Decision Identity +
  Draft + Confirmed Version) with full replacement snapshot corrections.
- 2026-07-15: Twelve Open Decisions (OD-S3-1 through OD-S3-12) recorded, all
  marked Open — Owner Decision Required.
- 2026-07-15: Draft PR created on planning/sprint-002-slice-3-decision-journal
  branch. The PR remains Draft and is not approved for merge.
- 2026-07-15: Merging the Slice 3 Technical Design does not authorize Slice 3
  implementation. Each implementation slice (3A, 3B, 3C) requires separate
  explicit authorization.
- 2026-07-16: Initial independent Technical Design Review of PR #10 concluded
  REQUEST CHANGES: 0 BLOCKER, 2 HIGH (M-1: Draft discard identity semantics
  undefined; M-2: correction_number IDENTITY ALWAYS technically incorrect),
  3 MEDIUM (M-3: Confirm lock order inconsistency; M-4: Archived+Correction
  treated as approved; M-5: Household audit timeline resource boundary),
  3 LOW (L-1: Decision Detail original/effective response ambiguity; L-2:
  Confirm/Discard loser response undefined; L-3: correction_count concurrent
  inaccuracy in audit metadata).
- 2026-07-16: All eight review findings (M-1 through M-5, L-1 through L-3)
  revised in the technical design document. Three new Open Decisions added:
  OD-S3-13 (Draft discard identity semantics), OD-S3-14 (Correction numbering
  and ordering), OD-S3-15 (Correction eligibility for Archived Decisions).
  OD-S3-10 expanded to cover Household audit timeline scope. OD-S3-7 updated
  to remove premature "archived Decisions still correctable" claim.
- 2026-07-16: OD-S3-1 through OD-S3-15 remain Open — Owner Decision Required.
  PR #10 remains Draft and is not approved for merge. Design remains pending
  independent re-review. Slice 3 Implementation remains Not Authorized.
  Slice 3A, 3B, 3C remain Not Started.
- 2026-07-16: Incremental Technical Design Re-Review concluded APPROVE WITH
  NON-BLOCKING FOLLOW-UP. All eight original findings (M-1 through M-5, L-1
  through L-3) are RESOLVED. Two new LOW non-blocking findings: NBF-1
  (Correction trigger missing status validation) and NBF-2 (lifecycle trigger
  missing discarded transition).
- 2026-07-16: OD-S3-1 through OD-S3-15 all Resolved by Project Owner.
  OD-S3-1 (Option B: multiple independent Drafts), OD-S3-2 (title, summary,
  rationale, decision_date required at Confirm), OD-S3-3 (no classification in
  MVP), OD-S3-4 (DATE, backfill allowed, future forbidden), OD-S3-5 (current
  Published Version only, lock + re-validate), OD-S3-6 (consume Draft + immutable
  snapshot), OD-S3-7 (Archive = list hiding, allow unarchive, optional reason),
  OD-S3-8 (full replacement snapshot), OD-S3-9 (user text/dates correctable,
  Policy Version/audit/archive metadata not correctable), OD-S3-10 (Decision-
  filtered audit + Household timeline includes, cursor pagination), OD-S3-11
  (provisional MVP non-advisory copy), OD-S3-12 (3A/3B/3C split), OD-S3-13
  (Option A: atomic identity deletion for never-Confirmed discard), OD-S3-14
  (Option A: per-decision sequential via Decision lock + MAX+1), OD-S3-15
  (Option A: Archived still allows Correction).
- 2026-07-16: NBF-1 resolved: Correction INSERT trigger now validates Decision
  status IN ('confirmed', 'archived') with stable SQLSTATE/error identifiers.
  NBF-2 resolved: new DELETE guard trigger fn_decision_identity_delete_guard
  allows DELETE only when status=draft; forbids confirmed/archived DELETE.
- 2026-07-16: Global consistency revision applied across all design sections.
  All conditional/Open language replaced with resolved decisions. PR #10 remains
  Draft. Design decision changes pending final consistency review. Slice 3
  Implementation remains Not Authorized. Slice 3A, 3B, 3C remain Not Started.
  Merging the Technical Design PR does not authorize Slice 3A. Existing Backlog
  preserved.
- 2026-07-16: Final Owner Decision Consistency Review of PR #10 concluded
  APPROVE WITH ONE MEDIUM FINDING: 14 of 15 ODs fully consistent; 1 MEDIUM
  (§8.12 pagination default 20 vs §5.6/OD table default 50); 2 LOW (NBF-1:
  §5.1 AuditEvent action names pending marker; NBF-2: §11.2 missing explicit
  decision_date boundary test).
- 2026-07-16: All three consistency review findings revised in the technical
  design document. M-1 fixed: §8.12 pagination default corrected to 50.
  NBF-1 resolved: §5.1 action names marked "Accepted for Slice 3
  implementation design" with explicit finality requirements. NBF-2 resolved:
  §11.2 test matrix now includes decision_date boundary tests (Schema/API,
  PostgreSQL, UI). OD-S3-1 through OD-S3-15 remain Resolved — no Owner
  Decision changed. PR #10 remains Draft. Slice 3 Implementation remains
  Not Authorized. Slice 3A, 3B, 3C remain Not Started. Design pending final
  focused re-review. Existing Backlog preserved.
- 2026-07-16: Final Focused Incremental Re-Review of PR #10 concluded APPROVE.
  M-1 (pagination default), NBF-1 (action names), NBF-2 (decision_date tests)
  all confirmed RESOLVED. Zero new findings. No regressions detected. OD-S3-1
  through OD-S3-15 remain Resolved.
- 2026-07-16: PR #10 approved for merge. Technical Design Gate Done. Merging
  the Technical Design PR does not authorize Slice 3A. Slice 3 Implementation
  remains Not Authorized. Slice 3A, 3B, 3C remain Not Started. The next step
  can only be decided by the Project Owner.
- 2026-07-16: Sprint 002 Slice 3A implementation authorized for Decision Journal
  Persistence and Immutability Foundation only.
- 2026-07-16: Slice 3A creates Alembic revision 0003 with four Decision Journal
  tables (decisions, decision_drafts, decision_confirmed_snapshots,
  decision_corrections), five PL/pgSQL trigger functions, deferred consistency
  enforcement, and aligned ORM models.
- 2026-07-16: Slice 3A adds no Decision service, repository workflow, API
  endpoint, Pydantic contract, router, frontend client, or /decisions page.
- 2026-07-16: Slice 3B and Slice 3C remain Not Authorized and Not Started.
- 2026-07-16: Sprint 002 Slice 3A initial independent review concluded REQUEST
  CHANGES with one BLOCKER finding (B1: deferred trigger fires only on decisions
  INSERT, missing UPDATE and child-table mutations that bypass lifecycle
  consistency checks via cross-transaction UPDATE, Draft deletion, snapshot
  insertion, and confirmed-to-draft regression).
- 2026-07-16: B1 resolved by adding two deferred CONSTRAINT TRIGGERs on
  decision_drafts (AFTER INSERT OR DELETE) and decision_confirmed_snapshots
  (AFTER INSERT OR DELETE), expanding decisions trigger to INSERT OR UPDATE, and
  updating the shared function to extract decision_id from TG_TABLE_NAME and
  query current database state at COMMIT time instead of relying on stale NEW
  records. Four bypass regression tests added and passing.
- 2026-07-16: Sprint 002 Slice 3A final independent review concluded APPROVE
  WITH NON-BLOCKING FOLLOW-UP. All BLOCKER, HIGH, and MEDIUM findings resolved.
  Zero outstanding issues. 138 required PostgreSQL tests passed, 0 skipped.
- 2026-07-16: Pull request #11 approved for merge. Slice 3A is Done. Sprint 002
  remains In Progress. Slice 3B and Slice 3C remain Not Authorized and Not
  Started. The next step can only be decided by the Project Owner.
- 2026-07-16: Sprint 002 Slice 3B implementation authorized for the Decision
  Journal Backend Workflow and API only.
- 2026-07-16: Slice 3B implements twelve Decision Journal API endpoints with
  strict Pydantic contracts, repository queries, atomic service transactions,
  Policy→Decision→Draft lock ordering, append-only Corrections, atomic
  never-Confirmed Draft discard, and redacted AuditEvents.
- 2026-07-16: Slice 3B adds no frontend, migration, dependency, Compose, CI,
  authentication, recommendation, Guardian, AI, Broker, trading, or Slice 3C
  behavior.
- 2026-07-17: Sprint 003 Slice C (Portfolio Frontend) authorized by Owner.
  Implemented /portfolio page with typed API client, decimal-string contracts,
  18 UI states from Technical Design §11, 80 new frontend tests. Independent
  blind review concluded APPROVE WITH NON-BLOCKING FOLLOWUP (0 BLOCKER/HIGH,
  zero MEDIUM after fix). PR #22 squash-merged as 0a841d4. Sprint 003 is Done.
  Sprint 004 remains Not Authorized.
- 2026-07-16: Slice 3B enters Review. Sprint 002 remains In Progress. Slice 3C
  remains Not Authorized and Not Started.
- 2026-07-28: Sprint 008 Slice A closeout — PR #69 squash-merged into main as
  aa444aa9b602fbef2bd8a6608bc7847eea1fa10d (main workflow 30322128439,
  3/3 SUCCESS). Guardian and Backup notification source wiring is Done.
  Review gate: 0 BLOCKER / 0 HIGH / 0 MEDIUM / 0 LOW. Slice B and Slice C
  remain NOT AUTHORIZED. No investment-rule, Guardian-threshold, or trading
  behavior changed.
- 2026-07-16: Slice 3B review completed — APPROVE WITH NON-BLOCKING FOLLOW-UP.
  Review findings (M-1, L-1 through L-5) and CI test failures (Policy Version
  trigger interaction, autobegin transaction conflict, missing confirmation
  field) resolved. CI: 6/6 checks pass, 302 tests (102 non-PG + 138 PG +
  62 frontend). Slice 3B is Done. Sprint 002 remains In Progress. Slice 3C
  remains Not Authorized and Not Started.
