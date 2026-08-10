# CompoundOS Architecture Snapshot — V1.0
# Post-Sprint 010

> **Date**: 2026-08-10
> **Main HEAD**: 55f039f
> **Migrations**: 0001–0025
> **PostgreSQL tables**: 44
> **Tests**: ~990

---

## 1. System Overview

CompoundOS is a family-office wealth-management platform with a FastAPI
backend, Next.js frontend, PostgreSQL persistence, and a Safe Autopilot
orchestration engine. After Sprint 010, the system provides:

- Complete financial data model with provenance
- Investment policy framework with versioning
- Decision journal with corrective records
- Guardian risk monitoring engine
- AI Investment Committee infrastructure
- CSV-based manual data import
- Wealth dashboard API
- Post-decision learning loop
- Owner API key authentication
- Immutable audit logging

---

## 2. Capability Map

### 2.1 Data Layer (Sprint 009-A, 009-D)

| Capability | Tables | Status |
|---|---|---|
| Asset identity | `assets` (ISIN, symbol, exchange, sector, confidence) | DONE |
| Portfolio accounting | `portfolios`, `portfolio_drafts` | DONE |
| Account management | `accounts` (capital_bucket, provider, currency) | DONE |
| Position tracking | `positions` (is_latest, market_value, observed_at) | DONE |
| Cash balances | `cash_balances` | DONE |
| Transaction history | `transactions` (immutable trigger) | DONE |
| FX rates | `fx_rates` | DONE |
| Data source registry | `data_sources` | DONE |
| Manual CSV import | CSV → parse → validate → resolve → store | DONE |
| Asset resolution | ISIN → (symbol, exchange) → create unverified | DONE |
| Data provenance | source, source_record_id, observed_at, imported_at on all records | DONE |

### 2.2 Policy Layer (Sprint 002, 009-B)

| Capability | Tables | Status |
|---|---|---|
| Investment policies | `investment_policies` | DONE |
| Policy versions | `investment_policy_versions` (sealed, superseded lifecycle) | DONE |
| Policy allocations | `investment_policy_version_allocations` | DONE |
| Capital bucket targets | `policy_capital_buckets` (target/min/max per bucket) | DONE |
| Policy rules | `policy_rules` (rule_type, rule_value, severity, enabled) | DONE |
| Version immutability | PL/pgSQL trigger on investment_policy_versions | DONE |

### 2.3 Decision Layer (Sprint 003, 009-C, 010-C)

| Capability | Tables | Status |
|---|---|---|
| Decision journal | `decisions`, `decision_drafts` | DONE |
| Decision confirmation | `decision_confirmed_snapshots` | DONE |
| Decision corrections | `decision_corrections` | DONE |
| Investment ideas | `investment_ideas`, `idea_status_history` | DONE |
| Idea lifecycle | draft → under_review → approved/rejected | DONE |
| Decision bridge | `investment_ideas` → `decision_drafts` FK | DONE |
| Post-decision reviews | `decision_reviews` (30d/90d/1yr/manual) | DONE |
| Review completion | outcome_notes, actual_return_pct, lessons_learned | DONE |
| High-impact detection | 5% portfolio threshold | DONE |

### 2.4 Risk Layer (Sprint 004, 010-B)

| Capability | Tables | Status |
|---|---|---|
| Guardian checks | `guardian_checks`, `guardian_check_drafts`, `guardian_check_confirmed` | DONE |
| Drift monitoring | check_type 'drift' — policy target vs actual | DONE |
| Category exposure | check_type 'category_exposure' | DONE |
| Bucket drift | check_type 'capital_bucket_drift' — Sprint 010-B | DONE |
| Position concentration | check_type 'single_position_concentration' | DONE |
| Sector concentration | check_type 'sector_concentration' | DONE |
| Exploration limit | check_type 'exploration_capital_limit' | DONE |
| Data staleness | check_type 'data_quality_staleness' | DONE |
| Evaluation engine | `guardian_evaluation_runs` | DONE |
| Events | `guardian_events` (drift_pp, exposure_pct, exceeded) | DONE |
| BLOCK_RECOMMENDATION | Critical events block committee review requests | DONE |

### 2.5 Intelligence Layer (Sprint 006, 010-A, 010-C)

| Capability | Tables | Status |
|---|---|---|
| Committee sessions | `committee_sessions` | DONE |
| Evidence pipeline | `committee_evidence_items` (9 source types) | DONE |
| Committee reports | `committee_reports` | DONE |
| Committee outcomes | `committee_outcomes` | DONE |
| Committee bridge | `committee_review_requests` (idea → session) | DONE |
| Wealth dashboard | GET /api/dashboard (7 data sections) | DONE |
| Net worth | Multi-currency, unconverted flagging | DONE |
| Allocation | By asset class, bucket, currency | DONE |
| Policy compliance | Bucket drifts, rule violations | DONE |
| Risk summary | Concentration risk, active events | DONE |

