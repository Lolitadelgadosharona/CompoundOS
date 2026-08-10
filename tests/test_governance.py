"""Tests for Sprint 012 Slice D — AI Governance Layer."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from apps.api.services.governance import (
    ActionMatrix,
    CostTracker,
    PermissionGate,
    PromptGovernor,
)

pytestmark = pytest.mark.postgres


def _now():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
# ActionMatrix — single source of truth
# ═══════════════════════════════════════════════════════════════════════


class TestActionMatrix:
    def test_auto_actions_exist(self):
        actions = ActionMatrix.all_auto()
        names = {a.name for a in actions}
        assert "execute_llm_call" in names
        assert "generate_memo" in names
        assert "fetch_market_data" in names
        assert len(actions) == 8

    def test_owner_actions_exist(self):
        actions = ActionMatrix.all_owner()
        names = {a.name for a in actions}
        assert "create_idea" in names
        assert "request_review" in names
        assert "approve_investment" in names
        assert "start_research" in names
        assert len(actions) == 4

    def test_never_actions_exist(self):
        actions = ActionMatrix.all_never()
        names = {a.name for a in actions}
        assert "execute_trade" in names
        assert "connect_broker" in names
        assert "modify_policy" in names
        assert len(actions) == 3

    def test_total_actions(self):
        total = (len(ActionMatrix.all_auto())
                 + len(ActionMatrix.all_owner())
                 + len(ActionMatrix.all_never()))
        assert total == 15

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError):
            ActionMatrix.get("nonexistent_action")


# ═══════════════════════════════════════════════════════════════════════
# PermissionGate
# ═══════════════════════════════════════════════════════════════════════


class TestPermissionGate:
    def test_auto_action_allowed_for_ai(self):
        result = PermissionGate.check("execute_llm_call", caller="ai")
        assert result.allowed

    def test_auto_action_allowed_for_owner(self):
        result = PermissionGate.check("execute_llm_call", caller="owner")
        assert result.allowed

    def test_owner_action_rejected_for_ai(self):
        result = PermissionGate.check("approve_investment", caller="ai")
        assert not result.allowed
        assert "Owner" in result.reason

    def test_owner_action_allowed_for_owner(self):
        result = PermissionGate.check("approve_investment", caller="owner")
        assert result.allowed

    def test_never_action_rejected_for_anyone(self):
        for caller in ["ai", "owner"]:
            result = PermissionGate.check("execute_trade", caller=caller)
            assert not result.allowed
            assert "NEVER" in result.reason

    def test_never_action_consistently_blocked(self):
        for action_name in ("execute_trade", "connect_broker",
                            "modify_policy"):
            result = PermissionGate.check(action_name)
            assert not result.allowed

    def test_unknown_action_rejected(self):
        result = PermissionGate.check("some_unknown_action")
        assert not result.allowed

    def test_action_matrix_includes_all(self):
        for action in ActionMatrix._ALL.values():
            result = PermissionGate.check(action.name)
            assert result.action is not None
            assert result.action.name == action.name


# ═══════════════════════════════════════════════════════════════════════
# PromptGovernor
# ═══════════════════════════════════════════════════════════════════════


class TestPromptGovernor:
    def test_requires_active_prompt(self, db_session):
        pid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO prompt_templates"
                " (id, perspective, version, status, purpose,"
                " system_prompt, user_prompt_template, default_model)"
                " VALUES (:id, 'value', 1, 'active', 'test', 'sys',"
                " 'user', 'claude-sonnet-4')"
            ),
            {"id": pid},
        )
        db_session.commit()
        result = PromptGovernor.require_active(db_session, "value")
        assert result.valid
        assert result.prompt_version == 1
        assert result.default_model == "claude-sonnet-4"

    def test_rejects_missing_prompt(self, db_session):
        result = PromptGovernor.require_active(db_session, "nonexistent")
        assert not result.valid
        assert "No active prompt" in result.error

    def test_rejects_deprecated_prompt(self, db_session):
        pid = uuid4()
        db_session.execute(
            text(
                "INSERT INTO prompt_templates"
                " (id, perspective, version, status, purpose,"
                " system_prompt, user_prompt_template)"
                " VALUES (:id, 'growth', 1, 'deprecated', 'test',"
                " 'sys', 'user')"
            ),
            {"id": pid},
        )
        db_session.commit()
        result = PromptGovernor.require_active(db_session, "growth")
        assert not result.valid


# ═══════════════════════════════════════════════════════════════════════
# CostTracker
# ═══════════════════════════════════════════════════════════════════════


class TestCostTracker:
    def test_estimate_claude(self):
        cost = CostTracker.estimate("anthropic/claude-sonnet-4", 1500, 800)
        # input: 1.5 × $0.003 = $0.0045
        # output: 0.8 × $0.015 = $0.012
        # total: ~$0.0165
        assert 0.01 <= cost <= 0.02

    def test_estimate_gpt4o(self):
        cost = CostTracker.estimate("openai/gpt-4o", 2000, 1000)
        # input: 2.0 × $0.0025 = $0.005
        # output: 1.0 × $0.010 = $0.010
        # total: $0.015
        assert 0.01 <= cost <= 0.02

    def test_estimate_unknown_model_defaults(self):
        cost = CostTracker.estimate("unknown-model", 1000, 500)
        assert cost > 0

    def test_log_execution_writes(self, db_session):
        # Create research run FK
        run_id = uuid4()
        req_id = uuid4()
        rr_id = uuid4()
        hh = uuid4()
        db_session.execute(text(
            "INSERT INTO household_profiles (id, singleton_key, household_name,"
            " base_currency, investment_horizon, liquidity_needs,"
            " risk_statement, notes, created_at, updated_at)"
            " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l', 'm', '', NOW(), NOW())"
        ), {"id": hh})
        idea = uuid4()
        db_session.execute(text(
            "INSERT INTO investment_ideas (id, household_id, title, status,"
            " source, confidence, created_at)"
            " VALUES (:id, :hh, 't', 'draft', 'owner', 'LOW', NOW())"
        ), {"id": idea, "hh": hh})
        db_session.execute(text(
            "INSERT INTO committee_review_requests (id, investment_idea_id,"
            " status, requested_by, created_at)"
            " VALUES (:id, :iid, 'pending', 'owner', NOW())"
        ), {"id": rr_id, "iid": idea})
        db_session.execute(text(
            "INSERT INTO research_requests (id, review_request_id, status,"
            " created_at, updated_at)"
            " VALUES (:id, :rrid, 'completed', NOW(), NOW())"
        ), {"id": req_id, "rrid": rr_id})
        db_session.execute(text(
            "INSERT INTO research_runs (id, request_id, run_number, status,"
            " created_at, updated_at)"
            " VALUES (:id, :req, 1, 'completed', NOW(), NOW())"
        ), {"id": run_id, "req": req_id})
        db_session.commit()
        ptid = uuid4()
        db_session.execute(text(
            "INSERT INTO prompt_templates (id, perspective, version, status,"
            " purpose, system_prompt, user_prompt_template)"
            " VALUES (:id, 'value', 1, 'active', '', '', '')"
        ), {"id": ptid})
        db_session.commit()
        eid = CostTracker.log_execution(
            db_session, run_id, "value", "claude-sonnet-4",
            ptid, 1500, 800, "success", 2500,
        )
        db_session.commit()
        row = db_session.execute(
            text(
                "SELECT cost_estimate, cost_currency, input_tokens,"
                " output_tokens, status FROM llm_execution_log"
                " WHERE id = :id"
            ),
            {"id": eid},
        ).fetchone()
        assert row is not None
        assert row[0] > 0
        assert row[1] == "USD"
        assert row[2] == 1500
        assert row[3] == 800
        assert row[4] == "success"


class TestAIAuthority:
    def test_no_trading_path(self):
        # PermissionGate enforces: trade/broker are NEVER actions
        for action in ActionMatrix.all_never():
            result = PermissionGate.check(action.name)
            assert not result.allowed
