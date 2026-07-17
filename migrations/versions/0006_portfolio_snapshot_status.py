"""Allow controlled snapshot status transition: current → superseded.

Revision ID: 0006_portfolio_snapshot_status
Revises: 0005_portfolio_cash_unit_price
Create Date: 2026-07-17

Owner Decision (2026-07-17):
  Option A — Allow current→superseded transition only.
  All other UPDATE and all DELETE remain forbidden.
  Snapshot holdings remain fully immutable.

Key change from 0004:
  Uses to_jsonb(row) - 'status' for future-proof column comparison
  rather than manually enumerating columns. Any column other than
  status that differs during current→superseded triggers an error.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_portfolio_snapshot_status"
down_revision: Union[str, None] = "0005_portfolio_cash_unit_price"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_FUNCTION = r"""
CREATE OR REPLACE FUNCTION public.fn_portfolio_snapshot_immutability()
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
        -- Allow exactly one controlled transition: current → superseded
        IF OLD.status = 'current' AND NEW.status = 'superseded' THEN
            -- Verify no other columns changed using JSONB row diff
            IF (to_jsonb(NEW) - 'status')
               IS NOT DISTINCT FROM
               (to_jsonb(OLD) - 'status')
            THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'portfolio_snapshot_update_column_not_allowed',
                DETAIL  = 'Only status may change during current→superseded '
                          'transition.';
        END IF;

        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'portfolio_snapshot_status_transition_forbidden',
            DETAIL  = format(
                'Cannot transition from %L to %L. '
                'Only current→superseded is allowed.',
                OLD.status, NEW.status
            );
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

DOWNGRADE_FUNCTION = r"""
CREATE OR REPLACE FUNCTION public.fn_portfolio_snapshot_immutability()
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


def upgrade() -> None:
    op.execute(UPGRADE_FUNCTION)


def downgrade() -> None:
    op.execute(DOWNGRADE_FUNCTION)
