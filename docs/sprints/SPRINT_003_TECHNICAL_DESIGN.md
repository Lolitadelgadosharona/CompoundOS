# Sprint 003 Technical Design: Portfolio Snapshot + Holdings Foundation

- Date: 2026-07-17
- Status: Approved Technical Design — Implementation Not Authorized
- Owner Decisions: All 15 Resolved by Project Owner on 2026-07-17
- Baseline: main @ 3c5edec
- Branch: planning/sprint-003-portfolio-foundation

## 1. Product Boundary

### What "Portfolio" means in CompoundOS

A Portfolio is the sole household's record of what it holds at a point in time.
It is user-entered, user-valued, and immutable once confirmed. It is not a live
balance, not a broker view, and not a trading blotter.

### Included

- One Portfolio per Household
- User-entered asset names, quantities, and unit prices
- Computed total_value = quantity × unit_price (authoritative)
- User-entered valuation date
- Immutable Confirmed Snapshots with full holding detail
- Draft → Confirm lifecycle
- Atomic Draft discard (identity deletion for never-Confirmed)
- Portfolio-filtered AuditEvent timeline
- Asset category as optional user label (no regulatory classification)

### Explicitly Excluded

- Real-time or delayed market data
- Automatic price updates from any source
- Broker synchronization or read-only broker views
- Actual trading, order placement, or execution
- Rebalancing recommendations
- Performance or return calculations (IRR, TWR, etc.)
- Tax lots, cost basis, realized/unrealized gains
- Suitability, eligibility, ranking, or scoring
- Guardian threshold detection or alert logic
- AI-generated holdings or classifications
- Multi-household or multi-tenancy
- Authentication or public deployment
- Foreign exchange or multi-currency conversion

---

## 2. Data Model — Three Approaches Compared

### Approach A: Current Mutable Holdings

A single `portfolio_holdings` table with mutable rows. No history.
Simple but non-auditable. Rejected — violates the "explainable" principle.

### Approach B: Immutable Portfolio Snapshots Only

Every recording is a new snapshot row with its own holdings. Always append.
Correction means a new snapshot. Simple, auditable. Rejected — no draft
workflow for user editing, and "correction by new snapshot" conflates distinct
intents.

### Approach C: Stable Identity + Draft + Immutable Snapshot (RECOMMENDED)

Reuses the proven Policy/Decision pattern:

- `portfolios` — stable identity row (one per household)
- `portfolio_drafts` — mutable working state (at most one)
- `portfolio_draft_holdings` — mutable holding rows under draft (ON DELETE CASCADE)
- `portfolio_snapshots` — immutable confirmed point-in-time record
- `portfolio_snapshot_holdings` — immutable holding rows under snapshot (RESTRICT FK)

This provides: draft workflow for editing, atomic confirm consuming draft,
immutable audit trail, identity stability, and reusable trigger patterns from
ADR 0003 and ADR 0005.

### Tables

```
portfolios
  id UUID PK
  household_id UUID FK → household_profiles (UNIQUE, one per household)
  status VARCHAR CHECK(draft|active)
  created_at TIMESTAMPTZ

portfolio_drafts
  portfolio_id UUID PK+FK → portfolios (ON DELETE CASCADE)
  expected_revision INTEGER DEFAULT 1
  valuation_date DATE CHECK(<= CURRENT_DATE)
  notes TEXT
  updated_at TIMESTAMPTZ

portfolio_draft_holdings
  id UUID PK
  portfolio_id UUID FK → portfolio_drafts (ON DELETE CASCADE)
  asset_name VARCHAR(500)
  asset_category VARCHAR(200)
  quantity NUMERIC(20,8) CHECK(> 0)
  unit_price NUMERIC(20,4) CHECK(>= 0)
  total_value NUMERIC(20,2) — COMPUTED on insert/update = quantity × unit_price
  valuation_date DATE CHECK(<= CURRENT_DATE)
  notes TEXT
  sort_order INTEGER DEFAULT 0

portfolio_snapshots
  id UUID PK
  portfolio_id UUID FK → portfolios (RESTRICT)
  version_number INTEGER (per-portfolio sequential, UNIQUE with portfolio_id)
  confirmed_at TIMESTAMPTZ
  holding_count INTEGER CHECK(>= 0)
  valuation_date DATE CHECK(<= CURRENT_DATE)
  notes TEXT
  — BEFORE INSERT/UPDATE/DELETE trigger prohibits all modification

portfolio_snapshot_holdings
  id UUID PK
  snapshot_id UUID FK → portfolio_snapshots (RESTRICT)
  asset_name VARCHAR(500)
  asset_category VARCHAR(200)
  quantity NUMERIC(20,8)
  unit_price NUMERIC(20,4)
  total_value NUMERIC(20,2)
  valuation_date DATE
  notes TEXT
  sort_order INTEGER
  — BEFORE INSERT/UPDATE/DELETE trigger prohibits all modification
```

