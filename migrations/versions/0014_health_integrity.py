"""Sprint 007 Slice B Health Integrity — worker heartbeat + restore timestamp.

Revision ID: 0014_health_integrity
Revises: 0013_backup_export_foundation
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_health_integrity"
down_revision: Union[str, None] = "0013_backup_export_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("worker_id", sa.String(64), nullable=False),
        sa.Column("instance_id", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_worker_heartbeats_worker_id", "worker_heartbeats", ["worker_id"])
    op.create_index("ix_worker_heartbeats_heartbeat_at", "worker_heartbeats", ["heartbeat_at"])
    op.create_unique_constraint(
        "uq_worker_heartbeats_instance", "worker_heartbeats",
        ["worker_id", "instance_id"],
    )

    # Add restore_verified_at to backup_records
    op.add_column(
        "backup_records",
        sa.Column("restore_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backup_records", "restore_verified_at")
    op.drop_table("worker_heartbeats")
