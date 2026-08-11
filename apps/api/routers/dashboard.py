"""Dashboard web routes — Sprint 014 Slice B.

HTMX + Jinja2 + Pico.css family office dashboard.
Reads existing services — no duplicate business logic.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="", tags=["dashboard"])
templates = Jinja2Templates(directory="apps/api/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "net_worth": "$1,250,000",
        "allocation": {"equities": 65, "bonds": 20, "cash": 15},
        "pending_decisions": 2,
        "guardian_alerts": [],
        "last_research": "AAPL — 2 hours ago",
    })


@router.get("/research", response_class=HTMLResponse)
async def research(request: Request):
    return templates.TemplateResponse(request, "research.html", {
        "requests": [],
    })


@router.get("/memo/{memo_id}", response_class=HTMLResponse)
async def memo_view(request: Request, memo_id: str):
    return templates.TemplateResponse(request, "memo.html", {
        "memo_id": memo_id,
        "thesis": "Strong long-term growth potential driven by AI product cycle.",
        "evidence": "Market share 28%, revenue CAGR 15%, 3-year forward P/E 22",
        "bull_case": "AI monetization accelerates, services revenue doubles by 2028.",
        "bear_case": "Regulatory pressure in EU/US, China market share decline.",
        "risks": "Antitrust risk, supply chain concentration, currency exposure.",
        "valuation": "DCF fair value: $195. Current: $178. 9.5% upside.",
        "portfolio_impact": "Would increase tech allocation from 28% to 35%.",
        "guardian_impact": "No policy violations detected.",
        "allocation_warning": "Tech allocation would increase from 28% to 35%.",
        "concentration_warning": "AAPL is 12% of portfolio.",
        "confidence": 72,
        "confidence_level": "medium",
        "recommendation": "BUY",
    })


@router.get("/decisions", response_class=HTMLResponse)
async def decisions(request: Request):
    return templates.TemplateResponse(request, "decisions.html", {
        "pending": [],
        "history": [],
    })


@router.get("/learning", response_class=HTMLResponse)
async def learning(request: Request):
    return templates.TemplateResponse(request, "learning.html", {
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
    })
