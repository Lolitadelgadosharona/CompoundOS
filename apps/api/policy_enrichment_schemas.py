"""Pydantic schemas for Sprint 009 Slice B — Investment Policy Enrichment.

Domain-layer schemas for policy_capital_buckets and policy_rules.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Constants ──────────────────────────────────────────────────────────

VALID_RULE_TYPES = frozenset({
    "max_single_position_pct",
    "max_sector_concentration_pct",
    "max_drawdown_pct",
    "min_cash_reserve_pct",
    "approval_required_for",
    "exploration_capital_limit",
    "custom",
})

VALID_SEVERITIES = frozenset({"info", "warning", "critical"})


def _validate_pct(value: Any, *, field_label: str = "value") -> Decimal:
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{field_label} must be a valid decimal") from exc
    elif isinstance(value, (int, float, Decimal)):
        parsed = Decimal(str(value))
    else:
        raise ValueError(f"{field_label} must be a decimal or numeric string")
    if parsed < 0 or parsed > 100:
        raise ValueError(f"{field_label} must be between 0 and 100")
    return parsed


# ── Capital Bucket ─────────────────────────────────────────────────────


class PolicyCapitalBucketCreate(BaseModel):
    """Input for a single capital bucket within a draft."""

    bucket_name: str = Field(..., min_length=1, max_length=200)
    target_pct: str  # decimal string
    min_pct: Optional[str] = None
    max_pct: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0

    @field_validator("target_pct", mode="before")
    @classmethod
    def _validate_target(cls, v: Any) -> str:
        parsed = _validate_pct(v, field_label="target_pct")
        return str(parsed)

    @field_validator("min_pct", mode="before")
    @classmethod
    def _validate_min(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        parsed = _validate_pct(v, field_label="min_pct")
        return str(parsed)

    @field_validator("max_pct", mode="before")
    @classmethod
    def _validate_max(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        parsed = _validate_pct(v, field_label="max_pct")
        return str(parsed)


class PolicyCapitalBucketResponse(BaseModel):
    """Capital bucket as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: Optional[UUID] = None
    version_id: Optional[UUID] = None
    bucket_name: str
    target_pct: Decimal
    min_pct: Optional[Decimal] = None
    max_pct: Optional[Decimal] = None
    description: Optional[str] = None
    sort_order: int
    created_at: datetime


class PolicyCapitalBucketReplace(BaseModel):
    """Replace all capital buckets for a draft."""

    buckets: list[PolicyCapitalBucketCreate]


# ── Policy Rule ────────────────────────────────────────────────────────


class PolicyRuleCreate(BaseModel):
    """Input for a single policy rule within a draft."""

    rule_type: str
    rule_value: str  # JSON or scalar string
    severity: str = "warning"
    enabled: bool = True
    description: Optional[str] = None
    sort_order: int = 0

    @field_validator("rule_type")
    @classmethod
    def _check_rule_type(cls, v: str) -> str:
        if v not in VALID_RULE_TYPES:
            raise ValueError(
                f"rule_type must be one of {sorted(VALID_RULE_TYPES)}, got: {v!r}"
            )
        return v

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v: str) -> str:
        if v not in VALID_SEVERITIES:
            raise ValueError(
                f"severity must be one of {sorted(VALID_SEVERITIES)}, got: {v!r}"
            )
        return v


class PolicyRuleResponse(BaseModel):
    """Policy rule as returned to consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    draft_id: Optional[UUID] = None
    version_id: Optional[UUID] = None
    rule_type: str
    rule_value: str
    severity: str
    enabled: bool
    description: Optional[str] = None
    sort_order: int
    created_at: datetime


class PolicyRuleReplace(BaseModel):
    """Replace all policy rules for a draft."""

    rules: list[PolicyRuleCreate]
