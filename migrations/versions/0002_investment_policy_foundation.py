"""Add Investment Policy persistence and immutable snapshot enforcement.

Revision ID: 0002_investment_policy_foundation
Revises: 0001_household_persistence
Create Date: 2026-07-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_investment_policy_foundation"
down_revision: Union[str, None] = "0001_household_persistence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POLICY_TEXT_LIMITS = {
    "objectives": 4_000,
    "time_horizon": 2_000,
    "liquidity": 4_000,
    "diversification": 4_000,
    "contribution_policy": 4_000,
    "rebalancing_policy": 4_000,
    "prohibited_assets": 4_000,
    "leverage_policy": 4_000,
    "decision_process": 4_000,
    "notes": 8_000,
}


def policy_text_columns() -> list[sa.Column]:
    return [sa.Column(column_name, sa.Text(), nullable=False) for column_name in POLICY_TEXT_LIMITS]


def policy_text_checks(table_name: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            f"char_length({column_name}) <= {maximum}",
            name=f"ck_{table_name}_{column_name}_length",
        )
        for column_name, maximum in POLICY_TEXT_LIMITS.items()
    ]


VERSION_IMMUTABILITY_FUNCTION = r"""
CREATE FUNCTION public.fn_investment_policy_version_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_version_delete_forbidden';
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NEW.version_number <= 0
           OR NEW.status <> 'published'
           OR NEW.published_at IS NULL
           OR NEW.sealed_at IS NOT NULL
           OR NEW.superseded_at IS NOT NULL
           OR NEW.objectives IS NULL
           OR NEW.time_horizon IS NULL
           OR NEW.liquidity IS NULL
           OR NEW.diversification IS NULL
           OR NEW.contribution_policy IS NULL
           OR NEW.rebalancing_policy IS NULL
           OR NEW.prohibited_assets IS NULL
           OR NEW.leverage_policy IS NULL
           OR NEW.decision_process IS NULL
           OR NEW.notes IS NULL THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'policy_version_insert_invalid';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.sealed_at IS NULL THEN
        IF NEW.sealed_at IS NOT NULL
           AND ROW(
               NEW.id, NEW.policy_id, NEW.version_number, NEW.status,
               NEW.objectives, NEW.time_horizon, NEW.liquidity,
               NEW.diversification, NEW.contribution_policy,
               NEW.rebalancing_policy, NEW.prohibited_assets,
               NEW.leverage_policy, NEW.decision_process, NEW.notes,
               NEW.published_at, NEW.superseded_at
           ) IS NOT DISTINCT FROM ROW(
               OLD.id, OLD.policy_id, OLD.version_number, OLD.status,
               OLD.objectives, OLD.time_horizon, OLD.liquidity,
               OLD.diversification, OLD.contribution_policy,
               OLD.rebalancing_policy, OLD.prohibited_assets,
               OLD.leverage_policy, OLD.decision_process, OLD.notes,
               OLD.published_at, OLD.superseded_at
           ) THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_version_unsealed_update_forbidden';
    END IF;

    IF OLD.status = 'published'
       AND NEW.status = 'superseded'
       AND OLD.superseded_at IS NULL
       AND NEW.superseded_at IS NOT NULL
       AND ROW(
           NEW.id, NEW.policy_id, NEW.version_number,
           NEW.objectives, NEW.time_horizon, NEW.liquidity,
           NEW.diversification, NEW.contribution_policy,
           NEW.rebalancing_policy, NEW.prohibited_assets,
           NEW.leverage_policy, NEW.decision_process, NEW.notes,
           NEW.published_at, NEW.sealed_at
       ) IS NOT DISTINCT FROM ROW(
           OLD.id, OLD.policy_id, OLD.version_number,
           OLD.objectives, OLD.time_horizon, OLD.liquidity,
           OLD.diversification, OLD.contribution_policy,
           OLD.rebalancing_policy, OLD.prohibited_assets,
           OLD.leverage_policy, OLD.decision_process, OLD.notes,
           OLD.published_at, OLD.sealed_at
       ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION USING
        ERRCODE = '55000',
        MESSAGE = 'policy_version_sealed_update_forbidden';
END;
$$
"""

VERSION_ALLOCATION_IMMUTABILITY_FUNCTION = r"""
CREATE FUNCTION public.fn_investment_policy_version_allocation_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_version_allocation_update_forbidden';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_version_allocation_delete_forbidden';
    END IF;

    PERFORM 1
    FROM public.investment_policy_versions
    WHERE id = NEW.version_id AND sealed_at IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'policy_version_allocation_parent_sealed';
    END IF;

    RETURN NEW;
END;
$$
"""

VERSION_SEALING_FUNCTION = r"""
CREATE FUNCTION public.fn_investment_policy_version_require_sealed()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.investment_policy_versions
        WHERE sealed_at IS NULL
    ) THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'policy_version_unsealed_at_commit';
    END IF;
    RETURN NULL;
