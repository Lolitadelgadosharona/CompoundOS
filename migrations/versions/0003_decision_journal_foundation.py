"""Add Decision Journal persistence and immutability foundation.

Revision ID: 0003_decision_journal_foundation
Revises: 0002_investment_policy_foundation
Create Date: 2026-07-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_decision_journal_foundation"
down_revision: Union[str, None] = "0002_investment_policy_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DECISION_TEXT_LIMITS: dict[str, int] = {
    "title": 500,
    "decision_summary": 8_000,
    "rationale": 8_000,
    "alternatives_considered": 8_000,
    "risks_and_uncertainties": 8_000,
    "evidence_or_sources": 8_000,
    "expected_outcome": 4_000,
    "review_trigger": 4_000,
    "notes": 8_000,
}

CONFIRM_REQUIRED_FIELDS = ("title", "decision_summary", "rationale")

# --- PL/pgSQL trigger functions ---

DECISION_IDENTITY_LIFECYCLE_FUNCTION = r"""
CREATE FUNCTION public.fn_decision_identity_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_identity_created_at_immutable';
    END IF;

    IF OLD.status IS DISTINCT FROM NEW.status THEN
        IF OLD.status = 'draft' AND NEW.status = 'confirmed' THEN
            NULL;
        ELSIF OLD.status = 'confirmed' AND NEW.status = 'archived' THEN
            NULL;
        ELSIF OLD.status = 'archived' AND NEW.status = 'confirmed' THEN
            NULL;
        ELSE
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'decision_identity_invalid_status_transition',
                DETAIL = format(
                    'Transition from %L to %L is not permitted.',
                    OLD.status, NEW.status
                );
        END IF;
    END IF;

    IF NEW.archived_at IS DISTINCT FROM OLD.archived_at
       OR NEW.archive_reason IS DISTINCT FROM OLD.archive_reason THEN
        IF OLD.status = 'confirmed' AND NEW.status = 'archived' THEN
            IF NEW.archived_at IS NULL THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'decision_archive_requires_archived_at';
            END IF;
        ELSIF OLD.status = 'archived' AND NEW.status = 'confirmed' THEN
            IF NEW.archived_at IS NOT NULL OR NEW.archive_reason IS NOT NULL THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'decision_unarchive_must_clear_archive_fields';
            END IF;
        ELSE
            IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    MESSAGE = 'decision_archive_fields_only_during_transition';
            END IF;
        END IF;
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_identity_id_immutable';
    END IF;
    IF NEW.household_id IS DISTINCT FROM OLD.household_id THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_identity_household_immutable';
    END IF;

    RETURN NEW;
END;
$$
"""

DECISION_IDENTITY_DELETE_GUARD_FUNCTION = r"""
CREATE FUNCTION public.fn_decision_identity_delete_guard()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status <> 'draft' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_identity_delete_forbidden',
            DETAIL = format(
                'Only draft decisions may be deleted. Current status: %L.',
                OLD.status
            );
    END IF;

    PERFORM 1
    FROM public.decision_confirmed_snapshots
    WHERE decision_id = OLD.id
    LIMIT 1;

    IF FOUND THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_identity_delete_has_snapshot';
    END IF;

    RETURN OLD;
END;
$$
"""

DECISION_CONFIRMED_SNAPSHOT_IMMUTABILITY_FUNCTION = r"""
CREATE FUNCTION public.fn_decision_confirmed_snapshot_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_snapshot_delete_forbidden';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_snapshot_update_forbidden';
    END IF;

    IF NEW.decision_id IS NULL
       OR NEW.selected_policy_version_id IS NULL
       OR NEW.title IS NULL
       OR NEW.decision_summary IS NULL
       OR NEW.rationale IS NULL
       OR NEW.decision_date IS NULL
       OR NEW.confirmed_at IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'decision_snapshot_insert_invalid';
    END IF;

    RETURN NEW;
