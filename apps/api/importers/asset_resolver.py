"""Import identity delegates to the canonical resolver; no network during file ingestion."""

from apps.api.services.instrument_resolver import ledger_identity


def resolve_asset(
    session, symbol, exchange=None, isin=None, currency=None, name=None, asset_type=None
):
    return ledger_identity(
        session,
        symbol,
        exchange.strip().upper() if exchange else None,
        isin.strip().upper() if isin else None,
        currency,
        name,
        asset_type,
    )
