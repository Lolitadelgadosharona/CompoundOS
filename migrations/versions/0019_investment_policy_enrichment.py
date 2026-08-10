"""Sprint 009 Slice B — Investment Policy Enrichment.

Revision ID: 0019_investment_policy_enrichment
Revises: 0018_portfolio_foundation
Create Date: 2026-08-10

Creates:
  - policy_capital_buckets  Capital allocation targets per policy version/draft
  - policy_rules            Extensible constraints versioned with policy
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_policy_enrichment"
down_revision: Union[str, None] = "0018_portfolio_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── PL/pgSQL trigger functions ──────────────────────────────────────────

POLICY_CAPITAL_BUCKETS_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_policy_capital_buckets_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.version_id IS NOT NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_capital_bucket_delete_forbidden';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.version_id IS NOT NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_capital_bucket_update_forbidden';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$
""".strip()

POLICY_RULES_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_policy_rules_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.version_id IS NOT NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_rule_delete_forbidden';
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.version_id IS NOT NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_rule_update_forbidden';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    RETURN NEW;
END;
$$
""".strip()


def upgrade() -> None:
    # ────────────────────────────────────────────────────────────────
    # 1. policy_capital_buckets — allocation targets
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "policy_capital_buckets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("bucket_name", sa.Text(), nullable=False),
        sa.Column("target_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("min_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("max_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(draft_id IS NOT NULL)::int + (version_id IS NOT NULL)::int = 1",
            name="ck_policy_capital_buckets_one_parent",
        ),
        sa.CheckConstraint(
            "target_pct >= 0 AND target_pct <= 100",
            name="ck_policy_capital_buckets_target_pct_range",
        ),
        sa.CheckConstraint(
            "min_pct IS NULL OR max_pct IS NULL OR min_pct <= max_pct",
            name="ck_policy_capital_buckets_min_max",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["investment_policy_drafts.id"],
            name="fk_policy_capital_buckets_draft_id_drafts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["investment_policy_versions.id"],
            name="fk_policy_capital_buckets_version_id_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_capital_buckets_draft",
        "policy_capital_buckets",
        ["draft_id", "sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_policy_capital_buckets_version",
        "policy_capital_buckets",
        ["version_id", "sort_order"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_policy_capital_buckets_draft_name"
        " ON policy_capital_buckets (draft_id, bucket_name)"
        " WHERE draft_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_policy_capital_buckets_version_name"
        " ON policy_capital_buckets (version_id, bucket_name)"
        " WHERE version_id IS NOT NULL"
    )

    # ────────────────────────────────────────────────────────────────
    # 2. policy_rules — extensible constraints
    # ────────────────────────────────────────────────────────────────
    op.create_table(
        "policy_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=True),
        sa.Column("version_id", sa.Uuid(), nullable=True),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("rule_value", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default=sa.text("'warning'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(draft_id IS NOT NULL)::int + (version_id IS NOT NULL)::int = 1",
            name="ck_policy_rules_one_parent",
        ),
        sa.CheckConstraint(
            "rule_type IN ("
            "'max_single_position_pct','max_sector_concentration_pct',"
            "'max_drawdown_pct','min_cash_reserve_pct',"
            "'approval_required_for','exploration_capital_limit',"
            "'custom')",
            name="ck_policy_rules_type",
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_policy_rules_severity",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["investment_policy_drafts.id"],
            name="fk_policy_rules_draft_id_drafts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["investment_policy_versions.id"],
            name="fk_policy_rules_version_id_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_rules_draft",
        "policy_rules",
        ["draft_id", "sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_policy_rules_version",
        "policy_rules",
        ["version_id", "sort_order"],
        unique=False,
    )

    # ────────────────────────────────────────────────────────────────
    # 3. Trigger functions + triggers (immutability for version rows)
    # ────────────────────────────────────────────────────────────────
    op.execute(POLICY_CAPITAL_BUCKETS_IMMUTABILITY_FN)
    op.execute(POLICY_RULES_IMMUTABILITY_FN)

    op.execute(
        """
        CREATE TRIGGER trg_policy_capital_buckets_immutability
        BEFORE UPDATE OR DELETE ON public.policy_capital_buckets
        FOR EACH ROW EXECUTE FUNCTION
        public.fn_policy_capital_buckets_immutability()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_rules_immutability
        BEFORE UPDATE OR DELETE ON public.policy_rules
        FOR EACH ROW EXECUTE FUNCTION
        public.fn_policy_rules_immutability()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_policy_rules_immutability"
        " ON public.policy_rules"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_policy_capital_buckets_immutability"
        " ON public.policy_capital_buckets"
    )
    op.execute("DROP FUNCTION IF EXISTS public.fn_policy_rules_immutability")
    op.execute("DROP FUNCTION IF EXISTS public.fn_policy_capital_buckets_immutability")

    op.drop_table("policy_rules")
    op.drop_table("policy_capital_buckets")
