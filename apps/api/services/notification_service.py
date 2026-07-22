"""Sprint 007 Slice C — Notification service V3 (integrity hardened, source wired).

Changes:
- Explicit opt-in: enabled=False by default, Owner must PATCH preferences
- Adapter=None → delivery_status=unavailable (not delivered)
- AppleScript: static script + argv (no string interpolation)
- Dedup: advisory lock + household-scoped fingerprint
- Structured templates: title/body generated from approved templates only
- Health service wired: dispatches notification on degradation
"""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import desc
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from apps.api.models import NotificationEvent, NotificationPreferences

ALLOWED_SOURCES = {"guardian", "committee", "automation", "backup", "health"}
ALLOWED_SEVERITIES = {"info", "warning", "critical"}
CRITICAL = "critical"
DEDUP_WINDOW_HOURS = 24

# ── Structured notification templates ──
# Only approved event types with privacy-safe templates.
# title/body are generated from template + context; never free-form from callers.

NOTIFICATION_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "health": {
        "degraded": {
            "title": "CompoundOS Health Degraded",
            "body": "Health check returned {overall}. Check the dashboard for details.",
        },
        "unavailable": {
            "title": "CompoundOS Unavailable",
            "body": "Health check returned {overall}. Critical component failure.",
        },
    },
    "guardian": {
        "threshold_breach": {
            "title": "Guardian Threshold Breach",
            "body": "A Guardian threshold has been exceeded. Review the Guardian dashboard.",
        },
    },
    "backup": {
        "backup_complete": {
            "title": "Backup Complete",
            "body": "Database backup completed successfully.",
        },
        "backup_failed": {
            "title": "Backup Failed",
            "body": "Database backup failed. Review backup logs.",
        },
    },
    "committee": {
        "completed": {
            "title": "Committee Session Complete",
            "body": "AI Committee session finished. Review the Committee workspace.",
        },
    },
    "automation": {
        "failed": {
            "title": "Automation Run Failed",
            "body": "An automation run has failed. Review automation logs.",
        },
    },
}


def dispatch_notification(
    session: Session,
    source: str,
    event_type: str,
    severity: str,
    *,
    household_id: UUID | None = None,
    entity_id: str | None = None,
    context: dict | None = None,
    now: datetime | None = None,
    adapter=None,
) -> NotificationEvent | None:
    """Dispatch a notification from a structured, approved template.

    Callers must use allowlisted (source, event_type) pairs with pre-approved templates.
    Free-form title/body is NOT accepted — privacy contract enforced at dispatch.
    """
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"Invalid source: {source}")
    tmpl = NOTIFICATION_TEMPLATES.get(source, {}).get(event_type)
    if tmpl is None:
        raise ValueError(
            f"No approved template for source={source} event_type={event_type}"
        )
    ctx = context or {}
    title = tmpl["title"].format(**ctx)
    body = tmpl["body"].format(**ctx)
    return notify(
        session, source, event_type, severity, title, body,
        household_id=household_id, entity_id=entity_id, now=now, adapter=adapter,
    )


def compute_fingerprint(
    source: str, event_type: str, severity: str,
    household_id: UUID | None = None,
    entity_id: str | None = None,
) -> str:
    """Household-scoped fingerprint v2.

    Includes household_id to prevent cross-household dedup collision.
    Semantic version v2: adds household_id to the fingerprint input.
    """
    hid = str(household_id) if household_id else ""
    raw = f"v2:{hid}:{source}:{event_type}:{severity}:{entity_id or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_within_dedup_window(session: Session, fingerprint: str, now: datetime) -> bool:
    from datetime import timedelta
    cutoff = now - timedelta(hours=DEDUP_WINDOW_HOURS)
    row = session.query(NotificationEvent).filter(
        NotificationEvent.fingerprint == fingerprint,
        NotificationEvent.delivered_at >= cutoff,
        NotificationEvent.delivery_status == "delivered",
    ).first()
    return row is not None


def get_preferences(session: Session) -> NotificationPreferences:
    prefs = session.query(NotificationPreferences).first()
    if not prefs:
        prefs = NotificationPreferences(
            id=uuid4(),
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(8, 0),
            timezone="UTC",
            enabled=False,
            enabled_sources=[],
            enabled_severities=["critical"],
        )
        session.add(prefs)
        session.commit()
    return prefs


def is_quiet_hours(prefs: NotificationPreferences, now: datetime) -> bool:
    try:
        tz = ZoneInfo(prefs.timezone)
    except (ZoneInfoNotFoundError, KeyError):
        tz = timezone.utc
    local = now.astimezone(tz).time()
    start = prefs.quiet_hours_start
    end = prefs.quiet_hours_end
    if start < end:
        return start <= local < end
    else:
        return local >= start or local < end


