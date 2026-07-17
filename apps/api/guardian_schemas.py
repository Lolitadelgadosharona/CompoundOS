"""Pydantic schemas for Guardian check lifecycle (Sprint 004 Slice B)."""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Decimal helpers (reused pattern from Portfolio schemas)
# ---------------------------------------------------------------------------

THRESHOLD_MAX_VALUE = Decimal("100")
THRESHOLD_MAX_DECIMALS = 2
NAME_MAX_LENGTH = 200


def _validate_name(value: str) -> str:
    """Trim + NFKC normalize. Raises ValueError on empty after trim."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("Name must not be empty")
    if len(stripped) > NAME_MAX_LENGTH:
        raise ValueError(f"Name must be at most {NAME_MAX_LENGTH} characters")
    return stripped


def canonicalize_name(name: str) -> str:
    """Trim + NFKC + casefold, then strip again."""
    return unicodedata.normalize("NFKC", name).casefold().strip()


def _parse_decimal_string(value: Any, *, field_label: str = "value") -> Decimal:
    if not isinstance(value, str):
        raise ValueError(f"{field_label} must be a decimal string")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_label} must be a decimal string") from exc


# ---------------------------------------------------------------------------
# Guardian Check — create / update / replace draft
# ---------------------------------------------------------------------------


class GuardianCheckDraftCreate(BaseModel):
    """Create a new Guardian check identity + draft."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., min_length=1, max_length=NAME_MAX_LENGTH,
        description="Human-readable check name (canonicalized on save)",
    )
    check_type: Literal["drift", "category_exposure", "staleness"] = Field(
        ...,
        description="Type of check to create",
    )
    threshold_value: str = Field(
        ..., description="Decimal string, 0 < value <= 100",
    )
    target_category: Optional[str] = Field(
        None, max_length=200,
        description="Policy asset class name (required for drift)",
    )
    target_holding_category: Optional[str] = Field(
        None, max_length=200,
        description="Portfolio asset category (required for drift and category_exposure)",
    )
    staleness_days: Optional[int] = Field(
        None, ge=1, description="Days threshold (required for staleness)",
    )
    severity: Literal["info", "warning", "critical"] = Field(
        "info", description="Owner-defined severity label",
    )
    notes: Optional[str] = Field(None, max_length=8000)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return _validate_name(v)

    @field_validator("threshold_value")
    @classmethod
    def _validate_threshold(cls, v: str) -> str:
        parsed = _parse_decimal_string(v, field_label="threshold_value")
        if parsed <= 0:
            raise ValueError("threshold_value must be greater than 0")
        if parsed > THRESHOLD_MAX_VALUE:
            raise ValueError(f"threshold_value must be at most {THRESHOLD_MAX_VALUE}")
        return v


