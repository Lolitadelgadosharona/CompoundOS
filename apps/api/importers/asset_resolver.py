"""Asset identity resolution for import pipeline.

Sprint 009 Slice D — Manual Import + Data Source Foundation.

Resolution strategy:
  1. ISIN match (exact)
  2. (symbol, exchange, currency) match
  3. Create new Asset with confidence='unverified'
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.models import Asset


def _normalize_symbol(s: str | None) -> str | None:
    if s is None:
        return None
    return s.strip().upper()


def _normalize_str(s: str | None) -> str | None:
    if s is None:
        return None
    return s.strip().upper()


def resolve_asset(
    session: Session,
    symbol: str,
    exchange: str | None = None,
    isin: str | None = None,
    currency: str | None = None,
    name: str | None = None,
    asset_type: str | None = None,
) -> Asset:
    """Resolve an asset by ISIN, then (symbol, exchange, currency), then create.

    Returns the resolved Asset. If a new asset is created, it is added to the
    session and flushed, with confidence='unverified'.
    """
    symbol_norm = _normalize_symbol(symbol)
    exchange_norm = _normalize_str(exchange)
    isin_norm = _normalize_str(isin)
    currency_norm = _normalize_str(currency)

    # 1. ISIN match
    if isin_norm:
        existing = session.scalar(select(Asset).where(Asset.isin == isin_norm))
        if existing is not None:
            return _enrich_asset(existing, symbol_norm, exchange_norm, name)

    # 2. (symbol, exchange, currency) match
    if symbol_norm and currency_norm:
        existing = session.scalar(
            select(Asset).where(
                Asset.symbol == symbol_norm,
                Asset.exchange == exchange_norm,
                Asset.currency == currency_norm,
            )
        )
        if existing is not None:
            return _enrich_asset(existing, symbol_norm, exchange_norm, name)

    # 3. Create new
    resolved_name = name or (symbol_norm or "Unknown Asset")
    resolved_type = asset_type if asset_type and asset_type in {
        "ETF", "STOCK", "BOND", "CASH", "MONEY_MARKET", "FUND", "OTHER",
    } else "OTHER"
    resolved_currency = currency_norm or "USD"

    asset = Asset(
        id=uuid4(),
        symbol=symbol_norm,
        exchange=exchange_norm,
        isin=isin_norm,
        name=resolved_name,
        asset_type=resolved_type,
        currency=resolved_currency,
        confidence="unverified",
    )
    session.add(asset)
    session.flush()
    return asset


def _enrich_asset(
    asset: Asset,
    symbol: str | None,
    exchange: str | None,
    name: str | None,
) -> Asset:
    """Optionally fill in missing identity fields on an existing asset."""
    if name and not asset.name:
        asset.name = name
    if symbol and not asset.symbol:
        asset.symbol = symbol
    if exchange and not asset.exchange:
        asset.exchange = exchange
    return asset