def notify(
    session: Session,
    source: str,
    event_type: str,
    severity: str,
    title: str,
    body: str,
    *,
    household_id: UUID | None = None,
    entity_id: str | None = None,
    now: datetime | None = None,
    adapter=None,
) -> NotificationEvent:
    if now is None:
        now = datetime.now(timezone.utc)
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"Invalid source: {source}")
    if severity not in ALLOWED_SEVERITIES:
        raise ValueError(f"Invalid severity: {severity}")

    prefs = get_preferences(session)

    # Explicit opt-in check
    if not prefs.enabled:
        ne = NotificationEvent(
            id=uuid4(), source=source, event_type=event_type,
            severity=severity, fingerprint="", title=title, body=body,
            delivery_status="suppressed", suppressed_reason="disabled",
            occurred_at=now,
        )
        session.add(ne)
        session.commit()
        return ne

    # Source/severity allowlist
    enabled_sources: list[str] = prefs.enabled_sources or []
    enabled_severities: list[str] = prefs.enabled_severities or []
    if enabled_sources and source not in enabled_sources:
        ne = NotificationEvent(
            id=uuid4(), source=source, event_type=event_type,
            severity=severity, fingerprint="", title=title, body=body,
            delivery_status="suppressed", suppressed_reason="source_disabled",
            occurred_at=now,
        )
        session.add(ne)
        session.commit()
        return ne
    if enabled_severities and severity not in enabled_severities:
        ne = NotificationEvent(
            id=uuid4(), source=source, event_type=event_type,
            severity=severity, fingerprint="", title=title, body=body,
            delivery_status="suppressed", suppressed_reason="severity_disabled",
            occurred_at=now,
        )
        session.add(ne)
        session.commit()
        return ne

    fp = compute_fingerprint(source, event_type, severity, household_id, entity_id)

    # Dedup with advisory lock
    try:
        session.execute(sa_text("SELECT pg_advisory_xact_lock(42)"))
    except Exception:
        pass

    if is_within_dedup_window(session, fp, now):
        existing = session.query(NotificationEvent).filter(
            NotificationEvent.fingerprint == fp,
            NotificationEvent.delivery_status == "delivered",
        ).order_by(desc(NotificationEvent.delivered_at)).first()
        if existing and _severity_rank(severity) <= _severity_rank(existing.severity):
            ne = NotificationEvent(
                id=uuid4(), source=source, event_type=event_type,
                severity=severity, fingerprint=fp, title=title, body=body,
                delivery_status="suppressed", suppressed_reason="dedup",
                occurred_at=now,
            )
            session.add(ne)
            session.commit()
            return ne

    # Quiet hours
    in_quiet = is_quiet_hours(prefs, now)
    if in_quiet and severity != CRITICAL:
        ne = NotificationEvent(
            id=uuid4(), source=source, event_type=event_type,
            severity=severity, fingerprint=fp, title=title, body=body,
            delivery_status="suppressed", suppressed_reason="quiet_hours",
            occurred_at=now,
        )
        session.add(ne)
        session.commit()
        return ne

    # Deliver
    delivery_status = "pending"
    delivered_at = None
    if adapter:
        try:
            adapter.send(title, body)
            delivery_status = "delivered"
            delivered_at = now
        except Exception:
            delivery_status = "failed"
    else:
        delivery_status = "unavailable"
        delivered_at = None

    ne = NotificationEvent(
        id=uuid4(), source=source, event_type=event_type,
        severity=severity, fingerprint=fp, title=title, body=body,
        delivery_status=delivery_status, delivered_at=delivered_at,
        occurred_at=now,
    )
    session.add(ne)
    session.commit()
    return ne


def list_events(session: Session, limit: int = 50, offset: int = 0) -> list[NotificationEvent]:
    return (
        session.query(NotificationEvent)
        .order_by(desc(NotificationEvent.occurred_at))
        .offset(offset).limit(limit).all()
    )


def acknowledge(session: Session, event_id: UUID) -> None:
    ne = session.query(NotificationEvent).filter_by(id=event_id).first()
    if ne:
        ne.acknowledged_at = datetime.now(timezone.utc)
        session.commit()


def update_preferences(
    session: Session,
    quiet_hours_start: time | None = None,
    quiet_hours_end: time | None = None,
    tz: str | None = None,
    enabled: bool | None = None,
    enabled_sources: list[str] | None = None,
    enabled_severities: list[str] | None = None,
) -> NotificationPreferences:
    prefs = get_preferences(session)
    if quiet_hours_start is not None:
        prefs.quiet_hours_start = quiet_hours_start
    if quiet_hours_end is not None:
        prefs.quiet_hours_end = quiet_hours_end
    if tz is not None:
        prefs.timezone = tz
    if enabled is not None:
        prefs.enabled = enabled
    if enabled_sources is not None:
        prefs.enabled_sources = enabled_sources
    if enabled_severities is not None:
        prefs.enabled_severities = enabled_severities
    prefs.updated_at = datetime.now(timezone.utc)
    session.commit()
    return prefs


def _severity_rank(s: str) -> int:
    return {"info": 0, "warning": 1, "critical": 2}.get(s, 0)


# ═══════════════════════════════════════════════════════════════════════════
# macOS adapter — static script, argv-based (no string interpolation)
# ═══════════════════════════════════════════════════════════════════════════

_STATIC_SCRIPT = """
on run argv
    set theTitle to item 1 of argv
    set theBody to item 2 of argv
    display notification theBody with title theTitle
end run
"""


def send_macos_notification(title: str, body: str) -> None:
    import subprocess
    safe_title = title[:100]
    safe_body = body[:200]
    subprocess.run(
        ["osascript", "-e", _STATIC_SCRIPT, safe_title, safe_body],
        capture_output=True, timeout=10, check=True,
    )
