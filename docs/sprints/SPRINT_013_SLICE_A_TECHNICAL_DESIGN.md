# Sprint 013 Slice A — Technical Design
# Real LLM Provider Runtime

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 012: COMPLETE (all 4 slices done)
> Sprint 013 Owner Decisions: ALL 8 APPROVED
> Sprint 013 Slice A: DESIGN ONLY

---

## 1. Objective

Slice A delivers the **first governed real LLM call**. It is the minimum
production-safe vertical slice that connects the existing Sprint 012
LLM runtime to real external providers while preserving every governance
guardrail built in prior sprints.

**Acceptance criteria**: CompoundOS can execute a real LLM call through
the provider abstraction, with full PromptGovernor enforcement, and
preserve complete execution provenance — all without expanding AI authority.

---

## 2. Provider Abstraction

### 2.1 LLMProvider Protocol

Domain code MUST NOT import `openai`, `anthropic`, or `google` packages.
All provider interaction goes through a single protocol:

```python
class LLMProvider(Protocol):
    """Provider-neutral LLM execution interface."""

    def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_input_tokens: int = 4000,
        max_output_tokens: int = 2000,
        **kwargs,
    ) -> LLMResponse: ...


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    finish_reason: str
    raw_response: dict  # For debugging only
```

### 2.2 Provider Registry

```python
class ProviderRouter:
    """Central routing: perspective → provider → model."""

    def __init__(self, providers: dict[str, LLMProvider]):
        self._providers = providers

    def route(self, perspective: str) -> tuple[LLMProvider, str]:
        """Returns (provider_instance, model_name) for perspective."""
        # Routing table loaded from prompt_templates.default_model
        ...
```

**Routing table** (configured, not hardcoded):

| Perspective | Provider | Model | Fallback |
|---|---|---|---|
| value | anthropic | claude-sonnet-4 | openai:gpt-4o |
| growth | anthropic | claude-sonnet-4 | openai:gpt-4o |
| risk | anthropic | claude-sonnet-4 | openai:gpt-4o |
| macro | openai | gpt-4o | anthropic:claude-sonnet-4 |
| policy | anthropic | claude-sonnet-4 | openai:gpt-4o |
| portfolio_fit | openai | gpt-4o | anthropic:claude-sonnet-4 |
| synthesis | google | gemini-2.5-pro | anthropic:claude-sonnet-4 |

---

## 3. Provider Adapters

### 3.1 AnthropicAdapter

```python
class AnthropicAdapter:
    """Wraps anthropic.Anthropic() client. Never leaks SDK types."""

    def __init__(self, api_key: str):
        self._client = None  # Lazy init
        self._api_key = api_key  # From ANTHROPIC_API_KEY env var

    def generate(self, model, system_prompt, user_prompt,
                 max_input_tokens, max_output_tokens, **kwargs) -> LLMResponse:
        # Calls self._client.messages.create()
        # Returns LLMResponse — never returns SDK Message object
```

**Credential boundary**: `api_key` is loaded from `os.environ.get("ANTHROPIC_API_KEY")`.
Fail closed: `__init__` raises `ConfigurationError` if key is empty/missing.
Key is never logged, never serialized, never returned in API responses.

### 3.2 OpenAIAdapter

Same pattern for `OPENAI_API_KEY`. Wraps `openai.OpenAI().chat.completions.create()`.

### 3.3 GeminiAdapter

Same pattern for `GEMINI_API_KEY`. Wraps `google.genai`.

### 3.4 Credential Isolation Rules

- All keys: environment variables only
- `__init__` validates key presence; raises if missing
- `__repr__` / `__str__` never expose key
- Logging: model + perspective logged; key NEVER logged
- `.env` file: in `.gitignore`, never committed
- No test fixture contains real keys

---

## 4. Governance Enforcement Chain

Every real LLM call traverses this chain — no bypass:

