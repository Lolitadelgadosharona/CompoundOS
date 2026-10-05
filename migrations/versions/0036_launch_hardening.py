"""Add verified observation identity; preserve all native financial history."""

from alembic import op
from sqlalchemy import text

revision = "0036_launch_hardening"
down_revision = "0035_launch_foundation"
branch_labels = None
depends_on = None


UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def upgrade():
    op.execute("ALTER TABLE market_observations ADD COLUMN identity jsonb")
    op.execute("ALTER TABLE fx_rates ADD COLUMN identity jsonb")
    op.execute(
        "ALTER TABLE fx_rates ADD COLUMN quality text CHECK (quality IN ('OBSERVED','DELAYED'))"
    )
    op.execute(
        """
    CREATE OR REPLACE FUNCTION fn_capture_research_source() RETURNS trigger AS $$
    DECLARE rid uuid;
    BEGIN
      IF NEW.evidence_or_sources ~ 'research_run_id=__UUID__' THEN
        rid := substring(NEW.evidence_or_sources FROM 'research_run_id=(__UUID__)')::uuid;
        IF EXISTS(SELECT 1 FROM research_runs WHERE id=rid) THEN
          INSERT INTO decision_research_sources VALUES (NEW.decision_id,rid) ON CONFLICT DO NOTHING;
        END IF;
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    INSERT INTO decision_research_sources
      SELECT d.decision_id,r.id FROM decision_drafts d JOIN research_runs r
      ON r.id::text=lower(substring(d.evidence_or_sources FROM 'research_run_id=(__UUID__)'))
      ON CONFLICT DO NOTHING;
    """.replace("__UUID__", UUID_PATTERN)
    )


def downgrade():
    conn = op.get_bind()
    if conn.execute(
        text(
            "SELECT EXISTS(SELECT 1 FROM market_observations WHERE identity IS NOT NULL) "
            "OR EXISTS(SELECT 1 FROM fx_rates WHERE identity IS NOT NULL OR quality IS NOT NULL)"
        )
    ).scalar():
        raise RuntimeError(
            "Preserve verified observation evidence; roll forward or use compatible app"
        )
    op.execute("ALTER TABLE fx_rates DROP COLUMN quality, DROP COLUMN identity")
    op.execute("ALTER TABLE market_observations DROP COLUMN identity")
    # Keep the safe capture function. 0035 uses the same non-destructive parser.
