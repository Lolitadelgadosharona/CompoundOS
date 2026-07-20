"""Tests for Sprint 006 Slice B — Provider, Validator, Orchestration."""

from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from apps.api.models import (
    CommitteeReport,
    CommitteeSession,
)
from apps.api.services.ai_provider import (
    DeepSeekProvider,
    FakeProvider,
    ProviderError,
    ProviderResponse,
    ProviderTimeoutError,
)
from apps.api.services.committee_orchestration import (
    build_privacy_preview,
    create_committee_session,
    record_outcome,
    run_committee,
)
from apps.api.services.credential_manager import (
    CredentialError,
    credential_available,
    get_api_key,
)
from apps.api.services.provider_output_validator import (
    validate_provider_output,
)

pytestmark = pytest.mark.postgres

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _create_household(db_session: Session) -> UUID:
    hid = uuid4()
    db_session.execute(text(
        "INSERT INTO household_profiles"
        " (id, household_name, base_currency, singleton_key,"
        "  investment_horizon, liquidity_needs, risk_statement, notes,"
        "  created_at, updated_at)"
        " VALUES (:id, 'Test', 'USD', true, 'Long', 'None', 'Low', '', now(), now())"
    ), {"id": str(hid)})
    db_session.commit()
    return hid


def _create_session(db_session: Session, hid: UUID) -> CommitteeSession:
    cs = create_committee_session(
        db_session, hid, "Test", "Should we increase equity exposure?",
    )
    return cs


