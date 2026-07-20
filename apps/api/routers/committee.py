"""Sprint 006 Slice B — Committee API router (9 endpoints)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.committee_schemas import (
    OutcomeCreate,
    OutcomeResponse,
    PrivacyPreviewResponse,
    ReportResponse,
    RunRequest,
    RunResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionResponse,
)
from apps.api.database import get_session
from apps.api.models import (
    CommitteeReport,
    CommitteeSession,
)
from apps.api.services import committee_orchestration as orch
from apps.api.services.ai_provider import DeepSeekProvider
from apps.api.services.credential_manager import CredentialError

router = APIRouter(prefix="/api/committee", tags=["committee"])


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _require_household_id(session: Session) -> str:
    row = session.execute(
        __import__("sqlalchemy").text(
            "SELECT id FROM household_profiles LIMIT 1"
        ),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No household found.")
    return str(row[0])


def _get_session_or_404(
    session: Session, session_id: str,
) -> CommitteeSession:
    cs = session.query(CommitteeSession).filter_by(id=session_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Committee session not found.")
    return cs


# ═══════════════════════════════════════════════════════════════════════════
# 1. POST /api/committee/sessions — Create session
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    payload: SessionCreate,
    session: Session = Depends(get_session),
) -> SessionResponse:
    household_id = UUID(_require_household_id(session))
    cs = orch.create_committee_session(
        session, household_id, payload.title, payload.proposal_text,
    )
    return SessionResponse.model_validate(cs)


# ═══════════════════════════════════════════════════════════════════════════
# 2. GET /api/committee/sessions — List sessions
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/sessions", response_model=list[SessionResponse])
def list_sessions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[SessionResponse]:
    household_id = _require_household_id(session)
    results = (
        session.query(CommitteeSession)
        .filter_by(household_id=household_id)
        .order_by(CommitteeSession.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [SessionResponse.model_validate(r) for r in results]


# ═══════════════════════════════════════════════════════════════════════════
# 3. GET /api/committee/sessions/{id} — Session detail
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(
    session_id: str,
    session: Session = Depends(get_session),
) -> SessionDetailResponse:
    cs = _get_session_or_404(session, session_id)
    evidence = [
        {
            "id": str(e.id), "source_type": e.source_type,
            "source_title": e.source_title, "citation_ref": e.citation_ref,
            "confidence": e.confidence, "provenance": e.provenance,
        }
        for e in cs.evidence_items
    ]
    report = None
    if cs.report:
        r = cs.report
        report = {
            "id": str(r.id), "provider": r.provider, "model_id": r.model_id,
            "prompt_version": r.prompt_version, "schema_version": r.schema_version,
            "temperature": float(r.temperature) if r.temperature else 0.0,
            "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "content_hash": r.content_hash,
        }
    outcomes = [
        {
            "id": str(o.id), "outcome": o.outcome,
            "owner_rationale": o.owner_rationale,
            "recorded_at": o.recorded_at.isoformat() if o.recorded_at else None,
        }
        for o in cs.outcomes
    ]
    return SessionDetailResponse(
        id=cs.id, household_id=cs.household_id,
        parent_session_id=cs.parent_session_id,
        title=cs.title, proposal_text=cs.proposal_text,
        status=cs.status,
        created_at=cs.created_at, updated_at=cs.updated_at,
        evidence_items=evidence, report=report, outcomes=outcomes,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4. GET /api/committee/sessions/{id}/privacy-preview — Preview
# ═══════════════════════════════════════════════════════════════════════════


@router.get(
    "/sessions/{session_id}/privacy-preview",
    response_model=PrivacyPreviewResponse,
)
def privacy_preview(
    session_id: str,
    session: Session = Depends(get_session),
) -> PrivacyPreviewResponse:
    cs = _get_session_or_404(session, session_id)
    if cs.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Privacy preview only available for draft sessions.",
        )
    household_id = cs.household_id
    try:
        preview = orch.build_privacy_preview(session, household_id, cs)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    return PrivacyPreviewResponse(
        session_id=cs.id,
        evidence_summary=preview["evidence_summary"],
        estimated_input_tokens=preview["estimated_input_tokens"],
        exceeds_budget=preview["exceeds_budget"],
        max_input_tokens=preview["max_input_tokens"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 5. POST /api/committee/sessions/{id}/run — Run committee
# ═══════════════════════════════════════════════════════════════════════════


@router.post(
    "/sessions/{session_id}/run",
    response_model=RunResponse,
    status_code=201,
)
def run_committee(
    session_id: str,
    payload: RunRequest,  # noqa: ARG001 — explicit Owner confirmation
    session: Session = Depends(get_session),
) -> RunResponse:
    cs = _get_session_or_404(session, session_id)
    if cs.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Session must be in 'draft' status to run.",
        )
    if not cs.evidence_items:
        raise HTTPException(
            status_code=422,
            detail="Privacy preview must be completed before running.",
        )
    cs.status = "queued"
    session.commit()

    try:
        provider = DeepSeekProvider()
        report = orch.run_committee(session, cs, provider)
        return RunResponse(
            session_id=cs.id, status="completed", report_id=report.id,
        )
    except CredentialError:
        raise HTTPException(
            status_code=500,
            detail="Provider credentials not configured.",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# 6. GET /api/committee/runs/{id} — Run status
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/runs/{session_id}", response_model=RunResponse)
def get_run_status(
    session_id: str,
    session: Session = Depends(get_session),
) -> RunResponse:
    cs = _get_session_or_404(session, session_id)
    return RunResponse(
        session_id=cs.id,
        status=cs.status,
        report_id=cs.report.id if cs.report else None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 7. GET /api/committee/reports/{id} — Get report
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    session: Session = Depends(get_session),
) -> ReportResponse:
    report = session.query(CommitteeReport).filter_by(id=report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return ReportResponse.model_validate(report)


# ═══════════════════════════════════════════════════════════════════════════
# 8. GET /api/committee/evidence/{session_id} — Evidence items
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/evidence/{session_id}")
def get_evidence(
    session_id: str,
    session: Session = Depends(get_session),
) -> list[dict]:
    cs = _get_session_or_404(session, session_id)
    return [
        {
            "id": str(e.id), "source_type": e.source_type,
            "source_title": e.source_title, "citation_ref": e.citation_ref,
            "structured_facts": e.structured_facts,
            "confidence": e.confidence, "provenance": e.provenance,
            "as_of": e.as_of.isoformat() if e.as_of else None,
        }
        for e in cs.evidence_items
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 9. POST /api/committee/outcomes — Record outcome
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/outcomes", response_model=OutcomeResponse, status_code=201)
def record_outcome(
    payload: OutcomeCreate,
    session_id: Optional[str] = None,
    session: Session = Depends(get_session),
) -> OutcomeResponse:
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    cs = _get_session_or_404(session, session_id)
    if cs.status != "completed":
        raise HTTPException(
            status_code=409,
            detail="Outcome can only be recorded for completed sessions.",
        )
    if not cs.report:
        raise HTTPException(
            status_code=422,
            detail="Session has no report.",
        )

    try:
        co = orch.record_outcome(
            session, cs, payload.outcome,
            owner_rationale=payload.owner_rationale,
        )
        return OutcomeResponse.model_validate(co)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