END;
$$
"""


def upgrade() -> None:
    # The approved descriptive revision identifier is longer than Alembic's
    # default VARCHAR(32). Widen the internal version column before Alembic writes
    # this revision at the end of the transaction. Downgrade intentionally keeps
    # the compatible width so Alembic can first write the shorter 0001 identifier.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.drop_index("ix_audit_events_household_order", table_name="audit_events")
    op.add_column(
        "audit_events",
        sa.Column(
            "sequence_number",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_audit_events_sequence_number", "audit_events", ["sequence_number"]
    )
    op.create_index(
        "ix_audit_events_household_order",
        "audit_events",
        ["household_id", "sequence_number"],
        unique=False,
    )

    op.create_table(
        "investment_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household_profiles.id"],
            name="fk_investment_policies_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", name="uq_investment_policies_household_id"),
    )

    op.create_table(
        "investment_policy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        *policy_text_columns(),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_investment_policy_versions_version_number_positive",
        ),
        sa.CheckConstraint(
            "status IN ('published', 'superseded')",
            name="ck_investment_policy_versions_status",
        ),
        sa.CheckConstraint(
            "(status = 'published' AND superseded_at IS NULL) "
            "OR (status = 'superseded' AND superseded_at IS NOT NULL)",
            name="ck_investment_policy_versions_status_timestamps",
        ),
        *policy_text_checks("investment_policy_versions"),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["investment_policies.id"],
            name="fk_investment_policy_versions_policy_id_investment_policies",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "policy_id",
            "version_number",
            name="uq_investment_policy_versions_policy_version",
        ),
    )
    op.create_index(
        "uq_investment_policy_versions_current_published",
        "investment_policy_versions",
        ["policy_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_investment_policy_versions_policy_history",
        "investment_policy_versions",
        ["policy_id", sa.text("version_number DESC")],
        unique=False,
    )

    op.create_table(
        "investment_policy_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *policy_text_columns(),
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
            "revision > 0", name="ck_investment_policy_drafts_revision_positive"
        ),
        *policy_text_checks("investment_policy_drafts"),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["investment_policies.id"],
            name="fk_investment_policy_drafts_policy_id_investment_policies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["investment_policy_versions.id"],
            name="fk_investment_policy_drafts_source_version_id_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", name="uq_investment_policy_drafts_policy_id"),
    )
    op.create_index(
        "ix_investment_policy_drafts_source_version_id",
        "investment_policy_drafts",
        ["source_version_id"],
        unique=False,
    )

    op.create_table(
        "investment_policy_draft_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("asset_class_name", sa.Text(), nullable=False),
        sa.Column("normalized_asset_class_name", sa.Text(), nullable=False),
        sa.Column("target_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "char_length(asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_draft_allocations_name_length",
        ),
        sa.CheckConstraint(
            "char_length(normalized_asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_draft_allocations_normalized_name_length",
        ),
        sa.CheckConstraint(
            "target_percentage > 0.00 AND target_percentage <= 100.00",
            name="ck_investment_policy_draft_allocations_percentage_range",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_investment_policy_draft_allocations_sort_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["investment_policy_drafts.id"],
            name="fk_policy_draft_allocations_draft_id_policy_drafts",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id",
            "normalized_asset_class_name",
            name="uq_investment_policy_draft_allocations_normalized_name",
        ),
        sa.UniqueConstraint(
            "draft_id",
            "sort_order",
            name="uq_investment_policy_draft_allocations_sort_order",
        ),
    )
    op.create_index(
        "ix_investment_policy_draft_allocations_draft_id",
        "investment_policy_draft_allocations",
        ["draft_id"],
        unique=False,
    )

    op.create_table(
        "investment_policy_version_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("asset_class_name", sa.Text(), nullable=False),
        sa.Column("normalized_asset_class_name", sa.Text(), nullable=False),
        sa.Column("target_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "char_length(asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_version_allocations_name_length",
        ),
        sa.CheckConstraint(
            "char_length(normalized_asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_version_allocations_normalized_name_length",
        ),
        sa.CheckConstraint(
            "target_percentage > 0.00 AND target_percentage <= 100.00",
            name="ck_investment_policy_version_allocations_percentage_range",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_investment_policy_version_allocations_sort_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["investment_policy_versions.id"],
            name="fk_policy_version_allocations_version_id_policy_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_id",
            "normalized_asset_class_name",
            name="uq_investment_policy_version_allocations_normalized_name",
        ),
        sa.UniqueConstraint(
            "version_id",
            "sort_order",
            name="uq_investment_policy_version_allocations_sort_order",
        ),
    )
    op.create_index(
        "ix_investment_policy_version_allocations_version_order",
        "investment_policy_version_allocations",
        ["version_id", "sort_order"],
        unique=False,
    )

    op.execute(VERSION_IMMUTABILITY_FUNCTION)
    op.execute(VERSION_ALLOCATION_IMMUTABILITY_FUNCTION)
    op.execute(VERSION_SEALING_FUNCTION)
    op.execute(
        """
        CREATE TRIGGER trg_investment_policy_version_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.investment_policy_versions
        FOR EACH ROW EXECUTE FUNCTION public.fn_investment_policy_version_immutability()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_investment_policy_version_allocation_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.investment_policy_version_allocations
        FOR EACH ROW EXECUTE FUNCTION public.fn_investment_policy_version_allocation_immutability()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_investment_policy_version_sealed_at_commit
        AFTER INSERT OR UPDATE ON public.investment_policy_versions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.fn_investment_policy_version_require_sealed()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_investment_policy_version_sealed_at_commit "
        "ON public.investment_policy_versions"
    )
    op.execute(
        "DROP TRIGGER trg_investment_policy_version_allocation_immutability "
        "ON public.investment_policy_version_allocations"
    )
    op.execute(
        "DROP TRIGGER trg_investment_policy_version_immutability "
        "ON public.investment_policy_versions"
    )
    op.execute("DROP FUNCTION public.fn_investment_policy_version_require_sealed()")
    op.execute("DROP FUNCTION public.fn_investment_policy_version_allocation_immutability()")
    op.execute("DROP FUNCTION public.fn_investment_policy_version_immutability()")

    op.drop_index(
        "ix_investment_policy_version_allocations_version_order",
        table_name="investment_policy_version_allocations",
    )
    op.drop_table("investment_policy_version_allocations")
    op.drop_index(
        "ix_investment_policy_draft_allocations_draft_id",
        table_name="investment_policy_draft_allocations",
    )
    op.drop_table("investment_policy_draft_allocations")
    op.drop_index(
        "ix_investment_policy_drafts_source_version_id",
        table_name="investment_policy_drafts",
    )
    op.drop_table("investment_policy_drafts")
    op.drop_index(
        "ix_investment_policy_versions_policy_history",
        table_name="investment_policy_versions",
    )
    op.drop_index(
        "uq_investment_policy_versions_current_published",
        table_name="investment_policy_versions",
    )
    op.drop_table("investment_policy_versions")
    op.drop_table("investment_policies")

    op.drop_index("ix_audit_events_household_order", table_name="audit_events")
    op.drop_constraint(
        "uq_audit_events_sequence_number", "audit_events", type_="unique"
    )
    op.drop_column("audit_events", "sequence_number")
    op.create_index(
        "ix_audit_events_household_order",
        "audit_events",
        ["household_id", "occurred_at", "id"],
        unique=False,
    )
