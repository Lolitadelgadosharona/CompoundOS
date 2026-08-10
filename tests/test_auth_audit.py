"""Tests for Sprint 010 Slice D — Auth, Audit & Escalation."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0025_auth_and_audit"


class TestMigration:
    def test_owner_api_keys_table(self, db_session):
        db_session.execute(text("SELECT 1 FROM owner_api_keys LIMIT 0"))

    def test_audit_log_table(self, db_session):
        db_session.execute(text("SELECT 1 FROM audit_log LIMIT 0"))

    def test_escalation_rules_table(self, db_session):
        db_session.execute(
            text("SELECT 1 FROM notification_escalation_rules LIMIT 0"),
        )

    def test_audit_log_immutability(self, db_session):
        """INSERT works, UPDATE and DELETE are rejected."""
        from datetime import datetime, timezone
        kid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO audit_log"
                " (id, event_type, action, outcome, occurred_at)"
                " VALUES (:id, 'system.action', 'test', 'success', :now)"
            ),
            {"id": kid, "now": datetime.now(timezone.utc)},
        )
        db_session.commit()

        # UPDATE must fail
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text("UPDATE audit_log SET action = 'hacked' WHERE id = :id"),
                {"id": kid},
            )
            db_session.commit()
        db_session.rollback()

        # DELETE must fail
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text("DELETE FROM audit_log WHERE id = :id"),
                {"id": kid},
            )
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


class TestNotificationEscalation:
    def test_escalation_rule_check_severity(self, db_session):
        """Invalid severity rejected by CHECK."""
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO notification_escalation_rules"
                    " (id, source, event_severity, escalate_after_hours,"
                    " escalation_level, enabled)"
                    " VALUES (:id, 'guardian', 'FATAL', 1, 1, TRUE)"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_escalation_rule_valid_severity(self, db_session):
        """Valid severities accepted."""
        for sev in ["critical", "warning", "info"]:
            db_session.execute(
                text(
                    "INSERT INTO notification_escalation_rules"
                    " (id, source, event_severity, escalate_after_hours,"
                    " escalation_level, enabled)"
                    " VALUES (:id, 'guardian', :sev, 1, 1, TRUE)"
                ),
                {"id": uuid4(), "sev": sev},
            )
            db_session.commit()
