"""Pydantic schemas for Sprint 009 Slice A — Core Portfolio Foundation.

These are domain-layer schemas for validation and serialization.
API-specific request/response contracts will be added in later slices.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Constants ──────────────────────────────────────────────────────────

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

VALID_ASSET_TYPES = frozenset({
    "ETF", "STOCK", "BOND", "CASH", "MONEY_MARKET", "FUND", "OTHER",
})

VALID_ACCOUNT_TYPES = frozenset({"brokerage", "bank", "retirement", "other"})

VALID_CAPITAL_BUCKETS = frozenset({
    "CORE", "EXPLORATION", "CASH_RESERVE", "RETIREMENT", "OTHER",
})

VALID_TRANSACTION_TYPES = frozenset({
    "BUY", "SELL", "DIVIDEND", "INTEREST", "DEPOSIT",
    "WITHDRAWAL", "FEE", "TRANSFER_IN", "TRANSFER_OUT", "SPLIT", "OTHER",
})

VALID_POSITION_SOURCES = frozenset({
    "interactive_brokers", "hsbc", "schwab", "csv", "manual", "compoundos_derived",
})

VALID_QUANTITY_SOURCES = frozenset({"provider_reported", "compoundos_derived"})

VALID_SOURCE_TYPES = frozenset({"broker", "bank", "csv", "manual"})


# ── Helpers ────────────────────────────────────────────────────────────


def _validate_currency(v: str) -> str:
    if not CURRENCY_PATTERN.match(v):
        raise ValueError(f"Currency must be a 3-letter ISO code, got: {v!r}")
    return v


def _validate_decimal(value: Any, *, field_label: str = "value") -> Decimal:
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{field_label} must be a valid decimal") from exc
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    raise ValueError(f"{field_label} must be a decimal or numeric string")


# ── Asset ──────────────────────────────────────────────────────────────


class AssetCreate(BaseModel):
    """Input for creating a canonical asset."""

    symbol: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    asset_type: str
    currency: str
    exchange: Optional[str] = None
    isin: Optional[str] = None
    asset_class: Optional[str] = None
    sub_asset_class: Optional[str] = None
    region: Optional[str] = None
    sector: Optional[str] = None

    @field_validator("asset_type")
    @classmethod
    def _check_asset_type(cls, v: str) -> str:
        if v not in VALID_ASSET_TYPES:
            raise ValueError(
                f"asset_type must be one of {sorted(VALID_ASSET_TYPES)}, got: {v!r}"
            )
        return v

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        return _validate_currency(v)


class AssetResponse(BaseModel):
    """Canonical asset as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: Optional[str]
    name: str
    asset_type: str
    currency: str
    exchange: Optional[str]
    isin: Optional[str]
    asset_class: Optional[str]
    sub_asset_class: Optional[str]
    region: Optional[str]
    sector: Optional[str]
    created_at: datetime


# ── Account (extended) ─────────────────────────────────────────────────


