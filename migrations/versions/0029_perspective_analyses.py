"""Sprint 011 Slice C — Multi-Perspective Reasoning Engine.

Revision ID: 0029_perspective_analyses
Revises: 0028_evidence_hardening
Create Date: 2026-08-10

Creates:
  - perspective_analyses      Structured analysis from each reasoning perspective.
                              Immutable after completion. 6 perspectives: Value,
                              Growth, Risk, Macro, Policy, Portfolio Fit.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_perspective_analyses"
down_revision: Union[str, None] = "0028_evidence_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "perspective_analyses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("run_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_runs.id",
                                name="fk_perspective_analyses_run_id",
                                ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("perspective", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=False,
                  server_default="1"),
        sa.Column("analysis", sa.dialects.postgresql.JSONB(),
                  nullable=False),
        sa.Column("conviction_score", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_check_constraint(
        "ck_perspective_analyses_perspective",
        "perspective_analyses",
        sa.text(
            "perspective IN ('value','growth','risk','macro','policy',"
            "'portfolio_fit')"
        ),
    )

    op.create_check_constraint(
        "ck_perspective_analyses_conviction",
        "perspective_analyses",
        sa.text(
            "conviction_score IS NULL OR"
            " conviction_score BETWEEN 1 AND 10"
        ),
    )

    # Completed analyses are immutable
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_perspective_analysis_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE') AND OLD.completed_at IS NOT NULL THEN
                RAISE EXCEPTION 'Completed perspective analyses are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_perspective_analyses_immutability
        BEFORE UPDATE OR DELETE ON perspective_analyses
        FOR EACH ROW EXECUTE FUNCTION fn_perspective_analysis_immutability();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_perspective_analyses_immutability"
               " ON perspective_analyses")
    op.execute("DROP FUNCTION IF EXISTS fn_perspective_analysis_immutability()")
    op.drop_table("perspective_analyses")
