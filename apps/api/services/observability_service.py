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


def execution_reliability(session: Session) -> dict:
    """Reliability metrics: success/failure/retry rates, latency, and
    failure breakdowns. Read-only SQL aggregation."""
    row = session.execute(
        text(
            "SELECT COUNT(*),"
            " COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0),"
            " COALESCE(SUM(CASE WHEN status IN ('failure','timeout',"
            "  'rate_limited') THEN 1 ELSE 0 END), 0),"
            " COALESCE(SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END), 0),"
            " COALESCE(AVG(duration_ms), 0),"
            " COALESCE(percentile_cont(0.95) WITHIN GROUP"
            "  (ORDER BY duration_ms), 0)"
            " FROM llm_execution_log"
        ),
    ).fetchone()
    total = int(row[0] or 0)
    success = int(row[1] or 0)
    failure = int(row[2] or 0)
    retried = int(row[3] or 0)

    by_status = session.execute(
        text("SELECT status, COUNT(*) FROM llm_execution_log"
             " GROUP BY status ORDER BY COUNT(*) DESC"),
    ).fetchall()
    failure_by_perspective = session.execute(
        text("SELECT COALESCE(perspective, 'unknown'), COUNT(*)"
             " FROM llm_execution_log"
             " WHERE status IN ('failure','timeout','rate_limited')"
             " GROUP BY perspective ORDER BY COUNT(*) DESC"),
    ).fetchall()
    failure_by_model = session.execute(
        text("SELECT COALESCE(model, 'unknown'), COUNT(*)"
             " FROM llm_execution_log"
             " WHERE status IN ('failure','timeout','rate_limited')"
             " GROUP BY model ORDER BY COUNT(*) DESC"),
    ).fetchall()
    recent_errors = session.execute(
        text("SELECT perspective, model, error_message, created_at"
             " FROM llm_execution_log WHERE error_message IS NOT NULL"
             " ORDER BY created_at DESC LIMIT 10"),
    ).fetchall()

    return {
        "total_calls": total,
        "success_rate": round(success / total, 3) if total else 0.0,
        "failure_rate": round(failure / total, 3) if total else 0.0,
        "retry_rate": round(retried / total, 3) if total else 0.0,
        "avg_latency_ms": round(_f(row[4]), 1),
        "p95_latency_ms": round(_f(row[5]), 1),
        "by_status": [
            {"status": r[0], "count": int(r[1] or 0)} for r in by_status
        ],
        "failure_by_perspective": [
            {"perspective": r[0], "failures": int(r[1] or 0)}
            for r in failure_by_perspective
        ],
        "failure_by_model": [
            {"model": r[0], "failures": int(r[1] or 0)}
            for r in failure_by_model
        ],
        "recent_errors": [
            {"perspective": r[0], "model": r[1], "error_message": r[2],
             "created_at": str(r[3]) if r[3] else None}
            for r in recent_errors
        ],
    }


def cost_trend(session: Session, days: int = 14) -> dict:
    """Estimated cost per day over a window + per-run cost trend."""
    rows = session.execute(
        text(
            "SELECT DATE(created_at)::text AS day, COUNT(*) AS calls,"
            " COALESCE(SUM(cost_estimate), 0) AS cost"
            " FROM llm_execution_log"
            " WHERE created_at > NOW() - make_interval(days => :days)"
            " GROUP BY DATE(created_at) ORDER BY day"
        ),
        {"days": max(1, days)},
    ).fetchall()
    return {
        "days": days,
        "daily": [
            {"day": r[0], "calls": int(r[1] or 0),
             "cost": round(_f(r[2]), 6)}
            for r in rows
        ],
        "by_run": cost_by_run(session, 20),
    }