### 2.6 Security Layer (Sprint 010-D)

| Capability | Tables | Status |
|---|---|---|
| API key auth | `owner_api_keys` (SHA-256 hashed) | DONE |
| Global auth middleware | X-API-Key for all non-health endpoints | DONE |
| Environment bypass | development/test only | DONE |
| Key bootstrap | `python -m apps.api.bootstrap_key` | DONE |
| Key lifecycle | create → use → revoke → rotate | DONE |
| Audit logging | `audit_log` (immutable trigger) | DONE |
| Audit events | authentication.success/failure, owner.mutation, authorization.denied | DONE |
| Escalation schema | `notification_escalation_rules` (schema only) | DONE |

### 2.7 Orchestration Layer (Sprint 005, 007, 008)

| Capability | Tables | Status |
|---|---|---|
| Job automation | `job_definitions`, `schedules`, `runs`, `attempts`, `leases` | DONE |
| Worker heartbeats | `worker_heartbeats` | DONE |
| Backup/export | `backup_records`, `export_tasks` | DONE |
| Notifications | `notification_events`, `notification_preferences` | DONE |
| Household management | `household_profiles` | DONE |
| Audit events | `audit_events` | DONE |

---

## 3. Data Model Summary

### 3.1 Table Inventory (44 total)

```
Layer          Tables
─────────────  ──────────────────────────────────────
Household      household_profiles
Data           assets, positions, cash_balances, transactions,
               fx_rates, data_sources, accounts,
               portfolios, portfolio_drafts, portfolio_draft_holdings,
               portfolio_snapshots, portfolio_snapshot_holdings
Policy         investment_policies, investment_policy_versions,
               investment_policy_version_allocations,
               investment_policy_drafts, investment_policy_draft_allocations,
               policy_capital_buckets, policy_rules
Decision       decisions, decision_drafts, decision_confirmed_snapshots,
               decision_corrections, investment_ideas, idea_status_history,
               decision_reviews
Risk           guardian_checks, guardian_check_drafts,
               guardian_check_confirmed, guardian_evaluation_runs,
               guardian_events
Intelligence   committee_sessions, committee_evidence_items,
               committee_reports, committee_outcomes,
               committee_review_requests
Security       owner_api_keys, audit_log, notification_escalation_rules
Orchestration  job_definitions, schedules, runs, attempts, leases,
               worker_heartbeats, backup_records, export_tasks,
               notification_events, notification_preferences,
               audit_events
```

### 3.2 Triggers & Constraints

| Trigger/Constraint | Table | Purpose |
|---|---|---|
| Immutability | `transactions` | Blocks UPDATE/DELETE of core fields |
| Immutability | `audit_log` | Blocks ALL UPDATE/DELETE |
| Immutability | `investment_policy_versions` | Enforces seal→supersede lifecycle |
| Lifecycle consistency | `decisions` + `decision_drafts` + `decision_confirmed_snapshots` | Draft ↔ Confirmed integrity |
| Status history | `investment_ideas` → `idea_status_history` | Auto-log status transitions |

---

## 4. API Inventory

### 4.1 Endpoint Summary by Layer

| Layer | Prefix | Endpoints | Classification |
|---|---|---|---|
| Health | /health, /api/health | 2 | PUBLIC |
| Household | /api/households | 2 | READ |
| Policy | /api/policies | 8 | READ + OWNER_MUTATION |
| Portfolio | /api/portfolios | 6 | READ + OWNER_MUTATION |
| Decisions | /api/decisions | 5 | READ + OWNER_MUTATION |
| Ideas | /api/ideas | 4 | READ + OWNER_MUTATION |
| Guardian | /api/guardian | 5 | READ + OWNER_MUTATION |
| Committee | /api/committee | 6 | READ + OWNER_MUTATION |
| Committee Bridge | /api/ideas/{id}/request-review | 2 | OWNER_MUTATION |
| Import | /api/import | 4 | OWNER_MUTATION |
| Dashboard | /api/dashboard | 3 | READ |
| Reviews | /api/reviews | 3 | OWNER_MUTATION |
| Auth | /api/auth/keys | 3 | OWNER_MUTATION |
| Automation | /api/automation | 8 | OWNER_MUTATION |
| Backup | /api/backup | 3 | OWNER_MUTATION |
| Notifications | /api/notifications | 3 | READ |
| **Total** | | **67** | |

### 4.2 Auth Enforcement

