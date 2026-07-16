from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class HouseholdProfile(Base):
    __tablename__ = "household_profiles"
    __table_args__ = (
        CheckConstraint("singleton_key", name="ck_household_profiles_singleton_key"),
        CheckConstraint(
            "char_length(household_name) BETWEEN 1 AND 200",
            name="ck_household_profiles_name_length",
        ),
        CheckConstraint(
            "base_currency ~ '^[A-Z]{3}$'",
            name="ck_household_profiles_currency_format",
        ),
        CheckConstraint(
            "char_length(investment_horizon) <= 2000",
            name="ck_household_profiles_investment_horizon_length",
        ),
        CheckConstraint(
            "char_length(liquidity_needs) <= 4000",
            name="ck_household_profiles_liquidity_needs_length",
        ),
        CheckConstraint(
            "char_length(risk_statement) <= 4000",
            name="ck_household_profiles_risk_statement_length",
        ),
        CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_household_profiles_notes_length",
        ),
        UniqueConstraint("singleton_key", name="uq_household_profiles_singleton_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    singleton_key: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    household_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_currency: Mapped[str] = mapped_column(Text, nullable=False)
    investment_horizon: Mapped[str] = mapped_column(Text, nullable=False, default="")
    liquidity_needs: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risk_statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_household_order", "household_id", "sequence_number"),
        UniqueConstraint("sequence_number", name="uq_audit_events_sequence_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    sequence_number: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), nullable=False
    )


POLICY_TEXT_COLUMNS: tuple[tuple[str, int], ...] = (
    ("objectives", 4_000),
    ("time_horizon", 2_000),
    ("liquidity", 4_000),
    ("diversification", 4_000),
    ("contribution_policy", 4_000),
    ("rebalancing_policy", 4_000),
    ("prohibited_assets", 4_000),
    ("leverage_policy", 4_000),
    ("decision_process", 4_000),
    ("notes", 8_000),
)


def policy_text_constraints(table_name: str) -> tuple[CheckConstraint, ...]:
    return tuple(
        CheckConstraint(
            f"char_length({column_name}) <= {maximum}",
            name=f"ck_{table_name}_{column_name}_length",
        )
        for column_name, maximum in POLICY_TEXT_COLUMNS
    )


class InvestmentPolicy(Base):
    __tablename__ = "investment_policies"
    __table_args__ = (
        UniqueConstraint("household_id", name="uq_investment_policies_household_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "household_profiles.id",
            name="fk_investment_policies_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvestmentPolicyVersion(Base):
    __tablename__ = "investment_policy_versions"
    __table_args__ = (
        CheckConstraint(
            "version_number > 0",
            name="ck_investment_policy_versions_version_number_positive",
        ),
        CheckConstraint(
            "status IN ('published', 'superseded')",
            name="ck_investment_policy_versions_status",
        ),
        CheckConstraint(
            "(status = 'published' AND superseded_at IS NULL) "
            "OR (status = 'superseded' AND superseded_at IS NOT NULL)",
            name="ck_investment_policy_versions_status_timestamps",
        ),
        *policy_text_constraints("investment_policy_versions"),
        UniqueConstraint(
            "policy_id",
            "version_number",
            name="uq_investment_policy_versions_policy_version",
        ),
        Index(
            "uq_investment_policy_versions_current_published",
            "policy_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
        Index(
            "ix_investment_policy_versions_policy_history",
            "policy_id",
            text("version_number DESC"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "investment_policies.id",
            name="fk_investment_policy_versions_policy_id_investment_policies",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    time_horizon: Mapped[str] = mapped_column(Text, nullable=False)
    liquidity: Mapped[str] = mapped_column(Text, nullable=False)
    diversification: Mapped[str] = mapped_column(Text, nullable=False)
    contribution_policy: Mapped[str] = mapped_column(Text, nullable=False)
    rebalancing_policy: Mapped[str] = mapped_column(Text, nullable=False)
    prohibited_assets: Mapped[str] = mapped_column(Text, nullable=False)
    leverage_policy: Mapped[str] = mapped_column(Text, nullable=False)
    decision_process: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sealed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InvestmentPolicyDraft(Base):
    __tablename__ = "investment_policy_drafts"
    __table_args__ = (
        CheckConstraint(
            "revision > 0", name="ck_investment_policy_drafts_revision_positive"
        ),
        *policy_text_constraints("investment_policy_drafts"),
        UniqueConstraint("policy_id", name="uq_investment_policy_drafts_policy_id"),
        Index("ix_investment_policy_drafts_source_version_id", "source_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "investment_policies.id",
            name="fk_investment_policy_drafts_policy_id_investment_policies",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    source_version_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(
            "investment_policy_versions.id",
            name="fk_investment_policy_drafts_source_version_id_versions",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    objectives: Mapped[str] = mapped_column(Text, nullable=False, default="")
    time_horizon: Mapped[str] = mapped_column(Text, nullable=False, default="")
    liquidity: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diversification: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contribution_policy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rebalancing_policy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prohibited_assets: Mapped[str] = mapped_column(Text, nullable=False, default="")
    leverage_policy: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision_process: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InvestmentPolicyDraftAllocation(Base):
    __tablename__ = "investment_policy_draft_allocations"
    __table_args__ = (
        CheckConstraint(
            "char_length(asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_draft_allocations_name_length",
        ),
        CheckConstraint(
            "char_length(normalized_asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_draft_allocations_normalized_name_length",
        ),
        CheckConstraint(
            "target_percentage > 0.00 AND target_percentage <= 100.00",
            name="ck_investment_policy_draft_allocations_percentage_range",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_investment_policy_draft_allocations_sort_order_nonnegative",
        ),
        UniqueConstraint(
            "draft_id",
            "normalized_asset_class_name",
            name="uq_investment_policy_draft_allocations_normalized_name",
        ),
        UniqueConstraint(
            "draft_id",
            "sort_order",
            name="uq_investment_policy_draft_allocations_sort_order",
        ),
        Index("ix_investment_policy_draft_allocations_draft_id", "draft_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "investment_policy_drafts.id",
            name="fk_policy_draft_allocations_draft_id_policy_drafts",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    asset_class_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_asset_class_name: Mapped[str] = mapped_column(Text, nullable=False)
    target_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class InvestmentPolicyVersionAllocation(Base):
    __tablename__ = "investment_policy_version_allocations"
    __table_args__ = (
        CheckConstraint(
            "char_length(asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_version_allocations_name_length",
        ),
        CheckConstraint(
            "char_length(normalized_asset_class_name) BETWEEN 1 AND 200",
            name="ck_investment_policy_version_allocations_normalized_name_length",
        ),
        CheckConstraint(
            "target_percentage > 0.00 AND target_percentage <= 100.00",
            name="ck_investment_policy_version_allocations_percentage_range",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_investment_policy_version_allocations_sort_order_nonnegative",
        ),
        UniqueConstraint(
            "version_id",
            "normalized_asset_class_name",
            name="uq_investment_policy_version_allocations_normalized_name",
        ),
        UniqueConstraint(
            "version_id",
            "sort_order",
            name="uq_investment_policy_version_allocations_sort_order",
        ),
        Index(
            "ix_investment_policy_version_allocations_version_order",
            "version_id",
            "sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "investment_policy_versions.id",
            name="fk_policy_version_allocations_version_id_policy_versions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    asset_class_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_asset_class_name: Mapped[str] = mapped_column(Text, nullable=False)
    target_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

# ---------------------------------------------------------------------------
# Decision Journal (Slice 3A)
# ---------------------------------------------------------------------------


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'archived')",
            name="ck_decisions_status_values",
        ),
        CheckConstraint(
            "archive_reason IS NULL OR char_length(archive_reason) <= 4000",
            name="ck_decisions_archive_reason_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "household_profiles.id",
            name="fk_decisions_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archive_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DecisionDraft(Base):
    __tablename__ = "decision_drafts"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) <= 500",
            name="ck_decision_drafts_title_length",
        ),
        CheckConstraint(
            "char_length(decision_summary) <= 8000",
            name="ck_decision_drafts_decision_summary_length",
        ),
        CheckConstraint(
            "char_length(rationale) <= 8000",
            name="ck_decision_drafts_rationale_length",
        ),
        CheckConstraint(
            "char_length(alternatives_considered) <= 8000",
            name="ck_decision_drafts_alternatives_considered_length",
        ),
        CheckConstraint(
            "char_length(risks_and_uncertainties) <= 8000",
            name="ck_decision_drafts_risks_and_uncertainties_length",
        ),
        CheckConstraint(
            "char_length(evidence_or_sources) <= 8000",
            name="ck_decision_drafts_evidence_or_sources_length",
        ),
        CheckConstraint(
            "char_length(expected_outcome) <= 4000",
            name="ck_decision_drafts_expected_outcome_length",
        ),
        CheckConstraint(
            "char_length(review_trigger) <= 4000",
            name="ck_decision_drafts_review_trigger_length",
        ),
        CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_decision_drafts_notes_length",
        ),
        CheckConstraint(
            "revision >= 1",
            name="ck_decision_drafts_revision_positive",
        ),
        UniqueConstraint(
            "decision_id",
            name="uq_decision_drafts_decision_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "decisions.id",
            name="fk_decision_drafts_decision_id_decisions",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    decision_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alternatives_considered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risks_and_uncertainties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_or_sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_date: Mapped[Optional[Any]] = mapped_column(
        Date, nullable=True
    )
    decision_date: Mapped[Optional[Any]] = mapped_column(
        Date, nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DecisionConfirmedSnapshot(Base):
    __tablename__ = "decision_confirmed_snapshots"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) <= 500",
            name="ck_decision_snapshots_title_length",
        ),
        CheckConstraint(
            "char_length(decision_summary) <= 8000",
            name="ck_decision_snapshots_decision_summary_length",
        ),
        CheckConstraint(
            "char_length(rationale) <= 8000",
            name="ck_decision_snapshots_rationale_length",
        ),
        CheckConstraint(
            "char_length(alternatives_considered) <= 8000",
            name="ck_decision_snapshots_alternatives_considered_length",
        ),
        CheckConstraint(
            "char_length(risks_and_uncertainties) <= 8000",
            name="ck_decision_snapshots_risks_and_uncertainties_length",
        ),
        CheckConstraint(
            "char_length(evidence_or_sources) <= 8000",
            name="ck_decision_snapshots_evidence_or_sources_length",
        ),
        CheckConstraint(
            "char_length(expected_outcome) <= 4000",
            name="ck_decision_snapshots_expected_outcome_length",
        ),
        CheckConstraint(
            "char_length(review_trigger) <= 4000",
            name="ck_decision_snapshots_review_trigger_length",
        ),
        CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_decision_snapshots_notes_length",
        ),
        CheckConstraint(
            "decision_date <= CURRENT_DATE",
            name="ck_decision_snapshots_decision_date_not_future",
        ),
        UniqueConstraint(
            "decision_id",
            name="uq_decision_snapshots_decision_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "decisions.id",
            name="fk_decision_snapshots_decision_id_decisions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    selected_policy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "investment_policy_versions.id",
            name="fk_decision_snapshots_policy_version_id_policy_versions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives_considered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risks_and_uncertainties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_or_sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_date: Mapped[Optional[Any]] = mapped_column(
        Date, nullable=True
    )
    decision_date: Mapped[Any] = mapped_column(
        Date, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DecisionCorrection(Base):
    __tablename__ = "decision_corrections"
    __table_args__ = (
        CheckConstraint(
            "char_length(title) <= 500",
            name="ck_decision_corrections_title_length",
        ),
        CheckConstraint(
            "char_length(decision_summary) <= 8000",
            name="ck_decision_corrections_decision_summary_length",
        ),
        CheckConstraint(
            "char_length(rationale) <= 8000",
            name="ck_decision_corrections_rationale_length",
        ),
        CheckConstraint(
            "char_length(alternatives_considered) <= 8000",
            name="ck_decision_corrections_alternatives_considered_length",
        ),
        CheckConstraint(
            "char_length(risks_and_uncertainties) <= 8000",
            name="ck_decision_corrections_risks_and_uncertainties_length",
        ),
        CheckConstraint(
            "char_length(evidence_or_sources) <= 8000",
            name="ck_decision_corrections_evidence_or_sources_length",
        ),
        CheckConstraint(
            "char_length(expected_outcome) <= 4000",
            name="ck_decision_corrections_expected_outcome_length",
        ),
        CheckConstraint(
            "char_length(review_trigger) <= 4000",
            name="ck_decision_corrections_review_trigger_length",
        ),
        CheckConstraint(
            "char_length(notes) <= 8000",
            name="ck_decision_corrections_notes_length",
        ),
        CheckConstraint(
            "char_length(correction_reason) BETWEEN 1 AND 8000",
            name="ck_decision_corrections_correction_reason_length",
        ),
        CheckConstraint(
            "decision_date <= CURRENT_DATE",
            name="ck_decision_corrections_decision_date_not_future",
        ),
        CheckConstraint(
            "correction_number >= 1",
            name="ck_decision_corrections_correction_number_positive",
        ),
        CheckConstraint(
            "actor = 'local-owner'",
            name="ck_decision_corrections_actor_local_owner",
        ),
        UniqueConstraint(
            "decision_id",
            "correction_number",
            name="uq_decision_corrections_decision_correction_number",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "decisions.id",
            name="fk_decision_corrections_decision_id_decisions",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    corrected_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "decision_confirmed_snapshots.id",
            name="fk_decision_corrections_corrected_entry_id_snapshots",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    correction_number: Mapped[int] = mapped_column(Integer, nullable=False)
    correction_reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'local-owner'")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives_considered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risks_and_uncertainties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_or_sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_date: Mapped[Optional[Any]] = mapped_column(
        Date, nullable=True
    )
    decision_date: Mapped[Any] = mapped_column(
        Date, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
