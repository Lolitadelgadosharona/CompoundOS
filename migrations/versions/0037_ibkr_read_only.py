"""Add isolated read-only connection/sync history; no existing ledger rewrite."""

from alembic import op
from sqlalchemy import text

revision = "0037_ibkr_read_only"
down_revision = "0036_launch_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE ibkr_read_connections (
      id uuid PRIMARY KEY,
      household_id uuid NOT NULL REFERENCES household_profiles(id) ON DELETE RESTRICT,
      mode text NOT NULL CHECK(mode IN ('PAPER','LIVE')),
      enabled boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(household_id,mode));
    CREATE FUNCTION fn_ibkr_connection_identity_guard() RETURNS trigger AS $$
      BEGIN
        IF ROW(NEW.id,NEW.household_id,NEW.mode,NEW.created_at)
           IS DISTINCT FROM ROW(OLD.id,OLD.household_id,OLD.mode,OLD.created_at) THEN
          RAISE EXCEPTION 'IBKR_CONNECTION_IDENTITY_IMMUTABLE';
        END IF;
        RETURN NEW;
      END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER tr_ibkr_connection_identity_guard BEFORE UPDATE ON ibkr_read_connections
      FOR EACH ROW EXECUTE FUNCTION fn_ibkr_connection_identity_guard();
    CREATE TABLE ibkr_read_sync_runs (
      id uuid PRIMARY KEY,
      connection_id uuid NOT NULL REFERENCES ibkr_read_connections(id) ON DELETE RESTRICT,
      started_at timestamptz NOT NULL,
      completed_at timestamptz NOT NULL CHECK(completed_at>=started_at),
      status text NOT NULL CHECK(status IN ('CURRENT','UNRESOLVED','SYNC_FAILED')),
      received integer NOT NULL CHECK(received>=0),
      accepted integer NOT NULL CHECK(accepted>=0),
      unresolved integer NOT NULL CHECK(unresolved>=0),
      error_code text,
      snapshot jsonb NOT NULL,
      CHECK((status='SYNC_FAILED' AND error_code IS NOT NULL)
        OR (status<>'SYNC_FAILED' AND error_code IS NULL)));
    CREATE INDEX ix_ibkr_runs_connection_time ON ibkr_read_sync_runs(connection_id,completed_at);
    CREATE FUNCTION fn_ibkr_read_run_immutable() RETURNS trigger AS $$
      BEGIN RAISE EXCEPTION 'IBKR_SYNC_RUN_IMMUTABLE'; END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER tr_ibkr_read_run_immutable BEFORE UPDATE OR DELETE ON ibkr_read_sync_runs
      FOR EACH ROW EXECUTE FUNCTION fn_ibkr_read_run_immutable();
    """)


def downgrade():
    if (
        op.get_bind()
        .execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM ibkr_read_connections) "
                "OR EXISTS(SELECT 1 FROM ibkr_read_sync_runs)"
            )
        )
        .scalar()
    ):
        raise RuntimeError("IBKR history present; preserve/backup and use forward-compatible app")
    op.execute(
        "DROP TABLE ibkr_read_sync_runs; DROP FUNCTION fn_ibkr_read_run_immutable(); "
        "DROP TABLE ibkr_read_connections; DROP FUNCTION fn_ibkr_connection_identity_guard();"
    )
