"""Sprint 010 Slice C — Wealth Dashboard + Learning Loop.

Revision ID: 0024_dashboard_learning
Revises: 0023_guardian_intelligence
Create Date: 2026-08-10

Creates:
  - decision_reviews              Learning loop — scheduled outcome reviews
Extends:
  - decision_confirmed_snapshots  + review_30d, review_90d, review_1yr, review_outcome
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_dashboard_learning"
down_revision: Union[str, None] = "0023_guardian_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- decision_reviews ---
    op.create_table(
        "decision_reviews",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "decision_id", sa.UUID(), sa.ForeignKey(
                "decisions.id", name="fk_decision_reviews_decision_id",
                ondelete="RESTRICT",
            ), nullable=False,
        ),
        sa.Column(
            "investment_idea_id", sa.UUID(), sa.ForeignKey(
                "investment_ideas.id",
                name="fk_decision_reviews_investment_idea_id",
                ondelete="SET NULL",
            ), nullable=True,
        ),
        sa.Column("review_type", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.Column("actual_return_pct", sa.Numeric(8, 2), nullable=True),
        sa.Column("policy_compliant", sa.Boolean(), nullable=True),
        sa.Column("lessons_learned", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_check_constraint(
        "ck_decision_reviews_type",
        "decision_reviews",
        "review_type IN ('30_day','90_day','1_year','manual')",
    )
    op.create_unique_constraint(
        "uq_decision_reviews_decision_type",
        "decision_reviews",
        ["decision_id", "review_type"],
    )
    op.create_index(
        "ix_decision_reviews_scheduled", "decision_reviews",
        ["scheduled_at"],
    )

    # --- Extend decision_confirmed_snapshots ---
    op.add_column(
        "decision_confirmed_snapshots",
        sa.Column("review_30d", sa.Date(), nullable=True),
    )
    op.add_column(
        "decision_confirmed_snapshots",
        sa.Column("review_90d", sa.Date(), nullable=True),
    )
    op.add_column(
        "decision_confirmed_snapshots",
        sa.Column("review_1yr", sa.Date(), nullable=True),
    )
    op.add_column(
        "decision_confirmed_snapshots",
        sa.Column("review_outcome", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("decision_confirmed_snapshots", "review_outcome")
    op.drop_column("decision_confirmed_snapshots", "review_1yr")
    op.drop_column("decision_confirmed_snapshots", "review_90d")
    op.drop_column("decision_confirmed_snapshots", "review_30d")
    op.drop_table("decision_reviews")
