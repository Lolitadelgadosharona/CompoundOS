from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from apps.api.main import app
from apps.api.models import (
    AuditEvent,
    HouseholdProfile,
    InvestmentPolicy,
    InvestmentPolicyDraft,
    InvestmentPolicyDraftAllocation,
    InvestmentPolicyVersion,
    InvestmentPolicyVersionAllocation,
)
from apps.api.policy_schemas import (
    POLICY_TEXT_LIMITS,
    AllocationReplaceRequest,
    CreatePolicyDraftRequest,
    PolicyDraftUpdate,
    PublishPolicyDraftRequest,
)
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


def allocation_content(items: list[dict]) -> list[dict]:
    return [
        {
            "asset_class_name": item["asset_class_name"],
            "target_percentage": item["target_percentage"],
            "sort_order": item["sort_order"],
        }
        for item in items
    ]


def policy_state_counts(session: Session) -> dict[str, int]:
    return {
        "drafts": session.scalar(select(func.count()).select_from(InvestmentPolicyDraft)),
        "draft_allocations": session.scalar(
            select(func.count()).select_from(InvestmentPolicyDraftAllocation)
        ),
        "versions": session.scalar(select(func.count()).select_from(InvestmentPolicyVersion)),
        "version_allocations": session.scalar(
            select(func.count()).select_from(InvestmentPolicyVersionAllocation)
        ),
    }


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


def test_policy_create_accepts_explicit_empty_object(api_client: TestClient) -> None:
    create_household(api_client)
    response = api_client.post("/api/policies", json={})
    assert response.status_code == 201


@pytest.mark.parametrize(
    "invalid_body",
    [
        {"unexpected": "secret-marker"},
        "secret-marker",
        42,
        ["secret-marker"],
    ],
)
def test_policy_create_rejects_nonempty_or_nonobject_body_without_writes(
    api_client: TestClient, db_session: Session, invalid_body
) -> None:
    create_household(api_client)
    response = api_client.post("/api/policies", json=invalid_body)
    assert response.status_code == 422
    assert "secret-marker" not in response.text
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicy)) == 0
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyDraft)) == 0
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == 1


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


@pytest.mark.parametrize("field_name,maximum", POLICY_TEXT_LIMITS.items())
def test_policy_text_unicode_boundaries_reach_real_postgresql(
    api_client: TestClient, field_name: str, maximum: int
) -> None:
    create_household(api_client)
    create_policy(api_client)
    accepted = api_client.patch(
        "/api/policies/current/draft",
        json={
            "expected_revision": 1,
            field_name: f"  {'界' * maximum}\u2003",
        },
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()[field_name] == "界" * maximum
    rejected = api_client.patch(
        "/api/policies/current/draft",
        json={"expected_revision": 2, field_name: "界" * (maximum + 1)},
    )
    assert rejected.status_code == 422
    assert api_client.get("/api/policies/current/draft").json()["revision"] == 2


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
    # Baseline: timezone serialization differs between POST/GET responses.
    # Normalize both published_at values to datetime objects for reliable comparison.
    # This does not weaken any business assertion — all other fields are compared exactly.
    from datetime import datetime as _dt
    got = api_client.get("/api/policies/current/published").json()
    for d in (published, got):
        d["published_at"] = _dt.fromisoformat(
            d["published_at"].replace("Z", "+00:00")
        )
    assert got == published
    got2 = api_client.get("/api/policies/current/versions/1").json()
    got2["published_at"] = _dt.fromisoformat(
        got2["published_at"].replace("Z", "+00:00")
    )
    assert got2 == published
    assert api_client.get("/api/policies/current/versions/2").status_code == 404


@pytest.mark.parametrize(
    "items",
    [
        [{"asset_class_name": "Cash", "target_percentage": "99.99"}],
        [
            {"asset_class_name": "Equity", "target_percentage": "50.00"},
            {"asset_class_name": "Cash", "target_percentage": "50.01"},
        ],
    ],
)
def test_publish_rejects_totals_below_or_above_100_without_consuming_draft(
    api_client: TestClient, db_session: Session, items: list[dict[str, str]]
) -> None:
    create_household(api_client)
    create_policy(api_client)
    updated = api_client.patch(
        "/api/policies/current/draft", json={"expected_revision": 1, **READY_TEXT}
    ).json()
    saved = api_client.put(
        "/api/policies/current/draft/allocations",
        json={"expected_revision": updated["revision"], "items": items},
    )
    assert saved.status_code == 200
    response = api_client.post(
        "/api/policies/current/draft/publish",
        json={"expected_revision": saved.json()["revision"], "confirmation": True},
    )
    assert response.status_code == 400
    assert api_client.get("/api/policies/current/draft").status_code == 200
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyVersion)) == 0
    assert "policy.published" not in list(db_session.scalars(select(AuditEvent.action)))


