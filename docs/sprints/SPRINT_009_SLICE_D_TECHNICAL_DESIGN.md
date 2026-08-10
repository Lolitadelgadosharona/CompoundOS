# Sprint 009 Slice D — Technical Design
# Manual Import + Data Source Foundation

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Slice A (Core Portfolio Schema): DONE — merged 2026-08-10 (9f0ed00, PR #78)
> Slice B (Investment Policy Enrichment): DONE — merged 2026-08-10 (4a7312c, PR #79)
> Slice C (Investment Idea + Decision Bridge): DONE — merged 2026-08-10 (f87e4e8, PR #80)
> Slice D (Manual Import + Data Source Foundation): DESIGN ONLY
>
> This document defines the architecture for manual financial data import.

---

## 1. Objective

Allow CompoundOS to safely ingest Owner financial data via manual CSV import,
establishing the data provenance foundation that will later serve automated
broker connectors.

**This is NOT:**
- Broker connection (HSBC, Interactive Brokers, Schwab)
- Automated trading
- Live API calls
- Credential storage

**This IS:**
- Manual CSV import foundation
- Data provenance preservation
- Validation and quality control
- Idempotent import safety
- Future connector interface definitions (Protocol classes only)

---

## 2. What Already Exists (Slice A Foundation)

Slice A (migration 0018) provides the complete ingestion target schema:

| Table | Ingested Entity | Uniqueness | Point-in-Time |
|---|---|---|---|
| `accounts` | Account metadata | PK only | N/A |
| `assets` | Instrument identity | ISIN, (symbol,exchange,currency) | N/A |
| `positions` | Account × asset holdings | (source, source_record_id) | is_latest toggle |
| `cash_balances` | Cash per account per currency | (source, source_record_id) | is_latest toggle |
| `transactions` | Financial events | (source, source_record_id) | immutable |
| `data_sources` | Provider registry | source_key | N/A |

All financial tables carry provenance columns:

| Column | Purpose |
|---|---|
| `source` | Which provider/system (e.g. 'csv', 'manual', 'interactive_brokers') |
| `source_record_id` | Provider's internal identifier |
| `observed_at` | When the provider observed/reported this datum |
| `imported_at` | When CompoundOS ingested it |

**Slice D does NOT create new tables or alter the schema.** It builds the
import pipeline on top of the existing Slice A schema.

---

## 3. Architecture Overview

### 3.1 Import Pipeline

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌───────────┐    ┌───────┐
│ Upload  │ →  │ Parse   │ →  │ Validate │ →  │ Normalize │ →  │ Store │
│  CSV    │    │  rows   │    │  rules   │    │  assets   │    │  DB    │
└─────────┘    └─────────┘    └──────────┘    └───────────┘    └───────┘
     │              │              │                │               │
     │         ┌────┴────┐    ┌───┴────┐      ┌────┴────┐     ┌───┴───┐
     │         │Reject   │    │Quality │      │Create   │     │Audit  │
     │         │malformed│    │report  │      │assets   │     │event  │
     │         └─────────┘    └────────┘      └─────────┘     └───────┘
```

At every stage, errors are collected — never silently dropped. The import
succeeds only when all rows pass validation, or the Owner explicitly accepts
warnings.

### 3.2 Layer Responsibilities

| Layer | File | Responsibility |
|---|---|---|
| Router | `apps/api/routers/imports.py` | HTTP endpoint, file upload, response |
| Service | `apps/api/services/import_service.py` | Orchestration, transaction boundary, audit |
| Parser | `apps/api/importers/csv_parser.py` | CSV → list[ParsedRow] with column mapping |
| Validator | `apps/api/importers/validators.py` | Field-level and row-level validation rules |
| Normalizer | `apps/api/importers/asset_resolver.py` | Asset identity resolution (ISIN → symbol → create) |
| Repository | `apps/api/repositories/portfolio_foundation.py` | Existing CRUD (extended with upsert) |
| Interfaces | `apps/api/importers/protocols.py` | Provider-agnostic Protocol classes (no impl) |

---

## 4. CSV Format Specification

### 4.1 Position Import Format

```
source_record_id,account_provider_id,symbol,exchange,isin,name,asset_type,currency,quantity,avg_cost,market_price,observed_at
IB-001,IB-U1234567,AAPL,NASDAQ,US0378331005,Apple Inc.,STOCK,USD,100,150.50,175.25,2026-08-09T16:00:00Z
CSV-001,HK-8881234,0700,HKEX,,Tencent Holdings Ltd,STOCK,HKD,500,320.00,335.00,2026-08-09T16:00:00Z
```

| Column | Required | Format | Notes |
|---|---|---|---|
| `source_record_id` | Yes | Text | Provider's unique ID for this record |
| `account_provider_id` | Yes | Text | Matches `accounts.provider_account_id` |
| `symbol` | Yes | Text | Ticker symbol |
| `exchange` | No | Text | Exchange code (e.g. NASDAQ, HKEX) |
| `isin` | No | Text | ISIN identifier |
| `name` | No | Text | Display name |
| `asset_type` | No | Text | One of: ETF, STOCK, BOND, CASH, MONEY_MARKET, FUND, OTHER |
| `currency` | Yes | Text | ISO 4217 (3 chars) |
| `quantity` | Yes | Decimal | Must be ≥ 0 |
| `avg_cost` | No | Decimal | Average cost basis |
| `market_price` | No | Decimal | Current market price |
| `observed_at` | Yes | ISO 8601 | Provider observation timestamp |

### 4.2 Transaction Import Format

```
source_record_id,account_provider_id,symbol,exchange,isin,transaction_type,quantity,price,amount,currency,executed_at,observed_at
IB-TXN-1,IB-U1234567,AAPL,NASDAQ,US0378331005,BUY,50,150.00,7500.00,USD,2026-07-15T10:30:00Z,2026-08-09T16:00:00Z
```

| Column | Required | Format | Notes |
|---|---|---|---|
| `source_record_id` | Yes | Text | Unique ID |
| `account_provider_id` | Yes | Text | Matches accounts |
| `symbol` | No | Text | Null for cash transactions |
| `exchange` | No | Text | |
| `isin` | No | Text | |
| `transaction_type` | Yes | Text | BUY, SELL, DIVIDEND, INTEREST, DEPOSIT, WITHDRAWAL, FEE, TRANSFER_IN, TRANSFER_OUT, OTHER |
| `quantity` | No | Decimal | Null for cash-only transactions |
| `price` | No | Decimal | Per-unit price |
| `amount` | No | Decimal | Total transaction amount |
| `currency` | Yes | Text | ISO 4217 |
| `executed_at` | Yes | ISO 8601 | When the transaction occurred |
| `observed_at` | Yes | ISO 8601 | When imported/observed |

### 4.3 Cash Balance Import Format

```
source_record_id,account_provider_id,currency,amount,observed_at
BAL-001,IB-U1234567,USD,25000.50,2026-08-09T16:00:00Z
BAL-002,HK-8881234,HKD,150000.00,2026-08-09T16:00:00Z
```

| Column | Required | Format | Notes |
|---|---|---|---|
| `source_record_id` | Yes | Text | Unique ID |
| `account_provider_id` | Yes | Text | Matches accounts |
| `currency` | Yes | Text | ISO 4217 |
| `amount` | Yes | Decimal | Current balance |
| `observed_at` | Yes | ISO 8601 | Observation timestamp |

---

## 5. Validation Rules

### 5.1 Field-Level Validation

| Rule | Check | Error Severity |
|---|---|---|
| `currency_format` | `^[A-Z]{3}$` | ERROR |
| `asset_type_valid` | Must be in approved list | ERROR |
| `transaction_type_valid` | Must be in approved list | ERROR |
| `quantity_non_negative` | quantity ≥ 0 | ERROR |
| `decimal_parse` | Valid Decimal coercion | ERROR |
| `iso8601_parse` | Valid datetime parse | ERROR |
| `symbol_clean` | No leading/trailing whitespace, ≤ 20 chars | WARNING |
| `isin_format` | If provided, 12 alphanumeric chars | WARNING |

### 5.2 Row-Level Validation

| Rule | Check | Error Severity |
|---|---|---|
| `account_exists` | account_provider_id matches an existing account | ERROR |
| `asset_identity` | At minimum symbol is provided (ISIN preferred) | ERROR |
| `duplicate_record` | (source, source_record_id) not already imported | WARNING (skip) |
| `observed_not_future` | observed_at ≤ now() | WARNING |
| `quantity_gt_zero` | For BUY/SELL: quantity > 0 | ERROR |
| `amount_gt_zero` | For non-BUY/SELL with amount: amount > 0 | ERROR |

### 5.3 Cross-Row Validation (Batch-Level)

| Rule | Check | Error Severity |
|---|---|---|
| `no_duplicate_in_batch` | source_record_id unique within batch | ERROR |
| `consistent_account_currency` | All rows for same account use consistent currency | WARNING |

### 5.4 Error Classification

| Severity | Import Behavior |
|---|---|
| ERROR | Import rejected entirely (rollback) |
| WARNING | Import proceeds; warnings reported in response |
| INFO | No action; diagnostic for future quality review |

---

## 6. Asset Resolution Strategy

When a CSV row references an asset, the resolver follows this sequence:

```
1. ISIN match (exact)
   └─ Found → use existing Asset
   └─ Not found → proceed to step 2

2. (symbol, exchange, currency) match (normalized)
   └─ Found → use existing Asset, link ISIN if provided
   └─ Not found → proceed to step 3

3. Create new Asset with:
   - source = 'csv'
   - All available identity fields from CSV
   - No ISIN → partial identity asset
   └─ Return new Asset

4. Owner can later merge/verify assets via manual curation
   (NOT in Sprint 009)
```

**Normalization rules:**
- Symbol: uppercase, strip whitespace
- Exchange: uppercase, map common aliases (e.g. "NASDAQ" ↔ "XNAS")
- ISIN: uppercase, strip whitespace

---

## 7. Import Idempotency

### 7.1 Duplicate Detection

Every importable entity already has a `(source, source_record_id)` partial
unique index (Slice A). The importer uses this:

| Entity | Dedup Strategy |
|---|---|
| Position | `uq_positions_source_record` — re-import updates via upsert |
| Transaction | `uq_transactions_source_record` — skip duplicates silently |
| Cash Balance | `uq_cash_balances_source_record` — re-import updates via upsert |

### 7.2 Position Upsert Logic

When a position with the same `(source, source_record_id)` is re-imported:

1. Lock the existing row with `SELECT ... FOR UPDATE`
2. Update: quantity, avg_cost, market_price, market_value, observed_at, imported_at
3. Do NOT create a new row (same source_record_id)
4. `is_latest` toggling handled by the import service (supersede old, write new when quantity changes materially)

### 7.3 Transaction Skip Logic

Transactions are historical records — once imported, they are never updated.
On duplicate `(source, source_record_id)`:

1. Skip silently (not an error)
2. Return count of skipped rows in response

### 7.4 Cash Balance Upsert

Same as positions: update amount, observed_at on re-import.

---

## 8. Import Transaction Safety

### 8.1 All-or-Nothing Import

The entire import batch runs in a single database transaction:

```python
def import_positions(session, rows, source_key, household_id):
    with session.begin():
        data_source = resolve_data_source(session, source_key)
        errors, warnings = validate_all(rows)
        if errors.has_blocking:
            raise ImportValidationError(errors)
        for row in rows:
            asset = resolve_asset(session, row)
            account = resolve_account(session, row)
            upsert_position(session, row, asset, account, source_key)
        write_audit_events(session, ...)
    # Commit only if all rows succeed
```

### 8.2 Partial Import (Future)

Not in Sprint 009. Future enhancement: "continue-on-error" mode that skips
individual erroneous rows and imports the rest. This requires per-row
savepoints, which adds complexity. Deferred.

### 8.3 Rollback Guarantee

If any step after the database transaction begins fails (e.g. asset resolution
returns None, validation error, DB constraint violation), the entire batch
rolls back. No partial data.

---

## 9. Data Quality Reporting

### 9.1 Import Response Schema

```python
class ImportResponse(BaseModel):
    source_key: str
    imported_at: datetime
    summary: ImportSummary
    warnings: list[ImportWarning]
    errors: list[ImportError]

class ImportSummary(BaseModel):
    rows_processed: int
    positions_created: int
    positions_updated: int
    transactions_created: int
    transactions_skipped: int  # duplicates
    cash_balances_created: int
    cash_balances_updated: int
    assets_resolved: int       # matched existing
    assets_created: int        # new during import
    errors: int
    warnings: int
```

### 9.2 Quality Warnings

Warnings are informational — they don't block import but surface data quality
concerns:

| Warning Code | Meaning |
|---|---|
| `ASSET_CREATED_UNVERIFIED` | New asset created during import; verify manually |
| `PARTIAL_IDENTITY` | Asset lacks ISIN; may collide with future imports |
| `STALE_DATA` | observed_at is older than 30 days |
| `ZERO_QUANTITY` | Position has quantity = 0 (closed position?) |
| `FUTURE_TIMESTAMP` | observed_at is in the future (clock skew?) |
| `MISSING_MARKET_PRICE` | Position imported without current price |

---

## 10. API Endpoints

### 10.1 Manual Import

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/import/positions` | OWNER | Upload CSV with positions |
| `POST` | `/api/import/transactions` | OWNER | Upload CSV with transactions |
| `POST` | `/api/import/cash-balances` | OWNER | Upload CSV with cash balances |
| `GET`  | `/api/import/sources` | READ | List active data sources |
| `GET`  | `/api/import/sources/{key}/history` | READ | Import history for a source |

### 10.2 Request Format

```
POST /api/import/positions
Content-Type: multipart/form-data

source_key: csv_broker_export
file: positions.csv
```

### 10.3 Future Connector Endpoints (NOT in Sprint 009)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/import/{provider}/accounts` | SYSTEM | Trigger connector account sync |
| `POST` | `/api/import/{provider}/positions` | SYSTEM | Trigger connector position sync |
| `POST` | `/api/import/{provider}/transactions` | SYSTEM | Trigger connector transaction sync |

These are defined in the TD §19.2. Slice D does NOT implement them.

---

## 11. Provider Connector Interfaces (Design Only)

Slice D defines Python `Protocol` classes. No implementations.

```python
# apps/api/importers/protocols.py

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass
class AccountImportResult:
    provider_account_id: str
    account_name: str
    account_type: str
    currency: str
    source_metadata: dict  # provider-specific, for debugging


@dataclass
class PositionImportResult:
    provider_record_id: str
    asset_identifier: AssetIdentifier
    quantity: Decimal
    avg_cost: Decimal | None
    market_price: Decimal | None
    observed_at: datetime
    source_metadata: dict


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
    source_metadata: dict


@dataclass
class BalanceImportResult:
    provider_record_id: str
    currency: str
    amount: Decimal
    observed_at: datetime
    source_metadata: dict


@dataclass
class AssetIdentifier:
    isin: str | None = None
    symbol: str | None = None
    exchange: str | None = None
    currency: str | None = None


class AccountImporter(Protocol):
    def import_accounts(self, household_id: UUID) -> list[AccountImportResult]: ...

class PositionImporter(Protocol):
    def import_positions(self, account_id: UUID) -> list[PositionImportResult]: ...

class TransactionImporter(Protocol):
    def import_transactions(
        self, account_id: UUID, from_date: date, to_date: date
    ) -> list[TransactionImportResult]: ...

class BalanceImporter(Protocol):
    def import_balances(self, account_id: UUID) -> list[BalanceImportResult]: ...
```

These interfaces match the existing Sprint 009 Technical Design §14.

---

## 12. Data Source Activation

### 12.1 Existing DataSource Model (Slice A)

The `data_sources` table already supports:
- `source_key` (unique): e.g. 'csv_broker_export', 'manual_entry'
- `source_type`: 'csv', 'manual' (broker/bank deferred)
- `is_active`: enable/disable a source
- `last_import_at`: timestamp of most recent import
- `metadata` (JSONB): source-specific configuration

### 12.2 DataSource CRUD

Slice D adds management endpoints:

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/import/sources` | OWNER | Register a new data source |
| `PATCH` | `/api/import/sources/{key}` | OWNER | Update source metadata/active state |
| `DELETE` | `/api/import/sources/{key}` | OWNER | Deactivate a source (soft — sets is_active=false) |

### 12.3 Source Registration

When the Owner creates a CSV data source:

```json
POST /api/import/sources
{
  "source_key": "hsbc_monthly_export",
  "source_type": "csv",
  "display_name": "HSBC Monthly Export",
  "metadata": {
    "export_format": "hsbc_portfolio",
    "default_currency": "HKD"
  }
}
```

This source_key is then used in import requests to set the `source` column on
all imported records.

---

## 13. Migration Plan

**Migration: 0021_manual_import_foundation**

### 13.1 Schema Changes

| Change | Type | Table | Detail |
|---|---|---|---|
| Add `confidence` column | ALTER | `assets` | Text, nullable, default 'verified' |
| Add `uq_assets_isin` | INDEX | `assets` | Already exists from 0018 (verify) |

The `confidence` column on `assets` supports the asset resolution strategy:
- `verified`: ISIN-confirmed or manually verified by Owner
- `unverified`: Created during CSV import, awaiting Owner review

### 13.2 New Model Extension

```python
class Asset(Base):
    # ... existing fields ...
    confidence: Mapped[str] = mapped_column(
        Text, nullable=False, default="verified", server_default="verified",
    )
```

### 13.3 No New Tables

Slice D uses the existing Slice A tables exclusively. The import pipeline
is a service layer, not a schema layer.

### 13.4 Reversible

Downgrade drops the `confidence` column from `assets`.

---

## 14. Security Boundary

### 14.1 Authentication

All import endpoints require OWNER authorization. Slice D does not introduce
new auth mechanisms — it uses the existing classification system.

### 14.2 No Credentials

Slice D defines NO:
- API keys
- OAuth tokens
- Connection strings for financial providers
- Environment variables for broker access

### 14.3 File Upload Safety

- Max file size: 10 MB (configurable)
- Accepted content types: text/csv, application/csv
- No executable content
- Files stored in memory only (no disk persistence)
- Parsed content validated before any database write

### 14.4 Data Privacy

- All imported data stays within the PostgreSQL database
- No data is sent to external services
- No LLM processing of imported data (deferred to Committee evidence pipeline, which aggregates anonymized views only)

---

## 15. Test Strategy

### 15.1 Unit Tests (No PostgreSQL)

| Test | What it proves |
|---|---|
| CSV parser handles valid input | All columns mapped correctly |
| CSV parser rejects malformed CSV | Invalid rows produce parse errors |
| CSV parser handles empty file | Graceful empty result |
| CSV parser handles missing headers | Clear error message |
| Validator rejects invalid currency | `XYZ` rejected, `USD` accepted |
| Validator rejects negative quantity | quantity < 0 rejected |
| Validator rejects invalid timestamp | Bad ISO 8601 caught |
| Validator accepts valid row | All checks pass |
| Asset resolver finds by ISIN | Existing asset returned |
| Asset resolver finds by symbol/exchange | Fallback works |
| Asset resolver creates new | New asset with confidence='unverified' |

### 15.2 Integration Tests (PostgreSQL Required)

| Test | What it proves |
|---|---|
| Full position import lifecycle | CSV → positions in DB |
| Duplicate position import updates | Same source_record_id → upsert |
| Duplicate transaction import skipped | No duplicate rows |
| Import rollback on error | Failed batch leaves no partial data |
| Asset created with unverified confidence | New assets flagged |
| Account resolution by provider_account_id | Correct account matched |
| AuditEvent written on import | Traceability |
| DataSource last_import_at updated | Metadata maintenance |
| Batch validation reports all errors | Collects, doesn't fail-fast |
| Cross-currency import | HKD, USD positions coexist |
| Empty import handled gracefully | 0 rows processed, no error |
| is_latest toggling on position update | Old position superseded |
| Warning issuance for stale data | observed_at > 30 days → WARNING |
| Warnings don't block import | Import proceeds with warnings |

### 15.3 Schema Tests

| Test | What it proves |
|---|---|
| assets.confidence column exists | Migration applied |
| assets.confidence defaults to 'verified' | Backward-compatible |
| Migration is reversible | Downgrade removes column cleanly |

---

## 16. Test Fixture Strategy

### 16.1 Pre-Seeded Data Sources

Tests use a fixture that creates standard data sources:

```python
@pytest.fixture
def seeded_data_sources(db_session):
    from apps.api.repositories.portfolio_foundation import create_data_source
    create_data_source(db_session, source_key="csv_test", source_type="csv",
                       display_name="Test CSV Source", is_active=True)
    db_session.commit()
```

### 16.2 CSV Fixture Files

Tests use in-memory CSV strings (not disk files):

```python
VALID_POSITIONS_CSV = (
    "source_record_id,account_provider_id,symbol,exchange,isin,"
    "name,asset_type,currency,quantity,avg_cost,market_price,observed_at\n"
    "CSV-001,IB-TEST,AAPL,NASDAQ,US0378331005,"
    "Apple Inc.,STOCK,USD,100,150.50,175.25,2026-08-09T16:00:00Z\n"
)
```

---

## 17. File List

### 17.1 New Files

| File | Purpose |
|---|---|
| `apps/api/routers/imports.py` | Import endpoints |
| `apps/api/services/import_service.py` | Import orchestration |
| `apps/api/importers/__init__.py` | Package init |
| `apps/api/importers/csv_parser.py` | CSV parser |
| `apps/api/importers/validators.py` | Validation rules |
| `apps/api/importers/asset_resolver.py` | Asset identity resolution |
| `apps/api/importers/protocols.py` | Protocol interfaces (no impl) |
| `apps/api/import_schemas.py` | Pydantic schemas for import |
| `tests/test_manual_import.py` | Integration tests |

### 17.2 Modified Files

| File | Change |
|---|---|
| `apps/api/models.py` | Add Asset.confidence column |
| `migrations/versions/0021_manual_import_foundation.py` | New migration |
| `apps/api/mutation_gate.py` | Update EXPECTED_HEAD to 0021 |
| `apps/api/services/health_service.py` | Update migration head |
| `tests/api/test_households.py` | No new tables (confidence column only) |
| `tests/test_portfolio_foundation.py` | Update HEAD_REVISION |
| `tests/test_policy_enrichment.py` | Update HEAD_REVISION |
| `tests/test_policy_migrations.py` | Update HEAD_REVISION |
| `tests/test_investment_idea.py` | Update HEAD_REVISION |
| `docs/MASTER_PLAN.md` | Slice D: IN PROGRESS |

---

## 18. Implementation Order

1. **Migration 0021**: Add `confidence` column to `assets`
2. **Protocol interfaces**: `importers/protocols.py` (zero-dependency)
3. **CSV Parser**: `importers/csv_parser.py`
4. **Validators**: `importers/validators.py`
5. **Asset Resolver**: `importers/asset_resolver.py`
6. **Import Service**: `services/import_service.py`
7. **Import Schemas**: `import_schemas.py`
8. **Router**: `routers/imports.py`
9. **Tests**: `tests/test_manual_import.py`
10. **HEAD updates**: All HEAD_REVISION references

---

## 19. Out of Scope (Explicit)

| Item | Reason |
|---|---|
| Broker API connections (HSBC, IB, Schwab) | NOT AUTHORIZED |
| OAuth token management | Requires credential architecture |
| Automated/scheduled import | Deferred to Sprint 010+ |
| Price history time series | Requires market data source |
| Live market price feeds | Requires provider authorization |
| Portfolio performance calculation | Schema exists, engine deferred |
| Tax lot / specific-ID cost basis | Requires tax jurisdiction design |
| Asset merge/curation UI | Manual process, deferred |
| Partial import (skip errors) | Added complexity, deferred |
| Drag-and-drop file upload UI | Frontend; deferred to UI sprint |

---

## 20. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| CSV column mapping brittle across providers | Medium | Parser supports column aliases; metadata in DataSource specifies mapping |
| Asset identity collision on symbol-only match | Medium | ISIN is primary; symbol-only assets flagged as unverified |
| Large CSV files cause memory pressure | Low | 10 MB limit; streaming parser if needed (deferred) |
| Currency mismatch between CSV and account | Low | Validator checks CSV currency against account currency; warns on mismatch |
| Timezone confusion in timestamps | Low | ISO 8601 with explicit timezone offset; stored as TIMESTAMPTZ |

---

## 21. Estimated Effort

| Component | Complexity | Tests |
|---|---|---|
| Migration 0021 | Trivial (1 column, 1 CHECK) | 3 tests |
| Protocol interfaces | Trivial (dataclasses only) | 0 tests (type-checked) |
| CSV Parser | Low (~80 lines) | 5 tests |
| Validators | Low (~120 lines) | 6 tests |
| Asset Resolver | Medium (~100 lines) | 4 tests |
| Import Service | Medium (~200 lines) | 7 tests |
| Import Schemas | Low (~80 lines) | 2 tests |
| Router | Low (~60 lines) | 2 tests |
| HEAD updates | Trivial (mechanical) | N/A |
| **Total** | **~640 lines code + ~29 tests** | |

---

## 22. Design Decisions (Owner)

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| OD-9-D-1 | Asset confidence: 'verified'/'unverified' enum or free-text? | Enum (2 values) | Keep simple; expand if needed |
| OD-9-D-2 | Partial import (skip errors) in Slice D? | No (deferred) | All-or-nothing is safer for V1 |
| OD-9-D-3 | CSV column aliases in metadata? | Yes (per source_key) | Enables broker-specific CSV formats |
| OD-9-D-4 | Store raw CSV rows for audit? | No (deferred) | Source provenance columns are sufficient |

---

## 23. Absolute Exclusions

- No broker/bank API connections (HSBC, Interactive Brokers, Schwab)
- No real financial credentials (API keys, OAuth tokens, connection strings)
- No trading, order placement, or execution
- No automatic rebalancing
- No AI-driven import decisions
- No external API calls
- No frontend implementation
- No performance calculation engine
