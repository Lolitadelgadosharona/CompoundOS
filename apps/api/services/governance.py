"""AI Governance Layer — Sprint 012 Slice D.

PermissionGate, prompt enforcement, action matrix. Single source of truth.
No scattered permission checks. No hardcoded rules across services.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


class ActionClassification(Enum):
    AUTO = "auto"
    OWNER = "owner"
    NEVER = "never"


@dataclass(frozen=True)
class Action:
    name: str
    classification: ActionClassification
    description: str


# ═══════════════════════════════════════════════════════════════════════════
# AI Action Matrix — single source of truth (OD-12-5)
# ═══════════════════════════════════════════════════════════════════════════


class ActionMatrix:
    """Central registry of ALL AI actions and their classifications."""

    FETCH_MARKET = Action("fetch_market_data", ActionClassification.AUTO,
                          "Retrieve market data from providers")
    LOAD_PORTFOLIO = Action("load_portfolio_data", ActionClassification.AUTO,
                            "Read portfolio positions and accounts")
    LOAD_POLICY = Action("load_policy_data", ActionClassification.AUTO,
                         "Read investment policy rules")
    LOAD_GUARDIAN = Action("load_guardian_data", ActionClassification.AUTO,
                           "Read guardian event status")
    EXECUTE_LLM = Action("execute_llm_call", ActionClassification.AUTO,
                         "Execute LLM perspective analysis")
    GENERATE_MEMO = Action("generate_memo", ActionClassification.AUTO,
                           "Synthesize perspectives into investment memo")
    CALCULATE_CONFIDENCE = Action("calculate_confidence",
                                  ActionClassification.AUTO,
                                  "Compute confidence score")
    LOG_EXECUTION = Action("log_execution", ActionClassification.AUTO,
                           "Record LLM execution metrics")
    CREATE_IDEA = Action("create_idea", ActionClassification.OWNER,
                         "Create new investment idea")
    REQUEST_REVIEW = Action("request_review", ActionClassification.OWNER,
                            "Request committee review")
    APPROVE_INVESTMENT = Action("approve_investment",
                                ActionClassification.OWNER,
                                "Approve investment decision")
    START_RESEARCH = Action("start_research", ActionClassification.OWNER,
                            "Start AI research execution")
    MODIFY_POLICY = Action("modify_policy", ActionClassification.NEVER,
                           "Modify investment policy rules")
    EXECUTE_TRADE = Action("execute_trade", ActionClassification.NEVER,
                           "Execute trade or order")
    CONNECT_BROKER = Action("connect_broker", ActionClassification.NEVER,
                            "Connect to external broker")

    _ALL: dict[str, Action] = {
        a.name: a for a in [
            FETCH_MARKET, LOAD_PORTFOLIO, LOAD_POLICY, LOAD_GUARDIAN,
            EXECUTE_LLM, GENERATE_MEMO, CALCULATE_CONFIDENCE, LOG_EXECUTION,
            CREATE_IDEA, REQUEST_REVIEW, APPROVE_INVESTMENT, START_RESEARCH,
            MODIFY_POLICY, EXECUTE_TRADE, CONNECT_BROKER,
        ]
    }

    @classmethod
    def get(cls, name: str) -> Action:
        a = cls._ALL.get(name)
        if a is None:
            raise ValueError(f"Unknown action: {name}")
        return a

    @classmethod
    def all_auto(cls) -> list[Action]:
        return [a for a in cls._ALL.values()
                if a.classification == ActionClassification.AUTO]

    @classmethod
    def all_owner(cls) -> list[Action]:
        return [a for a in cls._ALL.values()
                if a.classification == ActionClassification.OWNER]

    @classmethod
    def all_never(cls) -> list[Action]:
        return [a for a in cls._ALL.values()
                if a.classification == ActionClassification.NEVER]


# ═══════════════════════════════════════════════════════════════════════════
# PermissionGate
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""
    action: Optional[Action] = None


class PermissionGate:
    """Central permission enforcement. Single entry point for ALL checks."""

    @staticmethod
    def check(action_name: str, caller: str = "ai") -> PermissionResult:
        """Check if caller is permitted to perform action.

        Args:
            action_name: Action from ActionMatrix (e.g. 'execute_llm_call')
            caller: 'owner' or 'ai' (default)

        Returns:
            PermissionResult with allowed=True/False and reason.
        """
        try:
            action = ActionMatrix.get(action_name)
        except ValueError:
            return PermissionResult(allowed=False,
                                    reason=f"Unknown action: {action_name}")

        if action.classification == ActionClassification.NEVER:
            return PermissionResult(
                allowed=False, action=action,
                reason=f"Action '{action_name}' is NEVER permitted",
            )

        if (action.classification == ActionClassification.OWNER
                and caller != "owner"):
            return PermissionResult(
                allowed=False, action=action,
                reason=f"Action '{action_name}' requires Owner authorization",
            )

        return PermissionResult(allowed=True, action=action)


# ═══════════════════════════════════════════════════════════════════════════
# Prompt enforcement
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class PromptValidation:
    valid: bool
    prompt_id: Optional[UUID] = None
    prompt_version: int = 1
    default_model: Optional[str] = None
    error: Optional[str] = None


class PromptGovernor:
    """Hard enforcement: every LLM call requires active prompt (OD-12-D-2)."""

    @staticmethod
    def require_active(session: Session, perspective: str) -> PromptValidation:
        row = session.execute(
            text(
                "SELECT id, version, default_model FROM prompt_templates"
                " WHERE perspective = :p AND status = 'active'"
            ),
            {"p": perspective},
        ).fetchone()

        if row is None:
            return PromptValidation(
                valid=False,
                error=f"No active prompt for perspective '{perspective}'",
            )

        return PromptValidation(
            valid=True, prompt_id=row[0],
            prompt_version=row[1] or 1,
            default_model=row[2],
        )


# ═══════════════════════════════════════════════════════════════════════════
# Cost tracking
# ═══════════════════════════════════════════════════════════════════════════


# Pricing per 1000 tokens (input, output)
MODEL_PRICING = {
    "anthropic/claude-sonnet-4": (0.003, 0.015),
    "openai/gpt-4o": (0.0025, 0.010),
}


class CostTracker:
    """Log-only cost tracking. No blocking, no budget enforcement in V1."""

    @staticmethod
    def estimate(model: str, input_tokens: int,
                 output_tokens: int) -> float:
        prices = MODEL_PRICING.get(model, (0.005, 0.015))
        cost = (input_tokens / 1000 * prices[0]
                + output_tokens / 1000 * prices[1])
        return round(cost, 6)

    @staticmethod
    def log_execution(session: Session, run_id: UUID, perspective: str,
                      model: str, prompt_template_id: UUID,
                      input_tokens: int, output_tokens: int,
                      status: str, duration_ms: int,
                      retry_count: int = 0,
                      error: Optional[str] = None) -> UUID:
        """Write a complete llm_execution_log entry."""
        eid = uuid4()
        now = datetime.now(timezone.utc)
        cost = CostTracker.estimate(model, input_tokens, output_tokens)

        session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, run_id, prompt_template_id, perspective, model,"
                " input_tokens, output_tokens, cost_estimate,"
                " cost_currency, retry_count, status, duration_ms,"
                " error_message, started_at, completed_at)"
                " VALUES (:id, :rid, :ptid, :p, :m, :it, :ot, :cost,"
                " 'USD', :rc, :st, :dur, :err, :now, :now)"
            ),
            {
                "id": eid, "rid": run_id, "ptid": prompt_template_id,
                "p": perspective, "m": model, "it": input_tokens,
                "ot": output_tokens, "cost": cost, "rc": retry_count,
                "st": status, "dur": duration_ms, "err": error,
                "now": now,
            },
        )
        return eid
