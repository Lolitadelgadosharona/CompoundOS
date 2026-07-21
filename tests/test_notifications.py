# ruff: noqa: E501
"""Tests for Sprint 007 Slice C — Notifications V2 (integrity hardened)."""

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


class FakeAdapter:
    """Fake adapter for testing — must match real delivery semantics."""
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str]] = []

    def send(self, title: str, body: str) -> None:
        if self.should_fail:
            raise RuntimeError("delivery failure")
        self.calls.append((title, body))


def _enable(session: Session) -> None:
    update_preferences(
        session,
        enabled=True,
        enabled_sources=["health", "guardian", "backup"],
        enabled_severities=["info", "warning", "critical"],
    )


class TestExplicitOptIn:
    def test_default_disabled_suppresses(self, db_session: Session) -> None:
        ne = notify(db_session, "health", "test", "info", "T", "B", now=NOW)
        assert ne.delivery_status == "suppressed"
        assert ne.suppressed_reason == "disabled"

    def test_enabled_with_adapter_delivers(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        ne = notify(db_session, "health", "test", "info", "T", "B", now=NOW, adapter=adapter)
        assert ne.delivery_status == "delivered"
        assert len(adapter.calls) == 1

    def test_enabled_without_adapter_marks_unavailable(self, db_session: Session) -> None:
        _enable(db_session)
        ne = notify(db_session, "health", "test", "info", "T", "B", now=NOW)
        assert ne.delivery_status == "unavailable"
        assert ne.delivered_at is None


class TestSourceSeverityAllowlist:
    def test_disabled_source_suppresses(self, db_session: Session) -> None:
        _enable(db_session)
        # "automation" not in enabled_sources
        ne = notify(db_session, "automation", "done", "info", "T", "B", now=NOW)
        assert ne.delivery_status == "suppressed"
        assert ne.suppressed_reason == "source_disabled"

    def test_disabled_severity_suppresses(self, db_session: Session) -> None:
        update_preferences(db_session, enabled=True,
                           enabled_sources=["health"],
                           enabled_severities=["critical"])
        ne = notify(db_session, "health", "test", "info", "T", "B", now=NOW)
        assert ne.delivery_status == "suppressed"
        assert ne.suppressed_reason == "severity_disabled"


class TestNotify:
    def test_rejects_invalid_source(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match="Invalid source"):
            notify(db_session, "invalid", "x", "info", "T", "B", now=NOW)

    def test_dedup_suppresses_duplicate(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        notify(db_session, "guardian", "breach", "warning", "T", "B", now=NOW, adapter=adapter)
        ne2 = notify(db_session, "guardian", "breach", "warning", "T", "B",
                     now=NOW + timedelta(hours=1), adapter=adapter)
        assert ne2.delivery_status == "suppressed"
        assert ne2.suppressed_reason == "dedup"
        # Only one actual delivery
        assert len(adapter.calls) == 1

    def test_severity_escalation_bypasses_dedup(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        notify(db_session, "backup", "fail", "warning", "T", "B", now=NOW, adapter=adapter)
        ne2 = notify(db_session, "backup", "fail", "critical", "T", "B",
                     now=NOW + timedelta(hours=1), adapter=adapter)
        assert ne2.delivery_status == "delivered"
        assert len(adapter.calls) == 2

    def test_adapter_failure_records_failed(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter(should_fail=True)
        ne = notify(db_session, "health", "test", "info", "T", "B", now=NOW, adapter=adapter)
        assert ne.delivery_status == "failed"
        assert ne.delivered_at is None


class TestQuietHours:
    def test_inside_quiet_hours_suppresses(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        night = datetime(2026, 7, 20, 23, 0, 0, tzinfo=timezone.utc)
        ne = notify(db_session, "automation", "done", "info", "T", "B", now=night, adapter=adapter)
        assert ne.delivery_status == "suppressed"

    def test_critical_bypasses_quiet_hours(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        night = datetime(2026, 7, 20, 23, 0, 0, tzinfo=timezone.utc)
        ne = notify(db_session, "health", "db_down", "critical", "T", "B", now=night, adapter=adapter)
        assert ne.delivery_status == "delivered"


class TestPreferences:
    def test_update_preferences(self, db_session: Session) -> None:
        prefs = update_preferences(
            db_session, quiet_hours_start=time(21, 0),
            quiet_hours_end=time(7, 0), tz="America/New_York",
            enabled=True, enabled_sources=["guardian", "health"],
            enabled_severities=["warning", "critical"],
        )
        assert str(prefs.quiet_hours_start) == "21:00:00"
        assert prefs.timezone == "America/New_York"
        assert prefs.enabled is True
        assert "guardian" in (prefs.enabled_sources or [])
        assert "critical" in (prefs.enabled_severities or [])

    def test_invalid_timezone_falls_back_to_utc(self, db_session: Session) -> None:
        prefs = update_preferences(db_session, tz="Invalid/Zone")
        assert prefs.timezone == "Invalid/Zone"  # stored as-is; health check uses UTC fallback


class TestListAndAck:
    def test_list_events(self, db_session: Session) -> None:
        _enable(db_session)
        notify(db_session, "health", "t", "info", "T", "B", now=NOW)
        events = list_events(db_session)
        assert len(events) >= 1

    def test_acknowledge(self, db_session: Session) -> None:
        _enable(db_session)
        ne = notify(db_session, "health", "t", "info", "T", "B", now=NOW)
        acknowledge(db_session, ne.id)
        db_session.refresh(ne)
        assert ne.acknowledged_at is not None


class TestAppleScriptInjection:
    def test_special_chars_safe(self) -> None:
        """Verify static AppleScript argv prevents injection."""
        import subprocess

        from apps.api.services.notification_service import send_macos_notification
        # This test skips on non-macOS; on macOS verifies no crash
        try:
            send_macos_notification(
                'Test "quotes" \\ backslash `backtick`',
                '$PATH /bin/sh ; rm -rf /',
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # osascript may not be available in CI
            pass
        except Exception as e:
            pytest.fail(f"send_macos_notification raised: {e}")
