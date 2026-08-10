"""Auth middleware — X-API-Key authentication.

Sprint 010 Slice D.
Environment-based bypass for dev/test per OD-10-D-1.
Audit writes are committed atomically with auth outcome.
"""

from __future__ import annotations

import hashlib
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.database import get_session


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


async def verify_api_key(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Validate X-API-Key header. Bypassed in dev/test per OD-10-D-1."""
    env = os.getenv("ENVIRONMENT", "development")
    if env in ("development", "test"):
        request.state.role = "owner"
        return

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(401, "X-API-Key header required")

    key_hash = _hash_key(api_key)
    row = session.execute(
        text(
            "SELECT id FROM owner_api_keys"
            " WHERE key_hash = :kh AND revoked_at IS NULL"
        ),
        {"kh": key_hash},
    ).fetchone()

    if row is None:
        _log_audit(
            session, event_type="authentication.failure",
            actor_id=key_hash[:12], action=request.url.path,
            outcome="failure",
        )
        session.commit()
        raise HTTPException(401, "Invalid API key")

    # Update last_used_at
    session.execute(
        text(
            "UPDATE owner_api_keys SET last_used_at = NOW()"
            " WHERE id = :kid"
        ),
        {"kid": row[0]},
    )

    request.state.role = "owner"
    _log_audit(
        session, event_type="authentication.success",
        actor_id=key_hash[:12], actor_role="owner",
        action=request.url.path, outcome="success",
    )
    session.commit()


def _log_audit(
    session: Session,
    *,
    event_type: str,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    action: str = "",
    resource: Optional[str] = None,
    outcome: str = "success",
    detail: Optional[str] = None,
) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    session.execute(
        text(
            "INSERT INTO audit_log (id, event_type, actor_id, actor_role,"
            " action, resource, outcome, detail, occurred_at)"
            " VALUES (:id, :et, :aid, :ar, :act, :res, :out, :det, :now)"
        ),
        {
            "id": uuid4(),
            "et": event_type,
            "aid": actor_id,
            "ar": actor_role,
            "act": action,
            "res": resource,
            "out": outcome,
            "det": detail,
            "now": datetime.now(timezone.utc),
        },
    )
