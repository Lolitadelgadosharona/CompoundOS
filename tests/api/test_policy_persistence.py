from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from apps.api.models import (
    AuditEvent,
    HouseholdProfile,
    InvestmentPolicy,
    InvestmentPolicyDraft,
    InvestmentPolicyDraftAllocation,
    InvestmentPolicyVersion,
    InvestmentPolicyVersionAllocation,
)

pytestmark = pytest.mark.postgres

HOUSEHOLD_VALUES = {
    "household_name": "Persistence Test Household",
    "base_currency": "USD",
    "investment_horizon": "",
    "liquidity_needs": "",
    "risk_statement": "",
    "notes": "",
}

POLICY_TEXT = {
    "objectives": "Preserve the owner's stated objectives.",
    "time_horizon": "Long term",
    "liquidity": "",
    "diversification": "",
    "contribution_policy": "",
    "rebalancing_policy": "",
    "prohibited_assets": "",
    "leverage_policy": "",
    "decision_process": "Document decisions before acting.",
    "notes": "",
}

POLICY_TABLES = {
    "investment_policies",
    "investment_policy_drafts",
    "investment_policy_draft_allocations",
    "investment_policy_versions",
    "investment_policy_version_allocations",
}

EXPECTED_FUNCTIONS = {
    "fn_investment_policy_version_immutability",
    "fn_investment_policy_version_allocation_immutability",
    "fn_investment_policy_version_require_sealed",
}

EXPECTED_TRIGGERS = {
    "trg_investment_policy_version_immutability",
    "trg_investment_policy_version_allocation_immutability",
    "trg_investment_policy_version_sealed_at_commit",
}

EXPECTED_CHECKS = {
    "investment_policy_drafts": {
        "ck_investment_policy_drafts_revision_positive",
        *(f"ck_investment_policy_drafts_{name}_length" for name in POLICY_TEXT),
    },
    "investment_policy_draft_allocations": {
        "ck_investment_policy_draft_allocations_name_length",
        "ck_investment_policy_draft_allocations_normalized_name_length",
        "ck_investment_policy_draft_allocations_percentage_range",
        "ck_investment_policy_draft_allocations_sort_order_nonnegative",
    },
    "investment_policy_versions": {
        "ck_investment_policy_versions_version_number_positive",
        "ck_investment_policy_versions_status",
        "ck_investment_policy_versions_status_timestamps",
        *(f"ck_investment_policy_versions_{name}_length" for name in POLICY_TEXT),
    },
    "investment_policy_version_allocations": {
        "ck_investment_policy_version_allocations_name_length",
        "ck_investment_policy_version_allocations_normalized_name_length",
        "ck_investment_policy_version_allocations_percentage_range",
        "ck_investment_policy_version_allocations_sort_order_nonnegative",
    },
}

EXPECTED_FOREIGN_KEYS = {
    "investment_policies": {
        "fk_investment_policies_household_id_household_profiles",
    },
    "investment_policy_drafts": {
        "fk_investment_policy_drafts_policy_id_investment_policies",
        "fk_investment_policy_drafts_source_version_id_versions",
    },
    "investment_policy_draft_allocations": {
        "fk_policy_draft_allocations_draft_id_policy_drafts",
    },
    "investment_policy_versions": {
        "fk_investment_policy_versions_policy_id_investment_policies",
    },
    "investment_policy_version_allocations": {
        "fk_policy_version_allocations_version_id_policy_versions",
    },
}


def create_household_and_policy(session: Session) -> tuple[HouseholdProfile, InvestmentPolicy]:
    household = HouseholdProfile(**HOUSEHOLD_VALUES)
    session.add(household)
    session.flush()
    policy = InvestmentPolicy(household_id=household.id)
    session.add(policy)
    session.commit()
    return household, policy


def new_version(policy_id: UUID, version_number: int = 1) -> InvestmentPolicyVersion:
    return InvestmentPolicyVersion(
        policy_id=policy_id,
        version_number=version_number,
        status="published",
        published_at=datetime.now(timezone.utc),
        **POLICY_TEXT,
    )


