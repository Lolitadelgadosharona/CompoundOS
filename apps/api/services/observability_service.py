"""Production observability — AI execution + LLM cost visibility (M6-001).

Read-only aggregations over llm_execution_log. No mutation, no external
calls. Cost is treated as an ESTIMATE (cost_estimate is advisory).
NULL tokens/cost are coalesced to 0.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

# Failure-like statuses (anything that did not produce a usable result).
_FAILURE_STATUSES = ("failure", "timeout", "rate_limited")


def _f(value) -> float:
    """Coerce a possibly-None/Decimal value to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def list_executions(session: Session, limit: int = 50) -> list[dict]:
    """Most recent LLM executions (newest first)."""
    rows = session.execute(
        text(
            "SELECT id, run_id, perspective, model, model_version,"
            " input_tokens, output_tokens, cost_estimate, cost_currency,"
            " retry_count, status, duration_ms, error_message, created_at"
            " FROM llm_execution_log"
            " ORDER BY created_at DESC, id DESC LIMIT :limit"
        ),
        {"limit": max(1, min(limit, 500))},
    ).fetchall()
    return [
        {
            "id": str(r[0]),
            "run_id": str(r[1]) if r[1] else None,
            "perspective": r[2],
            "model": r[3],
            "model_version": r[4],
            "input_tokens": r[5] or 0,
            "output_tokens": r[6] or 0,
            "cost_estimate": _f(r[7]),
            "cost_currency": r[8] or "USD",
            "retry_count": r[9] or 0,
            "status": r[10],
            "duration_ms": r[11] or 0,
            "error_message": r[12],
            "created_at": str(r[13]) if r[13] else None,
        }
        for r in rows
    ]


def execution_summary(session: Session) -> dict:
    """Aggregate AI execution totals (calls, tokens, cost, duration)."""
    row = session.execute(
        text(
            "SELECT COUNT(*) AS total_calls,"
            " COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0),"
            " COALESCE(SUM(CASE WHEN status IN ('failure','timeout',"
            "  'rate_limited') THEN 1 ELSE 0 END), 0),"
            " COALESCE(SUM(input_tokens), 0),"
            " COALESCE(SUM(output_tokens), 0),"
            " COALESCE(SUM(cost_estimate), 0),"
            " COALESCE(AVG(duration_ms), 0)"
            " FROM llm_execution_log"
        ),
    ).fetchone()
    return {
        "total_calls": int(row[0] or 0),
        "success": int(row[1] or 0),
        "failure": int(row[2] or 0),
        "total_input_tokens": int(row[3] or 0),
        "total_output_tokens": int(row[4] or 0),
        "total_cost": round(_f(row[5]), 6),
        "avg_duration_ms": round(_f(row[6]), 1),
    }


def cost_by_perspective(session: Session) -> list[dict]:
    """Estimated cost + call counts grouped by perspective."""
    rows = session.execute(
        text(
            "SELECT COALESCE(perspective, 'unknown') AS perspective,"
            " COUNT(*) AS calls,"
            " COALESCE(SUM(cost_estimate), 0) AS total_cost,"
            " COALESCE(SUM(input_tokens), 0) AS input_tokens,"
            " COALESCE(SUM(output_tokens), 0) AS output_tokens"
            " FROM llm_execution_log"
            " GROUP BY perspective ORDER BY total_cost DESC"
        ),
    ).fetchall()
    return [
        {
            "perspective": r[0],
            "calls": int(r[1] or 0),
            "total_cost": round(_f(r[2]), 6),
            "input_tokens": int(r[3] or 0),
            "output_tokens": int(r[4] or 0),
        }
        for r in rows
    ]


def cost_by_run(session: Session, limit: int = 20) -> list[dict]:
    """Estimated cost grouped by research run (newest first)."""
    rows = session.execute(
        text(
            "SELECT run_id, COUNT(*) AS calls,"
            " COALESCE(SUM(cost_estimate), 0) AS total_cost,"
            " MAX(created_at) AS latest_at"
            " FROM llm_execution_log WHERE run_id IS NOT NULL"
            " GROUP BY run_id ORDER BY latest_at DESC LIMIT :limit"
        ),
        {"limit": max(1, min(limit, 100))},
    ).fetchall()
    return [
        {
            "run_id": str(r[0]),
            "calls": int(r[1] or 0),
            "total_cost": round(_f(r[2]), 6),
            "latest_at": str(r[3]) if r[3] else None,
        }
        for r in rows
    ]


def cost_breakdown(session: Session, run_limit: int = 20) -> dict:
    """Combined cost view: total + per-perspective + per-run."""
    return {
        "total_cost": execution_summary(session)["total_cost"],
        "by_perspective": cost_by_perspective(session),
        "by_run": cost_by_run(session, run_limit),
    }
