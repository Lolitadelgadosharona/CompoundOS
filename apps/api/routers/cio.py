"""Ask CIO — natural-language research request (PE-002 Slice B).

Owner asks an investment question in natural language; this resolves the
symbol and reuses the existing research chain (no pipeline duplication).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.repositories.decisions import get_household_id
from apps.api.services.dashboard_research import DashboardResearchService
from apps.api.services.pipeline_async import (
    PipelineProgressTracker,
    execute_pipeline,
)
from apps.api.services.symbol_resolver import (
    SymbolResolutionError,
    resolve_symbol,
)

router = APIRouter(prefix="/api/cio", tags=["cio"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(body: AskRequest, background_tasks: BackgroundTasks,
        session: Session = Depends(get_session)):
    """Owner asks an investment question → full research chain.

    AI CANNOT trigger this — only the Owner (via X-API-Key) may call it.
    """
    try:
        symbol = resolve_symbol(body.question)
    except SymbolResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    household_id = get_household_id(session)
    if household_id is None:
        raise HTTPException(status_code=404, detail="Household profile not found")

    result = DashboardResearchService.create_request(
        session, symbol, household_id, title=body.question,
    )
    run_id = UUID(result["run_id"])

    progress = PipelineProgressTracker.create(run_id)
    background_tasks.add_task(execute_pipeline, run_id, symbol, household_id)

    return {
        "run_id": str(run_id),
        "symbol": symbol,
        "status": progress.state.value,
    }
