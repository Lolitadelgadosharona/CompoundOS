"""Pydantic schemas for the Portfolio backend workflow (Sprint 003 Slice B)."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ASSET_NAME_MAX_LENGTH = 500
ASSET_CATEGORY_MAX_LENGTH = 200
NOTES_MAX_LENGTH = 8_000


def _validate_decimal_string(
    value: Any,
    *,
    min_value: Optional[Decimal] = None,
    max_value: Optional[Decimal] = None,
    max_decimals: int = 8,
    field_label: str = "value",
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_label} must be a decimal string")
    if not re.fullmatch(r"\d+(?:\.\d+)?", value):
        raise ValueError(f"{field_label} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field_label} must be a decimal string") from exc
    exponent: int = parsed.as_tuple().exponent  # type: ignore[assignment]
    if exponent < -max_decimals:
        raise ValueError(
            f"{field_label} must have at most {max_decimals} decimal places"
        )
    if min_value is not None and parsed < min_value:
        raise ValueError(f"{field_label} must be at least {min_value}")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"{field_label} must be at most {max_value}")
    return str(parsed)


def _validate_valuation_date(value: Any) -> date:
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("valuation_date must be a valid date") from exc
    if not isinstance(value, date):
        raise ValueError("valuation_date must be a valid date")
    if value > date.today():
        raise ValueError("valuation_date must not be in the future")
    return value


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EmptyPortfolioCreateRequest(BaseModel):
    """Explicitly empty body for idempotent portfolio creation."""

    model_config = ConfigDict(extra="forbid")


class HoldingInput(BaseModel):
    """A single holding to be created or replaced in the draft."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_name: str = Field(min_length=1, max_length=ASSET_NAME_MAX_LENGTH)
    asset_category: str = Field(min_length=1, max_length=ASSET_CATEGORY_MAX_LENGTH)
    quantity: str
    unit_price: str
    valuation_date: date
    notes: str = Field(default="", max_length=NOTES_MAX_LENGTH)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: str) -> str:
        return _validate_decimal_string(
            value,
            min_value=Decimal("0.00000001"),
            max_value=Decimal("999999999999.99999999"),
            max_decimals=8,
            field_label="quantity",
        )

    @field_validator("unit_price", mode="before")
    @classmethod
    def validate_unit_price(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("unit_price must be a decimal string")
        return _validate_decimal_string(
            value,
            min_value=Decimal("0.0000"),
            max_value=Decimal("9999999999999999.9999"),
            max_decimals=4,
            field_label="unit_price",
        )

    @field_validator("valuation_date", mode="before")
    @classmethod
    def validate_date(cls, value: Any) -> date:
        return _validate_valuation_date(value)


class HoldingsReplaceRequest(BaseModel):
    """Atomic replacement of the entire holding collection."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    items: list[HoldingInput]


class PortfolioDraftUpdate(BaseModel):
    """Partial update of draft metadata (valuation_date, notes)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expected_revision: int = Field(ge=1)
    valuation_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=NOTES_MAX_LENGTH)

    @field_validator("valuation_date", mode="before")
    @classmethod
    def validate_date(cls, value: Any) -> Optional[date]:
        if value is None:
            return None
        return _validate_valuation_date(value)

    @field_validator("notes")
    @classmethod
    def reject_null_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None and "notes" in cls.__pydantic_fields_set__:
            raise ValueError("notes cannot be null")
        return value


class ConfirmDraftRequest(BaseModel):
    """Confirm the draft, creating an immutable snapshot."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    confirmation: Literal[True]


class DiscardDraftRequest(BaseModel):
    """Discard the draft."""

    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_name: str
    asset_category: str
    quantity: str
    unit_price: str
    total_value: str
    valuation_date: date
    notes: Optional[str] = None
    sort_order: int

    @field_validator("quantity", mode="before")
    @classmethod
    def serialize_quantity(cls, value: Any) -> str:
        return format(Decimal(str(value)), ".8f")

    @field_validator("unit_price", mode="before")
    @classmethod
    def serialize_price(cls, value: Any) -> str:
        return format(Decimal(str(value)), ".4f")

    @field_validator("total_value", mode="before")
    @classmethod
    def serialize_total(cls, value: Any) -> str:
        return format(Decimal(str(value)), ".2f")


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    status: str
    created_at: datetime


class PortfolioDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: UUID
    expected_revision: int
    valuation_date: Optional[date] = None
    notes: Optional[str] = None
    updated_at: datetime
    holdings: list[HoldingResponse]


class PortfolioCreateResponse(BaseModel):
    portfolio: PortfolioResponse
    draft: PortfolioDraftResponse


class PortfolioSnapshotSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    status: str
    confirmed_at: Optional[datetime] = None
    holding_count: Optional[int] = None
    valuation_date: date


class PortfolioSnapshotDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    portfolio_id: UUID
    version_number: int
    status: str
    confirmed_at: Optional[datetime] = None
    holding_count: Optional[int] = None
    valuation_date: date
    notes: Optional[str] = None
    holdings: list[HoldingResponse]


class PortfolioSnapshotHistoryResponse(BaseModel):
    items: list[PortfolioSnapshotSummary]
    next_before_version_number: Optional[int] = None


class PortfolioAuditEventResponse(BaseModel):
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