def add_version_allocation(
    session: Session,
    version: InvestmentPolicyVersion,
    *,
    name: str = "Global Equity",
    normalized_name: str = "global equity",
    percentage: Decimal = Decimal("100.00"),
    sort_order: int = 0,
) -> InvestmentPolicyVersionAllocation:
    allocation = InvestmentPolicyVersionAllocation(
        version_id=version.id,
        asset_class_name=name,
        normalized_asset_class_name=normalized_name,
        target_percentage=percentage,
        sort_order=sort_order,
    )
    session.add(allocation)
    session.flush()
    return allocation


def persist_sealed_version(
    session: Session,
    policy_id: UUID,
    version_number: int = 1,
) -> tuple[InvestmentPolicyVersion, InvestmentPolicyVersionAllocation]:
    version = new_version(policy_id, version_number)
    session.add(version)
    session.flush()
    allocation = add_version_allocation(session, version)
    version.sealed_at = datetime.now(timezone.utc)
    session.commit()
    return version, allocation


def assert_database_error(
    session: Session,
    expected_identifier: str,
    operation,
) -> None:
    with pytest.raises(DBAPIError) as exc_info:
        operation()
    assert expected_identifier in str(exc_info.value.orig)
    session.rollback()


def test_policy_schema_installs_named_constraints_indexes_functions_and_triggers(
    postgres_engine,
) -> None:
    inspector = inspect(postgres_engine)
    assert POLICY_TABLES <= set(inspector.get_table_names())

    policy_uniques = {
        item["name"] for item in inspector.get_unique_constraints("investment_policies")
    }
    draft_uniques = {
        item["name"]
        for item in inspector.get_unique_constraints("investment_policy_drafts")
    }
    version_uniques = {
        item["name"]
        for item in inspector.get_unique_constraints("investment_policy_versions")
    }
    version_indexes = {
        item["name"]: item for item in inspector.get_indexes("investment_policy_versions")
    }
    assert "uq_investment_policies_household_id" in policy_uniques
    assert "uq_investment_policy_drafts_policy_id" in draft_uniques
    assert "uq_investment_policy_versions_policy_version" in version_uniques
    assert version_indexes["uq_investment_policy_versions_current_published"]["unique"]
    assert "ix_investment_policy_versions_policy_history" in version_indexes

    for table_name, expected_names in EXPECTED_CHECKS.items():
        installed_names = {
            item["name"] for item in inspector.get_check_constraints(table_name)
        }
        assert expected_names <= installed_names
        assert None not in installed_names

    for table_name, expected_names in EXPECTED_FOREIGN_KEYS.items():
        installed_names = {
            item["name"] for item in inspector.get_foreign_keys(table_name)
        }
        assert expected_names <= installed_names
        assert None not in installed_names

    audit_uniques = {
        item["name"] for item in inspector.get_unique_constraints("audit_events")
    }
    assert "uq_audit_events_sequence_number" in audit_uniques

    with postgres_engine.connect() as connection:
        functions = set(
            connection.scalars(
                text(
                    "SELECT proname FROM pg_proc "
                    "WHERE proname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_FUNCTIONS)},
            )
        )
        triggers = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_trigger "
                    "WHERE NOT tgisinternal AND tgname = ANY(CAST(:names AS text[]))"
                ),
                {"names": sorted(EXPECTED_TRIGGERS)},
            )
        )
    assert functions == EXPECTED_FUNCTIONS
    assert triggers == EXPECTED_TRIGGERS


def test_policy_and_draft_cardinality_constraints(db_session: Session) -> None:
    household, policy = create_household_and_policy(db_session)

    db_session.add(InvestmentPolicy(household_id=household.id))
    with pytest.raises(IntegrityError) as policy_error:
        db_session.commit()
    assert policy_error.value.orig.diag.constraint_name == "uq_investment_policies_household_id"
    db_session.rollback()

    db_session.add(InvestmentPolicyDraft(policy_id=policy.id))
    db_session.commit()
    db_session.add(InvestmentPolicyDraft(policy_id=policy.id))
    with pytest.raises(IntegrityError) as draft_error:
        db_session.commit()
    assert draft_error.value.orig.diag.constraint_name == "uq_investment_policy_drafts_policy_id"
    db_session.rollback()


