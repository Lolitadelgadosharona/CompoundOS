"""Dashboard data API — Sprint 015 Slice B.

Thin endpoints that query existing services and return JSON for HTMX
dashboard rendering. No business logic here — all data comes from the
Sprint 011-014 service layer.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.repositories.decisions import get_household_id
from apps.api.services import dashboard_service
from apps.api.services.dashboard_research import DashboardResearchService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard-data"])


@router.get("/summary")
def dashboard_summary(session: Session = Depends(get_session)):
    """Net worth, allocation, pending decisions, guardian alerts."""
    hid = get_household_id(session)
    if hid is None:
        return {"net_worth": "0.00", "pending_decisions": 0,
                "allocation": {}, "guardian_alerts": []}
    snap = dashboard_service.build_dashboard(session, hid)
    return {
        "net_worth": snap.net_worth.total_value,
        "pending_decisions": len(snap.pending_decisions),
        "allocation": dashboard_service.allocation_context(snap.allocation),
        "guardian_alerts": [
            v.description for v in snap.policy_compliance.rule_violations
        ],
        "last_research": dashboard_service.last_research(session),
    }


@router.get("/research/list")
def research_list(session: Session = Depends(get_session)):
    """List recent research runs."""
    return {"requests": DashboardResearchService.list_recent(session)}


@router.get("/decisions/pending")
def pending_decisions(session: Session = Depends(get_session)):
    """Pending owner decisions (journal drafts)."""
    hid = get_household_id(session)
    if hid is None:
        return {"pending": []}
    return {
        "pending": dashboard_service.list_pending_decisions_detail(session, hid),
    }


@router.get("/decisions/history")
def decision_history(session: Session = Depends(get_session)):
    """Past decisions with outcomes."""
    hid = get_household_id(session)
    if hid is None:
        return {"history": []}
    return {"history": dashboard_service.list_decision_history(session, hid)}


@router.get("/learning/metrics")
def learning_metrics(session: Session = Depends(get_session)):
    """Prediction accuracy and perspective performance."""
    return dashboard_service.learning_metrics(session)
