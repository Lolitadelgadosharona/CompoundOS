"""Sprint 011 Slice B — Evidence Collection + Knowledge Memory.

Revision ID: 0027_evidence_knowledge
Revises: 0026_research_foundation
Create Date: 2026-08-10

Creates:
  - market_data_cache           External market data cache (NOT source of truth)
  - investment_knowledge_memory  Entity profiles, thesis, evidence, decisions, outcomes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_evidence_knowledge"
down_revision: Union[str, None] = "0026_research_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── market_data_cache ──
    op.create_table(
        "market_data_cache",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("data", sa.dialects.postgresql.JSONB(),
                  nullable=False),
        sa.Column("source", sa.Text(), nullable=False,
                  server_default="alpha_vantage"),
        sa.Column("source_timestamp", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "uq_market_data_cache_symbol_type",
        "market_data_cache",
        ["symbol", "data_type"],
    )

    op.create_check_constraint(
        "ck_market_data_cache_type",
        "market_data_cache",
        sa.text(
            "data_type IN ('overview','income_statement','balance_sheet',"
            "'cash_flow','sector_performance','price_history','news',"
            "'fundamentals')"
        ),
    )

    # ── investment_knowledge_memory ──
    op.create_table(
        "investment_knowledge_memory",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_key", sa.Text(), nullable=False),
        sa.Column("profile", sa.dialects.postgresql.JSONB(),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("past_thesis", sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column("past_evidence", sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column("past_decisions", sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column("past_outcomes", sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column("prediction_accuracy", sa.dialects.postgresql.JSONB(),
                  nullable=True),
        sa.Column("source", sa.Text(), nullable=False,
                  server_default="market_data"),
        sa.Column("version", sa.Integer(), nullable=False,
                  server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )

    op.create_unique_constraint(
        "uq_knowledge_memory_entity",
        "investment_knowledge_memory",
        ["entity_type", "entity_key"],
    )

    op.create_check_constraint(
        "ck_knowledge_memory_entity_type",
        "investment_knowledge_memory",
        sa.text(
            "entity_type IN ('company','sector','macro_indicator','etf','fund')"
        ),
    )


def downgrade() -> None:
    op.drop_table("investment_knowledge_memory")
    op.drop_table("market_data_cache")
