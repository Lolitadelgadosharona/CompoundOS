"""Research workflow API — Sprint 015 (async + progress)."""

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from apps.api.services.pipeline_async import (
    PipelineProgressTracker,
    execute_pipeline,
)

router = APIRouter(prefix="/api/research", tags=["research-workflow"])


class StartResearchRequest(BaseModel):
    symbol: str


@router.post("/start")
def start_research(body: StartResearchRequest,
                   background_tasks: BackgroundTasks):
    """Create research request and start async pipeline execution."""
    if not body.symbol or not body.symbol.strip():
        raise HTTPException(status_code=400, detail="Symbol is required")

    symbol = body.symbol.strip().upper()
    run_id = uuid4()

    # Create progress tracker entry
    progress = PipelineProgressTracker.create(run_id)

    # Start pipeline in background
    background_tasks.add_task(execute_pipeline, run_id, symbol)

    return {
        "run_id": str(run_id),
        "symbol": symbol,
        "status": progress.state.value,
        "message": f"Research started for {symbol}",
    }


@router.get("/{run_id}/status")
def get_status(run_id: str):
    """Return current pipeline progress."""
    from uuid import UUID
    progress = PipelineProgressTracker.get(UUID(run_id))
    if progress is None:
        return {"status": "not_found"}

    return {
        "run_id": str(progress.run_id),
        "status": progress.state.value,
        "progress_pct": progress.progress_pct,
        "perspectives": f"{progress.perspective_count}/{progress.total_perspectives}",
        "memo_id": progress.memo_id,
        "confidence": progress.confidence,
        "error": progress.error,
        "is_complete": progress.is_complete,
        "is_failed": progress.is_failed,
        "steps": progress.steps,
        "started_at": progress.started_at,
        "completed_at": progress.completed_at,
    }


@router.get("/recent")
def list_recent():
    """List recent research runs."""
    runs = [
        {
            "run_id": str(rid),
            "status": p.state.value,
            "progress_pct": p.progress_pct,
            "is_complete": p.is_complete,
        }
        for rid, p in PipelineProgressTracker._runs.items()
    ]
    return {"requests": runs}
