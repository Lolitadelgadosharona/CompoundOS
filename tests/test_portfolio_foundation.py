"""Integration tests for Sprint 009 Slice A.

Tests cover:
  1. Asset identity constraints (isin, symbol+exchange+currency, type/currency checks)
  2. Account bucket constraints (type, bucket, currency, provider uniqueness)
  3. Currency validation (CHECK constraints on assets, accounts, positions, etc.)
  4. Foreign key integrity (positions→accounts/assets, cash_balances→accounts, etc.)
  5. Source provenance preservation (source + source_record_id on every datum)
  6. Duplicate import prevention (UNIQUE(source, source_record_id) partial indexes)
  7. Position/account relationships
  8. Transaction relationships
  9. FX rate uniqueness and constraints
  10. Data source key uniqueness
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0033_perspective_provenance"

SPRINT_009_TABLES = frozenset({
    "assets",
    "positions",
    "cash_balances",
    "transactions",
    "fx_rates",
    "data_sources",
})

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_household(session: Session) -> tuple:
    """Create the singleton household + portfolio + account prerequisite."""
    from apps.api.models import Account, HouseholdProfile, Portfolio, PortfolioDraft

    household = HouseholdProfile(
        id=uuid4(),
        household_name="Test Household",
        base_currency="USD",
    )
    session.add(household)
    session.flush()

    portfolio = Portfolio(
        id=uuid4(),
        household_id=household.id,
        status="draft",
    )
    session.add(portfolio)
    session.flush()

    draft = PortfolioDraft(portfolio_id=portfolio.id)
    session.add(draft)
    session.flush()

    account = Account(
        id=uuid4(),
        portfolio_id=portfolio.id,
        name="Test Account",
        sort_order=0,
        account_type="brokerage",
        capital_bucket="CORE",
        currency="USD",
    )
    session.add(account)
    session.flush()

    return household, portfolio, account


def _table_exists(engine: Engine, table_name: str) -> bool:
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


# ═══════════════════════════════════════════════════════════════════════
# Migration tests
# ═══════════════════════════════════════════════════════════════════════


class TestMigrationCreatesAllTables:
    def test_sprint_009_tables_exist(self, postgres_test_isolation, postgres_engine: Engine):
        """All six new tables and account extension columns exist after upgrade."""
        for table_name in SPRINT_009_TABLES:
            assert _table_exists(postgres_engine, table_name), (
                f"Table {table_name!r} not found after migration"
            )

    def test_account_has_new_columns(self, postgres_test_isolation, postgres_engine: Engine):
        """Accounts table has the five new financial classification columns."""
        inspector = inspect(postgres_engine)
        columns = {c["name"] for c in inspector.get_columns("accounts")}
        expected = {"account_type", "capital_bucket", "currency", "provider", "provider_account_id"}
        missing = expected - columns
        assert not missing, f"Missing account columns: {missing}"

    def test_migration_head_revision(self, db_session: Session):
        """Verify alembic_version is at 0018."""
        result = db_session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert result == HEAD_REVISION, (
            f"Expected {HEAD_REVISION}, got {result}"
        )


# ═══════════════════════════════════════════════════════════════════════
# Asset identity constraints
# ═══════════════════════════════════════════════════════════════════════


class TestAssetIdentityConstraints:
    def test_create_valid_asset(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset

        asset = create_asset(
            db_session,
            symbol="AAPL",
            name="Apple Inc.",
            asset_type="STOCK",
            currency="USD",
            exchange="NASDAQ",
            isin="US0378331005",
        )
        db_session.commit()
        assert asset.id is not None
        assert asset.asset_type == "STOCK"
        assert asset.currency == "USD"

    def test_asset_isin_unique(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset

        create_asset(
            db_session,
            symbol="AAPL", name="Apple", asset_type="STOCK",
            currency="USD", isin="US0378331005",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_asset(
                db_session,
                symbol="AAPL-DUP", name="Apple Duplicate", asset_type="STOCK",
                currency="USD", isin="US0378331005",
            )
            db_session.commit()
        db_session.rollback()

    def test_asset_symbol_exchange_currency_unique(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset

        create_asset(
            db_session, symbol="AAPL", name="Apple", asset_type="STOCK",
            currency="USD", exchange="NASDAQ",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_asset(
                db_session, symbol="AAPL", name="Apple Copy", asset_type="STOCK",
                currency="USD", exchange="NASDAQ",
            )
            db_session.commit()
        db_session.rollback()

    def test_asset_same_symbol_different_exchange_allowed(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset

        a1 = create_asset(
            db_session, symbol="AAPL", name="Apple NASDAQ", asset_type="STOCK",
            currency="USD", exchange="NASDAQ",
        )
        a2 = create_asset(
            db_session, symbol="AAPL", name="Apple MEXI", asset_type="STOCK",
            currency="MXN", exchange="BMV",
        )
        db_session.commit()
        assert a1.id != a2.id

    def test_asset_invalid_type_rejected(self, db_session: Session):
        with pytest.raises(IntegrityError):
            from apps.api.models import Asset
            asset = Asset(
                id=uuid4(), name="Bad", asset_type="CRYPTO",
                currency="USD",
            )
            db_session.add(asset)
            db_session.commit()
        db_session.rollback()

    def test_asset_invalid_currency_rejected(self, db_session: Session):
        with pytest.raises(IntegrityError):
            from apps.api.models import Asset
            asset = Asset(
                id=uuid4(), name="Bad Currency", asset_type="STOCK",
                currency="US",  # 2 chars, not 3
            )
            db_session.add(asset)
            db_session.commit()
        db_session.rollback()

    def test_asset_name_too_long_rejected(self, db_session: Session):
        with pytest.raises(IntegrityError):
            from apps.api.models import Asset
            asset = Asset(
                id=uuid4(), name="X" * 201, asset_type="STOCK",
                currency="USD",
            )
            db_session.add(asset)
            db_session.commit()
        db_session.rollback()

    def test_asset_null_isin_allowed_no_conflict(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset

        a1 = create_asset(
            db_session, name="Asset Without ISIN 1", asset_type="FUND",
            currency="USD",
        )
        a2 = create_asset(
            db_session, name="Asset Without ISIN 2", asset_type="FUND",
            currency="USD",
        )
        db_session.commit()
        assert a1.id != a2.id


# ═══════════════════════════════════════════════════════════════════════
# Account extension constraints
# ═══════════════════════════════════════════════════════════════════════


class TestAccountConstraints:
    def test_account_type_constraint(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import update_account_fields

        _, _, account = _create_household(db_session)
        db_session.commit()

        with pytest.raises(IntegrityError):
            update_account_fields(db_session, account.id, account_type="crypto_exchange")
            db_session.commit()
        db_session.rollback()

    def test_account_bucket_constraint(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import update_account_fields

        _, _, account = _create_household(db_session)
        db_session.commit()

        with pytest.raises(IntegrityError):
            update_account_fields(db_session, account.id, capital_bucket="GAMBLING")
            db_session.commit()
        db_session.rollback()

    def test_account_currency_constraint(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import update_account_fields

        _, _, account = _create_household(db_session)
        db_session.commit()

        with pytest.raises(IntegrityError):
            update_account_fields(db_session, account.id, currency="US")
            db_session.commit()
        db_session.rollback()

    def test_account_provider_unique_constraint(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import update_account_fields

        _, _, account = _create_household(db_session)
        db_session.commit()

        # First update succeeds
        update_account_fields(
            db_session, account.id,
            provider="interactive_brokers", provider_account_id="U123456",
        )
        db_session.commit()

        # Second account with same provider + provider_account_id fails
        from apps.api.models import Account
        account2 = Account(
            id=uuid4(),
            portfolio_id=account.portfolio_id,
            name="Test Account 2",
            sort_order=1,
            account_type="brokerage",
            capital_bucket="CORE",
            currency="USD",
            provider="interactive_brokers",
            provider_account_id="U123456",
        )
        db_session.add(account2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_account_null_provider_no_conflict(self, db_session: Session):
        _, _, account = _create_household(db_session)
        db_session.commit()

        from apps.api.models import Account
        account2 = Account(
            id=uuid4(),
            portfolio_id=account.portfolio_id,
            name="Test Account 2",
            sort_order=1,
            account_type="bank",
            capital_bucket="CASH_RESERVE",
            currency="HKD",
        )
        db_session.add(account2)
        db_session.commit()
        assert account2.id is not None


# ═══════════════════════════════════════════════════════════════════════
# Foreign key integrity
# ═══════════════════════════════════════════════════════════════════════


class TestForeignKeyIntegrity:
    def test_position_requires_valid_account(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset, create_position

        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_position(
                db_session,
                account_id=uuid4(),  # nonexistent
                asset_id=asset.id,
                quantity=Decimal("100"),
                quantity_source="provider_reported",
                avg_cost_currency="USD",
                market_price_currency="USD",
                observed_at=_now(),
                source="interactive_brokers",
            )
            db_session.commit()
        db_session.rollback()

    def test_position_requires_valid_asset(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_position

        _, _, account = _create_household(db_session)
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_position(
                db_session,
                account_id=account.id,
                asset_id=uuid4(),  # nonexistent
                quantity=Decimal("100"),
                quantity_source="provider_reported",
                avg_cost_currency="USD",
                market_price_currency="USD",
                observed_at=_now(),
                source="interactive_brokers",
            )
            db_session.commit()
        db_session.rollback()

    def test_cash_balance_requires_valid_account(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_cash_balance

        with pytest.raises(IntegrityError):
            create_cash_balance(
                db_session,
                account_id=uuid4(),
                currency="USD",
                amount=Decimal("10000"),
                observed_at=_now(),
                source="hsbc",
            )
            db_session.commit()
        db_session.rollback()

    def test_transaction_requires_valid_account(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_transaction

        with pytest.raises(IntegrityError):
            create_transaction(
                db_session,
                account_id=uuid4(),
                transaction_type="DEPOSIT",
                executed_at=_now(),
                source="hsbc",
            )
            db_session.commit()
        db_session.rollback()

    def test_transaction_valid_asset_fk(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_asset,
            create_transaction,
        )

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        txn = create_transaction(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("10"),
            price=Decimal("150.00"),
            executed_at=_now(),
            source="interactive_brokers",
        )
        db_session.commit()
        assert txn.id is not None
        assert txn.asset_id == asset.id

    def test_transaction_null_asset_allowed_for_cash_events(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_transaction

        _, _, account = _create_household(db_session)
        db_session.commit()

        txn = create_transaction(
            db_session,
            account_id=account.id,
            asset_id=None,
            transaction_type="DEPOSIT",
            amount=Decimal("5000"),
            amount_currency="USD",
            executed_at=_now(),
            source="hsbc",
        )
        db_session.commit()
        assert txn.id is not None
        assert txn.asset_id is None


# ═══════════════════════════════════════════════════════════════════════
# Source provenance preservation
# ═══════════════════════════════════════════════════════════════════════


class TestSourceProvenance:
    def test_position_preserves_source_and_record_id(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset, create_position

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test Stock", asset_type="STOCK", currency="USD",
        )
        db_session.commit()

        pos = create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("200"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="interactive_brokers",
            source_record_id="IB-2024-001",
        )
        db_session.commit()

        assert pos.source == "interactive_brokers"
        assert pos.source_record_id == "IB-2024-001"
        assert pos.quantity_source == "provider_reported"

    def test_transaction_preserves_source_and_record_id(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_transaction

        _, _, account = _create_household(db_session)
        db_session.commit()

        txn = create_transaction(
            db_session,
            account_id=account.id,
            transaction_type="BUY",
            quantity=Decimal("50"),
            price=Decimal("200.00"),
            executed_at=_now(),
            source="hsbc",
            source_record_id="HSBC-TXN-999",
        )
        db_session.commit()

        assert txn.source == "hsbc"
        assert txn.source_record_id == "HSBC-TXN-999"

    def test_cash_balance_preserves_source_and_record_id(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_cash_balance

        _, _, account = _create_household(db_session)
        db_session.commit()

        bal = create_cash_balance(
            db_session,
            account_id=account.id,
            currency="USD",
            amount=Decimal("25000"),
            observed_at=_now(),
            source="hsbc",
            source_record_id="HSBC-CASH-001",
        )
        db_session.commit()

        assert bal.source == "hsbc"
        assert bal.source_record_id == "HSBC-CASH-001"

    def test_provider_reported_vs_compoundos_derived_distinction(self, db_session: Session):
        """CompoundOS-derived values are never silently mixed with provider facts."""
        from apps.api.repositories.portfolio_foundation import create_asset, create_position

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        # Provider-reported position
        provider_pos = create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            quantity_source="provider_reported",
            avg_cost=Decimal("150.00"),
            avg_cost_currency="USD",
            avg_cost_source="interactive_brokers",
            market_price=Decimal("155.00"),
            market_price_currency="USD",
            observed_at=_now(),
            source="interactive_brokers",
        )
        db_session.commit()

        assert provider_pos.quantity_source == "provider_reported"
        assert provider_pos.source == "interactive_brokers"
        assert provider_pos.avg_cost_source == "interactive_brokers"

        # CompoundOS-derived position (manual or computed)
        derived_pos = create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            quantity_source="compoundos_derived",
            avg_cost=Decimal("151.00"),
            avg_cost_currency="USD",
            avg_cost_source="compoundos_derived",
            market_price=Decimal("155.00"),
            market_price_currency="USD",
            observed_at=_now(),
            source="compoundos_derived",
        )
        db_session.commit()

        assert derived_pos.quantity_source == "compoundos_derived"
        assert derived_pos.source == "compoundos_derived"


# ═══════════════════════════════════════════════════════════════════════
# Duplicate import prevention
# ═══════════════════════════════════════════════════════════════════════


class TestDuplicateImportPrevention:
    def test_duplicate_position_source_record_rejected(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_asset, create_position

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="interactive_brokers",
            source_record_id="IB-POS-001",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_position(
                db_session,
                account_id=account.id,
                asset_id=asset.id,
                quantity=Decimal("200"),
                quantity_source="provider_reported",
                avg_cost_currency="USD",
                market_price_currency="USD",
                observed_at=_now(),
                source="interactive_brokers",
                source_record_id="IB-POS-001",
            )
            db_session.commit()
        db_session.rollback()

    def test_duplicate_cash_balance_source_record_rejected(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_cash_balance

        _, _, account = _create_household(db_session)
        db_session.commit()

        create_cash_balance(
            db_session,
            account_id=account.id,
            currency="USD",
            amount=Decimal("10000"),
            observed_at=_now(),
            source="hsbc",
            source_record_id="HSBC-CASH-001",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_cash_balance(
                db_session,
                account_id=account.id,
                currency="USD",
                amount=Decimal("99999"),
                observed_at=_now(),
                source="hsbc",
                source_record_id="HSBC-CASH-001",
            )
            db_session.commit()
        db_session.rollback()

    def test_duplicate_transaction_source_record_rejected(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_transaction

        _, _, account = _create_household(db_session)
        db_session.commit()

        create_transaction(
            db_session,
            account_id=account.id,
            transaction_type="BUY",
            executed_at=_now(),
            source="hsbc",
            source_record_id="HSBC-TXN-001",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_transaction(
                db_session,
                account_id=account.id,
                transaction_type="SELL",
                executed_at=_now(),
                source="hsbc",
                source_record_id="HSBC-TXN-001",
            )
            db_session.commit()
        db_session.rollback()

    def test_null_source_record_id_allows_multiple_entries(self, db_session: Session):
        """Duplicates without source_record_id are allowed — no unique constraint."""
        from apps.api.repositories.portfolio_foundation import create_asset, create_position

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="manual",
            source_record_id=None,
        )
        create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("200"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="manual",
            source_record_id=None,
        )
        db_session.commit()


# ═══════════════════════════════════════════════════════════════════════
# Position / account relationships
# ═══════════════════════════════════════════════════════════════════════


class TestPositionAccountRelationships:
    def test_position_linked_to_account(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_asset,
            create_position,
            list_latest_positions,
        )

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("500"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="interactive_brokers",
        )
        db_session.commit()

        positions = list_latest_positions(db_session, account_id=account.id)
        assert len(positions) == 1
        assert positions[0].account_id == account.id

    def test_is_latest_supersede_workflow(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_asset,
            create_position,
            list_latest_positions,
            supersede_latest_positions,
        )

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test ETF", asset_type="ETF", currency="USD",
        )
        db_session.commit()

        # First position
        pos1 = create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("100"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="interactive_brokers",
        )
        db_session.commit()
        assert pos1.is_latest is True

        # Supersede existing
        supersede_latest_positions(db_session, account.id, asset.id)
        pos2 = create_position(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            quantity=Decimal("150"),
            quantity_source="provider_reported",
            avg_cost_currency="USD",
            market_price_currency="USD",
            observed_at=_now(),
            source="interactive_brokers",
        )
        db_session.commit()

        # Verify is_latest semantics
        db_session.refresh(pos1)
        assert pos1.is_latest is False
        assert pos2.is_latest is True

        latest = list_latest_positions(db_session, account_id=account.id)
        assert len(latest) == 1
        assert latest[0].id == pos2.id


# ═══════════════════════════════════════════════════════════════════════
# Transaction relationships
# ═══════════════════════════════════════════════════════════════════════


class TestTransactionRelationships:
    def test_transaction_valid_types_accepted(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_transaction

        _, _, account = _create_household(db_session)
        db_session.commit()

        for txn_type in ["BUY", "SELL", "DIVIDEND", "INTEREST", "DEPOSIT",
                         "WITHDRAWAL", "FEE", "TRANSFER_IN", "TRANSFER_OUT", "SPLIT", "OTHER"]:
            txn = create_transaction(
                db_session,
                account_id=account.id,
                transaction_type=txn_type,
                executed_at=_now(),
                source="manual",
            )
            assert txn.transaction_type == txn_type

        db_session.rollback()

    def test_transaction_invalid_type_rejected(self, db_session: Session):
        _, _, account = _create_household(db_session)
        db_session.commit()

        with pytest.raises(IntegrityError):
            from apps.api.models import Transaction
            txn = Transaction(
                id=uuid4(),
                account_id=account.id,
                transaction_type="OPTION_EXERCISE",
                executed_at=_now(),
                source="manual",
            )
            db_session.add(txn)
            db_session.commit()
        db_session.rollback()

    def test_transaction_list_by_account(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_transaction,
            list_transactions,
        )

        _, _, account = _create_household(db_session)
        db_session.commit()

        create_transaction(
            db_session,
            account_id=account.id,
            transaction_type="DEPOSIT",
            amount=Decimal("10000"),
            amount_currency="USD",
            executed_at=_now(),
            source="hsbc",
        )
        db_session.commit()

        txns = list_transactions(db_session, account_id=account.id)
        assert len(txns) == 1
        assert txns[0].transaction_type == "DEPOSIT"

    def test_transaction_quantity_amount_for_buy(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_asset,
            create_transaction,
        )

        _, _, account = _create_household(db_session)
        asset = create_asset(
            db_session, name="Test Stock", asset_type="STOCK", currency="USD",
        )
        db_session.commit()

        txn = create_transaction(
            db_session,
            account_id=account.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("100"),
            price=Decimal("50.50"),
            price_currency="USD",
            amount=Decimal("5050.00"),
            amount_currency="USD",
            fee=Decimal("5.00"),
            fee_currency="USD",
            executed_at=_now(),
            source="interactive_brokers",
        )
        db_session.commit()

        assert txn.quantity == Decimal("100")
        assert txn.price == Decimal("50.50")
        assert txn.amount == Decimal("5050.00")
        assert txn.fee == Decimal("5.00")


# ═══════════════════════════════════════════════════════════════════════
# FX Rate constraints
# ═══════════════════════════════════════════════════════════════════════


class TestFxRateConstraints:
    def test_create_valid_fx_rate(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_fx_rate

        rate = create_fx_rate(
            db_session,
            from_currency="USD",
            to_currency="HKD",
            rate=Decimal("7.8500"),
            rate_source="manual",
            observed_at=_now(),
        )
        db_session.commit()
        assert rate.id is not None

    def test_fx_rate_same_currency_rejected(self, db_session: Session):
        with pytest.raises(IntegrityError):
            from apps.api.models import FxRate
            rate = FxRate(
                id=uuid4(),
                from_currency="USD",
                to_currency="USD",
                rate=Decimal("1.0"),
                rate_source="manual",
                observed_at=_now(),
            )
            db_session.add(rate)
            db_session.commit()
        db_session.rollback()

    def test_fx_rate_duplicate_observation_rejected(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_fx_rate

        now = _now()
        create_fx_rate(
            db_session,
            from_currency="USD",
            to_currency="CNY",
            rate=Decimal("7.2500"),
            rate_source="manual",
            observed_at=now,
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_fx_rate(
                db_session,
                from_currency="USD",
                to_currency="CNY",
                rate=Decimal("7.2500"),
                rate_source="manual",
                observed_at=now,
            )
            db_session.commit()
        db_session.rollback()

    def test_fx_rate_invalid_currency_rejected(self, db_session: Session):
        with pytest.raises(IntegrityError):
            from apps.api.models import FxRate
            rate = FxRate(
                id=uuid4(),
                from_currency="US",  # 2 chars
                to_currency="HKD",
                rate=Decimal("7.85"),
                rate_source="manual",
                observed_at=_now(),
            )
            db_session.add(rate)
            db_session.commit()
        db_session.rollback()

    def test_get_latest_fx_rate(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_fx_rate,
            get_latest_fx_rate,
        )

        t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 2, tzinfo=timezone.utc)

        create_fx_rate(
            db_session, from_currency="USD", to_currency="HKD",
            rate=Decimal("7.80"), rate_source="ecb", observed_at=t1,
        )
        create_fx_rate(
            db_session, from_currency="USD", to_currency="HKD",
            rate=Decimal("7.85"), rate_source="ecb", observed_at=t2,
        )
        db_session.commit()

        latest = get_latest_fx_rate(db_session, "USD", "HKD")
        assert latest is not None
        assert latest.rate == Decimal("7.85")
        assert latest.observed_at == t2


# ═══════════════════════════════════════════════════════════════════════
# Data Sources
# ═══════════════════════════════════════════════════════════════════════


class TestDataSourceConstraints:
    def test_create_valid_data_source(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_data_source

        source = create_data_source(
            db_session,
            source_key="interactive_brokers",
            source_type="broker",
            display_name="Interactive Brokers",
        )
        db_session.commit()
        assert source.id is not None
        assert source.source_key == "interactive_brokers"

    def test_data_source_key_unique(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import create_data_source

        create_data_source(
            db_session, source_key="hsbc", source_type="bank",
        )
        db_session.commit()

        with pytest.raises(IntegrityError):
            create_data_source(
                db_session, source_key="hsbc", source_type="broker",
            )
            db_session.commit()
        db_session.rollback()

    def test_data_source_invalid_type_rejected(self, db_session: Session):
        with pytest.raises(IntegrityError):
            from apps.api.models import DataSource
            source = DataSource(
                id=uuid4(),
                source_key="some_api",
                source_type="rest_api",
            )
            db_session.add(source)
            db_session.commit()
        db_session.rollback()

    def test_list_active_sources(self, db_session: Session):
        from apps.api.repositories.portfolio_foundation import (
            create_data_source,
            list_active_data_sources,
        )

        create_data_source(
            db_session, source_key="ib", source_type="broker",
        )
        create_data_source(
            db_session, source_key="hsbc", source_type="bank",
        )
        db_session.commit()

        active = list_active_data_sources(db_session)
        assert len(active) == 2


# ═══════════════════════════════════════════════════════════════════════
# Pydantic schema validation
# ═══════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    def test_asset_create_validates_type(self):
        from pydantic import ValidationError

        from apps.api.portfolio_foundation_schemas import AssetCreate

        # Valid
        asset = AssetCreate(
            name="Apple Inc.",
            asset_type="STOCK",
            currency="USD",
        )
        assert asset.asset_type == "STOCK"

        # Invalid
        with pytest.raises(ValidationError):
            AssetCreate(
                name="Bad",
                asset_type="CRYPTO",
                currency="USD",
            )

    def test_asset_create_validates_currency(self):
        from pydantic import ValidationError

        from apps.api.portfolio_foundation_schemas import AssetCreate

        with pytest.raises(ValidationError):
            AssetCreate(
                name="Bad Currency",
                asset_type="STOCK",
                currency="US",
            )

    def test_position_create_validates_source(self):
        from pydantic import ValidationError

        from apps.api.portfolio_foundation_schemas import PositionCreate

        with pytest.raises(ValidationError):
            PositionCreate(
                account_id=uuid4(),
                asset_id=uuid4(),
                quantity="100",
                quantity_source="unknown_source",
                observed_at=_now(),
                source="interactive_brokers",
            )

    def test_fx_rate_create_rejects_zero_rate(self):
        from pydantic import ValidationError

        from apps.api.portfolio_foundation_schemas import FxRateCreate

        with pytest.raises(ValidationError):
            FxRateCreate(
                from_currency="USD",
                to_currency="HKD",
                rate="0",
                rate_source="manual",
                observed_at=_now(),
            )

    def test_data_source_create_validates_type(self):
        from pydantic import ValidationError

        from apps.api.portfolio_foundation_schemas import DataSourceCreate

        with pytest.raises(ValidationError):
            DataSourceCreate(
                source_key="test",
                source_type="invalid_type",
            )
