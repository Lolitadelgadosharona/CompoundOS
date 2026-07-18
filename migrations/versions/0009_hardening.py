"""Add status CHECK constraints, strengthen terminal immutability, atomic lease takeover.

Revision ID: 0009_hardening
Revises: 0008_orchestration_foundation
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_hardening"
down_revision: Union[str, None] = "0008_orchestration_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Revised terminal immutability — full row protection (v2)
# ---------------------------------------------------------------------------

RUN_FULL_IMMUTABILITY_V2 = r"""
CREATE OR REPLACE FUNCTION public.fn_run_immutability_v2()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status IN ('completed', 'failed', 'aborted') THEN
        IF (to_jsonb(NEW) - 'id') IS DISTINCT FROM (to_jsonb(OLD) - 'id') THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_run_terminal_immutable',
                DETAIL = 'Run ' || OLD.id || ' is in terminal state ' || OLD.status
                    || ' and must not be modified.';
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

ATTEMPT_FULL_IMMUTABILITY_V2 = r"""
CREATE OR REPLACE FUNCTION public.fn_attempt_immutability_v2()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status IN ('succeeded', 'failed', 'aborted') THEN
        IF (to_jsonb(NEW) - 'id') IS DISTINCT FROM (to_jsonb(OLD) - 'id') THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_attempt_terminal_immutable',
                DETAIL = 'Attempt ' || OLD.id
                    || ' is in terminal state ' || OLD.status
                    || ' and must not be modified.';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_attempt_deletion_forbidden',
            DETAIL = 'Attempts must never be deleted.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()

LEASE_TAKEOVER_ATOMIC_V2 = r"""
CREATE OR REPLACE FUNCTION public.fn_lease_takeover_prevention_v2()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.fencing_token := COALESCE(
            (SELECT MAX(fencing_token) FROM leases WHERE run_id = NEW.run_id), 0
        ) + 1;
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        -- Atomic takeover: allow token increment with worker change
        IF NEW.fencing_token = OLD.fencing_token + 1
           AND NEW.worker_id IS DISTINCT FROM OLD.worker_id THEN
            RETURN NEW;
        END IF;
        -- Reject any other token modification
        IF NEW.fencing_token <> OLD.fencing_token THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_lease_fencing_token_immutable',
                DETAIL = 'Fencing token can only be incremented during atomic takeover.';
        END IF;
    END IF;
    RETURN NEW;
END;
$$
""".strip()


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # --- CHECK constraints ---
    op.create_check_constraint(
        "ck_runs_status",
        "runs",
        sa.text("status IN ('pending', 'running', 'completed', 'failed', 'aborted')"),
    )
    op.create_check_constraint(
        "ck_runs_triggered_by",
        "runs",
        sa.text("triggered_by IN ('schedule', 'manual')"),
    )
    op.create_check_constraint(
        "ck_attempts_status",
        "attempts",
        sa.text("status IN ('pending', 'running', 'succeeded', 'failed', 'aborted')"),
    )
    op.create_check_constraint(
        "ck_attempts_attempt_number_positive",
        "attempts",
        sa.text("attempt_number >= 1"),
    )

    # --- Replace terminal immutability triggers with v2 (full row) ---
    op.execute("DROP TRIGGER IF EXISTS trg_run_immutability ON runs")
    op.execute("DROP TRIGGER IF EXISTS trg_attempt_immutability ON attempts")
    op.execute("DROP FUNCTION IF EXISTS fn_run_immutability")
    op.execute("DROP FUNCTION IF EXISTS fn_attempt_immutability")

    op.execute(RUN_FULL_IMMUTABILITY_V2)
    op.execute(ATTEMPT_FULL_IMMUTABILITY_V2)

    op.execute(sa.text(
        "CREATE TRIGGER trg_run_immutability"
        " BEFORE UPDATE OR DELETE ON runs"
        " FOR EACH ROW EXECUTE FUNCTION fn_run_immutability_v2()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_attempt_immutability"
        " BEFORE UPDATE OR DELETE ON attempts"
        " FOR EACH ROW EXECUTE FUNCTION fn_attempt_immutability_v2()"
    ))

    # --- Replace lease takeover trigger with atomic v2 ---
    op.execute("DROP TRIGGER IF EXISTS trg_lease_takeover_prevention ON leases")
    op.execute("DROP FUNCTION IF EXISTS fn_lease_takeover_prevention")

    op.execute(LEASE_TAKEOVER_ATOMIC_V2)

    op.execute(sa.text(
        "CREATE TRIGGER trg_lease_takeover_prevention"
        " BEFORE INSERT OR UPDATE ON leases"
        " FOR EACH ROW EXECUTE FUNCTION fn_lease_takeover_prevention_v2()"
    ))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # --- Restore original v1 triggers ---
    op.execute("DROP TRIGGER IF EXISTS trg_run_immutability ON runs")
    op.execute("DROP TRIGGER IF EXISTS trg_attempt_immutability ON attempts")
    op.execute("DROP FUNCTION IF EXISTS fn_run_immutability_v2")
    op.execute("DROP FUNCTION IF EXISTS fn_attempt_immutability_v2")

    # Re-create v1 functions from 0008
    op.execute(r"""
CREATE OR REPLACE FUNCTION public.fn_run_immutability()
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
    """.strip())
    op.execute(r"""
CREATE OR REPLACE FUNCTION public.fn_attempt_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.status IN ('succeeded', 'failed', 'aborted') THEN
        IF NEW.status <> OLD.status THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_attempt_terminal_immutable',
                DETAIL = 'Attempt ' || OLD.id
                    || ' is in terminal state ' || OLD.status;
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_attempt_deletion_forbidden',
            DETAIL = 'Attempts must never be deleted.';
    END IF;
    RETURN NEW;
END;
$$
    """.strip())

    op.execute(sa.text(
        "CREATE TRIGGER trg_run_immutability"
        " BEFORE UPDATE OR DELETE ON runs"
        " FOR EACH ROW EXECUTE FUNCTION fn_run_immutability()"
    ))
    op.execute(sa.text(
        "CREATE TRIGGER trg_attempt_immutability"
        " BEFORE UPDATE OR DELETE ON attempts"
        " FOR EACH ROW EXECUTE FUNCTION fn_attempt_immutability()"
    ))

    # --- Restore original lease takeover v1 ---
    op.execute("DROP TRIGGER IF EXISTS trg_lease_takeover_prevention ON leases")
    op.execute("DROP FUNCTION IF EXISTS fn_lease_takeover_prevention_v2")

    op.execute(r"""
CREATE OR REPLACE FUNCTION public.fn_lease_takeover_prevention()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.fencing_token := COALESCE(
            (SELECT MAX(fencing_token) FROM leases WHERE run_id = NEW.run_id), 0
        ) + 1;
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.fencing_token <> OLD.fencing_token THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'orchestration_lease_fencing_token_immutable',
            DETAIL = 'Fencing token cannot be directly modified.';
    END IF;
    RETURN NEW;
END;
$$
    """.strip())

    op.execute(sa.text(
        "CREATE TRIGGER trg_lease_takeover_prevention"
        " BEFORE INSERT OR UPDATE ON leases"
        " FOR EACH ROW EXECUTE FUNCTION fn_lease_takeover_prevention()"
    ))

    # --- Drop CHECK constraints ---
    op.drop_constraint("ck_attempts_attempt_number_positive", "attempts")
    op.drop_constraint("ck_attempts_status", "attempts")
    op.drop_constraint("ck_runs_triggered_by", "runs")
    op.drop_constraint("ck_runs_status", "runs")
