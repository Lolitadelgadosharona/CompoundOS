"""Portfolio Upgrade API — Sprint 018."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.portfolio_upgrade import (
    AnalyticsService,
    BenchmarkService,
    BondService,
    CommitteeBriefService,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio-upgrade"])


# ── Analytics ────────────────────────────────────────────────────────


class AnalyticsRequest(BaseModel):
    returns: list[float]
    benchmark_returns: Optional[list[float]] = None
    risk_free: float = 4.5
    period: str = "1y"


@router.post("/analytics")
def portfolio_analytics(body: AnalyticsRequest):
    pa = AnalyticsService.analyze(
        body.returns, body.benchmark_returns,
        body.risk_free, body.period,
    )
    return {
        "sharpe_ratio": pa.sharpe_ratio,
        "sharpe_rating": pa.sharpe_rating,
        "max_drawdown_pct": pa.max_drawdown_pct,
        "drawdown_rating": pa.drawdown_rating,
        "portfolio_beta": pa.portfolio_beta,
        "returns": pa.returns,
        "period": pa.period_label,
    }


# ── Benchmark ────────────────────────────────────────────────────────


class BenchmarkRequest(BaseModel):
    portfolio_return_pct: float
    period: str = "1y"


@router.post("/benchmark")
def benchmark_compare(body: BenchmarkRequest):
    br = BenchmarkService.compare(body.portfolio_return_pct, body.period)
    return {
        "portfolio_return": br.portfolio_return_pct,
        "sp500_return": br.sp500_return_pct,
        "balanced_return": br.balanced_return_pct,
        "outperformance_sp500": br.outperformance_vs_sp500,
        "outperformance_balanced": br.outperformance_vs_balanced,
        "beat_sp500": br.beat_sp500,
        "beat_balanced": br.beat_balanced,
        "period": br.period,
    }


# ── Committee Brief ──────────────────────────────────────────────────


class BriefRequest(BaseModel):
    symbol: str
    recommendation: str
    confidence: int
    quality_score: int
    quality_label: str
    votes: list[dict]
    key_facts: list[str]
    risks: list[str]


@router.post("/brief")
def committee_brief(body: BriefRequest):
    brief = CommitteeBriefService.generate(
        body.symbol, body.recommendation, body.confidence,
        body.quality_score, body.quality_label,
        body.votes, body.key_facts, body.risks,
    )
    return {
        "symbol": brief.symbol,
        "recommendation": brief.recommendation,
        "confidence": brief.confidence,
        "quality_score": brief.quality_score,
        "quality_label": brief.quality_label,
        "majority_vote": brief.majority_vote,
        "has_dissents": brief.has_dissents,
        "dissents": brief.dissents,
        "key_facts": brief.key_facts,
        "risks": brief.risks,
        "date": brief.date,
    }


# ── Bond Intelligence ────────────────────────────────────────────────


@router.get("/bond/{symbol}")
def bond_analysis(symbol: str):
    result = BondService.analyze(symbol)
    if result is None:
        return {"error": f"Unsupported bond: {symbol}"}
    return {
        "symbol": result.symbol,
        "name": result.name,
        "yield_pct": result.yield_pct,
        "effective_duration": result.effective_duration,
        "rate_sensitivity": result.rate_sensitivity,
        "duration_risk": result.duration_risk,
        "credit_quality": result.credit_quality,
        "role": result.role,
    }


class BondPortfolioRequest(BaseModel):
    positions: list[dict]


@router.post("/bond/portfolio")
def bond_portfolio(body: BondPortfolioRequest):
    return BondService.portfolio_context(body.positions)
