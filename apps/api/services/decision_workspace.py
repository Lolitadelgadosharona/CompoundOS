"""Decision Workspace read-model (PE-004A).

Assembles a single decision's full picture — summary, committee (6
perspectives), and memo summary — as natural-language text. Read-only;
no raw JSON is surfaced. Reuses existing tables only (no migration).
"""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

_RUN_ID_RE = re.compile(r"research_run_id=([0-9a-fA-F-]{36})")


class DecisionWorkspaceNotFoundError(ValueError):
    pass


def _narrative(value) -> str:
    """Flatten a nested memo/perspective value into natural-language text."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("narrative") or value.get("method") or str(value)
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def _impact(value) -> str | None:
    """Flatten a portfolio/guardian impact value, or None when empty.

    Never fabricates: only surfaces data that is actually present.
    """
    if not value:
        return None
    if isinstance(value, dict) and set(value.keys()) == {"compliant"}:
        return f"Policy compliant: {value['compliant']}"
    text = _narrative(value)
    return text or None


def _extract_missing_sources(evidence) -> list[str] | None:
    """Return the missing-source list from the memo's evidence, or None."""
    if isinstance(evidence, dict):
        sources = evidence.get("sources")
        if isinstance(sources, list) and sources:
            return [str(s) for s in sources]
    return None


def _extract_run_id(evidence: str | None) -> UUID | None:
    if not evidence:
        return None
    m = _RUN_ID_RE.search(str(evidence))
    return UUID(m.group(1)) if m else None


def decision_workspace(session: Session, decision_id: UUID) -> dict:
    """Assemble the decision workspace read-model (read-only)."""
    row = session.execute(text(
        "SELECT d.status,"
        " COALESCE(dd.title, s.title) AS title,"
        " COALESCE(dd.evidence_or_sources, s.evidence_or_sources) AS evidence"
        " FROM decisions d"
        " LEFT JOIN decision_drafts dd ON dd.decision_id = d.id"
        " LEFT JOIN decision_confirmed_snapshots s ON s.decision_id = d.id"
        " WHERE d.id = :id"
    ), {"id": decision_id}).fetchone()
    if row is None:
        raise DecisionWorkspaceNotFoundError(str(decision_id))

    status, title, evidence = row
    run_id = _extract_run_id(evidence)

    recommendation = None
    confidence = None
    memo = None
    memo_json = None
    perspectives: list[dict] = []

    if run_id is not None:
        memo_row = session.execute(text(
            "SELECT memo, recommendation, confidence_score"
            " FROM investment_memos WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        if memo_row is not None:
            memo_json = (memo_row[0] if isinstance(memo_row[0], dict)
                         else json.loads(memo_row[0] or "{}"))
            recommendation = memo_row[1]
            confidence = memo_row[2]
            committee = memo_json.get("committee") or {}
            memo = {
                "thesis": _narrative(memo_json.get("thesis")),
                "bull_case": _narrative(memo_json.get("bull_case")),
                "bear_case": _narrative(memo_json.get("bear_case")),
                "risks": memo_json.get("risks") or [],
                "valuation": _narrative(memo_json.get("valuation")),
                "consensus": committee.get("consensus"),
                "disagreements": committee.get("disagreements") or [],
                "portfolio_impact": _impact(memo_json.get("portfolio_impact")),
                "guardian_impact": _impact(memo_json.get("guardian_impact")),
            }

        p_rows = session.execute(text(
            "SELECT perspective, analysis, conviction_score"
            " FROM perspective_analyses WHERE run_id = :rid"
            " ORDER BY started_at, perspective"
        ), {"rid": run_id}).fetchall()
        perspectives = [
            {
                "perspective": r[0],
                "thesis": _narrative((r[1] or {}).get("thesis")),
                "evidence": _narrative((r[1] or {}).get("evidence")),
                "conviction_score": r[2],
            }
            for r in p_rows
        ]

    # Evidence coverage + confidence explanation (derived, read-only).
    evidence_coverage = {
        "total": len(perspectives),
        "with_evidence": sum(1 for p in perspectives if p.get("evidence")),
    }
    contributors = [
        p["perspective"] for p in perspectives
        if p.get("conviction_score") is not None and p["conviction_score"] >= 6
    ]
    reducers = [
        p["perspective"] for p in perspectives
        if p.get("conviction_score") is not None and p["conviction_score"] < 4
    ]
    missing_evidence = (
        _extract_missing_sources(memo_json.get("evidence"))
        if memo_json is not None else None
    )

    return {
        "decision_id": str(decision_id),
        "status": status,
        "title": title,
        "recommendation": recommendation,
        "confidence": confidence,
        "perspectives": perspectives,
        "memo": memo,
        "evidence_coverage": evidence_coverage,
        "missing_evidence": missing_evidence,
        "confidence_explanation": {
            "contributors": contributors,
            "reducers": reducers,
        },
    }
