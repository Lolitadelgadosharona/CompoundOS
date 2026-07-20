r"""Sprint 007 Slice A — Manual backup/export/verify CLI.

Usage:
  python -m apps.cli backup <dest_dir> <age_recipient>
  python -m apps.cli verify <backup_path> <age_recipient>
  python -m apps.cli export <entity_type> <format> [household_id]
  python -m apps.cli retention
"""

from __future__ import annotations

import sys
from uuid import UUID

from apps.api.database import get_session
from apps.api.services import backup_service, export_service, retention_service
from apps.api.services.restore_verification import restore_and_verify


def main() -> None:
    if len(sys.argv) < 2:
        _usage()
        return

    cmd = sys.argv[1]

    if cmd == "backup":
        if len(sys.argv) != 4:
            print("Usage: python -m apps.cli backup <dest_dir> <age_recipient>")
            return
        dest, recipient = sys.argv[2], sys.argv[3]
        session = next(get_session())
        try:
            record = backup_service.run_backup(session, dest, recipient)
            print(f"Backup {record.status}: {record.id}")
            if record.status == "completed":
                print(f"  SHA256: {record.sha256}")
                print(f"  Path: {record.file_path}")
                retention_service.apply_retention(session)
            else:
                print(f"  Error: {record.error_detail}")
        finally:
            session.close()

    elif cmd == "verify":
        if len(sys.argv) != 4:
            print("Usage: python -m apps.cli verify <backup_path> <age_recipient>")
            return
        path, recipient = sys.argv[2], sys.argv[3]
        err = backup_service.verify_backup(path, recipient)
        if err:
            print(f"VERIFY FAILED: {err}")
        else:
            print("VERIFY OK")

    elif cmd == "export":
        if len(sys.argv) < 4:
            print("Usage: python -m apps.cli export <entity_type> <format> [household_id]")
            return
        entity, fmt = sys.argv[2], sys.argv[3]
        hid = UUID(sys.argv[4]) if len(sys.argv) > 4 else None
        session = next(get_session())
        try:
            household_id = hid or _get_household_id(session)
            task = export_service.run_export(session, entity, fmt, household_id)
            print(f"Export {task.status}: {task.id}")
            print(f"  Rows: {task.row_count}")
            print(f"  Path: {task.file_path}")
            print(f"  Expires: {task.expires_at.isoformat()}")
        finally:
            session.close()

    elif cmd == "retention":
        session = next(get_session())
        try:
            deleted = retention_service.apply_retention(session)
            print(f"Retention applied: {deleted} backups deleted.")
        finally:
            session.close()

    elif cmd == "restore-verify":
        if len(sys.argv) != 4:
            print("Usage: python -m apps.cli restore-verify <backup_path> <age_recipient>")
            return
        path, recipient = sys.argv[2], sys.argv[3]
        err = restore_and_verify(path, recipient)
        if err:
            print(f"RESTORE-VERIFY FAILED: {err}")
        else:
            print("RESTORE-VERIFY OK")

    else:
        _usage()


def _usage() -> None:
    print("CompoundOS Backup CLI")
    print("  python -m apps.cli backup <dest_dir> <age_recipient>")
    print("  python -m apps.cli verify <backup_path> <age_recipient>")
    print("  python -m apps.cli export <entity_type> <format> [household_id]")
    print("  python -m apps.cli retention")
    print("  python -m apps.cli restore-verify <backup_path> <age_recipient>")


def _get_household_id(session) -> UUID:
    from sqlalchemy import text
    row = session.execute(text(
        "SELECT id FROM household_profiles LIMIT 1"
    )).fetchone()
    if not row:
        print("No household found. Provide household_id argument.")
        sys.exit(1)
    return row[0]


if __name__ == "__main__":
    main()
