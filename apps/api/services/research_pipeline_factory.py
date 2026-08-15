"""Research pipeline factory — the single place that builds a real pipeline.

Constructs ResearchIntelligencePipeline (the ONLY real research pipeline).
All components are injectable so tests pass mocks and production passes
real adapters. No duplicate pipeline logic lives here.
"""

from __future__ import annotations

from typing import Any, Optional

from apps.api.services.research_intelligence import (
    ConfidenceEngine,
    MemoGenerator,
    ResearchIntelligencePipeline,
)


def build_research_pipeline(
    evidence_collector: Optional[Any] = None,
    perspective_executor: Optional[Any] = None,
    memo_generator: Optional[Any] = None,
    confidence_engine: Optional[Any] = None,
) -> ResearchIntelligencePipeline:
    """Build a ResearchIntelligencePipeline.

    Any component may be injected (tests pass mocks). Omitted components
    are constructed from real production adapters.
    """
    executor = perspective_executor or _build_real_executor()
    return ResearchIntelligencePipeline(
        evidence_collector=evidence_collector or _build_real_evidence_collector(),
        perspective_executor=executor,
        memo_generator=memo_generator or MemoGenerator(executor),
        confidence_engine=confidence_engine or ConfidenceEngine(),
    )


def _build_real_executor() -> Any:
    """Construct a GovernedLLMExecutor over available provider adapters."""
    from apps.api.services.llm_provider_runtime import (
        AnthropicAdapter,
        GeminiAdapter,
        GovernedLLMExecutor,
        OpenAIAdapter,
        ProviderRouter,
    )

    providers: dict = {}
    for name, cls in (
        ("anthropic", AnthropicAdapter),
        ("openai", OpenAIAdapter),
        ("google", GeminiAdapter),
    ):
        try:
            providers[name] = cls()
        except Exception:
            # Missing credentials for this provider — skip it; routing
            # falls back to whatever is configured.
            continue
    if not providers:
        raise RuntimeError(
            "No LLM provider credentials configured "
            "(ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY)"
        )
    router = ProviderRouter(providers)
    return GovernedLLMExecutor(router)


def _build_real_evidence_collector() -> Any:
    from apps.api.services.evidence_collector_v2 import EvidenceCollector

    return EvidenceCollector()
