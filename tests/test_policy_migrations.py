from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.reflection import Inspector

from tests.conftest import postgres_test_database_url

HEAD_REVISION = "0029_perspective_analyses"
SLICE_2_REVISION = "0002_investment_policy_foundation"
SLICE_1_REVISION = "0001_household_persistence"


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def column_names(inspector: Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


@pytest.mark.postgres
def test_fresh_incremental_downgrade_and_reupgrade_preserve_slice_1_data(
    postgres_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = postgres_test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", database_url)

    postgres_engine.dispose()
    migration_engine = create_engine(database_url, pool_pre_ping=True)
    household_id = uuid4()
    event_id = uuid4()

    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION
        version_column = next(
            column
            for column in inspect(migration_engine).get_columns("alembic_version")
            if column["name"] == "version_num"
        )
        assert version_column["type"].length >= len(HEAD_REVISION)
        fresh_tables = set(inspect(migration_engine).get_table_names())
        assert {
            "audit_events",
            "household_profiles",
            "investment_policies",
            "investment_policy_drafts",
            "investment_policy_draft_allocations",
            "investment_policy_versions",
            "investment_policy_version_allocations",
        } <= fresh_tables

        command.downgrade(alembic_config, SLICE_1_REVISION)
        assert current_revision(migration_engine) == SLICE_1_REVISION
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO household_profiles "
                    "(id, singleton_key, household_name, base_currency, investment_horizon, "
                    "liquidity_needs, risk_statement, notes) "
                    "VALUES (:id, true, 'Migration Household', 'USD', '', '', '', '')"
                ),
                {"id": household_id},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                    "VALUES (:id, :household_id, 'local-owner', 'household.created', "
                    "'HouseholdProfile', :household_id, CAST('{}' AS jsonb))"
                ),
                {"id": event_id, "household_id": household_id},
            )

        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION
        upgraded_inspector = inspect(migration_engine)
        sequence_column = next(
            column
            for column in upgraded_inspector.get_columns("audit_events")
            if column["name"] == "sequence_number"
        )
        assert sequence_column["nullable"] is False
        assert sequence_column["identity"] is not None
        with migration_engine.begin() as connection:
            preserved = connection.execute(
                text(
                    "SELECT household_id, sequence_number FROM audit_events WHERE id = :id"
                ),
                {"id": event_id},
            ).one()
            assert preserved.household_id == household_id
            assert preserved.sequence_number is not None
            next_event_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, household_id, actor, action, entity_type, entity_id, metadata) "
                    "VALUES (:id, :household_id, 'local-owner', 'household.updated', "
                    "'HouseholdProfile', :household_id, CAST('{}' AS jsonb))"
                ),
                {"id": next_event_id, "household_id": household_id},
            )
            next_sequence = connection.scalar(
                text("SELECT sequence_number FROM audit_events WHERE id = :id"),
                {"id": next_event_id},
            )
            assert next_sequence is not None
            assert next_sequence > preserved.sequence_number

        command.downgrade(alembic_config, SLICE_1_REVISION)
        assert current_revision(migration_engine) == SLICE_1_REVISION
        slice_1_inspector = inspect(migration_engine)
        assert "sequence_number" not in column_names(slice_1_inspector, "audit_events")
        assert not {
            "investment_policies",
            "investment_policy_drafts",
            "investment_policy_draft_allocations",
            "investment_policy_versions",
            "investment_policy_version_allocations",
        } & set(slice_1_inspector.get_table_names())
        with migration_engine.connect() as connection:
            assert connection.scalar(
                text("SELECT count(*) FROM household_profiles WHERE id = :id"),
                {"id": household_id},
            ) == 1
            assert connection.scalar(
                text("SELECT count(*) FROM audit_events WHERE id = :id"),
                {"id": event_id},
            ) == 1

        command.upgrade(alembic_config, "head")
        assert current_revision(migration_engine) == HEAD_REVISION
    finally:
        command.upgrade(alembic_config, "head")
        migration_engine.dispose()


def test_application_never_calls_create_all() -> None:
    application_files = sorted(Path("apps").rglob("*.py"))
    offenders = [
        str(path)
        for path in application_files
        if ".create_all(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
