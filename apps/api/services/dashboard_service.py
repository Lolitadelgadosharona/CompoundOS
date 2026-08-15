"""Dashboard service — read-only wealth snapshot aggregation.

Sprint 010 Slice C — Wealth Dashboard.
All data is computed live from existing systems. No caching.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.dashboard_schemas import (
    ActivityFeed,
    ActivityItem,
    Allocation,
    AllocationEntry,
    BucketDrift,
    DashboardSnapshot,
    IdeaSummary,
    NetWorth,
    PendingDecision,
    PolicyCompliance,
    RiskSummary,
    RuleViolation,
)

HIGH_IMPACT_THRESHOLD_PCT = Decimal("5")
ACTIVITY_FEED_LIMIT = 20


def build_dashboard(session: Session, household_id: UUID) -> DashboardSnapshot:
    """Assemble complete dashboard from all existing systems. Read-only."""
    positions = _load_latest_positions(session, household_id)
    cash = _load_latest_cash_balances(session, household_id)
    base_currency = _get_base_currency(session, household_id) or "USD"

    net_worth = _compute_net_worth(
        session, positions, cash, base_currency,
    )
    allocation = _compute_allocation(positions)
    compliance = _compute_compliance(session, positions, household_id)
    risks = _compute_risks(session, household_id)
    pending = _load_pending_decisions(session, household_id)
    ideas = _count_ideas(session, household_id)
    activity = _load_activity_feed(session, household_id)

    return DashboardSnapshot(
        net_worth=net_worth, allocation=allocation,
        policy_compliance=compliance, risks=risks,
        pending_decisions=pending, ideas=ideas,
        recent_activity=activity,
    )


def is_high_impact(
    session: Session, investment_idea_id: Optional[UUID], household_id: UUID,
) -> bool:
    """Determine if a decision is high-impact based on allocation %."""
    if investment_idea_id is None:
        return False
    positions = _load_latest_positions(session, household_id)
    total = sum((p["market_value"] or Decimal("0")) for p in positions)
    if total == 0:
        return False
    row = session.execute(
        text(
            "SELECT proposed_allocation_pct FROM investment_ideas WHERE id = :iid"
        ),
        {"iid": investment_idea_id},
    ).fetchone()
    if row is None or row[0] is None:
        return False
    try:
        pct = Decimal(str(row[0]))
        return pct >= HIGH_IMPACT_THRESHOLD_PCT
    except Exception:
        return False


# ── Private helpers ───────────────────────────────────────────────────


def _load_latest_positions(session: Session, household_id: UUID) -> list[dict]:
    rows = session.execute(
        text(
            "SELECT p.id, p.market_value, p.quantity, a.capital_bucket,"
            " ast.sector, ast.asset_class, ast.currency, ast.name"
            " FROM positions p"
            " JOIN accounts a ON p.account_id = a.id"
            " JOIN portfolios pf ON a.portfolio_id = pf.id"
            " JOIN assets ast ON p.asset_id = ast.id"
            " WHERE pf.household_id = :hid AND p.is_latest = TRUE"
        ),
        {"hid": household_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _load_latest_cash_balances(
    session: Session, household_id: UUID,
) -> list[dict]:
    rows = session.execute(
        text(
            "SELECT cb.amount, cb.currency, a.account_type"
            " FROM cash_balances cb"
            " JOIN accounts a ON cb.account_id = a.id"
            " JOIN portfolios pf ON a.portfolio_id = pf.id"
            " WHERE pf.household_id = :hid AND cb.is_latest = TRUE"
        ),
        {"hid": household_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _get_base_currency(
    session: Session, household_id: UUID,
) -> Optional[str]:
    row = session.execute(
        text(
            "SELECT base_currency FROM household_profiles WHERE id = :hid"
        ),
        {"hid": household_id},
    ).fetchone()
    return row[0] if row else None


def _get_fx_rate(
    session: Session, from_currency: str, to_currency: str,
) -> Optional[Decimal]:
    if from_currency == to_currency:
        return Decimal("1")
    row = session.execute(
        text(
            "SELECT rate FROM fx_rates"
            " WHERE from_currency = :fc AND to_currency = :tc"
            " AND observed_at <= :now"
            " ORDER BY observed_at DESC LIMIT 1"
        ),
        {"fc": from_currency, "tc": to_currency, "now": datetime.now(timezone.utc)},
    ).fetchone()
    return Decimal(str(row[0])) if row else None


def _compute_net_worth(
    session: Session,
    positions: list[dict],
    cash: list[dict],
    base_currency: str,
) -> NetWorth:
    by_currency: dict[str, Decimal] = {}
    by_account_type: dict[str, Decimal] = {}
    unconverted: list[str] = []

    for p in positions:
        ccy = p.get("currency") or "USD"
        mv = p.get("market_value") or Decimal("0")
        by_currency[ccy] = by_currency.get(ccy, Decimal("0")) + mv
        atype = p.get("capital_bucket") or "Other"
        try:
            rate = _get_fx_rate(session, ccy, base_currency)
            if rate is not None:
                by_account_type[atype] = (
                    by_account_type.get(atype, Decimal("0"))
                    + mv * rate
                )
            else:
                unconverted.append(ccy)
        except Exception:
            unconverted.append(ccy)

    for cb in cash:
        ccy = cb.get("currency") or "USD"
        amt = cb.get("amount") or Decimal("0")
        by_currency[ccy] = by_currency.get(ccy, Decimal("0")) + amt
        atype = cb.get("account_type") or "Unknown"
        try:
            rate = _get_fx_rate(session, ccy, base_currency)
            if rate is not None:
                by_account_type[atype] = (
                    by_account_type.get(atype, Decimal("0"))
                    + amt * rate
                )
        except Exception:
            pass

    total = sum(by_account_type.values())
    if total == 0:
        return NetWorth(
            total_value="0.00",
            by_currency={k: str(v.quantize(Decimal("0.01")))
                         for k, v in by_currency.items()} if by_currency else {},
            by_account_type={},
            unconverted_currencies=sorted(set(unconverted)),
            as_of=datetime.now(timezone.utc),
        )

    return NetWorth(
        total_value=str(Decimal(total).quantize(Decimal("0.01"))),
        by_currency={k: str(v.quantize(Decimal("0.01")))
                     for k, v in by_currency.items()},
        by_account_type={k: str(v.quantize(Decimal("0.01")))
                        for k, v in by_account_type.items()},
        unconverted_currencies=sorted(set(unconverted)),
        as_of=datetime.now(timezone.utc),
    )


def _compute_allocation(positions: list[dict]) -> Allocation:
    total = sum(
        (p.get("market_value") or Decimal("0")) for p in positions
    )
    if total == 0:
        return Allocation()

    by_class: dict[str, Decimal] = {}
    by_bucket: dict[str, Decimal] = {}
    by_ccy: dict[str, Decimal] = {}

    for p in positions:
        mv = p.get("market_value") or Decimal("0")
        cls = p.get("asset_class") or "Unclassified"
        bucket = p.get("capital_bucket") or "Unknown"
        ccy = p.get("currency") or "USD"

        by_class[cls] = by_class.get(cls, Decimal("0")) + mv
        by_bucket[bucket] = by_bucket.get(bucket, Decimal("0")) + mv
        by_ccy[ccy] = by_ccy.get(ccy, Decimal("0")) + mv

    def _pct(v: Decimal) -> str:
        return str(((v / total) * 100).quantize(Decimal("0.01")))

    return Allocation(
        by_asset_class={
            k: AllocationEntry(
                value=str(v.quantize(Decimal("0.01"))),
                percentage=_pct(v),
            )
            for k, v in sorted(by_class.items())
        },
        by_bucket={
            k: AllocationEntry(
                value=str(v.quantize(Decimal("0.01"))),
                percentage=_pct(v),
            )
            for k, v in sorted(by_bucket.items())
        },
        by_currency={
            k: AllocationEntry(
                value=str(v.quantize(Decimal("0.01"))),
                percentage=_pct(v),
            )
            for k, v in sorted(by_ccy.items())
        },
    )


def _compute_compliance(
    session: Session, positions: list[dict], household_id: UUID,
) -> PolicyCompliance:
    drifts: list[BucketDrift] = []
    violations: list[RuleViolation] = []

    # Get active policy version
    prow = session.execute(
        text(
            "SELECT pv.id FROM investment_policy_versions pv"
            " JOIN investment_policies p ON p.id = pv.policy_id"
            " WHERE p.household_id = :hid"
            " AND pv.status = 'published' AND pv.superseded_at IS NULL"
        ),
        {"hid": household_id},
    ).fetchone()

    if prow is None:
        return PolicyCompliance(overall_status="compliant")

    version_id = str(prow[0])
    buckets = session.execute(
        text(
            "SELECT bucket_name, target_pct, min_pct, max_pct"
            " FROM policy_capital_buckets WHERE version_id = :vid"
        ),
        {"vid": version_id},
    ).fetchall()

    total = sum(
        (p.get("market_value") or Decimal("0")) for p in positions
    )
    if total > 0:
        bucket_actual: dict[str, Decimal] = {}
        for p in positions:
            b = p.get("capital_bucket") or "Unknown"
            bucket_actual[b] = (
                bucket_actual.get(b, Decimal("0"))
                + (p.get("market_value") or Decimal("0"))
            )

        for b in buckets:
            name = b[0]
            actual = bucket_actual.get(name, Decimal("0"))
            actual_pct = (actual / total * 100).quantize(Decimal("0.01"))
            max_pct = Decimal(str(b[3])) if b[3] is not None else None
            min_pct = Decimal(str(b[2])) if b[2] is not None else None

            severity = "info"
            drift = Decimal("0")
            if max_pct is not None and actual_pct > max_pct:
                severity = "warning"
                drift = actual_pct - max_pct
            elif min_pct is not None and actual_pct < min_pct:
                severity = "warning"
                drift = min_pct - actual_pct

            drifts.append(BucketDrift(
                bucket_name=name,
                target_pct=str(Decimal(str(b[1]))),
                actual_pct=str(actual_pct),
                drift_pct=str(drift),
                severity=severity,
            ))

    # Guardian events
    events = session.execute(
        text(
            "SELECT ge.check_type, ge.detected_at, cc.severity"
            " FROM guardian_events ge"
            " JOIN guardian_check_confirmed cc"
            "   ON ge.check_version_id = cc.id"
            " WHERE ge.household_id = :hid"
            " AND ge.as_of_date >= CURRENT_DATE - 7"
            " ORDER BY ge.detected_at DESC"
        ),
        {"hid": household_id},
    ).fetchall()

    for e in events:
        violations.append(RuleViolation(
            rule_type=e[0],
            description=f"Guardian: {e[0]}",
            severity=e[2] or "warning",
            detected_at=e[1],
        ))

    has_critical = any(v.severity == "critical" for v in violations)
    has_warning = any(v.severity == "warning" for v in violations)
    has_drift = any(d.severity == "warning" for d in drifts)

    if has_critical:
        overall = "breach"
    elif has_warning or has_drift:
        overall = "warning"
    else:
        overall = "compliant"

    return PolicyCompliance(
        overall_status=overall,
        bucket_drifts=drifts,
        rule_violations=violations,
    )


def _compute_risks(
    session: Session, household_id: UUID,
) -> RiskSummary:
    events = session.execute(
        text(
            "SELECT ge.detected_at FROM guardian_events ge"
            " JOIN guardian_check_confirmed cc"
            "   ON ge.check_version_id = cc.id"
            " WHERE ge.household_id = :hid AND cc.severity = 'critical'"
            " ORDER BY ge.detected_at DESC LIMIT 1"
        ),
        {"hid": household_id},
    ).fetchone()

    active = session.execute(
        text(
            "SELECT COUNT(*) FROM guardian_events ge"
            " JOIN guardian_check_confirmed cc"
            "   ON ge.check_version_id = cc.id"
            " WHERE ge.household_id = :hid"
            " AND ge.as_of_date >= CURRENT_DATE - 7"
        ),
        {"hid": household_id},
    ).scalar()

    # Concentration risk: max position % of total
    positions = _load_latest_positions(session, household_id)
    total = sum((p.get("market_value") or Decimal("0")) for p in positions)
    max_pct = Decimal("0")
    if total > 0:
        for p in positions:
            pct = ((p.get("market_value") or Decimal("0")) / total) * 100
            if pct > max_pct:
                max_pct = pct

    if max_pct > 40:
        conc_risk = "critical"
    elif max_pct > 25:
        conc_risk = "high"
    elif max_pct > 15:
        conc_risk = "medium"
    else:
        conc_risk = "low"

    return RiskSummary(
        concentration_risk=conc_risk,
        active_guardian_events=active or 0,
        newest_guardian_event_at=events[0] if events else None,
    )


def _load_pending_decisions(
    session: Session, household_id: UUID,
) -> list[PendingDecision]:
    rows = session.execute(
        text(
            "SELECT d.id, d.status, d.created_at, dd.title"
            " FROM decisions d"
            " LEFT JOIN decision_drafts dd ON dd.decision_id = d.id"
            " WHERE d.household_id = :hid AND d.status = 'draft'"
            " ORDER BY d.created_at DESC LIMIT 5"
        ),
        {"hid": household_id},
    ).fetchall()
    return [
        PendingDecision(
            decision_id=r[0], status=r[1], created_at=r[2],
            title=r[3] or "Untitled",
        )
        for r in rows
    ]


def _count_ideas(session: Session, household_id: UUID) -> IdeaSummary:
    rows = session.execute(
        text(
            "SELECT status, COUNT(*) FROM investment_ideas"
            " WHERE household_id = :hid GROUP BY status"
        ),
        {"hid": household_id},
    ).fetchall()
    counts = {r[0]: r[1] for r in rows}
    return IdeaSummary(
        total=sum(counts.values()),
        draft=counts.get("draft", 0),
        under_review=counts.get("under_review", 0),
        approved=counts.get("approved", 0),
        rejected=counts.get("rejected", 0),
    )


def _load_activity_feed(
    session: Session, household_id: UUID,
) -> ActivityFeed:
    items: list[ActivityItem] = []

    # Recent positions
    pos_rows = session.execute(
        text(
            "SELECT p.observed_at, ast.name, p.quantity"
            " FROM positions p"
            " JOIN accounts a ON p.account_id = a.id"
            " JOIN portfolios pf ON a.portfolio_id = pf.id"
            " JOIN assets ast ON p.asset_id = ast.id"
            " WHERE pf.household_id = :hid AND p.is_latest = TRUE"
            " ORDER BY p.observed_at DESC LIMIT :lim"
        ),
        {"hid": household_id, "lim": ACTIVITY_FEED_LIMIT},
    ).fetchall()
    for r in pos_rows:
        items.append(ActivityItem(
            type="position_import",
            title=f"Position: {r[1]}",
            description=f"{r[2]} shares",
            occurred_at=r[0],
        ))

    # Recent guardian events
    ge_rows = session.execute(
        text(
            "SELECT ge.check_type, ge.detected_at FROM guardian_events ge"
            " WHERE ge.household_id = :hid"
            " ORDER BY ge.detected_at DESC LIMIT :lim"
        ),
        {"hid": household_id, "lim": ACTIVITY_FEED_LIMIT},
    ).fetchall()
    for r in ge_rows:
        items.append(ActivityItem(
            type="guardian_event",
            title=f"Guardian: {r[0]}",
            description="Guardian event detected",
            occurred_at=r[1],
        ))

    # Sort by time desc, truncate
    items.sort(key=lambda i: i.occurred_at, reverse=True)
    return ActivityFeed(items=items[:ACTIVITY_FEED_LIMIT])


# ── M5-005: read-only display helpers ────────────────────────────────────
#
# These surface the M5-004 lifecycle (memo → decision → learning) through
# the dashboard templates. Read-only; no business logic duplicated.


def _parse_run_id(source: Optional[str]) -> Optional[UUID]:
    if not source:
        return None
    marker = "research_run_id="
    if marker in source:
        try:
            return UUID(source.split(marker, 1)[1].strip())
        except ValueError:
            return None
    return None


def _memo_text(value) -> str:
    """Coerce a memo JSON fragment into a display string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ", ".join(str(x) for x in value)
    if isinstance(value, dict):
        if "narrative" in value:
            return str(value["narrative"])
        if "compliant" in value:
            return ("No policy violations detected."
                    if value["compliant"] else "Policy violations detected.")
        return json.dumps(value)
    return str(value)


