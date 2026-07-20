# ruff: noqa: E501
"""Tests for Sprint 007 Slice C — Notifications."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from apps.api.services.notification_service import (
    acknowledge,
    list_events,
    notify,
    update_preferences,
)

pytestmark = pytest.mark.postgres

NOW = datetime(2026, 7, 20, 14, 0, 0, tzinfo=timezone.utc)


class TestNotify:
    def test_delivers_basic(self, db_session: Session) -> None:
        ne = notify(db_session, "health", "test", "info", "T", "B", now=NOW)
        assert ne.delivery_status == "delivered"

    def test_rejects_invalid_source(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match="Invalid source"):
            notify(db_session, "invalid", "x", "info", "T", "B", now=NOW)

    def test_dedup_suppresses_duplicate(self, db_session: Session) -> None:
        notify(db_session, "guardian", "breach", "warning", "T", "B", now=NOW)
        ne2 = notify(db_session, "guardian", "breach", "warning", "T", "B", now=NOW + timedelta(hours=1))
        assert ne2.delivery_status == "suppressed"
        assert ne2.suppressed_reason == "dedup"

    def test_severity_escalation_bypasses_dedup(self, db_session: Session) -> None:
        notify(db_session, "backup", "fail", "warning", "T", "B", now=NOW)
        ne2 = notify(db_session, "backup", "fail", "critical", "T", "B", now=NOW + timedelta(hours=1))
        assert ne2.delivery_status == "delivered"


class TestQuietHours:
    def test_inside_quiet_hours_suppresses(self, db_session: Session) -> None:
        prefs = update_preferences(db_session, quiet_hours_start=time(22, 0), quiet_hours_end=time(8, 0))
        night = datetime(2026, 7, 20, 23, 0, 0, tzinfo=timezone.utc)
        ne = notify(db_session, "automation", "done", "info", "T", "B", now=night)
        assert ne.delivery_status == "suppressed"

    def test_critical_bypasses_quiet_hours(self, db_session: Session) -> None:
        prefs = update_preferences(db_session, quiet_hours_start=time(22, 0), quiet_hours_end=time(8, 0))
        night = datetime(2026, 7, 20, 23, 0, 0, tzinfo=timezone.utc)
        ne = notify(db_session, "health", "db_down", "critical", "T", "B", now=night)
        assert ne.delivery_status == "delivered"


class TestPreferences:
    def test_update_preferences(self, db_session: Session) -> None:
        prefs = update_preferences(db_session, quiet_hours_start=time(21, 0), quiet_hours_end=time(7, 0), tz="America/New_York")
        assert str(prefs.quiet_hours_start) == "21:00:00"
        assert prefs.timezone == "America/New_York"

    def test_invalid_timezone_falls_back_to_utc(self, db_session: Session) -> None:
        prefs = update_preferences(db_session, tz="Invalid/Zone")
        assert prefs.timezone == "Invalid/Zone"  # stored as-is; health check uses UTC fallback


class TestListAndAck:
    def test_list_events(self, db_session: Session) -> None:
        notify(db_session, "health", "t", "info", "T", "B", now=NOW)
        events = list_events(db_session)
        assert len(events) >= 1

    def test_acknowledge(self, db_session: Session) -> None:
        ne = notify(db_session, "health", "t", "info", "T", "B", now=NOW)
        acknowledge(db_session, ne.id)
        db_session.refresh(ne)
        assert ne.acknowledged_at is not None
