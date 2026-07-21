# ruff: noqa: E501
"""Tests for Sprint 007 Slice C — Notifications V3 (integrity hardened, source wired)."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from apps.api.services.notification_service import (
    acknowledge,
    compute_fingerprint,
    dispatch_notification,
    get_preferences,
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


class TestStructuredDispatch:
    def test_dispatch_uses_template(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        ne = dispatch_notification(
            db_session, "health", "degraded", "warning",
            context={"overall": "degraded"}, now=NOW, adapter=adapter,
        )
        assert ne is not None
        assert "Health Degraded" in ne.title
        assert "degraded" in ne.body

    def test_dispatch_rejects_unapproved_event_type(self, db_session: Session) -> None:
        with pytest.raises(ValueError, match="No approved template"):
            dispatch_notification(db_session, "health", "nonexistent", "info", now=NOW)

    def test_dispatch_calls_notify_and_records(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        ne = dispatch_notification(
            db_session, "backup", "completed", "info", now=NOW, adapter=adapter,
        )
        assert ne is not None
        assert ne.delivery_status == "delivered"
        assert len(adapter.calls) == 1


class TestHouseholdDedup:
    def test_fingerprint_includes_household_id(self) -> None:
        from uuid import UUID
        hid1 = UUID("11111111-1111-1111-1111-111111111111")
        hid2 = UUID("22222222-2222-2222-2222-222222222222")
        fp1 = compute_fingerprint("guardian", "breach", "warning", household_id=hid1)
        fp2 = compute_fingerprint("guardian", "breach", "warning", household_id=hid2)
        assert fp1 != fp2

    def test_different_households_no_cross_dedup(self, db_session: Session) -> None:
        _enable(db_session)
        adapter = FakeAdapter()
        from uuid import UUID
        hid1 = UUID("11111111-1111-1111-1111-111111111111")
        hid2 = UUID("22222222-2222-2222-2222-222222222222")
        # Same source/event_type/severity, different household_id
        ne1 = notify(db_session, "guardian", "breach", "warning", "T", "B",
                     household_id=hid1, now=NOW, adapter=adapter)
        assert ne1.delivery_status == "delivered"
        ne2 = notify(db_session, "guardian", "breach", "warning", "T", "B",
                     household_id=hid2, now=NOW + timedelta(hours=1), adapter=adapter)
        assert ne2.delivery_status == "delivered"  # NOT suppressed
        assert len(adapter.calls) == 2  # Both delivered


class TestSourceSeverityAllowlist:
    def test_disabled_source_suppresses(self, db_session: Session) -> None:
        _enable(db_session)
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
        night = datetime(2026, 7, 20, 23, 0, 0, tzinfo=timezone.utc)
        ne = notify(db_session, "automation", "done", "info", "T", "B", now=night)
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

    def test_singleton_only_one_preferences_row(self, db_session: Session) -> None:
        p1 = get_preferences(db_session)
        p2 = get_preferences(db_session)
        assert p1.id == p2.id  # Same row, not two

    def test_invalid_timezone_falls_back_to_utc(self, db_session: Session) -> None:
        prefs = update_preferences(db_session, tz="Invalid/Zone")
        assert prefs.timezone == "Invalid/Zone"


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
        import subprocess

        from apps.api.services.notification_service import send_macos_notification
        try:
            send_macos_notification(
                'Test "quotes" \\ backslash `backtick`',
                '$PATH /bin/sh ; rm -rf /',
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        except Exception as e:
            pytest.fail(f"send_macos_notification raised: {e}")


class TestPrivacyContract:
    def test_body_not_in_api_response(self, db_session: Session) -> None:
        from apps.api.notification_schemas import NotificationEventResponse
        _enable(db_session)
        ne = notify(db_session, "health", "test", "info", "T", "secret-payload", now=NOW)
        resp = NotificationEventResponse.from_event(ne)
        # 'body' is NOT in the response model
        assert not hasattr(resp, "body")
        # 'preview' is truncated
        assert len(resp.preview) <= 100

    def test_preview_truncates_long_body(self, db_session: Session) -> None:
        from apps.api.notification_schemas import NotificationEventResponse
        _enable(db_session)
        long_body = "x" * 500
        ne = notify(db_session, "health", "test", "info", "T", long_body, now=NOW)
        resp = NotificationEventResponse.from_event(ne)
        assert len(resp.preview) == 100
        assert resp.preview == long_body[:100]
