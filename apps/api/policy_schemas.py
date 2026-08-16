from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

POLICY_TEXT_LIMITS = {
    "objectives": 4_000,
    "time_horizon": 2_000,
    "liquidity": 4_000,
    "diversification": 4_000,
    "contribution_policy": 4_000,
    "rebalancing_policy": 4_000,
    "prohibited_assets": 4_000,
    "leverage_policy": 4_000,
    "decision_process": 4_000,
    "notes": 8_000,
}
POLICY_TEXT_FIELDS = tuple(POLICY_TEXT_LIMITS)
REQUIRED_PUBLISH_FIELDS = ("objectives", "time_horizon", "decision_process")


def normalize_asset_class_name(value: str) -> tuple[str, str]:
    display_name = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip())
    if not display_name:
        raise ValueError("asset class name cannot be blank")
    if len(display_name) > 200:
        raise ValueError("asset class name must contain at most 200 characters")
    return display_name, display_name.casefold()


class PolicyTextFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    objectives: str = Field(default="", max_length=4_000)
    time_horizon: str = Field(default="", max_length=2_000)
    liquidity: str = Field(default="", max_length=4_000)
    diversification: str = Field(default="", max_length=4_000)
    contribution_policy: str = Field(default="", max_length=4_000)
    rebalancing_policy: str = Field(default="", max_length=4_000)
    prohibited_assets: str = Field(default="", max_length=4_000)
    leverage_policy: str = Field(default="", max_length=4_000)
    decision_process: str = Field(default="", max_length=4_000)
    notes: str = Field(default="", max_length=8_000)


class EmptyPolicyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1)
    objectives: Optional[str] = Field(default=None, max_length=4_000)
    time_horizon: Optional[str] = Field(default=None, max_length=2_000)
    liquidity: Optional[str] = Field(default=None, max_length=4_000)
    diversification: Optional[str] = Field(default=None, max_length=4_000)
    contribution_policy: Optional[str] = Field(default=None, max_length=4_000)
    rebalancing_policy: Optional[str] = Field(default=None, max_length=4_000)
    prohibited_assets: Optional[str] = Field(default=None, max_length=4_000)
    leverage_policy: Optional[str] = Field(default=None, max_length=4_000)
    decision_process: Optional[str] = Field(default=None, max_length=4_000)
    notes: Optional[str] = Field(default=None, max_length=8_000)

    @field_validator(*POLICY_TEXT_FIELDS)
    @classmethod
    def reject_null_text(cls, value: Optional[str]) -> str:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class AllocationItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_class_name: str
    target_percentage: str

    @field_validator("asset_class_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        display_name, _ = normalize_asset_class_name(value)
        return display_name

    @field_validator("target_percentage", mode="before")
    @classmethod
    def validate_decimal_string(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("target percentage must be a decimal string")
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
            raise ValueError("target percentage must have at most two decimal places")
        try:
            percentage = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("target percentage must be a decimal string") from exc
        if percentage <= Decimal("0.00") or percentage > Decimal("100.00"):
            raise ValueError("target percentage must be greater than 0 and at most 100")
        return format(percentage, ".2f")


class AllocationReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    items: list[AllocationItemInput]

    @model_validator(mode="after")
    def reject_canonical_duplicates(self) -> AllocationReplaceRequest:
        canonical_names = [
            normalize_asset_class_name(item.asset_class_name)[1] for item in self.items
        ]
        if len(canonical_names) != len(set(canonical_names)):
            raise ValueError("asset class names must be unique after normalization")
        return self


class ExpectedRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class CreatePolicyDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_version_id: Optional[UUID] = None


class PublishPolicyDraftRequest(ExpectedRevisionRequest):
    confirmation: Literal[True]


class AllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_class_name: str
    target_percentage: str
    sort_order: int

    @field_validator("target_percentage", mode="before")
    @classmethod
    def serialize_decimal(cls, value: Any) -> str:
        return format(Decimal(str(value)), ".2f")


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    created_at: datetime
    updated_at: datetime


class PolicyDraftResponse(PolicyTextFields):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_id: UUID
    source_version_id: Optional[UUID]
    revision: int
    created_at: datetime
    updated_at: datetime
    allocations: list[AllocationResponse]


class PolicyCreateResponse(BaseModel):
    policy: PolicyResponse
    draft: PolicyDraftResponse


class PolicyVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    status: str
    published_at: datetime
    superseded_at: Optional[datetime]


class PolicyVersionResponse(PolicyTextFields):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_id: UUID
    version_number: int
    status: str
    published_at: datetime
    superseded_at: Optional[datetime]
    allocations: list[AllocationResponse]


class PolicyVersionHistoryResponse(BaseModel):
    items: list[PolicyVersionSummary]
    next_before_version_number: Optional[int]


class PolicyAuditEventResponse(BaseModel):
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


class PersonalPolicySetupRequest(BaseModel):
    """PE-003 — one-shot Personal Edition policy setup payload.

    Maps the simple setup fields onto the existing policy text fields and
    a default equities/cash allocation derived from min_cash_pct.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    investment_goal: str = Field(min_length=1, max_length=4_000)
    risk_preference: Literal["Conservative", "Moderate", "Growth"]
    investment_horizon: str = Field(min_length=1, max_length=2_000)
    max_single_position_pct: int = Field(default=15, ge=1, le=100)
    min_cash_pct: int = Field(default=10, ge=0, le=99)
    principles: str = Field(min_length=1, max_length=4_000)
