from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from apps.api.models import (
    AuditEvent,
    HouseholdProfile,
    InvestmentPolicy,
    InvestmentPolicyDraft,
    InvestmentPolicyVersion,
)
from apps.api.policy_schemas import AllocationReplaceRequest, PublishPolicyDraftRequest
from apps.api.services import policies as policy_service

pytestmark = pytest.mark.postgres

HOUSEHOLD = {
    "household_name": "Policy API Household",
    "base_currency": "USD",
    "investment_horizon": "",
    "liquidity_needs": "",
    "risk_statement": "",
    "notes": "",
}
READY_TEXT = {
    "objectives": "Preserve the owner's stated long-term objectives.",
    "time_horizon": "Long term",
    "decision_process": "Record reasons before making a decision.",
}
ALLOCATIONS = [
    {"asset_class_name": "Global Equity", "target_percentage": "60.00"},
    {"asset_class_name": "Cash", "target_percentage": "40.00"},
]


def create_household(client: TestClient) -> None:
    response = client.post("/api/households", json=HOUSEHOLD)
    assert response.status_code == 201


def create_policy(client: TestClient) -> dict:
    response = client.post("/api/policies")
    assert response.status_code == 201, response.text
    return response.json()


def prepare_draft(client: TestClient, revision: int = 1) -> dict:
    text_response = client.patch(
        "/api/policies/current/draft",
        json={"expected_revision": revision, **READY_TEXT},
    )
    assert text_response.status_code == 200, text_response.text
    allocation_response = client.put(
        "/api/policies/current/draft/allocations",
        json={
            "expected_revision": text_response.json()["revision"],
            "items": ALLOCATIONS,
        },
    )
    assert allocation_response.status_code == 200, allocation_response.text
    return allocation_response.json()


