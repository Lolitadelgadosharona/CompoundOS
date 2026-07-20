r"""Sprint 007 Slice A — Manual backup/export/verify CLI.

Usage:
  python -m apps.cli backup <dest_dir> <age_recipient>
  python -m apps.cli verify <backup_path> <age_recipient>
  python -m apps.cli export <entity_type> <format> [household_id]
  python -m apps.cli retention
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
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
            db_url = __import__("apps.api.config").get_database_url()  # noqa: E501
            record = backup_service.run_backup(session, dest, recipient, db_url)
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

    elif cmd == "launchd-install":
        _install_launchd()
    elif cmd == "launchd-uninstall":
        _uninstall_launchd()
    elif cmd == "launchd-status":
        _launchd_status()
    else:
        _usage()


def _usage() -> None:
    print("CompoundOS Backup CLI")
    print("  python -m apps.cli backup <dest_dir> <age_recipient>")
    print("  python -m apps.cli verify <backup_path> <age_recipient>")
    print("  python -m apps.cli export <entity_type> <format> [household_id]")
    print("  python -m apps.cli retention")
    print("  python -m apps.cli restore-verify <backup_path> <age_recipient>")
    print("  python -m apps.cli launchd-install    # Opt-in daily backup agent")
    print("  python -m apps.cli launchd-uninstall  # Remove backup agent")
    print("  python -m apps.cli launchd-status     # Check agent status")


def _get_household_id(session) -> UUID:
    from sqlalchemy import text
    row = session.execute(text(
        "SELECT id FROM household_profiles LIMIT 1"
    )).fetchone()
    if not row:
        print("No household found. Provide household_id argument.")
        sys.exit(1)
    return row[0]


# ═══════════════════════════════════════════════════════════════
# Launchd opt-in backup agent
# ═══════════════════════════════════════════════════════════════

AGENT_LABEL = "com.compoundos.backup"


def _plist_content() -> str:  # noqa: E501
    """Generate launchd plist. Never installed without explicit Owner command."""
    python_exe = __import__("sys").executable
    home_dir = Path.home()
    dest = __import__("os").environ.get(
        "COMPOUNDOS_BACKUP_DEST",
        str(home_dir / ".compoundos" / "backups"),
    )
    recipient = __import__("os").environ.get(
        "COMPOUNDOS_BACKUP_AGE_RECIPIENT", "",
    )
    plist_path = str(home_dir / "Library" / "LaunchAgents"
                     / "com.compoundos.backup.plist")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.compoundos.backup</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_exe}</string>
        <string>-m</string>
        <string>apps.cli</string>
        <string>backup</string>
        <string>{dest}</string>
        <string>{recipient}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{plist_path}.log</string>
    <key>StandardErrorPath</key>
    <string>{plist_path}.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""


def _install_launchd() -> None:
    """Opt-in: install launchd agent. Owner must explicitly run this command."""
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = plist_dir / f"{AGENT_LABEL}.plist"
    plist_dir.mkdir(parents=True, exist_ok=True)
    content = _plist_content()
    with open(str(plist_path), "w") as f:
        f.write(content)
    os.chmod(str(plist_path), 0o644)
    __import__("subprocess").run(
        ["launchctl", "load", str(plist_path)], check=True,
    )
    print(f"Backup agent installed: {plist_path}")
    print("Runs daily at 03:00.")
    print("Uninstall: python -m apps.cli launchd-uninstall")


def _uninstall_launchd() -> None:
    """Opt-in: uninstall launchd agent."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"
    if plist_path.exists():
        __import__("subprocess").run(
            ["launchctl", "unload", str(plist_path)], check=True,
        )
        os.unlink(str(plist_path))
        print(f"Backup agent uninstalled: {plist_path}")
    else:
        print("No backup agent installed.")


def _launchd_status() -> None:
    """Check if backup agent is installed and loaded."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"
    result = __import__("subprocess").run(
        ["launchctl", "list", AGENT_LABEL],
        capture_output=True, text=True,
    )
    if result.returncode == 0 and AGENT_LABEL in result.stdout:
        print("Backup agent is loaded and running.")
    else:
        print("Backup agent is not loaded.")
    print(f"Plist: {plist_path} (exists={plist_path.exists()})")


if __name__ == "__main__":
    main()