def test_publish_uses_exact_decimal_sum_and_allows_empty_optional_text(
    api_client: TestClient,
) -> None:
    create_household(api_client)
    create_policy(api_client)
    updated = api_client.patch(
        "/api/policies/current/draft",
        json={
            "expected_revision": 1,
            "objectives": "x",
            "time_horizon": "y",
            "decision_process": "z",
        },
    ).json()
    saved = api_client.put(
        "/api/policies/current/draft/allocations",
        json={
            "expected_revision": updated["revision"],
            "items": [
                {"asset_class_name": "One", "target_percentage": "33.33"},
                {"asset_class_name": "Two", "target_percentage": "33.33"},
                {"asset_class_name": "Three", "target_percentage": "33.34"},
            ],
        },
    ).json()
    published = publish(api_client, saved["revision"])
    assert [item["target_percentage"] for item in published["allocations"]] == [
        "33.33",
        "33.33",
        "33.34",
    ]
    for optional_field in set(POLICY_TEXT_LIMITS) - set(READY_TEXT):
        assert published[optional_field] == ""


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
    assert allocation_content(copied.json()["allocations"]) == allocation_content(
        first["allocations"]
    )
    assert {item["id"] for item in copied.json()["allocations"]}.isdisjoint(
        {item["id"] for item in first["allocations"]}
    )
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


def test_policy_audit_latest_window_limits_order_filters_and_redacts(
    api_client: TestClient, db_session: Session
) -> None:
    create_household(api_client)
    create_policy(api_client)
    policy = db_session.scalar(select(InvestmentPolicy))
    assert policy is not None

    gap = AuditEvent(
        household_id=policy.household_id,
        actor="local-owner",
        action="policy.draft.updated",
        entity_type="InvestmentPolicy",
        entity_id=policy.id,
        event_metadata={"draft_revision": 999},
    )
    db_session.add(gap)
    db_session.flush()
    db_session.rollback()

    for index in range(120):
        db_session.add(
            AuditEvent(
                household_id=policy.household_id,
                actor="local-owner",
                action="policy.draft.updated",
                entity_type="InvestmentPolicy",
                entity_id=policy.id,
                event_metadata={"draft_revision": index + 2},
            )
        )
        if index % 20 == 0:
            db_session.add_all(
                [
                    AuditEvent(
                        household_id=policy.household_id,
                        actor="local-owner",
                        action="household.updated",
                        entity_type="HouseholdProfile",
                        entity_id=policy.household_id,
                        event_metadata={"changed_fields": ["secret-marker"]},
                    ),
                    AuditEvent(
                        household_id=policy.household_id,
                        actor="local-owner",
                        action="policy.draft.updated",
                        entity_type="InvestmentPolicy",
                        entity_id=uuid4(),
                        event_metadata={"draft_revision": 999},
                    ),
                ]
            )
    db_session.commit()

    matching_desc = list(
        db_session.scalars(
            select(AuditEvent.sequence_number)
            .where(
                AuditEvent.household_id == policy.household_id,
                AuditEvent.entity_type == "InvestmentPolicy",
                AuditEvent.entity_id == policy.id,
            )
            .order_by(AuditEvent.sequence_number.desc())
        )
    )
    default_response = api_client.get("/api/policies/current/audit-events")
    assert default_response.status_code == 200
    assert [event["sequence_number"] for event in default_response.json()] == list(
        reversed(matching_desc[:50])
    )
    maximum_response = api_client.get("/api/policies/current/audit-events?limit=100")
    assert [event["sequence_number"] for event in maximum_response.json()] == list(
        reversed(matching_desc[:100])
    )
    assert set(matching_desc[100:]).isdisjoint(
        {event["sequence_number"] for event in maximum_response.json()}
    )
    assert "secret-marker" not in maximum_response.text
    assert "asset_class_name" not in maximum_response.text
    assert "target_percentage" not in maximum_response.text
    for invalid_limit in (0, -1, 101):
        assert api_client.get(
            f"/api/policies/current/audit-events?limit={invalid_limit}"
        ).status_code == 422


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


