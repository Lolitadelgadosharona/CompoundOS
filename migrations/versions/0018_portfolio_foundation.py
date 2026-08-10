"""Sprint 009 Slice A — Core Portfolio Schema + Asset Identity.

Revision ID: 0018_portfolio_foundation
Revises: 0017_backup_daily_allowlist
Create Date: 2026-08-09

Creates:
  - assets               Canonical financial instrument identity
  - positions            Account × asset holdings with source provenance
  - cash_balances        Cash per account per currency
  - transactions         Financial events (buy, sell, dividend, deposit…)
  - fx_rates             Exchange rates with timestamped observations
  - data_sources         Lightweight registry of known data providers

Extends:
  - accounts             Adds financial classification columns
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_portfolio_foundation"
down_revision: Union[str, None] = "0017_backup_daily_allowlist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ────────────────────────────────────────────────────────────────
    # 1. assets — canonical financial instrument identity
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("isin", sa.Text(), nullable=True),
        sa.Column("asset_class", sa.Text(), nullable=True),
        sa.Column("sub_asset_class", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "asset_type IN ('ETF','STOCK','BOND','CASH','MONEY_MARKET','FUND','OTHER')",
            name="ck_assets_type",
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_assets_currency",
        ),
        sa.CheckConstraint(
            "char_length(name) <= 200",
            name="ck_assets_name_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_assets_type", "assets", ["asset_type"], unique=False,
    )
    op.create_index(
        "ix_assets_currency", "assets", ["currency"], unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_assets_isin ON assets (isin)"
        " WHERE isin IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_assets_symbol_exchange_currency"
        " ON assets (symbol, exchange, currency)"
        " WHERE symbol IS NOT NULL"
    )

    # ────────────────────────────────────────────────────────────────
    # 2. Extend existing accounts — financial classification
    # ────────────────────────────────────────────────────────────────
    op.add_column(
        "accounts",
        sa.Column(
            "account_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'brokerage'"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "capital_bucket",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'CORE'"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "currency",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'USD'"),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column("provider", sa.Text(), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("provider_account_id", sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        "ck_accounts_type",
        "accounts",
        "account_type IN ('brokerage','bank','retirement','other')",
    )
    op.create_check_constraint(
        "ck_accounts_bucket",
        "accounts",
        "capital_bucket IN ('CORE','EXPLORATION','CASH_RESERVE','RETIREMENT','OTHER')",
    )
    op.create_check_constraint(
        "ck_accounts_currency",
        "accounts",
        "currency ~ '^[A-Z]{3}$'",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_accounts_provider_id"
        " ON accounts (provider, provider_account_id)"
        " WHERE provider IS NOT NULL AND provider_account_id IS NOT NULL"
    )

    # ────────────────────────────────────────────────────────────────
    # 3. positions — account × asset holdings with source provenance
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity_source", sa.Text(), nullable=False),
        sa.Column("avg_cost", sa.Numeric(20, 8), nullable=True),
        sa.Column("avg_cost_currency", sa.Text(), nullable=False),
        sa.Column("avg_cost_source", sa.Text(), nullable=True),
        sa.Column("market_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("market_price_currency", sa.Text(), nullable=False),
        sa.Column("market_price_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("market_value", sa.Numeric(20, 8), nullable=True),
        sa.Column("market_value_currency", sa.Text(), nullable=True),
        sa.Column("cost_basis", sa.Numeric(20, 8), nullable=True),
        sa.Column("cost_basis_currency", sa.Text(), nullable=True),
        sa.Column("unrealized_gain_loss", sa.Numeric(20, 8), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=True),
        sa.Column(
            "is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity >= 0",
            name="ck_positions_quantity",
        ),
        sa.CheckConstraint(
            "quantity_source IN ('provider_reported','compoundos_derived')",
            name="ck_positions_quantity_source",
        ),
        sa.CheckConstraint(
            "source IN "
            "('interactive_brokers','hsbc','schwab','csv','manual','compoundos_derived')",
            name="ck_positions_source",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_positions_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name="fk_positions_asset_id_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_positions_account_asset_latest",
        "positions",
        ["account_id", "asset_id", "is_latest"],
        unique=False,
    )
    op.create_index(
        "ix_positions_account_latest",
        "positions",
        ["account_id", "is_latest"],
        unique=False,
    )
    op.create_index(
        "ix_positions_source",
        "positions",
        ["source"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_positions_source_record"
        " ON positions (source, source_record_id)"
        " WHERE source_record_id IS NOT NULL"
    )

    # ────────────────────────────────────────────────────────────────
    # 4. cash_balances — cash per account per currency
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "cash_balances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 8), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=True),
        sa.Column(
            "is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_cash_balances_currency",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_cash_balances_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cash_balances_account_currency_latest",
        "cash_balances",
        ["account_id", "currency", "is_latest"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_cash_balances_source_record"
        " ON cash_balances (source, source_record_id)"
        " WHERE source_record_id IS NOT NULL"
    )

    # ────────────────────────────────────────────────────────────────
    # 5. transactions — financial events
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("transaction_type", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=True),
        sa.Column("price", sa.Numeric(20, 8), nullable=True),
        sa.Column("price_currency", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("amount_currency", sa.Text(), nullable=True),
        sa.Column("fee", sa.Numeric(20, 8), nullable=True),
        sa.Column("fee_currency", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "transaction_type IN "
            "('BUY','SELL','DIVIDEND','INTEREST','DEPOSIT',"
            "'WITHDRAWAL','FEE','TRANSFER_IN','TRANSFER_OUT','SPLIT','OTHER')",
            name="ck_transactions_type",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_transactions_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name="fk_transactions_asset_id_assets",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transactions_account_executed",
        "transactions",
        ["account_id", "executed_at"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_asset",
        "transactions",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_source",
        "transactions",
        ["source"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_transactions_source_record"
        " ON transactions (source, source_record_id)"
        " WHERE source_record_id IS NOT NULL"
    )

    # ────────────────────────────────────────────────────────────────
    # 6. fx_rates — exchange rates with timestamped observations
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_currency", sa.Text(), nullable=False),
        sa.Column("to_currency", sa.Text(), nullable=False),
        sa.Column("rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("rate_source", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_currency ~ '^[A-Z]{3}$' AND to_currency ~ '^[A-Z]{3}$'",
            name="ck_fx_rates_currency",
        ),
        sa.CheckConstraint(
            "from_currency != to_currency",
            name="ck_fx_rates_different",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_currency", "to_currency", "observed_at", "rate_source",
            name="uq_fx_rates",
        ),
    )
    op.create_index(
        "ix_fx_rates_from_to_observed",
        "fx_rates",
        ["from_currency", "to_currency", "observed_at"],
        unique=False,
    )

    # ────────────────────────────────────────────────────────────────
    # 7. data_sources — lightweight registry
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"),
        ),
        sa.Column("last_import_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('broker','bank','csv','manual')",
            name="ck_data_sources_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_data_sources_source_key"),
    )


def downgrade() -> None:
    # Drop partial indexes (must be explicitly dropped)
    op.execute("DROP INDEX IF EXISTS uq_positions_source_record")
    op.execute("DROP INDEX IF EXISTS uq_cash_balances_source_record")
    op.execute("DROP INDEX IF EXISTS uq_transactions_source_record")

    # Drop in reverse-dependency order
    op.drop_table("data_sources")
    op.drop_table("fx_rates")
    op.drop_table("transactions")
    op.drop_table("cash_balances")
    op.drop_table("positions")

    # Remove account extension columns
    op.execute("DROP INDEX IF EXISTS uq_accounts_provider_id")
    op.drop_constraint("ck_accounts_currency", "accounts", type_="check")
    op.drop_constraint("ck_accounts_bucket", "accounts", type_="check")
    op.drop_constraint("ck_accounts_type", "accounts", type_="check")
    op.drop_column("accounts", "provider_account_id")
    op.drop_column("accounts", "provider")
    op.drop_column("accounts", "currency")
    op.drop_column("accounts", "capital_bucket")
    op.drop_column("accounts", "account_type")

    op.drop_table("assets")
