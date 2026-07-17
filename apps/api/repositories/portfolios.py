from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.models import (
    AuditEvent,
    Portfolio,
    PortfolioDraft,
    PortfolioDraftHolding,
    PortfolioSnapshot,
    PortfolioSnapshotHolding,
)

AUDIT_ACTOR = "local-owner"
PORTFOLIO_ENTITY_TYPE = "portfolio"


def get_portfolio(
    session: Session, household_id: UUID, *, for_update: bool = False
) -> Optional[Portfolio]:
    statement = select(Portfolio).where(Portfolio.household_id == household_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_portfolio(session: Session, household_id: UUID) -> Portfolio:
    portfolio = Portfolio(household_id=household_id, status="draft")
    session.add(portfolio)
    session.flush()
    return portfolio


def get_draft(
    session: Session, portfolio_id: UUID, *, for_update: bool = False
) -> Optional[PortfolioDraft]:
    statement = select(PortfolioDraft).where(
        PortfolioDraft.portfolio_id == portfolio_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_draft(session: Session, portfolio_id: UUID) -> PortfolioDraft:
    draft = PortfolioDraft(portfolio_id=portfolio_id)
    session.add(draft)
    session.flush()
    return draft


def list_draft_holdings(
    session: Session, portfolio_id: UUID
) -> list[PortfolioDraftHolding]:
    statement = (
        select(PortfolioDraftHolding)
        .where(PortfolioDraftHolding.portfolio_id == portfolio_id)
        .order_by(PortfolioDraftHolding.sort_order.asc())
    )
    return list(session.scalars(statement))


def replace_draft_holdings(
    session: Session, portfolio_id: UUID, items: list[dict[str, Any]]
) -> list[PortfolioDraftHolding]:
    session.execute(
        delete(PortfolioDraftHolding).where(
            PortfolioDraftHolding.portfolio_id == portfolio_id
        )
    )
    holdings = [
        PortfolioDraftHolding(portfolio_id=portfolio_id, **item) for item in items
    ]
    session.add_all(holdings)
    session.flush()
    return holdings


def get_latest_snapshot(
    session: Session, portfolio_id: UUID
) -> Optional[PortfolioSnapshot]:
    return session.scalar(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        .order_by(PortfolioSnapshot.version_number.desc())
        .limit(1)
    )


def get_current_snapshot(
    session: Session, portfolio_id: UUID
) -> Optional[PortfolioSnapshot]:
    return session.scalar(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.portfolio_id == portfolio_id,
            PortfolioSnapshot.status == "current",
        )
    )


def get_snapshot_by_id(
    session: Session, snapshot_id: UUID
) -> Optional[PortfolioSnapshot]:
    return session.scalar(
        select(PortfolioSnapshot).where(PortfolioSnapshot.id == snapshot_id)
    )


def list_snapshot_holdings(
    session: Session, snapshot_id: UUID
) -> list[PortfolioSnapshotHolding]:
    statement = (
        select(PortfolioSnapshotHolding)
        .where(PortfolioSnapshotHolding.snapshot_id == snapshot_id)
        .order_by(PortfolioSnapshotHolding.sort_order.asc())
    )
    return list(session.scalars(statement))


def has_any_snapshot(session: Session, portfolio_id: UUID) -> bool:
    return (
        session.scalar(
            select(func.count())
            .select_from(PortfolioSnapshot)
            .where(PortfolioSnapshot.portfolio_id == portfolio_id)
        )
        or 0
    ) > 0


def next_version_number(session: Session, portfolio_id: UUID) -> int:
    current = session.scalar(
        select(func.max(PortfolioSnapshot.version_number)).where(
            PortfolioSnapshot.portfolio_id == portfolio_id
        )
    )
    return (current or 0) + 1


def list_snapshots(
    session: Session,
    portfolio_id: UUID,
    *,
    before_version_number: Optional[int],
    limit: int,
) -> tuple[list[PortfolioSnapshot], Optional[int]]:
    statement = select(PortfolioSnapshot).where(
        PortfolioSnapshot.portfolio_id == portfolio_id
    )
    if before_version_number is not None:
        statement = statement.where(
            PortfolioSnapshot.version_number < before_version_number
        )
    snapshots = list(
        session.scalars(
            statement.order_by(PortfolioSnapshot.version_number.desc()).limit(
                limit + 1
            )
        )
    )
    has_more = len(snapshots) > limit
    page = snapshots[:limit]
    next_cursor = page[-1].version_number if has_more and page else None
    return page, next_cursor


def add_portfolio_audit_event(
    session: Session,
    *,
    household_id: UUID,
    portfolio_id: UUID,
    action: str,
    metadata: dict[str, Any],
) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        actor=AUDIT_ACTOR,
        action=action,
        entity_type=PORTFOLIO_ENTITY_TYPE,
        entity_id=portfolio_id,
        event_metadata=metadata,
    )
    session.add(event)
    session.flush()
    return event


def list_portfolio_audit_events(
    session: Session,
    *,
    household_id: UUID,
    portfolio_id: UUID,
    before_sequence_number: Optional[int],
    limit: int,
) -> tuple[list[AuditEvent], Optional[int]]:
    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.household_id == household_id,
            AuditEvent.entity_type == PORTFOLIO_ENTITY_TYPE,
            AuditEvent.entity_id == portfolio_id,
        )
    )
    if before_sequence_number is not None:
        statement = statement.where(
            AuditEvent.sequence_number < before_sequence_number
        )
    events = list(
        session.scalars(
            statement.order_by(AuditEvent.sequence_number.desc()).limit(limit + 1)
        )
    )
    has_more = len(events) > limit
    page = events[:limit]
    next_cursor = page[-1].sequence_number if has_more and page else None
    return list(reversed(page)), next_cursor
