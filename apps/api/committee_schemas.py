"""Sprint 006 Slice B — Committee request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# ═══════════════════════════════════════════════════════════════════════════
# Committee Session
# ═══════════════════════════════════════════════════════════════════════════


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    proposal_text: str = Field(min_length=1, max_length=20000)


class SessionResponse(BaseModel):
    id: UUID
    household_id: UUID
    parent_session_id: Optional[UUID] = None
    title: str
    proposal_text: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    report: Optional[dict[str, Any]] = None
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Privacy Preview
# ═══════════════════════════════════════════════════════════════════════════


class PrivacyPreviewResponse(BaseModel):
    session_id: UUID
    evidence_summary: list[dict[str, Any]]
    estimated_input_tokens: int
    exceeds_budget: bool
    max_input_tokens: int
    max_output_tokens: int = 8000
    max_cost_usd: str = "1.00"


# ═══════════════════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════════════════


class RunRequest(BaseModel):
    pass  # Owner confirmation — no additional fields needed


class RunResponse(BaseModel):
    session_id: UUID
    status: str
    report_id: Optional[UUID] = None


# ═══════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════


class ReportResponse(BaseModel):
    id: UUID
    session_id: UUID
    provider: str
    model_id: str
    model_version: Optional[str] = None
    prompt_version: str
    schema_version: str
    temperature: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None
    report_content: dict[str, Any]
    content_hash: str
    generated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════
# Outcome
# ═══════════════════════════════════════════════════════════════════════════


class OutcomeCreate(BaseModel):
    outcome: str
    owner_rationale: Optional[str] = Field(default=None, max_length=5000)
    create_decision_draft: bool = False

    @field_validator("outcome")
    @classmethod
    def _validate_outcome(cls, v: str) -> str:
        if v not in ("accepted", "rejected", "deferred"):
            raise ValueError(
                f"Invalid outcome '{v}'. Must be accepted, rejected, or deferred."
            )
        return v


class OutcomeResponse(BaseModel):
    id: UUID
    session_id: UUID
    report_id: UUID
    outcome: str
    owner_rationale: Optional[str] = None
    decision_draft_id: Optional[UUID] = None
    recorded_at: datetime

    model_config = {"from_attributes": True}
