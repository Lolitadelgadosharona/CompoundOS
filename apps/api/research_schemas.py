"""Pydantic schemas for Sprint 011 Slice A — Research Foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ResearchRequestCreate(BaseModel):
    review_request_id: UUID
    parameters: Optional[dict] = None


class ResearchRequestResponse(BaseModel):
    id: UUID
    review_request_id: UUID
    investment_idea_id: Optional[UUID] = None
    status: str
    parameters: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ResearchRunResponse(BaseModel):
    id: UUID
    request_id: UUID
    run_number: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
