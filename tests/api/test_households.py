from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import AuditEvent, HouseholdProfile
from apps.api.schemas import HouseholdCreate, HouseholdResponse, HouseholdUpdate
from apps.api.services import households as household_service

HOUSEHOLD_PAYLOAD: dict[str, str] = {
    "household_name": "Wang Household",
    "base_currency": "USD",
    "investment_horizon": "Long term",
    "liquidity_needs": "User-entered liquidity context",
    "risk_statement": "User-entered risk context",
    "notes": "Private household notes",
}

pytestmark = pytest.mark.postgres

HOUSEHOLD_CHECK_CONSTRAINTS = {
    "ck_household_profiles_name_length",
    "ck_household_profiles_currency_format",
    "ck_household_profiles_investment_horizon_length",
    "ck_household_profiles_liquidity_needs_length",
    "ck_household_profiles_risk_statement_length",
    "ck_household_profiles_notes_length",
}


def create_household(client: TestClient, payload: dict[str, Any] | None = None):
    return client.post("/api/households", json=payload or HOUSEHOLD_PAYLOAD)


def test_get_current_returns_404_without_household(api_client: TestClient) -> None:
    response = api_client.get("/api/households/current")
    assert response.status_code == 404
    assert response.json() == {"detail": "Household profile not found"}


def test_create_get_and_audit_household(api_client: TestClient) -> None:
    created = create_household(api_client)
    assert created.status_code == 201
    body = created.json()
    assert body["household_name"] == HOUSEHOLD_PAYLOAD["household_name"]
    assert body["base_currency"] == "USD"
    assert "singleton_key" not in body

    retrieved = api_client.get("/api/households/current")
    assert retrieved.status_code == 200
    assert retrieved.json() == body

    audit = api_client.get("/api/households/current/audit-events")
    assert audit.status_code == 200
    events = audit.json()
    assert len(events) == 1
    assert events[0]["sequence_number"] > 0
    assert events[0]["actor"] == "local-owner"
    assert events[0]["action"] == "household.created"
    assert events[0]["metadata"] == {"changed_fields": sorted(HOUSEHOLD_PAYLOAD)}
    assert not set(HOUSEHOLD_PAYLOAD.values()) & set(events[0]["metadata"]["changed_fields"])


def test_second_create_conflicts_and_client_identifiers_are_rejected(
    api_client: TestClient,
) -> None:
    assert create_household(api_client).status_code == 201
    second_create = create_household(
        api_client, {**HOUSEHOLD_PAYLOAD, "household_name": "Other"}
    )
    assert second_create.status_code == 409

    supplied_id = create_household(api_client, {**HOUSEHOLD_PAYLOAD, "id": "client-id"})
    assert supplied_id.status_code == 422
    assert "client-id" not in supplied_id.text


@pytest.mark.parametrize("field", ["id", "actor", "created_at", "updated_at", "unknown"])
def test_patch_rejects_unapproved_fields(api_client: TestClient, field: str) -> None:
    assert create_household(api_client).status_code == 201
    response = api_client.patch("/api/households/current", json={field: "sensitive-value"})
    assert response.status_code == 422
    assert "sensitive-value" not in response.text


def test_patch_rejects_explicit_null(api_client: TestClient) -> None:
    assert create_household(api_client).status_code == 201
    response = api_client.patch("/api/households/current", json={"notes": None})
    assert response.status_code == 422


def test_patch_updates_allowed_fields_and_appends_ordered_audit_event(
    api_client: TestClient,
) -> None:
    assert create_household(api_client).status_code == 201
    response = api_client.patch(
        "/api/households/current",
        json={"household_name": "Updated Household", "notes": "Updated private notes"},
    )
    assert response.status_code == 200
    assert response.json()["household_name"] == "Updated Household"

    events = api_client.get("/api/households/current/audit-events").json()
    assert [event["action"] for event in events] == ["household.created", "household.updated"]
    assert events[0]["sequence_number"] < events[1]["sequence_number"]
    assert events[1]["metadata"] == {"changed_fields": ["household_name", "notes"]}
    assert "Updated private notes" not in str(events)


def test_empty_and_noop_patch_return_400(api_client: TestClient) -> None:
    assert create_household(api_client).status_code == 201
    assert api_client.patch("/api/households/current", json={}).status_code == 400
    noop = api_client.patch(
        "/api/households/current", json={"household_name": HOUSEHOLD_PAYLOAD["household_name"]}
    )
    assert noop.status_code == 400
    assert len(api_client.get("/api/households/current/audit-events").json()) == 1


def test_validation_is_strict_and_does_not_echo_sensitive_input(api_client: TestClient) -> None:
    invalid = {
        **HOUSEHOLD_PAYLOAD,
        "household_name": "   ",
        "base_currency": "usd",
        "risk_statement": "secret-risk-text",
        "unexpected": "secret-extra-text",
    }
    response = create_household(api_client, invalid)
    assert response.status_code == 422
    assert "secret-risk-text" not in response.text
    assert "secret-extra-text" not in response.text


