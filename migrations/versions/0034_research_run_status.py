"""Fix research_runs status transitions — allow non-completed updates.

Revision ID: 0034_research_run_status
Revises: 0033_perspective_provenance
Create Date: 2026-08-15

The 0026 immutability trigger returned OLD for every non-completed UPDATE,
which silently discarded all status transitions (pending → analyzing →
generating_memo → completed/failed). This corrects the trigger to RETURN
NEW for non-completed updates while keeping completed runs immutable.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0034_research_run_status"
down_revision: Union[str, None] = "0033_perspective_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FIXED_FN = """
CREATE OR REPLACE FUNCTION fn_research_run_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.status = 'completed' THEN
        RAISE EXCEPTION 'Completed research runs are immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'completed' THEN
        RAISE EXCEPTION 'Completed research runs are immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RETURN NEW;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;
"""

_ORIGINAL_FN = """
CREATE OR REPLACE FUNCTION fn_research_run_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.status = 'completed' THEN
        RAISE EXCEPTION 'Completed research runs are immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'completed' THEN
        RAISE EXCEPTION 'Completed research runs are immutable'
            USING ERRCODE = '55000';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_FIXED_FN)


def downgrade() -> None:
    op.execute(_ORIGINAL_FN)
