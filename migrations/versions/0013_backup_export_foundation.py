"""Sprint 007 Slice A — Backup, Restore Verification & Owner Export persistence.

Revision ID: 0013_backup_export_foundation
Revises: 0012_ai_committee_foundation
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_backup_export_foundation"
down_revision: Union[str, None] = "0012_ai_committee_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backup_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("backup_type", sa.String(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("encryption", sa.String(), nullable=True),
        sa.Column("age_recipient", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("retention_category", sa.String(), nullable=True),
        sa.Column("restore_verified", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_backup_records_status", "backup_records", ["status"])
    op.create_index("ix_backup_records_retention_category", "backup_records", ["retention_category"])
    op.create_index("ix_backup_records_started_at", "backup_records", ["started_at"])

    op.create_check_constraint(
        "ck_backup_records_backup_type",
        "backup_records",
        "backup_type IN ('full')",
    )
    op.create_check_constraint(
        "ck_backup_records_status",
        "backup_records",
        "status IN ('requested', 'running', 'verifying', 'completed', 'failed', 'expired')",
    )
    op.create_check_constraint(
        "ck_backup_records_retention_category",
        "backup_records",
        "retention_category IS NULL OR retention_category IN ('daily', 'weekly', 'monthly', 'locked')",
    )

    op.create_table(
        "export_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_export_tasks_entity_type", "export_tasks", ["entity_type"])
    op.create_index("ix_export_tasks_expires_at", "export_tasks", ["expires_at"])

    op.create_check_constraint(
        "ck_export_tasks_entity_type",
        "export_tasks",
        "entity_type IN ('household', 'policy', 'portfolio', 'decisions', 'committee_sessions')",
    )
    op.create_check_constraint(
        "ck_export_tasks_format",
        "export_tasks",
        "format IN ('csv', 'json')",
    )
    op.create_check_constraint(
        "ck_export_tasks_status",
        "export_tasks",
        "status IN ('running', 'completed', 'failed')",
    )


def downgrade() -> None:
    op.drop_table("export_tasks")
    op.drop_table("backup_records")
