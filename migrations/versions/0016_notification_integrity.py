"""Sprint 007 Slice C Integrity — explicit opt-in + source prefs + singleton.

Revision ID: 0016_notification_integrity
Revises: 0015_notification_foundation
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_notification_integrity"
down_revision: Union[str, None] = "0015_notification_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("enabled_sources", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "notification_preferences",
        sa.Column("enabled_severities", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[\"critical\"]'::jsonb")),
    )
    # Expand delivery_status CHECK to include "unavailable"
    op.execute(
        "ALTER TABLE notification_events DROP CONSTRAINT ck_notification_events_delivery_status"
    )
    op.create_check_constraint(
        "ck_notification_events_delivery_status",
        "notification_events",
        "delivery_status IN ('pending', 'delivered', 'suppressed', 'failed', 'unavailable')",
    )
    # Singleton enforcement: at most one preferences row
    op.execute(
        "CREATE UNIQUE INDEX uq_notification_preferences_singleton"
        " ON notification_preferences ((1))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_preferences_singleton")
    # Revert CHECK constraint
    op.execute(
        "ALTER TABLE notification_events DROP CONSTRAINT ck_notification_events_delivery_status"
    )
    op.create_check_constraint(
        "ck_notification_events_delivery_status",
        "notification_events",
        "delivery_status IN ('pending', 'delivered', 'suppressed', 'failed')",
    )
    op.drop_column("notification_preferences", "enabled_severities")
    op.drop_column("notification_preferences", "enabled_sources")
    op.drop_column("notification_preferences", "enabled")
