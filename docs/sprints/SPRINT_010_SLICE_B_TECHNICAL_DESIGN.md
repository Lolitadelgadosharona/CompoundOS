# Sprint 010 Slice B — Technical Design
# Guardian Intelligence

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 010 Slice A (Committee Bridge): DONE — merged 2026-08-10 (972bf24, PR #82)
> Sprint 010 Slice B (Guardian Intelligence): DESIGN ONLY
>
> This document defines the detailed architecture for Guardian Intelligence
> expansion in Sprint 010 Slice B.

---

## 1. Objective

Expand the Guardian engine (Sprint 004) with 5 new check types that consume
Sprint 009 data (portfolio positions, policy buckets, policy rules) and wire
Guardian events into the notification infrastructure (Sprint 007/008).

**This is NOT:**
- Automatic trading or rebalancing
- AI-driven policy modification
- Broker integration
- Credential storage

**This IS:**
- Policy-backed risk detection
- Data quality monitoring
- Concentration and drift alerts
- Notification wiring for Guardian events

---

## 2. Existing Foundation (What Slice B Builds On)

### 2.1 Guardian Engine (Sprint 004)

| Component | Model | Status |
|---|---|---|
| Check definitions | `guardian_checks` | 3 types: drift, category_exposure, staleness |
| Check drafts | `guardian_check_drafts` | Draft→Confirmed lifecycle |
| Check confirmed | `guardian_check_confirmed` | Immutable version snapshots |
| Evaluation runs | `guardian_evaluation_runs` | Schedule-based, skip logic |
| Events | `guardian_events` | Violations with severity |
| Engine | `evaluate_core` | Transaction-neutral, reusable |

### 2.2 Portfolio Schema (Sprint 009-A)

| Table | Relevant Columns |
|---|---|
| `positions` | quantity, market_value, account_id → account.capital_bucket, asset_id → asset.sector/asset_type, observed_at, is_latest |
| `accounts` | capital_bucket (CORE/EXPLORATION/CASH_RESERVE/RETIREMENT/OTHER) |
| `assets` | sector, asset_type, currency |

### 2.3 Policy Enrichment (Sprint 009-B)

| Table | Relevant Columns |
|---|---|
| `policy_capital_buckets` | bucket_name, target_pct, min_pct, max_pct (per version) |
| `policy_rules` | rule_type, rule_value, severity, enabled |

### 2.4 Notifications (Sprint 007/008)

| Component | Model |
|---|---|
| Events | `notification_events` (fingerprint dedup, delivery tracking) |
| Preferences | `notification_preferences` (quiet hours, source/severity filters) |

---

## 3. New Check Types

### 3.1 Check Type Catalog

| # | Check Type | What it monitors | Data Source | Default Severity |
|---|---|---|---|---|
| 1 | `capital_bucket_drift` | Actual bucket allocation % vs policy target | policy_capital_buckets + positions + accounts | From policy_rule.severity |
| 2 | `single_position_concentration` | Any single position > max_single_position_pct of portfolio | positions + policy_rules | From policy_rule.severity |
| 3 | `sector_concentration` | Any sector > max_sector_concentration_pct of portfolio | positions + assets.sector + policy_rules | From policy_rule.severity |
| 4 | `exploration_capital_limit` | EXPLORATION bucket total > exploration_capital_limit | policy_rules + positions + accounts | critical |
| 5 | `data_quality_staleness` | Positions with observed_at older than N hours | positions.observed_at | warning |

### 3.2 Check Type Details

#### 3.2.1 capital_bucket_drift

**Algorithm:**
1. Load active policy version's `policy_capital_buckets`
2. For each bucket, sum `position.market_value` where `account.capital_bucket == bucket_name` and `position.is_latest = TRUE`
3. Calculate total portfolio value
4. For each bucket: `actual_pct = (bucket_value / total_value) * 100`
5. Compare against `target_pct`, `min_pct`, `max_pct`
6. Fire event if actual_pct outside [min_pct, max_pct]

**Parameters stored in check draft:**
- `threshold_value`: not used (thresholds come from policy_capital_buckets)
- `target_category`: bucket_name to monitor (NULL = all buckets)

**Severity:** Derived from associated `policy_rule.severity`. Default: warning.

#### 3.2.2 single_position_concentration

**Algorithm:**
1. Load active policy version's `policy_rules` where `rule_type == 'max_single_position_pct'`
2. Calculate total portfolio value
3. For each position: `position_pct = (market_value / total_value) * 100`
4. If `position_pct > rule_value` → fire event
5. Report the top-N violating positions (max 5)

**Parameters:**
- `threshold_value`: overridden by policy_rule.rule_value
- `target_holding_category`: not used

**Severity:** From `policy_rule.severity`. Default: warning.

#### 3.2.3 sector_concentration

**Algorithm:**
1. Load active policy version's `policy_rules` where `rule_type == 'max_sector_concentration_pct'`
2. Group positions by `asset.sector` (JOIN assets on position.asset_id)
3. For each sector: `sector_pct = (sum(market_value) / total_value) * 100`
4. If `sector_pct > rule_value` → fire event

**Parameters:**
- `threshold_value`: overridden by policy_rule.rule_value
- `target_category`: specific sector to monitor (NULL = all sectors)

**Severity:** From `policy_rule.severity`. Default: warning.

#### 3.2.4 exploration_capital_limit

**Algorithm:**
1. Load active policy version's `policy_rules` where `rule_type == 'exploration_capital_limit'`
2. Sum `position.market_value` where `account.capital_bucket == 'EXPLORATION'`
3. If `exploration_value > rule_value` → fire critical event
4. This check runs regardless of policy_rule.enabled (always-on safety)

**Parameters:**
- `threshold_value`: overridden by policy_rule.rule_value
- `target_category`: 'EXPLORATION' (fixed)

**Severity:** Always critical. This is a safety rail, not a guideline.

#### 3.2.5 data_quality_staleness

**Algorithm:**
1. Load check draft's `staleness_days`
2. Query positions where `observed_at < now() - interval 'N hours'`
3. Count stale positions
4. If count > 0 → fire warning event listing stale positions

**Parameters:**
- `staleness_days`: hours threshold (stored as days in existing schema; convert)
- `threshold_value`: not used

**Severity:** warning. Stale data is a quality concern, not a risk violation.

---

## 4. Policy-Backed Thresholds

Guardian checks read thresholds from active policy rules at evaluation time:

| Policy Rule | Guardian Check | How threshold is used |
|---|---|---|
| `max_single_position_pct` | single_position_concentration | Max allowed % per position |
| `max_sector_concentration_pct` | sector_concentration | Max allowed % per sector |
| `exploration_capital_limit` | exploration_capital_limit | Max allowed value in EXPLORATION bucket |
| `min_cash_reserve_pct` | capital_bucket_drift | Min % for CASH_RESERVE bucket |

**Fallback behavior:** If no matching policy_rule exists, the check runs with
a default threshold defined in code. Defaults are conservative (lower thresholds).

| Check | Default threshold |
|---|---|
| single_position_concentration | 20% (any position >20% of portfolio) |
| sector_concentration | 40% (any sector >40% of portfolio) |
| exploration_capital_limit | 10% (EXPLORATION >10% of portfolio) |

---

## 5. Database Impact

### 5.1 Migration: 0023_guardian_intelligence

**Changes:**

| Change | Table | Detail |
|---|---|---|
| CHECK extension | `guardian_checks` | Add 5 new check_types: capital_bucket_drift, single_position_concentration, sector_concentration, exploration_capital_limit, data_quality_staleness |
| No new tables | — | Slice B uses existing Guardian schema exclusively |
| No new columns | — | Existing draft threshold/staleness/target fields sufficient |

**Additive only. Fully reversible.**

### 5.2 CHECK Constraint Extension

```sql
-- Before (Sprint 004):
check_type IN ('drift','category_exposure','staleness')

-- After (Sprint 010 Slice B):
check_type IN (
    'drift','category_exposure','staleness',
    'capital_bucket_drift',
    'single_position_concentration',
    'sector_concentration',
    'exploration_capital_limit',
    'data_quality_staleness'
)
```

Pattern: DROP old constraint → CREATE new constraint with full list (same
approach as Slice A evidence source_type extension).

---

## 6. Service Layer Design

### 6.1 New Functions in Guardian Service

```python
# apps/api/services/guardian_intelligence.py

def evaluate_capital_bucket_drift(
    session, check, policy_version, positions
) -> list[GuardianEventParams]:
    """Compare actual bucket allocations against policy targets."""

def evaluate_single_position_concentration(
    session, check, policy_version, positions
) -> list[GuardianEventParams]:
    """Detect positions exceeding max_single_position_pct."""

def evaluate_sector_concentration(
    session, check, policy_version, positions
) -> list[GuardianEventParams]:
    """Detect sectors exceeding max_sector_concentration_pct."""

def evaluate_exploration_capital_limit(
    session, check, policy_version, positions
) -> list[GuardianEventParams]:
    """Check EXPLORATION bucket against capital limit."""

def evaluate_data_quality_staleness(
    session, check, positions
) -> list[GuardianEventParams]:
    """Flag positions with stale observed_at timestamps."""
```

### 6.2 Integration with evaluate_core

The existing `evaluate_core` function (Sprint 004) dispatches check types to
evaluation functions. Slice B adds 5 new dispatch cases:

```python
CHECK_EVALUATORS = {
    'drift': evaluate_drift,                          # existing
    'category_exposure': evaluate_category_exposure,   # existing
    'staleness': evaluate_staleness,                   # existing
    # --- Slice B additions ---
    'capital_bucket_drift': evaluate_capital_bucket_drift,
    'single_position_concentration': evaluate_single_position_concentration,
    'sector_concentration': evaluate_sector_concentration,
    'exploration_capital_limit': evaluate_exploration_capital_limit,
    'data_quality_staleness': evaluate_data_quality_staleness,
}
```

### 6.3 Position Data Query

All 5 new checks need position data. A single query fetches all needed data:

```sql
SELECT
    p.id, p.quantity, p.market_value,
    p.observed_at,
    a.capital_bucket,
    ast.sector, ast.asset_type
FROM positions p
JOIN accounts a ON p.account_id = a.id
JOIN assets ast ON p.asset_id = ast.id
WHERE p.is_latest = TRUE
```

This query is shared across all checks to avoid N+1 queries.

---

## 7. Notification Wiring

### 7.1 Event → Notification Mapping

| Guardian Event | Notification Source | Severity | Fingerprint |
|---|---|---|---|
| bucket_drift detected | 'guardian' | From check | `guardian:bucket_drift:{bucket_name}` |
| concentration violation | 'guardian' | From check | `guardian:concentration:{position_id}` |
| sector concentration | 'guardian' | From check | `guardian:sector:{sector_name}` |
| exploration limit exceeded | 'guardian' | critical | `guardian:exploration_limit` |
| data staleness | 'guardian' | warning | `guardian:staleness:{date}` |

### 7.2 Notification Preferences

Guardian events respect existing `notification_preferences`:
- `enabled_sources`: must include 'guardian'
- `enabled_severities`: must include the event's severity
- `quiet_hours`: events outside quiet hours are delivered immediately;
  events during quiet hours are queued (existing behavior)

### 7.3 Suppression Rules

| Rule | Behavior |
|---|---|
| Fingerprint dedup | Same fingerprint within 24h → suppress (existing) |
| Critical events | Never suppressed (existing) |
| Staleness events | Once per 24h period |

---

## 8. API Design

### 8.1 New Endpoints

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/guardian/checks | OWNER_MUTATION | Create a new Guardian check (extended types) |
| GET | /api/guardian/checks | READ | List all Guardian checks |
| GET | /api/guardian/checks/{id} | READ | Get check details |
| POST | /api/guardian/evaluate | OWNER_MUTATION | Trigger evaluation run |
| GET | /api/guardian/events | READ | List recent Guardian events |
| GET | /api/guardian/status | READ | Guardian health + last run summary |

### 8.2 Extended Endpoints

Existing Guardian endpoints (if any exist from Sprint 004) gain support for
new check types transparently — no API contract changes needed.

---

## 9. Test Strategy

### 9.1 Migration Tests (3 tests)

| Test | What it proves |
|---|---|
| guardian_checks accepts new check types | CHECK constraint extended |
| Migration is reversible | Downgrade restores original CHECK |

### 9.2 Check Evaluation Tests (8 tests)

| Test | What it proves |
|---|---|
| capital_bucket_drift within bounds → no event | Normal operation |
| capital_bucket_drift outside bounds → event fired | Drift detection |
| single_position_concentration exceeded → event | Concentration detection |
| single_position_concentration within limit → no event | False positive prevention |
| sector_concentration exceeded → event | Sector monitoring |
| exploration_capital_limit exceeded → critical event | Safety rail enforcement |
| exploration_capital_limit within limit → no event | Normal operation |
| data_quality_staleness → warning event | Quality monitoring |

### 9.3 Policy-Backed Threshold Tests (3 tests)

| Test | What it proves |
|---|---|
| Check reads threshold from policy_rule | Policy integration |
| Check uses default when no policy_rule exists | Fallback behavior |
| Disabled policy_rule → check still runs with default | Safety-first design |

### 9.4 Notification Wiring Tests (3 tests)

| Test | What it proves |
|---|---|
| Guardian event → notification_event created | Wiring works |
| Critical events never suppressed | Safety invariant |
| Fingerprint dedup prevents spam | Noise reduction |

### 9.5 AI Authority Tests (2 tests)

| Test | What it proves |
|---|---|
| Guardian cannot modify policy | Read-only access to policy tables |
| Guardian cannot execute trades | No trade/order code path |

### 9.6 Total: ~19 tests

---

## 10. False Positive Handling

### 10.1 Bucket Drift Tolerance

Bucket drift checks use `min_pct` and `max_pct` from `policy_capital_buckets`.
The Owner sets these ranges — drift within the range is NOT an event. This
allows intentional tactical deviations without alert noise.

### 10.2 Concentration "Top-N" Reporting

When multiple positions or sectors exceed thresholds, the event reports the
top 5 violators. Fewer than 5 → report all. This prevents a single broad
market move from generating 50 identical events.

### 10.3 Staleness Grace Period

Staleness checks use `staleness_days` from the check draft. A 24-hour grace
period prevents alerts for positions imported within the same day. The
Owner configures the threshold per check.

### 10.4 Fingerprint-Based Dedup

All Guardian events use content-based fingerprinting (hash of check_id +
violation identifier). Same fingerprint within 24h → suppressed. This is
existing behavior from Sprint 007.

---

## 11. Severity Levels

| Severity | Meaning | Example | Automatic Action |
|---|---|---|---|
| info | Informational, no action needed | "Bucket CORE at 59.2%, target 60%" | Log only |
| warning | Attention recommended | "Position AAPL at 22% (limit 20%)" | Notification |
| critical | Immediate Owner attention | "EXPLORATION bucket at 15% (limit 10%)" | Notification + BLOCK_RECOMMENDATION |

**BLOCK_RECOMMENDATION**: When a critical Guardian event is active, the
Committee bridge (Slice A) rejects new review requests with `409 Conflict`
until the event is acknowledged. This is implemented in Slice B.

---

## 12. Risk Scenarios

### 12.1 Scenario: Concentrated Position After Market Rally

**Setup**: AAPL position at 18% of portfolio. max_single_position_pct = 20%.
**Trigger**: AAPL rallies 30%. Position now at 23.4%.
**Guardian response**: `single_position_concentration` event at warning severity.
**Owner action**: Review position. Decide: hold, trim, or adjust policy threshold.

### 12.2 Scenario: Exploration Bucket Exceeds Safety Limit

**Setup**: EXPLORATION bucket at 8%. exploration_capital_limit = 10%.
**Trigger**: Owner adds speculative position. EXPLORATION goes to 12%.
**Guardian response**: `exploration_capital_limit` event at critical severity.
Committee recommendations BLOCKED until acknowledged.
**Owner action**: Acknowledge, then either reduce position or adjust limit.

### 12.3 Scenario: Stale Import Data

**Setup**: Position data imported 48 hours ago.
**Trigger**: Guardian runs, staleness_days = 1.
**Guardian response**: `data_quality_staleness` event at warning severity.
**Owner action**: Re-import data or acknowledge stale state.

### 12.4 Scenario: No Policy Rules Defined

**Setup**: No `max_single_position_pct` rule exists.
**Trigger**: Guardian runs concentration check.
**Guardian response**: Uses default threshold (20%). No policy-backed
threshold available.
**Owner action**: Optionally create policy rule for customized thresholds.

---

## 13. Implementation Plan

### 13.1 File List

| File | New/Modified | Purpose |
|---|---|---|
| `migrations/versions/0023_guardian_intelligence.py` | New | CHECK extension |
| `apps/api/models.py` | Modified | Update ck_guardian_checks_type (model only, CHECK already extended) |
| `apps/api/services/guardian_intelligence.py` | New | 5 evaluation functions |
| `apps/api/services/guardian.py` | Modified | Add dispatch cases to evaluate_core |
| `apps/api/schemas/guardian.py` | Modified | Extend check_type validation |
| `apps/api/routers/guardian.py` | Modified | Endpoints for new checks |
| `tests/test_guardian_intelligence.py` | New | ~19 integration tests |
| `apps/api/mutation_gate.py` | Modified | EXPECTED_HEAD → 0023 |
| `apps/api/services/health_service.py` | Modified | EXPECTED_HEAD → 0023 |
| (all other HEAD_REVISION files) | Modified | 0022 → 0023 |

### 13.2 Implementation Order

1. Migration 0023
2. Update model CHECK constraint docstring
3. Guardian intelligence evaluation functions
4. Wire into evaluate_core
5. BLOCK_RECOMMENDATION logic in committee bridge
6. API endpoints
7. Notification wiring
8. Tests
9. HEAD_REVISION sweep

---

## 14. Owner Decisions (Pending)

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| OD-10-B-1 | Default concentration threshold | 20% single / 40% sector | Conservative; Owner can adjust via policy |
| OD-10-B-2 | BLOCK_RECOMMENDATION on critical events? | Yes / No | Yes — prevents decisions during active critical risk |
| OD-10-B-3 | Staleness default threshold | 24 hours | Reasonable for manual-import data |
| OD-10-B-4 | Guardian evaluation schedule | Daily or on-import trigger | Daily by default; on-import trigger in future sprint |

---

## 15. Estimated Scope

| Component | Complexity | Lines | Tests |
|---|---|---|---|
| Migration | Low | ~50 | 2 |
| Evaluation functions | Medium | ~300 | 8 |
| evaluate_core wiring | Low | ~30 | 0 (covered by eval tests) |
| BLOCK_RECOMMENDATION | Low | ~40 | 2 |
| API endpoints | Low | ~80 | 0 (covered by eval tests) |
| Notification wiring | Low | ~60 | 3 |
| Model update | Trivial | ~5 | 0 |
| HEAD_REVISION sweep | Mechanical | ~15 files | 0 |
| **Total** | | **~565 lines** | **~15 tests** |

---

## 16. Absolute Exclusions

- No trading, order placement, or execution
- No broker/bank API connections
- No real financial credentials
- No automatic rebalancing or position modification
- No AI-driven policy changes
- No frontend implementation
- No Slice C (Dashboard + Learning)
