"""Repository layer for Sprint 010 Slice A — Committee Integration Bridge."""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import CommitteeReviewRequest


def create_review_request(
    session: Session,
    investment_idea_id: UUID,
    *,
    requested_by: str = "owner",
    notes: Optional[str] = None,
) -> CommitteeReviewRequest:
    request = CommitteeReviewRequest(
        id=uuid4(),
        investment_idea_id=investment_idea_id,
        requested_by=requested_by,
        notes=notes,
    )
    session.add(request)
    session.flush()
    return request


def get_review_request(
    session: Session, request_id: UUID, *, for_update: bool = False,
) -> Optional[CommitteeReviewRequest]:
    stmt = select(CommitteeReviewRequest).where(CommitteeReviewRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update()
    return session.scalar(stmt)


def list_review_requests_for_idea(
    session: Session, idea_id: UUID,
) -> list[CommitteeReviewRequest]:
    return list(
        session.scalars(
            select(CommitteeReviewRequest)
            .where(CommitteeReviewRequest.investment_idea_id == idea_id)
            .order_by(CommitteeReviewRequest.requested_at.desc())
        )
    )


def list_pending_reviews(session: Session) -> list[CommitteeReviewRequest]:
    return list(
        session.scalars(
            select(CommitteeReviewRequest)
            .where(CommitteeReviewRequest.status == "pending")
            .order_by(CommitteeReviewRequest.requested_at.asc())
        )
    )


def update_review_request(
    session: Session, request_id: UUID, **fields,
) -> Optional[CommitteeReviewRequest]:
    req = get_review_request(session, request_id, for_update=True)
    if req is None:
        return None
    for key, value in fields.items():
        if value is not None and hasattr(req, key):
            setattr(req, key, value)
    session.flush()
    return req
