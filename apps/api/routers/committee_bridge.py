"""Committee bridge router — Idea → Committee review endpoints.

Sprint 010 Slice A — Committee Integration Bridge.
Owner authentication only. AI never initiates review.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.committee_bridge_schemas import (
    CommitteeReviewRequestCreate,
    CommitteeReviewRequestResponse,
)
from apps.api.database import get_session
from apps.api.repositories.committee_bridge import (
    create_review_request,
    list_review_requests_for_idea,
)

router = APIRouter(prefix="/api/ideas", tags=["committee-bridge"])


@router.post(
    "/{idea_id}/request-review",
    response_model=CommitteeReviewRequestResponse,
)
def request_committee_review(
    idea_id: str,
    body: CommitteeReviewRequestCreate,
    session: Session = Depends(get_session),
) -> CommitteeReviewRequestResponse:
    """Owner requests AI Committee review for an Investment Idea."""
    from uuid import UUID as _UUID

    try:
        idea_uuid = _UUID(idea_id)
    except ValueError:
        raise HTTPException(400, "Invalid idea ID format")

    # Verify idea exists
    from apps.api.models import InvestmentIdea
    idea = session.scalar(
        __import__("sqlalchemy").select(InvestmentIdea).where(
            InvestmentIdea.id == idea_uuid,
        )
    )
    if idea is None:
        raise HTTPException(404, f"Idea {idea_id} not found")

    # Only allow one active review per idea
    existing = list_review_requests_for_idea(session, idea_uuid)
    active = [r for r in existing if r.status in ("pending", "in_progress")]
    if active:
        raise HTTPException(
            409,
            f"Idea already has an active review request (status: {active[0].status})",
        )

    request = create_review_request(
        session, idea_uuid, notes=body.notes,
    )
    session.commit()
    return request


@router.get(
    "/{idea_id}/reviews",
    response_model=list[CommitteeReviewRequestResponse],
)
def list_idea_reviews(
    idea_id: str,
    session: Session = Depends(get_session),
) -> list[CommitteeReviewRequestResponse]:
    """List all review requests for an Investment Idea."""
    from uuid import UUID as _UUID

    try:
        idea_uuid = _UUID(idea_id)
    except ValueError:
        raise HTTPException(400, "Invalid idea ID format")

    return list_review_requests_for_idea(session, idea_uuid)
