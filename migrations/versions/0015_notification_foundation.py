"""Sprint 007 Slice C — Notification persistence.

Revision ID: 0015_notification_foundation
Revises: 0014_health_integrity
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_notification_foundation"
down_revision: Union[str, None] = "0014_health_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_status", sa.String(), nullable=False),
        sa.Column("suppressed_reason", sa.String(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_notification_events_source", "notification_events", ["source"])
    op.create_index("ix_notification_events_fingerprint", "notification_events", ["fingerprint"])
    op.create_index("ix_notification_events_delivered_at", "notification_events", ["delivered_at"])
    op.create_index("ix_notification_events_occurred_at", "notification_events", ["occurred_at"])

    op.create_check_constraint(
        "ck_notification_events_source",
        "notification_events",
        "source IN ('guardian', 'committee', 'automation', 'backup', 'health')",
    )
    op.create_check_constraint(
        "ck_notification_events_severity",
        "notification_events",
        "severity IN ('info', 'warning', 'critical')",
    )
    op.create_check_constraint(
        "ck_notification_events_delivery_status",
        "notification_events",
        "delivery_status IN ('pending', 'delivered', 'suppressed', 'failed')",
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("quiet_hours_start", sa.Time(timezone=False), nullable=False,
                  server_default=sa.text("'22:00'")),
        sa.Column("quiet_hours_end", sa.Time(timezone=False), nullable=False,
                  server_default=sa.text("'08:00'")),
        sa.Column("timezone", sa.String(64), nullable=False,
                  server_default=sa.text("'UTC'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notification_events")
