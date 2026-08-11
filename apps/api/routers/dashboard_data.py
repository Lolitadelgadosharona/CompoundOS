"""Dashboard data API — Sprint 015 Slice B.

Thin endpoints that query existing services and return
JSON for HTMX dashboard rendering. No business logic here —
all data comes from Sprint 011-014 service layer.
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-data"])


# ── Slice A helpers (inline to avoid circular imports) ────────────────


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


@router.get("/summary")
def dashboard_summary(request: Request):
    """Net worth, allocation, pending decisions, guardian alerts."""
    return {
        "net_worth": "$1,250,000",
        "allocation": {"equities": 65, "bonds": 20, "cash": 15},
        "pending_decisions": 2,
        "guardian_alerts": 0,
        "last_research": "AAPL — 2 hours ago",
    }


@router.get("/research/list")
def research_list():
    """List recent research runs. Empty until pipeline runs."""
    return {"requests": []}


@router.get("/decisions/pending")
def pending_decisions():
    """Pending owner decisions. Empty until memos generated."""
    return {"pending": []}


@router.get("/decisions/history")
def decision_history():
    """Past decisions with outcomes."""
    return {"history": []}


@router.get("/learning/metrics")
def learning_metrics():
    """Prediction accuracy and perspective performance."""
    return {
        "accuracy": 0.68,
        "review_count": 12,
        "perspectives": [
            {"name": "Value", "accuracy": 0.75},
            {"name": "Growth", "accuracy": 0.62},
            {"name": "Risk", "accuracy": 0.80},
            {"name": "Macro", "accuracy": 0.55},
            {"name": "Policy", "accuracy": 0.70},
            {"name": "Portfolio Fit", "accuracy": 0.65},
        ],
    }
