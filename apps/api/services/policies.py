from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import (
    AuditEvent,
    InvestmentPolicy,
    InvestmentPolicyDraft,
    InvestmentPolicyDraftAllocation,
    InvestmentPolicyVersion,
    InvestmentPolicyVersionAllocation,
)
from apps.api.policy_schemas import (
    POLICY_TEXT_FIELDS,
    AllocationReplaceRequest,
    AllocationResponse,
    CreatePolicyDraftRequest,
    PersonalPolicySetupRequest,
    PolicyDraftResponse,
    PolicyDraftUpdate,
    PublishPolicyDraftRequest,
    normalize_asset_class_name,
)
from apps.api.repositories.households import get_current_household
from apps.api.repositories.policies import (
    add_draft,
    add_policy,
    add_policy_audit_event,
    get_current_published,
    get_draft,
    get_policy,
    get_version,
    list_draft_allocations,
    list_policy_audit_events,
    list_version_allocations,
    list_versions,
    next_version_number,
    replace_draft_allocations,
)


class PolicyNotFoundError(Exception):
    pass


class HouseholdRequiredError(Exception):
    pass


class PolicyAlreadyExistsError(Exception):
    pass


class DraftNotFoundError(Exception):
    pass


class DraftAlreadyExistsError(Exception):
    pass


class DraftConflictError(Exception):
    pass


class NoPolicyChangesError(Exception):
    pass


class PolicyIncompleteError(Exception):
    pass


class PublishedVersionNotFoundError(Exception):
    pass


class PolicyVersionNotFoundError(Exception):
    pass