### Named Constraints

- `ck_portfolio_draft_holdings_quantity_positive`: quantity > 0
- `ck_portfolio_draft_holdings_price_nonnegative`: unit_price >= 0
- `ck_portfolio_draft_valuation_date`: valuation_date <= CURRENT_DATE (draft)
- `ck_portfolio_snapshot_valuation_date`: valuation_date <= CURRENT_DATE (snapshot)
- `uq_portfolios_household`: UNIQUE(household_id) — at most one Portfolio
- `uq_snapshot_version`: UNIQUE(portfolio_id, version_number)
- `fk_draft_holdings_draft_cascade`: ON DELETE CASCADE — atomic discard
- `fk_snapshot_holdings_snapshot_restrict`: ON DELETE RESTRICT — immutable

### PL/pgSQL Triggers

- `fn_portfolio_snapshot_immutability`: BEFORE INSERT OR UPDATE OR DELETE —
  prohibits all UPDATE and DELETE on snapshots and snapshot_holdings
- `fn_portfolio_draft_consistency`: DEFERRED CONSTRAINT TRIGGER — verifies at
  COMMIT that draft state (portfolio_drafts row) has at least one holding when
  status transitions from draft to active (pending OD-S3-011)
- `fn_portfolio_lifecycle`: BEFORE UPDATE on portfolios — permits only
  draft→active transition

---

## 3. Asset Fields

### Required Fields per Holding (pending OD-S3-005/006)

| Field | Type | Constraint | Notes |
|-------|------|------------|-------|
| asset_name | VARCHAR(500) | NOT NULL, trimmed | User-defined; no symbol validation |
| quantity | NUMERIC(20,8) | > 0 | Fractional quantities allowed |
| unit_price | NUMERIC(20,4) | >= 0 | User-entered; zero allowed for unknown |
| total_value | NUMERIC(20,2) | COMPUTED | quantity × unit_price (authoritative per OD-S3-006 B) |

### Optional Fields

| Field | Type | Notes |
|-------|------|-------|
| asset_category | VARCHAR(200) | User label; not validated against enum |
| valuation_date | DATE | Per-holding override; defaults to draft snapshot date |
| notes | TEXT | Free text; no financial interpretation |

### Cash Position (OD-S3-012)

Cash is treated as a holding with asset_name = "Cash" or equivalent.
No special cash table or separate treatment. If the user records no
holdings, the confirmed snapshot reflects that state. Note: a zero-holding
confirmed snapshot means "no recorded assets" — this is distinct from
explicitly recording a Cash holding. The UI should make this distinction
clear.

### Private Assets (OD-S3-013)

Any asset name is accepted. No regulatory classification, no validation
against exchange listings. "Private" is just an asset_category label.

---

## 4. Currency and Precision

### Single Currency (OD-S3-008)

The Portfolio uses the Household's `base_currency` (three-letter ISO code,
stored in `household_profiles.base_currency`). No conversion, no exchange
rate, no multi-currency support in MVP.

### Precision Rules

| Value | PostgreSQL | Python | API |
|-------|-----------|--------|-----|
| quantity | NUMERIC(20,8) | Decimal | Decimal string |
| unit_price | NUMERIC(20,4) | Decimal | Decimal string |
| total_value | NUMERIC(20,2) | Decimal (computed) | Decimal string |

total_value is computed as quantity × unit_price then rounded to 2 decimal
places (cents) using ROUND_HALF_EVEN or Decimal quantization. This is
intentional currency rounding (to cents), not IEEE 754 floating-point
error. The Policy "no silent rounding" principle was about avoiding binary
floating-point artifacts; currency rounding to cents is explicit and
deterministic. API values remain decimal strings matching the stored
precision.

---

## 5. Lifecycle

### States

