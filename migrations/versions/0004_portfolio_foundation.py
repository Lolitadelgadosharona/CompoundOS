"""Add Portfolio persistence and immutable snapshot enforcement.

Revision ID: 0004_portfolio_foundation
Revises: 0003_decision_journal_foundation
Create Date: 2026-07-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_portfolio_foundation"
down_revision: Union[str, None] = "0003_decision_journal_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- PL/pgSQL trigger functions ---

PORTFOLIO_SNAPSHOT_IMMUTABILITY_FUNCTION = r"""
CREATE FUNCTION public.fn_portfolio_snapshot_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_snapshot_delete_forbidden';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_snapshot_update_forbidden';
    END IF;

    IF NEW.portfolio_id IS NULL
       OR NEW.version_number IS NULL
       OR NEW.valuation_date IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'portfolio_snapshot_insert_invalid';
    END IF;

    RETURN NEW;
END;
$$
"""

PORTFOLIO_SNAPSHOT_HOLDINGS_IMMUTABILITY_FUNCTION = r"""
CREATE FUNCTION public.fn_portfolio_snapshot_holdings_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_snapshot_holding_delete_forbidden';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_snapshot_holding_update_forbidden';
    END IF;

    IF NEW.snapshot_id IS NULL
       OR NEW.asset_name IS NULL
       OR NEW.asset_category IS NULL
       OR NEW.quantity IS NULL
       OR NEW.unit_price IS NULL
       OR NEW.total_value IS NULL
       OR NEW.valuation_date IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'portfolio_snapshot_holding_insert_invalid';
    END IF;

    RETURN NEW;
END;
$$
"""

PORTFOLIO_LIFECYCLE_FUNCTION = r"""
CREATE FUNCTION public.fn_portfolio_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_created_at_immutable';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_id_immutable';
    END IF;

    IF NEW.household_id IS DISTINCT FROM OLD.household_id THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_household_immutable';
    END IF;

    IF OLD.status IS DISTINCT FROM NEW.status THEN
        IF OLD.status = 'draft' AND NEW.status = 'active' THEN
            NULL;
        ELSIF OLD.status = 'active' AND NEW.status = 'draft' THEN
            NULL;
        ELSE
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'portfolio_invalid_status_transition',
                DETAIL = format(
                    'Transition from %L to %L is not permitted.',
                    OLD.status, NEW.status
                );
        END IF;
    END IF;

    RETURN NEW;
END;
$$
"""

PORTFOLIO_CURRENT_SNAPSHOT_FUNCTION = r"""
CREATE FUNCTION public.fn_portfolio_current_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_current_count bigint;
    v_portfolio_id uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_portfolio_id := OLD.portfolio_id;
    ELSE
        v_portfolio_id := NEW.portfolio_id;
    END IF;

    SELECT count(*)
    INTO v_current_count
    FROM public.portfolio_snapshots
    WHERE portfolio_id = v_portfolio_id
      AND status = 'current';

    IF v_current_count > 1 THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'portfolio_multiple_current_snapshots',
            DETAIL = format(
                'Portfolio %s has %s current snapshots.',
                v_portfolio_id, v_current_count
            );
    END IF;

    RETURN NULL;
END;
$$
"""

PORTFOLIO_DRAFT_HOLDINGS_CONSISTENCY_FUNCTION = r"""
CREATE FUNCTION public.fn_portfolio_draft_holdings_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_portfolio_id uuid;
    v_status text;
    v_has_draft boolean;