def _constraint_name(exc: IntegrityError) -> Optional[str]:
    diagnostics = getattr(exc.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


def _require_household(session: Session):
    household = get_current_household(session)
    if household is None:
        raise HouseholdRequiredError
    return household


def _require_policy(
    session: Session, household_id: UUID, *, for_update: bool = False
) -> InvestmentPolicy:
    policy = get_policy(session, household_id, for_update=for_update)
    if policy is None:
        raise PolicyNotFoundError
    return policy


def _require_draft(
    session: Session, policy_id: UUID, *, for_update: bool = False
) -> InvestmentPolicyDraft:
    draft = get_draft(session, policy_id, for_update=for_update)
    if draft is None:
        raise DraftNotFoundError
    return draft


def _require_mutable_draft(
    session: Session, policy_id: UUID
) -> InvestmentPolicyDraft:
    draft = get_draft(session, policy_id, for_update=True)
    if draft is not None:
        return draft
    if get_current_published(session, policy_id) is not None:
        raise DraftConflictError
    raise DraftNotFoundError


def create_policy(
    session: Session,
) -> tuple[InvestmentPolicy, InvestmentPolicyDraft, list[InvestmentPolicyDraftAllocation]]:
    try:
        with session.begin():
            household = _require_household(session)
            policy = add_policy(session, household.id)
            draft = add_draft(session, policy.id)
            add_policy_audit_event(
                session,
                household_id=household.id,
                policy_id=policy.id,
                action="policy.created",
                metadata={},
            )
            add_policy_audit_event(
                session,
                household_id=household.id,
                policy_id=policy.id,
                action="policy.draft.created",
                metadata={"draft_revision": draft.revision},
            )
        return policy, draft, []
    except IntegrityError as exc:
        session.rollback()
        if _constraint_name(exc) != "uq_investment_policies_household_id":
            raise
        raise PolicyAlreadyExistsError from exc


def read_current_policy(session: Session) -> InvestmentPolicy:
    household = _require_household(session)
    return _require_policy(session, household.id)


def read_current_draft(
    session: Session,
) -> tuple[InvestmentPolicyDraft, list[InvestmentPolicyDraftAllocation]]:
    policy = read_current_policy(session)
    draft = _require_draft(session, policy.id)
    return draft, list_draft_allocations(session, draft.id)


def update_draft_text(
    session: Session, payload: PolicyDraftUpdate
) -> PolicyDraftResponse:
    submitted = payload.model_dump(exclude={"expected_revision"}, exclude_unset=True)
    if not submitted:
        raise NoPolicyChangesError

    with session.begin():
        household = _require_household(session)
        policy = _require_policy(session, household.id, for_update=True)
        draft = _require_mutable_draft(session, policy.id)
        if draft.revision != payload.expected_revision:
            raise DraftConflictError
        changed = sorted(
            name for name, value in submitted.items() if getattr(draft, name) != value
        )
        if not changed:
            raise NoPolicyChangesError
        for name in changed:
            setattr(draft, name, submitted[name])
        draft.revision += 1
        now = datetime.now(timezone.utc)
        draft.updated_at = now
        policy.updated_at = now
        session.flush()
        add_policy_audit_event(
            session,
            household_id=household.id,
            policy_id=policy.id,
            action="policy.draft.updated",
            metadata={"changed_fields": changed, "draft_revision": draft.revision},
        )
        allocations = list_draft_allocations(session, draft.id)
        snapshot_values = {
            name: getattr(draft, name)
            for name in PolicyDraftResponse.model_fields
            if name != "allocations"
        }
        snapshot_values["allocations"] = [
            AllocationResponse.model_validate(item) for item in allocations
        ]
        snapshot = PolicyDraftResponse.model_validate(snapshot_values)
    return snapshot


def _allocation_values(payload: AllocationReplaceRequest) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for sort_order, item in enumerate(payload.items):
        display_name, canonical_name = normalize_asset_class_name(item.asset_class_name)
        values.append(
            {
                "asset_class_name": display_name,
                "normalized_asset_class_name": canonical_name,
                "target_percentage": Decimal(item.target_percentage),
                "sort_order": sort_order,
            }
        )
    return values


def replace_allocations(
    session: Session, payload: AllocationReplaceRequest
) -> tuple[InvestmentPolicyDraft, list[InvestmentPolicyDraftAllocation]]:
    values = _allocation_values(payload)
    with session.begin():
        household = _require_household(session)
        policy = _require_policy(session, household.id, for_update=True)
        draft = _require_mutable_draft(session, policy.id)
        if draft.revision != payload.expected_revision:
            raise DraftConflictError
        existing = list_draft_allocations(session, draft.id)
        existing_signature = [
            (
                item.asset_class_name,
                item.normalized_asset_class_name,
                item.target_percentage,
                item.sort_order,
            )
            for item in existing
        ]
        proposed_signature = [
            (
                item["asset_class_name"],
                item["normalized_asset_class_name"],
                item["target_percentage"],
                item["sort_order"],
            )
            for item in values
        ]
        if existing_signature == proposed_signature:
            raise NoPolicyChangesError
        allocations = replace_draft_allocations(session, draft.id, values)
        draft.revision += 1
        now = datetime.now(timezone.utc)
        draft.updated_at = now
        policy.updated_at = now
        session.flush()
        add_policy_audit_event(
            session,
            household_id=household.id,
            policy_id=policy.id,
            action="policy.draft.updated",
            metadata={
                "changed_fields": ["allocations"],
                "draft_revision": draft.revision,
                "allocation_item_count": len(allocations),
            },
        )
    return draft, allocations


def discard_draft(session: Session, expected_revision: int) -> None:
    with session.begin():
        household = _require_household(session)
        policy = _require_policy(session, household.id, for_update=True)
        draft = _require_mutable_draft(session, policy.id)
        if draft.revision != expected_revision:
            raise DraftConflictError
        revision = draft.revision
        session.delete(draft)
        policy.updated_at = datetime.now(timezone.utc)
        session.flush()
        add_policy_audit_event(
            session,
            household_id=household.id,
            policy_id=policy.id,
            action="policy.draft.discarded",
            metadata={"draft_revision": revision},
        )


def create_new_draft(
    session: Session, payload: CreatePolicyDraftRequest
) -> tuple[InvestmentPolicyDraft, list[InvestmentPolicyDraftAllocation]]:
    try:
        with session.begin():
            household = _require_household(session)
            policy = _require_policy(session, household.id, for_update=True)
            if get_draft(session, policy.id) is not None:
                raise DraftAlreadyExistsError

            source = None
            source_allocations: list[InvestmentPolicyVersionAllocation] = []
            values: dict[str, object] = {}
            if payload.source_version_id is not None:
                source = get_current_published(session, policy.id)
                if source is None or source.id != payload.source_version_id:
                    raise DraftConflictError
                values = {name: getattr(source, name) for name in POLICY_TEXT_FIELDS}
                source_allocations = list_version_allocations(session, source.id)

            draft = add_draft(
                session,
                policy.id,
                values=values,
                source_version_id=source.id if source is not None else None,
            )
            allocation_values = [
                {
                    "asset_class_name": item.asset_class_name,
                    "normalized_asset_class_name": item.normalized_asset_class_name,
                    "target_percentage": item.target_percentage,
                    "sort_order": item.sort_order,
                }
                for item in source_allocations
            ]
            allocations = replace_draft_allocations(session, draft.id, allocation_values)
            policy.updated_at = datetime.now(timezone.utc)
            metadata = {"draft_revision": draft.revision}
            if source is not None:
                metadata["source_version_number"] = source.version_number
            add_policy_audit_event(
                session,
                household_id=household.id,
                policy_id=policy.id,
                action="policy.draft.created",
                metadata=metadata,
            )
        return draft, allocations
    except IntegrityError as exc:
        session.rollback()
        if _constraint_name(exc) != "uq_investment_policy_drafts_policy_id":
            raise
        raise DraftAlreadyExistsError from exc


def publish_draft(
    session: Session, payload: PublishPolicyDraftRequest
) -> tuple[InvestmentPolicyVersion, list[InvestmentPolicyVersionAllocation]]:
    try:
        with session.begin():
            household = _require_household(session)
            policy = _require_policy(session, household.id, for_update=True)
            draft = get_draft(session, policy.id, for_update=True)
            if draft is None:
                raise DraftConflictError
            if draft.revision != payload.expected_revision:
                raise DraftConflictError
            required_fields = ("objectives", "time_horizon", "decision_process")
            if any(not getattr(draft, name).strip() for name in required_fields):
                raise PolicyIncompleteError

            draft_allocations = list_draft_allocations(session, draft.id)
            if not draft_allocations or sum(
                (item.target_percentage for item in draft_allocations), Decimal("0.00")
            ) != Decimal("100.00"):
                raise PolicyIncompleteError

            version_number = next_version_number(session, policy.id)
            current = get_current_published(session, policy.id)
            if current is not None:
                current.status = "superseded"
                current.superseded_at = datetime.now(timezone.utc)
                session.flush()
                add_policy_audit_event(
                    session,
                    household_id=household.id,
                    policy_id=policy.id,
                    action="policy.superseded",
                    metadata={"version_number": current.version_number},
                )

            now = datetime.now(timezone.utc)
            version = InvestmentPolicyVersion(
                policy_id=policy.id,
                version_number=version_number,
                status="published",
                published_at=now,
                **{name: getattr(draft, name) for name in POLICY_TEXT_FIELDS},
            )
            session.add(version)
            session.flush()
            allocations = [
                InvestmentPolicyVersionAllocation(
                    version_id=version.id,
                    asset_class_name=item.asset_class_name,
                    normalized_asset_class_name=item.normalized_asset_class_name,
                    target_percentage=item.target_percentage,
                    sort_order=item.sort_order,
                )
                for item in draft_allocations
            ]
            session.add_all(allocations)
            session.flush()
            version.sealed_at = now
            session.flush()
            session.delete(draft)
            policy.updated_at = now
            session.flush()
            add_policy_audit_event(
                session,
                household_id=household.id,
                policy_id=policy.id,
                action="policy.published",
                metadata={
                    "version_number": version.version_number,
                    "allocation_item_count": len(allocations),
                },
            )
        return version, allocations
    except IntegrityError as exc:
        session.rollback()
        if _constraint_name(exc) not in {
            "uq_investment_policy_versions_current_published",
            "uq_investment_policy_versions_policy_version",
        }:
            raise
        raise DraftConflictError from exc


def read_current_published(
    session: Session,
) -> tuple[InvestmentPolicyVersion, list[InvestmentPolicyVersionAllocation]]:
    policy = read_current_policy(session)
    version = get_current_published(session, policy.id)
    if version is None:
        raise PublishedVersionNotFoundError
    return version, list_version_allocations(session, version.id)


def read_version_history(
    session: Session,
    *,
    before_version_number: Optional[int],
    limit: int,
) -> tuple[list[InvestmentPolicyVersion], Optional[int]]:
    policy = read_current_policy(session)
    return list_versions(
        session,
        policy.id,
        before_version_number=before_version_number,
        limit=limit,
    )


def read_version(
    session: Session, version_number: int
) -> tuple[InvestmentPolicyVersion, list[InvestmentPolicyVersionAllocation]]:
    policy = read_current_policy(session)
    version = get_version(session, policy.id, version_number)
    if version is None:
        raise PolicyVersionNotFoundError
    return version, list_version_allocations(session, version.id)


def read_policy_audit_events(session: Session, limit: int) -> list[AuditEvent]:
    household = _require_household(session)
    policy = _require_policy(session, household.id)
    return list_policy_audit_events(
        session,
        household_id=household.id,
        policy_id=policy.id,
        limit=limit,
    )


def setup_personal_policy(
    session: Session, payload: PersonalPolicySetupRequest
) -> InvestmentPolicyVersion:
    """One-shot Personal Edition policy setup (PE-003).

    Runs in a single transaction: ensure policy + draft exist → fill the
    simple setup fields → default equities/cash allocation → publish.
    Uses the repository primitives directly (no governance bypass, no
    silent auto-approval).
    """
    now = datetime.now(timezone.utc)
    with session.begin():
        household = _require_household(session)

        policy = get_policy(session, household.id)
        if policy is None:
            policy = add_policy(session, household.id)
            add_policy_audit_event(
                session,
                household_id=household.id,
                policy_id=policy.id,
                action="policy.created",
                metadata={},
            )
            draft = add_draft(session, policy.id)
        else:
            draft = get_draft(session, policy.id)
            if draft is None:
                draft = add_draft(session, policy.id)

        # Fill the simple setup fields onto the draft text columns.
        notes = json.dumps({
            "risk_preference": payload.risk_preference,
            "max_single_position_pct": payload.max_single_position_pct,
            "min_cash_pct": payload.min_cash_pct,
        })
        draft.objectives = payload.investment_goal
        draft.time_horizon = payload.investment_horizon
        draft.decision_process = payload.principles
        draft.notes = notes
        draft.revision += 1
        draft.updated_at = now
        policy.updated_at = now
        session.flush()

        # Default allocation: equities + cash derived from min_cash_pct.
        allocation_items = [{
            "asset_class_name": "Equities",
            "normalized_asset_class_name": "equities",
            "target_percentage": Decimal(100 - payload.min_cash_pct),
            "sort_order": 0,
        }]
        if payload.min_cash_pct > 0:
            allocation_items.append({
                "asset_class_name": "Cash",
                "normalized_asset_class_name": "cash",
                "target_percentage": Decimal(payload.min_cash_pct),
                "sort_order": 1,
            })
        replace_draft_allocations(session, draft.id, allocation_items)

        # Publish: supersede current → create version → seal → delete draft.
        version_number = next_version_number(session, policy.id)
        current = get_current_published(session, policy.id)
        if current is not None:
            current.status = "superseded"
            current.superseded_at = now
        version = InvestmentPolicyVersion(
            policy_id=policy.id,
            version_number=version_number,
            status="published",
            published_at=now,
            **{name: getattr(draft, name) for name in POLICY_TEXT_FIELDS},
        )
        session.add(version)
        session.flush()
        draft_allocations = list_draft_allocations(session, draft.id)
        session.add_all([
            InvestmentPolicyVersionAllocation(
                version_id=version.id,
                asset_class_name=item.asset_class_name,
                normalized_asset_class_name=item.normalized_asset_class_name,
                target_percentage=item.target_percentage,
                sort_order=item.sort_order,
            )
            for item in draft_allocations
        ])
        session.flush()
        version.sealed_at = now
        session.flush()
        session.delete(draft)
        add_policy_audit_event(
            session,
            household_id=household.id,
            policy_id=policy.id,
            action="policy.published",
            metadata={"version_number": version.version_number},
        )
    return version
