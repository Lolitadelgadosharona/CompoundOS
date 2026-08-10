"""Sprint 010 Slice B — Guardian Intelligence.

Revision ID: 0023_guardian_intelligence
Revises: 0022_committee_bridge
Create Date: 2026-08-10

Extends:
  - guardian_checks.check_type  Add 5 new check types
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0023_guardian_intelligence"
down_revision: Union[str, None] = "0022_committee_bridge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE guardian_checks "
        "DROP CONSTRAINT IF EXISTS ck_guardian_checks_type"
    )
    op.create_check_constraint(
        "ck_guardian_checks_type",
        "guardian_checks",
        "check_type IN ("
        " 'drift','category_exposure','staleness',"
        " 'capital_bucket_drift',"
        " 'single_position_concentration',"
        " 'sector_concentration',"
        " 'exploration_capital_limit',"
        " 'data_quality_staleness'"
        ")",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE guardian_checks "
        "DROP CONSTRAINT IF EXISTS ck_guardian_checks_type"
    )
    op.create_check_constraint(
        "ck_guardian_checks_type",
        "guardian_checks",
        "check_type IN ('drift','category_exposure','staleness')",
    )