class AccountUpdate(BaseModel):
    """Fields that can be updated on an existing account."""

    account_type: Optional[str] = None
    capital_bucket: Optional[str] = None
    currency: Optional[str] = None
    provider: Optional[str] = None
    provider_account_id: Optional[str] = None

    @field_validator("account_type")
    @classmethod
    def _check_account_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ACCOUNT_TYPES:
            raise ValueError(
                f"account_type must be one of {sorted(VALID_ACCOUNT_TYPES)}, got: {v!r}"
            )
        return v

    @field_validator("capital_bucket")
    @classmethod
    def _check_bucket(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CAPITAL_BUCKETS:
            raise ValueError(
                f"capital_bucket must be one of {sorted(VALID_CAPITAL_BUCKETS)}, got: {v!r}"
            )
        return v

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_currency(v)
        return v


# ── Position ───────────────────────────────────────────────────────────


class PositionCreate(BaseModel):
    """Input for recording a position snapshot."""

    account_id: UUID
    asset_id: UUID
    quantity: str  # decimal string
    quantity_source: str
    avg_cost: Optional[str] = None
    avg_cost_currency: str = "USD"
    avg_cost_source: Optional[str] = None
    market_price: Optional[str] = None
    market_price_currency: Optional[str] = None
    market_price_as_of: Optional[datetime] = None
    observed_at: datetime
    source: str
    source_record_id: Optional[str] = None

    @field_validator("quantity", "avg_cost", "market_price", mode="before")
    @classmethod
    def _validate_numeric_strings(cls, v: Any) -> Any:
        if v is not None and isinstance(v, str):
            _validate_decimal(v, field_label="numeric value")
        return v

    @field_validator("quantity_source")
    @classmethod
    def _check_quantity_source(cls, v: str) -> str:
        if v not in VALID_QUANTITY_SOURCES:
            raise ValueError(
                f"quantity_source must be one of {sorted(VALID_QUANTITY_SOURCES)}, got: {v!r}"
            )
        return v

    @field_validator("source")
    @classmethod
    def _check_source(cls, v: str) -> str:
        if v not in VALID_POSITION_SOURCES:
            raise ValueError(
                f"source must be one of {sorted(VALID_POSITION_SOURCES)}, got: {v!r}"
            )
        return v

    @field_validator("avg_cost_currency", "market_price_currency")
    @classmethod
    def _check_currencies(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_currency(v)
        return v


class PositionResponse(BaseModel):
    """Position as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    asset_id: UUID
    quantity: Decimal
    quantity_source: str
    avg_cost: Optional[Decimal]
    avg_cost_currency: str
    avg_cost_source: Optional[str]
    market_price: Optional[Decimal]
    market_price_currency: str
    market_price_as_of: Optional[datetime]
    market_value: Optional[Decimal]
    market_value_currency: Optional[str]
    cost_basis: Optional[Decimal]
    cost_basis_currency: Optional[str]
    unrealized_gain_loss: Optional[Decimal]
    observed_at: datetime
    source: str
    source_record_id: Optional[str]
    is_latest: bool
    created_at: datetime


# ── Cash Balance ───────────────────────────────────────────────────────


class CashBalanceCreate(BaseModel):
    """Input for recording a cash balance snapshot."""

    account_id: UUID
    currency: str
    amount: str  # decimal string
    observed_at: datetime
    source: str
    source_record_id: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        return _validate_currency(v)

    @field_validator("amount", mode="before")
    @classmethod
    def _validate_amount(cls, v: Any) -> Any:
        if isinstance(v, str):
            _validate_decimal(v, field_label="amount")
        return v


class CashBalanceResponse(BaseModel):
    """Cash balance as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    currency: str
    amount: Decimal
    observed_at: datetime
    source: str
    source_record_id: Optional[str]
    is_latest: bool
    created_at: datetime


# ── Transaction ────────────────────────────────────────────────────────


class TransactionCreate(BaseModel):
    """Input for recording a financial transaction."""

    account_id: UUID
    asset_id: Optional[UUID] = None
    transaction_type: str
    quantity: Optional[str] = None
    price: Optional[str] = None
    price_currency: Optional[str] = None
    amount: Optional[str] = None
    amount_currency: Optional[str] = None
    fee: Optional[str] = None
    fee_currency: Optional[str] = None
    executed_at: datetime
    settled_at: Optional[datetime] = None
    source: str
    source_record_id: Optional[str] = None

    @field_validator("transaction_type")
    @classmethod
    def _check_transaction_type(cls, v: str) -> str:
        if v not in VALID_TRANSACTION_TYPES:
            raise ValueError(
                f"transaction_type must be one of {sorted(VALID_TRANSACTION_TYPES)}, got: {v!r}"
            )
        return v


class TransactionResponse(BaseModel):
    """Transaction as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    asset_id: Optional[UUID]
    transaction_type: str
    quantity: Optional[Decimal]
    price: Optional[Decimal]
    price_currency: Optional[str]
    amount: Optional[Decimal]
    amount_currency: Optional[str]
    fee: Optional[Decimal]
    fee_currency: Optional[str]
    executed_at: datetime
    settled_at: Optional[datetime]
    source: str
    source_record_id: Optional[str]
    imported_at: datetime
    created_at: datetime


# ── FX Rate ────────────────────────────────────────────────────────────


class FxRateCreate(BaseModel):
    """Input for recording an exchange rate observation."""

    from_currency: str
    to_currency: str
    rate: str  # decimal string
    rate_source: str
    observed_at: datetime

    @field_validator("from_currency", "to_currency")
    @classmethod
    def _check_currency(cls, v: str) -> str:
        return _validate_currency(v)

    @field_validator("rate", mode="before")
    @classmethod
    def _validate_rate(cls, v: Any) -> Any:
        if isinstance(v, str):
            parsed = _validate_decimal(v, field_label="rate")
            if parsed <= 0:
                raise ValueError("rate must be positive")
            return str(parsed)
        return v


class FxRateResponse(BaseModel):
    """FX rate as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_currency: str
    to_currency: str
    rate: Decimal
    rate_source: str
    observed_at: datetime
    imported_at: datetime
    created_at: datetime


# ── Data Source ────────────────────────────────────────────────────────


class DataSourceCreate(BaseModel):
    """Input for registering a data source."""

    source_key: str = Field(..., min_length=1, max_length=200)
    source_type: str
    display_name: Optional[str] = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def _check_source_type(cls, v: str) -> str:
        if v not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type must be one of {sorted(VALID_SOURCE_TYPES)}, got: {v!r}"
            )
        return v


class DataSourceResponse(BaseModel):
    """Data source as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_key: str
    source_type: str
    display_name: Optional[str]
    is_active: bool
    last_import_at: Optional[datetime]
    source_metadata: dict[str, Any]
    created_at: datetime
