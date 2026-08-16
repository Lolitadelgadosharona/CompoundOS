"""M7-003 Slice A — end-to-end business workflow (MOCK AI only).

Drives the full chain: Owner bootstrap → household → prompt approval →
research request → research execution (REAL GovernedLLMExecutor backed by
a mock provider) → prompt provenance + cost → llm_execution_log →
perspective analysis → memo → committee → decision draft → owner approval
→ confirmation → learning update.

No real AI calls.
"""

import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services.cost_tracker import CostTracker
from apps.api.services.dashboard_service import learning_metrics
from apps.api.services.decision_lifecycle import (
    CommitteeIntegrationService,
    DecisionBridgeService,
    OwnerDecisionService,
)
from apps.api.services.llm_provider_runtime import (
    GovernedLLMExecutor,
    LLMResponse,
    ProviderRouter,
)
from apps.api.services.permission_gate import PermissionGate
from apps.api.services.prompt_governor import PromptGovernor
from apps.api.services.research_evidence import EvidenceBundle
from apps.api.services.research_intelligence import (
    ConfidenceEngine,
    MemoGenerator,
    ResearchIntelligencePipeline,
)

pytestmark = pytest.mark.postgres


# ── Mocks (no real AI) ──────────────────────────────────────────────────


class MockProvider:
    """Deterministic LLMResponse for any perspective/model."""

    def generate(self, model, system_prompt, user_prompt,
                 max_output_tokens=2000):
        return LLMResponse(
            content='{"perspective": "value", "thesis": "Mock thesis",'
                    ' "conviction_score": 7}',
            model=model, provider="mock",
            input_tokens=100, output_tokens=50,
            duration_ms=100, finish_reason="stop",
        )


class MockEvidenceCollector:
    def collect(self, session, household_id, symbol=None):
        return EvidenceBundle(
            market_data={"overview": {"sector": "Tech"}},
            portfolio_context={"total_value": "1000000"},
            guardian_status={"active_events": 0},
        )


# ── Helpers ─────────────────────────────────────────────────────────────


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


def _seed_policy(db_session, household_id):
    policy_id = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_policies (id, household_id) VALUES (:id, :hh)"
    ), {"id": policy_id, "hh": household_id})
    vid = uuid4()
    db_session.execute(text(
        "INSERT INTO investment_policy_versions (id, policy_id,"
        " version_number, status, published_at, objectives, time_horizon,"
        " liquidity, diversification, contribution_policy,"
        " rebalancing_policy, prohibited_assets, leverage_policy,"
        " decision_process, notes)"
        " VALUES (:id, :pid, 1, 'published', NOW(), 'obj', 'horizon',"
        " '', '', '', '', '', '', 'decide', '')"
    ), {"id": vid, "pid": policy_id})
    db_session.execute(text(
        "UPDATE investment_policy_versions SET sealed_at = NOW() WHERE id = :id"
    ), {"id": vid})
    db_session.commit()


def _approve_prompts(db_session):
    """Seed draft prompts + Owner-approve all (bootstrap)."""
    gov = PromptGovernor()
    gov.seed_defaults(db_session)
    db_session.commit()
    for p in gov.list_prompts(db_session):
        if p["status"] == "draft":
            gov.approve(db_session, UUID(p["id"]))
    db_session.commit()
    return gov


def _governed_executor(db_session):
    gov = _approve_prompts(db_session)
    router = ProviderRouter({
        "anthropic": MockProvider(),
        "openai": MockProvider(),
        "google": MockProvider(),
    })
    return GovernedLLMExecutor(
        router,
        permission_gate=PermissionGate(),
        prompt_governor=gov,
        cost_tracker=CostTracker(),
    )


# ── E2E test ────────────────────────────────────────────────────────────


class TestEndToEndWorkflow:
    def test_full_business_chain(self, db_session):
        # 1. Owner bootstrap: household + policy + approved prompts
        hh = _setup_household(db_session)
        _seed_policy(db_session, hh)
        executor = _governed_executor(db_session)

        # 2. idea → review → request → run
        _idea_id, run_id = _setup_run(db_session, hh)

        # 3. Real governed executor runs the pipeline (mock evidence)
        pipeline = ResearchIntelligencePipeline(
            evidence_collector=MockEvidenceCollector(),
            perspective_executor=executor,
            memo_generator=MemoGenerator(executor),
            confidence_engine=ConfidenceEngine(),
        )
        output = pipeline.execute(db_session, run_id, hh, "AAPL")
        assert output.status == "completed"
        assert output.memo is not None

        # 4. Assert llm_execution_log carries provenance + cost + status
        logs = db_session.execute(text(
            "SELECT prompt_template_id, cost_estimate, status"
            " FROM llm_execution_log WHERE run_id = :rid"
        ), {"rid": run_id}).fetchall()
        assert len(logs) >= 6  # 6 perspectives (+ synthesis)
        for r in logs:
            assert r[0] is not None      # prompt_template_id (provenance)
            assert r[1] is not None      # cost_estimate (cost tracked)
            assert r[2] == "success"     # status

        # 5. Research → Committee → Decision draft
        bridge = CommitteeIntegrationService.complete_research(
            db_session, run_id, hh,
        )
        assert bridge["recommendation"] is not None
        memo_row = db_session.execute(text(
            "SELECT memo, recommendation FROM investment_memos WHERE id = :id"
        ), {"id": UUID(bridge["memo_id"])}).fetchone()
        memo_json = memo_row[0] if isinstance(memo_row[0], dict) \
            else json.loads(memo_row[0])
        decision, _draft = DecisionBridgeService.create_decision_draft(
            db_session, run_id, "AAPL", memo_row[1] or "HOLD",
            memo_json.get("thesis", ""), memo_json.get("risks", []),
        )
        assert decision.status == "draft"

        # 6. Owner approval → confirmed + review scheduling
        result = OwnerDecisionService.confirm_decision(db_session,
                                                       decision.id)
        assert result["status"] == "approved"
        status = db_session.execute(text(
            "SELECT status FROM decisions WHERE id = :id"
        ), {"id": decision.id}).scalar()
        assert status == "confirmed"

        # 7. Learning metrics reflect the confirmed decision
        metrics = learning_metrics(db_session)
        assert metrics["review_count"] == 3

    def test_permission_gate_enforced(self):
        """PermissionGate remains the explicit authorization boundary."""
        gate = PermissionGate()
        assert gate.check("execute_llm_call", "ai").allowed is True
        assert gate.check("execute_llm_call", "owner").allowed is True
        assert gate.check("execute_llm_call", "hacker").allowed is False
        assert gate.check("unknown_action", "owner").allowed is False
