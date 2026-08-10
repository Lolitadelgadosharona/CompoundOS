"""Sprint 010 Slice D — Authentication, Authorization, Audit & Escalation.

Revision ID: 0025_auth_and_audit
Revises: 0024_dashboard_learning
Create Date: 2026-08-10

Creates:
  - owner_api_keys              Hashed API key storage
  - audit_log                   Immutable security event records
  - notification_escalation_rules  Escalation config (schema only)
Extends:
  - notification_events          Add 'decision_review','escalation' sources
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_auth_and_audit"
down_revision: Union[str, None] = "0024_dashboard_learning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- owner_api_keys ---
    op.create_table(
        "owner_api_keys",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("revoked_by", sa.Text(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_owner_api_keys_key_hash", "owner_api_keys", ["key_hash"],
    )
    op.create_index(
        "ix_owner_api_keys_active", "owner_api_keys",
        ["revoked_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_check_constraint(
        "ck_audit_log_outcome",
        "audit_log",
        "outcome IN ('success','failure','denied')",
    )
    op.create_index(
        "ix_audit_log_event_type", "audit_log", ["event_type"],
    )
    op.create_index(
        "ix_audit_log_occurred_at", "audit_log", ["occurred_at"],
    )

    # Immutability trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_audit_log_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit log records are immutable'
                USING ERRCODE = '55000';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_log_immutability
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION fn_audit_log_immutability();
    """)

    # --- notification_escalation_rules ---
    op.create_table(
        "notification_escalation_rules",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("event_severity", sa.Text(), nullable=False),
        sa.Column("escalate_after_hours", sa.Integer(), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False,
                   server_default=sa.text("TRUE")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_check_constraint(
        "ck_notification_escalation_severity",
        "notification_escalation_rules",
        "event_severity IN ('critical','warning','info')",
    )

    # --- Extend notification_events source CHECK ---
    op.execute(
        "ALTER TABLE notification_events "
        "DROP CONSTRAINT IF EXISTS ck_notification_events_source"
    )
    op.create_check_constraint(
        "ck_notification_events_source",
        "notification_events",
        "source IN ("
        " 'guardian','committee','automation','backup','health',"
        " 'investment_idea','decision_review','escalation'"
        ")",
    )


def downgrade() -> None:
    # Restore original notification_events CHECK
    op.execute(
        "ALTER TABLE notification_events "
        "DROP CONSTRAINT IF EXISTS ck_notification_events_source"
    )
    op.create_check_constraint(
        "ck_notification_events_source",
        "notification_events",
        "source IN ("
        " 'guardian','committee','automation','backup','health',"
        " 'investment_idea'"
        ")",
    )

    op.drop_table("notification_escalation_rules")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_audit_log_immutability ON audit_log"
    )
    op.execute("DROP FUNCTION IF EXISTS fn_audit_log_immutability()")
    op.drop_table("audit_log")
    op.drop_table("owner_api_keys")
