"""Allow controlled snapshot status transition: current → superseded.

Revision ID: 0006_portfolio_snapshot_status_transition
Revises: 0005_portfolio_cash_unit_price
Create Date: 2026-07-17

Owner Decision (2026-07-17):
  Option A — Allow current→superseded transition only.
  All other UPDATE and all DELETE remain forbidden.
  Snapshot holdings remain fully immutable.

Background:
  0004 fn_portfolio_snapshot_immutability rejected ALL UPDATE.
  But the design requires current→superseded when a correction
  or new snapshot is confirmed. This migration relaxes the trigger
  to allow exactly that single controlled transition.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_portfolio_snapshot_status_transition"
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
            -- Verify no other columns changed
            IF OLD.id             IS NOT DISTINCT FROM NEW.id
               AND OLD.portfolio_id  IS NOT DISTINCT FROM NEW.portfolio_id
               AND OLD.version_number IS NOT DISTINCT FROM NEW.version_number
               AND OLD.confirmed_at   IS NOT DISTINCT FROM NEW.confirmed_at
               AND OLD.holding_count  IS NOT DISTINCT FROM NEW.holding_count
               AND OLD.valuation_date IS NOT DISTINCT FROM NEW.valuation_date
               AND OLD.notes          IS NOT DISTINCT FROM NEW.notes
            THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'portfolio_snapshot_update_column_not_allowed',
                DETAIL  = 'Only status may change during current→superseded transition.';
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
