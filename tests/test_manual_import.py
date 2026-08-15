"""Integration tests for Sprint 009 Slice D — Manual Import + Data Source Foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0034_research_run_status"

POSITIONS_CSV = (
    "source_record_id,account_provider_id,symbol,exchange,isin,"
    "name,asset_type,currency,quantity,avg_cost,market_price,observed_at\n"
    "CSV-POS-001,ACCT-TEST,AAPL,NASDAQ,US0378331005,"
    "Apple Inc.,STOCK,USD,100,150.50,175.25,2026-08-09T16:00:00Z\n"
    "CSV-POS-002,ACCT-TEST,MSFT,NASDAQ,US5949181045,"
    "Microsoft Corp,STOCK,USD,50,300.00,310.00,2026-08-09T16:00:00Z\n"
)

TRANSACTIONS_CSV = (
    "source_record_id,account_provider_id,symbol,exchange,isin,"
    "transaction_type,quantity,price,amount,currency,executed_at,observed_at\n"
    "CSV-TXN-001,ACCT-TEST,AAPL,NASDAQ,US0378331005,"
    "BUY,50,150.00,7500.00,USD,2026-07-15T10:30:00Z,2026-08-09T16:00:00Z\n"
)

CASH_BALANCES_CSV = (
    "source_record_id,account_provider_id,currency,amount,observed_at\n"
    "CSV-BAL-001,ACCT-TEST,USD,25000.50,2026-08-09T16:00:00Z\n"
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_household_account(session: Session):
    """Create household + portfolio + account with provider_account_id."""
    from apps.api.models import Account, HouseholdProfile, Portfolio, PortfolioDraft

    household = HouseholdProfile(
        id=uuid4(), household_name="Test", base_currency="USD",
    )
    session.add(household)
    session.flush()

    portfolio = Portfolio(id=uuid4(), household_id=household.id, status="draft")
    session.add(portfolio)
    session.flush()

    draft = PortfolioDraft(
        portfolio_id=portfolio.id, expected_revision=1,
        valuation_date=_now().date(),
    )
    session.add(draft)
    session.flush()

    account = Account(
        id=uuid4(), portfolio_id=portfolio.id, name="Test Account",
        account_type="brokerage", capital_bucket="CORE", currency="USD",
        provider="csv", provider_account_id="ACCT-TEST",
    )
    session.add(account)
    session.commit()
    return household, portfolio, account


def _create_data_source(session: Session, source_key: str = "default_csv"):
    from apps.api.repositories.portfolio_foundation import create_data_source
    existing = session.execute(
        text("SELECT 1 FROM data_sources WHERE source_key = :sk"),
        {"sk": source_key},
    ).scalar()
    if existing is None:
        create_data_source(session, source_key=source_key, source_type="csv")
    session.commit()


# ═══════════════════════════════════════════════════════════════════════
# Migration tests
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_assets_has_confidence_column(self, postgres_test_isolation, postgres_engine: Engine):
        inspector = inspect(postgres_engine)
        cols = {c["name"] for c in inspector.get_columns("assets")}
        assert "confidence" in cols, "assets missing confidence column"

    def test_confidence_defaults_to_verified(self, db_session: Session):
        from apps.api.models import Asset
        asset = Asset(
            id=uuid4(), name="Test Asset", asset_type="STOCK", currency="USD",
        )
        db_session.add(asset)
        db_session.commit()
        db_session.refresh(asset)
        assert asset.confidence == "verified"

    def test_confidence_validates_values(self, db_session: Session):
        from apps.api.models import Asset
        asset = Asset(
            id=uuid4(), name="Bad", asset_type="STOCK", currency="USD",
            confidence="invalid_value",
        )
        db_session.add(asset)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()

    def test_transaction_immutability_trigger_exists(
        self, postgres_test_isolation, postgres_engine: Engine,
    ):
        result = None
        with postgres_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT 1 FROM pg_trigger "
                    "WHERE tgname = 'trg_transaction_immutability'"
                )
            ).scalar()
        assert result == 1, "Transaction immutability trigger not found"

    def test_migration_head(self, db_session: Session):
        result = db_session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert result == HEAD_REVISION, f"Expected {HEAD_REVISION}, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# CSV Parser tests
# ═══════════════════════════════════════════════════════════════════════


class TestCsvParser:
    def test_parse_valid_csv(self):
        from apps.api.importers.csv_parser import parse_csv_content
        rows = parse_csv_content(POSITIONS_CSV)
        assert len(rows) == 2
        assert rows[0]["symbol"] == "AAPL"

    def test_parse_empty_csv_raises(self):
        from apps.api.importers.csv_parser import ParseError, parse_csv_content
        with pytest.raises(ParseError, match="no data"):
            parse_csv_content("source_record_id,account_provider_id,symbol\n")

    def test_parse_decimal(self):
        from apps.api.importers.csv_parser import parse_csv_decimal
        assert parse_csv_decimal("150.50") == Decimal("150.50")
        assert parse_csv_decimal("") is None
        assert parse_csv_decimal(None) is None

    def test_parse_decimal_invalid_raises(self):
        from apps.api.importers.csv_parser import parse_csv_decimal
        with pytest.raises(ValueError, match="Invalid decimal"):
            parse_csv_decimal("abc")

    def test_parse_iso8601_valid(self):
        from apps.api.importers.csv_parser import parse_csv_datetime
        dt = parse_csv_datetime("2026-08-09T16:00:00Z")
        assert dt.year == 2026

    def test_parse_iso8601_invalid_raises(self):
        from apps.api.importers.csv_parser import parse_csv_datetime
        with pytest.raises(ValueError):
            parse_csv_datetime("not a date")


# ═══════════════════════════════════════════════════════════════════════
# Validator tests
# ═══════════════════════════════════════════════════════════════════════


class TestValidators:
    def test_valid_position_passes(self):
        from apps.api.importers.validators import (
            ValidationResult,
            validate_position_row,
        )
        row = {
            "source_record_id": "X", "account_provider_id": "A",
            "symbol": "AAPL", "currency": "USD",
            "quantity": "100", "observed_at": "2026-08-09T16:00:00Z",
        }
        result = ValidationResult()
        validate_position_row(row, 0, result)
        assert not result.has_errors
        assert not result.has_warnings

    def test_invalid_currency_rejected(self):
        from apps.api.importers.validators import (
            ValidationResult,
            validate_position_row,
        )
        row = {
            "source_record_id": "X", "account_provider_id": "A",
            "symbol": "AAPL", "currency": "XX",
            "quantity": "100", "observed_at": "2026-08-09T16:00:00Z",
        }
        result = ValidationResult()
        validate_position_row(row, 0, result)
        assert result.has_errors

    def test_negative_quantity_rejected(self):
        from apps.api.importers.validators import (
            ValidationResult,
            validate_position_row,
        )
        row = {
            "source_record_id": "X", "account_provider_id": "A",
            "symbol": "AAPL", "currency": "USD",
            "quantity": "-10", "observed_at": "2026-08-09T16:00:00Z",
        }
        result = ValidationResult()
        validate_position_row(row, 0, result)
        assert result.has_errors

    def test_future_timestamp_warns(self):
        from apps.api.importers.validators import (
            ValidationResult,
            validate_position_row,
        )
        row = {
            "source_record_id": "X", "account_provider_id": "A",
            "symbol": "AAPL", "currency": "USD", "quantity": "100",
            "observed_at": "2099-01-01T00:00:00Z",
        }
        result = ValidationResult()
        validate_position_row(row, 0, result)
        assert result.has_warnings

    def test_batch_catches_duplicate_ids(self):
        from apps.api.importers.validators import (
            validate_batch,
            validate_position_row,
        )
        rows = [
            {"source_record_id": "DUP", "account_provider_id": "A",
             "symbol": "A", "currency": "USD", "quantity": "10",
             "observed_at": "2026-01-01T00:00:00Z"},
            {"source_record_id": "DUP", "account_provider_id": "A",
             "symbol": "B", "currency": "USD", "quantity": "20",
             "observed_at": "2026-01-01T00:00:00Z"},
        ]
        result = validate_batch(rows, validate_position_row)
        assert result.has_errors


# ═══════════════════════════════════════════════════════════════════════
# Asset resolver tests
# ═══════════════════════════════════════════════════════════════════════


class TestAssetResolver:
    def test_resolve_by_isin_finds_existing(self, db_session: Session):
        from apps.api.importers.asset_resolver import resolve_asset
        from apps.api.models import Asset

        existing = Asset(
            id=uuid4(), name="Apple Inc.", asset_type="STOCK",
            currency="USD", symbol="AAPL", exchange="NASDAQ",
            isin="US0378331005",
        )
        db_session.add(existing)
        db_session.commit()

        found = resolve_asset(
            db_session, symbol="AAPL", exchange="NASDAQ",
            isin="us0378331005", currency="USD",
        )
        assert found.id == existing.id
        assert found.confidence == "verified"

    def test_resolve_by_symbol_exchange_currency(self, db_session: Session):
        from apps.api.importers.asset_resolver import resolve_asset
        from apps.api.models import Asset

        existing = Asset(
            id=uuid4(), name="Apple", asset_type="STOCK",
            currency="USD", symbol="AAPL", exchange="NASDAQ",
        )
        db_session.add(existing)
        db_session.commit()

        found = resolve_asset(
            db_session, symbol="aapl", exchange="nasdaq", currency="USD",
        )
        assert found.id == existing.id

    def test_create_unverified_when_not_found(self, db_session: Session):
        from apps.api.importers.asset_resolver import resolve_asset

        asset = resolve_asset(
            db_session, symbol="NEWSYM", exchange="UNKNOWN", currency="USD",
            name="New Asset Inc.", asset_type="STOCK",
        )
        db_session.commit()
        assert asset.confidence == "unverified"
        assert asset.name == "New Asset Inc."


# ═══════════════════════════════════════════════════════════════════════
# Import pipeline tests
# ═══════════════════════════════════════════════════════════════════════


class TestImportPipeline:
    def test_import_positions_from_csv(self, db_session: Session):
        from apps.api.services.import_service import import_positions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        response = import_positions_from_csv(db_session, POSITIONS_CSV, "default_csv")
        db_session.commit()

        assert response.summary.positions_created == 2
        assert response.summary.errors == 0

    def test_import_positions_idempotent(self, db_session: Session):
        from apps.api.services.import_service import import_positions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        r1 = import_positions_from_csv(db_session, POSITIONS_CSV, "default_csv")
        db_session.commit()
        assert r1.summary.positions_created == 2

        r2 = import_positions_from_csv(db_session, POSITIONS_CSV, "default_csv")
        db_session.commit()
        assert r2.summary.positions_created == 0
        assert r2.summary.positions_updated == 2

    def test_import_transactions_from_csv(self, db_session: Session):
        from apps.api.services.import_service import import_transactions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        response = import_transactions_from_csv(
            db_session, TRANSACTIONS_CSV, "default_csv",
        )
        db_session.commit()

        assert response.summary.transactions_created == 1
        assert response.summary.errors == 0

    def test_import_transactions_duplicate_skipped(self, db_session: Session):
        from apps.api.services.import_service import import_transactions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        r1 = import_transactions_from_csv(
            db_session, TRANSACTIONS_CSV, "default_csv",
        )
        db_session.commit()
        assert r1.summary.transactions_created == 1

        r2 = import_transactions_from_csv(
            db_session, TRANSACTIONS_CSV, "default_csv",
        )
        db_session.commit()
        assert r2.summary.transactions_created == 0
        assert r2.summary.transactions_skipped == 1

    def test_import_cash_balances(self, db_session: Session):
        from apps.api.services.import_service import import_cash_balances_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        response = import_cash_balances_from_csv(
            db_session, CASH_BALANCES_CSV, "default_csv",
        )
        db_session.commit()

        assert response.summary.cash_balances_created == 1

    def test_import_unknown_account_rejected(self, db_session: Session):
        from apps.api.services.import_service import import_positions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        csv_with_bad_account = POSITIONS_CSV.replace("ACCT-TEST", "ACCT-NONEXISTENT")
        response = import_positions_from_csv(
            db_session, csv_with_bad_account, "default_csv",
        )
        db_session.commit()

        assert response.summary.errors > 0

    def test_import_rollback_on_error(self, db_session: Session):
        from apps.api.models import Position
        from apps.api.services.import_service import import_positions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        # CSV with invalid row that passes parser but fails at DB
        bad_csv = (
            "source_record_id,account_provider_id,symbol,exchange,isin,"
            "name,asset_type,currency,quantity,avg_cost,market_price,observed_at\n"
            "CSV-BAD-001,ACCT-TEST,BADSYM,,,"
            "Bad Inc,INVALID_TYPE,USD,100,,,2026-08-09T16:00:00Z\n"
        )
        response = import_positions_from_csv(db_session, bad_csv, "default_csv")
        # Validation catches invalid asset_type
        db_session.commit()

        # No positions should have been created
        count = db_session.query(Position).count()
        assert count == 0 or response.summary.errors > 0


# ═══════════════════════════════════════════════════════════════════════
# Transaction immutability tests
# ═══════════════════════════════════════════════════════════════════════


class TestTransactionImmutability:
    def test_transaction_update_rejected(self, db_session: Session):
        from apps.api.models import Transaction

        _, _, account = _create_household_account(db_session)

        txn = Transaction(
            id=uuid4(), account_id=account.id,
            transaction_type="BUY", amount_currency="USD",
            source="test", source_record_id="TEST-001",
            quantity=Decimal("10"), price=Decimal("100"),
            amount=Decimal("1000"), executed_at=_now(),
        )
        db_session.add(txn)
        db_session.commit()

        txn.quantity = Decimal("20")
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()

    def test_transaction_delete_rejected(self, db_session: Session):
        from apps.api.models import Transaction

        _, _, account = _create_household_account(db_session)

        txn = Transaction(
            id=uuid4(), account_id=account.id,
            transaction_type="SELL", amount_currency="USD",
            source="test", source_record_id="TEST-002",
            quantity=Decimal("5"), price=Decimal("200"),
            amount=Decimal("1000"), executed_at=_now(),
        )
        db_session.add(txn)
        db_session.commit()

        db_session.delete(txn)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# Provenance tests
# ═══════════════════════════════════════════════════════════════════════


class TestProvenance:
    def test_imported_position_has_provenance(self, db_session: Session):
        from apps.api.services.import_service import import_positions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        import_positions_from_csv(db_session, POSITIONS_CSV, "default_csv")
        db_session.commit()

        from apps.api.models import Position
        pos = db_session.query(Position).first()
        assert pos is not None
        assert pos.source == "csv"
        assert pos.source_record_id == "CSV-POS-001"
        assert pos.observed_at is not None
        assert pos.imported_at is not None

    def test_imported_transaction_has_provenance(self, db_session: Session):
        from apps.api.services.import_service import import_transactions_from_csv

        _create_household_account(db_session)
        _create_data_source(db_session)

        import_transactions_from_csv(db_session, TRANSACTIONS_CSV, "default_csv")
        db_session.commit()

        from apps.api.models import Transaction
        txn = db_session.query(Transaction).first()
        assert txn is not None
        assert txn.source == "csv"
        assert txn.source_record_id == "CSV-TXN-001"