def test_draft_allocation_numeric_and_normalized_name_constraints(db_session: Session) -> None:
    _, policy = create_household_and_policy(db_session)
    draft = InvestmentPolicyDraft(policy_id=policy.id)
    db_session.add(draft)
    db_session.commit()

    percentage_column = next(
        column
        for column in inspect(db_session.get_bind()).get_columns(
            "investment_policy_draft_allocations"
        )
        if column["name"] == "target_percentage"
    )
    assert percentage_column["type"].precision == 5
    assert percentage_column["type"].scale == 2

    for value in (Decimal("0.00"), Decimal("100.01")):
        db_session.add(
            InvestmentPolicyDraftAllocation(
                draft_id=draft.id,
                asset_class_name="Invalid",
                normalized_asset_class_name="invalid",
                target_percentage=value,
                sort_order=0,
            )
        )
        with pytest.raises(IntegrityError) as range_error:
            db_session.commit()
        assert (
            range_error.value.orig.diag.constraint_name
            == "ck_investment_policy_draft_allocations_percentage_range"
        )
        db_session.rollback()

    db_session.add_all(
        [
            InvestmentPolicyDraftAllocation(
                draft_id=draft.id,
                asset_class_name="Cash",
                normalized_asset_class_name="cash",
                target_percentage=Decimal("50.00"),
                sort_order=0,
            ),
            InvestmentPolicyDraftAllocation(
                draft_id=draft.id,
                asset_class_name=" CASH ",
                normalized_asset_class_name="cash",
                target_percentage=Decimal("50.00"),
                sort_order=1,
            ),
        ]
    )
    with pytest.raises(IntegrityError) as duplicate_error:
        db_session.commit()
    assert (
        duplicate_error.value.orig.diag.constraint_name
        == "uq_investment_policy_draft_allocations_normalized_name"
    )
    db_session.rollback()


def test_unsealed_version_allows_only_sealing_and_cannot_commit_or_delete(
    db_session: Session,
) -> None:
    _, policy = create_household_and_policy(db_session)
    version = new_version(policy.id)
    db_session.add(version)
    db_session.flush()
    version.notes = "forbidden edit"
    assert_database_error(
        db_session,
        "policy_version_unsealed_update_forbidden",
        db_session.flush,
    )

    version = new_version(policy.id)
    db_session.add(version)
    db_session.flush()
    db_session.delete(version)
    assert_database_error(db_session, "policy_version_delete_forbidden", db_session.flush)

    version = new_version(policy.id)
    db_session.add(version)
    assert_database_error(db_session, "policy_version_unsealed_at_commit", db_session.commit)
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyVersion)) == 0


