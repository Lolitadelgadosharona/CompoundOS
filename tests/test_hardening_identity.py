# ruff: noqa: F811
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.api.services.instrument_resolver import Instrument, InstrumentUnavailable, canonical_asset
from apps.api.services.launch_providers import YahooPublicProvider
from tests.test_launch_v1 import provider as provider
from tests.test_launch_v1 import setup as setup


@pytest.mark.postgres
def test_mapping_collision_fails_closed(db_session, setup, provider):
    _, _, assets, _ = setup
    for change in [
        dict(symbol="OTHER"),
        dict(currency="EUR"),
        dict(exchange="OTHER"),
        dict(asset_type="STOCK"),
    ]:
        with pytest.raises(InstrumentUnavailable, match="IDENTITY_MISMATCH"):
            canonical_asset(db_session, replace(provider.identify("VTI"), **change))
    assert canonical_asset(db_session, provider.identify("VTI")).id == assets[0].id


@pytest.mark.postgres
def test_same_ticker_different_venue_is_distinct(db_session, setup, provider):
    a = canonical_asset(db_session, provider.identify("DUP"))
    b = canonical_asset(
        db_session, replace(provider.identify("DUP"), exchange="SECOND", provider_id="DUP.OTHER")
    )
    assert a.id != b.id


@pytest.mark.parametrize(
    "dimension,value",
    [("symbol", "MSFT"), ("exchangeName", "NYQ"), ("currency", "EUR"), ("instrumentType", "ETF")],
)
def test_quote_response_mismatch(dimension, value, monkeypatch):
    p = YahooPublicProvider()
    meta = dict(
        symbol="AAPL",
        longName="Apple",
        exchangeName="NMS",
        currency="USD",
        instrumentType="EQUITY",
        regularMarketPrice=100,
        regularMarketTime=int(datetime.now(timezone.utc).timestamp()),
    )
    meta[dimension] = value
    monkeypatch.setattr(p, "_meta", lambda pid: meta)
    with pytest.raises(InstrumentUnavailable, match="IDENTITY_MISMATCH"):
        p.price(Instrument("AAPL", "Apple", "NMS", "STOCK", "USD", "yahoo_public", "AAPL"))


def test_brkb_preserves_class_and_quote_identity(monkeypatch):
    p = YahooPublicProvider()
    meta = dict(
        symbol="BRK-B",
        longName="Berkshire B",
        exchangeName="NYQ",
        currency="USD",
        instrumentType="EQUITY",
        regularMarketPrice=100,
        regularMarketTime=int(datetime.now(timezone.utc).timestamp()),
    )
    monkeypatch.setattr(p, "_meta", lambda pid: meta)
    instrument = p.identify("BRK-B")
    assert instrument.symbol == "BRK.B"
    quote = p.price(instrument)
    assert quote.identity["symbol"] == "BRK.B" and quote.provider_id == "BRK-B"
    meta["symbol"] = "BRK"
    with pytest.raises(InstrumentUnavailable):
        p.price(instrument)


def test_fx_actual_pair_is_validated(monkeypatch):
    p = YahooPublicProvider()
    monkeypatch.setattr(
        p,
        "_meta",
        lambda pid: dict(
            symbol="EURUSD=X",
            currency="USD",
            regularMarketPrice=Decimal(".15"),
            regularMarketTime=1,
        ),
    )
    with pytest.raises(InstrumentUnavailable, match="IDENTITY_MISMATCH"):
        p.fx("CNY", "USD")
