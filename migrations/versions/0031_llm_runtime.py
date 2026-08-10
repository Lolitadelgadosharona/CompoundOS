"""Sprint 012 Slice A — LLM Runtime Foundation.

Revision ID: 0031_llm_runtime
Revises: 0030_investment_memo
Create Date: 2026-08-10

Creates:
  - prompt_templates       Versioned AI prompt lifecycle (draft/active/deprecated)
  - llm_execution_log      Per-call execution audit (tokens, cost, retries)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_llm_runtime"
down_revision: Union[str, None] = "0030_investment_memo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── prompt_templates ──
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("perspective", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False,
                  server_default="1"),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default="draft"),
        sa.Column("purpose", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("default_model", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("user_prompt_template", sa.Text(), nullable=False,
                  server_default=""),
        sa.Column("active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "uq_prompt_templates_version",
        "prompt_templates",
        ["perspective", "version"],
    )

    op.create_check_constraint(
        "ck_prompt_templates_status",
        "prompt_templates",
        sa.text("status IN ('draft','active','deprecated')"),
    )

    op.create_check_constraint(
        "ck_prompt_templates_perspective",
        "prompt_templates",
        sa.text(
            "perspective IN ('value','growth','risk','macro','policy',"
            "'portfolio_fit','synthesis')"
        ),
    )

    # Active prompts are immutable
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_prompt_template_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD.status = 'active' THEN
                RAISE EXCEPTION 'Active prompt templates cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'UPDATE' AND OLD.status = 'active'
               AND NEW.status != 'deprecated' THEN
                RAISE EXCEPTION 'Active prompt templates are immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_prompt_templates_immutability
        BEFORE UPDATE ON prompt_templates
        FOR EACH ROW EXECUTE FUNCTION fn_prompt_template_immutability();
    """)

    # ── llm_execution_log ──
    op.create_table(
        "llm_execution_log",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("run_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_runs.id",
                                name="fk_llm_log_run_id",
                                ondelete="SET NULL"),
                  nullable=True),
        sa.Column("prompt_template_id",
                  sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("prompt_templates.id",
                                name="fk_llm_log_prompt_id",
                                ondelete="SET NULL"),
                  nullable=True),
        sa.Column("perspective", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_estimate", sa.Numeric(10, 6), nullable=True),
        sa.Column("cost_currency", sa.Text(), nullable=True,
                  server_default="USD"),
        sa.Column("retry_count", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("status", sa.Text(), nullable=False,
                  server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_check_constraint(
        "ck_llm_log_status",
        "llm_execution_log",
        sa.text(
            "status IN ('pending','running','success','failure','timeout',"
            "'rate_limited')"
        ),
    )

    op.create_check_constraint(
        "ck_llm_log_retry",
        "llm_execution_log",
        sa.text("retry_count BETWEEN 0 AND 5"),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_prompt_templates_immutability"
               " ON prompt_templates")
    op.execute("DROP FUNCTION IF EXISTS fn_prompt_template_immutability()")
    op.drop_table("llm_execution_log")
    op.drop_table("prompt_templates")