```
PerspectiveExecutor._execute_one(perspective, ...)
        │
        ▼
1. PermissionGate.check("execute_llm_call", caller="ai")
        │  └─ Returns: allowed=True (AUTO action)
        ▼
2. PromptGovernor.require_active(session, perspective)
        │  └─ Returns: PromptValidation(prompt_id, version, model)
        │  └─ Fails if no active prompt → run hard-fails
        ▼
3. ProviderRouter.route(perspective)
        │  └─ Returns: (provider, model)
        │  └─ Model from prompt_templates.default_model
        ▼
4. provider.generate(model, system_prompt, user_prompt)
        │  └─ AnthropicAdapter / OpenAIAdapter / GeminiAdapter
        │  └─ Returns: LLMResponse
        ▼
5. ResponseValidator.validate(response, perspective)
        │  └─ Checks JSON schema, required fields, conviction_score range
        │  └─ Invalid → retry once → mark perspective failed
        ▼
6. CostTracker.log_execution(session, run_id, perspective, ...)
        │  └─ Writes llm_execution_log row
        │  └─ Calculates cost via CostTracker.estimate()
        ▼
7. PerspectiveExecutor._store_analysis(session, ...)
        └─ Writes perspective_analyses row
```

**No bypass**: There is no code path that calls an LLM provider without
traversing steps 1-7. The governance chain is in the service layer, not
in middleware — it cannot be skipped by calling a different endpoint.

---

## 5. Provenance

Every real LLM execution produces one `perspective_analyses` row and
one `llm_execution_log` row. Together they provide complete provenance:

| Field | Source | Stored In |
|---|---|---|
| research_run_id | Pipeline orchestrator | Both tables |
| perspective | PerspectiveExecutor | Both tables |
| provider | ProviderRouter | llm_execution_log |
| model | prompt_templates.default_model | Both tables |
| prompt_template_id | PromptGovernor | llm_execution_log |
| prompt_version | PromptGovernor | perspective_analyses |
| started_at | PerspectiveExecutor | Both tables |
| completed_at | PerspectiveExecutor | Both tables |
| input_tokens | LLMResponse.input_tokens | llm_execution_log |
| output_tokens | LLMResponse.output_tokens | llm_execution_log |
| cost_estimate | CostTracker.estimate() | llm_execution_log |
| duration_ms | LLMResponse.duration_ms | llm_execution_log |
| status | PerspectiveExecutor | llm_execution_log |
| retry_count | PerspectiveExecutor | llm_execution_log |
| error_message | Exception | llm_execution_log |
| analysis (JSONB) | LLMResponse.content (parsed) | perspective_analyses |
| conviction_score | analysis.conviction_score | perspective_analyses |

---

## 6. Provider Failure Behavior

```
Primary provider call
        │
   ┌────┴────┐
   ▼         ▼
Success    Failure
   │         │
   │    ┌────┴────────────────┐
   │    ▼                     ▼
   │  401/403 (auth)      Timeout/429/5xx
   │    │                     │
   │    ▼                     ▼
   │  Fail fast          Retry (exp backoff)
   │  No retry           Max 3 attempts
   │  Log error               │
   │                      ┌───┴───┐
   │                      ▼       ▼
   │                   Success  All failed
   │                      │       │
   │                      │       ▼
   │                      │   Fallback provider
   │                      │   (route via fallback)
   │                      │       │
   │                      │   ┌───┴───┐
   │                      │   ▼       ▼
   │                      │Success  Failed
   │                      │   │       │
   │                      │   │       ▼
   │                      │   │  Mark perspective
   │                      │   │  failed
   │                      │   │  Return partial
   └──────┬───────────────┴───┘
          ▼
      Store result
      Log execution
```

**Key rules:**
- Auth failures (401/403): fail fast, no retry, no fallback
- Transient failures: retry 3× with exponential backoff (1s/4s/16s)
- After 3 primary failures: try fallback provider
- Fallback also fails: mark perspective failed
- **Never fabricate a response**