- Global FastAPI middleware in `main.py`
- `/health`, `/api/health` → PUBLIC
- All other endpoints → X-API-Key required (non-dev/test)
- Environment bypass: `ENVIRONMENT=development` or `ENVIRONMENT=test`

---

## 5. Technology Stack

| Component | Technology |
|---|---|
| Backend | FastAPI (Python 3.9) |
| Frontend | Next.js 16 (App Router) |
| Database | PostgreSQL (psycopg3) |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Tests | pytest (810+ backend + PostgreSQL) |
| Auth | X-API-Key (SHA-256) |
| Orchestration | Custom multiprocessing worker |

---

## 6. Architecture Principles Enforced

1. **AI advisory only** — AI reads/analyzes/recommends; never executes
2. **Owner final authority** — All decisions require Owner approval
3. **Immutable financial history** — Transactions, audit logs, policy versions
4. **Decimal in finances** — No floating-point for money
5. **Data provenance** — Every imported record carries source/observed_at/imported_at
6. **Fail-closed security** — Auth required unless explicitly bypassed
7. **No credentials in code** — API keys hashed, env vars for config
8. **Additive migrations** — All migrations are reversible and non-destructive
9. **Owner decisions documented** — OD-NNN-N tracking for every sprint

---

## 7. Architectural Gaps

### A. Required Before AI Intelligence (Sprint 011+)

| Gap | Priority | Rationale |
|---|---|---|
| Market data sources | HIGH | AI research needs price/fundamental data |
| Research memory system | HIGH | Persist AI-generated research across sessions |
| Evidence enrichment | HIGH | Auto-populate committee evidence from research |
| Multi-perspective reasoning | MEDIUM | Multiple AI "committee members" analyzing same idea |
| Structured memo generation | MEDIUM | AI → formatted investment memo |
| Confidence scoring engine | MEDIUM | Beyond manual confidence levels |

### B. Required Before Real Portfolio Usage

| Gap | Priority | Rationale |
|---|---|---|
| Secure Production deployment | BLOCKER | Currently development-only |
| Real data import (not CSV) | HIGH | Broker connectors or API integrations |
| Frontend implementation | HIGH | Dashboard, decision UI, portfolio views |
| SEC-001: Private repository | HIGH | Before real financial data enters system |
| Production auth hardening | MEDIUM | HTTPS, key rotation policies, session management |
| Backup integrity verification | MEDIUM | Restore testing, backup encryption |

### C. Required Before Commercial Product

| Gap | Priority | Rationale |
|---|---|---|
| Multi-user support | MEDIUM | Family office may have multiple stakeholders |
| OAuth2/JWT auth | MEDIUM | Beyond single API key |
| Notification delivery | MEDIUM | Email/SMS for critical Guardian events |
| Performance optimization | LOW | Caching, query optimization for larger portfolios |
| Frontend polish | LOW | Professional UX/UI |

### D. Optional Future Improvements

| Gap | Priority | Rationale |
|---|---|---|
| Real-time market data | LOW | WebSocket/streaming feeds |
| Multi-currency base | LOW | Alternate base currency views |
| Tax-aware reporting | LOW | Capital gains, tax lots |
| Automated rebalancing signals | LOW | Policy → target → rebalance plan |
| External API for data providers | LOW | OpenAPI for third-party tools |

---

## 8. Test Coverage Summary

| Sprint | Tests | Type |
|---|---|---|
| Sprint 002-008 | ~810 | Core + orchestration + notifications |
| Sprint 009-A | 50 | Portfolio foundation |
| Sprint 009-B | 35 | Policy enrichment |
| Sprint 009-C | 27 | Investment ideas |
| Sprint 009-D | 30 | Manual import |
| Sprint 010-A | 18 | Committee bridge |
| Sprint 010-B | 20 | Guardian intelligence |
| Sprint 010-C | 10 | Dashboard + learning |
| Sprint 010-D | 22 | Auth + audit |
| **Total** | **~1022** | |

---

## 9. Sprint History

| Sprint | Focus | Merged PRs |
|---|---|---|
| Sprint 001 | Project setup, README, ADR | Initial |
| Sprint 002 | Investment Policy engine | — |
| Sprint 003 | Decision Journal | — |
| Sprint 004 | Guardian monitoring | — |
| Sprint 005 | Automation orchestration | Corrective PRs |
| Sprint 006 | AI Committee foundation | — |
| Sprint 007/008 | Backup, notifications, health | Multiple |
| Sprint 009 | Portfolio, policy enrichment, ideas, import | #78-#81 |
| Sprint 010 | Committee bridge, Guardian intel, dashboard, auth | #82-#85 |
