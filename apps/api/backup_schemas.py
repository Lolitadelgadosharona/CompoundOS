"""Sprint 007 Slice A — Backup & Export API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class BackupTrigger(BaseModel):
    """Owner confirms backup. Default destination from config."""
    pass


class BackupRecordResponse(BaseModel):
    id: UUID
    backup_type: str
    file_path: str
    file_size_bytes: Optional[int] = None
    sha256: Optional[str] = None
    encryption: Optional[str] = None
    age_recipient: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    retention_category: Optional[str] = None
    restore_verified: bool = False
    error_detail: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportTrigger(BaseModel):
    entity_type: str
    format: str = "json"

    @field_validator("entity_type")
    @classmethod
    def _check_entity(cls, v: str) -> str:
        allowed = {"household", "policy", "portfolio", "decisions", "committee_sessions"}
        if v not in allowed:
            raise ValueError(f"entity_type must be one of {allowed}")
        return v

    @field_validator("format")
    @classmethod
    def _check_format(cls, v: str) -> str:
        if v not in ("csv", "json"):
            raise ValueError("format must be csv or json")
        return v


class ExportTaskResponse(BaseModel):
    id: UUID
    entity_type: str
    format: str
    file_path: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    row_count: Optional[int] = None
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
