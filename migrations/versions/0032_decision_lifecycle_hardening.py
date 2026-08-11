"""0032_decision_lifecycle_hardening

Align CHECK constraints with Sprint 013 Slice D owner decision semantics.

- ck_decisions_status_values: add 'proposed' status
- ck_evidence_items_confidence: add 'low' confidence level
- ck_evidence_items_provenance: add 'ai_generated' provenance

All changes are additive and reversible.
No destructive data migration.
No data changes to existing records.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-10
"""
from alembic import op

revision = "0032_decision_lifecycle_hardening"
down_revision = "0031_llm_runtime"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Drop and recreate ck_decisions_status_values: add 'proposed'
    op.execute(
        "ALTER TABLE decisions DROP CONSTRAINT IF EXISTS"
        " ck_decisions_status_values"
    )
    op.create_check_constraint(
        "ck_decisions_status_values",
        "decisions",
        "status IN ('draft', 'proposed', 'confirmed', 'archived')",
    )

    # 2. Drop and recreate ck_evidence_items_confidence: add 'low'
    op.execute(
        "ALTER TABLE committee_evidence_items DROP CONSTRAINT IF EXISTS"
        " ck_evidence_items_confidence"
    )
    op.create_check_constraint(
        "ck_evidence_items_confidence",
        "committee_evidence_items",
        "confidence IN ('high', 'medium', 'low')",
    )

    # 3. Drop and recreate ck_evidence_items_source_type: add 'research_memo'
    op.execute(
        "ALTER TABLE committee_evidence_items DROP CONSTRAINT IF EXISTS"
        " ck_evidence_items_source_type"
    )
    op.execute(
        "ALTER TABLE committee_evidence_items ADD CONSTRAINT"
        " ck_evidence_items_source_type CHECK (source_type IN"
        " ('portfolio_snapshot', 'policy_version'," 
        " 'guardian_event', 'decision', 'owner_claim', 'external',"
        " 'portfolio_position', 'policy_bucket', 'investment_idea',"
        " 'research_memo'))"
    )

    # 4. Drop and recreate ck_evidence_items_provenance: add 'ai_generated'
    op.execute(
        "ALTER TABLE committee_evidence_items DROP CONSTRAINT IF EXISTS"
        " ck_evidence_items_provenance"
    )
    op.create_check_constraint(
        "ck_evidence_items_provenance",
        "committee_evidence_items",
        "provenance IN ('compoundos_internal', 'owner_provided', 'ai_generated')",
    )


def downgrade():
    # Restore original source_type constraint
    op.execute(
        "ALTER TABLE committee_evidence_items DROP CONSTRAINT IF EXISTS"
        " ck_evidence_items_source_type"
    )
    op.execute(
        "ALTER TABLE committee_evidence_items ADD CONSTRAINT"
        " ck_evidence_items_source_type CHECK (source_type IN"
        " ('portfolio_snapshot', 'policy_version'," 
        " 'guardian_event', 'decision', 'owner_claim', 'external',"
        " 'portfolio_position', 'policy_bucket', 'investment_idea'))"
    )

    # Restore original constraints (remove added values)
    op.execute(
        "ALTER TABLE decisions DROP CONSTRAINT IF EXISTS"
        " ck_decisions_status_values"
    )
    op.create_check_constraint(
        "ck_decisions_status_values",
        "decisions",
        "status IN ('draft', 'confirmed', 'archived')",
    )

    op.execute(
        "ALTER TABLE committee_evidence_items DROP CONSTRAINT IF EXISTS"
        " ck_evidence_items_confidence"
    )
    op.create_check_constraint(
        "ck_evidence_items_confidence",
        "committee_evidence_items",
        "confidence IN ('high', 'medium')",
    )

    op.execute(
        "ALTER TABLE committee_evidence_items DROP CONSTRAINT IF EXISTS"
        " ck_evidence_items_provenance"
    )
    op.create_check_constraint(
        "ck_evidence_items_provenance",
        "committee_evidence_items",
        "provenance IN ('compoundos_internal', 'owner_provided')",
    )
