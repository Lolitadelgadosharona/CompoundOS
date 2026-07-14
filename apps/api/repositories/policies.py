from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from apps.api.models import (
    AuditEvent,
    InvestmentPolicy,
    InvestmentPolicyDraft,
    InvestmentPolicyDraftAllocation,
    InvestmentPolicyVersion,
    InvestmentPolicyVersionAllocation,
)

AUDIT_ACTOR = "local-owner"
POLICY_ENTITY_TYPE = "InvestmentPolicy"


def get_policy(
    session: Session, household_id: UUID, *, for_update: bool = False
) -> Optional[InvestmentPolicy]:
    statement = select(InvestmentPolicy).where(InvestmentPolicy.household_id == household_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_policy(session: Session, household_id: UUID) -> InvestmentPolicy:
    policy = InvestmentPolicy(household_id=household_id)
    session.add(policy)
    session.flush()
    return policy


def get_draft(
    session: Session, policy_id: UUID, *, for_update: bool = False
) -> Optional[InvestmentPolicyDraft]:
    statement = select(InvestmentPolicyDraft).where(InvestmentPolicyDraft.policy_id == policy_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_draft(
    session: Session,
    policy_id: UUID,
    *,
    values: Optional[dict[str, Any]] = None,
    source_version_id: Optional[UUID] = None,
) -> InvestmentPolicyDraft:
    draft = InvestmentPolicyDraft(
        policy_id=policy_id,
        source_version_id=source_version_id,
        **(values or {}),
    )
    session.add(draft)
    session.flush()
    return draft


def list_draft_allocations(
    session: Session, draft_id: UUID
) -> list[InvestmentPolicyDraftAllocation]:
    statement = (
        select(InvestmentPolicyDraftAllocation)
        .where(InvestmentPolicyDraftAllocation.draft_id == draft_id)
        .order_by(InvestmentPolicyDraftAllocation.sort_order.asc())
    )
    return list(session.scalars(statement))


def replace_draft_allocations(
    session: Session, draft_id: UUID, items: list[dict[str, Any]]
) -> list[InvestmentPolicyDraftAllocation]:
    session.execute(
        delete(InvestmentPolicyDraftAllocation).where(
            InvestmentPolicyDraftAllocation.draft_id == draft_id
        )
    )
    allocations = [InvestmentPolicyDraftAllocation(draft_id=draft_id, **item) for item in items]
    session.add_all(allocations)
    session.flush()
    return allocations


def get_current_published(
    session: Session, policy_id: UUID
) -> Optional[InvestmentPolicyVersion]:
    return session.scalar(
        select(InvestmentPolicyVersion).where(
            InvestmentPolicyVersion.policy_id == policy_id,
            InvestmentPolicyVersion.status == "published",
        )
    )


def get_version(
    session: Session, policy_id: UUID, version_number: int
) -> Optional[InvestmentPolicyVersion]:
    return session.scalar(
        select(InvestmentPolicyVersion).where(
            InvestmentPolicyVersion.policy_id == policy_id,
            InvestmentPolicyVersion.version_number == version_number,
        )
    )


def list_versions(
    session: Session,
    policy_id: UUID,
    *,
    before_version_number: Optional[int],
    limit: int,
) -> tuple[list[InvestmentPolicyVersion], Optional[int]]:
    statement = select(InvestmentPolicyVersion).where(
        InvestmentPolicyVersion.policy_id == policy_id
    )
    if before_version_number is not None:
        statement = statement.where(
            InvestmentPolicyVersion.version_number < before_version_number
        )
    versions = list(
        session.scalars(
            statement.order_by(InvestmentPolicyVersion.version_number.desc()).limit(limit + 1)
        )
    )
    has_more = len(versions) > limit
    page = versions[:limit]
    next_cursor = page[-1].version_number if has_more and page else None
    return page, next_cursor


def list_version_allocations(
    session: Session, version_id: UUID
) -> list[InvestmentPolicyVersionAllocation]:
    statement = (
        select(InvestmentPolicyVersionAllocation)
        .where(InvestmentPolicyVersionAllocation.version_id == version_id)
        .order_by(InvestmentPolicyVersionAllocation.sort_order.asc())
    )
    return list(session.scalars(statement))


def next_version_number(session: Session, policy_id: UUID) -> int:
    current = session.scalar(
        select(func.max(InvestmentPolicyVersion.version_number)).where(
            InvestmentPolicyVersion.policy_id == policy_id
        )
    )
    return (current or 0) + 1


def add_policy_audit_event(
    session: Session,
    *,
    household_id: UUID,
    policy_id: UUID,
    action: str,
    metadata: dict[str, Any],
) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        actor=AUDIT_ACTOR,
        action=action,
        entity_type=POLICY_ENTITY_TYPE,
        entity_id=policy_id,
        event_metadata=metadata,
    )
    session.add(event)
    session.flush()
    return event


def list_policy_audit_events(
    session: Session,
    *,
    household_id: UUID,
    policy_id: UUID,
    limit: int,
) -> list[AuditEvent]:
    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.household_id == household_id,
            AuditEvent.entity_type == POLICY_ENTITY_TYPE,
            AuditEvent.entity_id == policy_id,
        )
        .order_by(AuditEvent.sequence_number.desc())
        .limit(limit)
    )
    return list(reversed(list(session.scalars(statement))))
