"""FastAPI router for Decision Journal endpoints (Slice 3B)."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.decision_schemas import (
    AppendCorrectionRequest,
    ArchiveDecisionRequest,
    ArchiveResponse,
    ConfirmDecisionRequest,
    ConfirmResponse,
    CorrectionListResponse,
    CorrectionMetadataResponse,
    CorrectionResponse,
    CreateDecisionRequest,
    DecisionAuditEventResponse,
    DecisionAuditListResponse,
    DecisionCreateResponse,
    DecisionDetailResponse,
    DecisionListResponse,
    DiscardDecisionRequest,
    DraftDetailResponse,
    SnapshotResponse,
    UnarchiveDecisionRequest,
    UpdateDecisionDraftRequest,
)
from apps.api.services.decisions import (
    DecisionConflictError,
    DecisionIncompleteError,
    DecisionLifecycleError,
    DecisionNotFoundError,
    DraftNotFoundError,
    HouseholdRequiredError,
    NoDecisionChangesError,
    PolicyNotFoundError,
    PublishedPolicyNotFoundError,
    append_correction,
    archive_decision,
    confirm_draft,
    create_decision,
    discard_draft,
    read_corrections,
    read_decision_audit_events,
    read_decision_detail,
    read_decision_list,
    read_draft,
    unarchive_decision,
    update_draft,
)

router = APIRouter(prefix="/api/decisions", tags=["decisions"])
DatabaseSession = Annotated[Session, Depends(get_session)]


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, HouseholdRequiredError):
        return HTTPException(status_code=404, detail="Household profile not found")
    if isinstance(exc, DecisionNotFoundError):
        return HTTPException(status_code=404, detail="Decision not found")
    if isinstance(exc, DraftNotFoundError):
        return HTTPException(
            status_code=404, detail="Decision draft not found"
        )
    if isinstance(exc, PolicyNotFoundError):
        return HTTPException(status_code=404, detail="Investment policy not found")
    if isinstance(exc, PublishedPolicyNotFoundError):
        return HTTPException(
            status_code=404, detail="Published policy version not found"
        )
    if isinstance(exc, DecisionConflictError):
        return HTTPException(
            status_code=409, detail="Decision conflict or stale revision"
        )
    if isinstance(exc, DecisionLifecycleError):
        return HTTPException(
            status_code=409, detail="Decision lifecycle conflict"
        )
    if isinstance(exc, NoDecisionChangesError):
        return HTTPException(status_code=400, detail="No decision changes provided")
    if isinstance(exc, DecisionIncompleteError):
        return HTTPException(
            status_code=400,
            detail="Decision draft is incomplete: title, decision_summary, "
            "rationale, and decision_date are required for confirm",
        )
    raise exc


@router.post(
    "",
    response_model=DecisionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create(
    payload: CreateDecisionRequest, session: DatabaseSession
) -> DecisionCreateResponse:
    try:
        decision, draft = create_decision(session, payload)
        return DecisionCreateResponse(
            id=decision.id,
            title=draft.title,
            revision=draft.revision,
            status=decision.status,
            created_at=decision.created_at,
            updated_at=draft.updated_at,
        )
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("", response_model=DecisionListResponse)
def list_decisions(
    session: DatabaseSession,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    include_archived: bool = Query(default=False),
) -> DecisionListResponse:
    if status_filter is not None and status_filter not in (
        "draft",
        "confirmed",
        "archived",
    ):
        raise HTTPException(
            status_code=422,
            detail="status must be one of: draft, confirmed, archived",
        )
    try:
        rows = read_decision_list(
            session,
            status_filter=status_filter,
            include_archived=include_archived,
        )
        items = []
        for decision, draft, snapshot in rows:
            item_data: dict = {
                "id": decision.id,
                "title": "",
                "status": decision.status,
                "created_at": decision.created_at,
            }
            if draft is not None:
                item_data["title"] = draft.title
                item_data["updated_at"] = draft.updated_at
            if snapshot is not None:
                item_data["title"] = snapshot.title
                item_data["confirmed_at"] = snapshot.confirmed_at
            if not item_data.get("title") and draft is not None:
                item_data["title"] = draft.title
            items.append(item_data)
        return DecisionListResponse(items=items)
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/{decision_id}/draft", response_model=DraftDetailResponse)
def get_draft(
    decision_id: UUID, session: DatabaseSession
) -> DraftDetailResponse:
    try:
        draft = read_draft(session, decision_id)
        return DraftDetailResponse.model_validate(draft)
    except Exception as exc:
        raise _translate(exc) from exc


@router.patch("/{decision_id}/draft", response_model=DraftDetailResponse)
def patch_draft(
    decision_id: UUID,
    payload: UpdateDecisionDraftRequest,
    session: DatabaseSession,
) -> DraftDetailResponse:
    try:
        draft = update_draft(session, decision_id, payload)
        return DraftDetailResponse.model_validate(draft)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post(
    "/{decision_id}/draft/discard",
    status_code=status.HTTP_204_NO_CONTENT,
)
def discard(
    decision_id: UUID,
    payload: DiscardDecisionRequest,
    session: DatabaseSession,
) -> Response:
    try:
        discard_draft(session, decision_id, payload)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post(
    "/{decision_id}/draft/confirm",
    response_model=ConfirmResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm(
    decision_id: UUID,
    payload: ConfirmDecisionRequest,
    session: DatabaseSession,
) -> ConfirmResponse:
    try:
        snapshot = confirm_draft(session, decision_id, payload)
        return ConfirmResponse.model_validate(snapshot)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/{decision_id}/approve")
def approve(decision_id: UUID, session: DatabaseSession) -> dict:
    """Owner approves a pending decision draft (journal confirm + learning).

    Owner-only: enforced by the global X-API-Key auth middleware.
    """
    from apps.api.services.decision_lifecycle import OwnerDecisionService

    try:
        return OwnerDecisionService.confirm_decision(session, decision_id)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/{decision_id}/reject")
def reject(decision_id: UUID, session: DatabaseSession) -> dict:
    """Owner rejects a pending decision draft (journal discard).

    Owner-only: enforced by the global X-API-Key auth middleware.
    """
    from apps.api.services.decision_lifecycle import OwnerDecisionService

    try:
        return OwnerDecisionService.reject_decision(session, decision_id)
    except Exception as exc:
        raise _translate(exc) from exc


@router.get("/{decision_id}", response_model=DecisionDetailResponse)
def get_decision(
    decision_id: UUID, session: DatabaseSession
) -> DecisionDetailResponse:
    try:
        data = read_decision_detail(session, decision_id)
        response_data: dict = {
            "id": data["id"],
            "household_id": data["household_id"],
            "status": data["status"],
            "created_at": data["created_at"],
            "archived_at": data["archived_at"],
            "archive_reason": data["archive_reason"],
            "corrections_count": data["corrections_count"],
        }
        if data.get("original_snapshot") is not None:
            response_data["original_snapshot"] = SnapshotResponse.model_validate(
                data["original_snapshot"]
            )
        if data.get("effective_snapshot") is not None:
            snap = data["effective_snapshot"]
            if hasattr(snap, "correction_number"):
                # It's a DecisionCorrection - build snapshot response
                response_data["effective_snapshot"] = SnapshotResponse(
                    title=snap.title,
                    decision_summary=snap.decision_summary,
                    rationale=snap.rationale,
                    alternatives_considered=snap.alternatives_considered,
                    risks_and_uncertainties=snap.risks_and_uncertainties,
                    evidence_or_sources=snap.evidence_or_sources,
                    expected_outcome=snap.expected_outcome,
                    review_trigger=snap.review_trigger,
                    review_date=snap.review_date,
                    decision_date=snap.decision_date,
                    notes=snap.notes,
                    confirmed_at=snap.created_at,
                    selected_policy_version_id=data["original_snapshot"].selected_policy_version_id,
                )
            else:
                response_data["effective_snapshot"] = SnapshotResponse.model_validate(
                    snap
                )
        if data.get("latest_correction_metadata") is not None:
            response_data["latest_correction_metadata"] = CorrectionMetadataResponse(
                **data["latest_correction_metadata"]
            )
        return DecisionDetailResponse(**response_data)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/{decision_id}/archive", response_model=ArchiveResponse)
def archive(
    decision_id: UUID,
    session: DatabaseSession,
    payload: ArchiveDecisionRequest = Body(default_factory=ArchiveDecisionRequest),
) -> ArchiveResponse:
    try:
        decision = archive_decision(session, decision_id, payload)
        return ArchiveResponse.model_validate(decision)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post("/{decision_id}/unarchive", response_model=ArchiveResponse)
def unarchive(
    decision_id: UUID,
    payload: UnarchiveDecisionRequest,
    session: DatabaseSession,
) -> ArchiveResponse:
    try:
        decision = unarchive_decision(session, decision_id)
        return ArchiveResponse.model_validate(decision)
    except Exception as exc:
        raise _translate(exc) from exc


@router.post(
    "/{decision_id}/corrections",
    response_model=CorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def append_correction_endpoint(
    decision_id: UUID,
    payload: AppendCorrectionRequest,
    session: DatabaseSession,
) -> CorrectionResponse:
    try:
        correction = append_correction(session, decision_id, payload)
        return CorrectionResponse.model_validate(correction)
    except Exception as exc:
        raise _translate(exc) from exc


@router.get(
    "/{decision_id}/corrections", response_model=CorrectionListResponse
)
def get_corrections(
    decision_id: UUID, session: DatabaseSession
) -> CorrectionListResponse:
    try:
        corrections = read_corrections(session, decision_id)
        return CorrectionListResponse(
            items=[CorrectionResponse.model_validate(c) for c in corrections]
        )
    except Exception as exc:
        raise _translate(exc) from exc


@router.get(
    "/{decision_id}/audit-events",
    response_model=DecisionAuditListResponse,
)
def get_audit_events(
    decision_id: UUID,
    session: DatabaseSession,
    before_sequence_number: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
) -> DecisionAuditListResponse:
    try:
        events, next_cursor = read_decision_audit_events(
            session,
            decision_id,
            before_sequence_number=before_sequence_number,
            limit=limit,
        )
        return DecisionAuditListResponse(
            items=[DecisionAuditEventResponse.model_validate(e) for e in events],
            next_before_sequence_number=next_cursor,
        )
    except Exception as exc:
        raise _translate(exc) from exc
