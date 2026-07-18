"""Automation router — Sprint 005 Slice B."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.automation_schemas import (
    ManualTriggerRequest,
    RunDetailResponse,
    RunResponse,
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    WorkerStatusResponse,
)
from apps.api.database import get_session
from apps.api.services import orchestration as svc

router = APIRouter(prefix="/api/automation", tags=["automation"])


# ── Helper ──


def _require_household_id(session: Session) -> str:
    row = session.execute(
        __import__("sqlalchemy").text("SELECT id FROM household_profiles LIMIT 1")
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No household found.")
    return str(row[0])


# ── Schedule CRUD ──


@router.post("/schedules", response_model=ScheduleResponse, status_code=201)
def create_schedule(
    payload: ScheduleCreate,
    session: Session = Depends(get_session),
) -> ScheduleResponse:
    household_id = _require_household_id(session)
    try:
        result = svc.create_schedule(session, household_id, payload)
        session.commit()
        return ScheduleResponse(**result)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/schedules", response_model=list[ScheduleResponse])
def list_schedules(session: Session = Depends(get_session)) -> list[ScheduleResponse]:
    household_id = _require_household_id(session)
    results = svc.list_schedules(session, household_id)
    return [ScheduleResponse(**r) for r in results]


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: str,
    session: Session = Depends(get_session),
) -> ScheduleResponse:
    result = svc.get_schedule(session, schedule_id)
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return ScheduleResponse(**result)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    session: Session = Depends(get_session),
) -> ScheduleResponse:
    result = svc.update_schedule(session, schedule_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    session.commit()
    return ScheduleResponse(**result)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str,
    session: Session = Depends(get_session),
):  # noqa: ANN202 — 204 has no response body
    deleted = svc.delete_schedule(session, schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    session.commit()


# ── Runs ──


@router.get("/runs", response_model=list[RunResponse])
def list_runs(
    job_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[RunResponse]:
    household_id = _require_household_id(session)
    results = svc.list_runs(session, household_id, job_type=job_type,
                            limit=limit, offset=offset)
    return [RunResponse(**r) for r in results]


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run(
    run_id: str,
    session: Session = Depends(get_session),
) -> RunDetailResponse:
    result = svc.get_run_detail(session, run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found.")
    return RunDetailResponse(**result)


@router.post("/runs", response_model=RunResponse, status_code=201)
def manual_trigger(
    payload: ManualTriggerRequest,
    session: Session = Depends(get_session),
) -> RunResponse:
    household_id = _require_household_id(session)
    try:
        result = svc.manual_trigger_run(session, household_id, payload)
        session.commit()
        return RunResponse(**result)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))


# ── Worker status ──


@router.get("/worker/status", response_model=WorkerStatusResponse)
def worker_status(session: Session = Depends(get_session)) -> WorkerStatusResponse:
    result = svc.get_worker_status(session)
    return WorkerStatusResponse(**result)
