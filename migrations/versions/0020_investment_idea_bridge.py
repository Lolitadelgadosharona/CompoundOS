"""Sprint 009 Slice C — Investment Idea + Decision Bridge.

Revision ID: 0020_investment_idea_bridge
Revises: 0019_policy_enrichment
Create Date: 2026-08-10

Creates:
  - investment_ideas       Capture investment thoughts with lifecycle
  - idea_status_history    Append-only audit of status transitions

Extends:
  - decision_drafts        Add optional investment_idea_id FK
  - decision_confirmed_snapshots  Add optional investment_idea_id FK
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_investment_idea_bridge"
down_revision: Union[str, None] = "0019_policy_enrichment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── PL/pgSQL trigger function ──────────────────────────────────────────

IDEA_STATUS_HISTORY_TRIGGER_FN = r"""
CREATE FUNCTION public.fn_idea_status_history()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.idea_status_history
            (id, idea_id, old_status, new_status, reason)
        VALUES
            (gen_random_uuid(), NEW.id, NULL, NEW.status, 'Idea created');
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO public.idea_status_history
            (id, idea_id, old_status, new_status, reason)
        VALUES
            (gen_random_uuid(), NEW.id, OLD.status, NEW.status,
             COALESCE(NEW.status_change_reason, 'Status changed'));
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$
""".strip()


def upgrade() -> None:
    # ────────────────────────────────────────────────────────────────
    # 1. investment_ideas — investment thoughts with lifecycle
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "investment_ideas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("proposed_allocation_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("proposed_amount", sa.Numeric(20, 8), nullable=True),
        sa.Column("proposed_amount_currency", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("expected_holding_period", sa.Text(), nullable=True),
        sa.Column("expected_return_rationale", sa.Text(), nullable=True),
        sa.Column("downside_thesis", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("catalysts", sa.Text(), nullable=True),
        sa.Column("valuation_assumptions", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Text(), nullable=True),
        sa.Column("policy_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("status_change_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ("
            "'draft','under_review','approved','rejected',"
            "'deferred','cancelled')",
            name="ck_investment_ideas_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence IN"
            " ('HIGH','MEDIUM','LOW','SPECULATIVE')",
            name="ck_investment_ideas_confidence",
        ),
        sa.CheckConstraint(
            "source IN ('owner','committee','guardian','external')",
            name="ck_investment_ideas_source",
        ),
        sa.CheckConstraint(
            "char_length(title) <= 200",
            name="ck_investment_ideas_title_length",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household_profiles.id"],
            name="fk_investment_ideas_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name="fk_investment_ideas_asset_id_assets",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["investment_policy_versions.id"],
            name="fk_investment_ideas_policy_version_id_versions",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investment_ideas_household_status",
        "investment_ideas",
        ["household_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_investment_ideas_asset",
        "investment_ideas",
        ["asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_investment_ideas_policy_version",
        "investment_ideas",
        ["policy_version_id"],
        unique=False,
    )

    # ────────────────────────────────────────────────────────────────
    # 2. idea_status_history — append-only lifecycle audit
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "idea_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idea_id", sa.Uuid(), nullable=False),
        sa.Column("old_status", sa.Text(), nullable=True),
        sa.Column("new_status", sa.Text(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["idea_id"],
            ["investment_ideas.id"],
            name="fk_idea_status_history_idea_id_ideas",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_idea_status_history_idea",
        "idea_status_history",
        ["idea_id", "changed_at"],
        unique=False,
    )

    # ────────────────────────────────────────────────────────────────
    # 3. Status history trigger on investment_ideas
    # ────────────────────────────────────────────────────────────────
    op.execute(IDEA_STATUS_HISTORY_TRIGGER_FN)
    op.execute(
        """
        CREATE TRIGGER trg_idea_status_history
        AFTER INSERT OR UPDATE ON public.investment_ideas
        FOR EACH ROW EXECUTE FUNCTION public.fn_idea_status_history()
        """
    )

    # ────────────────────────────────────────────────────────────────
    # 4. Extend decision_drafts — add investment_idea_id
    # ────────────────────────────────────────────────────────────────
    op.add_column(
        "decision_drafts",
        sa.Column("investment_idea_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_decision_drafts_investment_idea_id_ideas",
        "decision_drafts",
        "investment_ideas",
        ["investment_idea_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ────────────────────────────────────────────────────────────────
    # 5. Extend decision_confirmed_snapshots — add investment_idea_id
    # ────────────────────────────────────────────────────────────────
    op.add_column(
        "decision_confirmed_snapshots",
        sa.Column("investment_idea_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_decision_snapshots_investment_idea_id_ideas",
        "decision_confirmed_snapshots",
        "investment_ideas",
        ["investment_idea_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove decision journal extensions
    op.drop_constraint(
        "fk_decision_snapshots_investment_idea_id_ideas",
        "decision_confirmed_snapshots",
        type_="foreignkey",
    )
    op.drop_column("decision_confirmed_snapshots", "investment_idea_id")

    op.drop_constraint(
        "fk_decision_drafts_investment_idea_id_ideas",
        "decision_drafts",
        type_="foreignkey",
    )
    op.drop_column("decision_drafts", "investment_idea_id")

    # Drop trigger + function
    op.execute("DROP TRIGGER IF EXISTS trg_idea_status_history ON public.investment_ideas")
    op.execute("DROP FUNCTION IF EXISTS public.fn_idea_status_history")

    # Drop tables in reverse order
    op.drop_table("idea_status_history")
    op.drop_table("investment_ideas")
