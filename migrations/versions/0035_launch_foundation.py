"""Additive V1 evidence/configuration foundation; no ledger/history rewrite."""

from alembic import op

revision = "0035_launch_foundation"
down_revision = "0034_research_run_status"
branch_labels = None
depends_on = None


UUID_PATTERN = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-" "[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def upgrade():
    op.execute(
        """
    CREATE TABLE owner_web_sessions (
      token_hash text PRIMARY KEY, key_id uuid NOT NULL REFERENCES owner_api_keys(id),
      expires_at timestamptz NOT NULL);
    CREATE TABLE instrument_provider_mappings (
      asset_id uuid NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
      provider text NOT NULL, provider_id text NOT NULL,
      metadata jsonb NOT NULL, verified_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(provider, provider_id), UNIQUE(asset_id, provider));
    CREATE TABLE market_observations (
      id uuid PRIMARY KEY, asset_id uuid NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
      price numeric NOT NULL CHECK(price>0), currency text NOT NULL,
      as_of timestamptz NOT NULL, provider text NOT NULL,
      quality text NOT NULL CHECK(quality IN ('OBSERVED','DELAYED')),
      received_at timestamptz NOT NULL DEFAULT now());
    CREATE INDEX ix_market_observations_asset_time ON market_observations(asset_id,as_of DESC);
    CREATE TABLE investment_configurations (
      id uuid PRIMARY KEY, household_id uuid NOT NULL REFERENCES household_profiles(id),
      policy_version_id uuid NOT NULL REFERENCES investment_policy_versions(id),
      settings jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE contribution_candidates (
      id uuid PRIMARY KEY, household_id uuid NOT NULL REFERENCES household_profiles(id),
      configuration_id uuid NOT NULL REFERENCES investment_configurations(id),
      evidence jsonb NOT NULL, content_hash text NOT NULL,
      expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE contribution_decisions (
      candidate_id uuid PRIMARY KEY REFERENCES contribution_candidates(id),
      decision_id uuid UNIQUE NOT NULL REFERENCES decisions(id) ON DELETE RESTRICT,
      committee_session_id uuid UNIQUE NOT NULL REFERENCES committee_sessions(id));
    CREATE TABLE decision_research_sources (
      decision_id uuid PRIMARY KEY REFERENCES decisions(id) ON DELETE RESTRICT,
      run_id uuid NOT NULL REFERENCES research_runs(id) ON DELETE RESTRICT);
    CREATE FUNCTION fn_launch_immutable() RETURNS trigger AS $$
    BEGIN RAISE EXCEPTION 'Launch evidence is append-only' USING ERRCODE='55000'; END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER immutable_config BEFORE UPDATE OR DELETE ON investment_configurations
      FOR EACH ROW EXECUTE FUNCTION fn_launch_immutable();
    CREATE TRIGGER immutable_candidate BEFORE UPDATE OR DELETE ON contribution_candidates
      FOR EACH ROW EXECUTE FUNCTION fn_launch_immutable();
    CREATE TRIGGER immutable_decision_link BEFORE UPDATE OR DELETE ON contribution_decisions
      FOR EACH ROW EXECUTE FUNCTION fn_launch_immutable();
    CREATE TRIGGER immutable_research_link BEFORE UPDATE OR DELETE ON decision_research_sources
      FOR EACH ROW EXECUTE FUNCTION fn_launch_immutable();
    CREATE TRIGGER immutable_observation BEFORE UPDATE OR DELETE ON market_observations
      FOR EACH ROW EXECUTE FUNCTION fn_launch_immutable();
    CREATE FUNCTION fn_capture_research_source() RETURNS trigger AS $$
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
    CREATE TRIGGER capture_research_source BEFORE INSERT OR UPDATE ON decision_drafts
      FOR EACH ROW EXECUTE FUNCTION fn_capture_research_source();
    INSERT INTO decision_research_sources
      SELECT d.decision_id,r.id FROM decision_drafts d JOIN research_runs r
      ON r.id::text=lower(substring(d.evidence_or_sources FROM 'research_run_id=(__UUID__)'))
      ON CONFLICT DO NOTHING;
    """.replace("__UUID__", UUID_PATTERN)
    )


def downgrade():
    # Reversible only before any V1 state exists. Never erase populated financial evidence.
    from sqlalchemy import text

    tables = [
        "contribution_decisions",
        "decision_research_sources",
        "contribution_candidates",
        "investment_configurations",
        "market_observations",
        "instrument_provider_mappings",
        "owner_web_sessions",
    ]
    connection = op.get_bind()
    for table in tables:
        if connection.execute(text("SELECT EXISTS(SELECT 1 FROM " + table + ")")).scalar():
            raise RuntimeError(
                "Preserve populated V1 evidence; use application rollback or roll forward"
            )
    op.execute("DROP TRIGGER capture_research_source ON decision_drafts")
    op.execute("DROP FUNCTION fn_capture_research_source()")
    for table in tables:
        op.drop_table(table)
    op.execute("DROP FUNCTION fn_launch_immutable()")
