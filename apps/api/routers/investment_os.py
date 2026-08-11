"""Investment OS API — Sprint 019."""

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from apps.api.services.investment_os import (
    AllocationService,
    ReportingService,
    ReportRequest,
    ReviewWorkflowService,
    RiskMonitoringService,
)

router = APIRouter(prefix="/api/os", tags=["investment-os"])


# ── Reviews ──────────────────────────────────────────────────────────


@router.get("/review/monthly")
def monthly_review():
    review = ReviewWorkflowService.monthly()
    return {
        "date": review.date,
        "portfolio_value": review.portfolio_value,
        "allocation": review.allocation,
        "recent_activity": review.recent_activity,
        "concentration_warnings": review.concentration_warnings,
        "guardian_alerts": review.guardian_alerts,
        "performance": review.performance_mtd,
        "actions_needed": review.actions_needed,
        "decision_reviews": review.decision_reviews,
        "needs_attention": review.needs_attention,
    }


@router.get("/review/quarterly")
def quarterly_review():
    return ReviewWorkflowService.quarterly()


# ── Risk ─────────────────────────────────────────────────────────────


@router.get("/risk/stress")
def stress_scenarios():
    scenarios = RiskMonitoringService.stress_scenarios()
    return {
        "scenarios": [
            {"name": s.name, "description": s.description,
             "impact_pct": s.portfolio_impact_pct,
             "affected": s.affected_holdings,
             "severity": s.severity}
            for s in scenarios
        ],
    }


class AlertRequest(BaseModel):
    positions: list[dict]
    beta: float = 1.2
    drawdown: float = 8.5


@router.post("/risk/alerts")
def risk_alerts(body: AlertRequest):
    alerts = RiskMonitoringService.check_alerts(
        body.positions, body.beta, body.drawdown,
    )
    return {
        "alerts": [
            {"rule": a.rule, "current": a.current_value,
             "threshold": a.threshold, "severity": a.severity,
             "recommendation": a.recommendation}
            for a in alerts
        ],
    }


# ── Allocation ───────────────────────────────────────────────────────


class DeployRequest(BaseModel):
    amount: float


@router.post("/allocate/deploy")
def deploy_capital(body: DeployRequest):
    guidance = AllocationService.deploy(body.amount)
    return {
        "available": guidance.available_capital,
        "recommendations": guidance.recommendations,
        "cash_alternative": guidance.cash_alternative,
        "constraints": guidance.constraints_checked,
        "disclaimer": guidance.disclaimer,
    }


class SellRequest(BaseModel):
    amount: float


@router.post("/allocate/sell")
def sell_to_raise(body: SellRequest):
    options = AllocationService.sell_to_raise(body.amount)
    return {
        "amount_needed": body.amount,
        "options": options,
        "disclaimer": "Guidance only. No execution. Not tax advice.",
    }


# ── Reporting ────────────────────────────────────────────────────────


class GenerateReportRequest(BaseModel):
    report_type: str  # monthly | quarterly | annual | custom
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = "dashboard"


@router.post("/report/generate")
def generate_report(body: GenerateReportRequest):
    req = ReportRequest(
        report_type=body.report_type,
        start_date=body.start_date,
        end_date=body.end_date,
        format=body.format,
    )
    return ReportingService.generate(req)


@router.get("/report/csv/{report_type}",
            response_class=PlainTextResponse)
def csv_export(report_type: str):
    return ReportingService.csv_export(report_type)
