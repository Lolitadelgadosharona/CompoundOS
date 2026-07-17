# Changelog

## Sprint 003 — Portfolio Snapshot + Holdings Foundation (2026-07-17)

### Slice A: Portfolio Persistence (PR #20)
- Alembic revision 0004: portfolios, portfolio_drafts, portfolio_draft_holdings,
  portfolio_snapshots, portfolio_snapshot_holdings
- Named CHECK and UNIQUE constraints on all tables
- PL/pgSQL triggers: fn_portfolio_snapshot_immutability,
  fn_portfolio_draft_consistency, fn_portfolio_lifecycle
- SQLAlchemy ORM models for all five tables
- 130 real PostgreSQL tests (0 skipped)

### Slice B: Portfolio Backend API (PR #21)
- Pydantic request/response schemas with decimal-string contracts
- Repository queries with FOR UPDATE support
- Service transaction boundaries with lock ordering
- All /api/portfolio endpoints: POST /draft, GET, PATCH /draft,
  PUT /draft/holdings, POST /draft/confirm, POST /draft/discard,
  GET /snapshots, GET /snapshots/{id}, GET /audit
- Concurrency tests, rollback tests, revision conflict tests
- Portfolio-filtered AuditEvent reads

### Slice C: Portfolio Frontend (PR #22)
- /portfolio page with typed Portfolio API client
- All 18 UI states: loading, no-household, no-portfolio, draft-editor,
  holding-editor, holding-validation, confirm-review, confirm,
  current-snapshot, snapshot-history, snapshot-detail, audit-timeline,
  409-conflict, error/retry, dirty-state, discard, local-only, non-advisory
- BigInt-based client-side total_value estimation (non-authoritative)
- Decimal strings throughout API boundary; no Number/parseFloat
- Cash unit_price 1.00 with neutral technical hint
- Zero holdings warning with explicit confirmation
- 409 conflict preserves local input with explicit reload
- Separate abort controllers for core, history, audit, and snapshot detail
- 80 new frontend tests (55 API client + 25 component)

## Sprint 002 — Household Investment Policy + Decision Journal (2026-07-13–2026-07-16)

### Slice 1: Household and Persistence Foundation
- HouseholdProfile CRUD, PostgreSQL, AuditEvent, household UI

### Slice 2A: Investment Policy Persistence
- Five Policy/Draft/Allocation/Version tables, immutability triggers

### Slice 2B: Investment Policy Backend API
- Pydantic contracts, decimal-string allocations, repository, service, router

### Slice 2C: Investment Policy Frontend
- /policy page, typed API client, draft editor, allocation management,
  publication review, version history, audit timeline

### Slice 3A: Decision Journal Persistence
- Four Decision Journal tables, five trigger functions, 138 PostgreSQL tests

### Slice 3B: Decision Journal Backend API
- Twelve endpoints, Pydantic contracts, atomic service transactions

### Slice 3C: Decision Journal Frontend
- /decisions page, draft creation and editing, confirm/review, corrections

### Safe Autopilot Foundation (PR #13)
- Self-driving infrastructure, launchd supervisor, blind reviewer, CI monitor

## Sprint 001 — Project Foundation (2026-07-11–2026-07-12)
- Monorepo with FastAPI + Next.js + PostgreSQL + Docker Compose
- Health endpoints, migration pipeline, CI gates
