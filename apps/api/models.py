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
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


# ---------------------------------------------------------------------------
# Portfolio (Sprint 003 Slice A)
# ---------------------------------------------------------------------------


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active')",
            name="ck_portfolios_status",
        ),
        UniqueConstraint(
            "household_id",
            name="uq_portfolios_household_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "household_profiles.id",
            name="fk_portfolios_household_id_household_profiles",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "char_length(name) <= 200",
            name="ck_accounts_name_length",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_accounts_sort_order_nonnegative",
        ),
        Index("ix_accounts_portfolio_id_sort_order", "portfolio_id", "sort_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "portfolios.id",
            name="fk_accounts_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class PortfolioDraft(Base):
    __tablename__ = "portfolio_drafts"
    __table_args__ = (
        CheckConstraint(
            "expected_revision >= 1",
            name="ck_portfolio_drafts_revision_positive",
        ),
        CheckConstraint(
            "valuation_date IS NULL OR valuation_date <= CURRENT_DATE",
            name="ck_portfolio_drafts_valuation_date",
        ),
    )

    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "portfolios.id",
            name="fk_portfolio_drafts_portfolio_id_portfolios",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    expected_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    valuation_date: Mapped[Optional[Any]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PortfolioDraftHolding(Base):
    __tablename__ = "portfolio_draft_holdings"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_portfolio_draft_holdings_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_portfolio_draft_holdings_price_nonnegative",
        ),
        CheckConstraint(
            "valuation_date <= CURRENT_DATE",
            name="ck_portfolio_draft_holdings_valuation_date",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_portfolio_draft_holdings_sort_order_nonnegative",
        ),
        Index(
            "ix_portfolio_draft_holdings_portfolio_sort",
            "portfolio_id",
            "sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "portfolio_drafts.portfolio_id",
            name="fk_portfolio_draft_holdings_portfolio_id_drafts",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    asset_name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_category: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    valuation_date: Mapped[Any] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey(
            "accounts.id",
            name="fk_portfolio_draft_holdings_account_id_accounts",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('current', 'superseded')",
            name="ck_portfolio_snapshots_status",
        ),
        CheckConstraint(
            "valuation_date <= CURRENT_DATE",
            name="ck_portfolio_snapshots_date",
        ),
        CheckConstraint(
            "holding_count IS NULL OR holding_count >= 0",
            name="ck_portfolio_snapshots_holding_count_nonnegative",
        ),
        UniqueConstraint(
            "portfolio_id",
            "version_number",
            name="uq_portfolio_snapshots_portfolio_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "portfolios.id",
            name="fk_portfolio_snapshots_portfolio_id_portfolios",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="current", server_default=text("'current'")
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    holding_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    valuation_date: Mapped[Any] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PortfolioSnapshotHolding(Base):
    __tablename__ = "portfolio_snapshot_holdings"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_portfolio_snapshot_holdings_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_portfolio_snapshot_holdings_price_nonnegative",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_portfolio_snapshot_holdings_sort_order_nonnegative",
        ),
        Index(
            "ix_portfolio_snapshot_holdings_snapshot_sort",
            "snapshot_id",
            "sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "portfolio_snapshots.id",
            name="fk_portfolio_snapshot_holdings_snapshot_id_snapshots",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    asset_name: Mapped[str] = mapped_column(Text, nullable=False)
    asset_category: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    valuation_date: Mapped[Any] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )


# ---------------------------------------------------------------------------
# Guardian (Sprint 004)
# ---------------------------------------------------------------------------


class GuardianCheck(Base):
    __tablename__ = "guardian_checks"
    __table_args__ = (
        CheckConstraint(
            "check_type IN ('drift','category_exposure','staleness')",
            name="ck_guardian_checks_type",
        ),
        CheckConstraint(
            "status IN ('draft','confirmed')",
            name="ck_guardian_checks_status",
        ),
        UniqueConstraint("canonical_name", name="uq_guardian_checks_name"),
        Index("ix_guardian_checks_household", "household_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "household_profiles.id",
            name="fk_guardian_checks_household_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft", server_default=text("'draft'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    confirmed_versions: Mapped[list[GuardianCheckConfirmed]] = relationship(
        "GuardianCheckConfirmed", back_populates="check",
    )


class GuardianCheckDraft(Base):
    __tablename__ = "guardian_check_drafts"
    __table_args__ = (
        CheckConstraint(
            "threshold_value > 0 AND threshold_value <= 100",
            name="ck_guardian_drafts_threshold",
        ),
        CheckConstraint(
            "staleness_days IS NULL OR staleness_days > 0",
            name="ck_guardian_drafts_staleness_days",
        ),
        CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_guardian_drafts_severity",
        ),
    )

    check_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "guardian_checks.id",
            name="fk_guardian_check_drafts_check_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    threshold_value: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    target_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_holding_category: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    staleness_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    severity: Mapped[str] = mapped_column(
        Text, nullable=False, default="info", server_default=text("'info'")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GuardianCheckConfirmed(Base):
    __tablename__ = "guardian_check_confirmed"
    __table_args__ = (
        UniqueConstraint(
            "check_id", "version_number",
            name="uq_guardian_check_confirmed_version",
        ),
        UniqueConstraint(
            "id", "check_type",
            name="uq_guardian_check_confirmed_id_type",
        ),
        Index("ix_guardian_check_confirmed_check", "check_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    check_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "guardian_checks.id",
            name="fk_guardian_check_confirmed_check_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    target_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_holding_category: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    staleness_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Back-reference for service layer (e.g., cc.check.household_id)
    check: Mapped[GuardianCheck] = relationship(
        "GuardianCheck", back_populates="confirmed_versions",
    )


class GuardianEvaluationRun(Base):
    __tablename__ = "guardian_evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed','skipped_no_published_policy',"
            "'skipped_no_portfolio_snapshot','skipped_zero_total_value')",
            name="ck_guardian_evaluation_runs_status",
        ),
        CheckConstraint(
            "checks_evaluated >= 0",
            name="ck_guardian_evaluation_runs_checks_evaluated",
        ),
        CheckConstraint(
            "events_created >= 0",
            name="ck_guardian_evaluation_runs_events_created",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "household_profiles.id",
            name="fk_guardian_evaluation_runs_household_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    checks_evaluated: Mapped[int] = mapped_column(Integer, nullable=False)
    events_created: Mapped[int] = mapped_column(Integer, nullable=False)
    skip_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    as_of_date: Mapped[Any] = mapped_column(Date, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Sprint 005: Data Orchestration Persistence
# ---------------------------------------------------------------------------


class JobDefinition(Base):
    __tablename__ = "job_definitions"
    __table_args__ = (
        Index("ix_job_definitions_household", "household_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("household_profiles.id", ondelete="RESTRICT"))
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    job_params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("job_definition_id", name="uq_schedules_one_per_job"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_definition_id: Mapped[UUID] = mapped_column(ForeignKey("job_definitions.id", ondelete="CASCADE"))
    execution_time: Mapped[Any] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("ix_runs_job_definition", "job_definition_id"),
        Index("ix_runs_schedule", "schedule_id"),
        Index("ix_runs_status", "status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_definition_id: Mapped[UUID] = mapped_column(ForeignKey("job_definitions.id", ondelete="RESTRICT"))
    schedule_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("schedules.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    household_id: Mapped[UUID] = mapped_column(ForeignKey("household_profiles.id", ondelete="RESTRICT"))
    # Relationships
    attempts: Mapped[list["Attempt"]] = relationship("Attempt", back_populates="run", cascade="all, delete-orphan")
    lease: Mapped[Optional["Lease"]] = relationship("Lease", back_populates="run", uselist=False, cascade="all, delete-orphan")


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        UniqueConstraint("run_id", "attempt_number", name="uq_attempts_run_attempt"),
        Index("ix_attempts_run", "run_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="RESTRICT"))
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    run: Mapped["Run"] = relationship("Run", back_populates="attempts")


class Lease(Base):
    __tablename__ = "leases"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_leases_run"),
        Index("ix_leases_worker", "worker_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id", ondelete="RESTRICT"))
    worker_id: Mapped[str] = mapped_column(Text, nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    run: Mapped["Run"] = relationship("Run", back_populates="lease")


class GuardianEvent(Base):
    __tablename__ = "guardian_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["check_version_id", "check_type"],
            ["guardian_check_confirmed.id", "guardian_check_confirmed.check_type"],
            name="fk_guardian_events_check_version_type",
            ondelete="RESTRICT",
        ),
        Index("ix_guardian_events_check", "check_id"),
        Index("ix_guardian_events_run", "evaluation_run_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "guardian_evaluation_runs.id",
            name="fk_guardian_events_evaluation_run_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "household_profiles.id",
            name="fk_guardian_events_household_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    check_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "guardian_checks.id",
            name="fk_guardian_events_check_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    check_version_id: Mapped[UUID] = mapped_column(
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "investment_policy_versions.id",
            name="fk_guardian_events_policy_version_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    portfolio_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "portfolio_snapshots.id",
            name="fk_guardian_events_portfolio_snapshot_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    drift_pp: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    exposure_pct: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    staleness_days_actual: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    exceeded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE")
    )
    as_of_date: Mapped[Any] = mapped_column(Date, nullable=False)
