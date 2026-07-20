from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# ── Force DATABASE_URL to match TEST_DATABASE_URL before any import ──
# SessionLocal in apps.api.database creates its engine at import time;
# we must redirect it BEFORE the import.
_test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
if _test_url:
    os.environ["DATABASE_URL"] = _test_url

from apps.api.database import get_session  # noqa: E402
from apps.api.main import app  # noqa: E402

# ═══════════════════════════════════════════════════════════════════════════
# Safety: database name enforcement
# ═══════════════════════════════════════════════════════════════════════════


def postgres_test_database_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not database_url:
        if os.environ.get("COMPOUNDOS_REQUIRE_POSTGRES_TESTS") == "1":
            pytest.fail(
                "CompoundOS CI requires real PostgreSQL tests,"
                " but TEST_DATABASE_URL is missing"
            )
        pytest.skip(
            "TEST_DATABASE_URL is required for PostgreSQL integration tests"
        )
    db_name = database_url.rsplit("/", 1)[-1].split("?")[0]
    if not db_name.endswith("_test"):
        pytest.fail(
            f"TEST_DATABASE_URL points to database '{db_name}',"
            " which does not end with '_test'."
            " Destructive tests must never run against a non-test database."
        )
    return database_url


# ═══════════════════════════════════════════════════════════════════════════
# Table discovery — auto-detect existing application tables
# ═══════════════════════════════════════════════════════════════════════════

_SYSTEM_TABLES = frozenset({"alembic_version", "spatial_ref_sys"})


def _application_table_names(engine: Engine) -> list[str]:
    """Return names of all application tables currently in the database."""
    inspector = inspect(engine)
    return sorted(
        t for t in inspector.get_table_names()
        if t not in _SYSTEM_TABLES
    )


def _truncate_all_tables(engine: Engine) -> None:
    """TRUNCATE all application tables that currently exist."""
    tables = _application_table_names(engine)
    if not tables:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                + ", ".join(tables)
                + " RESTART IDENTITY CASCADE"
            )
        )


def _ensure_schema_at_head(engine: Engine) -> None:
    """Idempotently upgrade schema to the latest head revision."""
    from alembic import command as _alembic_command
    from alembic.config import Config as _AlembicConfig
    cfg = _AlembicConfig()
    cfg.set_main_option("script_location", "migrations")
    cfg.attributes["connection"] = engine
    _alembic_command.upgrade(cfg, "head")


# ═══════════════════════════════════════════════════════════════════════════
# Isolation counter — verification that cleanup runs exactly once per test
# ═══════════════════════════════════════════════════════════════════════════

_isolation_call_count: dict[str, int] = {}


def _bump_isolation_counter(test_nodeid: str) -> int:
    key = test_nodeid
    _isolation_call_count[key] = _isolation_call_count.get(key, 0) + 1
    return _isolation_call_count[key]


def reset_isolation_counter() -> None:
    _isolation_call_count.clear()


def get_isolation_counter() -> dict[str, int]:
    return dict(_isolation_call_count)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine, None, None]:
    database_url = postgres_test_database_url()
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC"},
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def postgres_test_isolation(
    postgres_engine: Engine, request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Function-scoped: schema head + TRUNCATE — exactly once per test.

    Both db_session and api_client depend on this fixture.  When a single
    test requests both, pytest runs this fixture exactly once — no double
    TRUNCATE.  Only active for postgres-marked tests.
    """
    _ensure_schema_at_head(postgres_engine)
    _truncate_all_tables(postgres_engine)
    _bump_isolation_counter(request.node.nodeid)
    yield


@pytest.fixture()
def db_session(
    postgres_test_isolation: None,
    postgres_engine: Engine,
) -> Generator[Session, None, None]:
    """Function-scoped clean database session.

    Relies on postgres_test_isolation for schema-head + TRUNCATE.
    """
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture()
def api_client(
    postgres_test_isolation: None,
    postgres_engine: Engine,
) -> Generator[TestClient, None, None]:
    """Function-scoped TestClient with clean database.

    Relies on postgres_test_isolation for schema-head + TRUNCATE.
    """
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
