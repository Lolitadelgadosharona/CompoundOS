"""Sprint 007 Slice B — Component health checks V2 (integrity hardened).

Changes from V1:
- Worker: uses worker_heartbeats table, not MAX(runs.started_at)
- Restore: requires restore_verified_at timestamp within freshness window
- Backup: verifies artifact file exists + is regular file
- Mutation gate: middleware blocks writes on DB/schema failure
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

HEALTHY = "healthy"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
STALE = "stale"
UNKNOWN = "unknown"

ALLOWED_STATUSES = {HEALTHY, DEGRADED, UNAVAILABLE, STALE, UNKNOWN}
RPO_HOURS = 24
BACKUP_STALE_HOURS = 25
WORKER_HEARTBEAT_MINUTES = 5
WORKER_STALE_MINUTES = 15
RESTORE_FRESH_DAYS = 30
GUARDIAN_STALE_HOURS = 48
EXPECTED_MIGRATION_HEAD = "0020_investment_idea_bridge"


@dataclass
class ComponentHealth:
    component: str
    status: str
    reason: str = ""
    last_checked: Optional[datetime] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthResult:
    overall: str
    components: list[ComponentHealth]
    checked_at: datetime


def check_database(session: Session, now: datetime) -> ComponentHealth:
    try:
        row = session.execute(text("SELECT 1")).fetchone()
        if row is None:
            return ComponentHealth("database", UNAVAILABLE, "No result")
        return ComponentHealth("database", HEALTHY, "Connected", now)
    except Exception as e:
        return ComponentHealth("database", UNAVAILABLE, _safe(str(e)), now)


def check_migration_head(session: Session, now: datetime) -> ComponentHealth:
    try:
        row = session.execute(text(
            "SELECT version_num FROM alembic_version")).fetchone()
        if not row:
            return ComponentHealth("migration", UNAVAILABLE, "No revision", now)
        current = row[0]
        if current != EXPECTED_MIGRATION_HEAD:
            return ComponentHealth(
                "migration", DEGRADED, f"Head mismatch: {current}", now)
        return ComponentHealth("migration", HEALTHY, f"Head {current}", now)
    except Exception as e:
        return ComponentHealth("migration", UNAVAILABLE, _safe(str(e)), now)


def check_backup(session: Session, now: datetime) -> ComponentHealth:
    try:
        row = session.execute(text(
            "SELECT completed_at, file_path, sha256 FROM backup_records"
            " WHERE status='completed' ORDER BY completed_at DESC LIMIT 1"
        )).fetchone()
        if not row:
            return ComponentHealth("backup", UNKNOWN, "No backup found", now)
        completed_at, file_path, sha256 = row
        if not completed_at:
            return ComponentHealth("backup", UNKNOWN, "No completion time", now)
        age_hours = (now - completed_at).total_seconds() / 3600

        if file_path and sha256:
            try:
                p = Path(file_path)
                if not p.exists():
                    return ComponentHealth("backup", STALE,
                                           "Artifact missing", now)
                if not p.is_file():
                    return ComponentHealth("backup", STALE,
                                           "Artifact not a file", now)
            except OSError:
                return ComponentHealth("backup", STALE,
                                       "Artifact unreadable", now)

        if age_hours <= RPO_HOURS:
            return ComponentHealth("backup", HEALTHY,
                                   f"Last {age_hours:.1f}h ago", now,
                                   {"rpo_hours": RPO_HOURS})
        if age_hours <= BACKUP_STALE_HOURS:
            return ComponentHealth("backup", DEGRADED,
                                   f"Old {age_hours:.1f}h", now)
        return ComponentHealth("backup", STALE,
                               f"Stale {age_hours:.1f}h — RPO {RPO_HOURS}h", now)
    except Exception as e:
        return ComponentHealth("backup", UNKNOWN, _safe(str(e)), now)


def check_restore_verification(
    session: Session, now: datetime,
) -> ComponentHealth:
    try:
        row = session.execute(text(
            "SELECT restore_verified_at FROM backup_records"
            " WHERE restore_verified=TRUE AND restore_verified_at IS NOT NULL"
            " ORDER BY restore_verified_at DESC LIMIT 1"
        )).fetchone()
        if not row or not row[0]:
            return ComponentHealth("restore_verification", UNKNOWN,
                                   "No restore verified", now)
        verified_at = row[0]
        age_days = (now - verified_at).total_seconds() / 86400
        if age_days <= RESTORE_FRESH_DAYS:
            return ComponentHealth("restore_verification", HEALTHY,
                                   f"Last verified {age_days:.0f}d ago", now)
        return ComponentHealth("restore_verification", STALE,
                               f"Last verified {age_days:.0f}d ago", now)
    except Exception as e:
        return ComponentHealth("restore_verification", UNKNOWN,
                               _safe(str(e)), now)


def check_worker(session: Session, now: datetime) -> ComponentHealth:
    try:
        row = session.execute(text(
            "SELECT heartbeat_at, stopped_at FROM worker_heartbeats"
            " WHERE stopped_at IS NULL"
            " ORDER BY heartbeat_at DESC LIMIT 1"
        )).fetchone()
        if not row:
            return ComponentHealth("worker", UNKNOWN,
                                   "No heartbeat recorded", now)
        heartbeat_at, stopped_at = row
        age_minutes = (now - heartbeat_at).total_seconds() / 60
        if age_minutes <= WORKER_HEARTBEAT_MINUTES:
            return ComponentHealth("worker", HEALTHY,
                                   f"Heartbeat {age_minutes:.0f}m ago", now)
        if age_minutes <= WORKER_STALE_MINUTES:
            return ComponentHealth("worker", DEGRADED,
                                   f"Heartbeat {age_minutes:.0f}m ago", now)
        return ComponentHealth("worker", STALE,
                               f"Heartbeat {age_minutes:.0f}m ago", now)
    except Exception as e:
        return ComponentHealth("worker", UNKNOWN, _safe(str(e)), now)


def check_leases(session: Session, now: datetime) -> ComponentHealth:
    try:
        active_row = session.execute(text(
            "SELECT COUNT(*) FROM leases WHERE released_at IS NULL"
        )).fetchone()
        stale_row = session.execute(text(
            "SELECT COUNT(*) FROM leases WHERE released_at IS NULL"
            " AND expires_at < :now"
        ), {"now": now}).fetchone()
        active = active_row[0] if active_row else 0
        stale = stale_row[0] if stale_row else 0
        if active == 0:
            return ComponentHealth("leases", HEALTHY, "No active", now,
                                   {"active": 0, "stale": 0})
        if stale > 0:
            return ComponentHealth("leases", DEGRADED,
                                   f"{active} active, {stale} stale", now)
        return ComponentHealth("leases", HEALTHY,
                               f"{active} active", now)
    except Exception as e:
        return ComponentHealth("leases", UNKNOWN, _safe(str(e)), now)


def check_guardian(session: Session, now: datetime) -> ComponentHealth:
    try:
        row = session.execute(text(
            "SELECT MAX(evaluated_at) FROM guardian_events"
        )).fetchone()
        if not row or row[0] is None:
            return ComponentHealth("guardian", UNKNOWN, "No evaluations", now)
        age_hours = (now - row[0]).total_seconds() / 3600
        if age_hours <= GUARDIAN_STALE_HOURS:
            return ComponentHealth("guardian", HEALTHY,
                                   f"Last {age_hours:.1f}h ago", now)
        return ComponentHealth("guardian", STALE,
                               f"Last {age_hours:.1f}h ago", now)
    except Exception as e:
        return ComponentHealth("guardian", UNKNOWN, _safe(str(e)), now)


def check_credential(now: datetime) -> ComponentHealth:
    try:
        from apps.api.services.credential_manager import credential_available
        available = credential_available("deepseek")
        if available:
            return ComponentHealth("credential", HEALTHY,
                                   "Keychain available", now)
        return ComponentHealth("credential", DEGRADED,
                               "Credential not found", now)
    except Exception as e:
        return ComponentHealth("credential", UNKNOWN, _safe(str(e)), now)


def check_launchd(now: datetime) -> ComponentHealth:
    try:
        import subprocess
        result = subprocess.run(
            ["launchctl", "list", "com.compoundos.backup"],
            capture_output=True, text=True, timeout=5,
        )
        loaded = (result.returncode == 0
                  and "com.compoundos.backup" in result.stdout)
        if loaded:
            return ComponentHealth("launchd", HEALTHY, "Agent loaded", now)
        return ComponentHealth("launchd", UNKNOWN, "Agent not loaded", now)
    except Exception as e:
        return ComponentHealth("launchd", UNKNOWN, _safe(str(e)), now)


def check_notification(session: Session, now: datetime) -> ComponentHealth:
    if session is None:
        return ComponentHealth("notification", UNKNOWN,
                               "No session available", now)
    try:
        prefs_row = session.execute(text(
            "SELECT enabled FROM notification_preferences LIMIT 1"
        )).fetchone()
        if not prefs_row:
            return ComponentHealth("notification", HEALTHY,
                                   "Not configured (no impact)", now)
        enabled = prefs_row[0]
        if not enabled:
            return ComponentHealth("notification", HEALTHY,
                                   "Disabled (no impact)", now)
        import sys
        adapter_available = sys.platform == "darwin"
        if not adapter_available:
            return ComponentHealth("notification", HEALTHY,
                                   "No adapter (non-macOS, no impact)", now)
        row = session.execute(text(
            "SELECT delivery_status, delivered_at FROM notification_events"
            " ORDER BY occurred_at DESC LIMIT 1"
        )).fetchone()
        if not row:
            return ComponentHealth("notification", HEALTHY,
                                   "Enabled, no events yet", now)
        last_status, delivered_at = row
        if last_status == "delivered":
            if delivered_at:
                age_hours = (now - delivered_at).total_seconds() / 3600
                if age_hours <= 24:
                    return ComponentHealth("notification", HEALTHY,
                                           "Recent delivery", now)
                return ComponentHealth("notification", HEALTHY,
                                       f"Last delivery {age_hours:.0f}h ago", now)
            return ComponentHealth("notification", HEALTHY,
                                   "Last delivery successful", now)
        if last_status == "failed":
            return ComponentHealth("notification", DEGRADED,
                                   "Last delivery failed", now)
        if last_status == "suppressed":
            return ComponentHealth("notification", HEALTHY,
                                   "Last suppressed (no impact)", now)
        return ComponentHealth("notification", HEALTHY,
                               f"Last status: {last_status}", now)
    except Exception:
        return ComponentHealth("notification", UNKNOWN,
                               "Check error", now)


CRITICAL = {"database", "migration"}
DEGRADING = {
    "backup", "leases", "worker", "credential", "guardian",
    "restore_verification", "notification",
}


def compute_overall(components: list[ComponentHealth]) -> str:
    for c in components:
        if c.component in CRITICAL and c.status == UNAVAILABLE:
            return UNAVAILABLE
        if c.component in CRITICAL and c.status in (DEGRADED, STALE):
            return DEGRADED
    for c in components:
        if c.component in DEGRADING and c.status == UNAVAILABLE:
            return DEGRADED
        if c.component in DEGRADING and c.status == STALE:
            return DEGRADED
        if c.component in DEGRADING and c.status == DEGRADED:
            return DEGRADED
    for c in components:
        if c.status == UNKNOWN and c.component in CRITICAL:
            return DEGRADED
        if c.status == UNKNOWN and c.component in DEGRADING:
            return DEGRADED
    return HEALTHY


CheckFn = Callable[..., ComponentHealth]


def run_all_checks(
    session: Session,
    now: Optional[datetime] = None,
) -> HealthResult:
    if now is None:
        now = datetime.now(timezone.utc)

    checks: list[CheckFn] = [
        lambda: check_database(session, now),
        lambda: check_migration_head(session, now),
        lambda: check_backup(session, now),
        lambda: check_restore_verification(session, now),
        lambda: check_worker(session, now),
        lambda: check_leases(session, now),
        lambda: check_guardian(session, now),
        lambda: check_credential(now),
        lambda: check_launchd(now),
        lambda: check_notification(session, now),
    ]

    components: list[ComponentHealth] = []
    for fn in checks:
        try:
            components.append(fn())
        except Exception as e:
            components.append(
                ComponentHealth("unknown", UNKNOWN, _safe(str(e)), now))

    result = HealthResult(
        overall=compute_overall(components),
        components=components,
        checked_at=now,
    )

    # Dispatch notification on degradation — fire-and-forget, never crash health
    if result.overall in (DEGRADED, UNAVAILABLE):
        try:
            from apps.api.services.notification_service import dispatch_notification
            dispatch_notification(
                session, source="health",
                event_type=result.overall,
                severity="warning" if result.overall == DEGRADED else "critical",
                now=now,
            )
        except Exception:
            pass  # notification failure must not affect health response

    return result


def _safe(msg: str) -> str:
    for pattern in ("password=", "://", "DSN", "/Users/", "/home/", "Traceback"):
        if pattern in msg:
            return "Internal error"
    return msg[:200] if len(msg) > 200 else msg
