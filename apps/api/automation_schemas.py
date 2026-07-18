"""Automation schemas — Sprint 005 Slice B."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from apps.api.services.orchestration_scheduling import (
    ALLOWED_JOB_TYPES,
    validate_job_params,
    validate_timezone,
)

# ---------------------------------------------------------------------------
# Job Definition
# ---------------------------------------------------------------------------


class JobDefinitionCreate(BaseModel):
    job_type: str
    job_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("job_type")
    @classmethod
    def _validate_job_type(cls, v: str) -> str:
        if v not in ALLOWED_JOB_TYPES:
            raise ValueError(f"Job type '{v}' is not in the approved allowlist.")
        return v

    @field_validator("job_params")
    @classmethod
    def _validate_params(cls, v: dict, info: Any) -> dict:
        job_type = info.data.get("job_type", "")
        if job_type:
            validate_job_params(job_type, v)
        return v


class JobDefinitionResponse(BaseModel):
    id: UUID
    household_id: UUID
    job_type: str
    job_params: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    job_type: str
    job_params: dict[str, Any] = Field(default_factory=dict)
    execution_time: time
    timezone: str = "UTC"

    @field_validator("job_type")
    @classmethod
    def _validate_job_type(cls, v: str) -> str:
        if v not in ALLOWED_JOB_TYPES:
            raise ValueError(f"Job type '{v}' is not in the approved allowlist.")
        return v

    @field_validator("timezone")
    @classmethod
    def _validate_tz(cls, v: str) -> str:
        validate_timezone(v)
        return v


class ScheduleUpdate(BaseModel):
    execution_time: Optional[time] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("timezone")
    @classmethod
    def _validate_tz(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            validate_timezone(v)
        return v


class ScheduleResponse(BaseModel):
    id: UUID
    job_definition_id: UUID
    job_type: str
    job_params: dict[str, Any]
    execution_time: time
    timezone: str
    next_run_at: datetime
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


class ManualTriggerRequest(BaseModel):
    job_definition_id: UUID


class RunResponse(BaseModel):
    id: UUID
    job_definition_id: UUID
    schedule_id: Optional[UUID] = None
    status: str
    triggered_by: str
    scheduled_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    household_id: UUID

    model_config = {"from_attributes": True}


class RunDetailResponse(RunResponse):
    attempts: list[AttemptResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Attempt
# ---------------------------------------------------------------------------


class AttemptResponse(BaseModel):
    id: UUID
    run_id: UUID
    attempt_number: int
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Worker status (read-only)
# ---------------------------------------------------------------------------


class WorkerStatusResponse(BaseModel):
    worker_count: int
    active_leases: int
    running_runs: int
