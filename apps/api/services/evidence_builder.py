"""Sprint 006 Slice A — Evidence Packet Builder.

Deterministic extraction of structured facts from CompoundOS entities.
No LLM, no API — pure data queries.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.models import (
    CommitteeEvidenceItem,
    CommitteeSession,
    Decision,
    DecisionConfirmedSnapshot,
    GuardianEvent,
    InvestmentPolicy,
    InvestmentPolicyVersion,
    Portfolio,
    PortfolioSnapshot,
)

# ═══════════════════════════════════════════════════════════════════════════
# Source types
# ═══════════════════════════════════════════════════════════════════════════

SOURCE_PORTFOLIO = "portfolio_snapshot"
SOURCE_POLICY = "policy_version"
SOURCE_GUARDIAN = "guardian_event"
SOURCE_DECISION = "decision"
SOURCE_OWNER = "owner_claim"


# ═══════════════════════════════════════════════════════════════════════════
# Evidence Packet Builder
# ═══════════════════════════════════════════════════════════════════════════


def build_evidence_packet(
    session: Session,
    household_id: UUID,
    committee_session: CommitteeSession,
) -> list[CommitteeEvidenceItem]:
    """Extract evidence items from CompoundOS for a committee session."""
    items: list[CommitteeEvidenceItem] = []

    policy = _latest_published_policy(session, household_id)
    if policy:
        items.append(_policy_evidence(session, policy, committee_session.id))

    snapshot = _latest_portfolio_snapshot(session, household_id)
    if snapshot:
        items.append(_portfolio_evidence(session, snapshot, committee_session.id))

    guardian_items = _guardian_evidence(session, household_id, committee_session.id)
    items.extend(guardian_items)

    decision_items = _decision_evidence(session, household_id, committee_session.id)
    items.extend(decision_items)

    return items


# ═══════════════════════════════════════════════════════════════════════════
# Individual extractors
# ═══════════════════════════════════════════════════════════════════════════


def _latest_published_policy(
    session: Session,
    household_id: UUID,
) -> Optional[InvestmentPolicyVersion]:
    return (
        session.query(InvestmentPolicyVersion)
        .join(
            InvestmentPolicy,
            InvestmentPolicyVersion.policy_id == InvestmentPolicy.id,
        )
        .filter(InvestmentPolicy.household_id == household_id)
        .filter(InvestmentPolicyVersion.status == "published")
        .order_by(InvestmentPolicyVersion.version_number.desc())
        .first()
    )


def _policy_evidence(
    session: Session,
    policy: InvestmentPolicyVersion,
    session_id: UUID,
) -> CommitteeEvidenceItem:
    allocations = session.execute(
        text(
            "SELECT asset_category, target_percentage"
            " FROM investment_policy_version_allocations"
            " WHERE version_id = :vid"
            " ORDER BY sort_order",
        ),
        {"vid": str(policy.id)},
    ).fetchall()
    facts = {
        "objectives": policy.objectives,
        "time_horizon": policy.time_horizon,
        "version_number": policy.version_number,
        "allocations": [dict(row._mapping) for row in allocations],
    }
    return _make_evidence(
        session_id=session_id,
        source_type=SOURCE_POLICY,
        source_id=policy.id,
        title=f"Investment Policy v{policy.version_number}",
        as_of=policy.sealed_at or policy.published_at,
        facts=facts,
        citation=f"Policy v{policy.version_number}",
    )


def _latest_portfolio_snapshot(
    session: Session,
    household_id: UUID,
) -> Optional[PortfolioSnapshot]:
    return (
        session.query(PortfolioSnapshot)
        .join(
            Portfolio,
            PortfolioSnapshot.portfolio_id == Portfolio.id,
        )
        .filter(Portfolio.household_id == household_id)
        .order_by(PortfolioSnapshot.confirmed_at.desc())
        .first()
    )


def _portfolio_evidence(
    session: Session,
    snapshot: PortfolioSnapshot,
    session_id: UUID,
) -> CommitteeEvidenceItem:
    holdings = session.execute(
        text(
            "SELECT category FROM portfolio_snapshot_holdings"
            " WHERE snapshot_id = :sid",
        ),
        {"sid": str(snapshot.id)},
    ).fetchall()
    category_breakdown: dict[str, int] = {}
    for row in holdings:
        cat = row[0] if row[0] else "uncategorized"
        category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
    facts = {
        "confirmed_at": snapshot.confirmed_at.isoformat()
            if snapshot.confirmed_at else None,
        "holdings_count": len(holdings),
        "category_breakdown": category_breakdown,
    }
    return _make_evidence(
        session_id=session_id,
        source_type=SOURCE_PORTFOLIO,
        source_id=snapshot.id,
        title=f"Portfolio Snapshot {snapshot.id}",
        as_of=snapshot.confirmed_at or snapshot.valuation_date,
        facts=facts,
        citation="Portfolio Snapshot §Holdings",
    )


def _guardian_evidence(
    session: Session,
    household_id: UUID,
    session_id: UUID,
) -> list[CommitteeEvidenceItem]:
    events = (
        session.query(GuardianEvent)
        .filter_by(household_id=household_id)
        .order_by(GuardianEvent.detected_at.desc())
        .limit(20)
        .all()
    )
    if not events:
        return []

    checks: dict[UUID, dict] = {}
    for ev in events:
        cid = ev.check_id
        if cid not in checks:
            checks[cid] = {
                "check_type": ev.check_type,
                "total_events": 0,
                "exceeded_count": 0,
                "latest_detected_at": None,
            }
        checks[cid]["total_events"] += 1
        if ev.exceeded:
            checks[cid]["exceeded_count"] += 1
        latest = checks[cid]["latest_detected_at"]
        if latest is None or ev.detected_at > latest:
            checks[cid]["latest_detected_at"] = ev.detected_at

    items: list[CommitteeEvidenceItem] = []
    for cid, summary in checks.items():
        facts = {
            "check_id": str(cid),
            "check_type": summary["check_type"],
            "total_recent_events": summary["total_events"],
            "exceeded_count": summary["exceeded_count"],
            "latest_detected": summary["latest_detected_at"].isoformat()
                if summary["latest_detected_at"] else None,
        }
        items.append(_make_evidence(
            session_id=session_id,
            source_type=SOURCE_GUARDIAN,
            source_id=cid,
            title=f"Guardian: {summary['check_type']}",
            as_of=summary["latest_detected_at"] or datetime.now(timezone.utc),
            facts=facts,
            citation=f"Guardian Check {str(cid)[:8]}",
        ))
    return items


def _decision_evidence(
    session: Session,
    household_id: UUID,
    session_id: UUID,
) -> list[CommitteeEvidenceItem]:
    decisions = (
        session.query(DecisionConfirmedSnapshot)
        .join(
            Decision,
            DecisionConfirmedSnapshot.decision_id == Decision.id,
        )
        .filter(Decision.household_id == household_id)
        .order_by(DecisionConfirmedSnapshot.confirmed_at.desc())
        .limit(10)
        .all()
    )
    if not decisions:
        return []

    items: list[CommitteeEvidenceItem] = []
    for d in decisions:
        facts = {
            "decision_id": str(d.decision_id),
            "decision_date": d.decision_date.isoformat() if d.decision_date else None,
            "confirmed_at": d.confirmed_at.isoformat() if d.confirmed_at else None,
        }
        items.append(_make_evidence(
            session_id=session_id,
            source_type=SOURCE_DECISION,
            source_id=d.decision_id,
            title=f"Decision {str(d.decision_id)[:8]}",
            as_of=d.confirmed_at or datetime.now(timezone.utc),
            facts=facts,
            citation=f"Decision {str(d.decision_id)[:8]}",
        ))
    return items


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_evidence(
    *,
    session_id: UUID,
    source_type: str,
    source_id: Optional[UUID],
    title: str,
    as_of: datetime,
    facts: dict,
    citation: str,
) -> CommitteeEvidenceItem:
    provenance = (
        "compoundos_internal"
        if source_type != SOURCE_OWNER
        else "owner_provided"
    )
    return CommitteeEvidenceItem(
        session_id=session_id,
        source_type=source_type,
        source_id=source_id,
        source_title=title,
        as_of=as_of,
        content_hash=_sha256(_serialize_for_hash(facts)),
        structured_facts=facts,
        provenance=provenance,
        freshness="current",
        confidence="high",
        citation_ref=citation,
    )


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _serialize_for_hash(data: dict) -> str:
    import json
    return json.dumps(data, sort_keys=True, default=str)
