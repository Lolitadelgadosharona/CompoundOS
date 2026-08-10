"""Sprint 011 Slice D — Investment Memo + Confidence Engine.

Revision ID: 0030_investment_memo
Revises: 0029_perspective_analyses
Create Date: 2026-08-10

Creates:
  - investment_memos      Structured investment research memo.
                          Synthesizes perspective_analyses into formal memo.
                          Immutable after completion.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0030_investment_memo"
down_revision: Union[str, None] = "0029_perspective_analyses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investment_memos",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("run_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_runs.id",
                                name="fk_investment_memos_run_id",
                                ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("synthesis_model", sa.Text(), nullable=True),
        sa.Column("memo", sa.dialects.postgresql.JSONB(),
                  nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("confidence_level", sa.Text(), nullable=True),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_check_constraint(
        "ck_investment_memos_confidence",
        "investment_memos",
        sa.text(
            "confidence_level IS NULL OR"
            " confidence_level IN ('HIGH','MEDIUM','LOW')"
        ),
    )

    op.create_check_constraint(
        "ck_investment_memos_score",
        "investment_memos",
        sa.text(
            "confidence_score IS NULL OR"
            " confidence_score BETWEEN 0 AND 100"
        ),
    )

    op.create_check_constraint(
        "ck_investment_memos_recommendation",
        "investment_memos",
        sa.text(
            "recommendation IS NULL OR"
            " recommendation IN ('BUY','HOLD','PASS')"
        ),
    )

    # Completed memos are immutable
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_investment_memo_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP IN ('UPDATE','DELETE')
               AND OLD.generated_at IS NOT NULL THEN
                RAISE EXCEPTION 'Completed investment memos are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_investment_memos_immutability
        BEFORE UPDATE OR DELETE ON investment_memos
        FOR EACH ROW EXECUTE FUNCTION fn_investment_memo_immutability();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_investment_memos_immutability"
               " ON investment_memos")
    op.execute("DROP FUNCTION IF EXISTS fn_investment_memo_immutability()")
    op.drop_table("investment_memos")
