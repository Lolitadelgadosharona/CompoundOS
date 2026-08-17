"""Deterministic symbol/entity resolution — no AI (PE-002 Slice A, PE-002.2a).

Resolve a natural-language investment question to an intent + entity +
ticker using only regex + curated company/ETF maps. Unknown input returns
None so the caller can fall back to AI-assisted understanding.
"""

from __future__ import annotations

import re

# Company name → ticker (curated US large-caps).
COMPANY_TO_TICKER = {
    "nvidia": "NVDA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "tesla": "TSLA",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "salesforce": "CRM",
    "amd": "AMD",
    "intel": "INTC",
    "netflix": "NFLX",
    "broadcom": "AVGO",
    "adobe": "ADBE",
    "coca-cola": "KO",
    "disney": "DIS",
    "jpmorgan": "JPM",
    "visa": "V",
    "walmart": "WMT",
    "exxon": "XOM",
    "johnson": "JNJ",
}

# ETF ticker (lowercase key → uppercase symbol). ETFs are usually referenced
# by ticker; this map makes bare/lowercase ETF mentions resolve.
ETF_TICKERS = {
    "spy": "SPY",
    "qqq": "QQQ",
    "voo": "VOO",
    "vti": "VTI",
    "arkk": "ARKK",
    "dia": "DIA",
    "iwm": "IWM",
    "vgt": "VGT",
    "xlk": "XLK",
    "gld": "GLD",
    "sqqq": "SQQQ",
    "tqqq": "TQQQ",
    "schd": "SCHD",
    "vxus": "VXUS",
}

_KNOWN_TICKERS = frozenset(COMPANY_TO_TICKER.values()) | frozenset(
    ETF_TICKERS.values()
)


class SymbolResolutionError(ValueError):
    """Raised when a question cannot be resolved to a ticker."""


def resolve_symbol(question: str) -> str:
    """Resolve a question to an uppercase ticker symbol (backward compat).

    Deterministic, no AI, no network. Raises SymbolResolutionError for
    anything else.
    """
    resolved = resolve_entity(question)
    if resolved is None or resolved[2] is None:
        raise SymbolResolutionError(
            f"Could not resolve a symbol from {question!r}. "
            "Try a ticker ($NVDA) or a company name (Nvidia)."
        )
    return resolved[2]


def resolve_entity(question: str) -> tuple[str, str | None, str | None] | None:
    """Deterministically resolve a question to (intent, entity, symbol).

    intent ∈ {"stock", "company", "etf"}. Returns None when the question
    is not deterministically resolvable (caller falls back to AI).
    """
    q = (question or "").strip()
    if not q:
        return None

    # 1. Explicit $TICKER
    m = re.search(r"\$([A-Za-z]{1,5})\b", q)
    if m:
        ticker = m.group(1).upper()
        intent = "etf" if ticker in ETF_TICKERS.values() else "stock"
        return (intent, ticker, ticker)

    lower = q.lower()

    # 2. Company name → ticker
    for name, ticker in COMPANY_TO_TICKER.items():
        if re.search(rf"\b{re.escape(name)}\b", lower):
            return ("company", name, ticker)

    # 3. ETF ticker mention (bare or lowercase, e.g. "qqq", "spy")
    for name, ticker in ETF_TICKERS.items():
        if re.search(rf"\b{re.escape(name)}\b", lower):
            return ("etf", ticker, ticker)

    # 4. Bare known ticker (uppercase token matching a known ticker)
    for token in re.findall(r"\b[A-Z]{2,5}\b", q):
        if token in _KNOWN_TICKERS:
            intent = "etf" if token in ETF_TICKERS.values() else "stock"
            return (intent, token, token)

    return None
