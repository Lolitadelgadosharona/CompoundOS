"""Add cash unit_price CHECK constraint to portfolio holding tables.

Revision ID: 0005_portfolio_cash_unit_price
Revises: 0004_portfolio_foundation
Create Date: 2026-07-17

OD-S3-012 requires cash holdings to have unit_price = 1.00.
This additive migration adds CHECK constraints at the database level
on both draft and snapshot holding tables, complementing the
service-level enforcement in apps/api/services/portfolios.py.

Category normalization: LOWER(BTRIM(asset_category)).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005_portfolio_cash_unit_price"
down_revision: Union[str, None] = "0004_portfolio_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_portfolio_draft_holdings_cash_unit_price",
        "portfolio_draft_holdings",
        "LOWER(BTRIM(asset_category)) != 'cash' OR unit_price = 1.00",
    )
    op.create_check_constraint(
        "ck_portfolio_snapshot_holdings_cash_unit_price",
        "portfolio_snapshot_holdings",
        "LOWER(BTRIM(asset_category)) != 'cash' OR unit_price = 1.00",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_portfolio_draft_holdings_cash_unit_price",
        "portfolio_draft_holdings",
        type_="check",
    )
    op.drop_constraint(
        "ck_portfolio_snapshot_holdings_cash_unit_price",
        "portfolio_snapshot_holdings",
        type_="check",
    )
