"""Tests for Sprint 011 Slice A — Research Foundation."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0027_evidence_knowledge"


def _now():
    return datetime.now(timezone.utc)


def _create_review_request(db_session):
    """Create the minimum FK chain for a research_request.

    research_requests → committee_review_requests → investment_ideas → household_profiles
    """
    hh = uuid4()
    db_session.execute(
        text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes,"
            " created_at, updated_at)"
            " VALUES (:id, TRUE, 'test-hh', 'USD', 'long_term',"
            " 'low', 'moderate', '', :now, :now)"
        ),
        {"id": hh, "now": _now()},
    )
    idea = uuid4()
    db_session.execute(
        text(
            "INSERT INTO investment_ideas"
            " (id, household_id, title, status, source, confidence,"
            " created_at)"
            " VALUES (:id, :hh, 'Test Idea', 'draft', 'owner', 'LOW',"
            " :now)" 
        ),
        {"id": idea, "hh": hh, "now": _now()},
    )
    rr = uuid4()
    db_session.execute(
        text(
            "INSERT INTO committee_review_requests"
            " (id, investment_idea_id, status, requested_by, created_at)"
            " VALUES (:id, :iid, 'pending', 'owner', :now)"
        ),
        {"id": rr, "iid": idea, "now": _now()},
    )
    db_session.commit()
    return rr


# ═══════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_tables_exist(self, db_session):
        for t in ["research_requests", "research_runs"]:
            db_session.execute(text(f"SELECT 1 FROM {t} LIMIT 0"))

    def test_status_check_enforced(self, db_session):
        rr = _create_review_request(db_session)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO research_requests"
                    " (id, review_request_id, status, created_at, updated_at)"
                    " VALUES (:id, :rrid, 'INVALID', :now, :now)"
                ),
                {"id": uuid4(), "rrid": rr, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()

    def test_run_immutability_triggers(self, db_session):
        rr = _create_review_request(db_session)
        req_id = uuid4()
        run_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'completed', :now, :now)"
            ),
            {"id": req_id, "rrid": rr, "now": _now()},
        )
        db_session.execute(
            text(
                "INSERT INTO research_runs"
                " (id, request_id, run_number, status, completed_at,"
                " created_at, updated_at)"
                " VALUES (:id, :req, 1, 'completed', :now, :now, :now)"
            ),
            {"id": run_id, "req": req_id, "now": _now()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "UPDATE research_runs SET status = 'modified'"
                    " WHERE id = :id"
                ),
                {"id": run_id},
            )
            db_session.commit()
        db_session.rollback()

    def test_run_delete_protection(self, db_session):
        """Completed research runs cannot be deleted (err 55000)."""
        rr = _create_review_request(db_session)
        req_id = uuid4()
        run_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'completed', :now, :now)"
            ),
            {"id": req_id, "rrid": rr, "now": _now()},
        )
        db_session.execute(
            text(
                "INSERT INTO research_runs"
                " (id, request_id, run_number, status, completed_at,"
                " created_at, updated_at)"
                " VALUES (:id, :req, 1, 'completed', :now, :now, :now)"
            ),
            {"id": run_id, "req": req_id, "now": _now()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text("DELETE FROM research_runs WHERE id = :id"),
                {"id": run_id},
            )
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


# ═══════════════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestLifecycle:
    def test_request_creation(self, db_session):
        rr = _create_review_request(db_session)
        req_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'pending', :now, :now)"
            ),
            {"id": req_id, "rrid": rr, "now": _now()},
        )
        db_session.commit()

    def test_run_creation(self, db_session):
        rr = _create_review_request(db_session)
        req_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'pending', :now, :now)"
            ),
            {"id": req_id, "rrid": rr, "now": _now()},
        )
        db_session.commit()

        db_session.execute(
            text(
                "INSERT INTO research_runs"
                " (id, request_id, run_number, status,"
                " created_at, updated_at)"
                " VALUES (:id, :req, 1, 'pending', :now, :now)"
            ),
            {"id": uuid4(), "req": req_id, "now": _now()},
        )
        db_session.commit()

    def test_run_number_unique(self, db_session):
        rr = _create_review_request(db_session)
        req_id = uuid4()
        db_session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'pending', :now, :now)"
            ),
            {"id": req_id, "rrid": rr, "now": _now()},
        )
        db_session.commit()

        db_session.execute(
            text(
                "INSERT INTO research_runs"
                " (id, request_id, run_number, status,"
                " created_at, updated_at)"
                " VALUES (:id, :req, 1, 'pending', :now, :now)"
            ),
            {"id": uuid4(), "req": req_id, "now": _now()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO research_runs"
                    " (id, request_id, run_number, status,"
                    " created_at, updated_at)"
                    " VALUES (:id, :req, 1, 'pending', :now, :now)"
                ),
                {"id": uuid4(), "req": req_id, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# AI authority
# ═══════════════════════════════════════════════════════════════════════


class TestAIAuthority:
    def test_no_ai_initiation_path(self):
        import inspect

        from apps.api.routers.research import router

        for route in router.routes:
            src = inspect.getsource(route.endpoint)
            assert "ai_key" not in src.lower()
            assert "ai_agent" not in src.lower()

    def test_provenance_on_request(self, db_session):
        rr = _create_review_request(db_session)
        req_id = uuid4()
        now = _now()
        db_session.execute(
            text(
                "INSERT INTO research_requests"
                " (id, review_request_id, status, created_at, updated_at)"
                " VALUES (:id, :rrid, 'pending', :now, :now)"
            ),
            {"id": req_id, "rrid": rr, "now": now},
        )
        db_session.commit()
        r = db_session.execute(
            text(
                "SELECT created_at, updated_at FROM research_requests"
                " WHERE id = :id"
            ),
            {"id": req_id},
        ).fetchone()
        assert r[0] is not None
        assert r[1] is not None
