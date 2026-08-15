"""Cost Tracking — token-based cost estimation (M5-007).

Fail-open: a cost error must never fail the research run. Cost is
estimated from per-model input/output pricing (USD per 1k tokens).
"""

from __future__ import annotations

from typing import Optional

# (input price per 1k tokens, output price per 1k tokens) in USD.
# Includes the alias-resolved model names (e.g. claude-sonnet-4.6) so the
# canonical name and the provider-facing name both price correctly.
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4": (0.003, 0.015),
    "claude-sonnet-4.6": (0.003, 0.015),
    "claude-sonnet-4-6": (0.003, 0.015),
    "gpt-4o": (0.0025, 0.010),
    "openai/gpt-4o": (0.0025, 0.010),
    "gemini-2.5-pro": (0.00125, 0.005),
}

_DEFAULT_PRICE: tuple[float, float] = (0.005, 0.015)


class CostTracker:
    """Estimates and records LLM call cost. Advisory — never fatal."""

    def __init__(self, pricing: Optional[dict[str, tuple[float, float]]] = None):
        self._pricing = pricing or DEFAULT_PRICING

    def estimate(self, model: str,
                 input_tokens: Optional[int],
                 output_tokens: Optional[int]) -> float:
        """Estimate USD cost from token counts. Unknown model → default.

        Coerces None token counts to 0 so a missing usage value cannot
        raise (fail-open).
        """
        inp = int(input_tokens or 0)
        out = int(output_tokens or 0)
        in_price, out_price = self._pricing.get(model or "", _DEFAULT_PRICE)
        return round(inp / 1000 * in_price + out / 1000 * out_price, 6)
