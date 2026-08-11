"""Portfolio Intelligence Upgrade — Sprint 018.

Advanced portfolio analytics, benchmark tracking, committee briefs,
and bond intelligence. No trading. Analytics only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import sqrt
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice B — Advanced Portfolio Analytics
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PortfolioAnalytics:
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    portfolio_beta: float = 0.0
    correlation_matrix: dict[str, dict[str, float]] = field(
        default_factory=dict,
    )
    returns: dict[str, float] = field(default_factory=dict)
    risk_free_rate: float = 4.5
    period_label: str = "1y"

    @property
    def sharpe_rating(self) -> str:
        if self.sharpe_ratio >= 2.0:
            return "excellent"
        if self.sharpe_ratio >= 1.0:
            return "good"
        if self.sharpe_ratio >= 0.5:
            return "adequate"
        return "poor"

    @property
    def drawdown_rating(self) -> str:
        if self.max_drawdown_pct < 10:
            return "low"
        if self.max_drawdown_pct < 20:
            return "moderate"
        return "high"


class AnalyticsService:
    """Calculates advanced portfolio metrics. No trading."""

    @staticmethod
    def analyze(
        returns: list[float],
        benchmark_returns: Optional[list[float]] = None,
        risk_free: float = 4.5,
        period: str = "1y",
    ) -> PortfolioAnalytics:
        if not returns or len(returns) < 2:
            return PortfolioAnalytics(risk_free_rate=risk_free,
                                      period_label=period)

        mean_ret = sum(returns) / len(returns)
        excess = [r - risk_free / 12 / 100 for r in returns]
        mean_excess = sum(excess) / len(excess)

        # Volatility (monthly → annualized)
        n = len(excess)
        variance = (sum((x - mean_excess) ** 2 for x in excess)
                    / (n - 1)) if n > 1 else 0.0
        vol = sqrt(variance) * sqrt(12)

        # Sharpe
        sharpe = (mean_excess / vol * sqrt(12)) if vol > 0 else 0.0

        # Max drawdown
        peak = returns[0]
        max_dd = 0.0
        for r in returns:
            if r > peak:
                peak = r
            dd = (peak - r) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Beta (simplified: covariance / variance)
        beta = 1.0
        if benchmark_returns and len(benchmark_returns) == n:
            bex = [b - risk_free / 12 / 100 for b in benchmark_returns]
            bmean_ex = sum(bex) / n
            cov_val = sum((excess[i] - mean_excess)
                          * (bex[i] - bmean_ex) for i in range(n))
            cov_val = cov_val / (n - 1) if n > 1 else 0
            bvar = sum((x - bmean_ex) ** 2 for x in bex) / (n - 1) if n > 1 else 0
            beta = cov_val / bvar if bvar > 0 else 1.0

        return PortfolioAnalytics(
            sharpe_ratio=round(sharpe, 2),
            max_drawdown_pct=round(max_dd, 1),
            portfolio_beta=round(beta, 2),
            returns={
                "mean_monthly_pct": round(mean_ret, 2),
                "annualized_pct": round(mean_ret * 12, 2),
            },
            risk_free_rate=risk_free,
            period_label=period,
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Benchmark & Performance
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BenchmarkResult:
    portfolio_return_pct: float = 0.0
    sp500_return_pct: float = 0.0
    balanced_return_pct: float = 0.0
    outperformance_vs_sp500: float = 0.0
    outperformance_vs_balanced: float = 0.0
    period: str = "1y"

    @property
    def beat_sp500(self) -> bool:
        return self.outperformance_vs_sp500 > 0

    @property
    def beat_balanced(self) -> bool:
        return self.outperformance_vs_balanced > 0


class BenchmarkService:
    """Compares portfolio vs. S&P 500 and 60/40 benchmark. No trading."""

    SP500_ANNUAL_RETURN = 12.5  # representative YTD
    BALANCED_ANNUAL_RETURN = 8.2  # 60% SPY + 40% AGG approx

    @classmethod
    def compare(cls, portfolio_return_pct: float,
                period: str = "1y") -> BenchmarkResult:
        factor = {"1m": 1 / 12, "3m": 0.25, "6m": 0.5,
                  "1y": 1.0, "3y": 3.0}.get(period, 1.0)
        sp500 = cls.SP500_ANNUAL_RETURN * factor
        balanced = cls.BALANCED_ANNUAL_RETURN * factor
        return BenchmarkResult(
            portfolio_return_pct=portfolio_return_pct,
            sp500_return_pct=round(sp500, 2),
            balanced_return_pct=round(balanced, 2),
            outperformance_vs_sp500=round(
                portfolio_return_pct - sp500, 2,
            ),
            outperformance_vs_balanced=round(
                portfolio_return_pct - balanced, 2,
            ),
            period=period,
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Committee Brief
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PerspectiveVote:
    perspective: str
    vote: str  # BUY | HOLD | PASS
    rationale: str = ""


@dataclass
class CommitteeBrief:
    symbol: str
    recommendation: str
    confidence: int
    quality_score: int
    quality_label: str
    votes: list[PerspectiveVote] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    dissents: list[str] = field(default_factory=list)
    date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    @property
    def majority_vote(self) -> str:
        buys = sum(1 for v in self.votes if v.vote == "BUY")
        holds = sum(1 for v in self.votes if v.vote == "HOLD")
        if buys > holds:
            return "BUY"
        return "HOLD" if holds > 0 else "PASS"

    @property
    def has_dissents(self) -> bool:
        return len(self.dissents) > 0


class CommitteeBriefService:
    """Generates structured 1-page committee briefs."""

    @staticmethod
    def generate(
        symbol: str, recommendation: str, confidence: int,
        quality_score: int, quality_label: str,
        votes: list[dict], key_facts: list[str],
        risks: list[str],
    ) -> CommitteeBrief:
        pvs = [PerspectiveVote(**v) for v in votes]
        # Majority vote
        buys = sum(1 for v in pvs if v.vote == "BUY")
        holds = sum(1 for v in pvs if v.vote == "HOLD")
        majority = "BUY" if buys > holds else (
            "HOLD" if holds > 0 else "PASS"
        )
        # Dissents: any vote that differs from majority
        dissents = [
            f"{v.perspective} votes {v.vote}"
            f"{' (' + v.rationale + ')' if v.rationale else ''}"
            for v in pvs if v.vote != majority
        ]
        return CommitteeBrief(
            symbol=symbol, recommendation=recommendation,
            confidence=confidence, quality_score=quality_score,
            quality_label=quality_label, votes=pvs,
            key_facts=key_facts, risks=risks,
            dissents=dissents,
        )


# ═══════════════════════════════════════════════════════════════════════
# Slice A — Bond Intelligence
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BondAnalysis:
    symbol: str
    name: str
    yield_pct: float  # current yield
    effective_duration: float  # years
    rate_sensitivity: float  # % loss per 1% rate increase
    credit_quality: str = "AAA"  # Treasury = AAA
    role: str = ""  # income | diversification | inflation_protection

    @property
    def duration_risk(self) -> str:
        if self.effective_duration > 10:
            return "high"
        if self.effective_duration > 5:
            return "moderate"
        return "low"


BOND_PROFILES = {
    "TLT": {"name": "iShares 20+ Year Treasury Bond ETF",
            "yield_pct": 4.2, "effective_duration": 16.5,
            "role": "long_duration"},
    "IEF": {"name": "iShares 7-10 Year Treasury Bond ETF",
            "yield_pct": 3.8, "effective_duration": 7.5,
            "role": "intermediate"},
    "SHY": {"name": "iShares 1-3 Year Treasury Bond ETF",
            "yield_pct": 4.5, "effective_duration": 1.9,
            "role": "cash_alternative"},
}


class BondService:
    """Treasury ETF bond intelligence. Advisory only."""

    SUPPORTED = {"TLT", "IEF", "SHY"}

    @classmethod
    def analyze(cls, symbol: str) -> BondAnalysis | None:
        symbol = symbol.upper()
        if symbol not in cls.SUPPORTED:
            return None
        profile = BOND_PROFILES[symbol]
        return BondAnalysis(
            symbol=symbol,
            name=profile["name"],
            yield_pct=profile["yield_pct"],
            effective_duration=profile["effective_duration"],
            rate_sensitivity=round(profile["effective_duration"], 1),
            role=profile["role"],
        )

    @classmethod
    def portfolio_context(
        cls, bond_positions: list[dict],
    ) -> dict:
        bonds = []
        total_duration = 0.0
        total_value = 0.0
        for pos in bond_positions:
            analysis = cls.analyze(pos["symbol"])
            if analysis is None:
                continue
            value = pos.get("shares", 0) * pos.get("price", 0)
            bonds.append({
                "symbol": analysis.symbol,
                "name": analysis.name,
                "yield": analysis.yield_pct,
                "duration": analysis.effective_duration,
                "value": value,
                "risk": analysis.duration_risk,
            })
            total_duration += analysis.effective_duration * value
            total_value += value
        avg_duration = (total_duration / total_value
                        if total_value > 0 else 0.0)
        return {
            "bonds": bonds,
            "count": len(bonds),
            "avg_duration": round(avg_duration, 1),
            "total_value": round(total_value, 2),
            "rate_impact": (
                f"A 1% rate increase would reduce bond"
                f" portfolio by ~{round(avg_duration, 1)}%"
            ),
        }
