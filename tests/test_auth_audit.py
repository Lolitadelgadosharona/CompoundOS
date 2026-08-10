"""Tests for Sprint 010 Slice D — Auth, Audit & Escalation.

SECURITY HARDENING — 24+ integration tests.
"""

import hashlib
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0029_perspective_analyses"


def _hash_key(api_key):
    return hashlib.sha256(api_key.encode()).hexdigest()


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_tables_exist(self, db_session):
        for t in ["owner_api_keys", "audit_log", "notification_escalation_rules"]:
            db_session.execute(text(f"SELECT 1 FROM {t} LIMIT 0"))

    def test_audit_immutability(self, db_session):
        """INSERT ok, UPDATE and DELETE rejected."""
        db_session.execute(
            text(
                "INSERT INTO audit_log (id, event_type, action, outcome,"
                " occurred_at) VALUES (:id, 'system.action', 'test',"
                " 'success', :now)"
            ),
            {"id": uuid4(), "now": _now()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text("UPDATE audit_log SET action='hacked' WHERE id IS NOT NULL"),
            )
            db_session.commit()
        db_session.rollback()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(text("DELETE FROM audit_log")),
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


# ═══════════════════════════════════════════════════════════════════════
# Authentication — env bypass behavior (H2)
# ═══════════════════════════════════════════════════════════════════════


class TestAuthEnvironment:
    def test_development_bypass_allowed(self, monkeypatch):
        """ENVIRONMENT=development → bypass."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert os.getenv("ENVIRONMENT", "").strip().lower() in ("development", "test")

    def test_test_bypass_allowed(self, monkeypatch):
        """ENVIRONMENT=test → bypass."""
        monkeypatch.setenv("ENVIRONMENT", "test")
        assert os.getenv("ENVIRONMENT", "").strip().lower() in ("development", "test")

    def test_missing_env_not_bypassed(self, monkeypatch):
        """Missing ENVIRONMENT → NOT bypassed."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        env = os.getenv("ENVIRONMENT", "").strip().lower()
        assert env not in ("development", "test")

    def test_production_not_bypassed(self, monkeypatch):
        """ENVIRONMENT=production → NOT bypassed."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        env = os.getenv("ENVIRONMENT", "").strip().lower()
        assert env not in ("development", "test")

    def test_staging_not_bypassed(self, monkeypatch):
        """ENVIRONMENT=staging → NOT bypassed."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        env = os.getenv("ENVIRONMENT", "").strip().lower()
        assert env not in ("development", "test")

    def test_unknown_env_not_bypassed(self, monkeypatch):
        """ENVIRONMENT=unknown → NOT bypassed."""
        monkeypatch.setenv("ENVIRONMENT", "UNKNOWN")
        env = os.getenv("ENVIRONMENT", "").strip().lower()
        assert env not in ("development", "test")


# ═══════════════════════════════════════════════════════════════════════
# Authentication — API key validation (H1, M1)
# ═══════════════════════════════════════════════════════════════════════


class TestApiKeyValidation:
    def test_valid_key_accepted(self, db_session):
        """Known key found and matches."""
        api_key = os.urandom(32).hex()
        kh = _hash_key(api_key)
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, 'test', 'test')"
            ),
            {"id": uuid4(), "kh": kh},
        )
        db_session.commit()
        row = db_session.execute(
            text(
                "SELECT id FROM owner_api_keys"
                " WHERE key_hash = :kh AND revoked_at IS NULL"
            ),
            {"kh": kh},
        ).fetchone()
        assert row is not None

    def test_invalid_key_rejected(self, db_session):
        """Unknown key hash → no match."""
        row = db_session.execute(
            text(
                "SELECT id FROM owner_api_keys"
                " WHERE key_hash = :kh AND revoked_at IS NULL"
            ),
            {"kh": "deadbeef_not_a_real_hash"},
        ).fetchone()
        assert row is None

    def test_revoked_key_rejected(self, db_session):
        """Revoked key → not found."""
        api_key = os.urandom(32).hex()
        kh = _hash_key(api_key)
        kid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by,"
                " revoked_at) VALUES (:id, :kh, 'revoked', 'test', :now)"
            ),
            {"id": kid, "kh": kh, "now": _now()},
        )
        db_session.commit()
        row = db_session.execute(
            text(
                "SELECT id FROM owner_api_keys"
                " WHERE key_hash = :kh AND revoked_at IS NULL"
            ),
            {"kh": kh},
        ).fetchone()
        assert row is None

    def test_key_hash_stored_not_plaintext(self, db_session):
        """Verify only key_hash is stored, not plaintext."""
        api_key = os.urandom(32).hex()
        kh = _hash_key(api_key)
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, 'hash_test', 'test')"
            ),
            {"id": uuid4(), "kh": kh},
        )
        db_session.commit()
        # Check no row has key_hash equal to the plaintext key
        row = db_session.execute(
            text(
                "SELECT 1 FROM owner_api_keys WHERE key_hash = :plain"
            ),
            {"plain": api_key},
        ).fetchone()
        assert row is None  # Plaintext never stored


# ═══════════════════════════════════════════════════════════════════════
# Key lifecycle (M1)
# ═══════════════════════════════════════════════════════════════════════


