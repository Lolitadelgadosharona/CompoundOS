"""Deterministic symbol resolution — no AI (PE-002 Slice A).

Resolve a natural-language investment question to a ticker symbol using
only regex + a curated company-name map. Unknown input raises a clear
error (the UI can prompt the user to rephrase with a ticker or name).
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
}

_KNOWN_TICKERS = frozenset(COMPANY_TO_TICKER.values())


class SymbolResolutionError(ValueError):
    """Raised when a question cannot be resolved to a ticker."""


def resolve_symbol(question: str) -> str:
    """Resolve a question to an uppercase ticker symbol.

    Deterministic, no AI, no network. Resolution order:
      1. explicit ``$TICKER`` token
      2. company name (Nvidia → NVDA)
      3. bare known ticker (NVDA, AAPL, …)
    Raises SymbolResolutionError for anything else.
    """
    q = (question or "").strip()
    if not q:
        raise SymbolResolutionError("Question is empty")

    # 1. Explicit $TICKER
    m = re.search(r"\$([A-Za-z]{1,5})\b", q)
    if m:
        return m.group(1).upper()

    lower = q.lower()

    # 2. Company name → ticker
    for name, ticker in COMPANY_TO_TICKER.items():
        if re.search(rf"\b{re.escape(name)}\b", lower):
            return ticker

    # 3. Bare known ticker (uppercase token matching a known ticker)
    for token in re.findall(r"\b[A-Z]{2,5}\b", q):
        if token in _KNOWN_TICKERS:
            return token

    raise SymbolResolutionError(
        f"Could not resolve a symbol from {question!r}. "
        "Try a ticker ($NVDA) or a company name (Nvidia)."
    )
