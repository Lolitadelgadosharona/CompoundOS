"""Official-shaped synthetic responses only; no real gateway/session verification."""

import json
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from apps.api.services.broker_foundation import BrokerCapability
from apps.api.services.ibkr_adapter import (
    CAPABILITIES,
    GatewayReader,
    GatewayUnavailable,
    InteractiveBrokersProvider,
    configured_mode,
    contract_symbol,
)


def responses(account="DU1234567", kind="DEMO"):
    now = int(datetime.now(timezone.utc).timestamp())
    values = {
        "/portfolio/accounts": [
            {"id": account, "accountId": account, "type": kind, "currency": "USD"}
        ],
        f"/portfolio/{account}/ledger": {
            "USD": {"currency": "USD", "cashbalance": 100000, "timestamp": now},
            "CNY": {"currency": "CNY", "cashbalance": 10000, "timestamp": now},
            "BASE": {"currency": "BASE", "cashbalance": 999999999, "timestamp": now},
        },
        f"/portfolio/{account}/positions/0": [],
    }
    for i, symbol in enumerate(["AAPL", "VTI", "QQQ", "BRK B"], 1):
        values[f"/portfolio/{account}/positions/0"].append(
            {
                "acctId": account,
                "conid": i,
                "contractDesc": symbol,
                "assetClass": "STK",
                "currency": "USD",
                "position": 2.5,
                "avgCost": 100.25,
                "mktPrice": 200.0,
                "session_cookie": "NEVER_PERSIST_THIS",
                "password": "NEVER_PERSIST_THIS",
            }
        )
        values[f"/trsrv/secdef?conids={i}"] = {
            "secdef": [
                {
                    "conid": i,
                    "ticker": symbol,
                    "currency": "USD",
                    "listingExchange": "NYSE",
                    "name": symbol,
                    "assetClass": "STK",
                    "type": "ETF" if symbol in ["VTI", "QQQ"] else "COMMON",
                }
            ]
        }
    return values


def provider(values=None, mode="PAPER", requests=None):
    values = responses() if values is None else values

    def handler(request):
        if requests is not None:
            requests.append(request)
        key = request.url.path.removeprefix("/v1/api")
        if request.url.query:
            key += "?" + request.url.query.decode()
        data = values.get(key)
        if isinstance(data, httpx.Response):
            return data
        if data is None:
            return httpx.Response(404, json={"secret": "NEVER_PERSIST_THIS"})
        return httpx.Response(200, json=data, headers={"Set-Cookie": "secret=NEVER_PERSIST_THIS"})

    reader = GatewayReader(
        "https://localhost:5000/v1/api",
        transport=httpx.MockTransport(handler),
        pause=lambda _: None,
    )
    return InteractiveBrokersProvider(reader, mode)


def test_official_reads_normalize_conid_cash_class_share_cost_without_quotes_or_secrets():
    calls = []
    result = provider(requests=calls).read_result()
    assert result.mode == "PAPER"
    assert len(result.snapshot.cash) == 2
    assert result.snapshot.cash[1].amount == Decimal("10000")
    assert result.snapshot.positions[0].quantity == Decimal("2.5")
    assert result.details["DU1234567:1"]["average_cost"] == "100.25"
    assert result.snapshot.positions[-1].instrument.symbol == "BRK.B"
    assert result.snapshot.positions[-1].instrument.provider_id == "4"
    assert result.snapshot.positions[0].provenance.quality == "UNKNOWN"
    assert not result.details["DU1234567:1"]["incidental_price_trusted"]
    assert "NEVER_PERSIST_THIS" not in json.dumps(result.details)
    assert all(c.method == "GET" and "/iserver/" not in c.url.path for c in calls)
    assert all("authorization" not in c.headers and "cookie" not in c.headers for c in calls)
    assert (
        not {
            BrokerCapability.ORDER_EXECUTE,
            BrokerCapability.ORDER_PREVIEW,
            BrokerCapability.TRANSFER,
            BrokerCapability.WITHDRAWAL,
        }
        & CAPABILITIES
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:5000/v1/api",
        "https://example.com:5000/v1/api",
        "https://user:secret@localhost:5000/v1/api",
        "https://localhost:5000/v1/api?token=secret",
    ],
)
def test_gateway_rejects_unsafe_configuration(url):
    with pytest.raises(GatewayUnavailable):
        GatewayReader(url)


