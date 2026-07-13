from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import AuditEvent, HouseholdProfile
from apps.api.schemas import HouseholdCreate, HouseholdUpdate
from apps.api.services import households as household_service

HOUSEHOLD_PAYLOAD: dict[str, str] = {
    "household_name": "Wang Household",
    "base_currency": "USD",
    "investment_horizon": "Long term",
    "liquidity_needs": "User-entered liquidity context",
    "risk_statement": "User-entered risk context",
    "notes": "Private household notes",
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
    assert tables - {"alembic_version"} == {"household_profiles", "audit_events"}
