"""Dashboard web routes — Sprint 014 Slice B.

HTMX + Jinja2 + Pico.css family office dashboard.
Reads existing services — no duplicate business logic.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.repositories.decisions import get_household_id
from apps.api.services import dashboard_service, portfolio_reality
from apps.api.services.dashboard_research import DashboardResearchService

router = APIRouter(prefix="", tags=["dashboard"])
templates = Jinja2Templates(directory="apps/api/templates")


def _household(session: Session) -> UUID:
    hid = get_household_id(session)
    if hid is None:
        raise HTTPException(404, "Household profile not found")
    return hid


def _runtime_health(session: Session):
    """Lightweight runtime health (provider presence + AI execution).

    Deliberately does NOT run the full check suite (no backup/worker/
    launchd/etc.) — only the cheap, dashboard-relevant checks.
    """
    from datetime import datetime, timezone

    from apps.api.services.health_service import (
        check_ai_execution,
        check_providers,
    )

    now = datetime.now(timezone.utc)
    return check_providers(now), check_ai_execution(session, now)


def _policy_published(session: Session) -> bool:
    """True when a published investment policy version exists (PE-003)."""
    from apps.api.repositories.households import get_current_household
    from apps.api.repositories.policies import (
        get_current_published,
        get_policy,
    )

    household = get_current_household(session)
    if household is None:
        return False
    policy = get_policy(session, household.id)
    if policy is None:
        return False
    return get_current_published(session, policy.id) is not None


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request,
                    session: Session = Depends(get_session)):
    hid = _household(session)
    snap = dashboard_service.build_dashboard(session, hid)
    providers, ai_health = _runtime_health(session)
    return templates.TemplateResponse(request, "dashboard.html", {
        "net_worth": f"${snap.net_worth.total_value}",
        "cash_position": dashboard_service.cash_position(session, hid),
        "allocation": dashboard_service.allocation_context(snap.allocation),
        "pending_decisions": dashboard_service.list_pending_decisions_detail(
            session, hid),
        "guardian_alerts": [
            v.description for v in snap.policy_compliance.rule_violations
        ],
        "learning": dashboard_service.learning_metrics(session),
        "last_research": dashboard_service.last_research(session),
        "providers": providers,
        "ai_health": ai_health,
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request,
                   session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "settings.html", {})


@router.get("/settings/investment-policy", response_class=HTMLResponse)
async def investment_policy(request: Request,
                            session: Session = Depends(get_session)):
    from apps.api.services.policies import (
        PolicyNotFoundError,
        PublishedVersionNotFoundError,
        read_current_policy,
        read_current_published,
    )
    policy_status = "none"
    version_number = None
    published_at = None
    try:
        read_current_policy(session)
        policy_status = "draft"
        try:
            version, _ = read_current_published(session)
            policy_status = "published"
            version_number = version.version_number
            published_at = version.published_at
        except PublishedVersionNotFoundError:
            pass
    except PolicyNotFoundError:
        pass
    return templates.TemplateResponse(request, "investment_policy.html", {
        "policy_status": policy_status,
        "version_number": version_number,
        "published_at": published_at,
    })


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio(request: Request,
                    session: Session = Depends(get_session)):
    hid = _household(session)
    return templates.TemplateResponse(request, "portfolio.html", {
        "summary": portfolio_reality.wealth_summary(session, hid),
        "accounts": portfolio_reality.list_accounts(session, hid),
        "holdings": portfolio_reality.list_holdings(session, hid),
        "cash": portfolio_reality.list_cash(session, hid),
    })


@router.get("/decision/{decision_id}", response_class=HTMLResponse)
async def decision_workspace(request: Request, decision_id: str,
                             session: Session = Depends(get_session)):
    try:
        did = UUID(decision_id)
    except ValueError:
        raise HTTPException(400, "Invalid decision id")
    from apps.api.services.decision_workspace import (
        DecisionWorkspaceNotFoundError,
        decision_workspace,
    )
    try:
        data = decision_workspace(session, did)
    except DecisionWorkspaceNotFoundError:
        raise HTTPException(404, "Decision not found")
    return templates.TemplateResponse(request, "decision_workspace.html",
                                      {"ws": data})


@router.get("/research", response_class=HTMLResponse)
async def research(request: Request,
                   session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "research.html", {
        "requests": DashboardResearchService.list_recent(session),
    })


@router.get("/memo/{memo_id}", response_class=HTMLResponse)
async def memo_view(request: Request, memo_id: str,
                    session: Session = Depends(get_session)):
    try:
        mid = UUID(memo_id)
    except ValueError:
        raise HTTPException(400, "Invalid memo id")
    memo = dashboard_service.list_memo(session, mid)
    if memo is None:
        raise HTTPException(404, "Memo not found")
    return templates.TemplateResponse(request, "memo.html", memo)


@router.get("/decisions", response_class=HTMLResponse)
async def decisions(request: Request,
                    session: Session = Depends(get_session)):
    hid = _household(session)
    return templates.TemplateResponse(request, "decisions.html", {
        "pending": dashboard_service.list_pending_decisions_detail(session, hid),
        "history": dashboard_service.list_decision_history(session, hid),
        "policy_published": _policy_published(session),
    })


@router.get("/learning", response_class=HTMLResponse)
async def learning(request: Request,
                   session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request, "learning.html", dashboard_service.learning_metrics(session),
    )


@router.get("/observability", response_class=HTMLResponse)
async def observability(request: Request,
                        session: Session = Depends(get_session)):
    from apps.api.services import observability_service

    providers, ai_health = _runtime_health(session)
    return templates.TemplateResponse(request, "observability.html", {
        "summary": observability_service.execution_summary(session),
        "cost": observability_service.cost_breakdown(session),
        "reliability": observability_service.execution_reliability(session),
        "trend": observability_service.cost_trend(session),
        "prompt_stats": observability_service.prompt_version_stats(session),
        "executions": observability_service.list_executions(session, 50),
        "providers": providers,
        "ai_health": ai_health,
    })


@router.get("/setup", response_class=HTMLResponse)
async def setup(request: Request, session: Session = Depends(get_session)):
    from apps.api.services.readiness_service import readiness_status

    return templates.TemplateResponse(request, "setup.html",
                                      readiness_status(session))
