from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

HOUSEHOLD_NAME_MAX_LENGTH = 200
INVESTMENT_HORIZON_MAX_LENGTH = 2_000
LIQUIDITY_NEEDS_MAX_LENGTH = 4_000
RISK_STATEMENT_MAX_LENGTH = 4_000
NOTES_MAX_LENGTH = 8_000


class HouseholdFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    household_name: str = Field(min_length=1, max_length=HOUSEHOLD_NAME_MAX_LENGTH)
    base_currency: str = Field(pattern=r"^[A-Z]{3}$")
    investment_horizon: str = Field(default="", max_length=INVESTMENT_HORIZON_MAX_LENGTH)
    liquidity_needs: str = Field(default="", max_length=LIQUIDITY_NEEDS_MAX_LENGTH)
    risk_statement: str = Field(default="", max_length=RISK_STATEMENT_MAX_LENGTH)
    notes: str = Field(default="", max_length=NOTES_MAX_LENGTH)


class HouseholdCreate(HouseholdFields):
    pass


class HouseholdUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    household_name: Optional[str] = Field(
        default=None, min_length=1, max_length=HOUSEHOLD_NAME_MAX_LENGTH
    )
    base_currency: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")
    investment_horizon: Optional[str] = Field(
        default=None, max_length=INVESTMENT_HORIZON_MAX_LENGTH
    )
    liquidity_needs: Optional[str] = Field(default=None, max_length=LIQUIDITY_NEEDS_MAX_LENGTH)
    risk_statement: Optional[str] = Field(default=None, max_length=RISK_STATEMENT_MAX_LENGTH)
    notes: Optional[str] = Field(default=None, max_length=NOTES_MAX_LENGTH)

    @field_validator("*")
    @classmethod
    def reject_explicit_null(cls, value: Optional[str]) -> str:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class HouseholdResponse(HouseholdFields):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    actor: str
    action: str
    entity_type: str
    entity_id: UUID
    occurred_at: datetime
    metadata: dict[str, Any] = Field(validation_alias="event_metadata")
