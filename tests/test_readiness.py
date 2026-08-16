"""M7-001 tests — system readiness (read-only bootstrap status)."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apps.api.services import readiness_service
from apps.api.services.prompt_governor import PromptGovernor

pytestmark = pytest.mark.postgres


def _seed_household(db_session):
    hh = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles (id, singleton_key, household_name,"
        " base_currency, investment_horizon, liquidity_needs, risk_statement,"
        " notes, created_at, updated_at)"
        " VALUES (:id, TRUE, 't', 'USD', 'lt', 'l', 'm', '', NOW(), NOW())"
        " ON CONFLICT (singleton_key) DO NOTHING"
    ), {"id": hh})
    db_session.commit()


def _seed_owner_key(db_session):
    db_session.execute(text(
        "INSERT INTO owner_api_keys (id, key_hash, label, created_by)"
        " VALUES (:id, :kh, 'test', 'bootstrap')"
    ), {"id": uuid4(), "kh": "testhash"})
    db_session.commit()


def _seed_and_approve_prompts(db_session):
    gov = PromptGovernor()
    gov.seed_defaults(db_session)
    db_session.commit()
    for p in gov.list_prompts(db_session):
        if p["status"] == "draft":
            gov.approve(db_session, UUID(p["id"]))
    db_session.commit()


def _configure_providers(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AV_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


def _seed_published_policy(db_session):
    from apps.api.policy_schemas import PersonalPolicySetupRequest
    from apps.api.services.policies import setup_personal_policy

    setup_personal_policy(db_session, PersonalPolicySetupRequest(
        investment_goal="Long term wealth compounding",
        risk_preference="Growth",
        investment_horizon="10+ years",
        max_single_position_pct=15,
        min_cash_pct=10,
        principles="Focus on quality businesses",
    ))


class TestReadinessService:
    def test_empty_database_pending(self, db_session):
        r = readiness_service.readiness_status(db_session)
        assert r["overall"] == "pending"
        assert r["checks"]["schema_at_head"] is True
        assert r["checks"]["governance_ready"] is True
        assert r["checks"]["owner_key_present"] is False
        assert r["checks"]["household_created"] is False
        assert r["checks"]["prompts_approved"] is False
        assert r["checks"]["providers_configured"] is False
        assert r["checks"]["policy_published"] is False

    def test_all_ready(self, db_session, monkeypatch):
        _seed_household(db_session)
        _seed_owner_key(db_session)
        _seed_and_approve_prompts(db_session)
        _seed_published_policy(db_session)
        _configure_providers(monkeypatch)
        r = readiness_service.readiness_status(db_session)
        assert r["overall"] == "ready"
        assert all(r["checks"].values())
        assert r["remaining_steps"] == []

    def test_owner_key_flips(self, db_session):
        _seed_owner_key(db_session)
        r = readiness_service.readiness_status(db_session)
        assert r["checks"]["owner_key_present"] is True

    def test_household_flips(self, db_session):
        _seed_household(db_session)
        r = readiness_service.readiness_status(db_session)
        assert r["checks"]["household_created"] is True

    def test_prompts_approved_flips(self, db_session):
        _seed_and_approve_prompts(db_session)
        r = readiness_service.readiness_status(db_session)
        assert r["checks"]["prompts_approved"] is True

    def test_policy_published_flips(self, db_session):
        _seed_household(db_session)
        _seed_published_policy(db_session)
        r = readiness_service.readiness_status(db_session)
        assert r["checks"]["policy_published"] is True

    def test_remaining_steps_ordering(self, db_session):
        r = readiness_service.readiness_status(db_session)
        steps = r["remaining_steps"]
        # owner key → household → policy → prompts → providers
        assert "Owner API key" in steps[0]
        assert "household" in steps[1]
        assert "Investment Policy" in steps[2]
        assert "prompt" in steps[3]
        assert "provider" in steps[4]


class TestSetupAPI:
    def test_status_endpoint(self, api_client):
        r = api_client.get("/api/setup/status")
        assert r.status_code == 200
        data = r.json()
        assert data["overall"] in ("ready", "pending")
        assert "checks" in data
        assert "remaining_steps" in data

    def test_setup_page_renders(self, api_client):
        r = api_client.get("/setup")
        assert r.status_code == 200
        assert "System Readiness" in r.text
        assert "Remaining Actions" in r.text