def test_replacement_publish_failure_restores_superseded_version_and_draft(
    api_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_household(api_client)
    create_policy(api_client)
    first = publish(api_client, prepare_draft(api_client)["revision"])
    copied = api_client.post(
        "/api/policies/current/draft", json={"source_version_id": first["id"]}
    ).json()
    actions_before = list(
        db_session.scalars(
            select(AuditEvent.action).order_by(AuditEvent.sequence_number)
        )
    )
    db_session.rollback()
    real_add = policy_service.add_policy_audit_event

    def fail_after_supersession(*args, **kwargs):
        if kwargs.get("action") == "policy.published":
            raise RuntimeError("simulated replacement publish failure")
        return real_add(*args, **kwargs)

    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(
            policy_service, "add_policy_audit_event", fail_after_supersession
        )
        with pytest.raises(RuntimeError, match="replacement publish failure"):
            policy_service.publish_draft(
                db_session,
                PublishPolicyDraftRequest(
                    expected_revision=copied["revision"], confirmation=True
                ),
            )

    version = db_session.scalar(select(InvestmentPolicyVersion))
    assert version is not None
    assert version.status == "published"
    assert version.superseded_at is None
    assert policy_state_counts(db_session) == {
        "drafts": 1,
        "draft_allocations": 2,
        "versions": 1,
        "version_allocations": 2,
    }
    assert list(
        db_session.scalars(
            select(AuditEvent.action).order_by(AuditEvent.sequence_number)
        )
    ) == actions_before
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicy)) == 1


def test_allocation_database_failure_restores_collection_revision_and_audit(
    api_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    draft_id = draft["id"]
    original_content = allocation_content(draft["allocations"])
    original_actions = list(
        db_session.scalars(
            select(AuditEvent.action).order_by(AuditEvent.sequence_number)
        )
    )
    db_session.rollback()

    def fail_after_delete(
        session: Session, target_draft_id, _items
    ) -> list[InvestmentPolicyDraftAllocation]:
        session.execute(
            delete(InvestmentPolicyDraftAllocation).where(
                InvestmentPolicyDraftAllocation.draft_id == target_draft_id
            )
        )
        session.flush()
        session.add(
            InvestmentPolicyDraftAllocation(
                draft_id=target_draft_id,
                asset_class_name="Invalid",
                normalized_asset_class_name="invalid",
                target_percentage="0.00",
                sort_order=0,
            )
        )
        session.flush()
        raise AssertionError("database constraint should reject zero percentage")

    replacement = AllocationReplaceRequest(
        expected_revision=draft["revision"],
        items=[{"asset_class_name": "Cash", "target_percentage": "100.00"}],
    )
    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(
            policy_service, "replace_draft_allocations", fail_after_delete
        )
        with pytest.raises(IntegrityError):
            policy_service.replace_allocations(db_session, replacement)

    restored = policy_service.read_current_draft(db_session)
    assert str(restored[0].id) == draft_id
    assert restored[0].revision == draft["revision"]
    assert allocation_content(
        [
            {
                "asset_class_name": item.asset_class_name,
                "target_percentage": f"{item.target_percentage:.2f}",
                "sort_order": item.sort_order,
            }
            for item in restored[1]
        ]
    ) == original_content
    assert list(
        db_session.scalars(
            select(AuditEvent.action).order_by(AuditEvent.sequence_number)
        )
    ) == original_actions
    db_session.rollback()

    updated_draft, updated_allocations = policy_service.replace_allocations(
        db_session, replacement
    )
    assert updated_draft.revision == draft["revision"] + 1
    assert [item.target_percentage for item in updated_allocations] == [100]


def test_unrelated_integrity_error_propagates_rolls_back_and_session_is_reusable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(HouseholdProfile(**HOUSEHOLD))
    db_session.commit()
    real_add = policy_service.add_policy_audit_event

    def add_invalid_unrelated_row(session: Session, **_kwargs):
        session.add(
            InvestmentPolicyDraftAllocation(
                draft_id=uuid4(),
                asset_class_name="secret-marker",
                normalized_asset_class_name="secret-marker",
                target_percentage="10.00",
                sort_order=0,
            )
        )
        session.flush()

    with monkeypatch.context() as scoped_patch:
        scoped_patch.setattr(
            policy_service, "add_policy_audit_event", add_invalid_unrelated_row
        )
        with pytest.raises(IntegrityError) as exc_info:
            policy_service.create_policy(db_session)
        assert policy_service._constraint_name(exc_info.value) != (
            "uq_investment_policies_household_id"
        )

    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicy)) == 0
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyDraft)) == 0
    db_session.rollback()
    monkeypatch.setattr(policy_service, "add_policy_audit_event", real_add)
    policy, draft, allocations = policy_service.create_policy(db_session)
    assert policy.id and draft.id and allocations == []


