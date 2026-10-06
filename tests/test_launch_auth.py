"""Production-style auth, CSRF, revocation and build provenance; synthetic keys only."""

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.postgres


def test_revocable_browser_session_and_csrf(api_client, db_session, monkeypatch):
    key = "synthetic_test_owner_key"
    kid = uuid4()
    db_session.execute(
        text(
            "INSERT INTO owner_api_keys(id,key_hash,label,created_by) VALUES(:i,:h,'test','owner')"
        ),
        {"i": kid, "h": hashlib.sha256(key.encode()).hexdigest()},
    )
    db_session.commit()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COMPOUNDOS_GIT_SHA", "a" * 40)
    monkeypatch.setenv("COMPOUNDOS_BUILD_TIMESTAMP", "2026-10-05T00:00:00Z")
    monkeypatch.setenv("COMPOUNDOS_PUBLIC_ORIGIN", "http://testserver")
    assert api_client.get("/api/auth/keys").status_code == 401
    r = api_client.post("/api/auth/session", headers={"X-API-Key": key})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
    token = r.cookies["compoundos_session"]
    # Synthetic HTTP test transport explicitly carries the otherwise Secure cookie.
    headers = {"Cookie": "compoundos_session=" + token}
    assert api_client.get("/api/auth/keys", headers=headers).status_code == 200
    assert api_client.post("/api/auth/keys", headers=headers).status_code == 403
    assert (
        api_client.post(
            "/api/auth/keys", headers={**headers, "Origin": "https://attacker.invalid"}
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            "/api/auth/keys", headers={**headers, "Origin": "http://testserver"}
        ).status_code
        == 200
    )
    db_session.execute(text("UPDATE owner_api_keys SET revoked_at=NOW() WHERE id=:i"), {"i": kid})
    db_session.commit()
    assert api_client.get("/api/auth/keys", headers=headers).status_code == 401


def test_version_endpoint_traceability_no_secrets(api_client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COMPOUNDOS_GIT_SHA", "a" * 40)
    monkeypatch.setenv("COMPOUNDOS_BUILD_TIMESTAMP", "2026-10-04T00:00:00Z")
    r = api_client.get("/api/version")
    assert r.status_code == 200
    assert r.json()["traceable"] and set(r.json()) == {
        "git_sha",
        "build_timestamp",
        "application_version",
        "traceable",
        "status",
    }
    monkeypatch.setenv("COMPOUNDOS_GIT_SHA", "UNKNOWN")
    assert not api_client.get("/api/version").json()["traceable"]
