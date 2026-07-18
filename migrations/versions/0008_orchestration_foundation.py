"""Add Data Orchestration persistence foundation.

Revision ID: 0008_orchestration_foundation
Revises: 0007_guardian_foundation
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_orchestration_foundation"
down_revision: Union[str, None] = "0007_guardian_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# PL/pgSQL trigger functions
# ---------------------------------------------------------------------------

RUN_IMMUTABILITY_FN = r"""
CREATE FUNCTION public.fn_run_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status IN ('completed', 'failed', 'aborted') THEN
        IF NEW.status <> OLD.status THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_run_terminal_immutable',
                DETAIL = 'Run ' || OLD.id || ' is in terminal state ' || OLD.status;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_run_deletion_forbidden',
            DETAIL = 'Runs must never be deleted.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()

JOB_ALLOWLIST_FN = r"""
CREATE FUNCTION public.fn_job_definition_allowlist()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.job_type NOT IN ('guardian.evaluate_all', 'guardian.evaluate_one') THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_job_type_not_allowed',
            DETAIL = 'Job type ' || NEW.job_type || ' is not in the approved allowlist.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()

LEASE_TAKEOVER_PREVENTION_FN = r"""
CREATE FUNCTION public.fn_lease_takeover_prevention()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- When a lease is acquired, fencing_token increments
    IF TG_OP = 'INSERT' THEN
        NEW.fencing_token := COALESCE(
            (SELECT MAX(fencing_token) FROM leases WHERE run_id = NEW.run_id), 0
        ) + 1;
        RETURN NEW;
    END IF;
    -- Prevent direct fencing_token modification (only via takeover INSERT)
    IF TG_OP = 'UPDATE' AND NEW.fencing_token <> OLD.fencing_token THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_lease_fencing_token_immutable',
            DETAIL = 'Fencing token cannot be directly modified.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # --- Trigger functions ---
    op.execute(RUN_IMMUTABILITY_FN)
    op.execute(JOB_ALLOWLIST_FN)
    op.execute(LEASE_TAKEOVER_PREVENTION_FN)

    # --- job_definitions ---
    op.create_table(
        "job_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("job_params", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_job_definitions"),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household_profiles.id"],
            name="fk_job_definitions_household", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_job_definitions_household", "job_definitions", ["household_id"])

    # --- schedules ---
    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_definition_id", sa.Uuid(), nullable=False),
        sa.Column("execution_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_schedules"),
        sa.ForeignKeyConstraint(
            ["job_definition_id"], ["job_definitions.id"],
            name="fk_schedules_job_definition", ondelete="CASCADE",
        ),
        sa.UniqueConstraint("job_definition_id", name="uq_schedules_one_per_job"),
    )

    # --- runs ---
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_definition_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("triggered_by", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
        sa.UniqueConstraint("idempotency_key", name="uq_runs_idempotency_key"),
        sa.ForeignKeyConstraint(
            ["job_definition_id"], ["job_definitions.id"],
            name="fk_runs_job_definition", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"], ["schedules.id"],
            name="fk_runs_schedule", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household_profiles.id"],
            name="fk_runs_household", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_runs_job_definition", "runs", ["job_definition_id"])
    op.create_index("ix_runs_schedule", "runs", ["schedule_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    # Overlap prevention: at most one pending/running run per schedule
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_runs_one_active_per_schedule"
            " ON runs (schedule_id)"
            " WHERE status IN ('pending', 'running')"
        )
    )
    # Terminal state immutability trigger
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_run_immutability"
            " BEFORE UPDATE OR DELETE ON runs"
            " FOR EACH ROW EXECUTE FUNCTION fn_run_immutability()"
        )
    )

    # --- attempts ---
    op.create_table(
        "attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_attempts"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"],
            name="fk_attempts_run", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("run_id", "attempt_number", name="uq_attempts_run_attempt"),
    )
    op.create_index("ix_attempts_run", "attempts", ["run_id"])

    # --- leases ---
    op.create_table(
        "leases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_leases"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"],
            name="fk_leases_run", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("run_id", name="uq_leases_run"),
    )
    op.create_index("ix_leases_worker", "leases", ["worker_id"])
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_lease_takeover_prevention"
            " BEFORE INSERT OR UPDATE ON leases"
            " FOR EACH ROW EXECUTE FUNCTION fn_lease_takeover_prevention()"
        )
    )

    # --- job_definitions allowlist trigger ---
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_job_definition_allowlist"
            " BEFORE INSERT OR UPDATE ON job_definitions"
            " FOR EACH ROW EXECUTE FUNCTION fn_job_definition_allowlist()"
        )
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_job_definition_allowlist ON job_definitions")
    op.execute("DROP TRIGGER IF EXISTS trg_lease_takeover_prevention ON leases")
    op.execute("DROP TRIGGER IF EXISTS trg_run_immutability ON runs")
    op.execute("DROP INDEX IF EXISTS uq_runs_one_active_per_schedule")
    op.drop_table("leases")
    op.drop_table("attempts")
    op.drop_table("runs")
    op.drop_table("schedules")
    op.drop_table("job_definitions")
    op.execute("DROP FUNCTION IF EXISTS fn_lease_takeover_prevention")
    op.execute("DROP FUNCTION IF EXISTS fn_job_definition_allowlist")
    op.execute("DROP FUNCTION IF EXISTS fn_run_immutability")
