"""Pure evaluation functions — no database access, no ORM, no Session."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Optional, Sequence

# ---------------------------------------------------------------------------
# Input / output DTOs — no ORM, no Session
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckInput:
    check_id: str
    check_version_id: str
    check_type: str  # drift | category_exposure | staleness
    threshold_value: Decimal
    severity: str
    target_category_norm: Optional[str] = None
    target_holding_category_norm: Optional[str] = None
    staleness_days: Optional[int] = None


@dataclass(frozen=True)
class PolicyAllocation:
    asset_class_name: str
    normalized_name: str
    target_percentage: Decimal


@dataclass(frozen=True)
class PortfolioHolding:
    asset_category: str
    total_value: Decimal


@dataclass(frozen=True)
class SnapshotInfo:
    snapshot_id: str
    valuation_date: date


@dataclass(frozen=True)
class EvaluationInput:
    check: CheckInput
    policy_version_id: str
    allocations: Sequence[PolicyAllocation]
    portfolio_snapshot_id: str
    holdings: Sequence[PortfolioHolding]
    snapshot_valuation_date: date
    as_of_date: date


@dataclass(frozen=True)
class EvaluationResult:
    exceeded: bool
    drift_pp: Optional[Decimal] = None
    exposure_pct: Optional[Decimal] = None
    staleness_days_actual: Optional[int] = None


# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()


# ---------------------------------------------------------------------------
# Category map builder (pure)
# ---------------------------------------------------------------------------


def build_category_map(
    holdings: Sequence[PortfolioHolding],
) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for h in holdings:
        key = _norm(h.asset_category)
        result[key] = result.get(key, Decimal("0")) + h.total_value
    return result


def compute_total_value(holdings: Sequence[PortfolioHolding]) -> Decimal:
    return sum((h.total_value for h in holdings), Decimal("0"))


# ---------------------------------------------------------------------------
# Drift evaluation
# ---------------------------------------------------------------------------


def evaluate_drift(
    check: CheckInput,
    allocations: Sequence[PolicyAllocation],
    category_map: dict[str, Decimal],
    total_value: Decimal,
) -> EvaluationResult:
    """abs(actual_pp - target_pp). Strict > threshold. ROUND_HALF_EVEN."""
    if check.target_category_norm is None or check.target_holding_category_norm is None:
        return EvaluationResult(exceeded=False)

    target_pct: Optional[Decimal] = None
    target_norm = _norm(check.target_category_norm)
    for a in allocations:
        if _norm(a.asset_class_name) == target_norm:
            target_pct = a.target_percentage
            break

    if target_pct is None:
        return EvaluationResult(exceeded=False)

    holding_norm = _norm(check.target_holding_category_norm)
    cat_value = category_map.get(holding_norm, Decimal("0"))

    actual_pct: Decimal
    if total_value == Decimal("0"):
        return EvaluationResult(exceeded=False)
    actual_pct = (cat_value / total_value * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )

    drift_pp = abs(actual_pct - target_pct).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )

    if drift_pp <= check.threshold_value:
        return EvaluationResult(exceeded=False, drift_pp=drift_pp)

    return EvaluationResult(exceeded=True, drift_pp=drift_pp)


# ---------------------------------------------------------------------------
# Category exposure evaluation
# ---------------------------------------------------------------------------


def evaluate_category_exposure(
    check: CheckInput,
    category_map: dict[str, Decimal],
    total_value: Decimal,
) -> EvaluationResult:
    """category_pct > threshold. No Policy allocations needed."""
    if check.target_holding_category_norm is None:
        return EvaluationResult(exceeded=False)

    holding_norm = _norm(check.target_holding_category_norm)
    cat_value = category_map.get(holding_norm, Decimal("0"))

    if total_value == Decimal("0"):
        return EvaluationResult(exceeded=False)

    actual_pct = (cat_value / total_value * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    )

    if actual_pct <= check.threshold_value:
        return EvaluationResult(exceeded=False, exposure_pct=actual_pct)

    return EvaluationResult(exceeded=True, exposure_pct=actual_pct)


# ---------------------------------------------------------------------------
# Staleness evaluation
# ---------------------------------------------------------------------------


def evaluate_staleness(
    check: CheckInput,
    snapshot_valuation_date: date,
    as_of_date: date,
) -> EvaluationResult:
    """days_since_valuation > staleness_days. Calendar day subtraction."""
    if check.staleness_days is None:
        return EvaluationResult(exceeded=False)

    delta_days = (as_of_date - snapshot_valuation_date).days

    if delta_days <= check.staleness_days:
        return EvaluationResult(exceeded=False, staleness_days_actual=delta_days)

    return EvaluationResult(exceeded=True, staleness_days_actual=delta_days)
