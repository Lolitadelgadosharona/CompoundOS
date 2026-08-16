"""Bootstrap CLI — create the FIRST Owner API key.

Sprint 010 Slice D — SECURITY HARDENING (H3).
M7-002 — production-safe one-off bootstrap.

Usage: docker compose run --rm api python -m apps.api.bootstrap_key

Generates a cryptographically random API key, stores its SHA-256 hash
in the database, and prints the plaintext key exactly once.

This is a local CLI tool — no HTTP endpoint for unauthenticated key
creation. It only works when NO owner key exists yet (first-key guard),
so it cannot be used to mint extra keys out-of-band. Additional keys are
created via the authenticated POST /api/auth/keys endpoint.
"""

from __future__ import annotations

import hashlib
import os
import sys
from uuid import uuid4

from sqlalchemy import text

from apps.api.database import SessionLocal


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "Owner Bootstrap Key"

    session = SessionLocal()
    try:
        # First-key guard: refuse if any key already exists so this CLI
        # cannot be used to mint extra keys out-of-band. Extra keys are
        # created via the authenticated POST /api/auth/keys endpoint.
        existing = session.execute(
            text("SELECT COUNT(*) FROM owner_api_keys")
        ).scalar() or 0
        if existing > 0:
            print(
                "ERROR: an Owner API key already exists — refusing to "
                "bootstrap another. Create additional keys via the "
                "authenticated POST /api/auth/keys endpoint."
            )
            sys.exit(1)

        api_key = os.urandom(32).hex()
        key_hash = _hash_key(api_key)
        # Audit: key creation
        from datetime import datetime, timezone
        audit_id = uuid4()
        session.execute(
            text(
                "INSERT INTO audit_log"
                " (id, event_type, actor_role, action, outcome, occurred_at)"
                " VALUES (:id, 'owner.mutation', 'owner',"
                " 'bootstrap: create_api_key', 'success', :now)"
            ),
            {"id": audit_id, "now": datetime.now(timezone.utc)},
        )
        session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, :label, 'bootstrap')"
            ),
            {"id": uuid4(), "kh": key_hash, "label": label},
        )
        session.commit()

        print("API key created successfully.")
        print("")
        print(f"  Label: {label}")
        print(f"  Key:   {api_key}")
        print("")
        print("IMPORTANT: Copy this key now. It will not be displayed again.")
        print("Store it securely. Use it in the X-API-Key header.")
    except Exception as exc:
        session.rollback()
        print(f"ERROR: {exc}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
