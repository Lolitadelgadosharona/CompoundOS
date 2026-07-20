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
    return get_db_size_bytes(DATABASE_URL)


def is_cloud_sync_path(path: str) -> bool:
    """Detect known cloud-sync directories."""
    resolved = os.path.realpath(path).lower()
    for marker in CLOUD_SYNC_PATHS:
        if marker.lower() in resolved:
            return True
    return False


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
        return record

    record = _create_record(dest_dir, "requested")
    session.add(record)
    session.commit()
    dest = Path(dest_dir)

    try:
        # Phase 1: Dump
        record.status = "running"
        session.commit()
        dump_path = _do_dump(db_url, dest, record)
        record.file_size_bytes = os.path.getsize(str(dump_path))
        session.commit()

        # Phase 2: Encrypt
        encrypted_path = _do_encrypt(dump_path, age_recipient)
        os.unlink(str(dump_path))  # remove plaintext immediately
        final_path = encrypted_path
        record.file_size_bytes = os.path.getsize(str(final_path))
        record.encryption = "age"
        record.age_recipient = age_recipient
        session.commit()

        # Phase 3: Hash
        record.sha256 = _sha256_of(final_path)
        session.commit()

        # Phase 4: Verify
        record.status = "verifying"
        session.commit()
        _do_verify(final_path, age_recipient)

        # Success
        record.status = "completed"
        record.completed_at = datetime.now(timezone.utc)
        record.error_detail = None
        session.commit()
        return record

    except Exception as e:
        record.status = "failed"
        record.completed_at = datetime.now(timezone.utc)
        record.error_detail = _sanitize_error(str(e))
        session.commit()
        return record


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


def _do_dump(db_url: str, dest: Path, record: BackupRecord) -> Path:
    """Run pg_dump --format=custom to temp file, atomic rename."""
    tmp = dest / f".tmp_{record.id}.dump"
    try:
        result = subprocess.run(
            ["pg_dump", "--format=custom", "--dbname", db_url,
             "--file", str(tmp)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {_sanitize_error(result.stderr)}")
        final = dest / f"{record.id}.dump"
        os.rename(str(tmp), str(final))
        os.chmod(str(final), 0o600)
        return final
    finally:
        if tmp.exists():
            tmp.unlink()


def _do_encrypt(dump_path: Path, recipient: str) -> Path:
    """Encrypt with age. Atomic write to .age file."""
    age_path = Path(str(dump_path) + ".age")
    tmp = Path(str(age_path) + ".tmp")
    try:
        result = subprocess.run(
            ["age", "--encrypt", "-r", recipient,
             "-o", str(tmp), str(dump_path)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"age encrypt failed: {_sanitize_error(result.stderr)}")
        os.rename(str(tmp), str(age_path))
        os.chmod(str(age_path), 0o600)
        return age_path
    finally:
        if tmp.exists():
            tmp.unlink()


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
