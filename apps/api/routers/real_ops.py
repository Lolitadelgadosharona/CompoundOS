"""Real Ops API — Sprint 021."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.real_ops import (
    AccuracyService,
    KnowledgeService,
    PortfolioValidationService,
    WorkflowAutomationService,
)

router = APIRouter(prefix="/api/ops-real", tags=["real-ops"])


# ── Accuracy ─────────────────────────────────────────────────────────


class OutcomeRequest(BaseModel):
    decisions: list[dict]
    current_prices: dict[str, float]


@router.post("/accuracy/outcomes")
def record_outcomes(body: OutcomeRequest):
    outcomes = AccuracyService.record_outcomes(
        body.decisions, body.current_prices,
    )
    metrics = AccuracyService.calculate_metrics(outcomes)
    return {
        "outcomes": [
            {"symbol": o.symbol, "return_pct": o.return_pct,
             "direction_correct": o.direction_correct}
            for o in outcomes
        ],
        "metrics": [
            {"metric": m.metric, "value": m.value,
             "rating": m.rating, "detail": m.detail}
            for m in metrics
        ],
    }


class PerspectiveRequest(BaseModel):
    perspectives: list[dict]


@router.post("/accuracy/perspectives")
def perspective_accuracy(body: PerspectiveRequest):
    results = AccuracyService.by_perspective(body.perspectives)
    return {
        "perspectives": [
            {"name": p.perspective, "accuracy": round(p.accuracy, 3),
             "correct": p.correct, "total": p.total}
            for p in results
        ],
    }


# ── Knowledge ────────────────────────────────────────────────────────


class CrossReferenceRequest(BaseModel):
    symbol: str
    current_thesis: str
    past_memos: list[dict]


@router.post("/knowledge/cross-ref")
def cross_reference(body: CrossReferenceRequest):
    ref = KnowledgeService.cross_reference(
        body.symbol, body.current_thesis, body.past_memos,
    )
    return {
        "symbol": body.symbol,
        "current_thesis": ref.current_thesis,
        "past_thesis": ref.past_thesis,
        "past_date": ref.past_date,
        "contradiction": ref.contradiction,
        "contradiction_detail": ref.contradiction_detail,
        "context_blurb": KnowledgeService.context_blurb(ref),
    }


# ── Portfolio Validation ─────────────────────────────────────────────


class CSVImportRequest(BaseModel):
    rows: list[dict]
    expected_total: Optional[float] = None


@router.post("/portfolio/import")
def import_csv(body: CSVImportRequest):
    result = PortfolioValidationService.validate_csv(
        body.rows, body.expected_total,
    )
    return {
        "imported": result.rows_imported,
        "skipped": result.rows_skipped,
        "errors": result.errors,
        "total_value": result.total_value,
        "currency_flags": result.currency_flags,
    }


# ── Workflow ─────────────────────────────────────────────────────────


@router.get("/workflow/reminders")
def workflow_reminders():
    tasks = WorkflowAutomationService.reminders()
    return {
        "tasks": [
            {"id": t.task_id, "description": t.description,
             "frequency": t.frequency, "next_due": t.next_due,
             "action": t.action, "auto_execute": t.auto_execute}
            for t in tasks
        ],
    }