```
  [No Portfolio] → Create Draft → [Draft exists]
                                      ↓
                              Edit Draft (revision++)
                              Add/Remove/Reorder Holdings
                                      ↓
                              Confirm → [Active, Snapshot v1]
                                      ↓
                              Create new Draft → [Draft + Active]
                                      ↓
                              Confirm → [Active, Snapshot v2]
                                      ↓
                              (repeat)
```

### Draft

- At most one Draft at any time
- Creation: POST /api/portfolio/draft
- Update metadata: PATCH with expected_revision
- Replace holdings: PUT holdings collection with expected_revision
- Discard: atomic DELETE of Draft identity (OD-S3-13 from Sprint 002 pattern)
  — only allowed when no prior Confirmed snapshot exists

### Confirm

- Requires expected_revision
- Consumes Draft (deletes draft + draft_holdings)
- Inserts portfolio_snapshot + snapshot_holdings in same transaction
- Sets portfolio.status = active
- Portfolio → Draft lock ordering
- Response built from transaction-scoped data

### No Supersession, Archive, or Correction

Unlike Policy Versions (which supersede) and Decisions (which archive),
Portfolio Snapshots are discrete independent records. Each Confirm creates
a new Snapshot. The previous Snapshot is unchanged. This avoids:
- "current snapshot" semantics ambiguity
- Supersession race conditions
- Archive lifecycle complexity

### Discard

Two scenarios:

**(a) Discard before any Confirmed snapshot:**
Atomic identity deletion — both portfolio_drafts and portfolio rows deleted.
The portfolio_id is removed entirely (matching Decision Draft discard pattern
from OD-S3-13). Only allowed when no portfolio_snapshots row exists.

**(b) Discard while Confirmed snapshots exist:**
Delete draft + draft_holdings only. Portfolio identity persists (status stays
`active`). Latest Confirmed snapshot remains the current state. This is the
common case: "I started Draft v3, changed my mind, keep what was Confirmed."

---

## 6. Single Household and Portfolio

- One Portfolio per Household (OD-S3-003 A)
- Portfolio created automatically with first Draft (or explicit create)
- No "delete portfolio" endpoint — immutable history
- No portfolio rename in MVP

### Account Entity (OD-S3-004)

Recommendation B: Optional user-named Account labels as a local logical
container. If accepted:
- `accounts` table: id, portfolio_id, name, notes, sort_order
- `portfolio_draft_holdings.account_id` (nullable FK)
- Account is never a financial account — no institution, no number, no
  credentials. Pure user labeling.

If rejected (Option A), holdings are flat under Portfolio with no grouping.

---

## 7. API Design (Proposed — Not Implemented)

All endpoints under `/api/portfolio`. Decimal strings for all numeric values.
expected_revision on all mutations. 409 on revision conflict or lifecycle
error. 404 for missing resources. 422 for validation failures.

| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/portfolio/draft | Create Draft. 201 for new, 200 with existing Draft data if already exists (idempotent). 422 for validation failures. |
| GET | /api/portfolio | Current state: draft + latest snapshot |
| PATCH | /api/portfolio/draft | Update draft metadata |
| PUT | /api/portfolio/draft/holdings | Atomic replace holding collection |
| POST | /api/portfolio/draft/confirm | Confirm Snapshot |
| POST | /api/portfolio/draft/discard | Discard Draft |
| GET | /api/portfolio/snapshots | Cursor-paginated history (newest first, default 20, max 100) |
| GET | /api/portfolio/snapshots/{id} | Snapshot detail with holdings |
| GET | /api/portfolio/audit | Cursor-paginated audit (before_sequence_number, limit) |

### Response Snapshots

Following the Slice 2B PATCH pattern: all response data is materialized from
scalar values inside the locked transaction. No post-commit database queries.
The service returns a DTO built before commit.

### Lock Order

When touching multiple rows: Household → Portfolio → Draft.
For Draft mutations (update metadata, replace holdings, confirm, discard):
lock Portfolio row FOR UPDATE, then lock Draft row FOR UPDATE.
For Snapshot version numbering: lock Portfolio row,
SELECT MAX(version_number) FROM portfolio_snapshots (under the same
locked transaction), compute next version, then insert Snapshot.
Version numbering is safe because the Portfolio row lock serializes
all Confirms. This matches the Policy→Decision→Draft pattern from Slice 3B.

---

## 8. PostgreSQL Design

### Migration

