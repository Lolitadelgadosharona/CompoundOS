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
)

router = APIRouter(prefix="/api/cio", tags=["cio"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(
    body: AskRequest, background_tasks: BackgroundTasks, session: Session = Depends(get_session)
):
    """Owner asks an investment question → full research chain.

    AI CANNOT trigger this — only the Owner (via X-API-Key) may call it.
    """
    household_id = get_household_id(session)
    if household_id is None:
        raise HTTPException(status_code=404, detail="Household profile not found")
    from apps.api.services.instrument_resolver import (
        AmbiguousInstrument,
        canonical_asset,
        query_from_question,
        resolve_query,
    )
    from apps.api.services.launch_providers import get_instrument_provider

    try:
        instrument = resolve_query(query_from_question(body.question), get_instrument_provider())
        symbol = instrument.symbol
        canonical = canonical_asset(session, instrument)
    except AmbiguousInstrument as exc:
        raise HTTPException(
            409, detail={"message": str(exc), "candidates": exc.candidates}
        ) from exc
    except SymbolResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    household_id = get_household_id(session)
    if household_id is None:
        raise HTTPException(status_code=404, detail="Household profile not found")

    result = DashboardResearchService.create_request(
        session,
        symbol,
        household_id,
        title=body.question,
        asset_id=canonical.id,
    )
    run_id = UUID(result["run_id"])

    progress = PipelineProgressTracker.create(run_id)
    background_tasks.add_task(execute_pipeline, run_id, symbol, household_id)

    return {
        "run_id": str(run_id),
        "symbol": symbol,
        "status": progress.state.value,
    }
