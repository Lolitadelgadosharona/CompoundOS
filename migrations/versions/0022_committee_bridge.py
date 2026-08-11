"""Sprint 010 Slice A — AI Investment Committee Integration Bridge.

Revision ID: 0022_committee_bridge
Revises: 0021_manual_import_foundation
Create Date: 2026-08-10

Creates:
  - committee_review_requests  Bridge investment_ideas → committee_sessions

Extends:
  - committee_evidence_items.source_type  Add portfolio_position, policy_bucket, investment_idea
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_committee_bridge"
down_revision: Union[str, None] = "0021_manual_import_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ────────────────────────────────────────────────────────────────
    # 1. committee_review_requests — Idea → Committee bridge
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "committee_review_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("investment_idea_id", sa.Uuid(), nullable=False),
        sa.Column("committee_session_id", sa.Uuid(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed')",
            name="ck_committee_review_requests_status",
        ),
        sa.CheckConstraint(
            "requested_by IN ('owner','committee','guardian')",
            name="ck_committee_review_requests_requested_by",
        ),
        sa.ForeignKeyConstraint(
            ["investment_idea_id"],
            ["investment_ideas.id"],
            name="fk_committee_review_requests_idea_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["committee_session_id"],
            ["committee_sessions.id"],
            name="fk_committee_review_requests_session_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_committee_review_requests_idea",
        "committee_review_requests",
        ["investment_idea_id"],
        unique=False,
    )
    op.create_index(
        "ix_committee_review_requests_session",
        "committee_review_requests",
        ["committee_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_committee_review_requests_status",
        "committee_review_requests",
        ["status"],
        unique=False,
    )

    # ────────────────────────────────────────────────────────────────
    # 2. Extend committee_evidence_items source_type CHECK
    # ────────────────────────────────────────────────────────────────
    # Drop old constraint, add new one with extended types
    op.execute(
        "ALTER TABLE committee_evidence_items "
        "DROP CONSTRAINT IF EXISTS ck_evidence_items_source_type"
    )
    op.create_check_constraint(
        "ck_evidence_items_source_type",
        "committee_evidence_items",
        "source_type IN ("
        " 'portfolio_snapshot', 'policy_version', 'guardian_event',"
        " 'decision', 'owner_claim', 'external',"
        " 'portfolio_position', 'policy_bucket', 'investment_idea'"
        ")",
    )


def downgrade() -> None:
    # Restore original evidence source types
    op.execute(
        "ALTER TABLE committee_evidence_items "
        "DROP CONSTRAINT IF EXISTS ck_evidence_items_source_type"
    )
    op.create_check_constraint(
        "ck_evidence_items_source_type",
        "committee_evidence_items",
        "source_type IN ("
        " 'portfolio_snapshot', 'policy_version', 'guardian_event',"
        " 'decision', 'owner_claim', 'external'"
        ")",
    )

    # Drop bridge table
    op.drop_table("committee_review_requests")
