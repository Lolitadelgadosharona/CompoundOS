"""Auth router — API key management endpoints.

Sprint 010 Slice D. Owner-only.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import get_session

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


def _log_audit(
    session: Session,
    *,
    event_type: str,
    action: str = "",
    resource: Optional[str] = None,
    outcome: str = "success",
) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    session.execute(
        text(
            "INSERT INTO audit_log (id, event_type, actor_role, action,"
            " resource, outcome, occurred_at)"
            " VALUES (:id, :et, 'owner', :act, :res, :out, :now)"
        ),
        {
            "id": uuid4(),
            "et": event_type,
            "act": action,
            "res": resource,
            "out": outcome,
            "now": datetime.now(timezone.utc),
        },
    )


@router.post(
    "/keys",
    response_model=ApiKeyCreateResponse,
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
    _log_audit(
        session,
        event_type="owner.mutation",
        action="create_api_key",
        resource=str(kid),
        outcome="success",
    )
    session.commit()
    return ApiKeyCreateResponse(id=str(kid), label=label, api_key=api_key)


@router.get(
    "/keys",
    response_model=list[ApiKeyResponse],
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
            id=str(r[0]),
            label=r[1],
            created_at=r[2],
            last_used_at=r[3],
            revoked_at=r[4],
        )
        for r in rows
    ]


@router.delete(
    "/keys/{key_id}",
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
    # Audit: key revocation
    _log_audit(
        session,
        event_type="owner.mutation",
        action="revoke_api_key",
        resource=key_id,
        outcome="success",
    )
    session.commit()
    return {"status": "revoked"}


@router.post("/session")
def create_web_session(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    """Header-authenticated exchange for revocable, HttpOnly eight-hour browser session."""
    from datetime import timedelta
    from secrets import token_urlsafe

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(401, "X-API-Key required to sign in")
    key_id = session.execute(
        text("SELECT id FROM owner_api_keys WHERE key_hash=:h AND revoked_at IS NULL"),
        {"h": _hash_key(api_key)},
    ).scalar()
    if not key_id:
        raise HTTPException(401, "Invalid API key")
    token = token_urlsafe(32)
    session.execute(
        text("INSERT INTO owner_web_sessions(token_hash,key_id,expires_at) VALUES(:t,:k,:e)"),
        {"t": _hash_key(token), "k": key_id, "e": datetime.now(timezone.utc) + timedelta(hours=8)},
    )
    session.commit()
    production = os.getenv("ENVIRONMENT", "").lower() not in {"test", "development"}
    response.set_cookie(
        "compoundos_session",
        token,
        max_age=8 * 3600,
        httponly=True,
        secure=production,
        samesite="strict",
        path="/",
    )
    return {"status": "signed_in", "expires_in": 8 * 3600}


@router.delete("/session")
def logout_web_session(
    request: Request, response: Response, session: Session = Depends(get_session)
):
    token = request.cookies.get("compoundos_session")
    if token:
        session.execute(
            text("DELETE FROM owner_web_sessions WHERE token_hash=:t"), {"t": _hash_key(token)}
        )
        session.commit()
    response.delete_cookie("compoundos_session", path="/")
    return {"status": "signed_out"}
