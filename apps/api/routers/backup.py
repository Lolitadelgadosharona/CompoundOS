"""Sprint 007 Slice A — Backup & Export API router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.backup_schemas import (
    BackupRecordResponse,
    BackupTrigger,
    ExportTaskResponse,
    ExportTrigger,
)
from apps.api.config import get_database_url
from apps.api.database import get_session
from apps.api.models import BackupRecord, ExportTask
from apps.api.services import backup_service, export_service, retention_service

router = APIRouter(prefix="/api/backup", tags=["backup"])


def _require_household_id(session: Session) -> UUID:
    from sqlalchemy import text as sa_text
    row = session.execute(sa_text(
        "SELECT id FROM household_profiles LIMIT 1"
    )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No household found.")
    return row[0]


def _get_backup_config() -> tuple[str, str]:
    """Get destination dir and age recipient from env/config."""
    import os
    dest = os.environ.get("COMPOUNDOS_BACKUP_DEST",
                          str(__import__("pathlib").Path.home() / ".compoundos" / "backups"))
    recipient = os.environ.get("COMPOUNDOS_BACKUP_AGE_RECIPIENT", "")
    if not recipient:
        raise HTTPException(
            status_code=503,
            detail="Backup encryption not configured. Set COMPOUNDOS_BACKUP_AGE_RECIPIENT.",
        )
    return dest, recipient


# ═══════════════════════════════════════════════════════════════════════════
# Backup
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/backup", response_model=BackupRecordResponse, status_code=201)
def trigger_backup(
    payload: BackupTrigger,  # noqa: ARG001
    session: Session = Depends(get_session),
) -> BackupRecordResponse:
    _require_household_id(session)
    dest, recipient = _get_backup_config()
    record = backup_service.run_backup(session, dest, recipient, get_database_url())
    # Apply retention after successful backup
    if record.status == "completed":
        retention_service.apply_retention(session)
    return BackupRecordResponse.model_validate(record)


@router.get("/backup/records", response_model=list[BackupRecordResponse])
def list_backups(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[BackupRecordResponse]:
    _require_household_id(session)
    records = (
        session.query(BackupRecord)
        .order_by(BackupRecord.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [BackupRecordResponse.model_validate(r) for r in records]


@router.get("/backup/records/{record_id}", response_model=BackupRecordResponse)
def get_backup(
    record_id: str,
    session: Session = Depends(get_session),
) -> BackupRecordResponse:
    r = session.query(BackupRecord).filter_by(id=record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Backup record not found.")
    return BackupRecordResponse.model_validate(r)


# ═══════════════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/export", response_model=ExportTaskResponse, status_code=201)
def trigger_export(
    payload: ExportTrigger,
    session: Session = Depends(get_session),
) -> ExportTaskResponse:
    hid = _require_household_id(session)
    try:
        task = export_service.run_export(
            session, payload.entity_type, payload.format, hid,
        )
        return ExportTaskResponse.model_validate(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/tasks", response_model=list[ExportTaskResponse])
def list_exports(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[ExportTaskResponse]:
    _require_household_id(session)
    tasks = (
        session.query(ExportTask)
        .order_by(ExportTask.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [ExportTaskResponse.model_validate(t) for t in tasks]


@router.get("/export/tasks/{task_id}", response_model=ExportTaskResponse)
def get_export(
    task_id: str,
    session: Session = Depends(get_session),
) -> ExportTaskResponse:
    t = session.query(ExportTask).filter_by(id=task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Export task not found.")
    return ExportTaskResponse.model_validate(t)
