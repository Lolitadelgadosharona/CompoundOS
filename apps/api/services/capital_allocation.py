"""Capital Allocation service (PE-003B.1) — read-only policy-vs-reality drift.

Combines the published Investment Policy's capital buckets (target/min/max)
with the Portfolio Reality (positions + cash grouped by account
capital_bucket) to compute current % and drift per bucket.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.repositories.households import get_current_household
from apps.api.repositories.policy_enrichment import list_version_buckets
from apps.api.repositories.portfolios import get_portfolio
from apps.api.services.policies import (
    PolicyNotFoundError,
    PublishedVersionNotFoundError,
    read_current_published,
)


def capital_allocation(session: Session) -> dict:
    """Return per-bucket target/current/drift (read-only, no fabrication)."""
    try:
        version, _ = read_current_published(session)
    except (PolicyNotFoundError, PublishedVersionNotFoundError):
        return {"buckets": [], "policy_status": "none"}

    buckets = list_version_buckets(session, version.id)
    if not buckets:
        return {"buckets": [], "policy_status": "no_buckets"}

    # Reality: positions + cash grouped by account capital_bucket.
    bucket_values: dict[str, Decimal] = {}
    household = get_current_household(session)
    if household is not None:
        portfolio = get_portfolio(session, household.id)
        if portfolio is not None:
            rows = session.execute(text(
                "SELECT a.capital_bucket,"
                " COALESCE(SUM(p.market_value), 0)"
                " + COALESCE(SUM(cb.amount), 0)"
                " FROM accounts a"
                " LEFT JOIN positions p"
                "   ON p.account_id = a.id AND p.is_latest = TRUE"
                " LEFT JOIN cash_balances cb"
                "   ON cb.account_id = a.id AND cb.is_latest = TRUE"
                " WHERE a.portfolio_id = :pid"
                " GROUP BY a.capital_bucket"
            ), {"pid": portfolio.id}).fetchall()
            bucket_values = {r[0]: r[1] or Decimal("0") for r in rows}

    total = sum(bucket_values.values(), Decimal("0"))

    result = []
    for b in buckets:
        value = bucket_values.get(b.bucket_name, Decimal("0"))
        current_pct = (float(value / total * 100)) if total else 0.0
        target_pct = float(b.target_pct)
        result.append({
            "name": b.bucket_name,
            "target_pct": target_pct,
            "min_pct": float(b.min_pct) if b.min_pct is not None else None,
            "max_pct": float(b.max_pct) if b.max_pct is not None else None,
            "current_pct": round(current_pct, 2),
            "drift_pct": round(current_pct - target_pct, 2),
        })

    return {
        "buckets": result,
        "policy_status": "published",
        "version_number": version.version_number,
        "total_value": (
            str(total.quantize(Decimal("0.01"))) if total else None
        ),
    }
