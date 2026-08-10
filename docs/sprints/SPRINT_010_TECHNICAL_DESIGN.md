# Sprint 010 — Technical Design
# AI Wealth Intelligence

> **STATUS: SPRINT 010 COMPLETE — ALL 4 SLICES MERGED**
>
> Slice A (Committee Bridge): **DONE** — 2026-08-10 (972bf24, PR #82)
> Slice B (Guardian Intelligence): **DONE** — 2026-08-10 (414e38f, PR #83)
> Slice C (Dashboard + Learning): **DONE** — 2026-08-10 (558dbac, PR #84)
> Slice D (Auth, Audit & Escalation): **DONE** — 2026-08-10 (ba5054b, PR #85)
>
> This document defines the architecture for transforming CompoundOS from
> a wealth data system into an AI-assisted wealth decision system.

---

## 1. Executive Summary

Sprint 010 is the integration sprint. Sprint 009 built the data foundation
(portfolio, policy, ideas, import). Sprint 010 wires them together into
workflows that deliver AI-assisted intelligence while preserving absolute
Owner authority.

### 1.1 What Sprint 010 Builds

| Module | What it does | Existing foundation |
|---|---|---|
| Committee Integration | Wire ideas → evidence → review → recommendation | Committee sessions (006), Ideas (009-C) |
| Guardian Intelligence | Wire policy + portfolio → drift detection → alerts | Guardian checks (004), Policy rules (009-B), Positions (009-A) |
| Wealth Dashboard | Owner-facing view: net worth, allocation, policy compliance, risks | Portfolio (009-A), Policy (002, 009-B) |
| Learning Loop | Decision → outcome review → learning record | Decisions (003), Ideas (009-C) |
| Notification Wiring | Guardian events + Committee outcomes → notifications | Notifications (007/008), Guardian events (004) |

### 1.2 What Sprint 010 Does NOT Build

- No trading or order execution
- No broker API connections
- No credential storage
- No automatic rebalancing
- No AI-initiated decisions
- No frontend (UI scope defined, implementation in separate sprint)

---

## 2. Architecture Overview

### 2.1 System Integration Map

```
                          ┌─────────────────┐
                          │   Wealth Dashboard│
                          │   (Read-only)    │
                          └────────┬────────┘
                                   │ queries
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼────────┐  ┌───────▼───────┐  ┌────────▼────────┐
     │  Guardian Engine │  │   Committee   │  │  Decision Room  │
     │  (Sprint 004)    │  │   (Sprint 006)│  │  (Sprint 003)   │
     │                  │  │               │  │                 │
     │  Policy + Port   │  │  Evidence →   │  │  Idea → Review  │
     │  → Drift → Alert │  │  Report →     │  │  → Decision →   │
     │                  │  │  Outcome      │  │  Learning       │
     └────────┬────────┘  └───────┬───────┘  └────────┬────────┘
              │                   │                    │
              │         ┌─────────▼─────────┐          │
              │         │   Evidence        │          │
              │         │   Pipeline        │          │
              │         │   (New in 010)    │          │
              │         └─────────┬─────────┘          │
              │                   │                    │
     ┌────────▼───────────────────▼────────────────────▼────────┐
     │                    Data Foundation (Sprint 009)          │
     │  assets · positions · cash_balances · transactions      │
     │  accounts · fx_rates · data_sources                     │
     │  policy_capital_buckets · policy_rules                  │
     │  investment_ideas · idea_status_history                 │
     └──────────────────────────────────────────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │  Notifications  │
                          │  (Sprint 007/8) │
                          │  Email + Phone  │
                          │  (future)       │
                          └─────────────────┘
```

### 2.2 Data Flow

```
Portfolio Data (0018)
       +
Policy Rules (0019-B)
       ↓
Guardian Evaluation (004)
       ↓
Guardian Events → Notification Events → Owner Alert
       ↓
Investment Idea (009-C)
       ↓
Evidence Pipeline (010 — new)
       ↓
Committee Session (006)
       ↓
Committee Report + Outcome
       ↓
Decision Journal (003) → Decision Confirmed → Learning Record (010 — new)
```

---

## 3. Module Designs

---

### 3.1 AI Investment Committee Integration

#### 3.1.1 Current State

The Committee (Sprint 006) has:
- `committee_sessions`: draft→queued→running→completed/failed
- `committee_evidence_items`: structured facts with provenance
- `committee_reports`: immutable, 7 perspectives + synthesis
- `committee_outcomes`: append-only accept/reject/defer

Investment Ideas (Sprint 009-C) have:
- 6-status lifecycle: draft→under_review→approved/rejected/deferred/cancelled
- Auto-history trigger
- Policy version linkage
- Decision bridge (investment_idea_id FK on decisions)

**Gap**: Ideas and Committee sessions are not connected. An idea cannot
trigger committee review automatically. Evidence collection is manual.

#### 3.1.2 Bridge Design

Create a linkage table:

```
committee_review_requests
├── id (UUID PK)
├── investment_idea_id (FK → investment_ideas, RESTRICT)
├── committee_session_id (FK → committee_sessions, nullable, SET NULL)
├── requested_by (TEXT — 'owner' only in V1)
├── requested_at (TIMESTAMPTZ)
├── status (TEXT: 'pending','in_progress','completed')
├── notes (TEXT, nullable)
└── created_at (TIMESTAMPTZ)
```

**Workflow**:
1. Owner submits Investment Idea → status transitions to `under_review`
2. Owner clicks "Request Committee Review" → creates `committee_review_request`
3. Automation worker (Sprint 005) detects pending review → creates `committee_session`
4. Evidence pipeline populates session with evidence items
5. Committee executes → produces `committee_report` + `committee_outcome`
6. Review request status → `completed`
7. Owner reviews outcome → approves/rejects/deferrs idea

#### 3.1.3 Evidence Pipeline (New)

The existing evidence pipeline (Sprint 006) supports 6 source types. Sprint
010 adds 3 new source types:

| Source Type | Data Extracted | Privacy Rule |
|---|---|---|
| `portfolio_position` | Position summaries by asset class | No individual holdings exposed |
| `policy_bucket` | Capital bucket targets vs actual | Aggregated only |
| `investment_idea` | Idea thesis, allocation, risks | Full idea visible to committee |

**Evidence extraction rules**:
- Positions: aggregate by asset_type, show total value per category, NOT individual positions
- Policy: show bucket targets and actual allocation percentages
- Ideas: show full thesis and proposed allocation
- NEVER expose: individual account numbers, broker account IDs, exact holdings

#### 3.1.4 AI Authority Matrix (Extended)

| Action | AI Agent | Owner | Enforcement |
|---|---|---|---|
| Read portfolio data (aggregated) | Allowed | Allowed | Evidence pipeline aggregation |
| Generate committee report | Allowed | Allowed | Immutable report |
| Create recommendation | Allowed | Allowed | Labeled as AI-generated |
| Request committee review | NOT allowed | Required | OWNER_MUTATION endpoint |
| Approve investment idea | NOT allowed | Required | status→approved Owner only |
| Confirm decision | NOT allowed | Required | DecisionConfirmedSnapshot |
| Place trade | NEVER allowed | Required | Not in Sprint 010 |

---

### 3.2 Guardian Intelligence

#### 3.2.1 Current State

Guardian (Sprint 004) has:
- Check definitions: drift, category_exposure, staleness
- Evaluation runs: schedule-based, skip logic for missing data
- Events: violations with severity (info/warning/critical)
- `evaluate_core`: transaction-neutral, used by worker and HTTP

Policy enrichment (Sprint 009-B) added:
- `policy_capital_buckets`: target/min/max per bucket
- `policy_rules`: extensible constraints with severity

**Gap**: Guardian checks are limited to `drift`, `category_exposure`, `staleness`.
The new policy rules and portfolio positions are not consumed by Guardian.

#### 3.2.2 Guardian Check Extensions

Add 5 new check types to `ck_guardian_checks_type`:

| Check Type | What it monitors | Data Source | Severity |
|---|---|---|---|
| `capital_bucket_drift` | Actual bucket % vs policy target | policy_capital_buckets + positions | policy rule |
| `single_position_concentration` | Any position > max_single_position_pct | positions + policy_rules | policy rule |
| `sector_concentration` | Any sector > max_sector_concentration_pct | positions (via assets.sector) + policy_rules | policy rule |
| `exploration_capital_limit` | EXPLORATION bucket > policy max | policy_capital_buckets + positions | critical |
| `data_quality_staleness` | Position data older than N hours | positions.observed_at | warning |

**Check types must be added to the CHECK constraint in migration.** Existing
constraint: `check_type IN ('drift','category_exposure','staleness')`.
New: extend to 8 types.

#### 3.2.3 Policy-Backed Thresholds

Guardian checks read thresholds from `policy_rules`:

| Rule Type | Guardian Check | Parameter |
|---|---|---|
| `max_single_position_pct` | `single_position_concentration` | threshold = rule_value |
| `max_sector_concentration_pct` | `sector_concentration` | threshold = rule_value |
| `max_drawdown_pct` | (future) | threshold = rule_value |
| `min_cash_reserve_pct` | `capital_bucket_drift` (CASH_RESERVE) | threshold = rule_value |
| `exploration_capital_limit` | `exploration_capital_limit` | threshold = rule_value |

#### 3.2.4 Guardian Authority (Unchanged)

Sprint 010 preserves existing Guardian authority:

| Severity | Action | Automatic? |
|---|---|---|
| info | Log only | Yes |
| warning | Notification dispatch + UI badge | Yes (notification), No (UI → Owner) |
| critical | Notification + BLOCK_RECOMMENDATION | Yes (notification), No (no auto-sell) |
| NEVER | Auto-sell, auto-rebalance, auto-trade | No |

---

### 3.3 Wealth Dashboard (API Layer)

#### 3.3.1 Purpose

Provide a single read-only endpoint that aggregates the Owner's complete
wealth picture. Frontend implementation is a separate sprint — Sprint 010
builds the API only.

#### 3.3.2 Dashboard Endpoint

```
GET /api/dashboard
Authorization: READ
Response: DashboardSnapshot
```

**DashboardSnapshot schema**:

```python
class DashboardSnapshot(BaseModel):
    net_worth: NetWorth
    allocation: Allocation
    policy_compliance: PolicyCompliance
    risks: RiskSummary
    pending_decisions: list[PendingDecision]
    ideas: IdeaSummary
    recent_activity: ActivityFeed

class NetWorth(BaseModel):
    total_value: str           # Decimal string in base currency
    by_currency: dict[str, str]  # Currency → value
    by_account_type: dict[str, str]  # account_type → value
    as_of: datetime

class Allocation(BaseModel):
    by_asset_class: dict[str, AllocationEntry]
    by_bucket: dict[str, AllocationEntry]  # CORE, EXPLORATION, etc.
    by_currency: dict[str, AllocationEntry]

class AllocationEntry(BaseModel):
    value: str
    percentage: str  # Decimal string, e.g. "65.50"

class PolicyCompliance(BaseModel):
    overall_status: str  # 'compliant','warning','breach'
    bucket_drifts: list[BucketDrift]
    rule_violations: list[RuleViolation]

class BucketDrift(BaseModel):
    bucket_name: str
    target_pct: str
    actual_pct: str
    drift_pct: str
    severity: str

class RuleViolation(BaseModel):
    rule_type: str
    description: str
    severity: str
    detected_at: datetime

class RiskSummary(BaseModel):
    concentration_risk: str  # 'low','medium','high','critical'
    active_guardian_events: int
    newest_guardian_event_at: datetime | None

class PendingDecision(BaseModel):
    decision_id: UUID
    title: str
    investment_idea_id: UUID | None
    status: str
    created_at: datetime

class IdeaSummary(BaseModel):
    total: int
    draft: int
    under_review: int
    approved: int
    rejected: int

class ActivityFeed(BaseModel):
    items: list[ActivityItem]  # Last 20 items

class ActivityItem(BaseModel):
    type: str  # 'position_import','transaction','guardian_event','committee_report','decision'
    title: str
    description: str
    occurred_at: datetime
```

#### 3.3.3 Calculation Rules

- **Net worth**: Sum of all latest positions (quantity × market_price) + latest cash balances, converted to base currency via most recent FX rate
- **Allocation**: Group positions by asset.asset_class, asset.sector, account.capital_bucket
- **Policy compliance**: Compare actual bucket percentages against policy_capital_buckets targets; check positions against policy_rules thresholds
- **Risks**: Count active guardian_events (not acknowledged), highest concentration risk
- **No caching in V1** — every dashboard load computes from live DB

---

### 3.4 Learning Loop

#### 3.4.1 Purpose

Close the feedback loop: Decision → Outcome → Learning. The Owner makes
decisions, and the system helps review outcomes to improve future decisions.

#### 3.4.2 Schema

```
decision_reviews
├── id (UUID PK)
├── decision_id (FK → decisions, RESTRICT)
├── investment_idea_id (FK → investment_ideas, nullable, SET NULL)
├── review_type (TEXT: '30d','90d','1yr','manual')
├── scheduled_at (DATE)
├── completed_at (TIMESTAMPTZ, nullable)
├── outcome_notes (TEXT, nullable)
│     Owner's reflection on the decision outcome
├── actual_return_pct (NUMERIC(8,2), nullable)
│     If applicable, what was the actual return
├── policy_compliant (BOOLEAN, nullable)
│     Was the decision compliant with then-active policy
├── lessons_learned (TEXT, nullable)
│     Structured learning for future decisions
├── created_at (TIMESTAMPTZ)
└── updated_at (TIMESTAMPTZ)
```

**Constraints**:
- `ck_decision_reviews_type`: CHECK review_type IN ('30d','90d','1yr','manual')
- `uq_decision_reviews_decision_type`: UNIQUE(decision_id, review_type)
- FK: decision_id → decisions(id) RESTRICT

#### 3.4.3 Workflow

1. Owner confirms a Decision → DecisionConfirmedSnapshot created
2. System schedules reviews: review_30d, review_90d, review_1yr (dates in snapshot)
3. Automation worker detects due review → creates notification
4. Owner opens review → records outcome notes, lessons learned
5. Learning record preserved alongside original decision

#### 3.4.4 Post-Decision Review Fields on Snapshot

Extend `decision_confirmed_snapshots` (already has review_date, review_trigger):

| New Column | Type | Purpose |
|---|---|---|
| `review_30d` | DATE, nullable | Scheduled 30-day review |
| `review_90d` | DATE, nullable | Scheduled 90-day review |
| `review_1yr` | DATE, nullable | Scheduled 1-year review |
| `review_outcome` | TEXT, nullable | Free-text outcome notes (filled during review) |

These columns are already designed in Sprint 009 TD §11.2. Sprint 010
implements them.

---

### 3.5 Notification Architecture

#### 3.5.1 Current State

Notifications (Sprint 007/008) have:
- `notification_events`: fingerprint-based dedup, delivery status tracking
- `notification_preferences`: quiet hours, enabled sources/severities
- Source types: guardian, committee, automation, backup, health

#### 3.5.2 Sprint 010 Notification Wiring

Wire existing notification infrastructure to new events:

| Event Source | Trigger | Severity | Suppression Rule |
|---|---|---|---|
| Guardian `drift` violation | GuardianEvaluationRun completes | From policy_rule.severity | Fingerprint dedup |
| Guardian `concentration` violation | Same | critical | Never suppress |
| Committee report completed | CommitteeSession status→completed | info | Once per session |
| Investment idea needs review | Idea status→under_review | info | Once per idea |
| Post-decision review due | decision_reviews.scheduled_at ≤ today | info | Daily reminder |
| Data staleness detected | Guardian check data_quality_staleness | warning | Once per 24h |

#### 3.5.3 Future Escalation (Design Only)

```
Level 1: In-app notification (current)
Level 2: Email (future — SMTP/API integration)
Level 3: Phone/SMS (future — Twilio/WhatsApp)
```

Sprint 010 defines the escalation data model but does NOT implement
delivery channels beyond the existing notification infrastructure.

```
notification_escalation_rules
├── id (UUID PK)
├── event_severity (TEXT: 'critical' only in V1)
├── escalate_after (INTERVAL — e.g. '24 hours')
├── escalation_level (INT: 1=email, 2=sms)
├── enabled (BOOLEAN)
└── created_at (TIMESTAMPTZ)
```

No implementation in Sprint 010.

---

### 3.6 Security Boundary

#### 3.6.1 Authentication Design (SEC-002)

Sprint 010 defines the authentication architecture. No implementation yet.

```
Owner Authentication:
├── Local API key (V1 — Sprint 010)
│   └── Single API key in environment variable
│       COMPOUNDOS_API_KEY=<random-64-char>
│       All OWNER_MUTATION endpoints require X-API-Key header
│
├── Session-based auth (V2 — future)
│   └── JWT with refresh tokens
│
└── OAuth2 (V3 — future, for broker connections)
    └── Read-only scopes only
```

#### 3.6.2 Endpoint Classification

Sprint 010 classifies every endpoint. This is documentation + middleware
design — not endpoint-by-endpoint implementation (that's SEC-002
implementation sprint).

| Classification | HTTP Methods | Example Endpoints | Auth Required |
|---|---|---|---|
| READ | GET | /api/dashboard, /api/positions | None in V1 (local dev) |
| OWNER_MUTATION | POST, PATCH | /api/import/*, /api/investment-ideas/* | API key |
| SYSTEM_INTERNAL | POST | Worker-only endpoints | Shared secret |
| PUBLIC | GET | /health, /api/health | None |

#### 3.6.3 Hard Boundaries

- No credentials for financial providers (brokers, banks)
- No API keys in Git (environment variables only)
- No credential storage in database
- Repository remains PUBLIC during Sprint 010 (SEC-001: P0 gate
  before real financial account integration — NOT reached yet)

---

## 4. Database Impact

### 4.1 New Tables

| Table | Migration | Purpose |
|---|---|---|
| `committee_review_requests` | 0022 | Idea → Committee bridge |
| `decision_reviews` | 0022 | Learning loop records |
| `notification_escalation_rules` | 0022 | Escalation config (schema only) |

### 4.2 Modified Tables

| Table | Change | Details |
|---|---|---|
| `guardian_checks` | Extend CHECK | Add 5 new check_types |
| `committee_evidence_items` | Extend CHECK | Add 3 new source_types |
| `decision_confirmed_snapshots` | Add columns | review_30d, review_90d, review_1yr, review_outcome |
| `notification_events` | Extend CHECK | Add 'investment_idea' source |

### 4.3 Migration: 0022_ai_intelligence_foundation

Additive, reversible. No destructive changes.

### 4.4 No New Tables for Dashboard

The dashboard is a read-only API layer. No persistence beyond what already
exists in Sprints 002-009.

---

## 5. API Design

### 5.1 New Endpoints

| Method | Path | Classification | Sprint |
|---|---|---|---|
| GET | /api/dashboard | READ | 010 |
| POST | /api/ideas/{id}/request-review | OWNER_MUTATION | 010 |
| GET | /api/reviews | READ | 010 |
| POST | /api/reviews/{id}/complete | OWNER_MUTATION | 010 |
| GET | /api/reviews/due | READ | 010 |
| GET | /api/guardian/status | READ | 010 |

### 5.2 Extended Endpoints

| Method | Path | Change |
|---|---|---|
| GET | /api/committee/sessions | Add investment_idea_id filter |
| POST | /api/committee/sessions | Accept investment_idea_id, auto-create evidence |

### 5.3 No New Import/Export Endpoints

Sprint 010 does not modify the import pipeline from Slice 009-D.

---

## 6. Test Strategy

### 6.1 Schema Tests

| Test | What it proves |
|---|---|
| Migration 0022 creates all tables | Table existence |
| guardian_checks CHECK accepts new types | Constraint extended correctly |
| committee_evidence_items CHECK accepts new types | Evidence expansion |
| decision_reviews uniqueness per type | No duplicate review types per decision |
| Migration is fully reversible | Downgrade drops all cleanly |

### 6.2 Integration Tests

| Module | Tests | Scope |
|---|---|---|
| Committee Bridge | 8 | Create review request, link to session, status lifecycle, duplicate prevention |
| Evidence Pipeline | 6 | Extract positions aggregated, policy bucket data, idea thesis; privacy rules enforced |
| Guardian Intelligence | 10 | Bucket drift detection, concentration check, staleness, policy-backed thresholds, new check types |
| Dashboard API | 8 | Net worth calculation, allocation, policy compliance, risks, pending decisions, activity feed |
| Learning Loop | 6 | Schedule reviews, complete review, history preservation, decision linkage |
| Notification Wiring | 5 | Guardian event→notification, committee report→notification, review due→notification, dedup, suppression |
| Security | 4 | READ endpoint no auth, OWNER_MUTATION requires API key, SYSTEM_INTERNAL rejected from public |

### 6.3 AI Authority Tests

| Test | What it proves |
|---|---|
| Committee cannot approve idea | status transition blocked |
| Committee cannot confirm decision | DecisionConfirmedSnapshot requires owner |
| Committee recommendation is labeled | report includes 'ai_generated' flag |
| Evidence pipeline never exposes raw holdings | Aggregation verified |
| Policy rules cannot be changed by committee | Immutability trigger holds |

### 6.4 Estimated Test Count

**~47 tests** across all modules.

---

## 7. Implementation Slices

### Slice A — Committee Integration Bridge (8 tests)

- Migration: `committee_review_requests`
- Evidence pipeline extensions (new source_types, extraction rules)
- Bridge workflow: idea → review request → session → report → outcome
- AI authority tests

### Slice B — Guardian Intelligence (10 tests)

- Migration: extend guardian_checks CHECK
- New check types: capital_bucket_drift, concentration, staleness, exploration_limit
- Policy-backed thresholds from policy_rules
- Guardian → notification wiring

### Slice C — Dashboard API + Learning Loop (14 tests)

- Migration: `decision_reviews`, snapshot review columns
- GET /api/dashboard with full calculation logic
- Decision → review scheduling → completion workflow
- Review notifications

### Slice D — Security + Notification Wiring (15 tests)

- API key authentication middleware
- Endpoint classification
- Notification escalation rules (schema only)
- Cross-module notification wiring
- Full integration test suite

---

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Dashboard queries slow on large portfolios | Medium | Add indexes on is_latest + observed_at; V1 queries are simple aggregates |
| Guardian check proliferation → noisy alerts | Low | Fingerprint dedup, suppression rules, severity-based filtering |
| Committee evidence pipeline exposes sensitive data | Medium | Aggregation rules enforced at service layer; tests verify no raw data leaks |
| AI authority boundary confusion | Low | Clear matrix documented; trigger-level enforcement where possible |
| Review scheduling drifts over long periods | Low | Automation worker polls for due reviews; SLAs are informational |

---

## 9. Owner Decisions Required

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| OD-10-1 | Dashboard: compute on every load or cache? | Compute live (V1) | Simpler, always accurate for small portfolio |
| OD-10-2 | Review scheduling: mandatory or optional? | Optional | Owner chooses whether to schedule reviews |
| OD-10-3 | API key auth in Sprint 010 or defer? | Implement in Slice D | Security boundary before any real data |
| OD-10-4 | Committee: auto-trigger on idea submission or manual? | Manual trigger (Owner clicks) | Preserves deliberate decision process |
| OD-10-5 | Notification escalation: design only or implement email? | Design only | No email infrastructure in V1 |

---

## 10. Absolute Exclusions

- No trading, order placement, or execution
- No broker/bank API connections
- No real financial credentials
- No automatic rebalancing
- No AI-initiated decisions
- No frontend implementation
- No email/SMS delivery (design only)
- No real portfolio data in repository
- No credential storage in database
- Repository remains PUBLIC (SEC-001 gate not reached)

---

## 11. Sprint 010 Scope vs Future Sprints

| Capability | Sprint 010 | Future |
|---|---|---|
| Committee idea bridge | Schema + basic workflow | Automated evidence extraction, multi-idea sessions |
| Guardian intelligence | 5 new check types, policy-backed thresholds | Time-series drift tracking, ML-based anomaly detection |
| Dashboard | Read-only API, 6 data sections | Charts, trends, customizable layout (frontend sprint) |
| Learning loop | Review records, scheduling | Outcome-vs-prediction analytics, decision quality scoring |
| Notifications | Guardian + Committee wiring | Email, SMS, push notifications |
| Authentication | API key (middleware only) | JWT, OAuth2, session management |
| Broker connectors | Still NOT AUTHORIZED | Read-only connectors after SEC-001 (private repo) |

---

## 12. Estimated Effort

| Slice | Complexity | New Code | Tests |
|---|---|---|---|
| A — Committee Bridge | Medium | ~400 lines | 8 |
| B — Guardian Intelligence | Medium | ~350 lines | 10 |
| C — Dashboard + Learning | High | ~600 lines | 14 |
| D — Security + Notifications | Medium | ~400 lines | 15 |
| **Total** | | **~1,750 lines** | **~47 tests** |