def list_memo(session: Session, memo_id: UUID) -> Optional[dict]:
    """Read a single investment memo for the memo page."""
    row = session.execute(
        text(
            "SELECT memo, confidence_score, confidence_level, recommendation"
            " FROM investment_memos WHERE id = :id"
        ),
        {"id": memo_id},
    ).fetchone()
    if row is None:
        return None
    memo = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return {
        "memo_id": str(memo_id),
        "thesis": _memo_text(memo.get("thesis")),
        "evidence": _memo_text(memo.get("evidence")),
        "bull_case": _memo_text(memo.get("bull_case")),
        "bear_case": _memo_text(memo.get("bear_case")),
        "risks": _memo_text(memo.get("risks")),
        "valuation": _memo_text(memo.get("valuation")),
        "portfolio_impact": _memo_text(memo.get("portfolio_impact")),
        "guardian_impact": _memo_text(memo.get("guardian_impact")),
        "confidence": row[1],
        "confidence_level": row[2],
        "recommendation": row[3],
    }


def _memo_summary(session: Session, run_id: Optional[UUID]) -> tuple:
    """Return (recommendation, confidence, memo_id) for a run, if any."""
    if run_id is None:
        return ("—", None, None)
    row = session.execute(
        text(
            "SELECT id, recommendation, confidence_score"
            " FROM investment_memos WHERE run_id = :rid"
        ),
        {"rid": run_id},
    ).fetchone()
    if row is None:
        return ("—", None, None)
    return (row[1] or "—", row[2], str(row[0]))


