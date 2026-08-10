"""Tests for Sprint 011 Slice C — Multi-Perspective Reasoning Engine."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0030_investment_memo"


def _now():
    return datetime.now(timezone.utc)


def _setup_run(db_session):
    """Create FK chain: household → idea → review_request → request → run."""
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
            " VALUES (:id, :hh, 'Test', 'draft', 'owner', 'LOW', :now)"
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
    req_id = uuid4()
    db_session.execute(
        text(
            "INSERT INTO research_requests"
            " (id, review_request_id, status, created_at, updated_at)"
            " VALUES (:id, :rrid, 'completed', :now, :now)"
        ),
        {"id": req_id, "rrid": rr, "now": _now()},
    )
    run_id = uuid4()
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
    return run_id


# ═══════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_table_exists(self, db_session):
        db_session.execute(
            text("SELECT 1 FROM perspective_analyses LIMIT 0"))

    def test_perspective_check_enforced(self, db_session):
        run_id = _setup_run(db_session)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO perspective_analyses"
                    " (id, run_id, perspective, analysis, completed_at)"
                    " VALUES (:id, :rid, 'INVALID', '{}', :now)"
                ),
                {"id": uuid4(), "rid": run_id, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()

    def test_immutability_triggers(self, db_session):
        """Completed analyses cannot be updated or deleted (err 55000)."""
        run_id = _setup_run(db_session)
        pid = uuid4()
        now = _now()
        db_session.execute(
            text(
                "INSERT INTO perspective_analyses"
                " (id, run_id, perspective, analysis, completed_at)"
                " VALUES (:id, :rid, 'value', '{}', :now)"
            ),
            {"id": pid, "rid": run_id, "now": now},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "UPDATE perspective_analyses"
                    " SET analysis = :hack WHERE id = :id"
                ),
                {"id": pid, "hack": '{"hacked":true}'},
            )
            db_session.commit()
        db_session.rollback()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text("DELETE FROM perspective_analyses WHERE id = :id"),
                {"id": pid},
            )
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


# ═══════════════════════════════════════════════════════════════════════
# Perspective storage
# ═══════════════════════════════════════════════════════════════════════


class TestPerspectiveStorage:
    PERSPECTIVES = ["value", "growth", "risk", "macro", "policy",
                    "portfolio_fit"]

    def test_all_perspectives_accepted(self, db_session):
        run_id = _setup_run(db_session)
        for p in self.PERSPECTIVES:
            db_session.execute(
                text(
                    "INSERT INTO perspective_analyses"
                    " (id, run_id, perspective, analysis, model,"
                    " prompt_version, conviction_score, completed_at)"
                    " VALUES (:id, :rid, :p, '{}', 'claude-sonnet-4',"
                    " 1, 7, :now)"
                ),
                {"id": uuid4(), "rid": run_id, "p": p, "now": _now()},
            )
            db_session.commit()

    def test_provenance_fields(self, db_session):
        """model, prompt_version, started_at, completed_at preserved."""
        run_id = _setup_run(db_session)
        pid = uuid4()
        now = _now()
        db_session.execute(
            text(
                "INSERT INTO perspective_analyses"
                " (id, run_id, perspective, analysis, model,"
                " prompt_version, conviction_score, started_at,"
                " completed_at)"
                " VALUES (:id, :rid, 'value', '{}', 'claude-sonnet-4',"
                " 2, 8, :start, :comp)"
            ),
            {"id": pid, "rid": run_id, "start": now, "comp": now},
        )
        db_session.commit()
        r = db_session.execute(
            text(
                "SELECT model, prompt_version, conviction_score,"
                " started_at, completed_at"
                " FROM perspective_analyses WHERE id = :id"
            ),
            {"id": pid},
        ).fetchone()
        assert r[0] == "claude-sonnet-4"
        assert r[1] == 2
        assert r[2] == 8
        assert r[3] is not None
        assert r[4] is not None

    def test_conviction_score_range(self, db_session):
        """conviction_score must be 1-10 or NULL."""
        run_id = _setup_run(db_session)
        db_session.execute(
            text(
                "INSERT INTO perspective_analyses"
                " (id, run_id, perspective, analysis, conviction_score,"
                " completed_at)"
                " VALUES (:id, :rid, 'value', '{}', NULL, :now)"
            ),
            {"id": uuid4(), "rid": run_id, "now": _now()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO perspective_analyses"
                    " (id, run_id, perspective, analysis, conviction_score,"
                    " completed_at)"
                    " VALUES (:id, :rid, 'growth', '{}', 11, :now)"
                ),
                {"id": uuid4(), "rid": run_id, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()


# ═══════════════════════════════════════════════════════════════════════
# AI authority
# ═══════════════════════════════════════════════════════════════════════


class TestAIAuthority:
    def test_no_trading_path(self):
        import inspect

        from apps.api.routers.research import router

        for route in router.routes:
            src = inspect.getsource(route.endpoint)
            forbidden = ["trade", "broker", "rebalance",
                         "approve_investment", "order_placed"]
            for word in forbidden:
                assert word not in src.lower()
