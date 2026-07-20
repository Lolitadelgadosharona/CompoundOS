"""Sprint 006 Slice A — AI Committee Foundation persistence.

Revision ID: 0012_ai_committee_foundation
Revises: 0011_fencing_closure
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_ai_committee_foundation"
down_revision: Union[str, None] = "0011_fencing_closure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Immutable report trigger
# ---------------------------------------------------------------------------

REPORT_IMMUTABILITY_TRIGGER = r"""
CREATE OR REPLACE FUNCTION public.fn_committee_report_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'committee_report_immutable',
            DETAIL = 'Committee reports cannot be modified after creation.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()


# ---------------------------------------------------------------------------
# Append-only outcome trigger
# ---------------------------------------------------------------------------

OUTCOME_APPEND_ONLY_TRIGGER = r"""
CREATE OR REPLACE FUNCTION public.fn_committee_outcome_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'committee_outcome_append_only',
            DETAIL = 'Committee outcomes are append-only and cannot be modified.';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'committee_outcome_append_only',
            DETAIL = 'Committee outcomes are append-only and cannot be deleted.';
    END IF;
    RETURN NEW;
END;
$$
""".strip()


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # 1. committee_sessions
    op.create_table(
        "committee_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "household_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("household_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("proposal_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
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
    )
    op.create_index(
        "ix_committee_sessions_household",
        "committee_sessions",
        ["household_id"],
    )
    op.create_check_constraint(
        "ck_committee_sessions_status",
        "committee_sessions",
        "status IN ('draft', 'queued', 'running', 'completed', 'failed')",
    )
    op.create_check_constraint(
        "ck_committee_sessions_title_not_empty",
        "committee_sessions",
        "char_length(title) > 0",
    )
    op.create_check_constraint(
        "ck_committee_sessions_proposal_not_empty",
        "committee_sessions",
        "char_length(proposal_text) > 0",
    )

    # 2. committee_evidence_items
    op.create_table(
        "committee_evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("structured_facts", postgresql.JSONB, nullable=False),
        sa.Column(
            "provenance",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("freshness", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("citation_ref", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_committee_evidence_items_session",
        "committee_evidence_items",
        ["session_id"],
    )
    op.create_check_constraint(
        "ck_evidence_items_source_type",
        "committee_evidence_items",
        "source_type IN ("
        " 'portfolio_snapshot',"
        " 'policy_version',"
        " 'guardian_event',"
        " 'decision',"
        " 'owner_claim',"
        " 'external'"
        ")",
    )
    op.create_check_constraint(
        "ck_evidence_items_provenance",
        "committee_evidence_items",
        "provenance IN ('compoundos_internal', 'owner_provided')",
    )
    op.create_check_constraint(
        "ck_evidence_items_confidence",
        "committee_evidence_items",
        "confidence IN ('high', 'medium')",
    )
    op.create_check_constraint(
        "ck_evidence_items_freshness_not_empty",
        "committee_evidence_items",
        "char_length(freshness) > 0",
    )

    # 3. committee_reports (immutable)
    op.create_table(
        "committee_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column(
            "temperature",
            sa.Numeric(3, 2),
            nullable=False,
        ),
        sa.Column("provider_params", postgresql.JSONB, nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=True),
        sa.Column(
            "report_content",
            postgresql.JSONB,
            nullable=False,
        ),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_committee_reports_session",
        "committee_reports",
        ["session_id"],
    )
    op.create_check_constraint(
        "ck_committee_reports_provider_not_empty",
        "committee_reports",
        "char_length(provider) > 0",
    )
    op.create_check_constraint(
        "ck_committee_reports_model_id_not_empty",
        "committee_reports",
        "char_length(model_id) > 0",
    )
    op.create_check_constraint(
        "ck_committee_reports_temperature_range",
        "committee_reports",
        "temperature >= 0 AND temperature <= 2.0",
    )
    op.create_check_constraint(
        "ck_committee_reports_content_hash_not_empty",
        "committee_reports",
        "char_length(content_hash) > 0",
    )

    # Immutability trigger on reports
    op.execute(REPORT_IMMUTABILITY_TRIGGER)
    op.execute(sa.text(
        "CREATE TRIGGER trg_committee_report_immutability"
        " BEFORE UPDATE ON committee_reports"
        " FOR EACH ROW EXECUTE FUNCTION"
        " fn_committee_report_immutability()"
    ))

    # 4. committee_outcomes (append-only)
    op.create_table(
        "committee_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_reports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("owner_rationale", sa.Text(), nullable=True),
        sa.Column(
            "decision_draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("decision_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_committee_outcomes_session",
        "committee_outcomes",
        ["session_id"],
    )
    op.create_check_constraint(
        "ck_committee_outcomes_outcome",
        "committee_outcomes",
        "outcome IN ('accepted', 'rejected', 'deferred')",
    )

    # Append-only trigger on outcomes
    op.execute(OUTCOME_APPEND_ONLY_TRIGGER)
    op.execute(sa.text(
        "CREATE TRIGGER trg_committee_outcome_append_only"
        " BEFORE UPDATE OR DELETE ON committee_outcomes"
        " FOR EACH ROW EXECUTE FUNCTION"
        " fn_committee_outcome_append_only()"
    ))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_committee_outcome_append_only ON committee_outcomes")
    op.execute("DROP FUNCTION IF EXISTS fn_committee_outcome_append_only")
    op.drop_table("committee_outcomes")

    op.execute("DROP TRIGGER IF EXISTS trg_committee_report_immutability ON committee_reports")
    op.execute("DROP FUNCTION IF EXISTS fn_committee_report_immutability")
    op.drop_table("committee_reports")

    op.drop_table("committee_evidence_items")
    op.drop_table("committee_sessions")
