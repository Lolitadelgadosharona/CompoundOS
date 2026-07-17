"""Create HouseholdProfile and AuditEvent persistence.

Revision ID: 0001_household_persistence
Revises:
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_household_persistence"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("singleton_key", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("household_name", sa.Text(), nullable=False),
        sa.Column("base_currency", sa.Text(), nullable=False),
        sa.Column("investment_horizon", sa.Text(), nullable=False),
        sa.Column("liquidity_needs", sa.Text(), nullable=False),
        sa.Column("risk_statement", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False  # noqa: E501
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False  # noqa: E501
        ),
        sa.CheckConstraint("singleton_key", name="ck_household_profiles_singleton_key"),
        sa.CheckConstraint(
            "char_length(household_name) BETWEEN 1 AND 200",
            name="ck_household_profiles_name_length",
        ),
        sa.CheckConstraint(
            "base_currency ~ '^[A-Z]{3}$'",
            name="ck_household_profiles_currency_format",
        ),
        sa.CheckConstraint(
            "char_length(investment_horizon) <= 2000",
            name="ck_household_profiles_investment_horizon_length",
        ),
        sa.CheckConstraint(
            "char_length(liquidity_needs) <= 4000",
            name="ck_household_profiles_liquidity_needs_length",
        ),
        sa.CheckConstraint(
            "char_length(risk_statement) <= 4000",
            name="ck_household_profiles_risk_statement_length",
        ),
        sa.CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_household_profiles_notes_length",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key", name="uq_household_profiles_singleton_key"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False  # noqa: E501
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_events_household_order",
        "audit_events",
        ["household_id", "occurred_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_household_order", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("household_profiles")