def publish(client: TestClient, revision: int) -> dict:
    response = client.post(
        "/api/policies/current/draft/publish",
        json={"expected_revision": revision, "confirmation": True},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_policy_create_read_singleton_and_audit_redaction(api_client: TestClient) -> None:
    assert api_client.post("/api/policies").status_code == 404
    create_household(api_client)
    created = create_policy(api_client)
    assert created["policy"]["household_id"]
    assert created["draft"]["revision"] == 1
    assert created["draft"]["allocations"] == []
    assert api_client.get("/api/policies/current").status_code == 200
    assert api_client.post("/api/policies").status_code == 409

    events = api_client.get("/api/policies/current/audit-events").json()
    assert [event["action"] for event in events] == [
        "policy.created",
        "policy.draft.created",
    ]
    assert events[0]["metadata"] == {}
    assert events[1]["metadata"] == {"draft_revision": 1}
    assert all(event["actor"] == "local-owner" for event in events)


def test_draft_text_revision_noop_stale_and_validation(api_client: TestClient) -> None:
    create_household(api_client)
    create_policy(api_client)
    updated = api_client.patch(
        "/api/policies/current/draft",
        json={"expected_revision": 1, "objectives": "  Owner objective  "},
    )
    assert updated.status_code == 200
    assert updated.json()["objectives"] == "Owner objective"
    assert updated.json()["revision"] == 2

    assert api_client.patch(
        "/api/policies/current/draft",
        json={"expected_revision": 2, "objectives": "Owner objective"},
    ).status_code == 400
    assert api_client.patch(
        "/api/policies/current/draft",
        json={"expected_revision": 1, "notes": "stale private value"},
    ).status_code == 409
    invalid = api_client.patch(
        "/api/policies/current/draft",
        json={"expected_revision": 2, "unknown": "private value"},
    )
    assert invalid.status_code == 422
    assert "private value" not in invalid.text

    events = api_client.get("/api/policies/current/audit-events").json()
    assert [event["action"] for event in events].count("policy.draft.updated") == 1
    assert events[-1]["metadata"] == {
        "changed_fields": ["objectives"],
        "draft_revision": 2,
    }
    assert "Owner objective" not in str(events)


def test_allocation_replace_is_atomic_revisioned_and_validated(api_client: TestClient) -> None:
    create_household(api_client)
    create_policy(api_client)
    replaced = api_client.put(
        "/api/policies/current/draft/allocations",
        json={"expected_revision": 1, "items": ALLOCATIONS},
    )
    assert replaced.status_code == 200
    body = replaced.json()
    assert body["revision"] == 2
    assert [item["target_percentage"] for item in body["allocations"]] == [
        "60.00",
        "40.00",
    ]
    assert all("normalized_asset_class_name" not in item for item in body["allocations"])

    assert api_client.put(
        "/api/policies/current/draft/allocations",
        json={"expected_revision": 2, "items": ALLOCATIONS},
    ).status_code == 400
    duplicate = api_client.put(
        "/api/policies/current/draft/allocations",
        json={
            "expected_revision": 2,
            "items": [
                {"asset_class_name": "Cash", "target_percentage": "50.00"},
                {"asset_class_name": " ＣＡＳＨ ", "target_percentage": "50.00"},
            ],
        },
    )
    assert duplicate.status_code == 422
    assert api_client.put(
        "/api/policies/current/draft/allocations",
        json={
            "expected_revision": 2,
            "items": [{"asset_class_name": "Cash", "target_percentage": 100}],
        },
    ).status_code == 422
    assert api_client.get("/api/policies/current/draft").json()["allocations"] == body[
        "allocations"
    ]


def test_discard_and_blank_draft_lifecycle(api_client: TestClient) -> None:
    create_household(api_client)
    create_policy(api_client)
    assert api_client.post(
        "/api/policies/current/draft/discard", json={"expected_revision": 2}
    ).status_code == 409
    assert api_client.post(
        "/api/policies/current/draft/discard", json={"expected_revision": 1}
    ).status_code == 204
    assert api_client.get("/api/policies/current/draft").status_code == 404
    recreated = api_client.post("/api/policies/current/draft", json={})
    assert recreated.status_code == 201
    assert recreated.json()["source_version_id"] is None
    assert recreated.json()["allocations"] == []
    assert api_client.post("/api/policies/current/draft", json={}).status_code == 409


def test_publish_requires_complete_record_and_exposes_immutable_reads(
    api_client: TestClient,
) -> None:
    create_household(api_client)
    create_policy(api_client)
    assert api_client.post(
        "/api/policies/current/draft/publish",
        json={"expected_revision": 1, "confirmation": True},
    ).status_code == 400
    draft = prepare_draft(api_client)
    published = publish(api_client, draft["revision"])
    assert published["version_number"] == 1
    assert published["status"] == "published"
    assert "sealed_at" not in published
    assert [item["target_percentage"] for item in published["allocations"]] == [
        "60.00",
        "40.00",
    ]
    assert api_client.get("/api/policies/current/draft").status_code == 404
    assert api_client.get("/api/policies/current/published").json() == published
    assert api_client.get("/api/policies/current/versions/1").json() == published
    assert api_client.get("/api/policies/current/versions/2").status_code == 404


def test_replacement_publish_copy_provenance_history_and_audit_order(
    api_client: TestClient,
) -> None:
    create_household(api_client)
    create_policy(api_client)
    first = publish(api_client, prepare_draft(api_client)["revision"])

    invalid_source = api_client.post(
        "/api/policies/current/draft", json={"source_version_id": str(uuid4())}
    )
    assert invalid_source.status_code == 409
    copied = api_client.post(
        "/api/policies/current/draft", json={"source_version_id": first["id"]}
    )
    assert copied.status_code == 201
    assert copied.json()["source_version_id"] == first["id"]
    assert copied.json()["allocations"] == first["allocations"]
    second = publish(api_client, copied.json()["revision"])
    assert second["version_number"] == 2
    assert api_client.post(
        "/api/policies/current/draft", json={"source_version_id": first["id"]}
    ).status_code == 409

    history = api_client.get("/api/policies/current/versions?limit=1").json()
    assert [item["version_number"] for item in history["items"]] == [2]
    assert history["next_before_version_number"] == 2
    next_page = api_client.get(
        "/api/policies/current/versions?limit=1&before_version_number=2"
    ).json()
    assert [item["version_number"] for item in next_page["items"]] == [1]
    assert next_page["next_before_version_number"] is None

    events = api_client.get("/api/policies/current/audit-events?limit=2").json()
    assert [event["action"] for event in events] == [
        "policy.superseded",
        "policy.published",
    ]
    assert events[0]["sequence_number"] < events[1]["sequence_number"]
    assert events[0]["metadata"] == {"version_number": 1}
    assert events[1]["metadata"] == {
        "allocation_item_count": 2,
        "version_number": 2,
    }
    assert "Global Equity" not in str(events)
    assert "60.00" not in str(events)


def test_audit_failure_rolls_back_policy_create(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(HouseholdProfile(**HOUSEHOLD))
    db_session.commit()
    calls = 0
    real_add = policy_service.add_policy_audit_event

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated audit failure")
        return real_add(*args, **kwargs)

    monkeypatch.setattr(policy_service, "add_policy_audit_event", fail_second)
    with pytest.raises(RuntimeError):
        policy_service.create_policy(db_session)
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicy)) == 0
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyDraft)) == 0


