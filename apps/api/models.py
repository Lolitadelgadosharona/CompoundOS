from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
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
        Index("ix_audit_events_household_order", "household_id", "occurred_at", "id"),
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