def test_version_insert_contract_and_atomic_failure_rollback(db_session: Session) -> None:
    _, policy = create_household_and_policy(db_session)
    invalid = new_version(policy.id)
    invalid.status = "superseded"
    invalid.superseded_at = datetime.now(timezone.utc)
    db_session.add(invalid)
    assert_database_error(db_session, "policy_version_insert_invalid", db_session.flush)

    version = new_version(policy.id)
    db_session.add(version)
    db_session.flush()
    db_session.add(
        InvestmentPolicyVersionAllocation(
            version_id=version.id,
            asset_class_name="Invalid",
            normalized_asset_class_name="invalid",
            target_percentage=Decimal("0.00"),
            sort_order=0,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.scalar(select(func.count()).select_from(InvestmentPolicyVersion)) == 0
    assert (
        db_session.scalar(select(func.count()).select_from(InvestmentPolicyVersionAllocation))
        == 0
    )


def test_sealed_version_supersession_and_immutability(db_session: Session) -> None:
    _, policy = create_household_and_policy(db_session)
    version, _ = persist_sealed_version(db_session, policy.id)

    version.status = "superseded"
    version.superseded_at = datetime.now(timezone.utc)
    db_session.commit()

    version.notes = "forbidden"
    assert_database_error(
        db_session,
        "policy_version_sealed_update_forbidden",
        db_session.commit,
    )

    version = db_session.get(InvestmentPolicyVersion, version.id)
    assert version is not None
    version.status = "published"
    version.superseded_at = None
    assert_database_error(
        db_session,
        "policy_version_sealed_update_forbidden",
        db_session.commit,
    )

    version = db_session.get(InvestmentPolicyVersion, version.id)
    assert version is not None
    db_session.delete(version)
    assert_database_error(db_session, "policy_version_delete_forbidden", db_session.commit)


def test_version_allocation_is_insert_only_before_sealing(db_session: Session) -> None:
    _, policy = create_household_and_policy(db_session)
    version, allocation = persist_sealed_version(db_session, policy.id)

    allocation.asset_class_name = "Forbidden"
    assert_database_error(
        db_session,
        "policy_version_allocation_update_forbidden",
        db_session.commit,
    )

    allocation = db_session.get(InvestmentPolicyVersionAllocation, allocation.id)
    assert allocation is not None
    db_session.delete(allocation)
    assert_database_error(
        db_session,
        "policy_version_allocation_delete_forbidden",
        db_session.commit,
    )

    late = InvestmentPolicyVersionAllocation(
        version_id=version.id,
        asset_class_name="Late",
        normalized_asset_class_name="late",
        target_percentage=Decimal("1.00"),
        sort_order=1,
    )
    db_session.add(late)
    assert_database_error(
        db_session,
        "policy_version_allocation_parent_sealed",
        db_session.commit,
    )


def test_version_number_and_current_published_uniqueness(db_session: Session) -> None:
    _, policy = create_household_and_policy(db_session)
    first, _ = persist_sealed_version(db_session, policy.id)

    second = new_version(policy.id, 2)
    db_session.add(second)
    with pytest.raises(IntegrityError) as current_error:
        db_session.flush()
    assert (
        current_error.value.orig.diag.constraint_name
        == "uq_investment_policy_versions_current_published"
    )
    db_session.rollback()

    first = db_session.get(InvestmentPolicyVersion, first.id)
    assert first is not None
    first.status = "superseded"
    first.superseded_at = datetime.now(timezone.utc)
    db_session.commit()

    duplicate_number = new_version(policy.id, 1)
    db_session.add(duplicate_number)
    with pytest.raises(IntegrityError) as version_error:
        db_session.flush()
    assert (
        version_error.value.orig.diag.constraint_name
        == "uq_investment_policy_versions_policy_version"
    )
    db_session.rollback()


def add_audit_event(session: Session, household_id: UUID, action: str) -> AuditEvent:
    event = AuditEvent(
        household_id=household_id,
        actor="local-owner",
        action=action,
        entity_type="HouseholdProfile",
        entity_id=household_id,
        event_metadata={"changed_fields": []},
    )
    session.add(event)
    session.flush()
    return event


def test_audit_sequence_is_database_generated_monotonic_and_may_have_gaps(
    db_session: Session,
) -> None:
    household = HouseholdProfile(**HOUSEHOLD_VALUES)
    db_session.add(household)
    db_session.commit()

    first = add_audit_event(db_session, household.id, "test.first")
    second = add_audit_event(db_session, household.id, "test.second")
    db_session.commit()
    assert first.sequence_number < second.sequence_number

    rolled_back = add_audit_event(db_session, household.id, "test.rolled-back")
    rolled_back_sequence = rolled_back.sequence_number
    db_session.rollback()

    after_gap = add_audit_event(db_session, household.id, "test.after-gap")
    db_session.commit()
    assert second.sequence_number < rolled_back_sequence < after_gap.sequence_number
    assert after_gap.sequence_number > second.sequence_number + 1

    with pytest.raises(DBAPIError) as explicit_error:
        db_session.execute(
            text(
                "INSERT INTO audit_events "
                "(id, household_id, actor, action, entity_type, entity_id, metadata, "
                "sequence_number) VALUES "
                "(:id, :household_id, 'local-owner', 'test.explicit', "
                "'HouseholdProfile', :household_id, CAST('{}' AS jsonb), 999)"
            ),
            {"id": uuid4(), "household_id": household.id},
        )
    assert "generated always" in str(explicit_error.value.orig).lower()
    db_session.rollback()
