"""Sprint 011 Slice B — Hardening: data quality + memory classification.

Revision ID: 0028_evidence_hardening
Revises: 0027_evidence_knowledge
Create Date: 2026-08-10

Adds:
  - market_data_cache.data_quality_status (CHECK: VALID/STALE/FAILED/SUSPECT)
  - investment_knowledge_memory.memory_type (CHECK: classification)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0028_evidence_hardening"
down_revision: Union[str, None] = "0027_evidence_knowledge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "market_data_cache",
        sa.Column(
            "data_quality_status", sa.Text(), nullable=False,
            server_default="VALID",
        ),
    )
    op.create_check_constraint(
        "ck_market_data_cache_quality",
        "market_data_cache",
        sa.text("data_quality_status IN ('VALID','STALE','FAILED','SUSPECT')"),
    )

    op.add_column(
        "investment_knowledge_memory",
        sa.Column(
            "memory_type", sa.Text(), nullable=False,
            server_default="company_profile",
        ),
    )
    op.create_check_constraint(
        "ck_knowledge_memory_type",
        "investment_knowledge_memory",
        sa.text(
            "memory_type IN ('company_profile','historical_thesis',"
            "'risk_note','decision_lesson','sector_analysis','macro_note')"
        ),
    )


def downgrade() -> None:
    op.drop_column("investment_knowledge_memory", "memory_type")
    op.drop_column("market_data_cache", "data_quality_status")
