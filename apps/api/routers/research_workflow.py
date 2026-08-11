"""Research workflow API endpoints — Sprint 014 Slice C."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.services.dashboard_research import DashboardResearchService

router = APIRouter(prefix="/api/research", tags=["research-workflow"])


class StartResearchRequest(BaseModel):
    symbol: str


@router.post("/start")
def start_research(
    body: StartResearchRequest,
    session: Session = Depends(lambda: None),
):
    """Create a research request for the given symbol.

    The pipeline executes asynchronously. Poll GET /api/research/{run_id}/status
    for completion. When complete, the memo is available at /memo/{memo_id}.
    """
    if not body.symbol or not body.symbol.strip():
        raise HTTPException(status_code=400, detail="Symbol is required")
    symbol = body.symbol.strip().upper()

    # In a full implementation, session comes from FastAPI dependency injection.
    # For now, return a 501 if no DB session is available.
    if session is None:
        raise HTTPException(
            status_code=501,
            detail="Research pipeline requires database session. "
                   "Configure DATABASE_URL and restart.",
        )

    result = DashboardResearchService.create_request(
        session, symbol, None,
    )
    return result


@router.get("/{run_id}/status")
def get_status(run_id: str):
    return {"run_id": run_id, "status": "pending"}


@router.get("/recent")
def list_recent():
    return {"requests": []}
