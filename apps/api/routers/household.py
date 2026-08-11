"""Real World Ops API — Sprint 023."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.real_world_ops import (
    BehaviorService,
    CalibrationService,
    HouseholdService,
    WealthPlanningService,
)

router = APIRouter(prefix="/api/household", tags=["household"])


# ── Household ────────────────────────────────────────────────────────


class HouseholdRequest(BaseModel):
    investments: float
    cash: float
    real_estate: float
    debt: float = 0
    expenses: float = 0
    income: float = 0


@router.post("/snapshot")
def household_snapshot(body: HouseholdRequest):
    snap = HouseholdService.snapshot(
        body.investments, body.cash, body.real_estate,
        body.debt, body.expenses, body.income,
    )
    return {
        "date": snap.date,
        "net_worth": snap.net_worth,
        "investments": snap.investments,
        "cash": snap.cash_balances,
        "real_estate": snap.real_estate,
        "debt": snap.total_debt,
        "emergency_fund_months": round(snap.emergency_fund_months, 1),
        "emergency_fund_status": snap.emergency_fund_status,
        "savings_rate_pct": snap.savings_rate_pct,
    }


# ── Calibration ──────────────────────────────────────────────────────


class CalibrationRequest(BaseModel):
    outcomes: list[dict]
    perspective_data: Optional[dict[str, dict]] = None


@router.post("/calibration/report")
def calibration_report(body: CalibrationRequest):
    report = CalibrationService.generate_report(
        body.outcomes, body.perspective_data,
    )
    return {
        "week": report.week_start,
        "overall_accuracy": report.overall_accuracy,
        "perspectives": report.perspective_accuracy,
        "biggest_hit": report.biggest_hit,
        "biggest_miss": report.biggest_miss,
        "recommendations": report.recommendations,
    }


# ── Wealth Planning ──────────────────────────────────────────────────


class RetirementRequest(BaseModel):
    age: int
    retire_age: int
    savings: float
    contribution: float


@router.post("/planning/retirement")
def retirement_projection(body: RetirementRequest):
    proj = WealthPlanningService.retirement(
        body.age, body.retire_age, body.savings, body.contribution,
    )
    return {
        "projected_value": proj.projected_value,
        "years_to_retirement": proj.years_to_retirement,
        "monthly_withdrawal_4pct": proj.monthly_withdrawal_4pct,
        "disclaimer": WealthPlanningService.DISCLAIMER,
    }


class CollegeRequest(BaseModel):
    child_age: int
    savings: float = 0
    contribution: float = 0


@router.post("/planning/college")
def college_projection(body: CollegeRequest):
    proj = WealthPlanningService.college(
        body.child_age, body.savings, body.contribution,
    )
    return {
        "years_to_college": proj.years_to_college,
        "projected_annual_cost": proj.projected_cost,
        "total_4yr_cost": round(proj.projected_cost * 4, 2),
        "funding_gap": proj.funding_gap,
        "disclaimer": WealthPlanningService.DISCLAIMER,
    }


@router.get("/planning/estate")
def estate_checklist():
    return WealthPlanningService.estate_checklist()


# ── Behavior ─────────────────────────────────────────────────────────


class BehaviorRequest(BaseModel):
    decisions: list[dict]
    approvals: int = 0
    rejections: int = 0
    avg_latency_days: float = 0


@router.post("/behavior/insights")
def behavior_insights(body: BehaviorRequest):
    insights = BehaviorService.analyze(
        body.decisions, body.approvals, body.rejections,
        body.avg_latency_days,
    )
    return {
        "insights": [
            {"signal": i.signal, "value": i.value,
             "interpretation": i.interpretation,
             "category": i.category}
            for i in insights
        ],
    }
