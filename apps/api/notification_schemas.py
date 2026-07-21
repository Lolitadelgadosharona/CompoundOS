"""Sprint 007 Slice C — Notification schemas V2 (integrity hardened)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NotificationEventResponse(BaseModel):
    id: UUID
    source: str
    event_type: str
    severity: str
    title: str
    preview: str = ""
    delivery_status: str
    suppressed_reason: Optional[str] = None
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_event(cls, event) -> "NotificationEventResponse":
        body = getattr(event, "body", "") or ""
        return cls(
            id=event.id,
            source=event.source,
            event_type=event.event_type,
            severity=event.severity,
            title=event.title,
            preview=body[:100] if body else "",
            delivery_status=event.delivery_status,
            suppressed_reason=event.suppressed_reason,
            delivered_at=event.delivered_at,
            acknowledged_at=event.acknowledged_at,
            occurred_at=event.occurred_at,
            created_at=event.created_at,
        )


class PreferencesResponse(BaseModel):
    id: UUID
    quiet_hours_start: str
    quiet_hours_end: str
    timezone: str
    enabled: bool = False
    enabled_sources: list[str] = Field(default_factory=list)
    enabled_severities: list[str] = Field(default_factory=list)
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreferencesUpdate(BaseModel):
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None
    enabled_sources: Optional[list[str]] = None
    enabled_severities: Optional[list[str]] = None

    @field_validator("timezone")
    @classmethod
    def _check_tz(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            from zoneinfo import ZoneInfo
            ZoneInfo(v)
        return v
