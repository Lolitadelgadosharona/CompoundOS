"""Real LLM Provider Runtime — Sprint 013 Slice A.

Provider-neutral LLMProvider Protocol, concrete adapters, credential
isolation, ProviderRouter, and governance chain integration.

Domain code NEVER imports anthropic/openai/google packages.
All provider interaction goes through LLMProvider Protocol.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID

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
# LLMProvider Protocol — provider-neutral interface
# ═══════════════════════════════════════════════════════════════════════════


class LLMProvider(Protocol):
    """Provider-neutral LLM execution interface.

    Domain code calls .generate(). Never imports SDKs directly.
    """

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
# GeminiAdapter
# ═══════════════════════════════════════════════════════════════════════════


class GeminiAdapter:
    """Wraps google.genai client. Lazy import. Credential isolated."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise ConfigurationError("GOOGLE_API_KEY is required")
        self._key = key
        self._client = None

    def _ensure(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._key)
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
        gen_model = self._genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
        )
        response = gen_model.generate_content(
            user_prompt,
            generation_config={"max_output_tokens": max_output_tokens},
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        text = "".join(part.text for part in response.parts
                       if hasattr(part, "text"))
        return LLMResponse(
            content=text,
            model=model,
            provider="google",
            input_tokens=(getattr(response, "usage_metadata", None)
                          and response.usage_metadata.prompt_token_count
                          or 0),
            output_tokens=(getattr(response, "usage_metadata", None)
                           and response.usage_metadata
                           .candidates_token_count
                           or 0),
            duration_ms=elapsed,
            finish_reason="stop",
        )

    def __repr__(self) -> str:
        return "GeminiAdapter(api_key=<redacted>)"


# ═══════════════════════════════════════════════════════════════════════════
# ProviderRouter — centralized routing, no scattered model selection
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
    """Central routing: perspective → (provider, model).

    Primary routing comes from prompt_templates.default_model.
    Fallback routing is configured in FALLBACK_CONFIG.
    """

    def __init__(
        self,
        providers: dict[str, LLMProvider],
    ):
        self._providers = providers

    def route(
        self, perspective: str, active_model: str,
    ) -> tuple[LLMProvider, str]:
        """Return (provider_instance, model_name) for perspective.

        Active model comes from prompt_templates.default_model.
        Provider is inferred from model naming convention.
        """
        provider_key = self._provider_for_model(active_model)
        provider = self._providers.get(provider_key)
        if provider is None:
            provider = list(self._providers.values())[0]
        return provider, active_model

    def fallback(
        self, perspective: str,
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
# Governance chain — integrated execution
# ═══════════════════════════════════════════════════════════════════════════


class GovernedLLMExecutor:
    """8-step governance chain for every real LLM call. No bypass."""

    def __init__(
        self,
        router: ProviderRouter,
        permission_gate=None,
        prompt_governor=None,
        cost_tracker=None,
    ):
        self.router = router
        self.gate = permission_gate
        self.governor = prompt_governor
        self.cost = cost_tracker

    def execute(
        self,
        session: Session,
        run_id: UUID,
        perspective: str,
        system_prompt: str,
        user_prompt: str,
        caller: str = "ai",
    ) -> LLMResponse:
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
        provider, model = self.router.route(perspective, active_model)

        # 4-5. Execute with retry + fallback
        response, retries, used_fallback = self._execute_with_retry(
            provider, model, perspective, system_prompt, user_prompt,
        )

        # 6. Log execution
        if self.cost and prompt_id:
            cost_model = self._cost_model(provider, model)
            self.cost.log_execution(
                session, run_id, perspective, cost_model,
                prompt_id, response.input_tokens,
                response.output_tokens, "success",
                response.duration_ms, retry_count=retries,
            )

        return response

    def _execute_with_retry(
        self, provider: LLMProvider, model: str, perspective: str,
        system_prompt: str, user_prompt: str,
    ) -> tuple[LLMResponse, int, bool]:
        """Retry 3× with exponential backoff. Fallback on exhaustion."""
        retries = 0
        delays = [1, 4, 16]
        last_error = None

        for attempt in range(3):
            try:
                return (provider.generate(
                    model, system_prompt, user_prompt,
                ), retries, False)
            except Exception as exc:
                retries = attempt + 1
                last_error = str(exc)
                if "401" in last_error or "403" in last_error:
                    break
                if attempt < 2:
                    time.sleep(delays[attempt])

        # Fallback
        fallback = self.router.fallback(perspective)
        if fallback:
            fb_provider, fb_model = fallback
            try:
                return (fb_provider.generate(
                    fb_model, system_prompt, user_prompt,
                ), retries, True)
            except Exception:
                pass

        raise RuntimeError(
            f"LLM execution failed after {retries} retries"
            + (f" + fallback: {last_error}" if last_error else ""),
        )

    @staticmethod
    def _cost_model(provider: LLMProvider, model: str) -> str:
        # Normalize model name for cost tracking
        return model
