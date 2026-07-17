"""Add Guardian monitoring persistence foundation.

Revision ID: 0007_guardian_foundation
Revises: 0006_portfolio_snapshot_status
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_guardian_foundation"
down_revision: Union[str, None] = "0006_portfolio_snapshot_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# PL/pgSQL trigger functions
# ---------------------------------------------------------------------------

GUARDIAN_CHECK_CONFIRMED_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_guardian_check_confirmed_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'guardian_check_confirmed_delete_forbidden';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'guardian_check_confirmed_update_forbidden';
    END IF;
    RETURN NEW;
END;
$$
"""

GUARDIAN_EVALUATION_RUNS_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_guardian_evaluation_runs_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'guardian_evaluation_run_delete_forbidden';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'guardian_evaluation_run_update_forbidden';
    END IF;
    RETURN NEW;
END;
$$
"""

GUARDIAN_EVENTS_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_guardian_events_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'guardian_event_delete_forbidden';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'guardian_event_update_forbidden';
    END IF;
    RETURN NEW;
END;
$$
"""

# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # --- Trigger functions ---
    op.execute(GUARDIAN_CHECK_CONFIRMED_IMMUTABILITY_FN)
    op.execute(GUARDIAN_EVALUATION_RUNS_IMMUTABILITY_FN)
    op.execute(GUARDIAN_EVENTS_IMMUTABILITY_FN)

    # --- guardian_checks ---
    op.create_table(
        "guardian_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey(
                "household_profiles.id",
                name="fk_guardian_checks_household_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column(
            "check_type",
            sa.Text(),
            sa.CheckConstraint(
                "check_type IN ('drift','category_exposure','staleness')",
                name="ck_guardian_checks_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('draft','confirmed')",
                name="ck_guardian_checks_status",
            ),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guardian_checks"),
        sa.UniqueConstraint("canonical_name", name="uq_guardian_checks_name"),
    )

    # --- guardian_check_drafts ---
    op.create_table(
        "guardian_check_drafts",
        sa.Column(
            "check_id",
            sa.Uuid(),
            sa.ForeignKey(
                "guardian_checks.id",
                name="fk_guardian_check_drafts_check_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "threshold_value",
            sa.Numeric(5, 2),
            sa.CheckConstraint(
                "threshold_value > 0 AND threshold_value <= 100",
                name="ck_guardian_drafts_threshold",
            ),
            nullable=False,
        ),
        sa.Column("target_category", sa.Text(), nullable=True),
        sa.Column("target_holding_category", sa.Text(), nullable=True),
        sa.Column(
            "staleness_days",
            sa.Integer(),
            sa.CheckConstraint(
                "staleness_days IS NULL OR staleness_days > 0",
                name="ck_guardian_drafts_staleness_days",
            ),
            nullable=True,
        ),
        sa.Column(
            "severity",
            sa.Text(),
            sa.CheckConstraint(
                "severity IN ('info','warning','critical')",
                name="ck_guardian_drafts_severity",
            ),
            nullable=False,
            server_default=sa.text("'info'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "expected_revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("check_id", name="pk_guardian_check_drafts"),
    )

    # --- guardian_check_confirmed ---
    op.create_table(
        "guardian_check_confirmed",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "check_id",
            sa.Uuid(),
            sa.ForeignKey(
                "guardian_checks.id",
                name="fk_guardian_check_confirmed_check_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("check_type", sa.Text(), nullable=False),
        sa.Column("threshold_value", sa.Numeric(5, 2), nullable=False),
        sa.Column("target_category", sa.Text(), nullable=True),
        sa.Column("target_holding_category", sa.Text(), nullable=True),
        sa.Column("staleness_days", sa.Integer(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guardian_check_confirmed"),
        sa.UniqueConstraint(
            "check_id", "version_number",
            name="uq_guardian_check_confirmed_version",
        ),
    )

    op.execute(
        "CREATE TRIGGER trg_guardian_check_confirmed_immutability "
        "BEFORE INSERT OR UPDATE OR DELETE ON guardian_check_confirmed "
        "FOR EACH STATEMENT EXECUTE FUNCTION "
        "fn_guardian_check_confirmed_immutability()"
    )

    # --- guardian_evaluation_runs ---
    op.create_table(
        "guardian_evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey(
                "household_profiles.id",
                name="fk_guardian_evaluation_runs_household_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            sa.CheckConstraint(
                "status IN ('completed','skipped_no_published_policy',"
                "'skipped_no_portfolio_snapshot','skipped_zero_total_value')",
                name="ck_guardian_evaluation_runs_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "checks_evaluated",
            sa.Integer(),
            sa.CheckConstraint(
                "checks_evaluated >= 0",
                name="ck_guardian_evaluation_runs_checks_evaluated",
            ),
            nullable=False,
        ),
        sa.Column(
            "events_created",
            sa.Integer(),
            sa.CheckConstraint(
                "events_created >= 0",
                name="ck_guardian_evaluation_runs_events_created",
            ),
            nullable=False,
        ),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_guardian_evaluation_runs"),
    )

    op.execute(
        "CREATE TRIGGER trg_guardian_evaluation_runs_immutability "
        "BEFORE INSERT OR UPDATE OR DELETE ON guardian_evaluation_runs "
        "FOR EACH STATEMENT EXECUTE FUNCTION "
        "fn_guardian_evaluation_runs_immutability()"
    )

    # --- guardian_events ---
    op.create_table(
        "guardian_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "evaluation_run_id",
            sa.Uuid(),
            sa.ForeignKey(
                "guardian_evaluation_runs.id",
                name="fk_guardian_events_evaluation_run_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            sa.Uuid(),
            sa.ForeignKey(
                "household_profiles.id",
                name="fk_guardian_events_household_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "check_id",
            sa.Uuid(),
            sa.ForeignKey(
                "guardian_checks.id",
                name="fk_guardian_events_check_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "check_version_id",
            sa.Uuid(),
            sa.ForeignKey(
                "guardian_check_confirmed.id",
                name="fk_guardian_events_check_version_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "policy_version_id",
            sa.Uuid(),
            sa.ForeignKey(
                "investment_policy_versions.id",
                name="fk_guardian_events_policy_version_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "portfolio_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey(
                "portfolio_snapshots.id",
                name="fk_guardian_events_portfolio_snapshot_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("check_type", sa.Text(), nullable=False),
        sa.Column("drift_pp", sa.Numeric(5, 2), nullable=True),
        sa.Column("exposure_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("staleness_days_actual", sa.Integer(), nullable=True),
        sa.Column(
            "exceeded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_guardian_events"),
    )

    op.execute(
        "CREATE UNIQUE INDEX uq_guardian_events_drift_exposure"
        " ON guardian_events"
        " (check_version_id, policy_version_id, portfolio_snapshot_id)"
        " WHERE check_type IN ('drift', 'category_exposure')"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_guardian_events_staleness"
        " ON guardian_events"
        " (check_version_id, portfolio_snapshot_id, as_of_date)"
        " WHERE check_type = 'staleness'"
    )

    op.execute(
        "CREATE TRIGGER trg_guardian_events_immutability "
        "BEFORE INSERT OR UPDATE OR DELETE ON guardian_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION "
        "fn_guardian_events_immutability()"
    )

    # --- Indices ---
    op.create_index(
        "ix_guardian_checks_household", "guardian_checks",
        ["household_id"],
    )
    op.create_index(
        "ix_guardian_check_confirmed_check", "guardian_check_confirmed",
        ["check_id"],
    )
    op.create_index(
        "ix_guardian_events_check", "guardian_events",
        ["check_id"],
    )
    op.create_index(
        "ix_guardian_events_run", "guardian_events",
        ["evaluation_run_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_guardian_events_drift_exposure")
    op.execute("DROP INDEX IF EXISTS uq_guardian_events_staleness")
    op.execute("DROP TRIGGER IF EXISTS trg_guardian_events_immutability ON guardian_events")
    op.execute("DROP TRIGGER IF EXISTS trg_guardian_evaluation_runs_immutability ON guardian_evaluation_runs")
    op.execute("DROP TRIGGER IF EXISTS trg_guardian_check_confirmed_immutability ON guardian_check_confirmed")

    op.drop_table("guardian_events")
    op.drop_table("guardian_evaluation_runs")
    op.drop_table("guardian_check_confirmed")
    op.drop_table("guardian_check_drafts")
    op.drop_table("guardian_checks")

    op.execute("DROP FUNCTION IF EXISTS fn_guardian_events_immutability()")
    op.execute("DROP FUNCTION IF EXISTS fn_guardian_evaluation_runs_immutability()")
    op.execute("DROP FUNCTION IF EXISTS fn_guardian_check_confirmed_immutability()")
