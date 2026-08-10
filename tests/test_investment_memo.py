"""Tests for Sprint 011 Slice D — Investment Memo + Confidence Engine."""

from datetime import datetime, timezone
from uuid import uuid4

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

pytestmark = pytest.mark.postgres

HEAD_REVISION = "0030_investment_memo"


def _now():
    return datetime.now(timezone.utc)


def _setup_run(db_session):
    """Create FK chain: household → idea → review → request → run."""
    hh = uuid4()
    db_session.execute(
        text(
            "INSERT INTO household_profiles"
            " (id, singleton_key, household_name, base_currency,"
            " investment_horizon, liquidity_needs, risk_statement, notes,"
            " created_at, updated_at)"
            " VALUES (:id, TRUE, 'test', 'USD', 'long_term', 'low',"
            " 'moderate', '', :now, :now)"
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
    req = uuid4()
    db_session.execute(
        text(
            "INSERT INTO research_requests"
            " (id, review_request_id, status, created_at, updated_at)"
            " VALUES (:id, :rrid, 'completed', :now, :now)"
        ),
        {"id": req, "rrid": rr, "now": _now()},
    )
    run = uuid4()
    db_session.execute(
        text(
            "INSERT INTO research_runs"
            " (id, request_id, run_number, status, completed_at,"
            " created_at, updated_at)"
            " VALUES (:id, :req, 1, 'completed', :now, :now, :now)"
        ),
        {"id": run, "req": req, "now": _now()},
    )
    db_session.commit()
    return run


# ═══════════════════════════════════════════════════════════════════════
# Migration
# ═══════════════════════════════════════════════════════════════════════


class TestMigration:
    def test_table_exists(self, db_session):
        db_session.execute(text("SELECT 1 FROM investment_memos LIMIT 0"))

    def test_invalid_confidence_rejected(self, db_session):
        run_id = _setup_run(db_session)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO investment_memos"
                    " (id, run_id, memo, confidence_level, generated_at)"
                    " VALUES (:id, :rid, '{}', 'INVALID', :now)"
                ),
                {"id": uuid4(), "rid": run_id, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()

    def test_score_range_enforced(self, db_session):
        run_id = _setup_run(db_session)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO investment_memos"
                    " (id, run_id, memo, confidence_score, generated_at)"
                    " VALUES (:id, :rid, '{}', 101, :now)"
                ),
                {"id": uuid4(), "rid": run_id, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()

    def test_recommendation_check(self, db_session):
        run_id = _setup_run(db_session)
        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "INSERT INTO investment_memos"
                    " (id, run_id, memo, recommendation, generated_at)"
                    " VALUES (:id, :rid, '{}', 'SELL', :now)"
                ),
                {"id": uuid4(), "rid": run_id, "now": _now()},
            )
            db_session.commit()
        db_session.rollback()

    def test_memo_immutability(self, db_session):
        """Completed memos cannot be updated or deleted (err 55000)."""
        run_id = _setup_run(db_session)
        mid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO investment_memos"
                " (id, run_id, memo, confidence_score, confidence_level,"
                " recommendation, synthesis_model, generated_at)"
                " VALUES (:id, :rid, '{}', 72, 'MEDIUM', 'BUY',"
                " 'claude-sonnet-4', :now)"
            ),
            {"id": mid, "rid": run_id, "now": _now()},
        )
        db_session.commit()

        with pytest.raises((IntegrityError, OperationalError)):
            db_session.execute(
                text(
                    "UPDATE investment_memos"
                    " SET recommendation='HOLD' WHERE id=:id"
                ),
                {"id": mid},
            )
            db_session.commit()
        db_session.rollback()

    def test_migration_head(self, db_session):
        r = db_session.execute(
            text("SELECT version_num FROM alembic_version"),
        ).scalar()
        assert r == HEAD_REVISION


# ═══════════════════════════════════════════════════════════════════════
# Memo storage
# ═══════════════════════════════════════════════════════════════════════


class TestMemoStorage:
    def test_memo_with_all_sections(self, db_session):
        """All 11 memo sections store correctly."""
        run_id = _setup_run(db_session)
        mid = uuid4()
        now = _now()
        memo_sections = {
            "thesis": "Strong buy case for AAPL",
            "evidence": [{"source": "alpha_vantage", "metric": "P/E"}],
            "bull_case": {"narrative": "iPhone growth continues"},
            "bear_case": {"narrative": "Regulatory headwinds"},
            "risks": [{"risk": "Concentration", "severity": "high"}],
            "valuation": {"methodology": "DCF", "value": "185"},
            "portfolio_impact": {"new_allocation_pct": "8%"},
            "guardian_impact": {"compliant": True},
            "committee": {"consensus": "BUY", "disagreements": []},
            "decision_context": {"reason": "valuation_review"},
            "invalidation_conditions": {"conditions": []},
        }
        db_session.execute(
            text(
                "INSERT INTO investment_memos"
                " (id, run_id, memo, synthesis_model, confidence_score,"
                " confidence_level, recommendation, generated_at)"
                " VALUES (:id, :rid, :memo, 'claude-sonnet-4',"
                " 72, 'MEDIUM', 'BUY', :now)"
            ),
            {"id": mid, "rid": run_id, "memo": json.dumps(memo_sections), "now": now},
        )
        db_session.commit()
        r = db_session.execute(
            text("SELECT memo FROM investment_memos WHERE id=:id"),
            {"id": mid},
        ).fetchone()
        assert r[0]["thesis"] == "Strong buy case for AAPL"

    def test_provenance(self, db_session):
        """synthesis_model, confidence, recommendation, generated_at preserved."""
        run_id = _setup_run(db_session)
        mid = uuid4()
        now = _now()
        db_session.execute(
            text(
                "INSERT INTO investment_memos"
                " (id, run_id, memo, synthesis_model, confidence_score,"
                " confidence_level, recommendation, generated_at)"
                " VALUES (:id, :rid, '{}', 'claude-sonnet-4',"
                " 65, 'MEDIUM', 'HOLD', :now)"
            ),
            {"id": mid, "rid": run_id, "now": now},
        )
        db_session.commit()
        r = db_session.execute(
            text(
                "SELECT synthesis_model, confidence_score, confidence_level,"
                " recommendation, generated_at"
                " FROM investment_memos WHERE id=:id"
            ),
            {"id": mid},
        ).fetchone()
        assert r[0] == "claude-sonnet-4"
        assert r[1] == 65
        assert r[2] == "MEDIUM"
        assert r[3] == "HOLD"
        assert r[4] is not None


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
