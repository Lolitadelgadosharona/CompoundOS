"""Sprint 006 Slice B — AI Model Provider abstraction.

Provider-neutral interface. V1 implements DeepSeek adapter only.
OpenAI/Anthropic adapters require separate Owner authorization.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from apps.api.services.credential_manager import get_api_key

# ═══════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ProviderResponse:
    """Normalized provider response."""
    raw_text: str
    parsed_json: Optional[dict[str, Any]] = None
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    duration_ms: int = 0


@dataclass
class ProviderConfig:
    """Configuration for a provider call."""
    model: str = "deepseek-chat"
    temperature: float = 0.0
    max_output_tokens: int = 8000
    timeout_seconds: int = 120
    extra_params: dict[str, Any] = field(default_factory=dict)


class ProviderError(Exception):
    """Raised when a provider call fails."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    """Raised on connection timeout."""

    def __init__(self, message: str = "Provider connection timed out."):
        super().__init__(message, retryable=True)


class ProviderRateLimitError(ProviderError):
    """Raised on HTTP 429."""

    def __init__(self, message: str = "Provider rate limit exceeded."):
        super().__init__(message, retryable=True)


class ProviderServerError(ProviderError):
    """Raised on transient 5xx."""

    def __init__(self, message: str = "Provider server error."):
        super().__init__(message, retryable=True)


# ═══════════════════════════════════════════════════════════════════════════
# Abstract provider interface
# ═══════════════════════════════════════════════════════════════════════════


class AIModelProvider(ABC):
    """Abstract interface for LLM providers.

    V1: DeepSeek only.  OpenAI/Anthropic require separate authorization.
    """

    @abstractmethod
    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Optional[ProviderConfig] = None,
    ) -> ProviderResponse:
        """Make a single structured call to the provider.

        Args:
            system_prompt: System-level instructions (role definitions, output schema)
            user_prompt: User-level content (evidence packet + proposal)
            config: Optional provider configuration

        Returns:
            ProviderResponse with raw_text and metadata

        Raises:
            ProviderTimeoutError: Connection timeout (retryable)
            ProviderRateLimitError: HTTP 429 (retryable)
            ProviderServerError: Transient 5xx (retryable)
            ProviderError: Non-retryable failure (4xx, auth, schema, etc.)
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...


# ═══════════════════════════════════════════════════════════════════════════
# DeepSeek adapter
# ═══════════════════════════════════════════════════════════════════════════


class DeepSeekProvider(AIModelProvider):
    """DeepSeek API adapter.

    Uses the DeepSeek chat completions endpoint.
    API key from credential_manager.
    """

    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def _ensure_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return get_api_key("deepseek")

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Optional[ProviderConfig] = None,
    ) -> ProviderResponse:
        cfg = config or ProviderConfig()
        api_key = self._ensure_api_key()

        payload = {
            "model": cfg.model,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **cfg.extra_params,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        import urllib.error
        import urllib.request

        start = time.monotonic()
        try:
            req = urllib.request.Request(
                self.BASE_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=cfg.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            status = e.code
            if status == 429:
                raise ProviderRateLimitError()
            if 500 <= status < 600:
                raise ProviderServerError(f"Provider HTTP {status}")
            raise ProviderError(f"Provider HTTP {status}: {e.reason}", retryable=False)
        except OSError as e:
            raise ProviderTimeoutError(f"Connection failed: {e}")
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)

        choice = body.get("choices", [{}])[0]
        raw_text = choice.get("message", {}).get("content", "")
        usage = body.get("usage", {})

        return ProviderResponse(
            raw_text=raw_text,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            model=body.get("model", cfg.model),
            duration_ms=duration_ms,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Fake provider for deterministic testing
# ═══════════════════════════════════════════════════════════════════════════


class FakeProvider(AIModelProvider):
    """Deterministic fake provider for testing.

    Returns a pre-configured response.  Never calls an external API.
    """

    def __init__(
        self,
        response_text: str = "",
        response_json: Optional[dict[str, Any]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        raise_error: Optional[Exception] = None,
    ):
        self._response_text = response_text
        self._response_json = response_json
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._raise_error = raise_error

    @property
    def provider_name(self) -> str:
        return "fake"

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        config: Optional[ProviderConfig] = None,
    ) -> ProviderResponse:
        if self._raise_error:
            raise self._raise_error
        return ProviderResponse(
            raw_text=self._response_text,
            parsed_json=self._response_json,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            model="fake-model",
            duration_ms=1,
        )