def list_pending_decisions_detail(session: Session,
                                  household_id: UUID) -> list[dict]:
    """Pending (draft) decisions with memo summary for the decisions page."""
    rows = session.execute(
        text(
            "SELECT d.id, dd.title, dd.evidence_or_sources"
            " FROM decisions d"
            " JOIN decision_drafts dd ON dd.decision_id = d.id"
            " WHERE d.household_id = :hid AND d.status = 'draft'"
            " ORDER BY d.created_at DESC"
        ),
        {"hid": household_id},
    ).fetchall()
    result = []
    for r in rows:
        title = r[1] or "Untitled"
        symbol = title.replace(" investment decision", "").strip() or "?"
        recommendation, confidence, memo_id = _memo_summary(
            session, _parse_run_id(r[2]),
        )
        result.append({
            "decision_id": str(r[0]),
            "symbol": symbol,
            "recommendation": recommendation,
            "confidence": confidence,
            "memo_id": memo_id,
        })
    return result


def list_decision_history(session: Session, household_id: UUID) -> list[dict]:
    """Confirmed/archived decisions for the decisions page history table."""
    rows = session.execute(
        text(
            "SELECT s.title, s.decision_summary, s.confirmed_at"
            " FROM decisions d"
            " JOIN decision_confirmed_snapshots s ON s.decision_id = d.id"
            " WHERE d.household_id = :hid"
            "   AND d.status IN ('confirmed', 'archived')"
            " ORDER BY s.confirmed_at DESC"
        ),
        {"hid": household_id},
    ).fetchall()
    result = []
    for r in rows:
        title = r[0] or "Untitled"
        symbol = title.replace(" investment decision", "").strip() or "?"
        result.append({
            "symbol": symbol,
            "decision": r[1] or title,
            "date": str(r[2])[:10] if r[2] else None,
            "outcome": None,
        })
    return result


