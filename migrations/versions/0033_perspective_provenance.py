"""Production Hardening — perspective model provenance.

Revision ID: 0033_perspective_provenance
Revises: 0032_decision_lifecycle_hardening
Create Date: 2026-08-14

Adds model-provenance columns to perspective_analyses so the REAL LLM
execution result (requested_model, resolved_model, provider, actual_model)
is persisted instead of a hardcoded model name.

All columns are nullable and additive — no destructive migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_perspective_provenance"
down_revision: Union[str, None] = "0032_decision_lifecycle_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("perspective_analyses",
                  sa.Column("requested_model", sa.Text(), nullable=True))
    op.add_column("perspective_analyses",
                  sa.Column("resolved_model", sa.Text(), nullable=True))
    op.add_column("perspective_analyses",
                  sa.Column("provider", sa.Text(), nullable=True))
    op.add_column("perspective_analyses",
                  sa.Column("actual_model", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("perspective_analyses", "actual_model")
    op.drop_column("perspective_analyses", "provider")
    op.drop_column("perspective_analyses", "resolved_model")
    op.drop_column("perspective_analyses", "requested_model")
