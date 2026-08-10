"""Real LLM Provider Runtime — Sprint 013 Slice A (Hardened).

Provider-neutral LLMProvider Protocol, concrete adapters, credential
isolation, ProviderRouter, governance chain with ResponseValidator,
and hardened failure semantics.

Domain code NEVER imports anthropic/openai/google packages.
All provider interaction goes through LLMProvider Protocol.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# ═══════════════════════════════════════════════════════════════════════════
# LLMResponse — provider-neutral response
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    finish_reason: str
    raw_response: dict = field(default_factory=dict, repr=False)


# ═══════════════════════════════════════════════════════════════════════════
# LLMProvider Protocol
# ═══════════════════════════════════════════════════════════════════════════


class LLMProvider(Protocol):
    """Provider-neutral LLM execution interface."""

    def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        ...


# ═══════════════════════════════════════════════════════════════════════════
# ConfigurationError
# ═══════════════════════════════════════════════════════════════════════════


class ConfigurationError(Exception):
    """Raised when required configuration (API key) is missing."""


# ═══════════════════════════════════════════════════════════════════════════
# AnthropicAdapter
# ═══════════════════════════════════════════════════════════════════════════


class AnthropicAdapter:
    """Wraps anthropic.Anthropic client. Lazy import. Credential isolated."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ConfigurationError("ANTHROPIC_API_KEY is required")
        self._key = key
        self._client = None

    def _ensure(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._key)

    def generate(
        self,
        model: str = "claude-sonnet-4",
        system_prompt: str = "",
        user_prompt: str = "",
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        self._ensure()
        t0 = time.monotonic()
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_output_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        return LLMResponse(
            content=msg.content[0].text,
            model=msg.model,
            provider="anthropic",
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            duration_ms=elapsed,
            finish_reason=msg.stop_reason or "stop",
        )

    def __repr__(self) -> str:
        return "AnthropicAdapter(api_key=<redacted>)"


# ═══════════════════════════════════════════════════════════════════════════
# OpenAIAdapter
# ═══════════════════════════════════════════════════════════════════════════


class OpenAIAdapter:
    """Wraps openai.OpenAI client. Lazy import. Credential isolated."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ConfigurationError("OPENAI_API_KEY is required")
        self._key = key
        self._client = None

    def _ensure(self):
        if self._client is None:
            import openai
            self._client = openai.OpenAI(api_key=self._key)

    def generate(
        self,
        model: str = "gpt-4o",
        system_prompt: str = "",
        user_prompt: str = "",
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        self._ensure()
        t0 = time.monotonic()
        completion = self._client.chat.completions.create(
            model=model,
            max_completion_tokens=max_output_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        choice = completion.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=completion.model,
            provider="openai",
            input_tokens=completion.usage.prompt_tokens,
            output_tokens=completion.usage.completion_tokens,
            duration_ms=elapsed,
            finish_reason=choice.finish_reason or "stop",
        )

    def __repr__(self) -> str:
        return "OpenAIAdapter(api_key=<redacted>)"


# ═══════════════════════════════════════════════════════════════════════════
# GeminiAdapter — uses google-genai (new SDK, no global state)
# ═══════════════════════════════════════════════════════════════════════════


class GeminiAdapter:
    """Wraps google-genai client. Lazy import. Credential isolated.

    Uses google-genai (new unified SDK). No global configure() call.
    """

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise ConfigurationError("GOOGLE_API_KEY is required")
        self._key = key
        self._client = None

    def _ensure(self):
        if self._client is None:
            import google.genai as genai  # google-genai package
            self._client = genai.Client(api_key=self._key)
            self._genai = genai

    def generate(
        self,
        model: str = "gemini-2.5-pro",
        system_prompt: str = "",
        user_prompt: str = "",
        max_output_tokens: int = 2000,
    ) -> LLMResponse:
        self._ensure()
        t0 = time.monotonic()
        response = self._client.models.generate_content(
            model=model,
            contents=user_prompt,
            config={"system_instruction": system_prompt,
                     "max_output_tokens": max_output_tokens},
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        text = "".join(part.text for part in response.candidates[0].content.parts
                       if hasattr(part, "text"))
        usage = (response.usage_metadata
                 if hasattr(response, "usage_metadata") else None)
        return LLMResponse(
            content=text,
            model=model,
            provider="google",
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            duration_ms=elapsed,
            finish_reason=str(response.candidates[0].finish_reason
                              if response.candidates else "stop"),
        )

    def __repr__(self) -> str:
        return "GeminiAdapter(api_key=<redacted>)"


# ═══════════════════════════════════════════════════════════════════════════
# ProviderRouter
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RouteConfig:
    provider: str
    model: str


FALLBACK_CONFIG: dict[str, RouteConfig] = {
    "value": RouteConfig("openai", "gpt-4o"),
    "growth": RouteConfig("openai", "gpt-4o"),
    "risk": RouteConfig("openai", "gpt-4o"),
    "macro": RouteConfig("anthropic", "claude-sonnet-4"),
    "policy": RouteConfig("openai", "gpt-4o"),
    "portfolio_fit": RouteConfig("anthropic", "claude-sonnet-4"),
    "synthesis": RouteConfig("anthropic", "claude-sonnet-4"),
}


class ProviderRouter:
    """Central routing: perspective → (provider, model)."""

    def __init__(self, providers: dict[str, LLMProvider]):
        self._providers = providers

    def route(self, perspective: str, active_model: str,
              ) -> tuple[LLMProvider, str]:
        provider_key = self._provider_for_model(active_model)
        provider = self._providers.get(provider_key)
        if provider is None:
            provider = list(self._providers.values())[0]
        return provider, active_model

    def fallback(self, perspective: str,
                 ) -> tuple[LLMProvider, str] | None:
        config = FALLBACK_CONFIG.get(perspective)
        if config is None:
            return None
        provider = self._providers.get(config.provider)
        if provider is None:
            return None
        return provider, config.model

    @staticmethod
    def _provider_for_model(model: str) -> str:
        if "claude" in model:
            return "anthropic"
        if "gpt" in model or "o1" in model or "o3" in model:
            return "openai"
        if "gemini" in model:
            return "google"
        return "anthropic"


# ═══════════════════════════════════════════════════════════════════════════
# ResponseValidator
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ValidationResult:
    valid: bool
    parsed: Optional[dict] = None
    error: Optional[str] = None


class ResponseValidator:
    """Validates LLM responses before acceptance. Hard enforcement."""

    REQUIRED_FIELDS = {"perspective", "thesis", "conviction_score"}
    SYNTHESIS_REQUIRED_FIELDS = {"thesis"}

    @staticmethod
    def validate(content: str, perspective: str) -> ValidationResult:
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return ValidationResult(
                valid=False, error="Response is not valid JSON",
            )

        if not isinstance(parsed, dict):
            return ValidationResult(
                valid=False, error="Response is not a JSON object",
            )

        required = (ResponseValidator.REQUIRED_FIELDS
                    if perspective != "synthesis"
                    else ResponseValidator.SYNTHESIS_REQUIRED_FIELDS)

        missing = required - set(parsed.keys())
        if missing:
            return ValidationResult(
                valid=False,
                error=f"Missing required fields: {', '.join(sorted(missing))}",
            )

        cs = parsed.get("conviction_score")
        if cs is not None:
            if not isinstance(cs, (int, float)):
                return ValidationResult(
                    valid=False,
                    error=f"conviction_score must be numeric, got {type(cs).__name__}",
                )
            if cs < 1 or cs > 10:
                return ValidationResult(
                    valid=False,
                    error=f"conviction_score {cs} out of range [1-10]",
                )

        return ValidationResult(valid=True, parsed=parsed)


# ═══════════════════════════════════════════════════════════════════════════
# ExecutionResult — complete execution record
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ExecutionResult:
    response: LLMResponse
    validated: dict
    actual_provider: str
    actual_model: str
    retries: int = 0
    fallback_used: bool = False
    log_id: Optional[UUID] = None


# ═══════════════════════════════════════════════════════════════════════════
# GovernedLLMExecutor — hardened governance chain
# ═══════════════════════════════════════════════════════════════════════════


class GovernedLLMExecutor:
    """7-step governance chain. No bypass.

    PermissionGate → PromptGovernor → Router → Provider
    → Validator → Logger → Store (caller responsibility).
    """

    def __init__(
        self,
        router: ProviderRouter,
        permission_gate=None,
        prompt_governor=None,
        cost_tracker=None,
        validator: Optional[ResponseValidator] = None,
    ):
        self.router = router
        self.gate = permission_gate
        self.governor = prompt_governor
        self.cost = cost_tracker
        self.validator = validator or ResponseValidator()

    def execute(
        self,
        session: Session,
        run_id: UUID,
        perspective: str,
        system_prompt: str,
        user_prompt: str,
        caller: str = "ai",
    ) -> ExecutionResult:
        # 1. PermissionGate
        if self.gate:
            result = self.gate.check("execute_llm_call", caller)
            if not result.allowed:
                raise PermissionError(result.reason)

        # 2. PromptGovernor
        prompt_id: Optional[UUID] = None
        active_model: str = "claude-sonnet-4"
        if self.governor:
            pv = self.governor.require_active(session, perspective)
            if not pv.valid:
                raise ValueError(pv.error or "No active prompt")
            prompt_id = pv.prompt_id
            active_model = pv.default_model or active_model

        # 3. ProviderRouter
        primary_provider, primary_model = self.router.route(
            perspective, active_model,
        )

        # 4. Execute with retry + fallback
        response, actual_provider, actual_model, retries, fallback = (
            self._execute_with_retry(
                primary_provider, primary_model, perspective,
                system_prompt, user_prompt,
            )
        )

        # 5. ResponseValidator
        vr = self.validator.validate(response.content, perspective)
        if not vr.valid:
            log_id = self._log_failure(
                session, run_id, perspective,
                actual_provider, actual_model,
                prompt_id, response, retries, fallback,
                f"Validation failed: {vr.error}",
            )
            raise ValueError(f"LLM response validation failed: {vr.error}")

        # 6. Logger (llm_execution_log)
        log_id = self._log_success(
            session, run_id, perspective,
            actual_provider, actual_model,
            prompt_id, response, retries, fallback,
        )

        return ExecutionResult(
            response=response,
            validated=vr.parsed or {},
            actual_provider=actual_provider,
            actual_model=actual_model,
            retries=retries,
            fallback_used=fallback,
            log_id=log_id,
        )

    def _execute_with_retry(
        self, provider: LLMProvider, model: str, perspective: str,
        system_prompt: str, user_prompt: str,
    ) -> tuple[LLMResponse, str, str, int, bool]:
        """Retry 3× with exponential backoff. Auth fails fast. Fallback on
        exhaustion."""
        retries = 0
        delays = [1, 4, 16]
        last_error = None

        for attempt in range(3):
            try:
                return (provider.generate(model, system_prompt,
                                          user_prompt),
                        provider.__class__.__name__, model, retries, False)
            except Exception as exc:
                retries = attempt + 1
                last_error = str(exc)
                # Auth failure: fail fast, no fallback
                if "401" in last_error or "403" in last_error:
                    raise RuntimeError(
                        f"Auth failure ({last_error[:80]})"
                    ) from exc
                # Rate limit: respect Retry-After if present
                if "429" in last_error:
                    wait = _parse_retry_after(exc)
                    if wait and attempt < 2:
                        time.sleep(wait)
                        continue
                if attempt < 2:
                    time.sleep(delays[attempt])

        # Fallback
        fb = self.router.fallback(perspective)
        if fb:
            fb_provider, fb_model = fb
            try:
                resp = fb_provider.generate(fb_model, system_prompt,
                                            user_prompt)
                return (resp,
                        fb_provider.__class__.__name__,
                        fb_model, retries, True)
            except Exception:
                pass

        raise RuntimeError(
            f"LLM execution failed after {retries} retries"
            + (f" + fallback: {last_error}" if last_error else ""),
        )

    def _log_success(self, session, run_id, perspective,
                     actual_provider, actual_model,
                     prompt_id, response, retries, fallback):
        if not self.cost or not prompt_id:
            return None
        from uuid import uuid4 as _u4
        eid = _u4()
        now = datetime.now(timezone.utc)
        cost_est = _estimate_cost(actual_model,
                                  response.input_tokens,
                                  response.output_tokens)
        session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, run_id, prompt_template_id, perspective, model,"
                " input_tokens, output_tokens, cost_estimate,"
                " cost_currency, retry_count, status, duration_ms,"
                " started_at, completed_at)"
                " VALUES (:id, :rid, :ptid, :p, :m, :it, :ot, :cost,"
                " 'USD', :rc, 'success', :dur, :now, :now)"
            ),
            {"id": eid, "rid": run_id, "ptid": prompt_id,
             "p": perspective, "m": actual_model,
             "it": response.input_tokens, "ot": response.output_tokens,
             "cost": cost_est, "rc": retries, "dur": response.duration_ms,
             "now": now},
        )
        return eid

    def _log_failure(self, session, run_id, perspective,
                     actual_provider, actual_model,
                     prompt_id, response, retries, fallback, error_msg):
        if not self.cost or not prompt_id:
            return None
        from uuid import uuid4 as _u4
        eid = _u4()
        now = datetime.now(timezone.utc)
        session.execute(
            text(
                "INSERT INTO llm_execution_log"
                " (id, run_id, prompt_template_id, perspective, model,"
                " input_tokens, output_tokens, cost_estimate,"
                " cost_currency, retry_count, status, duration_ms,"
                " error_message, started_at, completed_at)"
                " VALUES (:id, :rid, :ptid, :p, :m, :it, :ot, 0,"
                " 'USD', :rc, 'failure', :dur, :err, :now, :now)"
            ),
            {"id": eid, "rid": run_id, "ptid": prompt_id,
             "p": perspective, "m": actual_model,
             "it": response.input_tokens if response else 0,
             "ot": response.output_tokens if response else 0,
             "rc": retries, "dur": response.duration_ms if response else 0,
             "err": error_msg, "now": now},
        )
        return eid


def _parse_retry_after(exc: Exception) -> Optional[float]:
    """Extract Retry-After value from exception if present."""
    try:
        if hasattr(exc, "response") and exc.response is not None:
            headers = getattr(exc.response, "headers", {})
            val = headers.get("Retry-After") or headers.get("retry-after")
            if val:
                return float(val)
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Cost estimation
# ═══════════════════════════════════════════════════════════════════════════


MODEL_PRICING = {
    "claude-sonnet-4": (0.003, 0.015),
    "gpt-4o": (0.0025, 0.010),
    "gemini-2.5-pro": (0.00125, 0.005),
}


def _estimate_cost(model: str, input_tokens: int,
                   output_tokens: int) -> float:
    prices = MODEL_PRICING.get(model, (0.005, 0.015))
    return round(input_tokens / 1000 * prices[0]
                 + output_tokens / 1000 * prices[1], 6)
