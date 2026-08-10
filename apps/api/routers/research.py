"""Research Foundation router — Sprint 011 Slice A.

Owner-triggered research endpoints. AI cannot initiate research.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.research_schemas import (
    ResearchRequestCreate,
    ResearchRequestResponse,
    ResearchRunResponse,
)

router = APIRouter(prefix="/api/research", tags=["research"])


# ═══════════════════════════════════════════════════════════════════════
# POST /api/research/request  —  Owner requests AI research
# ═══════════════════════════════════════════════════════════════════════


@router.post("/request", response_model=ResearchRequestResponse)
def request_research(
    body: ResearchRequestCreate,
    session: Session = Depends(get_session),
) -> ResearchRequestResponse:
    """Owner requests AI research for a committee review.

    AI CANNOT trigger this — only the Owner (via X-API-Key) may call it.
    """
    # Verify review request exists and fetch its idea
    review = session.execute(
        text(
            "SELECT id, investment_idea_id, status"
            " FROM committee_review_requests WHERE id = :rid"
        ),
        {"rid": body.review_request_id},
    ).fetchone()
    if review is None:
        raise HTTPException(404, "Review request not found")

    # One active research request per review
    existing = session.execute(
        text(
            "SELECT 1 FROM research_requests"
            " WHERE review_request_id = :rid"
        ),
        {"rid": body.review_request_id},
    ).fetchone()
    if existing is not None:
        raise HTTPException(409, "Research already requested for this review")

    rid = uuid4()
    now = datetime.now(timezone.utc)
    session.execute(
        text(
            "INSERT INTO research_requests"
            " (id, review_request_id, investment_idea_id, status, parameters,"
            " created_at, updated_at)"
            " VALUES (:id, :rrid, :iid, 'pending', :params, :now, :now)"
        ),
        {
            "id": rid, "rrid": body.review_request_id,
            "iid": review[1], "params": body.parameters, "now": now,
        },
    )
    session.commit()

    return ResearchRequestResponse(
        id=rid, review_request_id=body.review_request_id,
        investment_idea_id=review[1], status="pending",
        parameters=body.parameters, created_at=now, updated_at=now,
    )


# ═══════════════════════════════════════════════════════════════════════
# GET /api/research/{id}/status  —  Research request status
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{request_id}", response_model=ResearchRequestResponse)
def get_research_status(
    request_id: UUID,
    session: Session = Depends(get_session),
) -> ResearchRequestResponse:
    r = session.execute(
        text(
            "SELECT id, review_request_id, investment_idea_id, status,"
            " parameters, created_at, updated_at"
            " FROM research_requests WHERE id = :rid"
        ),
        {"rid": request_id},
    ).fetchone()
    if r is None:
        raise HTTPException(404, "Research request not found")

    return ResearchRequestResponse(
        id=r[0], review_request_id=r[1], investment_idea_id=r[2],
        status=r[3], parameters=r[4], created_at=r[5], updated_at=r[6],
    )


# ═══════════════════════════════════════════════════════════════════════
# GET /api/research/{id}/runs  —  List runs for a request
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{request_id}/runs", response_model=list[ResearchRunResponse])
def list_research_runs(
    request_id: UUID,
    session: Session = Depends(get_session),
) -> list[ResearchRunResponse]:
    # Verify request exists
    req = session.execute(
        text("SELECT 1 FROM research_requests WHERE id = :rid"),
        {"rid": request_id},
    ).fetchone()
    if req is None:
        raise HTTPException(404, "Research request not found")

    rows = session.execute(
        text(
            "SELECT id, request_id, run_number, status, started_at,"
            " completed_at, error_message, created_at"
            " FROM research_runs"
            " WHERE request_id = :rid ORDER BY run_number ASC"
        ),
        {"rid": request_id},
    ).fetchall()

    return [
        ResearchRunResponse(
            id=r[0], request_id=r[1], run_number=r[2], status=r[3],
            started_at=r[4], completed_at=r[5], error_message=r[6],
            created_at=r[7],
        )
        for r in rows
    ]
