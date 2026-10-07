"""Official Client Portal Gateway reads only. No auth automation or trading session setup."""

import ipaddress
import os
import re
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import httpx

from apps.api.services.broker_foundation import (
    BrokerAccount,
    BrokerCapability,
    BrokerCashBalance,
    BrokerPosition,
    BrokerSnapshot,
    Provenance,
)
from apps.api.services.instrument_resolver import Instrument, normalize_symbol

CAPABILITIES = frozenset(
    {
        BrokerCapability.ACCOUNT_READ,
        BrokerCapability.POSITIONS_READ,
        BrokerCapability.CASH_READ,
        BrokerCapability.COST_BASIS_READ,
    }
)
MAX_PAGES = 20
MAX_ACCOUNTS = 10
MAX_BYTES = 2_000_000


class GatewayUnavailable(ValueError):
    """Sanitized code only: never propagate provider response, URL or authentication artifact."""


def decimal_value(value):
    if isinstance(value, bool) or value is None:
        raise GatewayUnavailable("IBKR_INVALID_NUMBER")
    try:
        number = Decimal(str(value))
    except Exception:
        raise GatewayUnavailable("IBKR_INVALID_NUMBER") from None
    if not number.is_finite():
        raise GatewayUnavailable("IBKR_INVALID_NUMBER")
    return number


def safe_text(value, pattern, code):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise GatewayUnavailable(code)
    return value


def contract_symbol(value):
    # IB class-share separator is preserved, not truncated; only a single class letter.
    if isinstance(value, str) and re.fullmatch(r"[A-Z0-9.\-]+ [A-Z]", value):
        value = value.replace(" ", ".")
    try:
        return normalize_symbol(value)
    except ValueError:
        raise GatewayUnavailable("IBKR_UNRESOLVED_SYMBOL") from None


