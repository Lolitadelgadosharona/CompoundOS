"""Sprint 005 Corrective — Test 8 deterministic retry-exhaustion unit tests.

No PostgreSQL required. Monkeypatches _reconcile_attempt.
Run: pytest -q tests/test_retry_exhaustion.py
"""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import DBAPIError

from apps.api.services.orchestration_worker import (
    ReconciliationResult,
    reconcile_after_child_exit,
)

# ============================================================================
# Helpers
# ============================================================================


def _make_40P01() -> DBAPIError:
    orig = type("FakePgError", (), {"pgcode": "40P01", "sqlstate": "40P01"})()
    return DBAPIError("deadlock detected", None, orig)


def _make_non_40P01() -> DBAPIError:
    orig = type("FakePgError", (), {"pgcode": "42601", "sqlstate": "42601"})()
    return DBAPIError("syntax error", None, orig)


# ============================================================================
# Test 8a — Three consecutive 40P01 → reconciliation_deferred
# ============================================================================


class Test40P01ExhaustsRetries:
    def test_three_40P01_returns_deferred(self, monkeypatch) -> None:
        session = MagicMock()
        calls = []

        def fake_reconcile(*args, **kwargs):
            calls.append(1)
            raise _make_40P01()

        monkeypatch.setattr(
            "apps.api.services.orchestration_worker._reconcile_attempt",
            fake_reconcile,
        )

        result = reconcile_after_child_exit(
            session, "rid", "aid", "lid", "wid", 1, max_retries=3,
        )

        assert len(calls) == 3, f"Expected 3 calls, got {len(calls)}"
        assert session.rollback.call_count == 3, (
            f"Expected 3 rollbacks, got {session.rollback.call_count}"
        )
        assert result.outcome == "reconciliation_deferred"
        assert "40P01" in result.message
        assert "3" in result.message

    def test_fourth_attempt_not_called(self, monkeypatch) -> None:
        """Verify no call beyond max_retries=3."""
        session = MagicMock()
        calls = []

        def fake_reconcile(*args, **kwargs):
            calls.append(1)
            raise _make_40P01()

        monkeypatch.setattr(
            "apps.api.services.orchestration_worker._reconcile_attempt",
            fake_reconcile,
        )

        reconcile_after_child_exit(
            session, "rid", "aid", "lid", "wid", 1, max_retries=3,
        )
        assert len(calls) == 3, "No fourth call allowed"


# ============================================================================
# Test 8b — Two failures then success
# ============================================================================


class TestTwo40P01ThenSuccess:
    def test_succeeds_after_two_failures(self, monkeypatch) -> None:
        session = MagicMock()
        call_count = [0]

        def fake_two_then_ok(s, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise _make_40P01()
            return ReconciliationResult(
                "parent_finalized", run_status="completed",
                attempt_status="succeeded",
            )

        monkeypatch.setattr(
            "apps.api.services.orchestration_worker._reconcile_attempt",
            fake_two_then_ok,
        )

        result = reconcile_after_child_exit(
            session, "rid", "aid", "lid", "wid", 1, max_retries=3,
        )

        assert call_count[0] == 3
        assert session.rollback.call_count == 2, (
            f"Expected 2 rollbacks, got {session.rollback.call_count}"
        )
        assert result.outcome == "parent_finalized"
        assert result.run_status == "completed"
        assert result.attempt_status == "succeeded"


# ============================================================================
# Test 8c — Non-40P01 DBAPIError re-raised
# ============================================================================


class TestNon40P01ReRaised:
    def test_non_40P01_raises(self, monkeypatch) -> None:
        session = MagicMock()

        def fake_raise(*args, **kwargs):
            raise _make_non_40P01()

        monkeypatch.setattr(
            "apps.api.services.orchestration_worker._reconcile_attempt",
            fake_raise,
        )

        with pytest.raises(DBAPIError):
            reconcile_after_child_exit(
                session, "rid", "aid", "lid", "wid", 1, max_retries=3,
            )

        assert session.rollback.call_count == 1