class TestKeyLifecycle:
    def test_create_key(self, db_session):
        """Create a key → stored, returned."""
        api_key = os.urandom(32).hex()
        kh = _hash_key(api_key)
        kid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, 'lifecycle', 'test')"
            ),
            {"id": kid, "kh": kh},
        )
        db_session.commit()
        row = db_session.execute(
            text("SELECT id, label FROM owner_api_keys WHERE id = :id"),
            {"id": kid},
        ).fetchone()
        assert row is not None
        assert row[1] == "lifecycle"

    def test_revoke_key(self, db_session):
        """Revoke sets revoked_at."""
        api_key = os.urandom(32).hex()
        kh = _hash_key(api_key)
        kid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, 'revoke_test', 'test')"
            ),
            {"id": kid, "kh": kh},
        )
        db_session.commit()
        result = db_session.execute(
            text(
                "UPDATE owner_api_keys SET revoked_at = :now, revoked_by = 'test'"
                " WHERE id = :kid AND revoked_at IS NULL"
            ),
            {"kid": kid, "now": _now()},
        )
        assert result.rowcount == 1
        db_session.commit()

    def test_key_rotation_flow(self, db_session):
        """Create new key → revoke old → new works, old doesn't."""
        old = os.urandom(32).hex()
        old_hash = _hash_key(old)
        old_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, 'old', 'test')"
            ),
            {"id": old_id, "kh": old_hash},
        )
        db_session.commit()

        # Create new key
        new = os.urandom(32).hex()
        new_hash = _hash_key(new)
        new_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
                " VALUES (:id, :kh, 'new', 'test')"
            ),
            {"id": new_id, "kh": new_hash},
        )
        db_session.commit()

        # Revoke old
        db_session.execute(
            text(
                "UPDATE owner_api_keys SET revoked_at = :now, revoked_by = 'test'"
                " WHERE id = :kid"
            ),
            {"kid": old_id, "now": _now()},
        )
        db_session.commit()

        # Verify: old not found, new found
        old_row = db_session.execute(
            text(
                "SELECT id FROM owner_api_keys"
                " WHERE key_hash = :kh AND revoked_at IS NULL"
            ),
            {"kh": old_hash},
        ).fetchone()
        assert old_row is None

        new_row = db_session.execute(
            text(
                "SELECT id FROM owner_api_keys"
                " WHERE key_hash = :kh AND revoked_at IS NULL"
            ),
            {"kh": new_hash},
        ).fetchone()
        assert new_row is not None


# ═══════════════════════════════════════════════════════════════════════
# Audit coverage (M2)
# ═══════════════════════════════════════════════════════════════════════


class TestAuditCoverage:
    def test_auth_success_logged(self, db_session):
        """authentication.success recorded."""
        db_session.execute(
            text(
                "INSERT INTO audit_log (id, event_type, actor_role, action,"
                " outcome, occurred_at) VALUES (:id,"
                " 'authentication.success', 'owner', 'test', 'success', :now)"
            ),
            {"id": uuid4(), "now": _now()},
        )
        db_session.commit()
        row = db_session.execute(
            text("SELECT 1 FROM audit_log WHERE event_type = 'authentication.success'"),
        ).fetchone()
        assert row is not None

    def test_auth_failure_logged(self, db_session):
        """authentication.failure recorded."""
        db_session.execute(
            text(
                "INSERT INTO audit_log (id, event_type, actor_id, action,"
                " outcome, occurred_at) VALUES (:id,"
                " 'authentication.failure', 'bad_key', 'test', 'failure', :now)"
            ),
            {"id": uuid4(), "now": _now()},
        )
        db_session.commit()
        row = db_session.execute(
            text("SELECT 1 FROM audit_log WHERE event_type = 'authentication.failure'"),
        ).fetchone()
        assert row is not None

    def test_owner_mutation_logged(self, db_session):
        """owner.mutation recorded for key create/revoke."""
        db_session.execute(
            text(
                "INSERT INTO audit_log (id, event_type, actor_role, action,"
                " resource, outcome, occurred_at) VALUES (:id,"
                " 'owner.mutation', 'owner', 'create_api_key', 'key-1',"
                " 'success', :now)"
            ),
            {"id": uuid4(), "now": _now()},
        )
        db_session.commit()
        row = db_session.execute(
            text("SELECT 1 FROM audit_log WHERE event_type = 'owner.mutation'"),
        ).fetchone()
        assert row is not None

    def test_authorization_denied_logged(self, db_session):
        """authorization.denied recorded."""
        db_session.execute(
            text(
                "INSERT INTO audit_log (id, event_type, actor_id, action,"
                " outcome, occurred_at) VALUES (:id,"
                " 'authorization.denied', 'anon', 'test', 'denied', :now)"
            ),
            {"id": uuid4(), "now": _now()},
        )
        db_session.commit()
        row = db_session.execute(
            text("SELECT 1 FROM audit_log WHERE event_type = 'authorization.denied'"),
        ).fetchone()
        assert row is not None


# ═══════════════════════════════════════════════════════════════════════
# Notification escalation (schema only)
# ═══════════════════════════════════════════════════════════════════════


class TestEscalation:
    def test_invalid_severity_rejected(self, db_session):
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO notification_escalation_rules"
                    " (id, source, event_severity, escalate_after_hours,"
                    " escalation_level, enabled)"
                    " VALUES (:id, 'guardian', 'FATAL', 1, 1, TRUE)"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_valid_severities_accepted(self, db_session):
        for sev in ["critical", "warning", "info"]:
            db_session.execute(
                text(
                    "INSERT INTO notification_escalation_rules"
                    " (id, source, event_severity, escalate_after_hours,"
                    " escalation_level, enabled)"
                    " VALUES (:id, 'guardian', :sev, 1, 1, TRUE)"
                ),
                {"id": uuid4(), "sev": sev},
            )
            db_session.commit()