def learning_metrics(session: Session) -> dict:
    """Learning page metrics from decision_reviews + knowledge memory."""
    review_count = session.execute(
        text("SELECT COUNT(*) FROM decision_reviews"),
    ).scalar() or 0
    completed = session.execute(
        text("SELECT COUNT(*) FROM decision_reviews"
             " WHERE completed_at IS NOT NULL"),
    ).scalar() or 0

    # Best-effort prediction accuracy from knowledge memory.
    rows = session.execute(
        text(
            "SELECT prediction_accuracy FROM investment_knowledge_memory"
            " WHERE prediction_accuracy IS NOT NULL"
        ),
    ).fetchall()
    errors = []
    for r in rows:
        try:
            data = r[0] if isinstance(r[0], dict) else json.loads(r[0])
            if data and "error" in data:
                errors.append(abs(float(data["error"])))
        except (ValueError, TypeError):
            continue
    accuracy = 0.0
    if errors:
        avg_err = sum(errors) / len(errors)
        accuracy = max(0.0, min(1.0, 1.0 - avg_err / 100.0))

    perspectives = [
        {"name": n, "accuracy": 0.0}
        for n in ("Value", "Growth", "Risk", "Macro", "Policy", "Portfolio Fit")
    ]
    return {
        "accuracy": round(accuracy, 2),
        "review_count": review_count,
        "completed_reviews": completed,
        "perspectives": perspectives,
    }


