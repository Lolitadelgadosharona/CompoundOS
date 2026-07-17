from __future__ import annotations

import pytest

from tests.conftest import postgres_test_database_url


def test_missing_database_url_skips_outside_required_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("COMPOUNDOS_REQUIRE_POSTGRES_TESTS", raising=False)

    with pytest.raises(pytest.skip.Exception, match="TEST_DATABASE_URL is required"):
        postgres_test_database_url()


def test_missing_database_url_fails_in_required_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setenv("COMPOUNDOS_REQUIRE_POSTGRES_TESTS", "1")

    with pytest.raises(
        pytest.fail.Exception,
        match="CI requires real PostgreSQL tests",
    ):
        postgres_test_database_url()


def test_required_mode_returns_configured_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "postgresql+psycopg://test-host/compoundos_test"
    monkeypatch.setenv("TEST_DATABASE_URL", database_url)
    monkeypatch.setenv("COMPOUNDOS_REQUIRE_POSTGRES_TESTS", "1")

    assert postgres_test_database_url() == database_url
