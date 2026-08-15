"""Prompt approval API — Owner-gated prompt lifecycle (M6-004 Slice B).

draft → (Owner approval) → active → deprecated. Approval is enforced by
the global X-API-Key auth middleware (Owner-only); the AI research worker
never calls these endpoints.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.services.prompt_governor import PromptGovernor

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("")
def list_prompts(session: Session = Depends(get_session)) -> dict:
    """List all prompt templates (read-only)."""
    return {"prompts": PromptGovernor().list_prompts(session)}


@router.post("/{prompt_id}/approve")
def approve_prompt(prompt_id: UUID,
                   session: Session = Depends(get_session)) -> dict:
    """Owner approves a draft prompt → active.

    Owner-only: enforced by the global X-API-Key auth middleware.
    Deprecates the current active version for the same perspective.
    """
    try:
        result = PromptGovernor().approve(session, prompt_id)
        session.commit()
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