def allocation_context(allocation) -> dict:
    """Map DashboardSnapshot.allocation → the dashboard template's 3-card
    equities/bonds/cash shape (best-effort from asset classes)."""
    result = {"equities": 0.0, "bonds": 0.0, "cash": 0.0}
    for cls, entry in allocation.by_asset_class.items():
        try:
            pct = float(entry.percentage)
        except (ValueError, TypeError):
            pct = 0.0
        low = (cls or "").lower()
        if "equit" in low or "stock" in low:
            result["equities"] += pct
        elif "bond" in low or "fixed" in low:
            result["bonds"] += pct
        elif "cash" in low or "money" in low:
            result["cash"] += pct
    return result


def last_research(session: Session) -> str:
    """Latest research headline (symbol + rec + confidence + timestamp)."""
    row = session.execute(
        text(
            "SELECT m.confidence_score, m.recommendation, m.generated_at,"
            " i.title"
            " FROM investment_memos m"
            " LEFT JOIN research_runs r ON r.id = m.run_id"
            " LEFT JOIN research_requests rq ON rq.id = r.request_id"
            " LEFT JOIN committee_review_requests cr"
            "   ON cr.id = rq.review_request_id"
            " LEFT JOIN investment_ideas i ON i.id = cr.investment_idea_id"
            " ORDER BY m.generated_at DESC LIMIT 1"
        ),
    ).fetchone()
    if row is None:
        return "No research yet"
    symbol = (row[3] or "").replace("Research: ", "").strip() or "?"
    ts = row[2].strftime("%Y-%m-%d %H:%M") if row[2] else ""
    return f"{symbol}: {row[1] or '—'} (confidence {row[0]}, {ts})"