New Alembic revision `0004_portfolio_foundation` (or next available).
Creates tables, constraints, triggers, and indices. Empty database upgrade
must succeed. Downgrade provided for development.

### Triggers

- `fn_portfolio_snapshot_immutability`: BEFORE INSERT OR UPDATE OR DELETE on
  portfolio_snapshots and portfolio_snapshot_holdings — REJECT UPDATE/DELETE
- `fn_portfolio_draft_consistency`: DEFERRED CONSTRAINT TRIGGER — at COMMIT,
  verify draft state consistency
- `fn_portfolio_lifecycle`: BEFORE UPDATE on portfolios — draft↔active only

### Indices

- `portfolios.household_id` (unique)
Snapshot version_number starts at 1 for the first Confirmed snapshot and
increments by 1 per Confirm, computed as MAX(version_number) + 1 under
Portfolio row lock. There are no gaps (unless a Confirm transaction
rolls back — in which case the sequence_number gap in audit_events
records the attempt).
- `portfolio_draft_holdings(portfolio_id, sort_order)`
- `portfolio_snapshot_holdings(snapshot_id, sort_order)`

### AuditEvent

Reuses existing `audit_events` table with `sequence_number`.
Entity type: `portfolio`. No new migration for audit — the table supports it.

---

## 9. Concurrency and Transactions

| Scenario | Protection |
|----------|-----------|
| Two Draft creates | Singleton constraint on portfolio |
| Two holding replacements | expected_revision conflict |
| Confirm vs. update | expected_revision conflict |
| Confirm vs. Discard | Portfolio row lock → status check |
| Double Confirm | expected_revision + status check |
| Snapshot version numbering | Portfolio row lock + MAX(version_number)+1 |

All writes use `FOR UPDATE` on Portfolio row. PostgreSQL READ COMMITTED
provides statement-level snapshot isolation. Explicit row locks prevent
lost updates. All business writes and AuditEvent inserts share one
transaction — commit or rollback together.

---

## 10. AuditEvent

### Action Names (proposed)

| Action | Trigger |
|--------|---------|
| portfolio.draft.created | POST /api/portfolio/draft |
| portfolio.draft.updated | PATCH metadata or PUT holdings |
| portfolio.draft.discarded | POST discard |
| portfolio.snapshot.confirmed | POST confirm |

### Metadata Allowlist

| Field | Included |
|-------|----------|
| changed_fields | Yes (for updates) |
| draft_revision | Yes |
| snapshot_version_number | Yes |
| holding_count | Yes |
| asset names | NO |
| quantities | NO |
| prices | NO |
| total values | NO |
| user notes | NO |

Metadata is redacted — no financial values or user text in audit events.
This matches the Policy and Decision audit patterns.

### Household Timeline

The existing Household audit endpoint scope must be decided per OD-S3-014:
either it returns all entity types (Household, Policy, Decision, Portfolio)
for the household, or portfolio events are only available via
GET /api/portfolio/audit. This design proposes the inclusive option
(all types visible) because the Household timeline already includes
Policy and Decision events per Slice 2C and 3C.

---

## 11. UI Design (Proposed States — Not Implemented)

Based on the Policy and Decision frontend patterns:

1. **Loading** — initial portfolio fetch, skeleton or spinner
2. **No Household** — link to /household, cannot create portfolio
3. **Empty Portfolio** — no draft, no snapshots — "Create your first portfolio snapshot"
4. **Draft Editor** — metadata (valuation_date, notes) + holdings table
5. **Holding Editor** — add/remove rows, asset_name, quantity, unit_price
   inputs with decimal string validation
6. **Holding Validation** — quantity > 0, price >= 0, in-line errors
7. **Confirm Review** — read-only review of saved draft snapshot
8. **Confirm** — explicit confirmation button, dirty-state gate
9. **Current Snapshot** — latest confirmed snapshot with holdings table
10. **Snapshot History** — cursor-paginated list (newest first)
11. **Snapshot Detail** — read-only with holdings
12. **Audit Timeline** — portfolio-filtered audit events
13. **409 Conflict** — ConflictPanel with reload button
14. **404 / Network Error** — neutral error display, retry option
15. **Dirty State** — unsaved changes block Confirm; reload confirmation dialog
16. **Discard** — confirmation prompt, only when no prior snapshot
17. **Local-Only Notice** — "CompoundOS runs locally. Your data stays on your machine."
18. **Non-Advice Notice** — "Portfolio snapshots are your own records. Nothing here is advice."