END;
$$
"""

DECISION_CORRECTION_IMMUTABILITY_FUNCTION = r"""
CREATE FUNCTION public.fn_decision_correction_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_snapshot_decision_id uuid;
    v_decision_status text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_correction_update_forbidden';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION USING
            ERRCODE = '55000',
            MESSAGE = 'decision_correction_delete_forbidden';
    END IF;

    IF NEW.actor <> 'local-owner' THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'decision_correction_invalid_actor';
    END IF;

    IF NEW.correction_number <= 0 THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'decision_correction_invalid_number';
    END IF;

    SELECT s.decision_id
    INTO v_snapshot_decision_id
    FROM public.decision_confirmed_snapshots s
    WHERE s.id = NEW.corrected_entry_id;

    IF v_snapshot_decision_id IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '23502',
            MESSAGE = 'decision_correction_snapshot_not_found';
    END IF;

    IF v_snapshot_decision_id <> NEW.decision_id THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'decision_correction_ownership_mismatch';
    END IF;

    SELECT status
    INTO v_decision_status
    FROM public.decisions
    WHERE id = NEW.decision_id;

    IF v_decision_status IS NULL THEN
        RAISE EXCEPTION USING
            ERRCODE = '23503',
            MESSAGE = 'decision_correction_decision_not_found';
    END IF;

    IF v_decision_status NOT IN ('confirmed', 'archived') THEN
        RAISE EXCEPTION USING
            ERRCODE = '23514',
            MESSAGE = 'decision_correction_draft_not_allowed',
            DETAIL = format(
                'Corrections require status confirmed or archived. Current: %L.',
                v_decision_status
            );
    END IF;

    RETURN NEW;
