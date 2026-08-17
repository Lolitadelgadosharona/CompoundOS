"""Ask CIO — natural-language research request (PE-002, PE-002.2a).

Owner asks an investment question in natural language; the query-understanding
layer classifies intent and routes to research / portfolio / theme / macro.
No new public endpoint — POST /api/cio/ask is unchanged.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.repositories.decisions import get_household_id
from apps.api.services.cio_query import (
    CIOQueryError,
    QueryRoute,
    understand_query,
)
from apps.api.services.dashboard_research import DashboardResearchService
from apps.api.services.pipeline_async import (
    PipelineProgressTracker,
    execute_pipeline,
)

router = APIRouter(prefix="/api/cio", tags=["cio"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(body: AskRequest, background_tasks: BackgroundTasks,
        session: Session = Depends(get_session)):
    """Owner asks an investment question → routed response.

    AI CANNOT trigger this — only the Owner (via X-API-Key) may call it.
    """
    try:
        query = understand_query(session, body.question)
    except CIOQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Non-research routes: return an intent + friendly message (no silent
    # failure). Portfolio questions can be answered by the portfolio page;
    # theme/macro research is not built yet.
    if query.route == QueryRoute.PORTFOLIO:
        return {
            "intent": query.intent.value, "route": "portfolio",
            "message": "Portfolio question — see /portfolio",
        }
    if query.route in (QueryRoute.THEME, QueryRoute.MACRO):
        return {
            "intent": query.intent.value, "route": query.route.value,
            "message": f"{query.intent.value} research coming soon",
        }

    # Research route: symbol was deterministically verified.
    symbol = query.symbol
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
        "intent": query.intent.value,
        "entity": query.entity,
        "symbol": symbol,
        "confidence": query.confidence.value,
        "route": "research",
        "run_id": str(run_id),
        "status": progress.state.value,
    }