class GuardianCheckDraftUpdate(BaseModel):
    """Update mutable fields of a Guardian check draft."""

    model_config = ConfigDict(extra="forbid")

    threshold_value: Optional[str] = Field(
        None, description="Decimal string, 0 < value <= 100",
    )
    target_category: Optional[str] = Field(
        None, max_length=200, description="Policy asset class name",
    )
    target_holding_category: Optional[str] = Field(
        None, max_length=200, description="Portfolio asset category",
    )
    staleness_days: Optional[int] = Field(
        None, ge=1, description="Days threshold",
    )
    severity: Optional[Literal["info", "warning", "critical"]] = None
    notes: Optional[str] = Field(None, max_length=8000)
    expected_revision: int = Field(
        ..., ge=1, description="Revision counter for conflict detection",
    )

    @field_validator("threshold_value")
    @classmethod
    def _validate_threshold(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        parsed = _parse_decimal_string(v, field_label="threshold_value")
        if parsed <= 0:
            raise ValueError("threshold_value must be greater than 0")
        if parsed > THRESHOLD_MAX_VALUE:
            raise ValueError(f"threshold_value must be at most {THRESHOLD_MAX_VALUE}")
        return v

    @field_validator("target_category", "target_holding_category")
    @classmethod
    def _strip_if_present(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            return None
        return v.strip() if v is not None else None


class GuardianCheckConfirm(BaseModel):
    """Confirm a Guardian check draft into an immutable version."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(
        ..., ge=1,
        description="Expected draft revision — rejected on mismatch (409)",
    )
    confirmation: bool = Field(
        ..., description="Explicit confirmation gate — set to true",
    )


class GuardianCheckDiscard(BaseModel):
    """Discard a Guardian check draft."""

    model_config = ConfigDict(extra="forbid")

    confirmation: bool = Field(
        ..., description="Explicit discard gate — set to true",
    )


# ---------------------------------------------------------------------------
# Evaluation request
# ---------------------------------------------------------------------------


class GuardianEvaluateRequest(BaseModel):
    """Trigger evaluation. as_of_date is mandatory (no system clock reads)."""

    model_config = ConfigDict(extra="forbid")

    as_of_date: date = Field(
        ..., description="Explicit evaluation date (no system clock reads)",
    )
    confirmation: bool = Field(
        ..., description="Explicit evaluation gate — set to true",
    )


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------


class GuardianCheckIdentityResponse(BaseModel):
    """Identity fields for a Guardian check."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    name: str
    canonical_name: str
    check_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class GuardianCheckDraftResponse(BaseModel):
    """Mutable draft fields."""

    model_config = ConfigDict(from_attributes=True)

    threshold_value: str
    target_category: Optional[str] = None
    target_holding_category: Optional[str] = None
    staleness_days: Optional[int] = None
    severity: str
    notes: Optional[str] = None
    expected_revision: int
    updated_at: datetime

    @field_validator("threshold_value", mode="before")
    @classmethod
    def _decimal_to_str(cls, v: Any) -> str:
        return str(v)


class GuardianCheckDetailResponse(BaseModel):
    """Full check state: identity + draft + latest confirmed version."""

    model_config = ConfigDict(from_attributes=True)

    identity: GuardianCheckIdentityResponse
    draft: Optional[GuardianCheckDraftResponse] = None
    latest_version: Optional["GuardianCheckConfirmedResponse"] = None


class GuardianCheckConfirmedResponse(BaseModel):
    """Immutable confirmed version."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    check_id: UUID
    version_number: int
    check_type: str
    threshold_value: str
    target_category: Optional[str] = None
    target_holding_category: Optional[str] = None
    staleness_days: Optional[int] = None
    severity: str
    notes: Optional[str] = None
    confirmed_at: datetime

    @field_validator("threshold_value", mode="before")
    @classmethod
    def _decimal_to_str(cls, v: Any) -> str:
        return str(v)


class GuardianCheckListResponse(BaseModel):
    """List of check identities."""

    checks: list[GuardianCheckIdentityResponse]


class GuardianEventResponse(BaseModel):
    """A threshold breach event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evaluation_run_id: UUID
    check_id: UUID
    check_version_id: UUID
    check_type: str
    policy_version_id: UUID
    portfolio_snapshot_id: UUID
    exceeded: bool
    drift_pp: Optional[str] = None
    exposure_pct: Optional[str] = None
    staleness_days_actual: Optional[int] = None
    as_of_date: date
    detected_at: datetime

    @field_validator("drift_pp", "exposure_pct", mode="before")
    @classmethod
    def _decimal_to_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)


class GuardianEvaluationRunResponse(BaseModel):
    """An evaluation execution record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    status: str
    skip_reason: Optional[str] = None
    checks_evaluated: int
    events_created: int
    as_of_date: date
    created_at: datetime


class GuardianEvaluateResponse(BaseModel):
    """Returned after manual evaluation call."""

    evaluation_run: GuardianEvaluationRunResponse
    events: list[GuardianEventResponse]


class GuardianEvaluationRunListResponse(BaseModel):
    """List of evaluation runs."""

    runs: list[GuardianEvaluationRunResponse]


class GuardianEventListResponse(BaseModel):
    """Paginated event list."""

    events: list[GuardianEventResponse]


# Rebuild forward reference
GuardianCheckDetailResponse.model_rebuild()
