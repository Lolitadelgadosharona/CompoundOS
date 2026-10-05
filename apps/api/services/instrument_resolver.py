"""Canonical identity boundary. Search is dynamic; lexical parsing is not validation."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import uuid4

from sqlalchemy import select, text

from apps.api.models import Asset


class InstrumentUnavailable(ValueError):
    pass


class AmbiguousInstrument(InstrumentUnavailable):
    def __init__(self, candidates):
        self.candidates = candidates
        super().__init__("Select a candidate instrument; search is ambiguous")


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    exchange: str
    asset_type: str
    currency: str
    provider: str
    provider_id: str


class InstrumentProvider(Protocol):
    def search(self, query: str) -> list[Instrument]: ...
    def identify(self, provider_id: str) -> Instrument: ...


def normalize_symbol(symbol):
    s = (symbol or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-:^=]{0,29}", s):
        raise InstrumentUnavailable("Invalid instrument symbol")
    return s


def query_from_question(question):
    q = (question or "").strip()
    if not q or len(q) > 500:
        raise InstrumentUnavailable("Provide an instrument query")
    dollar = re.findall(r"\$([A-Za-z0-9][A-Za-z0-9.\-]{0,29})(?![A-Za-z0-9.\-])", q)
    tokens = re.findall(r"(?<![\w.])([A-Z][A-Z0-9.\-]{1,29})(?![\w.])", q)
    candidates = list(dict.fromkeys(dollar or tokens))
    if len(candidates) == 1:
        return normalize_symbol(candidates[0])
    if len(candidates) > 1:
        raise InstrumentUnavailable("Specify one instrument or use search to select a candidate")
    # Strip question scaffolding, keeping company/semantic description for provider search.
    return re.sub(
        r"(?i)^(should i (?:buy|increase)|what about)\s+|\s+(?:position|valuation).*|[?]", "", q
    ).strip()


def resolve_query(query, provider):
    if query.upper().startswith("CASH:"):
        ccy = query[5:].upper()
        if not re.fullmatch("[A-Z]{3}", ccy):
            raise InstrumentUnavailable("Invalid cash currency")
        return Instrument(
            "CASH:" + ccy, ccy + " cash", "CASH", "CASH", ccy, "identity", "CASH:" + ccy
        )
    candidates = provider.search(query)
    if not candidates:
        raise InstrumentUnavailable("Instrument not found")
    exact = [i for i in candidates if query.upper() in {i.symbol.upper(), i.provider_id.upper()}]
    if len(exact) == 1:
        return exact[0]
    # An uppercase lexical symbol must never resolve to a similar company/product.
    if re.fullmatch(r"[A-Z0-9][A-Z0-9.\-:^=]{0,29}", query):
        raise AmbiguousInstrument([asdict(i) for i in candidates])
    if len(candidates) == 1:
        return candidates[0]
    raise AmbiguousInstrument([asdict(i) for i in candidates])


def canonical_asset(session, instrument):
    """Preserve existing UUIDs; never mutate a historical identity to another market."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k,0))"),
        {"k": "instrument:" + instrument.symbol + ":" + instrument.currency},
    )
    mapping = session.execute(
        text(
            "SELECT asset_id FROM instrument_provider_mappings WHERE provider=:p AND provider_id=:i"
        ),
        {"p": instrument.provider, "i": instrument.provider_id},
    ).scalar()
    if mapping:
        return session.get(Asset, mapping)
    matches = list(
        session.scalars(
            select(Asset).where(
                Asset.symbol == instrument.symbol,
                Asset.currency == instrument.currency,
                Asset.exchange.in_([instrument.exchange]),
            )
        )
    )
    if not matches:
        # Existing imports without exchange may be mapped only if uniquely compatible.
        matches = list(
            session.scalars(
                select(Asset).where(
                    Asset.symbol == instrument.symbol,
                    Asset.currency == instrument.currency,
                    Asset.exchange.is_(None),
                )
            )
        )
    if len(matches) > 1:
        raise InstrumentUnavailable("Historical identity conflict requires explicit mapping")
    asset = (
        matches[0]
        if matches
        else Asset(
            id=uuid4(),
            symbol=instrument.symbol,
            name=instrument.name[:200],
            exchange=instrument.exchange,
            asset_type=instrument.asset_type,
            currency=instrument.currency,
            confidence="verified",
        )
    )
    session.add(asset)
    session.flush()
    session.execute(
        text("""INSERT INTO instrument_provider_mappings(asset_id,provider,provider_id,metadata)
      VALUES(:a,:p,:i,CAST(:m AS jsonb)) ON CONFLICT(provider,provider_id) DO NOTHING"""),
        {
            "a": asset.id,
            "p": instrument.provider,
            "i": instrument.provider_id,
            "m": json.dumps(asdict(instrument)),
        },
    )
    return asset


def ledger_identity(
    session, symbol, exchange=None, isin=None, currency=None, name=None, asset_type=None
):
    """Offline import identity remains explicitly unverified. Currency must be supplied."""
    symbol = normalize_symbol(symbol)
    if not currency or not re.fullmatch("[A-Z]{3}", currency.upper()):
        raise InstrumentUnavailable("Import currency is required; no USD assumption")
    currency = currency.upper()
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k,0))"),
        {"k": "instrument:" + symbol + ":" + currency},
    )
    if isin:
        asset = session.scalar(select(Asset).where(Asset.isin == isin.strip().upper()))
        if asset:
            if asset.currency != currency:
                raise InstrumentUnavailable("ISIN/currency conflict")
            return asset
    assets = list(
        session.scalars(
            select(Asset).where(
                Asset.symbol == symbol, Asset.exchange == exchange, Asset.currency == currency
            )
        )
    )
    if len(assets) > 1:
        raise InstrumentUnavailable("Ambiguous historical identity")
    if assets:
        return assets[0]
    asset = Asset(
        id=uuid4(),
        symbol=symbol,
        exchange=exchange,
        isin=isin,
        currency=currency,
        name=(name or symbol)[:200],
        asset_type=asset_type
        if asset_type in {"ETF", "STOCK", "BOND", "CASH", "MONEY_MARKET", "FUND", "OTHER"}
        else "OTHER",
        confidence="unverified",
    )
    session.add(asset)
    session.flush()
    return asset
