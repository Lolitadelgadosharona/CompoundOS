"""Daily Ops API — Sprint 016.

Daily brief, owner feedback, learning metrics, data quality.
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.daily_ops import (
    DailyBriefService,
    DataQualityService,
    FeedbackService,
    LearningService,
)

router = APIRouter(prefix="/api/ops", tags=["daily-ops"])


# ── Slice D — Daily Brief ────────────────────────────────────────────


@router.get("/brief")
def daily_brief():
    brief = DailyBriefService.generate()
    result = brief.__dict__.copy()
    result["needs_attention"] = brief.needs_attention
    return result


# ── Slice A — Owner Feedback ─────────────────────────────────────────


class FeedbackRequest(BaseModel):
    memo_id: str
    thesis_agreement: int  # 1-5
    evidence_sufficient: bool
    confidence_appropriate: str  # too_high | correct | too_low
    would_act: str  # yes | no | maybe
    notes: str = ""


@router.post("/feedback")
def submit_feedback(body: FeedbackRequest):
    if body.thesis_agreement < 1 or body.thesis_agreement > 5:
        return {"error": "thesis_agreement must be 1-5"}
    fb = FeedbackService.submit(
        body.memo_id, body.thesis_agreement,
        body.evidence_sufficient,
        body.confidence_appropriate, body.would_act,
        body.notes,
    )
    return {
        "status": "recorded",
        "memo_id": fb.memo_id,
        "submitted_at": fb.submitted_at,
    }


@router.get("/feedback/summary")
def feedback_summary():
    return FeedbackService.summary()


@router.get("/feedback/{memo_id}")
def feedback_for_memo(memo_id: str):
    fbs = FeedbackService.for_memo(memo_id)
    return {
        "memo_id": memo_id,
        "count": len(fbs),
        "items": [
            {"thesis": f.thesis_agreement, "evidence": f.evidence_sufficient,
             "confidence": f.confidence_appropriate, "act": f.would_act,
             "notes": f.notes, "when": f.submitted_at}
            for f in fbs
        ],
    }


# ── Slice B — Learning Metrics ───────────────────────────────────────


class OutcomeRequest(BaseModel):
    symbol: str
    predicted_confidence: int
    actual_return_pct: float
    review_type: str = "30_day"  # 30_day | 90_day | 1_year


@router.post("/learning/outcome")
def record_outcome(body: OutcomeRequest):
    metric = LearningService.record_outcome(
        body.symbol, body.predicted_confidence,
        body.actual_return_pct, body.review_type,
    )
    return {
        "symbol": metric.symbol,
        "direction_correct": metric.direction_correct,
        "confidence_error": round(metric.confidence_error, 1),
    }


@router.get("/learning/accuracy")
def learning_accuracy():
    return LearningService.accuracy()


@router.get("/learning/{symbol}")
def learning_by_symbol(symbol: str):
    metrics = LearningService.by_symbol(symbol)
    return {
        "symbol": symbol,
        "metrics": [
            {"confidence": m.predicted_confidence,
             "actual_return": m.actual_return_pct,
             "direction_correct": m.direction_correct,
             "review_type": m.review_type}
            for m in metrics[-5:]  # last 5
        ],
    }


# ── Slice C — Data Quality ───────────────────────────────────────────


class QualityCheckRequest(BaseModel):
    source_type: str
    last_fetched: Optional[str] = None


@router.post("/data-quality/check")
def check_quality(body: QualityCheckRequest):
    report = DataQualityService.check(body.source_type, body.last_fetched)
    return {
        "source_type": report.source_type,
        "status": report.status,
        "freshness_hours": report.freshness_hours,
        "confidence_impact": report.confidence_impact,
    }


@router.get("/data-quality/all")
def all_quality():
    reports = DataQualityService.all_checks({})
    return {
        "items": [
            {"source": r.source_type, "status": r.status,
             "impact": r.confidence_impact}
            for r in reports
        ],
    }
