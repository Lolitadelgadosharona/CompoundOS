"""Final lease fencing: atomic takeover, expiry enforcement, worker_id protection.

Revision ID: 0010_lease_fencing
Revises: 0009_hardening
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_lease_fencing"
down_revision: Union[str, None] = "0009_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Stricter lease trigger v3: completes fencing ownership guarantees
# ---------------------------------------------------------------------------

LEASE_FENCING_V3 = r"""
CREATE OR REPLACE FUNCTION public.fn_lease_takeover_prevention_v3()
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
        -- Atomic takeover: token must be strictly OLD + 1
        IF NEW.fencing_token = OLD.fencing_token + 1 THEN
            -- Lease must be expired for takeover
            IF OLD.expires_at > now() THEN
                RAISE EXCEPTION USING
                    ERRCODE = '55000',
                    MESSAGE = 'orchestration_lease_takeover_unexpired',
                    DETAIL = 'Cannot takeover lease '
                        || OLD.id || ' before expiry at ' || OLD.expires_at;
            END IF;
            RETURN NEW;
        END IF;

        -- Reject worker_id change without token increment
        IF NEW.worker_id IS DISTINCT FROM OLD.worker_id
           AND NEW.fencing_token = OLD.fencing_token THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_lease_worker_id_immutable',
                DETAIL = 'Worker ID cannot be changed without atomic token increment.';
        END IF;

        -- Reject any other fencing_token modification
        IF NEW.fencing_token <> OLD.fencing_token THEN
            RAISE EXCEPTION USING
                ERRCODE = '55000',
                MESSAGE = 'orchestration_lease_fencing_token_immutable',
                DETAIL = 'Fencing token can only be incremented'
                    || ' by exactly 1 during atomic takeover of an expired lease.';
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
    # Replace lease trigger with v3 (expiry enforcement + worker_id protection)
    op.execute("DROP TRIGGER IF EXISTS trg_lease_takeover_prevention ON leases")
    op.execute("DROP FUNCTION IF EXISTS fn_lease_takeover_prevention_v2")

    op.execute(LEASE_FENCING_V3)

    op.execute(sa.text(
        "CREATE TRIGGER trg_lease_takeover_prevention"
        " BEFORE INSERT OR UPDATE ON leases"
        " FOR EACH ROW EXECUTE FUNCTION fn_lease_takeover_prevention_v3()"
    ))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # Restore v2 trigger from 0009
    op.execute("DROP TRIGGER IF EXISTS trg_lease_takeover_prevention ON leases")
    op.execute("DROP FUNCTION IF EXISTS fn_lease_takeover_prevention_v3")

    op.execute(r"""
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
        IF NEW.fencing_token = OLD.fencing_token + 1
           AND NEW.worker_id IS DISTINCT FROM OLD.worker_id THEN
            RETURN NEW;
        END IF;
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
    """.strip())

    op.execute(sa.text(
        "CREATE TRIGGER trg_lease_takeover_prevention"
        " BEFORE INSERT OR UPDATE ON leases"
        " FOR EACH ROW EXECUTE FUNCTION fn_lease_takeover_prevention_v2()"
    ))
