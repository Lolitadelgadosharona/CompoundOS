"""Prompt Governance — versioned prompt resolution (M5-007).

Resolves the active prompt template for a perspective and seeds the
default templates. Fail-closed: an execution must NOT proceed without
an active prompt version.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class PromptVersionResult:
    """Outcome of an active-prompt lookup."""

    valid: bool
    prompt_id: Optional[UUID] = None
    version: Optional[int] = None
    default_model: Optional[str] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Default prompt templates — seeded once, idempotently.
#
# default_model matches the existing routing in research_intelligence.py:
#   claude-sonnet-4 → value / risk / policy / synthesis
#   gpt-4o         → growth / macro / portfolio_fit
# The system/user templates are descriptive seeds; the live path still
# builds prompts inline (DB-driven prompt text is a later slice).
# ═══════════════════════════════════════════════════════════════════════════

_SYSTEM = (
    "You are the {perspective} analyst for CompoundOS, an AI-assisted "
    "family office investment research system. Analyze the evidence and "
    "return structured JSON with: perspective, thesis, conviction_score "
    "(1-10), key_metrics."
)

_SYNTHESIS_SYSTEM = (
    "You are the synthesis analyst for CompoundOS. Combine the six "
    "perspective analyses and the evidence into a single investment memo. "
    "Return structured JSON with: thesis, evidence, bull_case, bear_case, "
    "risks, recommendation (BUY/HOLD/SELL), confidence."
)

DEFAULT_PROMPTS: dict[str, tuple[str, str, str]] = {
    # perspective → (default_model, system_prompt, user_prompt_template)
    "value": ("claude-sonnet-4", _SYSTEM.format(perspective="value"),
              "Analyze from a value perspective using the provided evidence."),
    "growth": ("gpt-4o", _SYSTEM.format(perspective="growth"),
               "Analyze from a growth perspective using the provided evidence."),
    "risk": ("claude-sonnet-4", _SYSTEM.format(perspective="risk"),
             "Analyze from a risk perspective using the provided evidence."),
    "macro": ("gpt-4o", _SYSTEM.format(perspective="macro"),
              "Analyze from a macro perspective using the provided evidence."),
    "policy": ("claude-sonnet-4", _SYSTEM.format(perspective="policy"),
               "Analyze from a policy perspective using the provided evidence."),
    "portfolio_fit": ("gpt-4o",
                      _SYSTEM.format(perspective="portfolio_fit"),
                      "Analyze from a portfolio-fit perspective using the "
                      "provided evidence."),
    "synthesis": ("claude-sonnet-4", _SYNTHESIS_SYSTEM,
                  "Synthesize the six perspectives into a final memo."),
}


class PromptGovernor:
    """Resolves active prompt versions. Read-only. Fails closed."""

    def require_active(self, session: Session,
                       perspective: str) -> PromptVersionResult:
        """Return the latest active prompt version for a perspective.

        Fail-closed: no active prompt → valid=False (caller must raise).
        """
        row = session.execute(
            text(
                "SELECT id, version, default_model FROM prompt_templates"
                " WHERE perspective = :p AND status = 'active'"
                " ORDER BY version DESC LIMIT 1"
            ),
            {"p": perspective},
        ).fetchone()
        if row is None:
            return PromptVersionResult(
                valid=False,
                error=f"No active prompt template for '{perspective}'",
            )
        return PromptVersionResult(
            valid=True, prompt_id=row[0], version=row[1],
            default_model=row[2],
        )

    def seed_defaults(self, session: Session) -> int:
        """Idempotently insert the default active prompt templates.

        Skips any perspective that already has an active prompt. Returns
        the number of rows inserted.
        """
        inserted = 0
        for perspective, (model, sys_prompt, user_tmpl) in \
                DEFAULT_PROMPTS.items():
            # Skip if an active prompt already exists for this perspective.
            existing = session.execute(
                text(
                    "SELECT 1 FROM prompt_templates"
                    " WHERE perspective = :p AND status = 'active' LIMIT 1"
                ),
                {"p": perspective},
            ).fetchone()
            if existing:
                continue
            result = session.execute(
                text(
                    "INSERT INTO prompt_templates"
                    " (id, perspective, version, status, purpose,"
                    "  default_model, system_prompt, user_prompt_template,"
                    "  active_at, created_at)"
                    " VALUES (:id, :p, 1, 'active', :purpose, :model,"
                    "  :sys, :tmpl, NOW(), NOW())"
                    " ON CONFLICT (perspective, version) DO NOTHING"
                ),
                {
                    "id": uuid4(), "p": perspective,
                    "purpose": f"{perspective} perspective analysis",
                    "model": model, "sys": sys_prompt, "tmpl": user_tmpl,
                },
            )
            if result.rowcount:
                inserted += result.rowcount
        return inserted
