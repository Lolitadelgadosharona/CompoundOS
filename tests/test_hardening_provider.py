"""Provider boundary checks are UNIT evidence, never a claimed real provider success."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from apps.api.services.ai_provider import DeepSeekProvider, ProviderError, ProviderTimeoutError


def test_deepseek_payload_json_and_timeout(monkeypatch):
    captured = {}

    def request(req, timeout):
        captured.update(body=json.loads(req.data), timeout=timeout)
        return BytesIO(
            json.dumps(
                {
                    "choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                    "model": "test-only",
                }
            ).encode()
        )

    monkeypatch.setattr("urllib.request.urlopen", request)
    response = DeepSeekProvider(api_key="synthetic-test-only").call("system", "user")
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 120 and response.input_tokens == 10


@pytest.mark.parametrize(
    "error",
    [OSError("synthetic timeout"), HTTPError("https://test", 401, "unauthorized", {}, None)],
)
def test_provider_failures_are_safe(monkeypatch, error):
    def request(*a, **k):
        raise error

    monkeypatch.setattr("urllib.request.urlopen", request)
    with pytest.raises((ProviderError, ProviderTimeoutError)):
        DeepSeekProvider(api_key="synthetic-test-only").call("system", "user")


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"{}",
        b'{"choices":[]}',
        json.dumps(
            {
                "choices": [{"message": {"content": "{}"}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        ).encode(),
        json.dumps(
            {
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": "NaN", "completion_tokens": 1},
            }
        ).encode(),
    ],
)
def test_malformed_truncated_or_invalid_usage_is_rejected(monkeypatch, body):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: BytesIO(body))
    with pytest.raises(ProviderError):
        DeepSeekProvider(api_key="synthetic-test-only").call("system", "user")


@pytest.mark.parametrize(
    "field",
    [
        "supporting_arguments",
        "risks",
        "policy_alignment",
        "long_term_compounding",
        "index_passive_investing",
        "macroeconomic_context",
        "risk_capital_preservation",
        "devils_advocate",
        "policy_alignment_role",
        "synthesis_chair",
    ],
)
def test_incomplete_structured_committee_cannot_validate(field):
    from apps.api.services.provider_output_validator import validate_provider_output
    from tests.test_committee_provider import _valid_report

    report = _valid_report()
    if field in report["sections"]:
        report["sections"][field] = {}
    else:
        report[field] = " " if field == "policy_alignment" else []
    assert not validate_provider_output(report, set()).passed
