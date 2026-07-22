"""Sprint 007 Slice A — Backup service.

PostgreSQL custom dump → age encryption → manifest → SHA256 → atomic write.
Fail closed if encryption not configured. Cloud-sync paths blocked.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from apps.api.config import get_database_url
from apps.api.models import BackupRecord

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

CLOUD_SYNC_PATHS = {
    "iCloud", "Mobile Documents", "Dropbox", "OneDrive",
    "Google Drive", "Box Sync",
}

MIN_FREE_SPACE_FACTOR = 2  # need 2× DB size free

# ═══════════════════════════════════════════════════════════════════════════


def get_db_size_bytes(db_url: str) -> int:
    """Estimate database size for disk-space pre-flight."""
    result = subprocess.run(
        ["psql", "-d", db_url, "-tAc",
         "SELECT pg_database_size(current_database())"],
        capture_output=True, text=True, timeout=10,
    )
    return int(result.stdout.strip() or 0)


def get_db_size_bytes_via_pg_dump() -> int:
    """Estimate by checking current database size via psql."""
    return get_db_size_bytes(get_database_url())


def is_cloud_sync_path(path: str) -> bool:
    """Detect known cloud-sync directories by path component matching."""
    resolved = os.path.realpath(path)
    components = set(c.lower() for c in Path(resolved).parts)
    markers_lower = {m.lower() for m in CLOUD_SYNC_PATHS}
    return bool(components & markers_lower)


def check_destination(dest_dir: str, db_size: int) -> str | None:
    """Pre-flight checks. Returns error string or None."""
    if is_cloud_sync_path(dest_dir):
        return "Cloud-sync destination forbidden"
    if not os.path.isdir(dest_dir):
        return f"Destination directory does not exist: {dest_dir}"
    if not os.access(dest_dir, os.W_OK):
        return f"Destination directory not writable: {dest_dir}"
    stat = os.statvfs(dest_dir)
    free = stat.f_frsize * stat.f_bavail
    if free < db_size * MIN_FREE_SPACE_FACTOR:
        return f"Disk space low: {free} free, {db_size * MIN_FREE_SPACE_FACTOR} needed"
    # Check for mount (empty root may indicate unmounted external disk)
    if free == 0:
        return "Destination has zero available blocks — possible unmounted disk"
    return None


def run_backup(
    session: Session,
    dest_dir: str,
    age_recipient: str,
    db_url: str,
) -> BackupRecord:
    """Full backup pipeline. Returns completed BackupRecord."""
    db_size = 0
    try:
        db_size = get_db_size_bytes(db_url)
    except Exception:
        pass

    err = check_destination(dest_dir, db_size)
    if err:
        record = _create_record(dest_dir, "failed", error_detail=err)
        session.add(record)
        session.commit()
        _maybe_notify_backup(record)
        return record

    record = _create_record(dest_dir, "requested")
    session.add(record)
    session.commit()
    dest = Path(dest_dir)

    try:
        # Phase 1: Dump + Encrypt (streaming, no plaintext on disk)
        record.status = "running"
        session.commit()
        encrypted_path = _do_dump_and_encrypt(db_url, dest, age_recipient, record)
        record.file_size_bytes = os.path.getsize(str(encrypted_path))
        record.encryption = "age"
        record.age_recipient = age_recipient
        session.commit()

        # Phase 2: Hash (covers ciphertext for integrity verification)
        record.sha256 = _sha256_of(encrypted_path)
        session.commit()

        # Phase 3: Verify
        record.status = "verifying"
        session.commit()
        _do_verify(encrypted_path, age_recipient)

        # Success
        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc)
        record.error_detail = None
        session.commit()
        _maybe_notify_backup(record)
        return record

    except Exception as e:
        record.status = "failed"
        record.completed_at = datetime.now(timezone.utc)
        record.error_detail = _sanitize_error(str(e))
        session.commit()
        _maybe_notify_backup(record)
        return record


def _maybe_notify_backup(record) -> None:
    """Dispatch Backup notification after record is committed."""
    event_type = "backup_complete" if record.status == "completed" else "backup_failed"
    severity = "info" if record.status == "completed" else "warning"
    try:
        from uuid import UUID

        from apps.api.database import SessionLocal
        from apps.api.services.notification_service import dispatch_notification
        household_id = _resolve_household_id()
        if household_id is None:
            return
        ns = SessionLocal()
        try:
            dispatch_notification(
                ns, source="backup", event_type=event_type,
                severity=severity, household_id=UUID(household_id),
                entity_id=str(record.id),
            )
        except Exception:
            ns.rollback()
        finally:
            ns.close()
    except Exception:
        pass


def _resolve_household_id() -> str | None:
    """Resolve the singleton household ID for backup notifications."""
    try:
        from sqlalchemy import text

        from apps.api.database import SessionLocal
        s = SessionLocal()
        try:
            row = s.execute(text("SELECT id FROM household_profiles LIMIT 1")).fetchone()
            return str(row[0]) if row else None
        finally:
            s.close()
    except Exception:
        return None


def verify_backup(path: str, age_recipient: str) -> str | None:
    """Verify an existing backup file. Returns error or None."""
    return _do_verify(Path(path), age_recipient)


# ═══════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════


def _create_record(
    dest_dir: str,
    status: str,
    error_detail: str | None = None,
) -> BackupRecord:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return BackupRecord(
        id=uuid4(),
        backup_type="full",
        file_path=str(Path(dest_dir) / f"compoundos_backup_{stamp}.age"),
        status=status,
        error_detail=error_detail,
        started_at=datetime.now(timezone.utc),
    )


def _do_dump_and_encrypt(
    db_url: str, dest: Path, age_recipient: str, record: BackupRecord,
) -> Path:
    """Stream pg_dump stdout → age stdin → atomic write. No plaintext on disk."""
    age_path = dest / f"{record.id}.age"
    tmp_age = Path(str(age_path) + ".tmp")
    try:
        dump_proc = subprocess.Popen(
            ["pg_dump", "--format=custom", "--dbname", db_url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        encrypt_proc = subprocess.Popen(
            ["age", "--encrypt", "-r", age_recipient, "-o", str(tmp_age)],
            stdin=dump_proc.stdout, stderr=subprocess.PIPE,
        )
        if dump_proc.stdout is not None:
            dump_proc.stdout.close()

        dump_stderr = dump_proc.stderr.read() if dump_proc.stderr else b""
        dump_rc = dump_proc.wait(timeout=120)
        if dump_rc != 0:
            raise RuntimeError(f"pg_dump failed (rc={dump_rc}): {_sanitize_error(dump_stderr.decode(errors='replace'))}")  # noqa: E501

        encrypt_stderr = encrypt_proc.stderr.read() if encrypt_proc.stderr else b""
        encrypt_rc = encrypt_proc.wait(timeout=60)
        if encrypt_rc != 0:
            raise RuntimeError(f"age encrypt failed (rc={encrypt_rc}): {_sanitize_error(encrypt_stderr.decode(errors='replace'))}")  # noqa: E501

        os.rename(str(tmp_age), str(age_path))
        os.chmod(str(age_path), 0o600)
        return age_path
    finally:
        if tmp_age.exists():
            tmp_age.unlink()


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _do_verify(backup_path: Path, age_recipient: str) -> str | None:
    """Decrypt + manifest check. Returns error or None."""
    tmp_dec = Path(str(backup_path) + ".verify.tmp")
    try:
        # Decrypt
        r = subprocess.run(
            ["age", "--decrypt", "-o", str(tmp_dec), str(backup_path)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return f"age decrypt failed: {_sanitize_error(r.stderr)}"

        # Read manifest from custom format
        r2 = subprocess.run(
            ["pg_restore", "--list", str(tmp_dec)],
            capture_output=True, text=True, timeout=30,
        )
        if r2.returncode != 0:
            return f"pg_restore list failed: {_sanitize_error(r2.stderr)}"
        if not r2.stdout.strip():
            return "pg_restore returned empty manifest"
        return None
    finally:
        if tmp_dec.exists():
            tmp_dec.unlink()


def _sanitize_error(msg: str) -> str:
    """Strip potential secrets from error messages."""
    # Remove known credential patterns
    for marker in ("password=", "PASSWORD=", "api_key=", "sk-"):
        msg = _redact_param(msg, marker)
    return msg[:1000]


def _redact_param(msg: str, key: str) -> str:
    import re
    return re.sub(rf"{re.escape(key)}\S+", key + "***", msg)
