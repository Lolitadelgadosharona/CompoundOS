"""Tests for Sprint 007 Slice B — Health service."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.services.health_service import (
    ALLOWED_STATUSES,
    DEGRADED,
    HEALTHY,
    STALE,
    UNAVAILABLE,
    UNKNOWN,
    ComponentHealth,
    check_backup,
    check_credential,
    check_database,
    check_migration_head,
    check_notification,
    compute_overall,
    run_all_checks,
)

pytestmark = pytest.mark.postgres


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _create_household(db_session: Session) -> str:
    hid = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles"
        " (id, household_name, base_currency, singleton_key,"
        "  investment_horizon, liquidity_needs, risk_statement, notes,"
        "  created_at, updated_at)"
        " VALUES (:id, 'Test', 'USD', true, 'Long', 'None', 'Low', '', now(), now())"
    ), {"id": str(hid)})
    db_session.commit()
    return str(hid)


NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# Component checks
# ═══════════════════════════════════════════════════════════════════════════


class TestDatabaseCheck:
    def test_healthy(self, db_session: Session) -> None:
        c = check_database(db_session, NOW)
        assert c.status == HEALTHY


class TestMigrationCheck:
    def test_healthy(self, db_session: Session) -> None:
        c = check_migration_head(db_session, NOW)
        assert c.status == HEALTHY


class TestBackupCheck:
    def test_no_backup_unknown(self, db_session: Session) -> None:
        c = check_backup(db_session, NOW)
        assert c.status == UNKNOWN

    def test_recent_backup_healthy(self, db_session: Session) -> None:
        tf = tempfile.NamedTemporaryFile(suffix=".age", delete=False)
        tf.close()
        db_session.execute(text(
            "INSERT INTO backup_records (id, backup_type, file_path, status, started_at, completed_at, sha256)"  # noqa: E501
            " VALUES (:id, 'full', :fp, 'completed', :t, :t, 'abc')"
        ), {"id": str(uuid4()), "fp": tf.name, "t": NOW - timedelta(hours=1)})
        db_session.commit()
        c = check_backup(db_session, NOW)
        assert c.status == HEALTHY

    def test_old_backup_stale(self, db_session: Session) -> None:
        import tempfile
        tf = tempfile.NamedTemporaryFile(suffix=".age", delete=False)
        tf.close()
        db_session.execute(text(
            "INSERT INTO backup_records (id, backup_type, file_path, status, started_at, completed_at, sha256)"  # noqa: E501
            " VALUES (:id, 'full', :fp, 'completed', :t, :t, 'abc')"
        ), {"id": str(uuid4()), "fp": tf.name, "t": NOW - timedelta(hours=30)})
        db_session.commit()
        c = check_backup(db_session, NOW)
        assert c.status == STALE


class TestCredentialCheck:
    def test_returns_known_status(self) -> None:
        c = check_credential(NOW)
        assert c.status in ALLOWED_STATUSES


class TestNotificationCheck:
    def test_returns_unknown(self) -> None:
        c = check_notification(NOW)
        assert c.status == UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════
# Aggregate
# ═══════════════════════════════════════════════════════════════════════════


class TestAggregate:
    def test_all_healthy(self) -> None:
        components = [
            ComponentHealth("database", HEALTHY, ""),
            ComponentHealth("migration", HEALTHY, ""),
        ]
        assert compute_overall(components) == HEALTHY

    def test_db_unavailable_degraded(self) -> None:
        components = [
            ComponentHealth("database", UNAVAILABLE, ""),
            ComponentHealth("migration", HEALTHY, ""),
        ]
        assert compute_overall(components) == UNAVAILABLE

    def test_unknown_not_healthy(self) -> None:
        components = [ComponentHealth("migration", UNKNOWN, "")]
        assert compute_overall(components) == DEGRADED

    def test_stale_backup_degrades(self) -> None:
        components = [
            ComponentHealth("database", HEALTHY, ""),
            ComponentHealth("migration", HEALTHY, ""),
            ComponentHealth("backup", STALE, ""),
        ]
        assert compute_overall(components) == DEGRADED


class TestFullHealth:
    def test_returns_all_components(self, db_session: Session) -> None:
        _create_household(db_session)
        result = run_all_checks(db_session)
        assert len(result.components) >= 8

    def test_each_component_has_valid_status(self, db_session: Session) -> None:
        _create_household(db_session)
        result = run_all_checks(db_session)
        for c in result.components:
            assert c.status in ALLOWED_STATUSES, f"{c.component}: {c.status}"
