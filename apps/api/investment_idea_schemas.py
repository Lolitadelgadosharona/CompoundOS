"""Pydantic schemas for Sprint 009 Slice C — Investment Idea + Decision Bridge."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_STATUSES = frozenset({
    "draft", "under_review", "approved", "rejected", "deferred", "cancelled",
})
VALID_CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW", "SPECULATIVE"})
VALID_SOURCES = frozenset({"owner", "committee", "guardian", "external"})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"under_review", "deferred", "cancelled"}),
    "under_review": frozenset({"approved", "rejected", "deferred", "cancelled"}),
    "approved": frozenset({"cancelled"}),
    "rejected": frozenset({"draft"}),
    "deferred": frozenset({"draft", "under_review"}),
    "cancelled": frozenset({"draft"}),
}


class InvestmentIdeaCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    asset_id: Optional[UUID] = None
    thesis: Optional[str] = None
    proposed_allocation_pct: Optional[str] = None
    proposed_amount: Optional[str] = None
    proposed_amount_currency: Optional[str] = None
    source: str = "owner"
    expected_holding_period: Optional[str] = None
    expected_return_rationale: Optional[str] = None
    downside_thesis: Optional[str] = None
    risks: Optional[str] = None
    catalysts: Optional[str] = None
    valuation_assumptions: Optional[str] = None
    confidence: Optional[str] = None
    policy_version_id: Optional[UUID] = None

    @field_validator("source")
    @classmethod
    def _check_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
        return v

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {sorted(VALID_CONFIDENCE)}")
        return v


class InvestmentIdeaUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    thesis: Optional[str] = None
    proposed_allocation_pct: Optional[str] = None
    proposed_amount: Optional[str] = None
    proposed_amount_currency: Optional[str] = None
    expected_holding_period: Optional[str] = None
    expected_return_rationale: Optional[str] = None
    downside_thesis: Optional[str] = None
    risks: Optional[str] = None
    catalysts: Optional[str] = None
    valuation_assumptions: Optional[str] = None
    confidence: Optional[str] = None
    policy_version_id: Optional[UUID] = None

    @field_validator("confidence")
    @classmethod
    def _check_confidence(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {sorted(VALID_CONFIDENCE)}")
        return v


class InvestmentIdeaStatusTransition(BaseModel):
    new_status: str
    reason: Optional[str] = None

    @field_validator("new_status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v


class InvestmentIdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    asset_id: Optional[UUID] = None
    title: str
    thesis: Optional[str] = None
    proposed_allocation_pct: Optional[Decimal] = None
    proposed_amount: Optional[Decimal] = None
    proposed_amount_currency: Optional[str] = None
    source: str
    expected_holding_period: Optional[str] = None
    expected_return_rationale: Optional[str] = None
    downside_thesis: Optional[str] = None
    risks: Optional[str] = None
    catalysts: Optional[str] = None
    valuation_assumptions: Optional[str] = None
    confidence: Optional[str] = None
    policy_version_id: Optional[UUID] = None
    status: str
    status_change_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IdeaStatusHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    idea_id: UUID
    old_status: Optional[str] = None
    new_status: str
    changed_at: datetime
    reason: Optional[str] = None
