"""Router for Sprint 010 Slice C — Wealth Dashboard + Learning Loop."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.dashboard_schemas import (
    DashboardSnapshot,
    DecisionReviewResponse,
)
from apps.api.database import get_session
from apps.api.services.dashboard_service import (
    build_dashboard,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardSnapshot)
def get_dashboard(
    session: Session = Depends(get_session),
) -> DashboardSnapshot:
    """Read-only wealth dashboard snapshot."""
    # Get the first household (single-owner system)
    from apps.api.models import HouseholdProfile
    hh = session.execute(
        __import__("sqlalchemy").select(
            HouseholdProfile.id,
        ).limit(1),
    ).scalar()
    if hh is None:
        raise HTTPException(404, "No household found")
    return build_dashboard(session, hh)


@router.get("/reviews/due", response_model=list[DecisionReviewResponse])
def list_due_reviews(
    session: Session = Depends(get_session),
) -> list[DecisionReviewResponse]:
    """List decision reviews that are due (scheduled_at <= today, not completed)."""
    from apps.api.models import DecisionReview
    today = date.today()
    reviews = session.execute(
        __import__("sqlalchemy").select(DecisionReview).where(
            DecisionReview.scheduled_at <= today,
            DecisionReview.completed_at.is_(None),
        ).order_by(DecisionReview.scheduled_at),
    ).scalars().all()
    return [DecisionReviewResponse(
        id=r.id, decision_id=r.decision_id,
        investment_idea_id=r.investment_idea_id,
        review_type=r.review_type, scheduled_at=r.scheduled_at,
        completed_at=r.completed_at,
        outcome_notes=r.outcome_notes,
        actual_return_pct=(
            str(r.actual_return_pct) if r.actual_return_pct else None
        ),
        policy_compliant=r.policy_compliant,
        lessons_learned=r.lessons_learned,
        created_at=r.created_at, updated_at=r.updated_at,
    ) for r in reviews]


@router.patch(
    "/reviews/{review_id}", response_model=DecisionReviewResponse,
)
def complete_review(
    review_id: UUID,
    outcome_notes: Optional[str] = None,
    actual_return_pct: Optional[str] = None,
    policy_compliant: Optional[bool] = None,
    lessons_learned: Optional[str] = None,
    session: Session = Depends(get_session),
) -> DecisionReviewResponse:
    """Complete a scheduled review with outcome data."""
    from decimal import Decimal as _D

    from apps.api.models import DecisionReview

    review = session.get(DecisionReview, review_id)
    if review is None:
        raise HTTPException(404, "Review not found")
    if review.completed_at is not None:
        raise HTTPException(409, "Review already completed")

    if outcome_notes is not None:
        review.outcome_notes = outcome_notes
    if actual_return_pct is not None:
        review.actual_return_pct = _D(actual_return_pct)
    if policy_compliant is not None:
        review.policy_compliant = policy_compliant
    if lessons_learned is not None:
        review.lessons_learned = lessons_learned
    review.completed_at = datetime.now(timezone.utc)
    review.updated_at = datetime.now(timezone.utc)

    session.commit()

    return DecisionReviewResponse(
        id=review.id, decision_id=review.decision_id,
        investment_idea_id=review.investment_idea_id,
        review_type=review.review_type,
        scheduled_at=review.scheduled_at,
        completed_at=review.completed_at,
        outcome_notes=review.outcome_notes,
        actual_return_pct=(
            str(review.actual_return_pct)
            if review.actual_return_pct else None
        ),
        policy_compliant=review.policy_compliant,
        lessons_learned=review.lessons_learned,
        created_at=review.created_at, updated_at=review.updated_at,
    )