@pytest.mark.parametrize(
    "path",
    [
        "/iserver/auth/ssodh/init",
        "/iserver/account/U1/orders",
        "/logout",
        "/tickle",
        "/portfolio/../orders",
        "/portfolio/U1/ledger?token=x",
        "/trsrv/secdef?conids=1&token=x",
    ],
)
def test_closed_get_allowlist(path):
    with pytest.raises(GatewayUnavailable):
        provider().reader.get(path)


@pytest.mark.parametrize("mode", ["PAPER", "LIVE"])
def test_mode_is_verified_not_merely_a_label(mode):
    p = provider(responses("U1234567", "REAL") if mode == "PAPER" else responses(), mode)
    with pytest.raises(GatewayUnavailable, match="MODE_MISMATCH"):
        p.read_result()


def test_live_read_requires_separate_owner_authorization(monkeypatch):
    monkeypatch.setenv("COMPOUNDOS_IBKR_READ_ENABLED", "1")
    monkeypatch.setenv("COMPOUNDOS_IBKR_ACCOUNT_MODE", "LIVE")
    monkeypatch.delenv("COMPOUNDOS_IBKR_LIVE_READ_AUTHORIZED", raising=False)
    with pytest.raises(GatewayUnavailable):
        configured_mode()


@pytest.mark.parametrize("status", [301, 401, 403, 429, 500])
def test_errors_are_sanitized_and_no_retry_or_auth_escalation(status):
    calls = []
    values = responses()
    values["/portfolio/accounts"] = httpx.Response(
        status, json={"session_token": "NEVER_PERSIST_THIS"}
    )
    with pytest.raises(GatewayUnavailable) as e:
        provider(values, requests=calls).read_result()
    assert "NEVER_PERSIST_THIS" not in str(e.value) and len(calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("position", "NaN"),
        ("position", -1),
        ("currency", "GBp"),
        ("conid", None),
        ("avgCost", "Infinity"),
    ],
)
def test_invalid_position_fails_batch(field, value):
    v = responses()
    v["/portfolio/DU1234567/positions/0"][0][field] = value
    with pytest.raises(GatewayUnavailable):
        provider(v).read_result()


def test_unresolved_identity_keeps_position_visible():
    v = responses()
    v["/trsrv/secdef?conids=4"]["secdef"][0]["listingExchange"] = None
    result = provider(v).read_result()
    assert result.snapshot.positions[-1].instrument is None
    assert result.snapshot.positions[-1].quantity == Decimal("2.5")
    assert contract_symbol("BRK B") == "BRK.B"


def test_account_currencies_future_cash_timestamp_and_pagination_fail_closed():
    v = responses()
    v["/portfolio/DU1234567/ledger"]["CNY"]["timestamp"] = 9999999999
    with pytest.raises(GatewayUnavailable):
        provider(v).read_result()
    v = responses()
    v["/portfolio/DU1234567/ledger"] = {"BASE": {"cashbalance": 100}}
    with pytest.raises(GatewayUnavailable):
        provider(v).read_result()


def test_tls_hostname_verification_enabled():
    import ssl

    reader = provider().reader
    assert reader.context.check_hostname and reader.context.verify_mode == ssl.CERT_REQUIRED


def test_paper_owner_confirmation_for_account_type_without_paper_marker():
    v = responses()
    v["/portfolio/accounts"][0]["type"] = "INDIVIDUAL"
    p = provider(v)
    with pytest.raises(GatewayUnavailable):
        p.read_result()
    p.approved_paper_accounts = frozenset({"DU1234567"})
    assert p.read_result().mode == "PAPER"


def test_no_broker_reads_by_default(monkeypatch):
    monkeypatch.delenv("COMPOUNDOS_IBKR_READ_ENABLED", raising=False)
    with pytest.raises(GatewayUnavailable, match="OWNER_SETUP_REQUIRED"):
        configured_mode()


def test_unknown_security_subtype_and_page_limit_are_not_guessed(monkeypatch):
    v = responses()
    v["/trsrv/secdef?conids=1"]["secdef"][0]["type"] = "UNKNOWN"
    assert provider(v).read_result().snapshot.positions[0].instrument is None
    v = responses()
    v["/portfolio/DU1234567/positions/0"] *= 25
    monkeypatch.setattr("apps.api.services.ibkr_adapter.MAX_PAGES", 1)
    with pytest.raises(GatewayUnavailable, match="PAGINATION_INCOMPLETE"):
        provider(v).read_result()
