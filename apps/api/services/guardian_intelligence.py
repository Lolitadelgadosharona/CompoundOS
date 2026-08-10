"""Guardian Intelligence — Sprint 010 Slice B evaluation functions.

Transaction-neutral evaluation functions for 5 new Guardian check types.
These consume Sprint 009 portfolio data (positions, accounts, assets)
and Sprint 009-B policy data (policy_capital_buckets, policy_rules).

All functions are callable from evaluate_core and follow the existing
pattern: accept a CheckInput, return an EvaluationResult.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# ── Default thresholds (used when no policy_rule exists) ────────────

DEFAULT_MAX_SINGLE_POSITION_PCT = Decimal("20")
DEFAULT_MAX_SECTOR_PCT = Decimal("40")
DEFAULT_EXPLORATION_CAPITAL_PCT = Decimal("10")
DEFAULT_STALENESS_HOURS = 24


@dataclass
class PositionRow:
    position_id: UUID
    account_id: UUID
    asset_id: UUID
    market_value: Optional[Decimal]
    quantity: Decimal
    observed_at: datetime
    capital_bucket: str
    sector: Optional[str]
    asset_type: str


@dataclass
class BucketTarget:
    bucket_name: str
    target_pct: Decimal
    min_pct: Optional[Decimal]
    max_pct: Optional[Decimal]


@dataclass
class EvalResult:
    exceeded: bool
    detail: str = ""
    actual_value: Optional[Decimal] = None
    threshold_value: Optional[Decimal] = None
    context: dict | None = None


def _load_positions(
    session: Session, household_id: UUID,
) -> list[PositionRow]:
    """Load all latest positions with account and asset info."""
    rows = session.execute(
        text(
            "SELECT p.id, p.account_id, p.asset_id, p.market_value, p.quantity,"
            " p.observed_at, a.capital_bucket, ast.sector, ast.asset_type"
            " FROM positions p"
            " JOIN accounts a ON p.account_id = a.id"
            " JOIN portfolios pf ON a.portfolio_id = pf.id"
            " JOIN assets ast ON p.asset_id = ast.id"
            " WHERE p.is_latest = TRUE AND pf.household_id = :hid"
        ),
        {"hid": household_id},
    ).fetchall()

    return [
        PositionRow(
            position_id=r[0], account_id=r[1], asset_id=r[2],
            market_value=Decimal(str(r[3])) if r[3] is not None else None,
            quantity=Decimal(str(r[4])),
            observed_at=r[5],
            capital_bucket=r[6], sector=r[7], asset_type=r[8],
        )
        for r in rows
    ]


def _load_bucket_targets(
    session, policy_version_id: str,
) -> list[BucketTarget]:
    """Load capital bucket targets from active policy version."""
    rows = session.execute(
        text(
            "SELECT bucket_name, target_pct, min_pct, max_pct"
            " FROM policy_capital_buckets"
            " WHERE version_id = :vid"
        ),
        {"vid": policy_version_id},
    ).fetchall()
    return [
        BucketTarget(
            bucket_name=r[0],
            target_pct=Decimal(str(r[1])),
            min_pct=Decimal(str(r[2])) if r[2] is not None else None,
            max_pct=Decimal(str(r[3])) if r[3] is not None else None,
        )
        for r in rows
    ]


def _load_policy_rule_threshold(
    session, policy_version_id: str, rule_type: str,
) -> Optional[Decimal]:
    """Load a numeric threshold from policy_rules."""
    row = session.execute(
        text(
            "SELECT rule_value FROM policy_rules"
            " WHERE version_id = :vid AND rule_type = :rtype AND enabled = TRUE"
            " LIMIT 1"
        ),
        {"vid": policy_version_id, "rtype": rule_type},
    ).fetchone()
    if row is None:
        return None
    try:
        return Decimal(str(row[0]))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# Evaluation functions
# ═══════════════════════════════════════════════════════════════════════


def evaluate_capital_bucket_drift(
    session: Session,
    household_id: UUID,
    policy_version_id: str,
) -> list[EvalResult]:
    """Compare actual bucket allocations against policy targets."""
    positions = _load_positions(session, household_id)
    targets = _load_bucket_targets(session, policy_version_id)
    if not targets:
        return []

    total_value = sum(
        (p.market_value or Decimal("0")) for p in positions
    )
    if total_value == 0:
        return []

    # Compute actual bucket values
    bucket_values: dict[str, Decimal] = {}
    for p in positions:
        b = p.capital_bucket
        bucket_values[b] = bucket_values.get(b, Decimal("0")) + (p.market_value or Decimal("0"))

    results: list[EvalResult] = []
    for t in targets:
        actual = bucket_values.get(t.bucket_name, Decimal("0"))
        actual_pct = (actual / total_value * 100).quantize(Decimal("0.01"))

        if t.max_pct is not None and actual_pct > t.max_pct:
            results.append(EvalResult(
                exceeded=True,
                detail=f"Bucket {t.bucket_name}: {actual_pct}% (max {t.max_pct}%)",
                actual_value=actual_pct, threshold_value=t.max_pct,
            ))
        elif t.min_pct is not None and actual_pct < t.min_pct:
            results.append(EvalResult(
                exceeded=True,
                detail=f"Bucket {t.bucket_name}: {actual_pct}% (min {t.min_pct}%)",
                actual_value=actual_pct, threshold_value=t.min_pct,
            ))

    return results


def evaluate_single_position_concentration(
    session: Session,
    household_id: UUID,
    policy_version_id: str,
) -> list[EvalResult]:
    """Detect positions exceeding max_single_position_pct."""
    positions = _load_positions(session, household_id)
    if not positions:
        return []

    total_value = sum(
        (p.market_value or Decimal("0")) for p in positions
    )
    if total_value == 0:
        return []

    threshold = _load_policy_rule_threshold(
        session, policy_version_id, "max_single_position_pct",
    )
    if threshold is None:
        threshold = DEFAULT_MAX_SINGLE_POSITION_PCT

    results: list[EvalResult] = []
    for p in positions:
        mv = p.market_value or Decimal("0")
        pct = (mv / total_value * 100).quantize(Decimal("0.01"))
        if pct > threshold:
            results.append(EvalResult(
                exceeded=True,
                detail=f"Position {p.position_id}: {pct}% (limit {threshold}%)",
                actual_value=pct, threshold_value=threshold,
            ))

    return results


def evaluate_sector_concentration(
    session: Session,
    household_id: UUID,
    policy_version_id: str,
) -> list[EvalResult]:
    """Detect sectors exceeding max_sector_concentration_pct."""
    positions = _load_positions(session, household_id)
    if not positions:
        return []

    total_value = sum(
        (p.market_value or Decimal("0")) for p in positions
    )
    if total_value == 0:
        return []

    threshold = _load_policy_rule_threshold(
        session, policy_version_id, "max_sector_concentration_pct",
    )
    if threshold is None:
        threshold = DEFAULT_MAX_SECTOR_PCT

    sector_values: dict[str, Decimal] = {}
    for p in positions:
        s = p.sector or "Unclassified"
        sector_values[s] = sector_values.get(s, Decimal("0")) + (p.market_value or Decimal("0"))

    results: list[EvalResult] = []
    for sector, value in sector_values.items():
        pct = (value / total_value * 100).quantize(Decimal("0.01"))
        if pct > threshold:
            results.append(EvalResult(
                exceeded=True,
                detail=f"Sector {sector}: {pct}% (limit {threshold}%)",
                actual_value=pct, threshold_value=threshold,
            ))

    return results


def evaluate_exploration_capital_limit(
    session: Session,
    household_id: UUID,
    policy_version_id: str,
) -> list[EvalResult]:
    """Check EXPLORATION bucket against capital limit."""
    positions = _load_positions(session, household_id)
    if not positions:
        return []

    total_value = sum(
        (p.market_value or Decimal("0")) for p in positions
    )
    if total_value == 0:
        return []

    exploration_value = sum(
        (p.market_value or Decimal("0"))
        for p in positions if p.capital_bucket == "EXPLORATION"
    )

    threshold = _load_policy_rule_threshold(
        session, policy_version_id, "exploration_capital_limit",
    )
    if threshold is None:
        threshold = DEFAULT_EXPLORATION_CAPITAL_PCT

    exploration_pct = (exploration_value / total_value * 100).quantize(Decimal("0.01"))
    if exploration_pct > threshold:
        return [EvalResult(
            exceeded=True,
            detail=f"EXPLORATION bucket: {exploration_pct}% (limit {threshold}%)",
            actual_value=exploration_pct, threshold_value=threshold,
        )]

    return []


def evaluate_data_quality_staleness(
    session: Session,
    household_id: UUID,
    staleness_hours: int = DEFAULT_STALENESS_HOURS,
) -> list[EvalResult]:
    """Flag positions with stale observed_at timestamps."""
    positions = _load_positions(session, household_id)
    if not positions:
        return []

    cutoff = datetime.now(timezone.utc)
    from datetime import timedelta
    threshold_dt = cutoff - timedelta(hours=staleness_hours)

    stale = [p for p in positions if p.observed_at < threshold_dt]
    if stale:
        return [EvalResult(
            exceeded=True,
            detail=f"{len(stale)} position(s) with data older than {staleness_hours}h",
            actual_value=Decimal(str(len(stale))),
            threshold_value=Decimal("0"),
        )]

    return []


def has_active_critical_event(session: Session, household_id: UUID) -> bool:
    """Check if household has any unacknowledged critical Guardian events."""
    row = session.execute(
        text(
            "SELECT 1 FROM guardian_events ge"
            " JOIN guardian_check_confirmed cc ON ge.check_version_id = cc.id"
            " WHERE ge.household_id = :hid"
            " AND cc.severity = 'critical'"
            " LIMIT 1"
        ),
        {"hid": household_id},
    ).fetchone()
    return row is not None
