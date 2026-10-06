"""Preview controls without loosening LIVE source/approval rules."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.api.services.owner_preview import enabled, validate_environment
from apps.api.services.preview_providers import DemoProvider, PreviewCommittee
from apps.api.services.provider_output_validator import validate_provider_output
from apps.api.services.valuation import trusted_source


def preview(monkeypatch):
    monkeypatch.setenv("COMPOUNDOS_PREVIEW_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/compoundos_owner_preview_test")


def test_default_off(monkeypatch):
    monkeypatch.delenv("COMPOUNDOS_PREVIEW_MODE", raising=False)
    assert not enabled()
    with pytest.raises(RuntimeError):
        DemoProvider()


@pytest.mark.parametrize("environment", ["production", "development", ""])
def test_preview_fails_outside_isolated_test(monkeypatch, environment):
    preview(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", environment)
    with pytest.raises(RuntimeError):
        validate_environment()


def test_no_live_database_or_preview_promotion(monkeypatch):
    preview(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/real_owner")
    with pytest.raises(RuntimeError):
        validate_environment()
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/compoundos_owner_preview_test")
    monkeypatch.setenv("COMPOUNDOS_PREVIEW_MODE", "false")
    with pytest.raises(RuntimeError):
        validate_environment()
    assert not trusted_source("DEMO_PROVIDER")


@pytest.mark.parametrize("symbol", ["VTI", "QQQ", "VXUS", "SGOV", "BRK.B", "AAPL"])
def test_demo_identity_quality_and_no_network(monkeypatch, symbol):
    preview(monkeypatch)
    p = DemoProvider()
    i = p.identify(symbol)
    q = p.price(i)
    assert i.exchange == "DEMO_EXCHANGE" and q.provider == "DEMO_PROVIDER" and q.quality == "DEMO"
    assert q.as_of <= datetime.now(timezone.utc)
    assert p.search(symbol) == [i]


def test_demo_fx_inverse(monkeypatch):
    preview(monkeypatch)
    p = DemoProvider()
    assert abs(p.fx("USD", "CNY").rate * p.fx("CNY", "USD").rate - Decimal(1)) < Decimal("1e-25")
    assert p.fx("USD", "CNY").quality == "DEMO"


def test_simulated_report_real_citation_validation(monkeypatch):
    preview(monkeypatch)
    eid = "00000000-0000-0000-0000-000000000001"
    registry = {
        eid: {
            "citation_ref": "demo:context",
            "claim": "[model inference] Reference supplied evidence [simulated]",
            "mode": "SIMULATED",
        }
    }
    p = PreviewCommittee(registry)
    r = json.loads(p.call("", "").raw_text)
    assert "SIMULATED" in r["limitations"][0]
    assert validate_provider_output(r, set(registry), registry).passed
    r["evidence_citations"][0]["evidence_id"] = "invented"
    assert not validate_provider_output(r, set(registry), registry).passed


def test_preview_factories_never_construct_real_providers(monkeypatch):
    from types import SimpleNamespace

    from apps.api.services import launch_providers
    from apps.api.services.ai_provider import DeepSeekProvider
    from apps.api.services.preview_providers import committee_provider

    preview(monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("External provider called in Preview")

    monkeypatch.setattr(launch_providers, "_configured_yahoo", forbidden)
    monkeypatch.setattr(DeepSeekProvider, "__init__", forbidden)
    for factory in [
        launch_providers.get_instrument_provider,
        launch_providers.get_market_provider,
        launch_providers.get_fx_provider,
    ]:
        assert factory().name == "DEMO_PROVIDER"
    p = committee_provider(SimpleNamespace(evidence_items=[]))
    assert p.provider_name == "SIMULATED_COMMITTEE"
    assert json.loads(p.call("", "").raw_text)["recommended_direction"] == "insufficient_evidence"


def test_demo_quality_rejected_outside_preview(monkeypatch):
    from apps.api.services.launch_investment import check_observation
    from apps.api.services.valuation import RecommendationUnavailable, Valuation

    preview(monkeypatch)
    p = DemoProvider()
    q = p.price(p.identify("VTI"))
    assert Valuation("USD", datetime.now(timezone.utc)).contract()["data_mode"] == "DEMO"
    monkeypatch.setenv("COMPOUNDOS_PREVIEW_MODE", "false")
    with pytest.raises(RecommendationUnavailable):
        check_observation(q, datetime.now(timezone.utc))


def test_production_startup_fails_before_serving(monkeypatch):
    import os
    import subprocess
    import sys

    env = dict(
        os.environ,
        ENVIRONMENT="production",
        COMPOUNDOS_PREVIEW_MODE="true",
        DATABASE_URL="postgresql+psycopg://localhost/compoundos_owner_preview_test",
    )
    p = subprocess.run(
        [sys.executable, "-c", "import apps.api.main"], env=env, capture_output=True, text=True
    )
    assert p.returncode != 0
    assert "Owner Preview requires test environment" in p.stderr


def test_preview_http_boundaries(monkeypatch):
    from fastapi.testclient import TestClient

    from apps.api.main import app

    preview(monkeypatch)
    with TestClient(app) as c:
        for path in [
            "/api/research",
            "/api/automation",
            "/api/transactions",
            "/api/ops-real",
            "/api/scale",
            "/api/os",
        ]:
            assert c.post(path).status_code == 403
        assert c.get("/health", headers={"host": "public.example"}).status_code == 403
        assert (
            c.post(
                "/api/investment/candidates", headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert c.post("/settings/ai/test").status_code == 403
