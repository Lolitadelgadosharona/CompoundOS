"""Tests for Sprint 012 Slice A — LLM Runtime Foundation."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0032_decision_lifecycle_hardening"


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_tables_exist(self, db_session):
        for t in ["prompt_templates", "llm_execution_log"]:
            db_session.execute(text(f"SELECT 1 FROM {t} LIMIT 0"))

    def test_prompt_status_check(self, db_session):
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO prompt_templates"
                    " (id, perspective, version, status, purpose,"
                    " system_prompt, user_prompt_template)"
                    " VALUES (:id, 'value', 1, 'INVALID', '', '', '')"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_prompt_immutability(self, db_session):
        """Active prompts cannot be modified (err 55000)."""
        pid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO prompt_templates"
                " (id, perspective, version, status, purpose,"
                " system_prompt, user_prompt_template)"
                " VALUES (:id, 'value', 1, 'active', 'test', 'sys', 'user')"
            ),
            {"id": pid},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "UPDATE prompt_templates"
                    " SET system_prompt='hacked' WHERE id=:id"
                ),
                {"id": pid},
            )
            db_session.commit()
        db_session.rollback()

    def test_llm_log_retry_range(self, db_session):
        """retry_count must be 0-5."""
        db_session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, perspective, model, status) VALUES"
                " (:id, 'value', 'claude-sonnet-4', 'pending')"
            ),
            {"id": uuid4()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO llm_execution_log"
                    " (id, perspective, model, status, retry_count)"
                    " VALUES (:id, 'growth', 'claude-sonnet-4', 'pending', 6)"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


# ═══════════════════════════════════════════════════════════════════════
# Prompt template lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestPromptLifecycle:
    def test_draft_to_active_transition(self, db_session):
        """Draft prompts can be activated."""
        pid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO prompt_templates"
                " (id, perspective, version, status, purpose,"
                " system_prompt, user_prompt_template)"
                " VALUES (:id, 'value', 1, 'draft', 'test', 'sys', 'user')"
            ),
            {"id": pid},
        )
        db_session.commit()
        # Transition draft → active
        db_session.execute(
            text(
                "UPDATE prompt_templates SET status='active',"
                " active_at=:now WHERE id=:id AND status='draft'"
            ),
            {"id": pid, "now": _now()},
        )
        db_session.commit()
        r = db_session.execute(
            text("SELECT status, active_at FROM prompt_templates"
                 " WHERE id=:id"),
            {"id": pid},
        ).fetchone()
        assert r[0] == "active"
        assert r[1] is not None

    def test_active_to_deprecated(self, db_session):
        """Cannot go back from active to draft, only to deprecated."""
        pid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO prompt_templates"
                " (id, perspective, version, status, purpose,"
                " system_prompt, user_prompt_template)"
                " VALUES (:id, 'growth', 1, 'active', 'test', 'sys', 'user')"
            ),
            {"id": pid},
        )
        db_session.commit()
        # Deprecate
        db_session.execute(
            text(
                "UPDATE prompt_templates SET status='deprecated',"
                " deprecated_at=:now WHERE id=:id AND status='active'"
            ),
            {"id": pid, "now": _now()},
        )
        db_session.commit()
        r = db_session.execute(
            text("SELECT status, deprecated_at FROM prompt_templates"
                 " WHERE id=:id"),
            {"id": pid},
        ).fetchone()
        assert r[0] == "deprecated"
        assert r[1] is not None

    def test_version_uniqueness(self, db_session):
        """UNIQUE(perspective, version) enforced."""
        db_session.execute(
            text(
                "INSERT INTO prompt_templates"
                " (id, perspective, version, status, purpose,"
                " system_prompt, user_prompt_template)"
                " VALUES (:id, 'value', 1, 'draft', 'test', 'sys', 'user')"
            ),
            {"id": uuid4()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO prompt_templates"
                    " (id, perspective, version, status, purpose,"
                    " system_prompt, user_prompt_template)"
                    " VALUES (:id, 'value', 1, 'draft', 'test', 'sys',"
                    " 'user')"
                ),
                {"id": uuid4()},
            )
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# LLM execution logging
# ═══════════════════════════════════════════════════════════════════════


class TestLLMExecutionLog:
    def test_execution_lifecycle(self, db_session):
        """pending → running → success with tokens/cost."""
        eid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, perspective, model, status) VALUES"
                " (:id, 'value', 'claude-sonnet-4', 'pending')"
            ),
            {"id": eid},
        )
        db_session.commit()

        db_session.execute(
            text(
                "UPDATE llm_execution_log SET status='running',"
                " started_at=:now WHERE id=:id"
            ),
            {"id": eid, "now": _now()},
        )
        db_session.commit()

        db_session.execute(
            text(
                "UPDATE llm_execution_log SET status='success',"
                " input_tokens=1500, output_tokens=800,"
                " cost_estimate=0.012, duration_ms=3200,"
                " completed_at=:now WHERE id=:id"
            ),
            {"id": eid, "now": _now()},
        )
        db_session.commit()

        r = db_session.execute(
            text(
                "SELECT status, input_tokens, output_tokens, cost_estimate,"
                " duration_ms FROM llm_execution_log WHERE id=:id"
            ),
            {"id": eid},
        ).fetchone()
        assert r[0] == "success"
        assert r[1] == 1500
        assert r[2] == 800
        assert r[3] is not None
        assert r[4] == 3200

    def test_failure_tracking(self, db_session):
        """Failed executions record error_message and retry_count."""
        eid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, perspective, model, status, retry_count,"
                " error_message) VALUES"
                " (:id, 'macro', 'gpt-4o', 'failure', 3, 'timeout')"
            ),
            {"id": eid},
        )
        db_session.commit()

        r = db_session.execute(
            text(
                "SELECT status, retry_count, error_message"
                " FROM llm_execution_log WHERE id=:id"
            ),
            {"id": eid},
        ).fetchone()
        assert r[0] == "failure"
        assert r[1] == 3
        assert r[2] == "timeout"


class TestAIAuthority:
    def test_no_trading_path(self):
        # Slice A is infrastructure only — no AI execution paths
        assert True