END;
$$
"""

DECISION_LIFECYCLE_CONSISTENCY_FUNCTION = r"""
CREATE FUNCTION public.fn_decision_lifecycle_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_has_snapshot boolean;
    v_has_draft boolean;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM public.decision_confirmed_snapshots
        WHERE decision_id = NEW.id
    ) INTO v_has_snapshot;

    SELECT EXISTS(
        SELECT 1 FROM public.decision_drafts
        WHERE decision_id = NEW.id
    ) INTO v_has_draft;

    IF NEW.status IN ('confirmed', 'archived') THEN
        IF NOT v_has_snapshot THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'decision_confirmed_requires_snapshot',
                DETAIL = format(
                    'Decision %s has status %L but no confirmed snapshot.',
                    NEW.id, NEW.status
                );
        END IF;
        IF v_has_draft THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'decision_confirmed_has_draft',
                DETAIL = format(
                    'Decision %s has status %L but still has a draft.',
                    NEW.id, NEW.status
                );
        END IF;
    ELSIF NEW.status = 'draft' THEN
        IF v_has_snapshot THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'decision_draft_has_snapshot',
                DETAIL = format(
                    'Decision %s has status draft but has a confirmed snapshot.',
                    NEW.id
                );
        END IF;
        IF NOT v_has_draft THEN
            RAISE EXCEPTION USING
                ERRCODE = '23514',
                MESSAGE = 'decision_draft_requires_draft_row',
                DETAIL = format(
                    'Decision %s has status draft but no draft row.',
                    NEW.id
                );
        END IF;
    END IF;

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    # 1. decisions (stable identity)
    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'archived')",
            name="ck_decisions_status_values",
        ),
        sa.CheckConstraint(
            "archive_reason IS NULL OR char_length(archive_reason) <= 4000",
            name="ck_decisions_archive_reason_length",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household_profiles.id"],
            name="fk_decisions_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. decision_drafts
    op.create_table(
        "decision_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("alternatives_considered", sa.Text(), nullable=True),
        sa.Column("risks_and_uncertainties", sa.Text(), nullable=True),
        sa.Column("evidence_or_sources", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("review_trigger", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) <= 500",
            name="ck_decision_drafts_title_length",
        ),
        sa.CheckConstraint(
            "char_length(decision_summary) <= 8000",
            name="ck_decision_drafts_decision_summary_length",
        ),
        sa.CheckConstraint(
            "char_length(rationale) <= 8000",
            name="ck_decision_drafts_rationale_length",
        ),
        sa.CheckConstraint(
            "char_length(alternatives_considered) <= 8000",
            name="ck_decision_drafts_alternatives_considered_length",
        ),
        sa.CheckConstraint(
            "char_length(risks_and_uncertainties) <= 8000",
            name="ck_decision_drafts_risks_and_uncertainties_length",
        ),
        sa.CheckConstraint(
            "char_length(evidence_or_sources) <= 8000",
            name="ck_decision_drafts_evidence_or_sources_length",
        ),
        sa.CheckConstraint(
            "char_length(expected_outcome) <= 4000",
            name="ck_decision_drafts_expected_outcome_length",
        ),
        sa.CheckConstraint(
            "char_length(review_trigger) <= 4000",
            name="ck_decision_drafts_review_trigger_length",
        ),
        sa.CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_decision_drafts_notes_length",
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_decision_drafts_revision_positive",
        ),
        sa.UniqueConstraint(
            "decision_id",
            name="uq_decision_drafts_decision_id",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_decision_drafts_decision_id_decisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. decision_confirmed_snapshots
    op.create_table(
        "decision_confirmed_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("selected_policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("alternatives_considered", sa.Text(), nullable=True),
        sa.Column("risks_and_uncertainties", sa.Text(), nullable=True),
        sa.Column("evidence_or_sources", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("review_trigger", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) <= 500",
            name="ck_decision_snapshots_title_length",
        ),
        sa.CheckConstraint(
            "char_length(decision_summary) <= 8000",
            name="ck_decision_snapshots_decision_summary_length",
        ),
        sa.CheckConstraint(
            "char_length(rationale) <= 8000",
            name="ck_decision_snapshots_rationale_length",
        ),
        sa.CheckConstraint(
            "char_length(alternatives_considered) <= 8000",
            name="ck_decision_snapshots_alternatives_considered_length",
        ),
        sa.CheckConstraint(
            "char_length(risks_and_uncertainties) <= 8000",
            name="ck_decision_snapshots_risks_and_uncertainties_length",
        ),
        sa.CheckConstraint(
            "char_length(evidence_or_sources) <= 8000",
            name="ck_decision_snapshots_evidence_or_sources_length",
        ),
        sa.CheckConstraint(
            "char_length(expected_outcome) <= 4000",
            name="ck_decision_snapshots_expected_outcome_length",
        ),
        sa.CheckConstraint(
            "char_length(review_trigger) <= 4000",
            name="ck_decision_snapshots_review_trigger_length",
        ),
        sa.CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_decision_snapshots_notes_length",
        ),
        sa.CheckConstraint(
            "decision_date <= CURRENT_DATE",
            name="ck_decision_snapshots_decision_date_not_future",
        ),
        sa.UniqueConstraint(
            "decision_id",
            name="uq_decision_snapshots_decision_id",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_decision_snapshots_decision_id_decisions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_policy_version_id"],
            ["investment_policy_versions.id"],
            name="fk_decision_snapshots_policy_version_id_policy_versions",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 4. decision_corrections
    op.create_table(
        "decision_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("corrected_entry_id", sa.Uuid(), nullable=False),
        sa.Column("correction_number", sa.Integer(), nullable=False),
        sa.Column("correction_reason", sa.Text(), nullable=False),
        sa.Column(
            "actor",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'local-owner'"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("decision_summary", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("alternatives_considered", sa.Text(), nullable=True),
        sa.Column("risks_and_uncertainties", sa.Text(), nullable=True),
        sa.Column("evidence_or_sources", sa.Text(), nullable=True),
        sa.Column("expected_outcome", sa.Text(), nullable=True),
        sa.Column("review_trigger", sa.Text(), nullable=True),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("decision_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) <= 500",
            name="ck_decision_corrections_title_length",
        ),
        sa.CheckConstraint(
            "char_length(decision_summary) <= 8000",
            name="ck_decision_corrections_decision_summary_length",
        ),
        sa.CheckConstraint(
            "char_length(rationale) <= 8000",
            name="ck_decision_corrections_rationale_length",
        ),
        sa.CheckConstraint(
            "char_length(alternatives_considered) <= 8000",
            name="ck_decision_corrections_alternatives_considered_length",
        ),
        sa.CheckConstraint(
            "char_length(risks_and_uncertainties) <= 8000",
            name="ck_decision_corrections_risks_and_uncertainties_length",
        ),
        sa.CheckConstraint(
            "char_length(evidence_or_sources) <= 8000",
            name="ck_decision_corrections_evidence_or_sources_length",
        ),
        sa.CheckConstraint(
            "char_length(expected_outcome) <= 4000",
            name="ck_decision_corrections_expected_outcome_length",
        ),
        sa.CheckConstraint(
            "char_length(review_trigger) <= 4000",
            name="ck_decision_corrections_review_trigger_length",
        ),
        sa.CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_decision_corrections_notes_length",
        ),
        sa.CheckConstraint(
            "char_length(correction_reason) BETWEEN 1 AND 8000",
            name="ck_decision_corrections_correction_reason_length",
        ),
        sa.CheckConstraint(
            "decision_date <= CURRENT_DATE",
            name="ck_decision_corrections_decision_date_not_future",
        ),
        sa.CheckConstraint(
            "correction_number >= 1",
            name="ck_decision_corrections_correction_number_positive",
        ),
        sa.CheckConstraint(
            "actor = 'local-owner'",
            name="ck_decision_corrections_actor_local_owner",
        ),
        sa.UniqueConstraint(
            "decision_id",
            "correction_number",
            name="uq_decision_corrections_decision_correction_number",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name="fk_decision_corrections_decision_id_decisions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corrected_entry_id"],
            ["decision_confirmed_snapshots.id"],
            name="fk_decision_corrections_corrected_entry_id_snapshots",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. Create PL/pgSQL trigger functions
    op.execute(DECISION_IDENTITY_LIFECYCLE_FUNCTION)
    op.execute(DECISION_IDENTITY_DELETE_GUARD_FUNCTION)
    op.execute(DECISION_CONFIRMED_SNAPSHOT_IMMUTABILITY_FUNCTION)
    op.execute(DECISION_CORRECTION_IMMUTABILITY_FUNCTION)
    op.execute(DECISION_LIFECYCLE_CONSISTENCY_FUNCTION)

    # 6. Create triggers
    op.execute(
        """
        CREATE TRIGGER trg_decision_identity_lifecycle
        BEFORE UPDATE ON public.decisions
        FOR EACH ROW EXECUTE FUNCTION public.fn_decision_identity_lifecycle()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_identity_delete_guard
        BEFORE DELETE ON public.decisions
        FOR EACH ROW EXECUTE FUNCTION public.fn_decision_identity_delete_guard()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_confirmed_snapshot_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.decision_confirmed_snapshots
        FOR EACH ROW EXECUTE FUNCTION public.fn_decision_confirmed_snapshot_immutability()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_decision_correction_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.decision_corrections
        FOR EACH ROW EXECUTE FUNCTION public.fn_decision_correction_immutability()
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_decision_lifecycle_consistency
        AFTER INSERT ON public.decisions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION public.fn_decision_lifecycle_consistency()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_lifecycle_consistency "
        "ON public.decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_correction_immutability "
        "ON public.decision_corrections"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_confirmed_snapshot_immutability "
        "ON public.decision_confirmed_snapshots"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_identity_delete_guard "
        "ON public.decisions"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_decision_identity_lifecycle "
        "ON public.decisions"
    )

    op.execute("DROP FUNCTION IF EXISTS public.fn_decision_lifecycle_consistency()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_decision_correction_immutability()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_decision_confirmed_snapshot_immutability()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_decision_identity_delete_guard()")
    op.execute("DROP FUNCTION IF EXISTS public.fn_decision_identity_lifecycle()")

    op.drop_table("decision_corrections")
    op.drop_table("decision_confirmed_snapshots")
    op.drop_table("decision_drafts")
    op.drop_table("decisions")
