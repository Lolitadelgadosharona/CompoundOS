"""Sprint 007 Slice B — Health API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ComponentHealthResponse(BaseModel):
    component: str
    status: str
    reason: str = ""
    last_checked: Optional[datetime] = None
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    overall: str
    components: list[ComponentHealthResponse]
    checked_at: datetime


class LivenessResponse(BaseModel):
    alive: bool = True
    checked_at: datetime


class ReadinessResponse(BaseModel):
    ready: bool
    reason: str = ""
    checked_at: datetime
