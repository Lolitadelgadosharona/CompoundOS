from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# If TEST_DATABASE_URL is set, ensure DATABASE_URL also points there
# so SessionLocal (in apps.api.database) uses the test database
# for independent-session assertions. Must happen BEFORE importing
# apps.api.database, which creates its engine at import time.
_test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
if _test_url:
    os.environ.setdefault("DATABASE_URL", _test_url)

from apps.api.database import get_session  # noqa: E402
from apps.api.main import app  # noqa: E402


def postgres_test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not database_url:
        if os.environ.get("COMPOUNDOS_REQUIRE_POSTGRES_TESTS") == "1":
            pytest.fail(
                "CompoundOS CI requires real PostgreSQL tests,"
                " but TEST_DATABASE_URL is missing"
            )
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    # Safety: database name must end with _test
    db_name = _extract_db_name(database_url)
    if not db_name.endswith("_test"):
        pytest.fail(
            f"TEST_DATABASE_URL points to database '{db_name}',"
            " which does not end with '_test'."
            " Destructive tests must never run against a non-test database."
        )
    return database_url


def _extract_db_name(url: str) -> str:
    """Extract database name from a SQLAlchemy database URL."""
    # Format: postgresql+psycopg://user:pass@host:port/dbname
    return url.rsplit("/", 1)[-1].split("?")[0]


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
    # Ensure schema is at latest revision before truncating
    from alembic.config import Config as _AlembicConfig
    from alembic import command as _alembic_command
    _cfg = _AlembicConfig()
    _cfg.set_main_option("script_location", "migrations")
    _cfg.attributes["connection"] = postgres_engine
    try:
        _alembic_command.upgrade(_cfg, "head")
    except Exception:
        pass
    with postgres_engine.begin() as connection:
        try:
            connection.execute(
                text(
                    "TRUNCATE TABLE portfolio_snapshot_holdings, portfolio_snapshots,"
                    " portfolio_draft_holdings, portfolio_drafts,"
                    " accounts, portfolios,"
                    " decision_corrections, decision_confirmed_snapshots,"
                    " decision_drafts, decisions, audit_events,"
                    " investment_policy_version_allocations,"
                    " investment_policy_draft_allocations,"
                    " investment_policy_versions, investment_policy_drafts,"
                    " investment_policies,"
                    " guardian_events, guardian_evaluation_runs,"
                    " guardian_check_confirmed, guardian_check_drafts,"
                    " guardian_checks,"
                    " leases, attempts, runs, schedules, job_definitions,"
                    " household_profiles"
                    " RESTART IDENTITY CASCADE"
                )
            )
        except Exception:
            pass
    session_factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    with session_factory() as session:
        yield session


@pytest.fixture()
def api_client(postgres_engine: Engine) -> Generator[TestClient, None, None]:
    with postgres_engine.begin() as connection:
        try:
            connection.execute(
                text(
                    "TRUNCATE TABLE portfolio_snapshot_holdings, portfolio_snapshots,"
                    " portfolio_draft_holdings, portfolio_drafts,"
                    " accounts, portfolios,"
                    " decision_corrections, decision_confirmed_snapshots,"
                    " decision_drafts, decisions, audit_events,"
                    " investment_policy_version_allocations,"
                    " investment_policy_draft_allocations,"
                    " investment_policy_versions, investment_policy_drafts,"
                    " investment_policies,"
                    " guardian_events, guardian_evaluation_runs,"
                    " guardian_check_confirmed, guardian_check_drafts,"
                    " guardian_checks,"
                    " leases, attempts, runs, schedules, job_definitions,"
                    " household_profiles"
                    " RESTART IDENTITY CASCADE"
                )
            )
        except Exception:
            pass
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
