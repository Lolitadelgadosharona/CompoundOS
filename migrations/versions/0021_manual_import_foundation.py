"""Sprint 009 Slice D — Manual Import + Data Source Foundation.

Revision ID: 0021_manual_import_foundation
Revises: 0020_investment_idea_bridge
Create Date: 2026-08-10

Adds:
  - assets.confidence  Enum: 'verified' / 'unverified'
  - fn_transaction_immutability() trigger on transactions

No new tables. Import pipeline is a service layer on existing Slice A schema.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0021_manual_import_foundation"
down_revision: Union[str, None] = "0020_investment_idea_bridge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TRANSACTION_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_transaction_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Only allow updating nullable enrichment columns,
        -- not core financial fields
        IF (OLD.source IS DISTINCT FROM NEW.source)
           OR (OLD.source_record_id IS DISTINCT FROM NEW.source_record_id)
           OR (OLD.quantity IS DISTINCT FROM NEW.quantity)
           OR (OLD.price IS DISTINCT FROM NEW.price)
           OR (OLD.amount IS DISTINCT FROM NEW.amount)
           OR (OLD.amount_currency IS DISTINCT FROM NEW.amount_currency)
           OR (OLD.executed_at IS DISTINCT FROM NEW.executed_at)
           OR (OLD.transaction_type IS DISTINCT FROM NEW.transaction_type)
           OR (OLD.account_id IS DISTINCT FROM NEW.account_id)
           OR (OLD.asset_id IS DISTINCT FROM NEW.asset_id) THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'Financial transaction records are immutable. '
                          'Core fields (source, source_record_id, quantity, price, '
                          'amount, currency, executed_at, transaction_type, '
                          'account_id, asset_id) cannot be changed.';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'Financial transaction records cannot be deleted.';
    END IF;

    RETURN NEW;
END;
$$
""".strip()


def upgrade() -> None:
    # ────────────────────────────────────────────────────────────────
    # 1. Add confidence column to assets
    # ────────────────────────────────────────────────────────────────
    op.add_column(
        "assets",
        sa.Column(
            "confidence",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'verified'"),
        ),
    )
    op.create_check_constraint(
        "ck_assets_confidence",
        "assets",
        "confidence IN ('verified','unverified')",
    )

    # ────────────────────────────────────────────────────────────────
    # 2. Transaction immutability trigger
    # ────────────────────────────────────────────────────────────────
    op.execute(TRANSACTION_IMMUTABILITY_FN)
    op.execute(
        """
        CREATE TRIGGER trg_transaction_immutability
        BEFORE UPDATE OR DELETE ON public.transactions
        FOR EACH ROW EXECUTE FUNCTION public.fn_transaction_immutability()
        """
    )


def downgrade() -> None:
    # Drop trigger + function
    op.execute(
        "DROP TRIGGER IF EXISTS trg_transaction_immutability ON public.transactions"
    )
    op.execute("DROP FUNCTION IF EXISTS public.fn_transaction_immutability")

    # Drop constraint then column
    op.drop_constraint("ck_assets_confidence", "assets", type_="check")
    op.drop_column("assets", "confidence")
