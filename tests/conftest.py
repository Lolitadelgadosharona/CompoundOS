from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.database import get_session
from apps.api.main import app


def postgres_test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if database_url:
        return database_url
    if os.environ.get("COMPOUNDOS_REQUIRE_POSTGRES_TESTS") == "1":
        pytest.fail(
            "CompoundOS CI requires real PostgreSQL tests, but TEST_DATABASE_URL is missing"
        )
    pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")


@pytest.fixture(scope="session")
def postgres_engine() -> Engine:
    database_url = postgres_test_database_url()
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def db_session(postgres_engine: Engine) -> Generator[Session, None, None]:
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE decision_corrections, decision_confirmed_snapshots,"
                " decision_drafts, decisions, audit_events,"
                " investment_policy_version_allocations,"
                " investment_policy_draft_allocations,"
                " investment_policy_versions, investment_policy_drafts,"
                " investment_policies, household_profiles"
                " RESTART IDENTITY CASCADE"
            )
        )
    session_factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    with session_factory() as session:
        yield session


@pytest.fixture()
def api_client(postgres_engine: Engine) -> Generator[TestClient, None, None]:
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE decision_corrections, decision_confirmed_snapshots,"
                " decision_drafts, decisions, audit_events,"
                " investment_policy_version_allocations,"
                " investment_policy_draft_allocations,"
                " investment_policy_versions, investment_policy_drafts,"
                " investment_policies, household_profiles"
                " RESTART IDENTITY CASCADE"
            )
        )
    session_factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
