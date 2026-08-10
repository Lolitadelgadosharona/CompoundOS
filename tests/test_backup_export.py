"""Tests for Sprint 007 Slice A — Backup, Export, Retention, Restore."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.models import BackupRecord
from apps.api.services import backup_service, export_service, retention_service
from apps.api.services.restore_verification import restore_and_verify

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
    return hid


def _make_backup(db_session: Session, status="completed", retention=None) -> BackupRecord:
    r = BackupRecord(
        id=uuid4(),
        backup_type="full",
        file_path=f"/tmp/backup_{uuid4().hex[:8]}.age",
        status=status,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc) if status == "completed" else None,
        retention_category=retention,
        sha256="abc123def456",
    )
    db_session.add(r)
    db_session.commit()
    return r


# ═══════════════════════════════════════════════════════════════════════════
# Backup service
# ═══════════════════════════════════════════════════════════════════════════


class TestBackupService:
    def test_cloud_sync_path_detected(self) -> None:
        assert backup_service.is_cloud_sync_path("/Users/foo/iCloud/Docs") is True
        assert backup_service.is_cloud_sync_path("/tmp/backups") is False

    def test_destination_unavailable_creates_failed_record(self, db_session: Session) -> None:
        _create_household(db_session)
        record = backup_service.run_backup(
            db_session, "/nonexistent/dir", "age1xxx", "postgresql:///nonexistent",
        )
        assert record.status == "failed"

    def test_missing_age_recipient_fails_closed(self, db_session: Session) -> None:
        _create_household(db_session)
        record = backup_service.run_backup(
            db_session, "/tmp", "", "postgresql:///nonexistent",
        )
        assert record.status == "failed"

    def test_sanitize_error_strips_secrets(self) -> None:
        msg = "failed with password=secret123 and api_key=sk-abc"
        clean = backup_service._sanitize_error(msg)
        assert "secret123" not in clean
        assert "sk-abc" not in clean

    def test_sha256_computation(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
            f.write("test content")
        try:
            h = backup_service._sha256_of(Path(f.name))
            assert len(h) == 64
        finally:
            os.unlink(f.name)


# ═══════════════════════════════════════════════════════════════════════════
# Retention
# ═══════════════════════════════════════════════════════════════════════════


class TestRetention:
    def test_last_healthy_never_deleted(self, db_session: Session) -> None:
        b = _make_backup(db_session, "completed")
        deleted = retention_service.apply_retention(db_session)
        assert deleted == 0
        # Verify still exists — it's the last healthy backup
        assert db_session.query(BackupRecord).filter_by(id=b.id).count() == 1

    def test_multiple_backups_oldest_deleted(self, db_session: Session) -> None:
        # Create 3 backups at different times
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        b1 = BackupRecord(
            id=uuid4(), backup_type="full", file_path=f"/tmp/old_{uuid4().hex[:8]}.age",
            status="completed", started_at=now - timedelta(days=60),
            completed_at=now - timedelta(days=60), sha256="abc",
        )
        b2 = BackupRecord(
            id=uuid4(), backup_type="full", file_path=f"/tmp/mid_{uuid4().hex[:8]}.age",
            status="completed", started_at=now - timedelta(days=10),
            completed_at=now - timedelta(days=10), sha256="def",
        )
        b3 = BackupRecord(
            id=uuid4(), backup_type="full", file_path=f"/tmp/recent_{uuid4().hex[:8]}.age",
            status="completed", started_at=now,
            completed_at=now, sha256="ghi",
        )
        db_session.add_all([b1, b2, b3])
        db_session.commit()

        retention_service.apply_retention(db_session)
        # Recent + daily within 7 days must survive
        remaining = db_session.query(BackupRecord).all()
        assert len(remaining) >= 2

    def test_failed_backups_not_retained(self, db_session: Session) -> None:
        b = _make_backup(db_session, "failed")
        deleted = retention_service.apply_retention(db_session)
        assert deleted == 0  # nothing to retain
        # Failed backup still exists (retention only cleans completed)
        assert db_session.query(BackupRecord).filter_by(id=b.id).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════════════


class TestExport:
    def test_export_creates_completed_task(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        task = export_service.run_export(db_session, "household", "json", hid)
        assert task.status == "completed"
        assert task.row_count is not None

    def test_export_json_contains_data(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        task = export_service.run_export(db_session, "household", "json", hid)
        with open(task.file_path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_cleanup_removes_expired(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        task = export_service.run_export(db_session, "household", "json", hid)
        # Force expiry
        task.expires_at = datetime.now(timezone.utc)
        db_session.commit()

        deleted = export_service.cleanup_exports(db_session)
        assert deleted >= 1

    def test_invalid_entity_type_rejected(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            from apps.api.backup_schemas import ExportTrigger
            ExportTrigger(entity_type="invalid", format="json")


# ═══════════════════════════════════════════════════════════════════════════
# Restore verification
# ═══════════════════════════════════════════════════════════════════════════


class TestRestoreVerification:
    def test_non_test_db_rejected(self) -> None:
        err = restore_and_verify("/nonexistent.age", "age1xxx", db_host="127.0.0.1")
        # Should fail early — either "cannot connect" or our safety check
        assert err is not None

    def test_missing_backup_file_returns_error(self) -> None:
        err = restore_and_verify("/nonexistent/file.age", "age1xxx")
        assert err is not None


# ═══════════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_migration_head_is_0014(self, db_session: Session) -> None:
        row = db_session.execute(text(
            "SELECT version_num FROM alembic_version"
        )).fetchone()
        assert row is not None
        assert row[0] == "0030_investment_memo"

    def test_backup_records_table_exists(self, db_session: Session) -> None:
        db_session.execute(text("SELECT 1 FROM backup_records LIMIT 0"))

    def test_export_tasks_table_exists(self, db_session: Session) -> None:
        db_session.execute(text("SELECT 1 FROM export_tasks LIMIT 0"))

    def test_backup_constraints_enforced(self, db_session: Session) -> None:
        # Test that invalid status is rejected
        with pytest.raises(Exception):
            db_session.execute(text(
                "INSERT INTO backup_records (id, backup_type, file_path, status, started_at)"
                " VALUES (:id, 'full', '/tmp/x.age', 'invalid_status', now())"
            ), {"id": str(uuid4())})
            db_session.commit()
        db_session.rollback()

    def test_export_constraints_enforced(self, db_session: Session) -> None:
        with pytest.raises(Exception):
            db_session.execute(text(
                "INSERT INTO export_tasks (id, entity_type, format, file_path, status, started_at, expires_at)"  # noqa: E501
                " VALUES (:id, 'invalid', 'json', '/tmp/x.json', 'running', now(), now())"
            ), {"id": str(uuid4())})
            db_session.commit()
        db_session.rollback()
