"""Pydantic schemas for Sprint 010 Slice A — Committee Integration Bridge."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CommitteeReviewRequestCreate(BaseModel):
    investment_idea_id: UUID
    notes: Optional[str] = None


class CommitteeReviewRequestUpdate(BaseModel):
    committee_session_id: Optional[UUID] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class CommitteeReviewRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    investment_idea_id: UUID
    committee_session_id: Optional[UUID] = None
    requested_by: str
    requested_at: datetime
    status: str
    notes: Optional[str] = None
    created_at: datetime