def test_unrelated_integrity_error_returns_redacted_generic_500(
    api_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_household(api_client)

    def add_invalid_unrelated_row(session: Session, **_kwargs):
        session.add(
            InvestmentPolicyDraftAllocation(
                draft_id=uuid4(),
                asset_class_name="secret-marker",
                normalized_asset_class_name="secret-marker",
                target_percentage="10.00",
                sort_order=0,
            )
        )
        session.flush()

    monkeypatch.setattr(
        policy_service, "add_policy_audit_event", add_invalid_unrelated_row
    )
    with TestClient(app, raise_server_exceptions=False) as redacted_client:
        response = redacted_client.post("/api/policies")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    assert "secret-marker" not in response.text
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicy)) == 0
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyDraft)) == 0


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


def test_concurrent_new_draft_creation_has_one_winner(
    api_client: TestClient, postgres_engine
) -> None:
    create_household(api_client)
    create_policy(api_client)
    published = publish(api_client, prepare_draft(api_client)["revision"])
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    start = Barrier(2)

    def attempt() -> str:
        with factory() as session:
            start.wait()
            try:
                policy_service.create_new_draft(
                    session,
                    CreatePolicyDraftRequest(source_version_id=published["id"]),
                )
                return "created"
            except policy_service.DraftAlreadyExistsError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _index: attempt(), range(2)))
    assert outcomes == ["conflict", "created"]
    with Session(postgres_engine) as session:
        assert policy_state_counts(session)["drafts"] == 1
        assert policy_state_counts(session)["draft_allocations"] == 2
        actions = list(session.scalars(select(AuditEvent.action)))
        assert actions.count("policy.draft.created") == 2


def test_discard_and_new_draft_race_is_linearizable(
    api_client: TestClient, postgres_engine
) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    start = Barrier(2)

    def discard_attempt() -> str:
        with factory() as session:
            start.wait()
            policy_service.discard_draft(session, draft["revision"])
            return "discarded"

    def create_attempt() -> str:
        with factory() as session:
            start.wait()
            try:
                policy_service.create_new_draft(session, CreatePolicyDraftRequest())
                return "created"
            except policy_service.DraftAlreadyExistsError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(discard_attempt), executor.submit(create_attempt)]
        outcomes = sorted(future.result() for future in futures)
    assert outcomes in (["conflict", "discarded"], ["created", "discarded"])
    with Session(postgres_engine) as session:
        counts = policy_state_counts(session)
        assert counts["drafts"] in (0, 1)
        assert counts["draft_allocations"] == 0
        actions = list(session.scalars(select(AuditEvent.action)))
        assert actions.count("policy.draft.discarded") == 1
        assert actions.count("policy.draft.created") == 1 + counts["drafts"]