class GatewayReader:
    """Fixed local HTTPS base, closed GET allowlist, TLS/proxy/redirect protections."""

    def __init__(self, base_url, ca_file=None, transport=None, pause=time.sleep):
        u = urlparse(base_url)
        if (
            u.scheme != "https"
            or u.hostname not in {"localhost", "127.0.0.1", "::1"}
            or u.username
            or u.password
            or u.path != "/v1/api"
            or u.query
            or u.fragment
            or not u.port
        ):
            raise GatewayUnavailable("IBKR_LOCAL_HTTPS_REQUIRED")
        self.base_url = base_url
        self.hostname = u.hostname
        self.port = u.port
        self.pause = pause
        self.last_request = 0.0
        self.started_at = time.monotonic()
        self.context = ssl.create_default_context(cafile=ca_file)
        # Test injection is a mock HTTP transport, never a credential override.
        self.transport = transport

    def get(self, path):
        if not (
            path == "/portfolio/accounts"
            or re.fullmatch(r"/portfolio/[A-Z0-9]{2,32}/(?:ledger|positions/[0-9]{1,2})", path)
            or re.fullmatch(r"/trsrv/secdef\?conids=[1-9][0-9]{0,17}", path)
        ):
            raise GatewayUnavailable("IBKR_READ_ENDPOINT_FORBIDDEN")
        if self.transport is None:
            try:
                addresses = socket.getaddrinfo(self.hostname, self.port, type=socket.SOCK_STREAM)
                if not addresses or any(
                    not ipaddress.ip_address(a[4][0]).is_loopback for a in addresses
                ):
                    raise GatewayUnavailable("IBKR_NONLOCAL_GATEWAY")
            except OSError:
                raise GatewayUnavailable("IBKR_GATEWAY_UNAVAILABLE") from None
        if time.monotonic() - self.started_at > 120:
            raise GatewayUnavailable("IBKR_READ_BUDGET_EXCEEDED")
        # Conservative pacing below global10rps; no automatic retry.
        self.pause(max(0, 0.2 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        try:
            with httpx.Client(
                verify=self.context,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
                timeout=10,
                headers={"User-Agent": "CompoundOS-ReadOnly/1", "Accept": "application/json"},
            ) as client:
                with client.stream("GET", self.base_url + path) as response:
                    if response.status_code in {401, 403}:
                        raise GatewayUnavailable("IBKR_OWNER_REAUTHENTICATION_REQUIRED")
                    if response.status_code != 200:
                        raise GatewayUnavailable("IBKR_READ_FAILED")
                    content = b""
                    for chunk in response.iter_bytes():
                        content += chunk
                        if len(content) > MAX_BYTES:
                            raise GatewayUnavailable("IBKR_RESPONSE_TOO_LARGE")
                    import json

                    return json.loads(content, parse_float=Decimal)
        except GatewayUnavailable:
            raise
        except Exception:
            raise GatewayUnavailable("IBKR_GATEWAY_UNAVAILABLE") from None


@dataclass(frozen=True)
class IBKRReadResult:
    snapshot: BrokerSnapshot
    details: dict
    mode: str


class InteractiveBrokersProvider:
    capabilities = CAPABILITIES

    def __init__(self, reader, mode="PAPER", approved_paper_accounts=frozenset()):
        if mode not in {"PAPER", "LIVE"}:
            raise GatewayUnavailable("IBKR_MODE_REQUIRED")
        self.reader, self.mode = reader, mode
        self.approved_paper_accounts = approved_paper_accounts

    def read_snapshot(self):
        return self.read_result().snapshot

    def read_result(self):
        retrieved = datetime.now(timezone.utc)
        raw_accounts = self.reader.get("/portfolio/accounts")
        if (
            not isinstance(raw_accounts, list)
            or not raw_accounts
            or len(raw_accounts) > MAX_ACCOUNTS
        ):
            raise GatewayUnavailable("IBKR_ACCOUNTS_INCOMPLETE")
        accounts, positions, cash, details = [], [], [], {}
        for raw in raw_accounts:
            account = safe_text(raw.get("id"), r"[A-Z0-9]{2,32}", "IBKR_ACCOUNT_ID_INVALID")
            # A mode choice alone is not evidence that returned accounts are Paper.
            paper = account.startswith("DU") and (
                raw.get("type") == "DEMO" or account in self.approved_paper_accounts
            )
            if (self.mode == "PAPER" and not paper) or (
                self.mode == "LIVE" and (account.startswith("DU") or raw.get("type") == "DEMO")
            ):
                raise GatewayUnavailable("IBKR_ACCOUNT_MODE_MISMATCH")
            if raw.get("accountId") and raw["accountId"] != account:
                raise GatewayUnavailable("IBKR_ACCOUNT_ID_MISMATCH")
            currency = safe_text(raw.get("currency"), r"[A-Z]{3}", "IBKR_CURRENCY_UNKNOWN")
            accounts.append(
                BrokerAccount(
                    account,
                    currency,
                    Provenance("interactive_brokers", account, retrieved, retrieved, "UNKNOWN"),
                )
            )
            ledger = self.reader.get(f"/portfolio/{account}/ledger")
            if not isinstance(ledger, dict) or not ledger:
                raise GatewayUnavailable("IBKR_LEDGER_INCOMPLETE")
            native_count = 0
            for key, value in ledger.items():
                if key == "BASE":  # derived summary, never double count native balances
                    continue
                ccy = safe_text(key, r"[A-Z]{3}", "IBKR_CURRENCY_UNKNOWN")
                if not isinstance(value, dict) or value.get("currency") != ccy:
                    raise GatewayUnavailable("IBKR_CURRENCY_MISMATCH")
                if value.get("acctcode") and value["acctcode"] != account:
                    raise GatewayUnavailable("IBKR_ACCOUNT_ID_MISMATCH")
                if not value.get("timestamp"):
                    raise GatewayUnavailable("IBKR_BALANCE_TIMESTAMP_MISSING")
                try:
                    observed = datetime.fromtimestamp(float(value["timestamp"]), timezone.utc)
                    if observed > datetime.now(timezone.utc):
                        raise ValueError()
                    provenance = Provenance(
                        "interactive_brokers",
                        account + ":" + ccy,
                        observed,
                        datetime.now(timezone.utc),
                        "DELAYED",
                    )
                except Exception:
                    raise GatewayUnavailable("IBKR_BALANCE_TIMESTAMP_INVALID") from None
                cash.append(
                    BrokerCashBalance(
                        account + ":" + ccy,
                        account,
                        decimal_value(value.get("cashbalance")),
                        ccy,
                        provenance,
                    )
                )
                native_count += 1
            if not native_count:
                raise GatewayUnavailable("IBKR_NATIVE_CASH_MISSING")
            ended = False
            for page in range(MAX_PAGES):
                rows = self.reader.get(f"/portfolio/{account}/positions/{page}")
                if not isinstance(rows, list) or len(rows) > 100:
                    raise GatewayUnavailable("IBKR_POSITIONS_INCOMPLETE")
                for row in rows:
                    if not isinstance(row, dict) or row.get("acctId") != account:
                        raise GatewayUnavailable("IBKR_ACCOUNT_ID_MISMATCH")
                    conid = str(row.get("conid", ""))
                    safe_text(conid, r"[1-9][0-9]{0,17}", "IBKR_CONID_INVALID")
                    ccy = safe_text(row.get("currency"), r"[A-Z]{3}", "IBKR_CURRENCY_UNKNOWN")
                    quantity = decimal_value(row.get("position"))
                    if quantity < 0:
                        raise GatewayUnavailable("IBKR_SHORT_POSITION_UNSUPPORTED")
                    cost = None if row.get("avgCost") is None else decimal_value(row["avgCost"])
                    if cost is not None and cost < 0:
                        raise GatewayUnavailable("IBKR_COST_INVALID")
                    identity = self.reader.get("/trsrv/secdef?conids=" + conid)
                    definitions = identity.get("secdef", []) if isinstance(identity, dict) else []
                    definition = definitions[0] if len(definitions) == 1 else {}
                    instrument = None
                    try:
                        symbol = contract_symbol(definition.get("ticker"))
                        # Only explicit equity security definitions; derivatives stay unresolved.
                        if (
                            str(definition.get("conid")) != conid
                            or definition.get("currency") != ccy
                            or definition.get("assetClass") != "STK"
                            or row.get("assetClass") != "STK"
                        ):
                            raise ValueError()
                        venue = safe_text(
                            definition.get("listingExchange"),
                            r"[A-Z0-9._\-]{2,30}",
                            "IBKR_VENUE_UNKNOWN",
                        )
                        if definition.get("type") not in {"ETF", "COMMON", "STOCK"}:
                            raise ValueError()
                        classification = "ETF" if definition.get("type") == "ETF" else "STOCK"
                        name = safe_text(
                            definition.get("name"), r"[^\x00-\x1f]{1,200}", "IBKR_NAME_UNKNOWN"
                        )
                        instrument = Instrument(
                            symbol, name, venue, classification, ccy, "interactive_brokers", conid
                        )
                    except ValueError:
                        pass
                    observed = datetime.now(timezone.utc)
                    provenance = Provenance(
                        "interactive_brokers", account + ":" + conid, observed, observed, "UNKNOWN"
                    )
                    positions.append(
                        BrokerPosition(
                            account + ":" + conid,
                            account,
                            quantity,
                            ccy,
                            provenance,
                            instrument,
                            cost_basis=None,
                        )
                    )
                    # Whitelist fields only; no raw responses/session headers persisted.
                    details[account + ":" + conid] = {
                        "conid": conid,
                        "symbol": instrument.symbol if instrument else definition.get("ticker"),
                        "broker_symbol": definition.get("ticker"),
                        "local_symbol": row.get("localSymbol") or row.get("contractDesc"),
                        "security_type": row.get("assetClass"),
                        "exchange": row.get("exchs"),
                        "primary_exchange": definition.get("listingExchange"),
                        "average_cost": str(cost) if cost is not None else None,
                        "cost_currency": ccy,
                        "as_of_basis": "RETRIEVAL_TIME_NOT_PROVIDER_OBSERVATION",
                        "incidental_price_present": row.get("mktPrice") is not None,
                        "incidental_price_trusted": False,
                    }
                if len(rows) < 100:
                    ended = True
                    break
            if not ended:
                raise GatewayUnavailable("IBKR_PAGINATION_INCOMPLETE")
        return IBKRReadResult(
            BrokerSnapshot(tuple(accounts), tuple(positions), tuple(cash), (), True),
            details,
            self.mode,
        )


def configured_mode():
    if os.getenv("COMPOUNDOS_IBKR_READ_ENABLED") != "1":
        raise GatewayUnavailable("IBKR_OWNER_SETUP_REQUIRED")
    mode = os.getenv("COMPOUNDOS_IBKR_ACCOUNT_MODE", "PAPER")
    if mode == "LIVE" and os.getenv("COMPOUNDOS_IBKR_LIVE_READ_AUTHORIZED") != "1":
        raise GatewayUnavailable("IBKR_LIVE_OWNER_AUTHORIZATION_REQUIRED")
    if mode not in {"PAPER", "LIVE"}:
        raise GatewayUnavailable("IBKR_MODE_REQUIRED")
    return mode


def configured_provider():
    mode = configured_mode()
    ca = os.getenv("COMPOUNDOS_IBKR_GATEWAY_CA_FILE")
    if not ca or not Path(ca).is_file():
        raise GatewayUnavailable("IBKR_LOCAL_TLS_SETUP_REQUIRED")
    approved = frozenset()
    account_file = os.getenv("COMPOUNDOS_IBKR_PAPER_ACCOUNT_FILE")
    if account_file:
        import json

        try:
            accounts = json.loads(Path(account_file).read_text())
            if (
                not isinstance(accounts, list)
                or not accounts
                or any(
                    not isinstance(a, str) or not re.fullmatch(r"DU[0-9]{5,30}", a)
                    for a in accounts
                )
            ):
                raise ValueError()
            approved = frozenset(accounts)
        except Exception:
            raise GatewayUnavailable("IBKR_PAPER_ACCOUNT_CONFIRMATION_INVALID") from None
    try:
        return InteractiveBrokersProvider(
            GatewayReader(
                os.getenv("COMPOUNDOS_IBKR_GATEWAY_URL", "https://localhost:5000/v1/api"), ca
            ),
            mode,
            approved,
        )
    except GatewayUnavailable:
        raise
    except Exception:
        raise GatewayUnavailable("IBKR_LOCAL_TLS_SETUP_REQUIRED") from None
