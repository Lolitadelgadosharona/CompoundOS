"""Sprint 011 Slice A — Research Foundation.

Revision ID: 0026_research_foundation
Revises: 0025_auth_and_audit
Create Date: 2026-08-10

Creates:
  - research_requests           Owner-created research objectives
  - research_runs               Individual research executions (1+ per request)

Additive only. Fully reversible.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "0026_research_foundation"
down_revision: Union[str, None] = "0025_auth_and_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_requests",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("review_request_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("committee_review_requests.id",
                                name="fk_research_requests_review_request_id",
                                ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("investment_idea_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("investment_ideas.id",
                                name="fk_research_requests_idea_id",
                                ondelete="SET NULL"),
                  nullable=True),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default="pending"),
        sa.Column("parameters", sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    # Only ONE active request per review_request
    op.create_unique_constraint(
        "uq_research_requests_active",
        "research_requests",
        ["review_request_id"],
    )

    op.create_check_constraint(
        "ck_research_requests_status",
        "research_requests",
        sa.text("status IN ('pending','running','completed','failed')"),
    )

    op.create_table(
        "research_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("request_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_requests.id",
                                name="fk_research_runs_request_id",
                                ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "uq_research_runs_number",
        "research_runs",
        ["request_id", "run_number"],
    )

    op.create_check_constraint(
        "ck_research_runs_status",
        "research_runs",
        sa.text(
            "status IN ('pending','collecting_evidence','analyzing',"
            "'generating_memo','completed','failed')"
        ),
    )

    # Prevent completed runs from being modified
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_research_run_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD.status = 'completed' THEN
                RAISE EXCEPTION 'Completed research runs are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.status = 'completed' THEN
                RAISE EXCEPTION 'Completed research runs are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_research_runs_immutability
        BEFORE UPDATE OR DELETE ON research_runs
        FOR EACH ROW EXECUTE FUNCTION fn_research_run_immutability();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_research_runs_immutability"
               " ON research_runs")
    op.execute("DROP FUNCTION IF EXISTS fn_research_run_immutability()")

    op.drop_table("research_runs")
    op.drop_table("research_requests")
