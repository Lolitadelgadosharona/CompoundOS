"""Repository layer for Sprint 009 Slice C — Investment Idea + Decision Bridge."""

from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import IdeaStatusHistory, InvestmentIdea

# ═══════════════════════════════════════════════════════════════════════
# Investment Ideas
# ═══════════════════════════════════════════════════════════════════════


def get_idea(
    session: Session, idea_id: UUID, *, for_update: bool = False,
) -> Optional[InvestmentIdea]:
    statement = select(InvestmentIdea).where(InvestmentIdea.id == idea_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def create_idea(session: Session, household_id: UUID, **kwargs) -> InvestmentIdea:
    idea = InvestmentIdea(id=uuid4(), household_id=household_id, **kwargs)
    session.add(idea)
    session.flush()
    return idea


def list_ideas(
    session: Session,
    household_id: UUID,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[InvestmentIdea]:
    statement = (
        select(InvestmentIdea)
        .where(InvestmentIdea.household_id == household_id)
        .order_by(InvestmentIdea.updated_at.desc())
        .limit(limit)
    )
    if status is not None:
        statement = statement.where(InvestmentIdea.status == status)
    return list(session.scalars(statement))


def update_idea_fields(
    session: Session, idea_id: UUID, **fields,
) -> Optional[InvestmentIdea]:
    idea = get_idea(session, idea_id, for_update=True)
    if idea is None:
        return None
    for key, value in fields.items():
        if hasattr(idea, key) and value is not None:
            setattr(idea, key, value)
    session.flush()
    return idea


def transition_idea_status(
    session: Session, idea_id: UUID, new_status: str, reason: Optional[str] = None,
) -> Optional[InvestmentIdea]:
    idea = get_idea(session, idea_id, for_update=True)
    if idea is None:
        return None
    idea.status = new_status
    if reason is not None:
        idea.status_change_reason = reason
    session.flush()
    return idea


# ═══════════════════════════════════════════════════════════════════════
# Status History
# ═══════════════════════════════════════════════════════════════════════


def list_idea_history(
    session: Session, idea_id: UUID,
) -> list[IdeaStatusHistory]:
    statement = (
        select(IdeaStatusHistory)
        .where(IdeaStatusHistory.idea_id == idea_id)
        .order_by(IdeaStatusHistory.changed_at.asc())
    )
    return list(session.scalars(statement))
