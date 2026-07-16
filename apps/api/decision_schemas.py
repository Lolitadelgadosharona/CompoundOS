"""Pydantic schemas for the Decision Journal backend workflow (Slice 3B)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

DECISION_TEXT_FIELDS = tuple(DECISION_TEXT_LIMITS)

CONFIRM_REQUIRED_FIELDS = ("title", "decision_summary", "rationale", "decision_date")



def _validate_decision_date(value: date | None) -> date | None:
    """Validate decision_date: strict DATE, no future, no impossible."""
    if value is None:
        return None
    if value > date.today():
        raise ValueError("decision_date must not be in the future")
    return value


class CreateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=DECISION_TEXT_LIMITS["title"])


class UpdateDecisionDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1)
    title: Optional[str] = Field(
        default=None, min_length=1, max_length=DECISION_TEXT_LIMITS["title"]
    )
    decision_summary: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["decision_summary"]
    )
    rationale: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["rationale"]
    )
    alternatives_considered: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["alternatives_considered"]
    )
    risks_and_uncertainties: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["risks_and_uncertainties"]
    )
    evidence_or_sources: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["evidence_or_sources"]
    )
    expected_outcome: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["expected_outcome"]
    )
    review_trigger: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["review_trigger"]
    )
    notes: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["notes"]
    )
    decision_date: Optional[date] = None
    review_date: Optional[date] = None

    @field_validator("decision_date")
    @classmethod
    def validate_decision_date(cls, value: date | None) -> date | None:
        return _validate_decision_date(value)


class ConfirmDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1)
    confirmation: Literal[True]


class DiscardDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class ArchiveDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    archive_reason: Optional[str] = Field(default=None, max_length=4_000)


class UnarchiveDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AppendCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    correction_reason: str = Field(min_length=1, max_length=8_000)
    title: str = Field(min_length=1, max_length=DECISION_TEXT_LIMITS["title"])
    decision_summary: str = Field(
        min_length=1, max_length=DECISION_TEXT_LIMITS["decision_summary"]
    )
    rationale: str = Field(
        min_length=1, max_length=DECISION_TEXT_LIMITS["rationale"]
    )
    alternatives_considered: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["alternatives_considered"]
    )
    risks_and_uncertainties: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["risks_and_uncertainties"]
    )
    evidence_or_sources: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["evidence_or_sources"]
    )
    expected_outcome: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["expected_outcome"]
    )
    review_trigger: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["review_trigger"]
    )
    notes: Optional[str] = Field(
        default=None, max_length=DECISION_TEXT_LIMITS["notes"]
    )
    decision_date: date
    review_date: Optional[date] = None

    @field_validator("decision_date")
    @classmethod
    def validate_correction_decision_date(cls, value: date) -> date:
        result = _validate_decision_date(value)
        assert result is not None
        return result


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DecisionCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    revision: int
    status: str
    created_at: datetime
    updated_at: datetime


class DecisionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None


class DecisionListResponse(BaseModel):
    items: list[DecisionListItem]


class DraftDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    decision_id: UUID
    title: str
    decision_summary: Optional[str]
    rationale: Optional[str]
    alternatives_considered: Optional[str]
    risks_and_uncertainties: Optional[str]
    evidence_or_sources: Optional[str]
    expected_outcome: Optional[str]
    review_trigger: Optional[str]
    review_date: Optional[date]
    decision_date: Optional[date]
    notes: Optional[str]
    revision: int
    created_at: datetime
    updated_at: datetime


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    decision_summary: str
    rationale: str
    alternatives_considered: Optional[str]
    risks_and_uncertainties: Optional[str]
    evidence_or_sources: Optional[str]
    expected_outcome: Optional[str]
    review_trigger: Optional[str]
    review_date: Optional[date]
    decision_date: date
    notes: Optional[str]
    confirmed_at: datetime
    selected_policy_version_id: UUID


class ConfirmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    decision_id: UUID
    title: str
    decision_summary: str
    rationale: str
    alternatives_considered: Optional[str]
    risks_and_uncertainties: Optional[str]
    evidence_or_sources: Optional[str]
    expected_outcome: Optional[str]
    review_trigger: Optional[str]
    review_date: Optional[date]
    decision_date: date
    notes: Optional[str]
    confirmed_at: datetime
    selected_policy_version_id: UUID


class CorrectionMetadataResponse(BaseModel):
    correction_id: UUID
    correction_number: int
    created_at: datetime
    correction_reason: str


class DecisionDetailResponse(BaseModel):
    id: UUID
    household_id: UUID
    status: str
    created_at: datetime
    archived_at: Optional[datetime]
    archive_reason: Optional[str]
    original_snapshot: Optional[SnapshotResponse] = None
    effective_snapshot: Optional[SnapshotResponse] = None
    latest_correction_metadata: Optional[CorrectionMetadataResponse] = None
    corrections_count: int = 0


class ArchiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    archived_at: Optional[datetime]
    archive_reason: Optional[str]


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    decision_id: UUID
    corrected_entry_id: UUID
    correction_number: int
    correction_reason: str
    actor: str
    title: str
    decision_summary: str
    rationale: str
    alternatives_considered: Optional[str]
    risks_and_uncertainties: Optional[str]
    evidence_or_sources: Optional[str]
    expected_outcome: Optional[str]
    review_trigger: Optional[str]
    review_date: Optional[date]
    decision_date: date
    notes: Optional[str]
    created_at: datetime


class CorrectionListResponse(BaseModel):
    items: list[CorrectionResponse]


class DecisionAuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    actor: str
    action: str
    entity_type: str
    entity_id: UUID
    occurred_at: datetime
    sequence_number: int
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")


class DecisionAuditListResponse(BaseModel):
    items: list[DecisionAuditEventResponse]
    next_before_sequence_number: Optional[int]