def test_publish_failure_rolls_back_snapshot_draft_and_audit(
    api_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    real_add = policy_service.add_policy_audit_event

    def fail_published(*args, **kwargs):
        if kwargs.get("action") == "policy.published":
            raise RuntimeError("simulated publish audit failure")
        return real_add(*args, **kwargs)

    monkeypatch.setattr(policy_service, "add_policy_audit_event", fail_published)
    with pytest.raises(RuntimeError):
        policy_service.publish_draft(
            db_session,
            PublishPolicyDraftRequest(
                expected_revision=draft["revision"], confirmation=True
            ),
        )
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyVersion)) == 0
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyDraft)) == 1
    actions = list(db_session.scalars(select(AuditEvent.action)))
    assert "policy.published" not in actions


def test_concurrent_policy_create_has_one_winner(postgres_engine, db_session: Session) -> None:
    del db_session
    with Session(postgres_engine) as setup:
        setup.add(HouseholdProfile(**HOUSEHOLD))
        setup.commit()
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)

    def attempt() -> str:
        with factory() as session:
            try:
                policy_service.create_policy(session)
                return "created"
            except policy_service.PolicyAlreadyExistsError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: attempt(), range(2)))
    assert sorted(results) == ["conflict", "created"]


def test_concurrent_publish_has_one_winner(api_client: TestClient, postgres_engine) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)

    def attempt() -> str:
        with factory() as session:
            try:
                policy_service.publish_draft(
                    session,
                    PublishPolicyDraftRequest(
                        expected_revision=draft["revision"], confirmation=True
                    ),
                )
                return "published"
            except policy_service.DraftConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: attempt(), range(2)))
    assert sorted(results) == ["conflict", "published"]
    with Session(postgres_engine) as session:
        assert session.scalar(select(func.count()).select_from(InvestmentPolicyVersion)) == 1


def test_allocation_replace_racing_publish_cannot_create_mixed_snapshot(
    api_client: TestClient, postgres_engine
) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)

    def replace_attempt() -> str:
        with factory() as session:
            try:
                policy_service.replace_allocations(
                    session,
                    AllocationReplaceRequest(
                        expected_revision=draft["revision"],
                        items=[
                            {
                                "asset_class_name": "Cash",
                                "target_percentage": "100.00",
                            }
                        ],
                    ),
                )
                return "allocations"
            except policy_service.DraftConflictError:
                return "conflict"

    def publish_attempt() -> str:
        with factory() as session:
            try:
                policy_service.publish_draft(
                    session,
                    PublishPolicyDraftRequest(
                        expected_revision=draft["revision"], confirmation=True
                    ),
                )
                return "published"
            except policy_service.DraftConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [
            executor.submit(replace_attempt),
            executor.submit(publish_attempt),
        ]
        outcomes = sorted(future.result() for future in results)
    assert "conflict" in outcomes
    assert len(set(outcomes)) == 2

    published = api_client.get("/api/policies/current/published")
    if published.status_code == 200:
        assert published.json()["allocations"] == draft["allocations"]
    else:
        current_draft = api_client.get("/api/policies/current/draft").json()
        assert current_draft["allocations"][0]["target_percentage"] == "100.00"
