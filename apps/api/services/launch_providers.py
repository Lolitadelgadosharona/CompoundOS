"""Provider adapters with explicit observation times. No secrets, trading or synthetic fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from urllib.parse import quote as urlquote

import httpx

from apps.api.services.instrument_resolver import (
    Instrument,
    InstrumentUnavailable,
    normalize_symbol,
)


@dataclass(frozen=True)
class PriceObservation:
    provider_id: str
    price: Decimal
    currency: str
    as_of: datetime
    provider: str
    quality: str = "DELAYED"
    identity: dict | None = None


@dataclass(frozen=True)
class FXObservation:
    base_currency: str
    quote_currency: str
    rate: Decimal
    as_of: datetime
    provider: str
    quality: str = "OBSERVED"
    identity: dict | None = None


class MarketDataProvider(Protocol):
    def price(self, instrument: Instrument) -> PriceObservation: ...


class FXProvider(Protocol):
    def fx(self, base: str, quote: str) -> FXObservation: ...


class YahooPublicProvider:
    """Unofficial public endpoints: delayed observations, outages fail closed.

    Fixed hosts and bounded requests. No promise of availability or licensed redistribution.
    """

    name = "yahoo_public"

    def _get(self, path, params=None):
        try:
            r = httpx.get(
                "https://query1.finance.yahoo.com" + path,
                params=params,
                timeout=12,
                follow_redirects=False,
                headers={"User-Agent": "CompoundOS/0.2 personal-analysis"},
            )
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise InstrumentUnavailable("Market provider unavailable; no fallback values") from exc

    def _meta(self, pid):
        normalize_symbol(pid)
        data = self._get(
            "/v8/finance/chart/" + urlquote(pid, safe=""), {"range": "5d", "interval": "1d"}
        )
        results = data.get("chart", {}).get("result")
        if not results:
            raise InstrumentUnavailable("Provider did not identify instrument")
        return results[0]["meta"]

    def _identity(self, provider_id, meta):
        if meta.get("symbol") != provider_id:
            raise InstrumentUnavailable("QUOTE_IDENTITY_MISMATCH: provider symbol")
        typ = {"EQUITY": "STOCK", "ETF": "ETF", "MUTUALFUND": "FUND"}.get(
            meta.get("instrumentType")
        )
        ccy = meta.get("currency")
        if not typ or not ccy or not meta.get("exchangeName"):
            raise InstrumentUnavailable("Incomplete instrument metadata or unsupported asset type")
        pid = meta["symbol"]
        # Yahoo class-share separator is provider-specific, preserve owner-facing BRK.B.
        symbol = (
            pid.replace("-", ".")
            if meta.get("exchangeName") in {"NYQ", "NMS", "NGM", "NCM", "PCX", "ASE"}
            else pid
        )
        return Instrument(
            symbol,
            meta.get("longName") or meta.get("shortName") or symbol,
            meta["exchangeName"],
            typ,
            "GBP" if ccy == "GBp" else ccy,
            self.name,
            pid,
        )

    def identify(self, provider_id):
        return self._identity(provider_id, self._meta(provider_id))

    def search(self, query):
        if not query.strip() or len(query) > 200:
            raise InstrumentUnavailable("Invalid search query")
        data = self._get("/v1/finance/search", {"q": query, "quotesCount": 10, "newsCount": 0})
        matches = [
            i
            for i in data.get("quotes", [])
            if i.get("quoteType") in {"ETF", "EQUITY", "MUTUALFUND"}
        ]
        # Exact symbols avoid unrelated suggestions; semantic search returns candidates.
        exact = [
            i for i in matches if i.get("symbol", "").upper().replace("-", ".") == query.upper()
        ]
        if not exact and re.fullmatch(r"[A-Z]+\.[A-Z]", query):
            # Provider-specific US class-share spelling must be verified, not guessed.
            alternate = self.identify(query.replace(".", "-"))
            if alternate.symbol == query and alternate.exchange in {
                "NYQ",
                "NMS",
                "NGM",
                "NCM",
                "PCX",
                "ASE",
            }:
                return [alternate]
            raise InstrumentUnavailable("Class-share identity was not verified")
        selected = exact if exact else matches[:5]
        result = []
        for item in selected:
            result.append(self.identify(item["symbol"]))
        return result

    def price(self, instrument):
        meta = self._meta(instrument.provider_id)
        from apps.api.services.instrument_resolver import identity_dimensions

        actual = self._identity(instrument.provider_id, meta)
        if identity_dimensions(actual) != identity_dimensions(instrument):
            raise InstrumentUnavailable("QUOTE_IDENTITY_MISMATCH: canonical dimensions")
        try:
            p = Decimal(str(meta["regularMarketPrice"]))
            stamp = datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc)
            ccy = meta["currency"]
        except (KeyError, ValueError, TypeError) as exc:
            raise InstrumentUnavailable("Price/provenance missing") from exc
        if not p.is_finite() or p <= 0:
            raise InstrumentUnavailable("Invalid market price")
        if ("GBP" if ccy == "GBp" else ccy) != instrument.currency:
            raise InstrumentUnavailable("Quote currency does not match canonical instrument")
        return PriceObservation(
            actual.provider_id, p, ccy, stamp, self.name, identity=identity_dimensions(actual)
        )

    def fx(self, base, quote):
        if (
            not re.fullmatch("[A-Z]{3}", base)
            or not re.fullmatch("[A-Z]{3}", quote)
            or base == quote
        ):
            raise InstrumentUnavailable("Invalid FX pair")
        pair = base + quote + "=X"
        meta = self._meta(pair)
        if meta.get("symbol") != pair or meta.get("currency") != quote:
            raise InstrumentUnavailable("QUOTE_IDENTITY_MISMATCH: FX pair/currency")
        try:
            return FXObservation(
                base,
                quote,
                Decimal(str(meta["regularMarketPrice"])),
                datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc),
                self.name,
                "DELAYED",
                {"from_currency": base, "to_currency": quote, "provider_id": pair},
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise InstrumentUnavailable("FX provenance missing") from exc


def _configured_yahoo():
    import os

    if (
        os.getenv("ENVIRONMENT", "").lower() not in {"development", "test"}
        and os.getenv("COMPOUNDOS_YAHOO_ACCESS_AUTHORIZED") != "1"
    ):
        raise InstrumentUnavailable(
            "Production market source not authorized: configure a licensed adapter "
            "or verify Yahoo access permission"
        )
    return YahooPublicProvider()


def get_instrument_provider():
    return _configured_yahoo()


def get_market_provider():
    return _configured_yahoo()


def get_fx_provider():
    return _configured_yahoo()


def configured_data_sources():
    """Authoritative adapter registry; business services do not name a market vendor."""
    import os
    adapters = [get_instrument_provider(), get_market_provider(), get_fx_provider()]
    if any(getattr(p, "test_only", False) for p in adapters) and os.getenv("ENVIRONMENT") != "test":
        raise InstrumentUnavailable("Test-only provider cannot support production recommendations")
    return {p.name for p in adapters}
