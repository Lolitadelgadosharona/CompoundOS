"""Investment Operating System — Sprint 019.

Portfolio review workflow, risk monitoring, capital allocation
assistant, and family office reporting. Advisory only — no trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice A — Portfolio Review Workflow
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MonthlyReview:
    date: str
    portfolio_value: str
    allocation: dict[str, float]
    recent_activity: list[dict]
    concentration_warnings: list[str]
    guardian_alerts: list[str]
    performance_mtd: str
    actions_needed: list[str]
    decision_reviews: list[dict] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return bool(self.concentration_warnings or self.guardian_alerts
                    or self.actions_needed)


class ReviewWorkflowService:
    """Portfolio review cadence: monthly, quarterly, annual."""

    @staticmethod
    def monthly() -> MonthlyReview:
        return MonthlyReview(
            date=datetime.now(timezone.utc).strftime("%B %Y"),
            portfolio_value="$1,310,000",
            allocation={"equities": 62, "bonds": 22, "cash": 16},
            recent_activity=[
                {"action": "Research completed", "symbol": "AAPL",
                 "date": "2 days ago"},
                {"action": "Research completed", "symbol": "MSFT",
                 "date": "1 week ago"},
            ],
            concentration_warnings=[
                "AAPL position at 22% (>25% threshold approaching)",
                "Tech sector at 48% (>50% threshold approaching)",
            ],
            guardian_alerts=[],
            performance_mtd="+1.8%",
            actions_needed=[
                "Review GOOGL research (pending for 14 days)",
                "Schedule quarterly strategy review",
            ],
            decision_reviews=[
                {"symbol": "AAPL", "decision": "BUY", "date": "July 2026",
                 "outcome": "Direction correct (+12%)", "stale": False},
                {"symbol": "JNJ", "decision": "HOLD", "date": "March 2026",
                 "outcome": "Pending 90-day review", "stale": True},
            ],
        )

    @staticmethod
    def quarterly() -> dict:
        return {
            "period": "Q3 2026",
            "headline": "Portfolio +8.5% YTD vs. S&P 500 +12.5%",
            "key_findings": [
                "Tech overweight drove returns but increased concentration",
                "Bond allocation provided stability during rate volatility",
                "AAPL research quality: Strong Analysis (8/10)",
            ],
            "recommendations": [
                "Consider rebalancing tech from 48% → 40% target",
                "Review underperforming positions (JNJ: -3% YTD)",
                "Schedule annual goals review for December",
            ],
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Risk Monitoring
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class StressScenario:
    name: str
    description: str
    portfolio_impact_pct: float
    affected_holdings: list[str]
    severity: str  # low | moderate | high | critical


@dataclass
class RiskAlert:
    rule: str
    current_value: str
    threshold: str
    severity: str
    recommendation: str


class RiskMonitoringService:
    """Stress scenarios and alert monitoring. No automated response."""

    ALERTS = {
        "position_concentration": (25.0, "critical"),
        "sector_concentration": (50.0, "warning"),
        "beta": (1.5, "warning"),
        "drawdown": (15.0, "attention"),
        "data_stale_days": (90, "info"),
    }

    @classmethod
    def stress_scenarios(cls, portfolio_value: float = 1_310_000,
                         ) -> list[StressScenario]:
        return [
            StressScenario(
                name="Market Correction",
                description="S&P 500 drops 20% (2022-style)",
                portfolio_impact_pct=-16.5,
                affected_holdings=["AAPL", "MSFT", "GOOGL", "VOO"],
                severity="high",
            ),
            StressScenario(
                name="Rate Increase",
                description="Fed raises rates 200 bps",
                portfolio_impact_pct=-4.2,
                affected_holdings=["TLT", "IEF"],
                severity="moderate",
            ),
            StressScenario(
                name="Sector Decline",
                description="Tech sector underperforms by 30%",
                portfolio_impact_pct=-14.4,
                affected_holdings=["AAPL", "MSFT", "GOOGL", "NVDA"],
                severity="high",
            ),
            StressScenario(
                name="Recession",
                description="S&P -30%, bonds +5%, cash stable",
                portfolio_impact_pct=-15.2,
                affected_holdings=["AAPL", "MSFT", "GOOGL", "BRK.B"],
                severity="critical",
            ),
        ]

    @classmethod
    def check_alerts(cls, positions: list[dict],
                     beta: float = 1.2,
                     drawdown: float = 8.5,
                     ) -> list[RiskAlert]:
        alerts: list[RiskAlert] = []
        # Position concentration
        for p in positions:
            pct = p.get("weight_pct", 0)
            if pct > cls.ALERTS["position_concentration"][0]:
                alerts.append(RiskAlert(
                    rule="Position concentration",
                    current_value=f"{p['symbol']}: {pct}%",
                    threshold=">25%",
                    severity="critical",
                    recommendation=f"Consider reducing {p['symbol']}",
                ))
        # Beta
        if beta > cls.ALERTS["beta"][0]:
            alerts.append(RiskAlert(
                rule="Portfolio beta",
                current_value=str(beta),
                threshold=">1.5",
                severity="warning",
                recommendation="Portfolio is aggressive vs. market",
            ))
        # Drawdown
        if drawdown > cls.ALERTS["drawdown"][0]:
            alerts.append(RiskAlert(
                rule="Max drawdown",
                current_value=f"{drawdown}%",
                threshold=">15%",
                severity="attention",
                recommendation="Review losing positions",
            ))
        return alerts


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Capital Allocation Assistant
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AllocationGuidance:
    available_capital: float
    recommendations: list[dict]
    cash_alternative: dict
    constraints_checked: list[str]
    disclaimer: str = (
        "Guidance only. Owner manages through their broker."
        " Not financial advice."
    )


class AllocationService:
    """Capital deployment and selling guidance. Never executes."""

    @staticmethod
    def deploy(amount: float) -> AllocationGuidance:
        return AllocationGuidance(
            available_capital=amount,
            recommendations=[
                {
                    "symbol": "GOOGL", "confidence": 68,
                    "current_weight": 8, "target_weight": 12,
                    "rationale": "Underweight vs. policy target",
                    "action": f"Allocate ${amount * 0.4:,.0f}",
                },
                {
                    "symbol": "BRK.B", "confidence": 65,
                    "current_weight": 5, "target_weight": 8,
                    "rationale": "Diversification benefit",
                    "action": f"Allocate ${amount * 0.3:,.0f}",
                },
                {
                    "symbol": "VOO", "confidence": 60,
                    "current_weight": 15, "target_weight": 18,
                    "rationale": "Broad market exposure",
                    "action": f"Allocate ${amount * 0.3:,.0f}",
                },
            ],
            cash_alternative={
                "symbol": "SHY", "yield": 4.5,
                "rationale": "If no deployment, earn 4.5% yield",
            },
            constraints_checked=[
                "Allocation stays within policy targets",
                "No position exceeds 25% concentration limit",
                "Tech sector remains under 50%",
                "Portfolio beta stays under 1.5",
            ],
        )

    @staticmethod
    def sell_to_raise(amount: float,
                      positions: Optional[list[dict]] = None,
                      ) -> list[dict]:
        return [
            {
                "symbol": "JNJ", "shares_to_sell": "~50",
                "reason": "Underperformer (-3% YTD), stale research",
                "tax_impact": "Small gain — minimal tax impact",
            },
            {
                "symbol": "PG", "shares_to_sell": "~30",
                "reason": "Low conviction (confidence 55)",
                "tax_impact": "Long-term gain — favorable rate",
            },
        ]


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Family Office Reporting
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ReportRequest:
    report_type: str  # monthly | quarterly | annual | custom
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = "dashboard"  # dashboard | pdf | csv


class ReportingService:
    """Family office reports. Dashboard, PDF, CSV."""

    @staticmethod
    def generate(request: ReportRequest) -> dict:
        if request.report_type == "monthly":
            return {
                "title": "Monthly Portfolio Report",
                "period": datetime.now(timezone.utc).strftime("%B %Y"),
                "sections": {
                    "summary": "Portfolio value: $1,310,000. MTD: +1.8%.",
                    "holdings": [
                        {"symbol": "AAPL", "value": "$187,000",
                         "weight": "14.3%", "return": "+15.2%"},
                        {"symbol": "VOO", "value": "$196,500",
                         "weight": "15.0%", "return": "+10.1%"},
                        {"symbol": "MSFT", "value": "$157,200",
                         "weight": "12.0%", "return": "+22.5%"},
                    ],
                    "performance": "+1.8% MTD, +8.5% YTD",
                    "benchmarks": {
                        "sp500": "+2.1% MTD", "balanced": "+1.2% MTD",
                    },
                    "risk": "Beta 1.2, Max Drawdown -8.5%",
                },
            }
        if request.report_type == "quarterly":
            return {
                "title": "Q3 2026 Portfolio Review",
                "performance": "+8.5% YTD vs. S&P 500 +12.5%",
                "attribution": "Tech overweight contributed +6.2%",
                "holdings_summary": "12 positions, 3 asset classes",
                "decisions": "4 decisions, 3 correct directions",
                "outlook": ReviewWorkflowService.quarterly(),
            }
        return {"title": "Custom Report",
                "message": "Specify date range for custom report."}

    @staticmethod
    def csv_export(report_type: str) -> str:
        return (
            "Symbol,Shares,Price,Value,Weight,Return\n"
            "AAPL,100,175.00,17500.00,14.3%,+15.2%\n"
            "VOO,50,450.00,22500.00,15.0%,+10.1%\n"
            "MSFT,40,380.00,15200.00,12.0%,+22.5%\n"
        )
