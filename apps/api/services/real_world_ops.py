"""Real World Operation & Intelligence Optimization — Sprint 023.

Household operations, AI calibration, investor behavior,
and wealth planning. No trading. Advisory only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice A — Live Household Operation
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class HouseholdSnapshot:
    date: str
    investments: float
    cash_balances: float
    real_estate: float
    total_debt: float = 0.0
    monthly_expenses: float = 0.0
    monthly_income: float = 0.0

    @property
    def net_worth(self) -> float:
        return (self.investments + self.cash_balances
                + self.real_estate - self.total_debt)

    @property
    def emergency_fund_months(self) -> float:
        if self.monthly_expenses == 0:
            return 0
        return self.cash_balances / self.monthly_expenses

    @property
    def emergency_fund_status(self) -> str:
        months = self.emergency_fund_months
        if months >= 6:
            return "green"
        if months >= 3:
            return "yellow"
        return "red"

    @property
    def savings_rate_pct(self) -> float:
        if self.monthly_income == 0:
            return 0
        return round(
            (self.monthly_income - self.monthly_expenses)
            / self.monthly_income * 100, 1,
        )


class HouseholdService:
    """Monthly household financial snapshot. No account connections."""

    @staticmethod
    def snapshot(
        investments: float, cash: float, real_estate: float,
        debt: float = 0, expenses: float = 0, income: float = 0,
    ) -> HouseholdSnapshot:
        return HouseholdSnapshot(
            date=datetime.now(timezone.utc).strftime("%B %Y"),
            investments=investments, cash_balances=cash,
            real_estate=real_estate, total_debt=debt,
            monthly_expenses=expenses, monthly_income=income,
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice B — AI Calibration Improvement
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CalibrationReport:
    week_start: str
    overall_accuracy: float
    perspective_accuracy: dict[str, float]
    confidence_scatter: list[dict] = field(default_factory=list)
    biggest_hit: Optional[dict] = None
    biggest_miss: Optional[dict] = None
    recommendations: list[str] = field(default_factory=list)


class CalibrationService:
    """Weekly AI calibration. Equal weighting until 50+ outcomes."""

    @staticmethod
    def generate_report(
        outcomes: list[dict],
        perspective_data: Optional[dict[str, dict]] = None,
    ) -> CalibrationReport:
        if not outcomes:
            return CalibrationReport(
                week_start=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                overall_accuracy=0, perspective_accuracy={},
            )

        correct = sum(1 for o in outcomes if o.get("correct"))
        accuracy = correct / len(outcomes)

        persp_acc = {}
        if perspective_data:
            for name, data in perspective_data.items():
                total = data.get("total", 0)
                persp_acc[name] = (
                    round(data["correct"] / total, 3) if total > 0 else 0
                )

        # Biggest hit/miss
        sorted_outcomes = sorted(
            outcomes, key=lambda o: abs(o.get("return_pct", 0)),
            reverse=True,
        )
        recs = []
        if accuracy < 0.5:
            recs.append(
                "Accuracy below 50% — review prompt quality",
            )

        return CalibrationReport(
            week_start=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            overall_accuracy=round(accuracy, 3),
            perspective_accuracy=persp_acc,
            biggest_hit=(
                {"symbol": sorted_outcomes[0]["symbol"],
                 "return": sorted_outcomes[0].get("return_pct")}
                if sorted_outcomes else None
            ),
            biggest_miss=(
                {"symbol": sorted_outcomes[-1]["symbol"],
                 "return": sorted_outcomes[-1].get("return_pct")}
                if sorted_outcomes else None
            ),
            recommendations=recs,
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Long-Term Wealth Planning
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class RetirementProjection:
    current_age: int
    retirement_age: int
    current_savings: float
    monthly_contribution: float
    annual_return_pct: float = 7.0
    inflation_pct: float = 3.0

    @property
    def years_to_retirement(self) -> int:
        return max(0, self.retirement_age - self.current_age)

    @property
    def projected_value(self) -> float:
        """Compound growth projection (educational — not advice)."""
        r = self.annual_return_pct / 100
        n = self.years_to_retirement
        if n == 0:
            return self.current_savings
        fv_savings = self.current_savings * ((1 + r) ** n)
        monthly_r = r / 12
        months = n * 12
        fv_contributions = (
            self.monthly_contribution
            * ((1 + monthly_r) ** months - 1)
            / monthly_r
        )
        return round(fv_savings + fv_contributions, 2)

    @property
    def monthly_withdrawal_4pct(self) -> float:
        return round(self.projected_value * 0.04 / 12, 2)


@dataclass
class CollegeProjection:
    child_age: int
    college_age: int = 18
    current_savings: float = 0
    monthly_contribution: float = 0
    annual_cost: float = 35000
    cost_inflation: float = 5.0

    @property
    def years_to_college(self) -> int:
        return max(0, self.college_age - self.child_age)

    @property
    def projected_cost(self) -> float:
        return round(
            self.annual_cost
            * ((1 + self.cost_inflation / 100) ** self.years_to_college),
            2,
        )

    @property
    def funding_gap(self) -> float:
        return round(self.projected_cost * 4 - self.current_savings, 2)


class WealthPlanningService:
    """Educational wealth planning tools. Not financial advice."""

    DISCLAIMER = (
        "Educational projection only. Not financial advice."
        " Consult a professional."
    )

    @staticmethod
    def retirement(age: int, retire_age: int, savings: float,
                   contribution: float) -> RetirementProjection:
        return RetirementProjection(
            current_age=age, retirement_age=retire_age,
            current_savings=savings, monthly_contribution=contribution,
        )

    @staticmethod
    def college(child_age: int, savings: float = 0,
                contribution: float = 0) -> CollegeProjection:
        return CollegeProjection(
            child_age=child_age, current_savings=savings,
            monthly_contribution=contribution,
        )

    @staticmethod
    def estate_checklist() -> dict:
        return {
            "will": "Do you have a current will?",
            "trust": "Have you considered a revocable living trust?",
            "beneficiaries": "Are retirement account beneficiaries current?",
            "power_of_attorney": "Do you have healthcare and financial POA?",
            "guardianship": "If minor children: guardianship designated?",
            "disclaimer": "Informational checklist. Consult an estate attorney.",
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Investor Behavior Layer
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BehaviorInsight:
    signal: str
    value: str
    interpretation: str
    category: str  # neutral | positive | attention


class BehaviorService:
    """Investor behavior insights. Informational only. Private."""

    @staticmethod
    def analyze(
        decisions: list[dict],
        approvals: int = 0,
        rejections: int = 0,
        avg_latency_days: float = 0,
    ) -> list[BehaviorInsight]:
        insights = []

        # Action bias
        total = approvals + rejections
        if total > 0:
            rate = approvals / total * 100
            cat = "attention" if rate > 80 else "neutral"
            insights.append(BehaviorInsight(
                signal="action_bias",
                value=f"{rate:.0f}% approved",
                interpretation=(
                    "High approval rate — consider more scrutiny"
                    if rate > 80
                    else "Balanced decision-making"
                ),
                category=cat,
            ))

        # Decision latency
        if avg_latency_days > 0:
            cat = "attention" if avg_latency_days > 14 else "neutral"
            insights.append(BehaviorInsight(
                signal="decision_latency",
                value=f"{avg_latency_days:.0f} days avg",
                interpretation=(
                    "Decisions take >2 weeks — risk of missed opportunities"
                    if avg_latency_days > 14
                    else "Reasonable decision pace"
                ),
                category=cat,
            ))

        # Sector preference
        if decisions:
            sectors: dict[str, int] = {}
            for d in decisions:
                s = d.get("sector", "unknown")
                sectors[s] = sectors.get(s, 0) + 1
            top = max(sectors, key=sectors.get)
            insights.append(BehaviorInsight(
                signal="sector_preference",
                value=f"Most approved: {top}",
                interpretation=f"You tend to favor {top} sector",
                category="neutral",
            ))

        return insights