BEGIN
    IF TG_TABLE_NAME = 'portfolios' THEN
        IF TG_OP = 'DELETE' THEN
            v_portfolio_id := OLD.id;
        ELSE
            v_portfolio_id := NEW.id;
        END IF;
    ELSIF TG_TABLE_NAME = 'portfolio_drafts' THEN
        IF TG_OP = 'DELETE' THEN
            v_portfolio_id := OLD.portfolio_id;
        ELSE
            v_portfolio_id := NEW.portfolio_id;
        END IF;
    ELSE
        RETURN NEW;
    END IF;

    SELECT status INTO v_status
    FROM public.portfolios
    WHERE id = v_portfolio_id;

    IF v_status IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT EXISTS(
        SELECT 1 FROM public.portfolio_drafts
        WHERE portfolio_id = v_portfolio_id
    ) INTO v_has_draft;

    IF v_status = 'draft' AND NOT v_has_draft THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'portfolio_draft_requires_draft_row',
            DETAIL = format(
                'Portfolio %s has status draft but no draft row.',
                v_portfolio_id
            );
    END IF;

    IF v_status = 'active' AND v_has_draft THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'portfolio_active_cannot_have_draft',
            DETAIL = format(
                'Portfolio %s has status active but still has a draft.',
                v_portfolio_id
            );
    END IF;

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    # 1. portfolios (stable identity — one per household)
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active')",
            name="ck_portfolios_status",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household_profiles.id"],
            name="fk_portfolios_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            name="uq_portfolios_household_id",
        ),
    )

    # 2. accounts (organisational labels under portfolio)
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint(
            "char_length(name) <= 200",
            name="ck_accounts_name_length",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_accounts_sort_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_accounts_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_accounts_portfolio_id_sort_order",
        "accounts",
        ["portfolio_id", "sort_order"],
        unique=False,
    )

    # 3. portfolio_drafts (mutable working state, at most one per portfolio)
    op.create_table(
        "portfolio_drafts",
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column(
            "expected_revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("valuation_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "expected_revision >= 1",
            name="ck_portfolio_drafts_revision_positive",
        ),
        sa.CheckConstraint(
            "valuation_date IS NULL OR valuation_date <= CURRENT_DATE",
            name="ck_portfolio_drafts_valuation_date",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_portfolio_drafts_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("portfolio_id"),
    )

    # 4. portfolio_draft_holdings (mutable holding rows under draft)
    op.create_table(
        "portfolio_draft_holdings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("asset_name", sa.Text(), nullable=False),
        sa.Column("asset_category", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_portfolio_draft_holdings_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_portfolio_draft_holdings_price_nonnegative",
        ),
        sa.CheckConstraint(
            "valuation_date <= CURRENT_DATE",
            name="ck_portfolio_draft_holdings_valuation_date",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_portfolio_draft_holdings_sort_order_nonnegative",
        ),
        sa.CheckConstraint(
            "LOWER(asset_category) != 'cash' OR unit_price = 1.00",
            name="ck_portfolio_draft_holdings_cash_unit_price",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolio_drafts.portfolio_id"],
            name="fk_portfolio_draft_holdings_portfolio_id_drafts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_portfolio_draft_holdings_account_id_accounts",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_draft_holdings_portfolio_sort",
        "portfolio_draft_holdings",
        ["portfolio_id", "sort_order"],
        unique=False,
    )

    # 5. portfolio_snapshots (immutable confirmed point-in-time record)
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'current'"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("holding_count", sa.Integer(), nullable=True),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('current', 'superseded')",
            name="ck_portfolio_snapshots_status",
        ),
        sa.CheckConstraint(
            "valuation_date <= CURRENT_DATE",
            name="ck_portfolio_snapshots_date",
        ),
        sa.CheckConstraint(
            "holding_count IS NULL OR holding_count >= 0",
            name="ck_portfolio_snapshots_holding_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name="fk_portfolio_snapshots_portfolio_id_portfolios",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "portfolio_id",
            "version_number",
            name="uq_portfolio_snapshots_portfolio_version",
        ),
    )

    # 6. portfolio_snapshot_holdings (immutable holding rows under snapshot)
    op.create_table(
        "portfolio_snapshot_holdings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("asset_name", sa.Text(), nullable=False),
        sa.Column("asset_category", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("unit_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("total_value", sa.Numeric(20, 2), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("account_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_portfolio_snapshot_holdings_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price >= 0",
            name="ck_portfolio_snapshot_holdings_price_nonnegative",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_portfolio_snapshot_holdings_sort_order_nonnegative",
        ),
        sa.CheckConstraint(
            "LOWER(asset_category) != 'cash' OR unit_price = 1.00",
            name="ck_portfolio_snapshot_holdings_cash_unit_price",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["portfolio_snapshots.id"],
            name="fk_portfolio_snapshot_holdings_snapshot_id_snapshots",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_snapshot_holdings_snapshot_sort",
        "portfolio_snapshot_holdings",
        ["snapshot_id", "sort_order"],
        unique=False,
    )

    # 7. Create PL/pgSQL trigger functions
    op.execute(PORTFOLIO_SNAPSHOT_IMMUTABILITY_FUNCTION)
    op.execute(PORTFOLIO_SNAPSHOT_HOLDINGS_IMMUTABILITY_FUNCTION)
    op.execute(PORTFOLIO_LIFECYCLE_FUNCTION)
    op.execute(PORTFOLIO_CURRENT_SNAPSHOT_FUNCTION)
    op.execute(PORTFOLIO_DRAFT_HOLDINGS_CONSISTENCY_FUNCTION)

    # 8. Create triggers
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_snapshot_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.portfolio_snapshots
        FOR EACH ROW EXECUTE FUNCTION public.fn_portfolio_snapshot_immutability()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_snapshot_holdings_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.portfolio_snapshot_holdings
        FOR EACH ROW EXECUTE FUNCTION public.fn_portfolio_snapshot_holdings_immutability()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_lifecycle
        BEFORE UPDATE ON public.portfolios
        FOR EACH ROW EXECUTE FUNCTION public.fn_portfolio_lifecycle()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_portfolio_current_snapshot
        AFTER INSERT OR UPDATE OR DELETE ON public.portfolio_snapshots
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.fn_portfolio_current_snapshot()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_portfolio_draft_holdings_consistency_portfolios
        AFTER INSERT OR UPDATE ON public.portfolios
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.fn_portfolio_draft_holdings_consistency()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_portfolio_draft_holdings_consistency_drafts
        AFTER INSERT OR DELETE ON public.portfolio_drafts
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.fn_portfolio_draft_holdings_consistency()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_draft_holdings_consistency_drafts "
        "ON public.portfolio_drafts"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_draft_holdings_consistency_portfolios "
        "ON public.portfolios"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_current_snapshot "
        "ON public.portfolio_snapshots"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_lifecycle "
        "ON public.portfolios"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_snapshot_holdings_immutability "
        "ON public.portfolio_snapshot_holdings"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_portfolio_snapshot_immutability "
        "ON public.portfolio_snapshots"
    )

    op.execute("DROP FUNCTION IF EXISTS public.fn_portfolio_draft_holdings_consistency()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_portfolio_current_snapshot()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_portfolio_lifecycle()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_portfolio_snapshot_holdings_immutability()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_portfolio_snapshot_immutability()")

    op.drop_index(
        "ix_portfolio_snapshot_holdings_snapshot_sort",
        table_name="portfolio_snapshot_holdings",
    )
    op.drop_table("portfolio_snapshot_holdings")
    op.drop_table("portfolio_snapshots")
    op.drop_index(
        "ix_portfolio_draft_holdings_portfolio_sort",
        table_name="portfolio_draft_holdings",
    )
    op.drop_table("portfolio_draft_holdings")
    op.drop_table("portfolio_drafts")
    op.drop_index("ix_accounts_portfolio_id_sort_order", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("portfolios")
