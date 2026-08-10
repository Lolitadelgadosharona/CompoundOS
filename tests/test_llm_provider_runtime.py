"""Tests for Sprint 013 Slice A — Real LLM Provider Runtime (Hardened).

All tests use mock providers. No real API calls. No API keys required.
No dependency on sprint-012-slice-d governance module (not yet merged).
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services.llm_provider_runtime import (
    AnthropicAdapter,
    ConfigurationError,
    ExecutionResult,
    GeminiAdapter,
    GovernedLLMExecutor,
    LLMResponse,
    OpenAIAdapter,
    ProviderRouter,
    ResponseValidator,
)

pytestmark = pytest.mark.postgres


# ═══════════════════════════════════════════════════════════════════════
# Inline mock governance
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MockPermissionResult:
    allowed: bool
    reason: str = ""


class MockPermissionGate:
    @staticmethod
    def check(action_name: str, caller: str = "ai") -> MockPermissionResult:
        never = {"execute_trade", "connect_broker", "modify_policy"}
        if action_name in never:
            return MockPermissionResult(allowed=False, reason="NEVER")
        owner = {"approve_investment", "create_idea", "request_review",
                 "start_research"}
        if action_name in owner and caller != "owner":
            return MockPermissionResult(allowed=False, reason="Owner")
        return MockPermissionResult(allowed=True)


@dataclass
class MockPromptValidation:
    valid: bool
    prompt_id: Optional[UUID] = None
    prompt_version: int = 1
    default_model: Optional[str] = None
    error: Optional[str] = None


class MockPromptGovernor:
    @staticmethod
    def require_active(session, perspective: str) -> MockPromptValidation:
        row = session.execute(
            text(
                "SELECT id, version, default_model FROM prompt_templates"
                " WHERE perspective = :p AND status = 'active'"
            ),
            {"p": perspective},
        ).fetchone()
        if row is None:
            return MockPromptValidation(
                valid=False,
                error=f"No active prompt for '{perspective}'",
            )
        return MockPromptValidation(
            valid=True, prompt_id=row[0],
            prompt_version=row[1] or 1,
            default_model=row[2],
        )


class MockCostTracker:
    @staticmethod
    def log_execution(session, run_id, perspective, model,
                      prompt_template_id, input_tokens, output_tokens,
                      status, duration_ms, retry_count=0, error=None):
        eid = uuid4()
        now = datetime.now(timezone.utc)
        cost = 0.01
        session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, run_id, prompt_template_id, perspective, model,"
                " input_tokens, output_tokens, cost_estimate,"
                " cost_currency, retry_count, status, duration_ms,"
                " error_message, started_at, completed_at)"
                " VALUES (:id, :rid, :ptid, :p, :m, :it, :ot, :cost,"
                " 'USD', :rc, :st, :dur, :err, :now, :now)"
            ),
            {"id": eid, "rid": run_id, "ptid": prompt_template_id,
             "p": perspective, "m": model, "it": input_tokens,
             "ot": output_tokens, "cost": cost, "rc": retry_count,
             "st": status, "dur": duration_ms, "err": error, "now": now},
        )


# ═══════════════════════════════════════════════════════════════════════
# Mock providers
# ═══════════════════════════════════════════════════════════════════════


class MockAnthropicProvider:
    def generate(self, model="claude-sonnet-4", system_prompt="",
                 user_prompt="", max_output_tokens=2000, **kwargs):
        return LLMResponse(
            content=json.dumps({
                "perspective": "value",
                "thesis": "Mock Claude analysis",
                "conviction_score": 7,
            }),
            model=model, provider="anthropic",
            input_tokens=500, output_tokens=300,
            duration_ms=150, finish_reason="stop",
        )


class MockOpenAIProvider:
    def generate(self, model="gpt-4o", system_prompt="",
                 user_prompt="", max_output_tokens=2000, **kwargs):
        return LLMResponse(
            content=json.dumps({
                "perspective": "macro",
                "thesis": "Mock GPT-4o analysis",
                "conviction_score": 6,
            }),
            model=model, provider="openai",
            input_tokens=600, output_tokens=400,
            duration_ms=200, finish_reason="stop",
        )


class MockGeminiProvider:
    def generate(self, model="gemini-2.5-pro", system_prompt="",
                 user_prompt="", max_output_tokens=2000, **kwargs):
        return LLMResponse(
            content=json.dumps({"thesis": "Synthesis memo"}),
            model=model, provider="google",
            input_tokens=2000, output_tokens=800,
            duration_ms=300, finish_reason="stop",
        )


class FailingProvider:
    def generate(self, model="", system_prompt="", user_prompt="",
                 max_output_tokens=2000, **kwargs):
        raise ConnectionError("Simulated provider failure")


class AuthFailingProvider:
    def generate(self, model="", system_prompt="", user_prompt="",
                 max_output_tokens=2000, **kwargs):
        raise PermissionError("401 Unauthorized")


class BadJSONProvider:
    def generate(self, model="", system_prompt="", user_prompt="",
                 max_output_tokens=2000, **kwargs):
        return LLMResponse(
            content="not valid json {{{",
            model=model, provider="mock",
            input_tokens=100, output_tokens=50,
            duration_ms=10, finish_reason="stop",
        )


class MissingFieldsProvider:
    def generate(self, model="", system_prompt="", user_prompt="",
                 max_output_tokens=2000, **kwargs):
        return LLMResponse(
            content=json.dumps({"perspective": "value"}),  # no thesis, no conviction
            model=model, provider="mock",
            input_tokens=100, output_tokens=50,
            duration_ms=10, finish_reason="stop",
        )


class BadConvictionProvider:
    def generate(self, model="", system_prompt="", user_prompt="",
                 max_output_tokens=2000, **kwargs):
        return LLMResponse(
            content=json.dumps({
                "perspective": "value", "thesis": "ok",
                "conviction_score": 99,
            }),
            model=model, provider="mock",
            input_tokens=100, output_tokens=50,
            duration_ms=10, finish_reason="stop",
        )


def _setup_prompt(db_session, perspective="value"):
    pid = uuid4()
    db_session.execute(
        text(
            "INSERT INTO prompt_templates"
            " (id, perspective, version, status, purpose,"
            " system_prompt, user_prompt_template, default_model)"
            " VALUES (:id, :p, 1, 'active', 'test', 'sys', 'user',"
            " 'claude-sonnet-4')"
        ),
        {"id": pid, "p": perspective},
    )
    db_session.commit()
    return pid


def _setup_run(db_session, run_id):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key,"
        " household_name, base_currency, investment_horizon,"
        " liquidity_needs, risk_statement, notes, created_at, updated_at)"
        " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l','m','',NOW(),NOW())"
    ), {"id": hh})
    idea = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_ideas (id, household_id, title,"
        " status, source, confidence, created_at)"
        " VALUES (:id, :hh, 't', 'draft', 'owner', 'LOW', NOW())"
    ), {"id": idea, "hh": hh})
    rr = uuid4()
    db_session.execute(text(
        "INSERT INTO committee_review_requests (id,"
        " investment_idea_id, status, requested_by, created_at)"
        " VALUES (:id, :iid, 'pending', 'owner', NOW())"
    ), {"id": rr, "iid": idea})
    req = uuid4()
    db_session.execute(text(
        "INSERT INTO research_requests (id, review_request_id,"
        " status, created_at, updated_at)"
        " VALUES (:id, :rrid, 'pending', NOW(), NOW())"
    ), {"id": req, "rrid": rr})
    db_session.execute(text(
        "INSERT INTO research_runs (id, request_id, run_number,"
        " status, created_at, updated_at)"
        " VALUES (:id, :req, 1, 'analyzing', NOW(), NOW())"
    ), {"id": run_id, "req": req})
    db_session.commit()


# ═══════════════════════════════════════════════════════════════════════
# ResponseValidator
# ═══════════════════════════════════════════════════════════════════════


class TestResponseValidator:
    def test_valid_response_accepted(self):
        content = json.dumps({
            "perspective": "value", "thesis": "Test",
            "conviction_score": 7,
        })
        result = ResponseValidator.validate(content, "value")
        assert result.valid
        assert result.parsed["conviction_score"] == 7

    def test_invalid_json_rejected(self):
        result = ResponseValidator.validate("not json", "value")
        assert not result.valid
        assert "JSON" in result.error

    def test_missing_fields_rejected(self):
        result = ResponseValidator.validate(
            json.dumps({"perspective": "value"}), "value",
        )
        assert not result.valid
        assert "thesis" in result.error

    def test_conviction_score_out_of_range(self):
        result = ResponseValidator.validate(
            json.dumps({
                "perspective": "value", "thesis": "x",
                "conviction_score": 15,
            }),
            "value",
        )
        assert not result.valid
        assert "range" in result.error

    def test_conviction_score_non_numeric(self):
        result = ResponseValidator.validate(
            json.dumps({
                "perspective": "value", "thesis": "x",
                "conviction_score": "high",
            }),
            "value",
        )
        assert not result.valid

    def test_non_dict_rejected(self):
        result = ResponseValidator.validate("[1,2,3]", "value")
        assert not result.valid

    def test_synthesis_allows_fewer_fields(self):
        content = json.dumps({"thesis": "Synthesized"})
        result = ResponseValidator.validate(content, "synthesis")
        assert result.valid


# ═══════════════════════════════════════════════════════════════════════
# ProviderRouter
# ═══════════════════════════════════════════════════════════════════════


class TestProviderRouter:
    def test_routes_value_to_claude(self):
        providers = {"anthropic": MockAnthropicProvider(),
                     "openai": MockOpenAIProvider()}
        router = ProviderRouter(providers)
        provider, model = router.route("value", "claude-sonnet-4")
        assert isinstance(provider, MockAnthropicProvider)

    def test_routes_macro_to_openai(self):
        providers = {"anthropic": MockAnthropicProvider(),
                     "openai": MockOpenAIProvider()}
        router = ProviderRouter(providers)
        provider, _ = router.route("macro", "gpt-4o")
        assert isinstance(provider, MockOpenAIProvider)

    def test_fallback_returns_alternate(self):
        providers = {"anthropic": MockAnthropicProvider(),
                     "openai": MockOpenAIProvider()}
        router = ProviderRouter(providers)
        fb = router.fallback("value")
        assert fb is not None
        assert isinstance(fb[0], MockOpenAIProvider)

    def test_fallback_unknown_returns_none(self):
        router = ProviderRouter({})
        assert router.fallback("unknown") is None


# ═══════════════════════════════════════════════════════════════════════
# GovernedLLMExecutor — hardened
# ═══════════════════════════════════════════════════════════════════════


class TestGovernedExecutor:
    def test_execute_returns_execution_result(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": MockAnthropicProvider()})
        executor = GovernedLLMExecutor(
            router=router,
            permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor,
            cost_tracker=None,
        )
        result = executor.execute(db_session, uuid4(), "value", "s", "u")
        assert isinstance(result, ExecutionResult)
        assert result.validated["conviction_score"] == 7

    def test_execute_logs_to_llm_execution_log(self, db_session):
        run_id = uuid4()
        _setup_run(db_session, run_id)
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": MockAnthropicProvider()})
        executor = GovernedLLMExecutor(
            router=router,
            permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor,
            cost_tracker=MockCostTracker,
        )
        executor.execute(db_session, run_id, "value", "s", "u")
        rows = db_session.execute(
            text("SELECT COUNT(*) FROM llm_execution_log WHERE run_id = :rid"),
            {"rid": run_id},
        ).scalar()
        assert rows >= 1

    def test_rejects_when_no_active_prompt(self, db_session):
        router = ProviderRouter({"anthropic": MockAnthropicProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        with pytest.raises(ValueError, match="No active prompt"):
            executor.execute(db_session, uuid4(), "nonexistent", "s", "u")

    def test_retry_then_fallback(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": FailingProvider(),
                                 "openai": MockOpenAIProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        result = executor.execute(db_session, uuid4(), "value", "s", "u")
        assert result.fallback_used

    def test_fail_fast_on_auth_error(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": AuthFailingProvider(),
                                 "openai": MockOpenAIProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        with pytest.raises(RuntimeError, match="Auth"):
            executor.execute(db_session, uuid4(), "value", "s", "u")

    def test_raises_when_all_fail(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": FailingProvider(),
                                 "openai": FailingProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        with pytest.raises(RuntimeError):
            executor.execute(db_session, uuid4(), "value", "s", "u")

    # ── Validation tests ──
    def test_rejects_bad_json_response(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": BadJSONProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        with pytest.raises(ValueError, match="JSON"):
            executor.execute(db_session, uuid4(), "value", "s", "u")

    def test_rejects_missing_fields_response(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": MissingFieldsProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        with pytest.raises(ValueError, match="Missing"):
            executor.execute(db_session, uuid4(), "value", "s", "u")

    def test_rejects_bad_conviction_score(self, db_session):
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": BadConvictionProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor, cost_tracker=None,
        )
        with pytest.raises(ValueError, match="conviction_score"):
            executor.execute(db_session, uuid4(), "value", "s", "u")

    # ── Fallback provenance test ──
    def test_fallback_logs_correct_provider(self, db_session):
        """Fallback: log shows actual provider/model, not primary."""
        run_id = uuid4()
        _setup_run(db_session, run_id)
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": FailingProvider(),
                                 "openai": MockOpenAIProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor,
            cost_tracker=MockCostTracker,
        )
        result = executor.execute(db_session, run_id, "value", "s", "u")
        assert result.fallback_used
        # Check log: model should be gpt-4o (fallback), not claude-sonnet-4
        row = db_session.execute(
            text("SELECT model, status FROM llm_execution_log"
                 " WHERE run_id = :rid"),
            {"rid": run_id},
        ).fetchone()
        assert row is not None
        assert row[0] == "gpt-4o"

    # ── Failed execution logging ──
    def test_failed_execution_logged(self, db_session):
        """Validation failure still writes llm_execution_log."""
        run_id = uuid4()
        _setup_run(db_session, run_id)
        _setup_prompt(db_session, "value")
        router = ProviderRouter({"anthropic": BadJSONProvider()})
        executor = GovernedLLMExecutor(
            router=router, permission_gate=MockPermissionGate,
            prompt_governor=MockPromptGovernor,
            cost_tracker=MockCostTracker,
        )
        with pytest.raises(ValueError):
            executor.execute(db_session, run_id, "value", "s", "u")
        rows = db_session.execute(
            text("SELECT COUNT(*) FROM llm_execution_log WHERE run_id = :rid"),
            {"rid": run_id},
        ).scalar()
        assert rows >= 1


# ═══════════════════════════════════════════════════════════════════════
# Credential isolation
# ═══════════════════════════════════════════════════════════════════════


class TestCredentialIsolation:
    def test_anthropic_fails_closed_without_key(self):
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ConfigurationError):
                AnthropicAdapter(api_key="")
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_openai_fails_closed_without_key(self):
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with pytest.raises(ConfigurationError):
                OpenAIAdapter(api_key="")
        finally:
            if old:
                os.environ["OPENAI_API_KEY"] = old

    def test_gemini_fails_closed_without_key(self):
        old = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            with pytest.raises(ConfigurationError):
                GeminiAdapter(api_key="")
        finally:
            if old:
                os.environ["GOOGLE_API_KEY"] = old

    def test_adapter_never_exposes_key_in_repr(self):
        adapter = AnthropicAdapter(api_key="«redacted:sk-…»")
        r = repr(adapter)
        assert "«redacted:sk-…»" not in r
        assert "<redacted>" in r


# ═══════════════════════════════════════════════════════════════════════
# AI Authority
# ═══════════════════════════════════════════════════════════════════════


class TestAIAuthority:
    def test_never_action_still_blocked(self):
        for action in ("execute_trade", "connect_broker", "modify_policy"):
            result = MockPermissionGate.check(action, caller="ai")
            assert not result.allowed