---

## 7. Testing Strategy

### 7.1 Default: Mock Providers

All tests use mock LLMProvider implementations — **never** real API calls.

```python
class MockLLMProvider:
    def generate(self, model, system_prompt, user_prompt, **kwargs):
        return LLMResponse(
            content=json.dumps({
                "perspective": "value",
                "thesis": "Mock analysis",
                "conviction_score": 7,
            }),
            model=model, provider="mock",
            input_tokens=100, output_tokens=200,
            duration_ms=100, finish_reason="stop",
            raw_response={},
        )
```

### 7.2 CI Safety

- No test loads real API keys
- CI environment has no `*_API_KEY` variables set
- Provider adapters raise `ConfigurationError` if initialized without keys
- This is verified by a dedicated test: `test_provider_fails_closed_without_key`

### 7.3 Opt-In Smoke Test

A separate `tests/smoke/` directory contains real-provider tests.
They are NOT run by default CI. Activated only via:

```bash
ENABLE_PAID_PROVIDER_TESTS=1 pytest tests/smoke/
```

This requires manual environment variable setup and explicit opt-in.

---

## 8. Database Impact

No new tables or columns. Slice A uses existing:
- `prompt_templates` (model routing via default_model)
- `llm_execution_log` (provenance)
- `perspective_analyses` (results)

---

## 9. API Impact

No new API endpoints. The existing POST /api/research/start (Sprint 012-B)
triggers the upgraded pipeline with real providers.

---

## 10. AI Authority

Slice A MUST NOT expand AI authority. Verification checklist:

| Check | Status |
|---|---|
| No investment approval code path | ✓ (unchanged from Sprint 012) |
| No policy modification code path | ✓ (unchanged) |
| No broker access code path | ✓ (never existed) |
| No trading code path | ✓ (never existed) |
| PermissionGate traversed before every LLM call | ✓ (step 1 of governance chain) |
| PromptGovernor traversed before every LLM call | ✓ (step 2) |
| All execution logged to llm_execution_log | ✓ (step 6) |

---

## 11. First Real Intelligence Milestone

Slice A is the **first real intelligence milestone** for CompoundOS.
When Slice A is complete:

✅ CompoundOS can load provider credentials from environment variables
✅ CompoundOS can initialize provider adapters (fail-closed if key missing)
✅ CompoundOS can route a perspective to the correct provider + model
✅ CompoundOS can execute a real LLM call with full governance chain
✅ CompoundOS can store structured analysis + execution provenance
✅ CompoundOS can handle provider failures with retry + fallback
✅ CompoundOS never fabricates data when providers are unavailable

**What Slice A does NOT do**: full investment memo synthesis, Alpha Vantage
integration, end-to-end research workflow. Those are Slice B/C/D.

---

## 12. Estimate

| Component | Lines | Tests |
|---|---|---|
| LLMProvider Protocol + LLMResponse | ~40 | 0 (type-checked) |
| AnthropicAdapter | ~80 | 5 |
| OpenAIAdapter | ~80 | 5 |
| GeminiAdapter | ~80 | 5 |
| ProviderRouter | ~60 | 5 |
| Governance chain integration | ~60 | 4 |
| Credential validation | ~30 | 3 |
| **Total** | **~430** | **~27** |

---

## 13. Dependencies

Sprint 013 Slice A adds optional Python packages:

```
anthropic>=0.30.0    # AnthropicAdapter
openai>=1.50.0       # OpenAIAdapter
google-genai>=0.6.0  # GeminiAdapter
```

These are declared in `requirements.txt` as optional extras.
The adapters import lazily — the package is only loaded when the
adapter is initialized, not at import time.

---

## 14. Owner Decisions Dependency

Slice A is gated on all 8 Sprint 013 Owner Decisions being approved.
All are approved as of this design phase.

No additional Slice-A-specific decisions required.
