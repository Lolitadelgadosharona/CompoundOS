import pytest

from apps.api.services.broker_connections import (
    FutureOrderCapability,
    ReadOnlyConnection,
    connection_directory,
)
from apps.api.services.launch_investment import audit_action


def test_no_order_capability_in_v1():
    with pytest.raises(ValueError):
        ReadOnlyConnection("future", capabilities=(FutureOrderCapability.ORDER_EXECUTE,))
    with pytest.raises(ValueError):
        ReadOnlyConnection("future", capabilities=(FutureOrderCapability.ORDER_PREVIEW,))


def test_directory_reports_only_declared_read_access():
    d = connection_directory([{"source": "manual"}])
    assert not d["credentials_accepted"] and not d["order_execution_supported"]
    assert d["manual"]["status"] == "CONNECTED" and not d["manual"]["external_connection"]
    for row in d["brokers"]:
        assert row["status"] == "NOT_CONNECTED" and not row["available"]
        assert "ORDER_EXECUTE" not in row["capabilities"]


def test_preview_rejection_namespace_matches_its_writer(monkeypatch):
    monkeypatch.setenv("COMPOUNDOS_PREVIEW_MODE", "true")
    assert audit_action("contribution.rejected") == "preview.contribution.rejected"
    monkeypatch.setenv("COMPOUNDOS_PREVIEW_MODE", "false")
    assert audit_action("contribution.rejected") == "contribution.rejected"