def _valid_report() -> dict:
    return {
        "supporting_arguments": ["Strong equity returns historically"],
        "opposing_arguments": ["Current elevated valuations"],
        "risks": ["Market drawdown risk"],
        "policy_alignment": "Aligned with 70% equity target",
        "minority_opinions": ["Consider waiting for better entry"],
        "evidence_citations": [],
        "limitations": ["No market data available"],
        "recommended_direction": "conditionally_aligned",
        "sections": {
            "long_term_compounding": "Equities support long-term compounding.",
            "index_passive_investing": "Passive approach is consistent.",
            "macroeconomic_context": "Insufficient current macro evidence.",
            "risk_capital_preservation": "Moderate risk, acceptable.",
            "devils_advocate": "Valuation risk exists.",
            "policy_alignment_role": "Aligned with policy allocations.",
            "synthesis_chair": "Balanced view: aligned, but cautious.",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Provider interface + FakeProvider
# ═══════════════════════════════════════════════════════════════════════════


class TestFakeProvider:
    def test_returns_configured_response(self) -> None:
        p = FakeProvider(response_text="hello", input_tokens=10, output_tokens=20)
        resp = p.call("system", "user")
        assert resp.raw_text == "hello"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 20
        assert resp.model == "fake-model"

    def test_raises_configured_error(self) -> None:
        p = FakeProvider(raise_error=ProviderTimeoutError())
        with pytest.raises(ProviderTimeoutError):
            p.call("system", "user")

    def test_provider_name(self) -> None:
        assert FakeProvider().provider_name == "fake"


class TestDeepSeekProvider:
    def test_provider_name(self) -> None:
        assert DeepSeekProvider(api_key="test-key").provider_name == "deepseek"


# ═══════════════════════════════════════════════════════════════════════════
# Credential manager
# ═══════════════════════════════════════════════════════════════════════════


class TestCredentialManager:
    def test_env_fallback_disabled_by_default(self) -> None:
        with patch.dict("os.environ", {
            "COMPOUNDOS_DEEPSEEK_API_KEY": "test-key",
        }, clear=True):
            with pytest.raises(CredentialError):
                get_api_key("deepseek")

    def test_env_fallback_explicitly_enabled(self) -> None:
        with patch.dict("os.environ", {
            "COMPOUNDOS_ALLOW_ENV_CREDENTIALS": "1",
            "COMPOUNDOS_DEEPSEEK_API_KEY": "test-key",
        }, clear=True):
            assert get_api_key("deepseek") == "test-key"

    def test_credential_available(self) -> None:
        with patch.dict("os.environ", {
            "COMPOUNDOS_ALLOW_ENV_CREDENTIALS": "1",
            "COMPOUNDOS_DEEPSEEK_API_KEY": "test-key",
        }, clear=True):
            assert credential_available("deepseek") is True

    def test_missing_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(CredentialError):
                get_api_key("deepseek")


# ═══════════════════════════════════════════════════════════════════════════
# Output Validator
# ═══════════════════════════════════════════════════════════════════════════


class TestOutputValidator:
    def test_valid_report_passes(self) -> None:
        report = _valid_report()
        result = validate_provider_output(report, set())
        assert result.passed

    def test_missing_section_fails(self) -> None:
        report = _valid_report()
        del report["supporting_arguments"]
        result = validate_provider_output(report, set())
        assert not result.passed
        assert any("supporting_arguments" in e.field for e in result.errors)

    def test_empty_opposing_arguments_fails(self) -> None:
        report = _valid_report()
        report["opposing_arguments"] = []
        result = validate_provider_output(report, set())
        assert not result.passed

    def test_invalid_direction_fails(self) -> None:
        report = _valid_report()
        report["recommended_direction"] = "buy_more"
        result = validate_provider_output(report, set())
        assert not result.passed

    def test_citation_must_exist_in_evidence(self) -> None:
        report = _valid_report()
        report["evidence_citations"] = [{"evidence_id": "evt-nonexistent"}]
        result = validate_provider_output(report, {"evt-real"})
        assert not result.passed

    def test_citation_in_valid_set_passes(self) -> None:
        report = _valid_report()
        report["evidence_citations"] = [{"evidence_id": "evt-real"}]
        result = validate_provider_output(report, {"evt-real"})
        assert result.passed

    def test_missing_role_section_fails(self) -> None:
        report = _valid_report()
        del report["sections"]["devils_advocate"]
        result = validate_provider_output(report, set())
        assert not result.passed

    def test_forbidden_language_detected(self) -> None:
        report = _valid_report()
        report["supporting_arguments"] = ["you should buy more equity"]
        result = validate_provider_output(report, set())
        assert not result.passed

    def test_non_dict_input_fails(self) -> None:
        result = validate_provider_output("not_json", set())  # type: ignore[arg-type]
        assert not result.passed


# ═══════════════════════════════════════════════════════════════════════════
# Committee Orchestration
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestration:
    def test_create_session_defaults_to_draft(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        assert cs.status == "draft"
        assert cs.title == "Test"

    def test_build_privacy_preview(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        preview = build_privacy_preview(db_session, hid, cs)
        assert "evidence_summary" in preview
        assert "estimated_input_tokens" in preview
        assert "exceeds_budget" in preview

    def test_run_committee_with_fake_provider(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()

        valid = _valid_report()
        fake = FakeProvider(
            response_text=json.dumps(valid),
            input_tokens=100,
            output_tokens=200,
        )
        report = run_committee(db_session, cs, fake)
        assert report is not None
        assert cs.status == "completed"
        assert report.provider == "fake"
        assert report.input_tokens == 100

    def test_run_requires_queued_status(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        with pytest.raises(ValueError, match="queued"):
            run_committee(db_session, cs, FakeProvider())

    def test_invalid_json_fails_session(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()

        fake = FakeProvider(response_text="not json")
        with pytest.raises(ValueError, match="Provider returned invalid JSON"):
            run_committee(db_session, cs, fake)
        assert cs.status == "failed"

    def test_validation_failure_fails_session(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()

        invalid = _valid_report()
        del invalid["opposing_arguments"]
        fake = FakeProvider(response_text=json.dumps(invalid))
        with pytest.raises(ValueError, match="validation failed"):
            run_committee(db_session, cs, fake)
        assert cs.status == "failed"

    def test_retry_on_transient_error(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()

        call_count = [0]

        def _flaky_call(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ProviderTimeoutError()
            valid = _valid_report()
            return ProviderResponse(
                raw_text=json.dumps(valid),
                input_tokens=10,
                output_tokens=20,
            )

        fake = FakeProvider()
        fake.call = _flaky_call  # type: ignore[method-assign]
        report = run_committee(db_session, cs, fake)
        assert report is not None
        assert call_count[0] == 2  # original + 1 retry

    def test_no_retry_on_validation_failure(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()

        call_count = [0]

        def _bad_call(*args, **kwargs):
            call_count[0] += 1
            raise ProviderError("bad request", retryable=False)

        fake = FakeProvider()
        fake.call = _bad_call  # type: ignore[method-assign]
        with pytest.raises(Exception):
            run_committee(db_session, cs, fake)
        assert call_count[0] == 1  # no retry

    def test_record_outcome(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()

        valid = _valid_report()
        fake = FakeProvider(response_text=json.dumps(valid))
        run_committee(db_session, cs, fake)

        outcome = record_outcome(db_session, cs, "accepted", "Looks good")
        assert outcome.outcome == "accepted"
        assert outcome.owner_rationale == "Looks good"

    def test_outcome_all_three_values(self, db_session: Session) -> None:
        hid = _create_household(db_session)
        for val in ("accepted", "rejected", "deferred"):
            cs = _create_session(db_session, hid)
            build_privacy_preview(db_session, hid, cs)
            cs.status = "queued"
            db_session.commit()
            valid = _valid_report()
            fake = FakeProvider(response_text=json.dumps(valid))
            run_committee(db_session, cs, fake)

            outcome = record_outcome(db_session, cs, val)
            assert outcome.outcome == val

    def test_outcome_decision_draft_id_is_none(self, db_session: Session) -> None:
        """Decision Draft creation is delegated to Slice C — outcome records
        decision_draft_id=None by default."""
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()
        valid = _valid_report()
        fake = FakeProvider(response_text=json.dumps(valid))
        run_committee(db_session, cs, fake)

        outcome = record_outcome(db_session, cs, "accepted")
        assert outcome.decision_draft_id is None


# ═══════════════════════════════════════════════════════════════════════════
# Report immutability
# ═══════════════════════════════════════════════════════════════════════════


class TestReportImmutability:
    def test_report_cannot_be_updated_after_creation(
        self, db_session: Session, postgres_engine: Engine,
    ) -> None:
        hid = _create_household(db_session)
        cs = _create_session(db_session, hid)
        build_privacy_preview(db_session, hid, cs)
        cs.status = "queued"
        db_session.commit()
        valid = _valid_report()
        fake = FakeProvider(response_text=json.dumps(valid))
        report = run_committee(db_session, cs, fake)

        with pytest.raises(Exception, match="committee_report_immutable"):
            with postgres_engine.connect() as conn:
                conn.execute(text(
                    "UPDATE committee_reports SET model_id = 'new' WHERE id = :id"
                ), {"id": str(report.id)})
                conn.commit()
