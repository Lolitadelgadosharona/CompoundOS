"""CIO Query Understanding Layer (PE-002.2a).

Understands a natural-language investment question via a hybrid:
  1. deterministic entity resolution (ticker / company / ETF)
  2. deterministic portfolio-intent keyword detection
  3. governed AI-assisted intent classification (fail-closed)

The AI only ever outputs intent + entity + confidence — never a ticker,
never a buy/sell recommendation, never a position size. Any entity the AI
produces must pass deterministic verification before a symbol is assigned.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from apps.api.services.symbol_resolver import resolve_entity

# ── Enums ─────────────────────────────────────────────────────────────────


class QueryIntent(str, Enum):
    STOCK = "stock"
    COMPANY = "company"
    ETF = "etf"
    PORTFOLIO = "portfolio"
    THEME = "theme"
    MACRO = "macro"


class QueryRoute(str, Enum):
    RESEARCH = "research"
    PORTFOLIO = "portfolio"
    THEME = "theme"
    MACRO = "macro"


class QueryConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class CIOQueryIntent:
    intent: QueryIntent
    entity: str | None
    symbol: str | None
    confidence: QueryConfidence
    route: QueryRoute


class CIOQueryError(ValueError):
    """Raised when a question cannot be understood (fail-closed)."""


# ── Deterministic portfolio intent ─────────────────────────────────────────

_PORTFOLIO_KEYWORDS = (
    "my portfolio", "portfolio", "rebalance", "rebalancing", "allocation",
    "my holdings", "my cash", "net worth", "how risky", "my risk",
    "concentration",
)


def _looks_like_portfolio(question: str) -> bool:
    lower = (question or "").lower()
    return any(k in lower for k in _PORTFOLIO_KEYWORDS)


# ── AI-assisted classification ─────────────────────────────────────────────

_QUERY_SYSTEM = (
    "You are the query-understanding layer for CompoundOS. Classify the "
    "user's investment question. Return ONLY structured JSON with: thesis "
    "(a one-line summary of the classification), intent (one of stock, "
    "company, etf, portfolio, theme, macro), entity (the company/ETF/theme "
    "text, or null), confidence (high/medium/low). Do NOT output a ticker "
    "symbol, a buy/sell recommendation, or a position size."
)


def _ai_classify(session: Session, question: str) -> CIOQueryIntent:
    """Classify intent via the governed executor (fail-closed).

    Reuses the existing "synthesis" perspective so no new prompt/migration
    is required (the prompt_templates CHECK constraint only allows the 7
    seeded perspectives). The classification output includes a "thesis"
    summary to satisfy the synthesis validator, alongside intent/entity/
    confidence. No bypass — PermissionGate + PromptGovernor + CostTracker
    all apply.
    """
    from apps.api.services.research_pipeline_factory import (
        build_governed_executor,
    )

    try:
        executor = build_governed_executor()
        result = executor.execute(
            session,
            None,
            "synthesis",
            system_prompt=_QUERY_SYSTEM,
            user_prompt=f"Classify this investment question: {question}",
            caller="ai",
        )
    except Exception as exc:  # noqa: BLE001 — fail closed on any layer
        raise CIOQueryError(
            f"Could not understand the question ({exc.__class__.__name__})"
        ) from exc

    parsed = result.validated if result is not None else None
    if not isinstance(parsed, dict):
        raise CIOQueryError("Could not understand the question")

    intent_str = str(parsed.get("intent", "")).lower()
    entity = parsed.get("entity")
    confidence_str = str(parsed.get("confidence", "low")).lower()

    try:
        intent = QueryIntent(intent_str)
    except ValueError:
        raise CIOQueryError("Could not understand the question")
    try:
        confidence = QueryConfidence(confidence_str)
    except ValueError:
        confidence = QueryConfidence.LOW

    return _route_intent(session, intent, entity, confidence)


def _route_intent(
    session: Session,
    intent: QueryIntent,
    entity: str | None,
    confidence: QueryConfidence,
) -> CIOQueryIntent:
    """Map an intent + entity to a route, verifying the entity first."""
    if intent in (QueryIntent.STOCK, QueryIntent.COMPANY, QueryIntent.ETF):
        symbol = _verify_entity(entity)
        if symbol is None:
            raise CIOQueryError(
                f"Could not verify '{entity}' as a known company or ETF"
            )
        return CIOQueryIntent(
            intent=intent, entity=entity, symbol=symbol,
            confidence=confidence, route=QueryRoute.RESEARCH,
        )
    if intent == QueryIntent.PORTFOLIO:
        return CIOQueryIntent(
            intent=intent, entity=entity, symbol=None,
            confidence=confidence, route=QueryRoute.PORTFOLIO,
        )
    if intent == QueryIntent.THEME:
        return CIOQueryIntent(
            intent=intent, entity=entity, symbol=None,
            confidence=confidence, route=QueryRoute.THEME,
        )
    if intent == QueryIntent.MACRO:
        return CIOQueryIntent(
            intent=intent, entity=entity, symbol=None,
            confidence=confidence, route=QueryRoute.MACRO,
        )
    raise CIOQueryError("Could not understand the question")


def _verify_entity(entity: str | None) -> str | None:
    """Verify an AI-produced entity against the deterministic resolver.

    The LLM never creates a ticker directly — the entity (a company/ETF
    name) must map through resolve_entity. Returns the symbol or None.
    """
    if not entity or not str(entity).strip():
        return None
    resolved = resolve_entity(str(entity))
    if resolved is None:
        return None
    return resolved[2]


# ── Public entrypoint ──────────────────────────────────────────────────────


def understand_query(session: Session, question: str) -> CIOQueryIntent:
    """Understand a question → CIOQueryIntent (hybrid, fail-closed)."""
    q = (question or "").strip()
    if not q:
        raise CIOQueryError("Question is empty")

    # 1. Portfolio intent (deterministic)
    if _looks_like_portfolio(q):
        return CIOQueryIntent(
            intent=QueryIntent.PORTFOLIO, entity=None, symbol=None,
            confidence=QueryConfidence.HIGH, route=QueryRoute.PORTFOLIO,
        )

    # 2. Deterministic entity resolution (ticker / company / ETF)
    resolved = resolve_entity(q)
    if resolved is not None:
        intent_str, entity, symbol = resolved
        return CIOQueryIntent(
            intent=QueryIntent(intent_str), entity=entity, symbol=symbol,
            confidence=QueryConfidence.HIGH, route=QueryRoute.RESEARCH,
        )

    # 3. AI-assisted classification (governed, fail-closed)
    return _ai_classify(session, q)