### Non-Goals

- No autosave
- No default asset names, categories, or allocations
- No market price lookup or ticker validation
- No chart, graph, or visualization
- No CSV or spreadsheet import
- No export

---

## 12. Data Privacy

### Principles

- Financial data is sensitive. CompoundOS remains local-only.
- No authentication means NO public deployment with portfolio data.
- Local development is the only supported mode.

### What Is NOT Recorded

- Brokerage account numbers
- Routing numbers
- Login credentials or API keys
- Passwords or tokens
- Tax identifiers (SSN, EIN, etc.)
- Physical addresses
- Bank names or institution identifiers (unless user enters as asset name)

### Audit Metadata

Audit events contain zero financial values. Only structural metadata
(changed_fields, revision, version_number, holding_count).

### Deferred to Production

- Encryption at rest
- Backup automation
- Export/import
- Data retention policy
- Right to deletion
- Multi-user access control
- Audit log integrity verification

---

## 13. Test Matrix

| Category | Slice | Tests |
|----------|-------|-------|
| Schema/API | B | Pydantic validation, decimal string format, currency, unicode limits |
| PostgreSQL | A | Real database: constraints, triggers, deferred consistency, trigger inspection |
| Migration | A | upgrade head, downgrade, re-upgrade, offline SQL |
| Bypass regression | A | Cross-table mutations, cross-transaction updates, direct SQL bypass of triggers |
| Decimal precision | B | NUMERIC(20,8) × NUMERIC(20,4) = NUMERIC(20,2), cents rounding |
| Currency | B | ISO 4217 validation, single-currency enforcement |
| Singleton | B | One portfolio, one draft, double-create rejection |
| Draft lifecycle | B | create, update, holding replace, confirm, discard (both scenarios) |
| Immutable Snapshot | A | UPDATE/DELETE rejected via trigger; direct SQL bypass test |
| Transactions | B | Commit together, rollback on failure, session reuse |
| Concurrency | B | Double confirm, confirm vs discard, holding replace race, version numbering |
| Audit ordering | B | sequence_number ascending, entity_type filter |
| Pagination | B | Cursor stability, window boundaries, has_more |
| Frontend states | C | All 18 UI states (Vitest, React Testing Library or similar) |
| Accessibility | C | aria-labels, keyboard navigation, screen reader |
| Localhost | C | CORS origin check, no public binding |
| Docker | C | compose up, browser path validation |
| Secret scan | All | No credentials, keys, or tokens in codebase |

---

## 14. Implementation Slices

Each slice requires separate explicit Owner authorization.
Naming uses "Sprint 003 Slice A/B/C" to avoid confusion with
Sprint 002 Slice 3A/3B/3C.

### Sprint 003 Slice A: Portfolio Persistence and Immutability Foundation

- Alembic migration creating portfolio tables, constraints, triggers
- SQLAlchemy ORM models
- Named CHECK and UNIQUE constraints
- Immutability triggers on snapshots and snapshot_holdings
- Deferred consistency trigger
- AuditEvent sequence_number integration
- Real PostgreSQL tests only
- NO service, repository, API, or frontend

### Sprint 003 Slice B: Portfolio Backend Workflow and API

- Pydantic request/response schemas with decimal string contracts
- Repository queries with FOR UPDATE support
- Service transaction boundaries with lock ordering
- All API endpoints under /api/portfolio
- Concurrency tests, rollback tests, revision conflict tests
- Portfolio-filtered AuditEvent reads
- NO frontend

### Sprint 003 Slice C: Portfolio Frontend Workflow

- /portfolio page with all 18 UI states
- Typed Portfolio API client
- Draft editor with holding management
- Confirm review and confirmation
- Snapshot history and detail
- Audit timeline
- Accessibility and non-advice notices
- Vitest tests covering all states

---

## Owner Decision Status

All 15 Owner Decisions (OD-S3-001 through OD-S3-015) are documented in
`docs/sprints/SPRINT_003_OPEN_QUESTIONS.md`. This Technical Design reflects
the RECOMMENDED options but does NOT resolve them. Every section above that
depends on an Owner Decision is marked with the relevant OD reference.

**This design does not authorize implementation.** Each slice requires
separate authorization after Owner Decisions are resolved.
