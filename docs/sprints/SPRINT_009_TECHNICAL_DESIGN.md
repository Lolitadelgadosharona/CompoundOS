# Sprint 009 — Technical Design Gate

> **STATUS: IMPLEMENTATION IN PROGRESS**
>
> Slice A (Core Portfolio Schema + Asset Identity): **DONE** — merged 2026-08-10 (9f0ed00, PR #78)
> Slice B (Investment Policy Enrichment): **DONE** — merged 2026-08-10 (4a7312c, PR #79)
> Slice C (Investment Idea + Decision Bridge): **DONE** — merged 2026-08-10 (f87e4e8, PR #80)
> Slice D (Manual Import + Data Source Foundation): NOT AUTHORIZED
>
> This document defines the architecture for the Wealth Intelligence Foundation.
> Slice A implementation complete. Subsequent slices require separate Owner authorization.
> No migrations, production code, or financial credentials are authorized.
> Owner approval of this design is the gate to implementation authorization.

---

## Executive Summary

Sprint 009 establishes the durable domain foundation for CompoundOS as a Wealth
Intelligence system.  It builds on the existing portfolio, policy, committee,
and Guardian infrastructure from Sprints 001–008 and adds:

1. **Canonical Asset/Instrument identity** — a single source of truth for what
   is held, distinct from provider-specific representations.

2. **Financial Account classification** — economic purpose (Core / Exploration /
   Cash Reserve) separated from provider/account type.

3. **Position & Cost Basis model** — provider-reported vs. CompoundOS-derived
   values tracked independently with full provenance.

4. **Multi-currency foundation** — native currency, base reporting currency,
   FX conversion with timestamped rates and historical traceability.

5. **Investment Idea lifecycle** — structured proposal → Committee review →
   Owner decision, with audit trail from idea to outcome.

6. **Versioned Investment Policy enrichment** — Capital Bucket definitions,
   allocation targets, risk limits, and approval requirements as policy rules.

7. **Explicit AI Authority Matrix** — every financial action classified as
   Allowed / Not Allowed / Requires Owner for AI agents.  Hard boundary
   against autonomous trading.

8. **Read-only Connector Architecture** — provider-agnostic adapter interfaces
   for future broker/bank connections.  No providers implemented.

Sprint 009 does NOT implement trading, broker connections, or real financial
data ingestion.  It creates the schema, contracts, and invariants those
capabilities will depend on.

---

## 1. Predecessor Verification

| Sprint | Status | Key Deliverables |
|--------|--------|-----------------|
| 001–002 | Done | Household, Policy (versioned, immutable), Decision Journal |
| 003 | Done | Portfolio snapshots, draft holdings, accounts skeleton |
| 004 | Done | Guardian checks, evaluation engine, events |
| 005 | Done | Orchestration: schedules, worker, leases, fencing (PR #75 corrective) |
| 006 | Done | AI Investment Committee: evidence pipeline, provider, 7 perspectives |
| 007 | Done | Backup, health, notification (explicit opt-in) |
| 008 | Done | Notification source wiring, daily schedules (Slice C merged #74) |

Migration head: 0017_backup_daily_allowlist.
All existing models, constraints, and invariants preserved.
Sprint 009 is additive — no existing migration is modified.

**PREDECESSOR VERIFIED.**

---

## 2. Architecture Principles (Sprint 009)

1. **Build on existing domain, don't duplicate it.**  Portfolio snapshots,
   Policy versions, Decision Journal, Committee sessions, and Guardian
   checks already exist.  Sprint 009 enriches them, never replaces them.

2. **Provenance is mandatory.**  Every financial datum carries a source,
   timestamp, and confidence indicator.  Provider facts, CompoundOS
   calculations, AI inferences, and Owner inputs are never silently mixed.

3. **Multi-currency by design.**  USD, HKD, CNY and future currencies.
   Native amount stored alongside base-currency equivalent.  Never silently
   convert or compare across currencies.

4. **Policy governs, code enforces.**  Capital allocations, risk limits,
   and approval requirements live in versioned Policy.  The schema supports
   the policy; it does not encode it as irreversible rules.

5. **AI may analyze and recommend but must never silently execute.**
   The Authority Matrix is explicit and enforced at the API boundary.

6. **Smallest change that enables the next step.**  Tables added only for
   concepts that have a clear consumer in this or the immediately following
   sprint.  No speculative schema.

---

## 3. Domain Model

### 3.1 Asset / Instrument

An **Asset** (or **Instrument**) is the canonical identity for something that
can be held in a portfolio.  It is distinct from any provider's representation
of that asset.

```
┌─────────────────────────────────────────────────────────┐
│                      Asset                              │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ symbol (TEXT, nullable — provider-independent ticker)   │
│ name (TEXT, NOT NULL, ≤200 chars)                       │
│ asset_type (TEXT, NOT NULL)  — ETF/STOCK/BOND/CASH/... │
│ currency (TEXT, NOT NULL, 3-char ISO)                   │
│ exchange (TEXT, nullable)                               │
│ isin (TEXT, nullable, UNIQUE where not null)            │
│ asset_class (TEXT, nullable)                            │
│ sub_asset_class (TEXT, nullable)                        │
│ region (TEXT, nullable)                                 │
│ sector (TEXT, nullable)                                 │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

**Canonical identity strategy**: ISIN is the primary global identifier.
Where ISIN is absent (e.g. some ETFs, custom instruments), identity is
established by (symbol, exchange, currency) tuple with a UNIQUE constraint.
Manual-entry assets may have no ISIN — the system allows this but flags
it as lower-confidence data.

**Constraints**:
- `uq_assets_isin`: UNIQUE (isin) WHERE isin IS NOT NULL
- `uq_assets_symbol_exchange_currency`: UNIQUE (symbol, exchange, currency) WHERE symbol IS NOT NULL
- `ck_assets_type`: CHECK (asset_type IN ('ETF','STOCK','BOND','CASH','MONEY_MARKET','FUND','OTHER'))
- `ck_assets_currency`: CHECK (currency ~ '^[A-Z]{3}$')

**Why not over-model**: Asset class, sub-class, region, sector are free-text
with planned future constraint to approved enum values.  Sprint 009 stores
them; Sprint 010+ validates them.

### 3.2 Financial Account

An **Account** extends the existing `accounts` table (which currently has only
name, notes, and sort_order).  Sprint 009 adds classification and metadata
without breaking the existing schema.

```
┌─────────────────────────────────────────────────────────┐
│               Account (extended)                         │
├─────────────────────────────────────────────────────────┤
│ + account_type (TEXT, NOT NULL)                         │
│     — 'brokerage' / 'bank' / 'retirement' / 'other'    │
│ + account_subtype (TEXT, nullable)                      │
│     — provider-specific: 'HSBC_ONE', 'IB_INDIVIDUAL'   │
│ + capital_bucket (TEXT, NOT NULL, DEFAULT 'CORE')      │
│     — 'CORE' / 'EXPLORATION' / 'CASH_RESERVE' /        │
│       'RETIREMENT' / 'OTHER'                            │
│ + currency (TEXT, NOT NULL, 3-char ISO, DEFAULT 'USD') │
│ + provider (TEXT, nullable)                             │
│     — 'interactive_brokers' / 'hsbc' / 'manual' / ...  │
│ + provider_account_id (TEXT, nullable)                  │
│ + is_active (BOOLEAN, NOT NULL, DEFAULT true)           │
│ + opened_at (DATE, nullable)                            │
│ + closed_at (DATE, nullable)                            │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `ck_accounts_type`: CHECK (account_type IN (...))
- `ck_accounts_bucket`: CHECK (capital_bucket IN ('CORE','EXPLORATION','CASH_RESERVE','RETIREMENT','OTHER'))
- `ck_accounts_currency`: CHECK (currency ~ '^[A-Z]{3}$')
- `uq_accounts_provider_id`: UNIQUE (provider, provider_account_id) WHERE provider IS NOT NULL AND provider_account_id IS NOT NULL

**Relationship to existing `accounts` table**: These columns are ADDED to the
existing table via additive migration.  Existing accounts rows receive defaults
(account_type='brokerage', capital_bucket='CORE', currency from household
base_currency).

### 3.3 Position

A **Position** represents a holding of an Asset in an Account at a point in time.

```
┌─────────────────────────────────────────────────────────┐
│                      Position                            │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ account_id (UUID FK → accounts, NOT NULL)               │
│ asset_id (UUID FK → assets, NOT NULL)                   │
│ quantity (NUMERIC(20,8), NOT NULL)                      │
│ quantity_source (TEXT, NOT NULL)                        │
│     — 'provider_reported' / 'compoundos_derived'        │
│ avg_cost (NUMERIC(20,8), nullable)                      │
│ avg_cost_currency (TEXT, NOT NULL, 3-char ISO)         │
│ avg_cost_source (TEXT, nullable)                        │
│ market_price (NUMERIC(20,8), nullable)                  │
│ market_price_currency (TEXT, NOT NULL, DEFAULT → asset)│
│ market_price_as_of (TIMESTAMPTZ, nullable)              │
│ market_value (NUMERIC(20,8), nullable)                  │
│     — compoundos_derived: quantity × market_price       │
│ market_value_currency (TEXT, nullable)                  │
│ cost_basis (NUMERIC(20,8), nullable)                    │
│     — compoundos_derived: quantity × avg_cost           │
│ cost_basis_currency (TEXT, nullable)                    │
│ unrealized_gain_loss (NUMERIC(20,8), nullable)          │
│     — compoundos_derived: market_value − cost_basis     │
│ observed_at (TIMESTAMPTZ, NOT NULL)                     │
│     — when provider reported this position              │
│ imported_at (TIMESTAMPTZ, NOT NULL, DEFAULT now())     │
│ source (TEXT, NOT NULL)                                 │
│     — 'interactive_brokers' / 'hsbc' / 'manual' / ...  │
│ source_record_id (TEXT, nullable)                       │
│     — provider's internal ID for traceability           │
│ is_latest (BOOLEAN, NOT NULL, DEFAULT true)             │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `uq_positions_source_record`: UNIQUE (source, source_record_id) WHERE source_record_id IS NOT NULL
- `ck_positions_quantity`: CHECK (quantity >= 0) — zero-quantity positions allowed (closed)
- `ck_positions_source`: CHECK (source IN ('interactive_brokers','hsbc','schwab','csv','manual','compoundos_derived'))

**Source attribution**: Every Position row carries `source` and `source_record_id`.
CompoundOS-derived values (market_value, cost_basis, unrealized_gain_loss) are
computed columns marked with `_source = 'compoundos_derived'`. Provider-reported
values have the provider's name as source.

**is_latest semantics**: When a new position snapshot arrives, the previous
`is_latest=true` row for the same (account_id, asset_id) is set to `is_latest=false`
in the same transaction.  This provides point-in-time position history without
a separate positions_history table.

### 3.4 Cash Balance

```
┌─────────────────────────────────────────────────────────┐
│                   CashBalance                            │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ account_id (UUID FK → accounts, NOT NULL)               │
│ currency (TEXT, NOT NULL, 3-char ISO)                   │
│ amount (NUMERIC(20,8), NOT NULL)                        │
│ observed_at (TIMESTAMPTZ, NOT NULL)                     │
│ source (TEXT, NOT NULL)                                 │
│ source_record_id (TEXT, nullable)                       │
│ is_latest (BOOLEAN, NOT NULL, DEFAULT true)             │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `uq_cash_balances_source_record`: UNIQUE (source, source_record_id) WHERE source_record_id IS NOT NULL

Cash is tracked separately from positions because it has no asset_id, no
quantity, and no cost basis.  Multiple currencies per account are supported.

### 3.5 Transaction

A **Transaction** records a financial event: buy, sell, dividend, deposit,
withdrawal, fee, etc.

```
┌─────────────────────────────────────────────────────────┐
│                     Transaction                          │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ account_id (UUID FK → accounts, NOT NULL)               │
│ asset_id (UUID FK → assets, nullable)                   │
│     — null for cash transactions                        │
│ transaction_type (TEXT, NOT NULL)                       │
│     — 'BUY'/'SELL'/'DIVIDEND'/'INTEREST'/'DEPOSIT'     │
│       /'WITHDRAWAL'/'FEE'/'TRANSFER_IN'/'TRANSFER_OUT' │
│       /'SPLIT'/'OTHER'                                  │
│ quantity (NUMERIC(20,8), nullable)                      │
│ price (NUMERIC(20,8), nullable)                         │
│ price_currency (TEXT, nullable)                         │
│ amount (NUMERIC(20,8), nullable)                        │
│     — cash amount (positive = inflow, negative = out)   │
│ amount_currency (TEXT, nullable)                        │
│ fee (NUMERIC(20,8), nullable)                           │
│ fee_currency (TEXT, nullable)                           │
│ executed_at (TIMESTAMPTZ, NOT NULL)                     │
│     — when the transaction occurred (provider time)     │
│ settled_at (TIMESTAMPTZ, nullable)                      │
│ source (TEXT, NOT NULL)                                 │
│ source_record_id (TEXT, nullable)                       │
│ imported_at (TIMESTAMPTZ, NOT NULL, DEFAULT now())     │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `uq_transactions_source_record`: UNIQUE (source, source_record_id) WHERE source_record_id IS NOT NULL
- `ck_transactions_type`: CHECK (transaction_type IN (...))
- `ck_transactions_amount_sign`: CHECK — no constraint; sign conveys direction

### 3.6 DataSource / ImportSource

A lightweight registry of known data sources.

```
┌─────────────────────────────────────────────────────────┐
│                    DataSource                            │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ source_key (TEXT, NOT NULL, UNIQUE)                     │
│     — 'interactive_brokers' / 'hsbc' / 'manual'        │
│ source_type (TEXT, NOT NULL)                            │
│     — 'broker' / 'bank' / 'csv' / 'manual'             │
│ is_active (BOOLEAN, NOT NULL, DEFAULT true)            │
│ last_import_at (TIMESTAMPTZ, nullable)                  │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Multi-Currency Design

### 4.1 Currency Model

Every monetary value in Sprint 009 carries its currency as an explicit column.
The system never assumes USD or any single currency.

**Base reporting currency**: Defined in `HouseholdProfile.base_currency`
(already exists).  This is the currency for portfolio-level aggregation and
reporting.

**Native currency**: The currency in which an account, position, or transaction
is denominated.  Stored alongside each value.

### 4.2 FX Rates

```
┌─────────────────────────────────────────────────────────┐
│                     FxRate                               │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ from_currency (TEXT, NOT NULL, 3-char ISO)              │
│ to_currency (TEXT, NOT NULL, 3-char ISO)                │
│ rate (NUMERIC(20,10), NOT NULL)                         │
│     — 1 from_currency = rate to_currency                │
│ rate_source (TEXT, NOT NULL)                            │
│     — provider or 'manual'                              │
│ observed_at (TIMESTAMPTZ, NOT NULL)                     │
│     — the effective timestamp of this rate              │
│ imported_at (TIMESTAMPTZ, NOT NULL, DEFAULT now())     │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `uq_fx_rates`: UNIQUE (from_currency, to_currency, observed_at, rate_source)
- `ck_fx_rates_currency`: CHECK (from_currency ~ '^[A-Z]{3}$' AND to_currency ~ '^[A-Z]{3}$')
- `ck_fx_rates_different`: CHECK (from_currency != to_currency)

**FX rate source**: Sprint 009 provides the schema only.  Rate ingestion is
deferred to a future sprint (or manual entry).  The design supports eventual
automated rate feeds.

### 4.3 Conversion Semantics

- **Portfolio aggregation**: All position values are converted to base currency
  using the most recent FX rate at or before `observed_at` for the
  `(position_currency → base_currency)` pair.

- **Historical conversion**: Performance calculations use the FX rate effective
  at the time of the valuation, not the current rate.  This prevents FX drift
  from distorting historical performance.

- **Never silently mix**: Any API that accepts or returns a monetary value MUST
  include its currency.  Cross-currency arithmetic without explicit conversion
  is a type error at the service layer.

---

## 5. Position & Cost Basis

### 5.1 Provider-Reported vs. CompoundOS-Derived

Every Position field has an explicit source:

| Field | Provider Reports | CompoundOS Derives |
|--------|------------------|-------------------|
| quantity | ✓ (from statement) | — |
| avg_cost | ✓ (from provider) | Optional: average of buy transactions |
| market_price | ✓ (from provider snapshot) | Optional: external feed |
| market_value | Optional | ✓ = quantity × market_price |
| cost_basis | Optional | ✓ = quantity × avg_cost |
| unrealized_gain_loss | — | ✓ = market_value − cost_basis |

**Key invariant**: CompoundOS never silently overwrites a provider-reported
value with its own derivation.  If both exist, the provider value is
preserved and the derived value is stored in a separate column suffixed
`_compoundos` (future refinement — Sprint 009 uses source attribution only).

### 5.2 Cost Basis Method

Sprint 009 does not implement FIFO/LIFO/specific-ID cost basis calculation.
It stores:

1. `avg_cost` as reported by the provider (authoritative).
2. `avg_cost_compoundos` as calculated from transaction history (when
   transactions are available).

This distinction prevents the system from claiming a cost basis different
from what the provider (and tax authority) reports.

---

## 6. Performance Model

Sprint 009 provides the schema for future performance calculations without
implementing the calculation engine.

### 6.1 Performance Snapshot

```
┌─────────────────────────────────────────────────────────┐
│               PerformanceSnapshot                        │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ account_id (UUID FK → accounts, nullable)               │
│     — null = portfolio-level                            │
│ currency (TEXT, NOT NULL, 3-char ISO)                   │
│ period_start (DATE, NOT NULL)                           │
│ period_end (DATE, NOT NULL)                             │
│ beginning_value (NUMERIC(20,8), NOT NULL)            │
│ ending_value (NUMERIC(20,8), NOT NULL)               │
│ contributions (NUMERIC(20,8), NOT NULL, DEFAULT 0)   │
│ withdrawals (NUMERIC(20,8), NOT NULL, DEFAULT 0)     │
│ income (NUMERIC(20,8), NOT NULL, DEFAULT 0)          │
│ return_pct (NUMERIC(10,6), nullable)                    │
│     — compoundos_derived (TWR or MWR)                  │
│ is_derived (BOOLEAN, NOT NULL, DEFAULT false)          │
│     — true = CompoundOS calculated                     │
│ calculated_at (TIMESTAMPTZ, nullable)                   │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `uq_perf_snapshot`: UNIQUE (account_id, currency, period_start, period_end)
- `ck_perf_period`: CHECK (period_start < period_end)

**Derived vs. persisted**: `beginning_value`, `ending_value`, `contributions`,
`withdrawals`, `income` are persisted facts.  `return_pct` is a derived value
that may be recomputed if the method changes.  `is_derived=true` signals that
CompoundOS calculated it.

---

## 7. Investment Policy Enrichment

The existing `investment_policies` + `investment_policy_versions` + `*_drafts`
architecture (Sprint 002) is preserved.  Sprint 009 adds policy rules without
changing the versioning model.

### 7.1 Capital Bucket Definition

Added to `investment_policy_drafts` and `investment_policy_versions` as a new
section:

```
┌─────────────────────────────────────────────────────────┐
│           PolicyCapitalBucket (new table)                 │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ draft_id (UUID FK → investment_policy_drafts, nullable) │
│ version_id (UUID FK → investment_policy_versions,       │
│             nullable)                                    │
│     — exactly one of draft_id/version_id NOT NULL       │
│ bucket_name (TEXT, NOT NULL)                            │
│     — 'CORE' / 'EXPLORATION' / 'CASH_RESERVE' / ...    │
│ target_pct (NUMERIC(5,2), NOT NULL)                     │
│ min_pct (NUMERIC(5,2), nullable)                        │
│ max_pct (NUMERIC(5,2), nullable)                        │
│ description (TEXT, nullable)                            │
│ sort_order (INTEGER, NOT NULL, DEFAULT 0)               │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `ck_bucket_one_parent`: CHECK ((draft_id IS NOT NULL)::int + (version_id IS NOT NULL)::int = 1)
- `ck_bucket_pct_range`: CHECK (target_pct >= 0 AND target_pct <= 100)
- `ck_bucket_min_max`: CHECK (min_pct IS NULL OR max_pct IS NULL OR min_pct <= max_pct)

**Version snapshot semantics**: When a Policy is published (Draft → Version),
`PolicyCapitalBucket` rows for the version are INSERTED from the draft's rows.
Version rows are immutable (no UPDATE/DELETE trigger, matching existing policy
version allocation pattern).  Draft rows are editable and consumed on publish.

### 7.2 Policy Rule (extensible)

```
┌─────────────────────────────────────────────────────────┐
│                     PolicyRule                           │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ draft_id (UUID FK → investment_policy_drafts, nullable) │
│ version_id (UUID FK → investment_policy_versions,       │
│             nullable)                                    │
│ rule_type (TEXT, NOT NULL)                               │
│     — 'max_single_position_pct'                         │
│       / 'max_sector_concentration_pct'                   │
│       / 'max_drawdown_pct'                              │
│       / 'min_cash_reserve_pct'                          │
│       / 'approval_required_for'                         │
│       / 'custom'                                        │
│ rule_value (TEXT, NOT NULL)                             │
│     — JSON or scalar, depends on rule_type              │
│ description (TEXT, nullable)                            │
│ sort_order (INTEGER, NOT NULL, DEFAULT 0)               │
└─────────────────────────────────────────────────────────┘
```

**Constraints**:
- `ck_rule_one_parent`: same pattern as buckets
- `ck_rule_type`: CHECK (rule_type IN (...))

**Example rules**:
```json
{"rule_type": "max_single_position_pct", "rule_value": "20.00"}
{"rule_type": "max_sector_concentration_pct", "rule_value": "40.00"}
{"rule_type": "approval_required_for", "rule_value": "{\"actions\":[\"SELL\",\"WITHDRAWAL\"],\"min_amount\":\"50000.00\"}"}
```

**Why JSON rule_value**: Different rule types need different value shapes.
A single TEXT column with documented JSON schemas per type avoids table
explosion while remaining queryable (PostgreSQL JSONB path queries when
moved to Version table).

---

## 8. Capital Bucket Policy

### 8.1 Design

Capital Buckets are defined in the Investment Policy, not in application code
or database constants.

Example policy (not hard-coded):
```
CORE:           target 95%, min 90%, max 100%
EXPLORATION:    target  5%, min  0%, max  10%
CASH_RESERVE:   target  0%, min  0%, max   5%
```

### 8.2 Account-to-Bucket Assignment

Each Account is assigned to one `capital_bucket`.  The aggregate value of all
accounts in a bucket is compared against the policy's bucket targets.

### 8.3 Drift Detection (Guardian Integration)

The Guardian (Sprint 004) already has evaluation infrastructure.  Sprint 009
adds Guardian check definitions for bucket drift:

- `capital_bucket_drift`: evaluate actual vs. policy target for each bucket
- `drift_tolerance`: configurable via PolicyRule (e.g. ±2%)
- Alert when drift exceeds tolerance — WARN, never auto-rebalance

---

## 9. Investment Idea Model

### 9.1 Entity

```
┌─────────────────────────────────────────────────────────┐
│                   InvestmentIdea                         │
├─────────────────────────────────────────────────────────┤
│ id (UUID PK)                                            │
│ household_id (UUID FK → household_profiles, NOT NULL)   │
│ asset_id (UUID FK → assets, nullable)                   │
│     — null for ideas not tied to a specific instrument  │
│ title (TEXT, NOT NULL, ≤200 chars)                      │
│ thesis (TEXT, nullable)                                 │
│ proposed_allocation_pct (NUMERIC(5,2), nullable)        │
│ proposed_amount (NUMERIC(20,8), nullable)               │
│ proposed_amount_currency (TEXT, nullable)               │
│ source (TEXT, NOT NULL)                                 │
│     — 'owner' / 'committee' / 'guardian' / 'external'   │
│ expected_holding_period (TEXT, nullable)                │
│     — free-text: 'LT_5YR' / 'MT_1_3YR' / 'ST_6MO'     │
│ expected_return_rationale (TEXT, nullable)              │
│ downside_thesis (TEXT, nullable)                        │
│ risks (TEXT, nullable)                                  │
│ catalysts (TEXT, nullable)                              │
│ valuation_assumptions (TEXT, nullable)                  │
│ confidence (TEXT, nullable)                             │
│     — 'HIGH' / 'MEDIUM' / 'LOW' / 'SPECULATIVE'        │
│ policy_version_id (UUID FK → investment_policy_versions,
│                     nullable)                            │
│     — which policy version was active when created      │
│ status (TEXT, NOT NULL, DEFAULT 'draft')                │
│ created_at (TIMESTAMPTZ, NOT NULL)                      │
│ updated_at (TIMESTAMPTZ, NOT NULL)                      │
└─────────────────────────────────────────────────────────┘
```

### 9.2 Lifecycle

```
DRAFT ──→ UNDER_REVIEW ──→ APPROVED
  │            │               │
  │            ├──→ REJECTED   ├──→ EXECUTED (future)
  │            │               │
  ├──→ DEFERRED               └──→ CANCELLED
  │
  └──→ CANCELLED
```

**Constraints**:
- `ck_idea_status`: CHECK (status IN ('draft','under_review','approved','rejected','deferred','cancelled'))
- `ck_idea_confidence`: CHECK (confidence IS NULL OR confidence IN ('HIGH','MEDIUM','LOW','SPECULATIVE'))

### 9.3 Committee Integration

An Investment Idea in `under_review` status can be submitted to the AI
Investment Committee (Sprint 006).  The Committee's evidence pipeline
extracts the idea's thesis, proposed allocation, and risks as evidence
items.  The Committee report references the `investment_idea_id`.

**Key invariant**: Committee APPROVAL ≠ trade authorization.  The Committee
provides analysis and recommendation.  Only the Owner may approve an idea
for execution.  Execution itself (placing an order) is NOT in Sprint 009.

---

## 10. AI Investment Committee — Sprint 009 Extensions

### 10.1 Existing Architecture (Sprint 006)

The Committee already has:
- `committee_sessions`: draft→queued→running→completed/failed
- `committee_evidence_items`: structured facts with provenance
- `committee_reports`: immutable, 7 perspectives + synthesis
- `committee_outcomes`: append-only accept/reject/defer

### 10.2 Sprint 009 Additions

**Evidence source: Position/Holdings data**
The evidence pipeline (Sprint 006) extracts from Policy, Portfolio,
Guardian, and Decisions.  Sprint 009 adds Positions and Transactions
as evidence sources — but only in aggregate form:
- Total portfolio value by currency
- Asset allocation by category (no individual holdings)
- Recent transactions summary (count, total volume, not individual)
- Concentration metrics (largest position pct, top-3 pct)

**No raw position data exposed to LLM.** Individual holdings, quantities,
prices, and account identifiers are never included in evidence.

**Committee perspective: PORTFOLIO_CONSTRUCTION**
A seventh approved perspective (Sprint 006 has 7 already — Sprint 009
formalizes the seventh as `portfolio_construction` focusing on position
sizing, concentration, and portfolio-level impact of proposed ideas).

**Outcome → Decision Journal bridge**
When the Owner records an ACCEPT outcome, the system optionally creates
a Decision Journal Draft with the Committee Report as supporting evidence.
The Decision is never auto-confirmed.

---

## 11. Decision Journal — Sprint 009 Extensions

### 11.1 Existing Architecture (Sprint 002/003)

The Decision Journal already has:
- Immutable `decision_confirmed_snapshots`
- Append-only `decision_corrections`
- `decision_date` ≤ CURRENT_DATE enforced
- Policy version FK

### 11.2 Sprint 009 Additions

**Decision → Investment Idea linkage**
`decision_confirmed_snapshots` and `decision_drafts` add an optional
`investment_idea_id` FK.  This preserves the chain: Idea → Committee
Review → Owner Decision → Outcome.

**Decision → Post-Decision Review**
Add a `review_schedule` field to DecisionConfirmedSnapshot:
- `review_30d` (DATE, nullable): scheduled 30-day review
- `review_90d` (DATE, nullable): scheduled 90-day review
- `review_1yr` (DATE, nullable): scheduled 1-year review
- `review_outcome` (TEXT, nullable): free-text outcome notes

These are scheduled reminders, not automated actions.  The Automation
worker (Sprint 005) can pick up due reviews and dispatch notifications.

---

## 12. Guardian Integration — Sprint 009

### 12.1 Existing Architecture (Sprint 004)

Guardian has:
- `guardian_checks`: check definitions (drift, staleness, etc.)
- `guardian_evaluation_runs`: evaluation history
- `guardian_events`: detected violations
- Transaction-neutral `evaluate_core` (used by HTTP and worker)

### 12.2 Sprint 009 Guardian Checks

New check types added to the existing Guardian framework:

| Check | What it monitors | Severity |
|-------|-----------------|----------|
| `capital_bucket_drift` | Actual bucket % vs policy target | warning |
| `single_position_concentration` | Any position > max_single_position_pct | warning |
| `sector_concentration` | Any sector > max_sector_concentration_pct | warning |
| `exploration_capital_limit` | EXPLORATION bucket > policy max | critical |
| `data_quality_staleness` | Position data older than N hours | warning |
| `missing_asset_identity` | Position with no asset_id / manual entry | info |
| `behavioral_flag` | Rapid successive idea submissions | info |

**All checks use existing `evaluate_core` infrastructure.** No new
evaluation engine.  Check definitions are rows in `guardian_checks`;
thresholds come from `PolicyRule`.

**Guardian authority (unchanged)**:
- WARN: notification dispatch (Sprint 007/008)
- BLOCK_RECOMMENDATION: committee outcome cannot be "ACCEPT" while active
- REQUIRE_OWNER_CONFIRMATION: extra confirmation step in UI
- NEVER: auto-sell, auto-rebalance, auto-trade

---

## 13. Data Quality & Provenance

### 13.1 Provenance Fields (standard across all Sprint 009 tables)

Every imported or derived financial datum carries:

| Field | Purpose | Example |
|-------|---------|---------|
| `source` | Which system/provider | `interactive_brokers` |
| `source_record_id` | Provider's internal ID | `IB-20260809-AAPL` |
| `observed_at` | When provider observed/reported this | `2026-08-09T16:00:00Z` |
| `imported_at` | When CompoundOS ingested it | `2026-08-09T16:05:00Z` |
| `_source` suffix on derived fields | Distinguishes provider vs CompoundOS | `market_value` vs `market_value_source` |

### 13.2 Data Categories

Every datum is classified into exactly one category:

| Category | Source | Trust Level | Can Override |
|----------|--------|-------------|-------------|
| `provider_fact` | Broker/bank API or statement | High | Provider only |
| `compoundos_calculation` | Determined from provider facts | Derived | Recalculated on new data |
| `ai_inference` | AI Committee analysis | Advisory | Never overrides provider |
| `owner_input` | Manual entry by Owner | Authoritative for manual | Owner only |

### 13.3 Audit Trail

All mutations to financial data produce `AuditEvent` rows (existing table).
Sprint 009 adds audit actions:
- `position.imported`
- `position.updated`
- `transaction.imported`
- `asset.created`
- `account.classified`
- `investment_idea.status_changed`

Audit metadata includes changed field names only (never sensitive values,
matching existing convention).

---

## 14. Future Read-Only Connector Architecture

### 14.1 Provider-Agnostic Interfaces

Sprint 009 defines Python protocol interfaces.  No implementations.

```python
class AccountImporter(Protocol):
    """Import account metadata from a provider."""
    def import_accounts(self, household_id: UUID) -> list[AccountImportResult]: ...

class PositionImporter(Protocol):
    """Import current positions from a provider."""
    def import_positions(self, account_id: UUID) -> list[PositionImportResult]: ...

class TransactionImporter(Protocol):
    """Import transaction history from a provider."""
    def import_transactions(
        self, account_id: UUID, from_date: date, to_date: date
    ) -> list[TransactionImportResult]: ...

class BalanceImporter(Protocol):
    """Import cash balances from a provider."""
    def import_balances(self, account_id: UUID) -> list[BalanceImportResult]: ...
```

### 14.2 Result Types

```python
@dataclass
class AccountImportResult:
    provider_account_id: str
    account_name: str
    account_type: str
    currency: str
    raw_data: dict  # provider-specific, for debugging

@dataclass
class PositionImportResult:
    provider_record_id: str
    asset_identifier: AssetIdentifier  # ISIN or (symbol, exchange)
    quantity: Decimal
    avg_cost: Decimal | None
    market_price: Decimal | None
    observed_at: datetime
    raw_data: dict

@dataclass
class TransactionImportResult:
    provider_record_id: str
    asset_identifier: AssetIdentifier | None
    transaction_type: str
    quantity: Decimal | None
    price: Decimal | None
    amount: Decimal | None
    fee: Decimal | None
    executed_at: datetime
    raw_data: dict

@dataclass
class BalanceImportResult:
    provider_record_id: str
    currency: str
    amount: Decimal
    observed_at: datetime
    raw_data: dict
```

### 14.3 Asset Resolution Strategy

When a provider reports a position, the importer resolves the provider's
asset identifier to a CompoundOS `Asset`:

1. Try ISIN match (exact).
2. Try (symbol, exchange) match (normalized).
3. If no match: create a new Asset with `source='provider_name'` and flag
   as `confidence='unverified'`.
4. Owner can later merge/verify assets via manual curation.

### 14.4 Idempotent Import

All importers use `(source, source_record_id)` uniqueness to prevent
duplicate imports.  Re-running an import is safe — existing records are
updated (position quantity, price) or skipped (transactions).

---

## 15. Security Boundary

### 15.1 SEC-001 (Existing)

Repository must become PRIVATE before real financial account integration.
This P0 gate is preserved and noted in the design.  Sprint 009 adds no
credentials and does not change repository visibility.

### 15.2 Credential Architecture (Design Only)

Future credential storage:
- Secrets never in Git or database dumps.
- Provider credentials stored in environment variables or a local secret
  manager (macOS Keychain, as already used by AI Committee credential
  manager in Sprint 006).
- Read-only API keys where providers support them.
- Audit: every credential access logged (AuditEvent).
- Least privilege: one credential per provider, scoped to read-only
  account/position/transaction data.

### 15.3 No Credentials in Sprint 009

Sprint 009 defines the architecture.  No API keys, OAuth tokens, or
connection strings for financial providers are added.

---

## 16. AI Authority Matrix

### 16.1 Action Classification

| Action | AI Agent | Owner | Notes |
|--------|----------|-------|-------|
| Read portfolio data | Allowed | Allowed | Read-only access |
| Calculate portfolio metrics | Allowed | Allowed | Deterministic computation |
| Generate investment analysis | Allowed | Allowed | Must cite evidence |
| Run Investment Committee | Allowed | Allowed | Manual trigger only |
| Generate recommendation | Allowed | Allowed | Labeled as AI-generated |
| Create Investment Idea | Allowed | Allowed | Draft status only |
| Modify Investment Policy | NOT allowed | Required | Policy changes are Owner-only |
| Change Guardian threshold | NOT allowed | Required | Thresholds in Policy |
| Approve Investment Idea | NOT allowed | Required | Status: draft→under_review AI; →approved Owner only |
| Confirm Decision | NOT allowed | Required | Immutable decision snapshot |
| Place trade | NOT allowed | Required | NOT in Sprint 009 |
| Withdraw funds | NEVER allowed | Required | Not in scope |
| Transfer funds | NEVER allowed | Required | Not in scope |
| Enable trading capability | NOT allowed | Required | Requires explicit architecture approval |
| Import provider data | Allowed (read) | Allowed | Read-only connector |
| Modify imported data | NOT allowed | Allowed | Provider facts immutable |
| Delete audit records | NEVER allowed | NEVER allowed | Append-only |

### 16.2 Enforcement

- API layer: endpoint classification (READ / OWNER_MUTATION / SYSTEM_INTERNAL)
- Service layer: authorization check before mutation
- Database layer: triggers prevent certain mutations regardless of caller
- Immutable tables: UPDATE/DELETE blocked by PostgreSQL triggers

---

## 17. Database Design Summary

### 17.1 New Tables (Sprint 009)

| Table | Migration | Purpose |
|-------|-----------|---------|
| `assets` | 0018 | Canonical instrument identity |
| `positions` | 0018 | Holdings with source attribution |
| `cash_balances` | 0018 | Cash per account per currency |
| `transactions` | 0018 | Financial event records |
| `fx_rates` | 0018 | Currency conversion rates |
| `data_sources` | 0018 | Provider registry |
| `performance_snapshots` | 0019 | Computed performance metrics |
| `investment_ideas` | 0019 | Structured investment proposals |
| `idea_status_history` | 0019 | Audit trail for idea lifecycle |
| `policy_capital_buckets` | 0020 | Bucket definitions in Policy |
| `policy_rules` | 0020 | Extensible policy rules |

### 17.2 Modified Tables (additive only)

| Table | New Columns |
|-------|------------|
| `accounts` | account_type, account_subtype, capital_bucket, currency, provider, provider_account_id, is_active, opened_at, closed_at |
| `decision_drafts` | investment_idea_id (nullable FK) |
| `decision_confirmed_snapshots` | investment_idea_id, review_30d, review_90d, review_1yr, review_outcome |

### 17.3 Tables Deferred to Later Sprints

| Concept | Why Deferred |
|---------|-------------|
| Price history (time series) | Requires market data integration |
| Portfolio performance calculation engine | Requires TWR/MWR decision |
| Tax lot / specific-ID cost basis | Requires tax jurisdiction design |
| External price feed integration | Requires provider authorization |
| Order / execution records | NOT AUTHORIZED (trading) |
| Rebalancing suggestions | Requires Owner policy on rebalancing |
| Benchmark comparison | Requires benchmark data sources |

---

## 18. Event Model

### 18.1 Domain Events (Design Only)

| Event | Trigger | Consumer |
|-------|---------|----------|
| `portfolio.position_imported` | Position rows inserted/updated | Guardian, Audit, Notification |
| `portfolio.transaction_imported` | Transaction rows inserted | Audit |
| `portfolio.snapshot_created` | Existing PortfolioSnapshot created | Notification |
| `policy.version_activated` | Existing PolicyVersion published | Guardian (reload thresholds) |
| `policy.bucket_defined` | PolicyCapitalBucket created | Guardian |
| `investment_idea.submitted` | Idea status → under_review | Committee |
| `investment_idea.approved` | Idea status → approved | Decision Journal |
| `committee.review_completed` | CommitteeReport created | Notification, Decision Journal |
| `guardian.policy_violation_detected` | GuardianEvent created | Notification |
| `owner.decision_recorded` | DecisionConfirmedSnapshot created | Audit |
| `data.quality_warning` | Data staleness detected | Notification |

### 18.2 Integration with Existing Orchestration

Events use the existing `notification_events` table for delivery (Sprint 007).
The Automation worker (Sprint 005) already has schedule-based dispatch.
Sprint 009 does not introduce a new event bus or message queue.

---

## 19. API Boundaries

### 19.1 Proposed Endpoints

| Method | Path | Classification | Sprint |
|--------|------|---------------|--------|
| GET | /api/assets | READ | 009-A |
| POST | /api/assets | OWNER_MUTATION | 009-A |
| GET | /api/assets/{id} | READ | 009-A |
| GET | /api/accounts | READ | 009-A |
| PATCH | /api/accounts/{id} | OWNER_MUTATION | 009-A |
| GET | /api/positions | READ | 009-A |
| GET | /api/positions?account_id=... | READ | 009-A |
| GET | /api/transactions | READ | 009-A |
| GET | /api/cash-balances | READ | 009-A |
| GET | /api/performance | READ | 009-B |
| POST | /api/investment-ideas | OWNER_MUTATION | 009-C |
| GET | /api/investment-ideas | READ | 009-C |
| PATCH | /api/investment-ideas/{id} | OWNER_MUTATION | 009-C |
| POST | /api/investment-ideas/{id}/submit | OWNER_MUTATION | 009-C |
| GET | /api/import/sources | READ | 009-D |
| POST | /api/import/manual/positions | OWNER_MUTATION | 009-D |

### 19.2 Future Connector Endpoints (NOT in Sprint 009)

| Method | Path | Classification |
|--------|------|---------------|
| POST | /api/import/{provider}/accounts | SYSTEM_INTERNAL |
| POST | /api/import/{provider}/positions | SYSTEM_INTERNAL |
| POST | /api/import/{provider}/transactions | SYSTEM_INTERNAL |

---

## 20. UI / Product Information Architecture

### 20.1 Proposed Navigation

```
Overview (dashboard)
├── Portfolio
│   ├── Positions (by account, by asset)
│   ├── Transactions (filterable)
│   ├── Performance (charts, metrics)
│   └── Accounts (manage accounts)
├── Investment Ideas
│   ├── Idea Board (kanban/list)
│   ├── New Idea
│   └── Idea Detail (thesis, committee, decision)
├── Decision Room
│   ├── Pending Decisions
│   ├── Decision History
│   └── Post-Decision Reviews
├── AI Investment Committee (existing /committee)
├── Guardian (existing guardian dashboard)
├── Investment Policy (existing /policy)
├── Automation (existing /automation)
├── Decision Journal (existing /decisions)
└── Settings
    ├── Household (existing /household)
    ├── Notifications (existing)
    └── Data Sources
```

### 20.2 Decision Room Purpose

The Decision Room is the central workspace for making investment decisions:

1. **Context**: Displays current portfolio state, active policy, recent
   Guardian alerts, and pending Committee reviews.

2. **Idea → Decision pipeline**: Owner reviews Investment Ideas, submits
   to Committee, reviews Committee analysis, then records a Decision.

3. **Post-decision review**: Scheduled reviews (30d, 90d, 1yr) appear
   as tasks.  Owner records outcome notes.  Historical rationale is
   preserved and compared against actual outcomes.

4. **Deliberate slowness**: The Decision Room is intentionally designed
   to encourage reflection, not speed.  No one-click trading.  Every
   significant action requires explicit confirmation.

---

## 21. Sprint 009 Implementation Slices

### Slice A — Core Portfolio Schema + Asset Identity

**Scope**:
- Migration 0018: `assets`, `positions`, `cash_balances`, `transactions`,
  `fx_rates`, `data_sources`
- Extend `accounts` table with new columns
- SQLAlchemy models
- Basic CRUD for assets and accounts (API + service + repository)
- Read endpoints for positions, transactions, cash balances
- PostgreSQL constraints and immutability triggers

**Exclusions**: No import logic, no performance, no ideas, no policy rules.

**Merge gate**: Migration applies cleanly.  Existing tests pass.  New
constraint tests pass.  Accounts extension is backward-compatible.

### Slice B — Investment Policy Enrichment

**Scope**:
- Migration 0019: `policy_capital_buckets`, `policy_rules`
- Extend Policy draft/version to include buckets and rules
- Guardian check definitions for bucket drift, concentration
- Performance snapshot table (schema only, no calculation)

**Exclusions**: No performance calculation engine.  No idea model.  
No Committee changes.

**Merge gate**: Policy versioning still works.  Bucket/rule snapshot on
publish.  Guardian check definitions createable.

### Slice C — Investment Idea + Decision Journal Bridge

**Scope**:
- Migration 0020: `investment_ideas`, `idea_status_history`
- Investment Idea CRUD API
- Idea lifecycle state machine with status transitions
- Decision Journal extensions: `investment_idea_id` FK, review scheduling
- Committee evidence pipeline extracts idea data

**Exclusions**: No automated idea approval.  No execution.  No performance
calculation.

**Merge gate**: Full idea lifecycle testable.  Decision→Idea link preserved.
Committee can receive ideas as evidence source.

### Slice D — Manual Import + Data Source Foundation

**Scope**:
- Manual position/transaction import (CSV or form-based)
- DataSource activation/deactivation
- Import idempotency (source + source_record_id uniqueness)
- Asset resolution on import (ISIN match → symbol/exchange match → create)
- Provider interface definitions (Protocol classes, no implementations)

**Exclusions**: No real broker connection.  No OAuth.  No automated import.
No live API calls.

**Merge gate**: Manual import creates positions with correct provenance.
Duplicate imports are idempotent.  Asset resolution works correctly.
Provider interfaces are documented and type-checked.

---

## 22. Test Strategy

### 22.1 Schema Tests (PostgreSQL required)

| Test | What it proves |
|------|---------------|
| `uq_assets_isin` prevents duplicate ISIN | Canonical identity |
| `uq_positions_source_record` prevents duplicate import | Idempotency |
| `ck_positions_source` rejects invalid sources | Data integrity |
| `ck_fx_rates_different` rejects same-currency rates | Currency safety |
| Account extension backward-compatible (existing rows get defaults) | Migration safety |
| Policy bucket snapshot on publish (immutable after) | Version immutability |
| Idea status transition valid (draft→under_review ok, draft→approved blocked) | Lifecycle enforcement |
| Position `is_latest` toggle in transaction | Point-in-time history |

### 22.2 Currency Tests

| Test | What it proves |
|------|---------------|
| Multi-currency position storage (USD, HKD, CNY) | Currency support |
| Cross-currency comparison blocked without conversion | Safety |
| FX rate lookup by timestamp | Historical accuracy |

### 22.3 Provenance Tests

| Test | What it proves |
|------|---------------|
| Position source preserved on import | Traceability |
| CompoundOS-derived values never overwrite provider values | Data integrity |
| AuditEvent created on position import | Audit trail |

### 22.4 Integration Tests

| Test | What it proves |
|------|---------------|
| Full idea→committee→decision lifecycle | End-to-end |
| Guardian bucket drift detection with positions | Guardian integration |
| Policy publication consumes draft buckets/rules | Policy versioning |
| Manual import idempotency (double import = no duplicates) | Data safety |

---

## 23. Architecture Decision Records (ADRs)

### Recommended ADRs

| ADR | Topic | Status |
|-----|-------|--------|
| ADR-0007 | Canonical Asset Identity Model | Proposed |
| ADR-0008 | Multi-Currency Financial Data Architecture | Proposed |
| ADR-0009 | Financial Data Provenance and Source Attribution | Proposed |
| ADR-0010 | AI Authority Matrix for Financial Operations | Proposed |
| ADR-0011 | Read-Only Provider Connector Architecture | Proposed |

### ADR-0007 Summary: Asset Identity
ISIN is the primary canonical identifier.  Where ISIN is absent, (symbol,
exchange, currency) tuple provides identity.  Manual-entry assets without
identifiers are permitted but flagged as unverified.  Asset merges require
Owner action.

### ADR-0008 Summary: Multi-Currency
Every monetary column carries an explicit currency column.  Base reporting
currency is defined in HouseholdProfile.  Portfolio aggregation converts to
base currency using the most recent FX rate at or before the valuation
timestamp.  Never silently mix currencies.

### ADR-0009 Summary: Provenance
Every imported financial datum carries source, source_record_id, observed_at,
and imported_at.  Four data categories (provider_fact, compoundos_calculation,
ai_inference, owner_input) are never mixed.  Derived values are tagged as
compoundos_derived.

### ADR-0010 Summary: AI Authority
Sixteen actions classified across four authority levels.  AI may read,
analyze, and recommend but never modify policy, approve decisions, place
trades, or transfer funds.  Enforcement at API, service, and database layers.

### ADR-0011 Summary: Connectors
Provider adapters implement Protocol interfaces.  All connectors are read-only
in V1.  Asset resolution is provider-agnostic.  Import idempotency enforced
by (source, source_record_id) uniqueness.

---

## 24. Risks and Unresolved Decisions

### Owner Decisions Required

| ID | Decision | Options |
|----|----------|---------|
| OD-9-1 | Asset identity: ISIN-primary or (symbol, exchange) primary? | RECOMMEND: ISIN primary with (symbol, exchange) fallback |
| OD-9-2 | Capital bucket names: free-text or constrained enum? | RECOMMEND: Constrained enum (CORE/EXPLORATION/CASH_RESERVE/RETIREMENT/OTHER) with future extensibility |
| OD-9-3 | Performance calculation method: TWR or MWR? | RECOMMEND: TWR for portfolio-level, defer MWR |
| OD-9-4 | Slicing: implement all four slices in Sprint 009, or Slice A only? | RECOMMEND: All four slices in Sprint 009 (they form a coherent foundation) |
| OD-9-5 | Investment Idea → Decision Journal bridge: auto-create Draft or manual? | RECOMMEND: Optional auto-create (Owner checkbox) but never auto-confirm |
| OD-9-6 | Manual CSV import format: define now or defer? | RECOMMEND: Define in Slice D; simple CSV with named columns |
| OD-9-7 | Post-decision review scheduling: 30d/90d/1yr or configurable? | RECOMMEND: 30d/90d/1yr as defaults, configurable per idea |

### Architectural Risks

| Risk | Mitigation |
|------|-----------|
| Position `is_latest` toggling could miss rows under concurrent writes | Use SELECT...FOR UPDATE on (account_id, asset_id) when toggling |
| Asset identity collisions (same ISIN, different names) | Owner-managed merge; system flags duplicates |
| FX rate gaps (no rate for a specific timestamp) | Use most recent rate before timestamp; flag gaps |
| Policy rules becoming too complex for TEXT JSON values | Future migration to JSONB with path indexing if needed |
| Performance calculation method changes invalidate historical data | Store method version alongside computed values; recompute on method change |

---

## 25. Existing Backlog (Preserved)

| ID | Description | Status |
|----|-------------|--------|
| M1 | Schedule DELETE confirmation | Not addressed |
| M2 | Lazy GET schedule seed | Not addressed |
| M3 | validate_lease clock parameter | Not addressed |
| L1 | Schedule allowlist drift protection | Not addressed |
| TECH-001 | Frontend npm audit failure | Not addressed |
| OM-001 | Orchestration corrective cleanup | Not addressed |
| SEC-001 | Repository PRIVATE before real financial integration | Preserved — P0 gate |

---

## 26. Absolute Exclusions (Sprint 009)

- No trading, order placement, or execution
- No broker/bank API connections (HSBC, IB, Schwab)
- No real financial credentials
- No real portfolio data in the repository
- No automatic rebalancing
- No performance calculation engine (schema only)
- No external market data integration
- No cloud deployment
- No multi-user authentication
- No repository visibility change
- No modification of Guardian thresholds
- No `backup.daily` execution implementation

---

*This Technical Design is submitted for Owner review.  No implementation is
authorized until approval of this document and individual slice authorization.*
