"""Repository helpers for Decision Journal entities (Slice 3B)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.models import (
    AuditEvent,
    Decision,
    DecisionConfirmedSnapshot,
    DecisionCorrection,
    DecisionDraft,
    InvestmentPolicy,
    InvestmentPolicyVersion,
)

AUDIT_ACTOR = "local-owner"
DECISION_ENTITY_TYPE = "Decision"


def get_household_id(session: Session) -> Optional[UUID]:
    from apps.api.models import HouseholdProfile

    return session.scalar(select(HouseholdProfile.id))




def get_decision_for_household(
    session: Session,
    decision_id: UUID,
    household_id: UUID,
    *,
    for_update: bool = False,
) -> Optional[Decision]:
    statement = select(Decision).where(
        Decision.id == decision_id,
        Decision.household_id == household_id,
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_decision(session: Session, household_id: UUID) -> Decision:
    decision = Decision(household_id=household_id, status="draft")
    session.add(decision)
    session.flush()
    return decision


def get_draft(
    session: Session, decision_id: UUID, *, for_update: bool = False
) -> Optional[DecisionDraft]:
    statement = select(DecisionDraft).where(
        DecisionDraft.decision_id == decision_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def add_draft(
    session: Session,
    decision_id: UUID,
    *,
    values: Optional[dict[str, Any]] = None,
) -> DecisionDraft:
    draft = DecisionDraft(decision_id=decision_id, **(values or {}))
    session.add(draft)
    session.flush()
    return draft


def delete_draft(session: Session, draft: DecisionDraft) -> None:
    session.delete(draft)
    session.flush()


def list_decisions(
    session: Session,
    household_id: UUID,
    *,
    status_filter: Optional[str] = None,
    include_archived: bool = False,
) -> list[tuple[Decision, Optional[DecisionDraft], Optional[DecisionConfirmedSnapshot]]]:
    statement = select(Decision).where(Decision.household_id == household_id)
    if status_filter is not None:
        statement = statement.where(Decision.status == status_filter)
    elif not include_archived:
        statement = statement.where(Decision.status != "archived")

    decisions = list(session.scalars(statement.order_by(Decision.created_at.desc())))

    results: list[
        tuple[Decision, Optional[DecisionDraft], Optional[DecisionConfirmedSnapshot]]
    ] = []
    for decision in decisions:
        draft = session.scalar(
            select(DecisionDraft).where(DecisionDraft.decision_id == decision.id)
        )
        snapshot = session.scalar(
            select(DecisionConfirmedSnapshot).where(
                DecisionConfirmedSnapshot.decision_id == decision.id
            )
        )
        results.append((decision, draft, snapshot))
    return results


def get_snapshot(
    session: Session, decision_id: UUID
) -> Optional[DecisionConfirmedSnapshot]:
    return session.scalar(
        select(DecisionConfirmedSnapshot).where(
            DecisionConfirmedSnapshot.decision_id == decision_id
        )
    )


def add_snapshot(
    session: Session,
    *,
    decision_id: UUID,
    selected_policy_version_id: UUID,
    values: dict[str, Any],
) -> DecisionConfirmedSnapshot:
    snapshot = DecisionConfirmedSnapshot(
        decision_id=decision_id,
        selected_policy_version_id=selected_policy_version_id,
        **values,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def list_corrections(
    session: Session, decision_id: UUID
) -> list[DecisionCorrection]:
    statement = (
        select(DecisionCorrection)
        .where(DecisionCorrection.decision_id == decision_id)
        .order_by(DecisionCorrection.correction_number.asc())
    )
    return list(session.scalars(statement))


def get_latest_correction(
    session: Session, decision_id: UUID
) -> Optional[DecisionCorrection]:
    return session.scalar(
        select(DecisionCorrection)
        .where(DecisionCorrection.decision_id == decision_id)
        .order_by(DecisionCorrection.correction_number.desc())
        .limit(1)
    )


def next_correction_number(session: Session, decision_id: UUID) -> int:
    current = session.scalar(
        select(func.max(DecisionCorrection.correction_number)).where(
            DecisionCorrection.decision_id == decision_id
        )
    )
    return (current or 0) + 1


def add_correction(
    session: Session,
    *,
    decision_id: UUID,
    corrected_entry_id: UUID,
    correction_number: int,
    values: dict[str, Any],
) -> DecisionCorrection:
    correction = DecisionCorrection(
        decision_id=decision_id,
        corrected_entry_id=corrected_entry_id,
        correction_number=correction_number,
        **values,
    )
    session.add(correction)
    session.flush()
    return correction


def get_policy_for_household(
    session: Session, household_id: UUID, *, for_update: bool = False
) -> Optional[InvestmentPolicy]:
    statement = select(InvestmentPolicy).where(
        InvestmentPolicy.household_id == household_id
    )
    if for_update:
        statement = statement.with_for_update()
    return session.scalar(statement)


def get_current_published_version(
    session: Session, policy_id: UUID
) -> Optional[InvestmentPolicyVersion]:
    return session.scalar(
        select(InvestmentPolicyVersion).where(
            InvestmentPolicyVersion.policy_id == policy_id,
            InvestmentPolicyVersion.status == "published",
        )
    )


def add_decision_audit_event(
    session: Session,
    *,
    household_id: UUID,
    decision_id: UUID,
    action: str,
    metadata: dict[str, Any],
) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        actor=AUDIT_ACTOR,
        action=action,
        entity_type=DECISION_ENTITY_TYPE,
        entity_id=decision_id,
        event_metadata=metadata,
    )
    session.add(event)
    session.flush()
    return event


def list_decision_audit_events(
    session: Session,
    *,
    household_id: UUID,
    decision_id: UUID,
    before_sequence_number: Optional[int] = None,
    limit: int = 50,
) -> tuple[list[AuditEvent], Optional[int]]:
    statement = (
        select(AuditEvent)
        .where(
            AuditEvent.household_id == household_id,
            AuditEvent.entity_type == DECISION_ENTITY_TYPE,
            AuditEvent.entity_id == decision_id,
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
