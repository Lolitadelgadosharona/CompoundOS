"""Intelligence Expansion API — Sprint 017."""


from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.intelligence_expansion import (
    AssetHolding,
    MacroService,
    MemoryEntry,
    MultiAssetService,
    QualityScorer,
    ResearchMemory,
)

router = APIRouter(prefix="/api/intel", tags=["intelligence"])


# ── Quality Scoring ──────────────────────────────────────────────────


class ScoreRequest(BaseModel):
    memo: dict
    source_count: int = 0
    data_age_hours: float = 0


@router.post("/quality/score")
def score_memo(body: ScoreRequest):
    qs = QualityScorer.score(body.memo, body.source_count,
                              body.data_age_hours)
    return {
        "completeness": qs.completeness,
        "evidence_quality": qs.evidence_quality,
        "balance": qs.balance,
        "confidence_alignment": qs.confidence_alignment,
        "clarity": qs.clarity,
        "overall": qs.overall,
        "label": qs.label,
    }


# ── Memory ───────────────────────────────────────────────────────────


class MemoryStoreRequest(BaseModel):
    symbol: str
    memo_id: str
    thesis: str
    confidence: int
    recommendation: str
    tags: list[str] = []


@router.post("/memory/store")
def store_memory(body: MemoryStoreRequest):
    entry = MemoryEntry(
        symbol=body.symbol, memo_id=body.memo_id,
        thesis=body.thesis, confidence=body.confidence,
        recommendation=body.recommendation, tags=body.tags,
        created_at="now",
    )
    ResearchMemory.store(entry)
    return {"stored": body.symbol, "count": len(
        ResearchMemory.for_symbol(body.symbol),
    )}


@router.get("/memory/{symbol}")
def memory_for_symbol(symbol: str):
    entries = ResearchMemory.for_symbol(symbol.upper())
    return {
        "symbol": symbol.upper(), "count": len(entries),
        "entries": [
            {"memo_id": e.memo_id, "thesis": e.thesis[:100],
             "confidence": e.confidence, "outcome": e.outcome}
            for e in entries[-5:]  # last 5
        ],
    }


@router.get("/memory/{symbol}/summary")
def memory_summary(symbol: str):
    return ResearchMemory.summary(symbol.upper())


# ── Macro ────────────────────────────────────────────────────────────


@router.get("/macro")
def macro_snapshot():
    snap = MacroService.snapshot()
    return {
        "fed_funds_rate": snap.fed_funds_rate,
        "ten_year_yield": snap.ten_year_yield,
        "two_ten_spread": snap.two_ten_spread,
        "sp500_ytd": snap.sp500_ytd,
        "vix": snap.vix,
        "recession_signal": snap.recession_signal,
        "market_regime": snap.market_regime,
        "context_blurb": snap.context_blurb(),
        "sector_performance": snap.sector_performance,
    }


# ── Multi-Asset ──────────────────────────────────────────────────────


class MultiAssetRequest(BaseModel):
    holdings: list[dict]


@router.post("/multi-asset/classify")
def classify_holdings(body: MultiAssetRequest):
    holdings = [
        AssetHolding(
            symbol=h["symbol"], asset_type=h["asset_type"],
            shares=h["shares"], price=h["price"],
            name=h.get("name", ""),
            expense_ratio=h.get("expense_ratio", 0),
            yield_pct=h.get("yield_pct", 0),
        )
        for h in body.holdings
    ]
    return MultiAssetService.classify(holdings)


@router.get("/multi-asset/etf/{symbol}")
def etf_detail(symbol: str):
    return MultiAssetService.etf_detail(
        symbol,
        top_holdings=[
            {"symbol": "AAPL", "weight": 7.1, "name": "Apple Inc."},
            {"symbol": "MSFT", "weight": 6.8, "name": "Microsoft"},
            {"symbol": "NVDA", "weight": 5.2, "name": "NVIDIA"},
            {"symbol": "AMZN", "weight": 3.8, "name": "Amazon"},
            {"symbol": "META", "weight": 2.4, "name": "Meta"},
        ],
        expense_ratio=0.03,
    )
