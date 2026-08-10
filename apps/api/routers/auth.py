"""Auth router — API key management endpoints.

Sprint 010 Slice D. Owner-only.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import get_session
from apps.api.middleware.auth import verify_api_key

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ApiKeyCreateResponse(BaseModel):
    id: str
    label: str
    api_key: str


class ApiKeyResponse(BaseModel):
    id: str
    label: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


@router.post(
    "/keys", response_model=ApiKeyCreateResponse,
    dependencies=[Depends(verify_api_key)],
)
def create_api_key(
    label: str = "default",
    session: Session = Depends(get_session),
) -> ApiKeyCreateResponse:
    """Register a new API key. Returns key once — store it securely."""
    api_key = os.urandom(32).hex()
    key_hash = _hash_key(api_key)
    kid = uuid4()
    session.execute(
        text(
            "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
            " VALUES (:id, :kh, :label, :created_by)"
        ),
        {"id": kid, "kh": key_hash, "label": label, "created_by": "owner"},
    )
    session.commit()
    return ApiKeyCreateResponse(id=str(kid), label=label, api_key=api_key)


@router.get(
    "/keys", response_model=list[ApiKeyResponse],
    dependencies=[Depends(verify_api_key)],
)
def list_api_keys(
    session: Session = Depends(get_session),
) -> list[ApiKeyResponse]:
    """List all API keys."""
    rows = session.execute(
        text(
            "SELECT id, label, created_at, last_used_at, revoked_at"
            " FROM owner_api_keys ORDER BY created_at DESC"
        ),
    ).fetchall()
    return [
        ApiKeyResponse(
            id=str(r[0]), label=r[1], created_at=r[2],
            last_used_at=r[3], revoked_at=r[4],
        )
        for r in rows
    ]


@router.delete(
    "/keys/{key_id}", dependencies=[Depends(verify_api_key)],
)
def revoke_api_key(
    key_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Revoke an API key."""
    from uuid import UUID as _UUID

    try:
        kid = _UUID(key_id)
    except ValueError:
        raise HTTPException(400, "Invalid key ID format")

    result = session.execute(
        text(
            "UPDATE owner_api_keys SET revoked_at = :now, revoked_by = 'owner'"
            " WHERE id = :kid AND revoked_at IS NULL"
        ),
        {"kid": kid, "now": datetime.now(timezone.utc)},
    )
    if result.rowcount == 0:
        raise HTTPException(404, "Key not found or already revoked")
    session.commit()
    return {"status": "revoked"}