def test_database_singleton_constraint_is_enforced(db_session: Session) -> None:
    first = HouseholdProfile(**HOUSEHOLD_PAYLOAD)
    db_session.add(first)
    db_session.commit()
    db_session.add(HouseholdProfile(**{**HOUSEHOLD_PAYLOAD, "household_name": "Other"}))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(HouseholdProfile)) == 1


@pytest.mark.parametrize(
    ("constraint_name", "overrides"),
    [
        ("ck_household_profiles_name_length", {"household_name": ""}),
        ("ck_household_profiles_name_length", {"household_name": "x" * 201}),
        ("ck_household_profiles_currency_format", {"base_currency": "usd"}),
        (
            "ck_household_profiles_investment_horizon_length",
            {"investment_horizon": "x" * 2_001},
        ),
        ("ck_household_profiles_liquidity_needs_length", {"liquidity_needs": "x" * 4_001}),
        ("ck_household_profiles_risk_statement_length", {"risk_statement": "x" * 4_001}),
        ("ck_household_profiles_notes_length", {"notes": "x" * 8_001}),
    ],
)
def test_database_rejects_values_outside_named_safety_constraints(
    db_session: Session,
    constraint_name: str,
    overrides: dict[str, str],
) -> None:
    db_session.add(HouseholdProfile(**{**HOUSEHOLD_PAYLOAD, **overrides}))

    with pytest.raises(IntegrityError) as exc_info:
        db_session.commit()

    assert exc_info.value.orig.diag.constraint_name == constraint_name
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(HouseholdProfile)) == 0
    assert db_session.scalar(select(text("1"))) == 1


def test_database_accepts_unicode_at_character_limits_and_response_schema(
    db_session: Session,
) -> None:
    household = HouseholdProfile(
        **{
            **HOUSEHOLD_PAYLOAD,
            "household_name": "家" * 200,
            "investment_horizon": "期" * 2_000,
            "liquidity_needs": "流" * 4_000,
            "risk_statement": "险" * 4_000,
            "notes": "注" * 8_000,
        }
    )
    db_session.add(household)
    db_session.commit()

    response = HouseholdResponse.model_validate(household)
    assert len(response.household_name) == 200
    assert len(response.notes) == 8_000


def test_migration_installs_all_named_household_check_constraints(postgres_engine) -> None:
    constraints = {
        constraint["name"]
        for constraint in inspect(postgres_engine).get_check_constraints("household_profiles")
    }
    assert HOUSEHOLD_CHECK_CONSTRAINTS <= constraints


def test_required_postgres_suite_uses_live_postgresql(postgres_engine) -> None:
    with postgres_engine.connect() as connection:
        version = connection.scalar(text("SELECT current_setting('server_version_num')::int"))
        assert version >= 160000


def test_audit_failure_rolls_back_household_create(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_audit(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(household_service, "add_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        household_service.create_household(db_session, HouseholdCreate(**HOUSEHOLD_PAYLOAD))
    assert db_session.scalar(select(func.count()).select_from(HouseholdProfile)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_audit_failure_rolls_back_household_update(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    household_service.create_household(db_session, HouseholdCreate(**HOUSEHOLD_PAYLOAD))

    def fail_audit(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(household_service, "add_audit_event", fail_audit)
    with pytest.raises(RuntimeError, match="simulated audit failure"):
        household_service.update_current_household(
            db_session, HouseholdUpdate(household_name="Should Roll Back")
        )
    db_session.expire_all()
    household = db_session.scalar(select(HouseholdProfile))
    assert household is not None
    assert household.household_name == HOUSEHOLD_PAYLOAD["household_name"]
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == 1


def test_migration_contains_only_approved_product_tables(postgres_engine) -> None:
    tables = set(inspect(postgres_engine).get_table_names())
    assert tables - {"alembic_version"} == {
        "audit_events",
        "household_profiles",
        "investment_policies",
        "investment_policy_draft_allocations",
        "investment_policy_drafts",
        "investment_policy_version_allocations",
        "investment_policy_versions",
        "decisions",
        "decision_drafts",
        "decision_confirmed_snapshots",
        "decision_corrections",
        "portfolios",
        "portfolio_drafts",
        "portfolio_draft_holdings",
        "portfolio_snapshots",
        "portfolio_snapshot_holdings",
        "accounts",
        "guardian_checks",
        "guardian_check_drafts",
        "guardian_check_confirmed",
        "guardian_evaluation_runs",
        "guardian_events",
        "job_definitions",
        "schedules",
        "runs",
        "attempts",
        "leases",
    }
