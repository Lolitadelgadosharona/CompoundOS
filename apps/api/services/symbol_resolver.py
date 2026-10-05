"""Compatibility entry point delegates to the canonical dynamic resolver."""

from apps.api.services.instrument_resolver import (
    InstrumentUnavailable,
    query_from_question,
    resolve_query,
)
from apps.api.services.launch_providers import get_instrument_provider

SymbolResolutionError = InstrumentUnavailable


def resolve_symbol(question, provider=None):
    return resolve_query(
        query_from_question(question), provider or get_instrument_provider()
    ).symbol
