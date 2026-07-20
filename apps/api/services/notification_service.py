"""Sprint 007 Slice C — Notification service."""

from __future__ import annotations

import hashlib
from datetime import datetime, time, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import desc
from sqlalchemy.orm import Session

from apps.api.models import NotificationEvent, NotificationPreferences

ALLOWED_SOURCES = {"guardian", "committee", "automation", "backup", "health"}
ALLOWED_SEVERITIES = {"info", "warning", "critical"}
CRITICAL = "critical"
DEDUP_WINDOW_HOURS = 24
QUIET_START_DEFAULT = time(22, 0)
QUIET_END_DEFAULT = time(8, 0)


def compute_fingerprint(source: str, event_type: str, severity: str, entity_id: str | None = None) -> str:
    raw = f"{source}:{event_type}:{severity}:{entity_id or ''}"
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
        from datetime import time as dt_time
        prefs = NotificationPreferences(
            id=uuid4(),
            quiet_hours_start=dt_time(22, 0),
            quiet_hours_end=dt_time(8, 0),
            timezone="UTC",
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

    fp = compute_fingerprint(source, event_type, severity, entity_id)
    prefs = get_preferences(session)

    # Dedup check
    if is_within_dedup_window(session, fp, now):
        # Severity escalation: if new severity > old, allow
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
        delivery_status = "delivered"
        delivered_at = now

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
) -> NotificationPreferences:
    prefs = get_preferences(session)
    if quiet_hours_start is not None:
        prefs.quiet_hours_start = quiet_hours_start
    if quiet_hours_end is not None:
        prefs.quiet_hours_end = quiet_hours_end
    if tz is not None:
        prefs.timezone = tz
    prefs.updated_at = datetime.now(timezone.utc)
    session.commit()
    return prefs


def _severity_rank(s: str) -> int:
    return {"info": 0, "warning": 1, "critical": 2}.get(s, 0)


# ═══════════════════════════════════════════════════════════════════════════
# macOS adapter
# ═══════════════════════════════════════════════════════════════════════════

def send_macos_notification(title: str, body: str) -> None:
    import subprocess
    safe_title = title.replace('"', "'")[:100]
    safe_body = body.replace('"', "'")[:200]
    script = f'display notification "{safe_body}" with title "{safe_title}"'
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, timeout=10, check=True,
    )
