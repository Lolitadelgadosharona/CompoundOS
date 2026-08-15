"""M5-007 tests — prompt governance, cost tracking, execution logging."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services.cost_tracker import CostTracker
from apps.api.services.llm_provider_runtime import (
    GovernedLLMExecutor,
    LLMResponse,
    ProviderRouter,
)
from apps.api.services.prompt_governor import PromptGovernor

pytestmark = pytest.mark.postgres


# ── Helpers ──────────────────────────────────────────────────────────────


def _setup_household(db_session):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement,"
        " notes, created_at, updated_at)"
        " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l', 'm', '', NOW(), NOW())"
        " ON CONFLICT (singleton_key) DO NOTHING"
    ), {"id": hh})
    db_session.commit()
    return db_session.execute(text(
        "SELECT id FROM household_profiles WHERE singleton_key = TRUE"
    )).fetchone()[0]


def _setup_run(db_session, household_id):
    idea_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title, status,"
        " source, confidence, created_at)"
        " VALUES (:id, :hh, 'AAPL', 'draft', 'owner', 'LOW', NOW())"
    ), {"id": idea_id, "hh": household_id})
    rr_id = uuid4()
    db_session.execute(text(
        "INSERT INTO committee_review_requests (id, investment_idea_id,"
        " status, requested_by, created_at)"
        " VALUES (:id, :iid, 'pending', 'owner', NOW())"
    ), {"id": rr_id, "iid": idea_id})
    req_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_requests (id, review_request_id, status,"
        " created_at, updated_at)"
        " VALUES (:id, :rrid, 'pending', NOW(), NOW())"
    ), {"id": req_id, "rrid": rr_id})
    run_id = uuid4()
    db_session.execute(text(
        "INSERT INTO research_runs (id, request_id, run_number, status,"
        " created_at, updated_at)"
        " VALUES (:id, :req, 1, 'pending', NOW(), NOW())"
    ), {"id": run_id, "req": req_id})
    db_session.commit()
    return idea_id, run_id


class _MockProvider:
    """Provider returning a valid, deterministic response."""

    def generate(self, model, system_prompt, user_prompt,
                 max_output_tokens=2000):
        return LLMResponse(
            content='{"perspective": "value", "thesis": "T",'
                    ' "conviction_score": 7}',
            model=model, provider="anthropic",
            input_tokens=100, output_tokens=50,
            duration_ms=100, finish_reason="stop",
        )


class _FailingCost:
    """Cost estimator that raises — to verify fail-open logging."""

    def estimate(self, model, input_tokens, output_tokens):
        raise RuntimeError("cost failure")


def _seed_and_approve(db_session):
    """Seed default prompts (draft) then Owner-approve all of them."""
    gov = PromptGovernor()
    gov.seed_defaults(db_session)
    db_session.commit()
    for p in gov.list_prompts(db_session):
        if p["status"] == "draft":
            gov.approve(db_session, UUID(p["id"]))
    db_session.commit()
    return gov


# ── PromptGovernor ───────────────────────────────────────────────────────


class TestPromptGovernor:
    def test_require_active_returns_prompt_after_approval(self, db_session):
        gov = _seed_and_approve(db_session)
        result = gov.require_active(db_session, "value")
        assert result.valid is True
        assert result.prompt_id is not None
        assert result.version == 1
        assert result.default_model == "claude-sonnet-4"

    def test_require_active_fails_closed_when_unseeded(self, db_session):
        gov = PromptGovernor()
        result = gov.require_active(db_session, "value")
        assert result.valid is False
        assert result.error and "No active prompt" in result.error

    def test_require_active_fails_closed_for_draft(self, db_session):
        # Seeded as draft but NOT approved → still no active prompt.
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        result = gov.require_active(db_session, "value")
        assert result.valid is False

    def test_seed_defaults_idempotent(self, db_session):
        gov = PromptGovernor()
        first = gov.seed_defaults(db_session)
        db_session.commit()
        second = gov.seed_defaults(db_session)
        assert first == 7
        assert second == 0

    def test_seed_defaults_as_draft(self, db_session):
        gov = PromptGovernor()
        gov.seed_defaults(db_session)
        db_session.commit()
        draft = db_session.execute(text(
            "SELECT COUNT(*) FROM prompt_templates WHERE status = 'draft'"
        )).scalar()
        active = db_session.execute(text(
            "SELECT COUNT(*) FROM prompt_templates WHERE status = 'active'"
        )).scalar()
        assert draft == 7
        assert active == 0


# ── CostTracker ──────────────────────────────────────────────────────────


class TestCostTracker:
    def test_estimate_known_model(self):
        tracker = CostTracker()
        # claude-sonnet-4: $0.003 in / $0.015 out per 1k tokens
        cost = tracker.estimate("claude-sonnet-4", 1000, 1000)
        assert cost == pytest.approx(0.018, abs=1e-6)

    def test_estimate_alias_resolved_model(self):
        tracker = CostTracker()
        cost = tracker.estimate("claude-sonnet-4.6", 1000, 1000)
        assert cost == pytest.approx(0.018, abs=1e-6)

    def test_estimate_unknown_model_uses_default(self):
        tracker = CostTracker()
        cost = tracker.estimate("unknown-model", 1000, 1000)
        assert cost == pytest.approx(0.020, abs=1e-6)

    def test_estimate_none_tokens_fails_open(self):
        tracker = CostTracker()
        assert tracker.estimate("gpt-4o", None, None) == 0.0


# ── GovernedLLMExecutor logging ──────────────────────────────────────────


class TestGovernedExecutorLogging:
    def _executor(self, db_session, cost=None):
        gov = _seed_and_approve(db_session)
        router = ProviderRouter({"anthropic": _MockProvider()})
        return GovernedLLMExecutor(
            router, prompt_governor=gov,
            cost_tracker=cost if cost is not None else CostTracker(),
        )

    def test_execution_is_logged(self, db_session):
        hh = _setup_household(db_session)
        _idea_id, run_id = _setup_run(db_session, hh)
        executor = self._executor(db_session)
        result = executor.execute(
            db_session, run_id, "value", "sys", "user",
            requested_model="claude-sonnet-4",
        )
        db_session.commit()
        assert result.log_id is not None
        row = db_session.execute(text(
            "SELECT prompt_template_id, cost_estimate, input_tokens,"
            " output_tokens, status FROM llm_execution_log"
            " WHERE run_id = :rid"
        ), {"rid": run_id}).fetchone()
        assert row is not None
        assert row[0] is not None            # prompt_template_id
        assert float(row[1]) > 0             # cost_estimate
        assert row[2] == 100 and row[3] == 50  # tokens
        assert row[4] == "success"

    def test_logging_failure_fails_open(self, db_session):
        hh = _setup_household(db_session)
        _idea_id, run_id = _setup_run(db_session, hh)
        executor = self._executor(db_session, cost=_FailingCost())
        result = executor.execute(
            db_session, run_id, "value", "sys", "user",
            requested_model="claude-sonnet-4",
        )
        # execution still succeeded; logging was skipped, not fatal
        assert result.validated["thesis"] == "T"
        assert result.log_id is None

    def test_prompt_governor_fails_closed(self, db_session):
        hh = _setup_household(db_session)
        _idea_id, run_id = _setup_run(db_session, hh)
        # No seeding → no active prompt → fail closed
        router = ProviderRouter({"anthropic": _MockProvider()})
        executor = GovernedLLMExecutor(
            router, prompt_governor=PromptGovernor(),
            cost_tracker=CostTracker(),
        )
        with pytest.raises(ValueError):
            executor.execute(db_session, run_id, "value", "sys", "user")
