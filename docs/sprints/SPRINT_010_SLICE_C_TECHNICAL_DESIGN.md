# Sprint 010 Slice C — Technical Design
# Wealth Dashboard + Learning Loop

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 010 Slice A (Committee Bridge): DONE — merged 2026-08-10 (972bf24, PR #82)
> Sprint 010 Slice B (Guardian Intelligence): DONE — merged 2026-08-10 (414e38f, PR #83)
> Sprint 010 Slice C (Wealth Dashboard + Learning Loop): DESIGN ONLY
>
> This document defines the detailed architecture for the Wealth Dashboard
> API and the Decision Learning Loop.

---

## 1. Objective

Provide the Owner with a single read-only API endpoint that aggregates the
complete wealth picture, and implement the post-decision learning loop to
close the feedback cycle between decisions and outcomes.

**This is NOT:**
- Frontend/UI implementation
- Trading or execution
- Broker integration

**This IS:**
- Read-only dashboard API aggregating all Sprint 002-010 systems
- Decision review scheduling and outcome tracking
- Learning loop records for decision quality feedback

---

## 2. What Slice C Builds On

### 2.1 Existing Systems Consumed (Read-Only)

| System | Tables Queried | Data Extracted |
|---|---|---|
| Portfolio (Sprint 009-A) | positions, cash_balances, accounts, assets, fx_rates | Net worth, allocation, currency breakdown |
| Policy (Sprint 002 + 009-B) | investment_policy_versions, policy_capital_buckets, policy_rules | Compliance status, bucket targets |
| Guardian (Sprint 004 + 010-B) | guardian_events, guardian_check_confirmed | Risk status, active events |
| Ideas (Sprint 009-C) | investment_ideas | Idea counts by status |
| Committee (Sprint 006 + 010-A) | committee_review_requests, committee_sessions | Pending reviews |
| Decisions (Sprint 003) | decisions, decision_drafts | Pending decisions |
| Activity | transactions, guardianevaluation_runs | Recent activity feed |

### 2.2 New Tables

| Table | Purpose |
|---|---|
| `decision_reviews` | Learning loop: scheduled reviews + outcomes |

### 2.3 Modified Tables

| Table | Change |
|---|---|
| `decision_confirmed_snapshots` | + review_30d, review_90d, review_1yr, review_outcome columns |

---

## 3. Wealth Dashboard API

### 3.1 Endpoint

```
GET /api/dashboard
Authorization: READ
Response: DashboardSnapshot
```

### 3.2 Response Schema

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
    total_value: str              # Decimal string in base currency
    by_currency: dict[str, str]  # Currency → value
    by_account_type: dict[str, str]
    as_of: datetime

class Allocation(BaseModel):
    by_asset_class: dict[str, AllocationEntry]
    by_bucket: dict[str, AllocationEntry]
    by_currency: dict[str, AllocationEntry]

class AllocationEntry(BaseModel):
    value: str
    percentage: str               # e.g. "65.50"

class PolicyCompliance(BaseModel):
    overall_status: str           # 'compliant','warning','breach'
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
    concentration_risk: str       # 'low','medium','high','critical'
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
    items: list[ActivityItem]     # Last 20 items

class ActivityItem(BaseModel):
    type: str
    title: str
    description: str
    occurred_at: datetime
```

### 3.3 Calculation Rules

#### 3.3.1 Net Worth

```sql
-- Total portfolio value from latest positions
SELECT COALESCE(SUM(p.market_value), 0)
FROM positions p
JOIN accounts a ON p.account_id = a.id
JOIN portfolios pf ON a.portfolio_id = pf.id
WHERE pf.household_id = :hid AND p.is_latest = TRUE;

-- Plus latest cash balances
SELECT COALESCE(SUM(cb.amount), 0)
FROM cash_balances cb
JOIN accounts a ON cb.account_id = a.id
JOIN portfolios pf ON a.portfolio_id = pf.id
WHERE pf.household_id = :hid AND cb.is_latest = TRUE;
```

**Currency handling**: Values stored in native currencies. Dashboard reports
in base currency (HouseholdProfile.base_currency). Cross-currency conversion
uses most recent FX rate before or at current timestamp from `fx_rates`.

If no FX rate exists for a currency pair: flag as "unconverted" and report
the currency-breakdown section in native currency.

#### 3.3.2 Allocation

Computes three views from the same position data:

| View | Grouping | Source |
|---|---|---|
| by_asset_class | asset.asset_class (nullable → "Unclassified") | assets JOIN positions |
| by_bucket | account.capital_bucket | accounts JOIN positions |
| by_currency | asset.currency | assets JOIN positions |

Each entry: `value` (absolute) and `percentage` (of total).

#### 3.3.3 Policy Compliance

Compares actual portfolio state against active policy:

1. Load active policy version's `policy_capital_buckets`
2. Compute actual bucket % from position data (same as allocation.by_bucket)
3. For each bucket with min/max bounds:
   - `actual_pct < min_pct` → WARNING, drift = min_pct - actual_pct
   - `actual_pct > max_pct` → WARNING, drift = actual_pct - max_pct
4. Count rule violations from `guardian_events` where as_of_date is recent (≤ 7 days)
5. Overall status:
   - `compliant`: no drifts and no violations
   - `warning`: any warnings
   - `breach`: any critical severity events active

#### 3.3.4 Risk Summary

- `concentration_risk`: Derived from max single position % (from allocation data)
  - ≤ 15% → 'low', ≤ 25% → 'medium', ≤ 40% → 'high', > 40% → 'critical'
- `active_guardian_events`: COUNT of guardian_events (not acknowledged)
- `newest_guardian_event_at`: MAX(detected_at) from guardian_events

#### 3.3.5 Pending Decisions

Queries `decisions WHERE status = 'draft'` with their `decision_drafts` titles.
Limited to 5 most recent.

#### 3.3.6 Idea Summary

Simple COUNT queries on `investment_ideas` grouped by status for the household.

#### 3.3.7 Activity Feed

Union of recent events across systems, last 20 items:

| Type | Source | Title format |
|---|---|---|
| position_import | positions WHERE is_latest | "N positions imported" |
| transaction | transactions ORDER BY executed_at | "{type} {quantity} {symbol}" |
| guardian_event | guardian_events ORDER BY detected_at | "{check_type}: {detail}" |
| committee_report | committee_sessions WHERE status='completed' | "Committee: {title}" |
| decision | decisions ORDER BY created_at | "Decision: {draft.title}" |

### 3.4 No Caching in V1

Per OD-10-1 (Tiered approach): Dashboard computes live for real-time data
(net worth, allocation, compliance, risks). Historical/analytics caching
is deferred to a future sprint.

---

## 4. Learning Loop

### 4.1 Schema

```
decision_reviews
├── id (UUID PK)
├── decision_id (FK → decisions, RESTRICT)
├── investment_idea_id (FK → investment_ideas, nullable, SET NULL)
├── review_type (TEXT: '30d', '90d', '1yr', 'manual')
├── scheduled_at (DATE, NOT NULL)
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

**Constraints:**
- `ck_decision_reviews_type`: CHECK review_type IN ('30d','90d','1yr','manual')
- `uq_decision_reviews_decision_type`: UNIQUE(decision_id, review_type)
- FK: decision_id → decisions(id) RESTRICT
- FK: investment_idea_id → investment_ideas(id) SET NULL

### 4.2 Extended Snapshot Columns

| Column | Type | Purpose |
|---|---|---|
| `review_30d` | DATE, nullable | Scheduled 30-day review date |
| `review_90d` | DATE, nullable | Scheduled 90-day review date |
| `review_1yr` | DATE, nullable | Scheduled 1-year review date |
| `review_outcome` | TEXT, nullable | Free-text outcome notes |

These columns are added to `decision_confirmed_snapshots` (already has
`review_date` and `review_trigger` from Sprint 003).

### 4.3 Workflow

```
Owner confirms Decision
       ↓
DecisionConfirmedSnapshot created
       ↓
System auto-schedules reviews per OD-10-2:
  - High-impact decisions: 30d, 90d, 1yr reviews auto-created
  - Low-impact decisions: Owner optionally schedules
       ↓
decision_reviews rows created (status: pending)
       ↓
Automation worker (Sprint 005) detects due reviews
       ↓
Notification dispatched to Owner
       ↓
Owner opens review → records:
  - outcome_notes
  - actual_return_pct (if applicable)
  - policy_compliant (was decision within policy?)
  - lessons_learned
       ↓
Review marked complete (completed_at = now())
```

### 4.4 High-Impact vs Low-Impact Classification

Per OD-10-2 (Tiered optional model):

| Classification | Threshold | Review Behavior |
|---|---|---|
| High-impact | proposed_allocation_pct > 5% of portfolio OR amount > threshold | Auto-schedule 30d, 90d, 1yr reviews |
| Low-impact | Below threshold | Reviews optional; Owner schedules manually |

The threshold is configurable. Default: 5% of portfolio value.

Implementation: When `decision_confirmed_snapshots` is created, check the
associated `investment_idea.proposed_allocation_pct`. If > threshold,
auto-create 3 `decision_reviews` rows (30d, 90d, 1yr) with `scheduled_at`
computed from `decision_date + N days`.

If no investment_idea linked, classify as low-impact (manual scheduling only).

---

## 5. Database Impact

### 5.1 Migration: 0024_dashboard_learning

| Change | Table | Detail |
|---|---|---|
| CREATE | `decision_reviews` | New table with CHECK + UNIQUE + 2 FKs |
| ADD | `decision_confirmed_snapshots` | + review_30d, review_90d, review_1yr, review_outcome |

Additive only. Fully reversible.

### 5.2 No New Tables for Dashboard

The dashboard is a read-only service layer. All data comes from existing tables.
No dashboard-specific tables, caches, or materialized views in V1.

---

## 6. API Design

### 6.1 New Endpoints

| Method | Path | Classification | Description |
|---|---|---|---|
| GET | /api/dashboard | READ | Wealth dashboard snapshot |
| POST | /api/reviews | OWNER_MUTATION | Schedule a manual review |
| GET | /api/reviews/due | READ | List due reviews |
| GET | /api/reviews/{id} | READ | Review detail |
| PATCH | /api/reviews/{id} | OWNER_MUTATION | Complete review (record outcomes) |
| GET | /api/decisions/{id}/reviews | READ | All reviews for a decision |

### 6.2 Review Completion Schema

```python
class ReviewCompletionRequest(BaseModel):
    outcome_notes: str | None = None
    actual_return_pct: str | None = None    # Decimal string
    policy_compliant: bool | None = None
    lessons_learned: str | None = None
```

---

## 7. Service Layer Design

### 7.1 Dashboard Service

```python
# apps/api/services/dashboard_service.py

def build_dashboard(session: Session, household_id: UUID) -> DashboardSnapshot:
    """Assemble dashboard from all existing systems. Read-only."""
    positions = _load_latest_positions(session, household_id)
    cash = _load_latest_cash_balances(session, household_id)
    policy = _load_active_policy(session, household_id)
    guardian = _load_guardian_status(session, household_id)
    ideas = _count_ideas_by_status(session, household_id)
    decisions = _load_pending_decisions(session, household_id)
    activity = _load_activity_feed(session, household_id)

    net_worth = _compute_net_worth(positions, cash, session)
    allocation = _compute_allocation(positions)
    compliance = _compute_compliance(positions, policy)
    risks = _compute_risks(positions, guardian)

    return DashboardSnapshot(
        net_worth=net_worth, allocation=allocation,
        policy_compliance=compliance, risks=risks,
        pending_decisions=decisions, ideas=ideas,
        recent_activity=activity,
    )
```

### 7.2 Review Service

```python
# apps/api/services/review_service.py

def schedule_reviews_for_decision(
    session: Session, decision_id: UUID, snapshot: DecisionConfirmedSnapshot,
) -> list[DecisionReview]:
    """Auto-schedule reviews based on decision impact."""
    idea = _load_linked_idea(session, snapshot.investment_idea_id)
    is_high_impact = _is_high_impact(idea, session)

    if not is_high_impact:
        return []  # Owner schedules manually for low-impact

    return _create_review_rows(session, decision_id, [
        ("30d", snapshot.decision_date + timedelta(days=30)),
        ("90d", snapshot.decision_date + timedelta(days=90)),
        ("1yr", snapshot.decision_date + timedelta(days=365)),
    ])
```

---

## 8. Test Strategy

### 8.1 Migration Tests (4 tests)

| Test | What it proves |
|---|---|
| decision_reviews table exists | Migration applied |
| decision_reviews CHECK constraint | Invalid review_type rejected |
| decision_confirmed_snapshots new columns | Columns exist |
| Migration reversible | Downgrade clean |

### 8.2 Dashboard Tests (10 tests)

| Test | What it proves |
|---|---|
| Net worth computed from positions + cash | Aggregation correct |
| Net worth empty portfolio = 0 | Edge case |
| Allocation by asset_class correct | Grouping logic |
| Allocation by bucket correct | Capital bucket mapping |
| Policy compliance within bounds | No drift = compliant |
| Policy compliance exceeds max | Drift detected = warning |
| Risk summary with no events | Empty risks = low |
| Risk summary with critical event | Concentration = critical |
| Pending decisions listed | Decision query correct |
| Activity feed returns recent items | Union query correct |

### 8.3 Learning Loop Tests (6 tests)

| Test | What it proves |
|---|---|
| Schedule reviews for high-impact decision | 3 rows created |
| No auto-schedule for low-impact decision | 0 rows created |
| Manual review scheduling works | POST creates row |
| Complete review with outcomes | PATCH updates row |
| Duplicate review_type per decision rejected | UNIQUE constraint |
| Review survives idea deletion | SET NULL FK |

### 8.4 Total: ~20 tests

---

## 9. File List

### 9.1 New Files

| File | Purpose |
|---|---|
| `migrations/versions/0024_dashboard_learning.py` | Migration |
| `apps/api/services/dashboard_service.py` | Dashboard aggregation |
| `apps/api/services/review_service.py` | Learning loop logic |
| `apps/api/routers/dashboard.py` | Dashboard + review endpoints |
| `apps/api/dashboard_schemas.py` | Pydantic schemas |
| `tests/test_dashboard_learning.py` | Integration tests |

### 9.2 Modified Files

| File | Change |
|---|---|
| `apps/api/models.py` | + DecisionReview model, + snapshot columns |
| `apps/api/main.py` | Register dashboard router |
| `apps/api/mutation_gate.py` | EXPECTED_HEAD → 0024 |
| `apps/api/services/health_service.py` | EXPECTED_HEAD → 0024 |
| `tests/api/test_households.py` | + decision_reviews table |
| All HEAD_REVISION files | 0023 → 0024 |

---

## 10. Owner Decisions (Pending)

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| OD-10-C-1 | High-impact threshold for auto-review | 5% of portfolio | Reasonable for family office |
| OD-10-C-2 | Activity feed: last N items | 20 items | Balanced: informative without overwhelming |
| OD-10-C-3 | FX rate gap handling | Flag as unconverted | Transparent; no silent assumption |
| OD-10-C-4 | Dashboard response size | Full snapshot (no pagination) | Single-owner dashboard, small portfolio |

---

## 11. Estimated Scope

| Component | Complexity | Lines | Tests |
|---|---|---|---|
| Migration | Low | ~80 | 4 |
| Dashboard schemas | Low | ~150 | 0 |
| Dashboard service | Medium | ~250 | 10 |
| Review service | Medium | ~150 | 6 |
| Router | Low | ~80 | 0 |
| Model changes | Low | ~60 | 0 |
| HEAD_REVISION sweep | Mechanical | ~15 files | 0 |
| **Total** | | **~770 lines** | **~20 tests** |

---

## 12. Absolute Exclusions

- No trading, order placement, or execution
- No broker/bank API connections
- No real financial credentials
- No automatic investment decisions
- No frontend implementation
- No Slice D (Security + Notifications)
