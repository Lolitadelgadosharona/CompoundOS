"""Non-PostgreSQL tests for Decision Journal Pydantic schemas and HTTP contracts."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from apps.api.decision_schemas import (
    AppendCorrectionRequest,
    ArchiveDecisionRequest,
    ConfirmDecisionRequest,
    CreateDecisionRequest,
    DiscardDecisionRequest,
    UpdateDecisionDraftRequest,
)

# ---------------------------------------------------------------------------
# Create Decision Request
# ---------------------------------------------------------------------------


class TestCreateDecisionRequest:
    def test_valid_title(self) -> None:
        req = CreateDecisionRequest(title="Buy bonds")
        assert req.title == "Buy bonds"

    def test_title_too_long(self) -> None:
        with pytest.raises(ValidationError):
            CreateDecisionRequest(title="x" * 501)

    def test_blank_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreateDecisionRequest(title="   ")

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CreateDecisionRequest(title="ok", extra_field="bad")

    def test_title_trimmed(self) -> None:
        req = CreateDecisionRequest(title="  Trimmed  ")
        assert req.title == "Trimmed"


# ---------------------------------------------------------------------------
# Update Decision Draft Request
# ---------------------------------------------------------------------------


class TestUpdateDecisionDraftRequest:
    def test_minimal_update(self) -> None:
        req = UpdateDecisionDraftRequest(
            expected_revision=1, title="Updated"
        )
        assert req.expected_revision == 1
        assert req.title == "Updated"

    def test_stale_revision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateDecisionDraftRequest(expected_revision=0, title="bad")

    def test_no_changes(self) -> None:
        req = UpdateDecisionDraftRequest(expected_revision=1)
        assert req.title is None

    def test_decision_date_validation_today_allowed(self) -> None:
        req = UpdateDecisionDraftRequest(
            expected_revision=1, decision_date=date.today()
        )
        assert req.decision_date == date.today()

    def test_decision_date_validation_yesterday_allowed(self) -> None:
        yesterday = date.today() - timedelta(days=1)
        req = UpdateDecisionDraftRequest(
            expected_revision=1, decision_date=yesterday
        )
        assert req.decision_date == yesterday

    def test_decision_date_validation_future_rejected(self) -> None:
        future = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError):
            UpdateDecisionDraftRequest(
                expected_revision=1, decision_date=future
            )

    def test_review_date_future_allowed(self) -> None:
        future = date.today() + timedelta(days=30)
        req = UpdateDecisionDraftRequest(
            expected_revision=1, review_date=future
        )
        assert req.review_date == future

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UpdateDecisionDraftRequest(
                expected_revision=1, unknown_field="bad"
            )

    def test_all_text_fields(self) -> None:
        req = UpdateDecisionDraftRequest(
            expected_revision=1,
            title="t",
            decision_summary="s",
            rationale="r",
            alternatives_considered="a",
            risks_and_uncertainties="ru",
            evidence_or_sources="e",
            expected_outcome="o",
            review_trigger="rt",
            notes="n",
        )
        assert req.title == "t"
        assert req.notes == "n"


# ---------------------------------------------------------------------------
# Confirm Decision Request
# ---------------------------------------------------------------------------


class TestConfirmDecisionRequest:
    def test_valid_confirm(self) -> None:
        req = ConfirmDecisionRequest(expected_revision=1, confirmation=True)
        assert req.confirmation is True

    def test_confirmation_false_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConfirmDecisionRequest(expected_revision=1, confirmation=False)

    def test_missing_confirmation_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ConfirmDecisionRequest(expected_revision=1)


# ---------------------------------------------------------------------------
# Discard Decision Request
# ---------------------------------------------------------------------------


class TestDiscardDecisionRequest:
    def test_valid_discard(self) -> None:
        req = DiscardDecisionRequest(expected_revision=3)
        assert req.expected_revision == 3

    def test_zero_revision_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DiscardDecisionRequest(expected_revision=0)


# ---------------------------------------------------------------------------
# Archive Decision Request
# ---------------------------------------------------------------------------


class TestArchiveDecisionRequest:
    def test_empty_archive(self) -> None:
        req = ArchiveDecisionRequest()
        assert req.archive_reason is None

    def test_with_reason(self) -> None:
        req = ArchiveDecisionRequest(archive_reason="Outdated")
        assert req.archive_reason == "Outdated"

    def test_reason_too_long(self) -> None:
        with pytest.raises(ValidationError):
            ArchiveDecisionRequest(archive_reason="x" * 4001)


# ---------------------------------------------------------------------------
# Append Correction Request
# ---------------------------------------------------------------------------


class TestAppendCorrectionRequest:
    def _base_values(self, **overrides):
        values = {
            "correction_reason": "Typo fix",
            "title": "Corrected title",
            "decision_summary": "Corrected summary",
            "rationale": "Corrected rationale",
            "decision_date": date.today(),
        }
        values.update(overrides)
        return values

    def test_valid_correction(self) -> None:
        req = AppendCorrectionRequest(**self._base_values())
        assert req.correction_reason == "Typo fix"
        assert req.decision_date == date.today()

    def test_future_date_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AppendCorrectionRequest(
                **self._base_values(decision_date=date.today() + timedelta(days=1))
            )

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            AppendCorrectionRequest(correction_reason="r")

    def test_blank_correction_reason_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AppendCorrectionRequest(
                **self._base_values(correction_reason="")
            )

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AppendCorrectionRequest(
                **self._base_values(), extra="bad"
            )