def test_publish_and_new_draft_race_is_linearizable(
    api_client: TestClient, postgres_engine
) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    start = Barrier(2)

    def publish_attempt() -> str:
        with factory() as session:
            start.wait()
            policy_service.publish_draft(
                session,
                PublishPolicyDraftRequest(
                    expected_revision=draft["revision"], confirmation=True
                ),
            )
            return "published"

    def create_attempt() -> str:
        with factory() as session:
            start.wait()
            try:
                policy_service.create_new_draft(session, CreatePolicyDraftRequest())
                return "created"
            except policy_service.DraftAlreadyExistsError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(publish_attempt), executor.submit(create_attempt)]
        outcomes = sorted(future.result() for future in futures)
    assert outcomes in (["conflict", "published"], ["created", "published"])
    with Session(postgres_engine) as session:
        counts = policy_state_counts(session)
        assert counts["versions"] == 1
        assert counts["version_allocations"] == 2
        assert counts["drafts"] in (0, 1)
        assert counts["draft_allocations"] == 0
        assert session.scalar(
            select(func.count())
            .select_from(InvestmentPolicyVersion)
            .where(InvestmentPolicyVersion.status == "published")
        ) == 1
        actions = list(session.scalars(select(AuditEvent.action)))
        assert actions.count("policy.published") == 1
        assert actions.count("policy.draft.created") == 1 + counts["drafts"]


def test_patch_response_uses_precommit_snapshot_and_never_queries_after_commit(
    api_client: TestClient, postgres_engine
) -> None:
    create_household(api_client)
    create_policy(api_client)
    draft = prepare_draft(api_client)
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    commit_reached = Event()
    release_return = Event()
    post_commit_selects: list[str] = []

    with factory() as patch_session:
        def hold_after_commit(_session: Session) -> None:
            commit_reached.set()
            assert release_return.wait(timeout=10)

        def record_post_commit_select(orm_execute_state) -> None:
            if commit_reached.is_set() and orm_execute_state.is_select:
                post_commit_selects.append(str(orm_execute_state.statement))

        event.listen(patch_session, "after_commit", hold_after_commit)
        event.listen(patch_session, "do_orm_execute", record_post_commit_select)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    policy_service.update_draft_text,
                    patch_session,
                    PolicyDraftUpdate(
                        expected_revision=draft["revision"], notes="patched snapshot"
                    ),
                )
                assert commit_reached.wait(timeout=10)
                with factory() as concurrent_session:
                    concurrent_draft, _ = policy_service.replace_allocations(
                        concurrent_session,
                        AllocationReplaceRequest(
                            expected_revision=draft["revision"] + 1,
                            items=[
                                {
                                    "asset_class_name": "Cash",
                                    "target_percentage": "100.00",
                                }
                            ],
                        ),
                    )
                    assert concurrent_draft.revision == draft["revision"] + 2
                release_return.set()
                snapshot = future.result(timeout=10)
        finally:
            release_return.set()
            event.remove(patch_session, "after_commit", hold_after_commit)
            event.remove(patch_session, "do_orm_execute", record_post_commit_select)

    assert snapshot.revision == draft["revision"] + 1
    assert snapshot.notes == "patched snapshot"
    assert allocation_content(
        [allocation.model_dump(mode="json") for allocation in snapshot.allocations]
    ) == allocation_content(draft["allocations"])
    assert post_commit_selects == []
    assert api_client.get("/api/policies/current/draft").json()["revision"] == (
        draft["revision"] + 2
    )


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
        assert allocation_content(published.json()["allocations"]) == allocation_content(
            draft["allocations"]
        )
    else:
        current_draft = api_client.get("/api/policies/current/draft").json()
        assert current_draft["allocations"][0]["target_percentage"] == "100.00"
