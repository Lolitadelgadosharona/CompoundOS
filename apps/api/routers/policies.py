from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.policy_schemas import (
    AllocationReplaceRequest,
    AllocationResponse,
    CreatePolicyDraftRequest,
    EmptyPolicyCreateRequest,
    ExpectedRevisionRequest,
    PersonalPolicySetupRequest,
    PolicyAuditEventResponse,
    PolicyCreateResponse,
    PolicyDraftResponse,
    PolicyDraftUpdate,
    PolicyResponse,
    PolicyVersionHistoryResponse,
    PolicyVersionResponse,
    PolicyVersionSummary,
    PublishPolicyDraftRequest,
)
from apps.api.services.policies import (
    DraftAlreadyExistsError,
    DraftConflictError,
    DraftNotFoundError,
    HouseholdRequiredError,
    NoPolicyChangesError,
    PolicyAlreadyExistsError,
    PolicyIncompleteError,
    PolicyNotFoundError,
    PolicyVersionNotFoundError,
    PublishedVersionNotFoundError,
    create_new_draft,
    create_policy,
    discard_draft,
    publish_draft,
    read_current_draft,
    read_current_policy,
    read_current_published,
    read_policy_audit_events,
    read_version,
    read_version_history,
    replace_allocations,
    setup_personal_policy,
    update_draft_text,
)

router = APIRouter(prefix="/api/policies", tags=["policies"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def _draft_response(draft, allocations) -> PolicyDraftResponse:
    values = {
        name: getattr(draft, name)
        for name in PolicyDraftResponse.model_fields
        if name != "allocations"
    }
    values["allocations"] = [AllocationResponse.model_validate(item) for item in allocations]
    return PolicyDraftResponse.model_validate(values)


def _version_response(version, allocations) -> PolicyVersionResponse:
    values = {
        name: getattr(version, name)
        for name in PolicyVersionResponse.model_fields
        if name != "allocations"
    }
    values["allocations"] = [AllocationResponse.model_validate(item) for item in allocations]
    return PolicyVersionResponse.model_validate(values)


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, HouseholdRequiredError):
        return HTTPException(status_code=404, detail="Household profile not found")
    if isinstance(exc, PolicyNotFoundError):
        return HTTPException(status_code=404, detail="Investment policy not found")
    if isinstance(exc, DraftNotFoundError):
        return HTTPException(status_code=404, detail="Investment policy draft not found")
    if isinstance(exc, PublishedVersionNotFoundError):
        return HTTPException(status_code=404, detail="Published policy version not found")
    if isinstance(exc, PolicyVersionNotFoundError):
        return HTTPException(status_code=404, detail="Policy version not found")
    if isinstance(exc, PolicyAlreadyExistsError):
        return HTTPException(status_code=409, detail="An investment policy already exists")
    if isinstance(exc, DraftAlreadyExistsError):
        return HTTPException(status_code=409, detail="An investment policy draft already exists")
    if isinstance(exc, DraftConflictError):
        return HTTPException(
            status_code=409, detail="Investment policy draft changed or unavailable"
        )
    if isinstance(exc, NoPolicyChangesError):
        return HTTPException(status_code=400, detail="No investment policy changes provided")
    if isinstance(exc, PolicyIncompleteError):
        return HTTPException(status_code=400, detail="Investment policy draft is incomplete")
    raise exc


@router.post("", response_model=PolicyCreateResponse, status_code=status.HTTP_201_CREATED)
def create(
    session: DatabaseSession,
    _payload: EmptyPolicyCreateRequest = Body(default_factory=EmptyPolicyCreateRequest),
) -> PolicyCreateResponse:
    try:
        policy, draft, allocations = create_policy(session)
        return PolicyCreateResponse(
            policy=PolicyResponse.model_validate(policy),
            draft=_draft_response(draft, allocations),
        )
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/current", response_model=PolicyResponse)
def get_current(session: DatabaseSession) -> PolicyResponse:
    try:
        return PolicyResponse.model_validate(read_current_policy(session))
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/current/draft", response_model=PolicyDraftResponse)
def get_draft(session: DatabaseSession) -> PolicyDraftResponse:
    try:
        draft, allocations = read_current_draft(session)
        return _draft_response(draft, allocations)
    except Exception as exc:
        raise _translate(exc) from exc


@router.patch("/current/draft", response_model=PolicyDraftResponse)
def patch_draft(payload: PolicyDraftUpdate, session: DatabaseSession) -> PolicyDraftResponse:
    try:
        return update_draft_text(session, payload)
    except Exception as exc:
        raise _translate(exc) from exc


@router.put("/current/draft/allocations", response_model=PolicyDraftResponse)
def put_allocations(
    payload: AllocationReplaceRequest, session: DatabaseSession
) -> PolicyDraftResponse:
    try:
        draft, allocations = replace_allocations(session, payload)
        return _draft_response(draft, allocations)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/current/draft/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard(payload: ExpectedRevisionRequest, session: DatabaseSession) -> Response:
    try:
        discard_draft(session, payload.expected_revision)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post(
    "/current/draft",
    response_model=PolicyDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def new_draft(
    session: DatabaseSession,
    payload: CreatePolicyDraftRequest = Body(default_factory=CreatePolicyDraftRequest),
) -> PolicyDraftResponse:
    try:
        draft, allocations = create_new_draft(session, payload)
        return _draft_response(draft, allocations)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post(
    "/current/draft/publish",
    response_model=PolicyVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish(
    payload: PublishPolicyDraftRequest, session: DatabaseSession
) -> PolicyVersionResponse:
    try:
        version, allocations = publish_draft(session, payload)
        return _version_response(version, allocations)
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/current/published", response_model=PolicyVersionResponse)
def get_published(session: DatabaseSession) -> PolicyVersionResponse:
    try:
        version, allocations = read_current_published(session)
        return _version_response(version, allocations)
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/current/versions", response_model=PolicyVersionHistoryResponse)
def get_versions(
    session: DatabaseSession,
    before_version_number: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> PolicyVersionHistoryResponse:
    try:
        versions, next_cursor = read_version_history(
            session,
            before_version_number=before_version_number,
            limit=limit,
        )
        return PolicyVersionHistoryResponse(
            items=[PolicyVersionSummary.model_validate(item) for item in versions],
            next_before_version_number=next_cursor,
        )
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/current/versions/{version_number}", response_model=PolicyVersionResponse)
def get_version(
    version_number: int, session: DatabaseSession
) -> PolicyVersionResponse:
    if version_number < 1:
        raise HTTPException(status_code=422, detail="version number must be positive")
    try:
        version, allocations = read_version(session, version_number)
        return _version_response(version, allocations)
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/current/audit-events", response_model=list[PolicyAuditEventResponse])
def get_audit_events(
    session: DatabaseSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PolicyAuditEventResponse]:
    try:
        return [
            PolicyAuditEventResponse.model_validate(event)
            for event in read_policy_audit_events(session, limit)
        ]
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup_personal(
    payload: PersonalPolicySetupRequest, session: DatabaseSession,
) -> dict:
    """One-shot Personal Edition policy setup → published version (PE-003)."""
    try:
        version = setup_personal_policy(session, payload)
        return {
            "policy_id": str(version.policy_id),
            "version_number": version.version_number,
            "status": version.status,
        }
    except Exception as exc:
        raise _translate(exc) from exc
