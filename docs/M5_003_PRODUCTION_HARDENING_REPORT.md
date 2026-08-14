# M5-003 Production Hardening Report

CompoundOS — Research Pipeline Reliability
2026-08-14

Goal: promote the Research Pipeline from "validation works" to
"reliable for continued operation", based strictly on problems exposed by the
FULL_AAPL_SIX_PERSPECTIVE_REPORT real-run validation.

---

## 1. Summary

Four problems were addressed. Three are code fixes with tests (JSON robustness,
model provenance, memo token cap); one is an analysis deliverable (runtime shim
boundary). One additive, non-destructive migration was introduced. No full
Governance Layer was implemented — per the scope boundary it is only recorded
as a gap.

| Problem | Status | Type |
|---------|--------|------|
| P1 ResponseValidator JSON robustness | FIXED | code + tests |
| P2 Model provenance correctness | FIXED | code + migration + tests |
| P3 Memo synthesis token limit | FIXED | code + tests |
| P4 Runtime shim boundary | DOCUMENTED | analysis (§7/§8) |

---

## 2. Problems Fixed

### P1 — ResponseValidator JSON robustness
`ResponseValidator.validate` previously called `json.loads(content)` directly,
rejecting real Claude/GPT-4o responses that wrap JSON in markdown fences or
prose. Added `_extract_json()` which:
- returns pure JSON verbatim,
- unwraps ```json ... ``` fences (any language tag, case-insensitive),
- strips surrounding prose by locating the first `{` / last `}`.

Schema validation, required-field validation, conviction-score type/range
validation, and fail-closed behavior are unchanged. When no valid JSON object
can be extracted, validation fails (`valid=False`).

### P2 — Model provenance correctness
Root cause: `GovernedLLMExecutor.execute()` hardcoded `active_model =
"claude-sonnet-4"` whenever no PromptGovernor was present, so the growth
perspective routed to anthropic/claude-sonnet-4 first and only reached
openai/gpt-4o via fallback — while `perspective_analyses.model` persisted the
hardcoded/requested name, not the real result.

Fixes:
- `execute()` now accepts `requested_model` (caller's configured model) and no
  longer defaults routing to a hardcoded model when the governor is absent.
- `ExecutionResult` now carries `requested_model`, `resolved_model`
  (post-`COMPOUNDOS_MODEL_ALIASES`), `actual_provider`, `actual_model`
  (provider-reported). `_execute_with_retry` returns the model actually used.
- `perspective_analyses` persistence records the real execution result
  (see §4).

### P3 — Memo synthesis token limit
`MemoGenerator` hardcoded `MAX_OUTPUT_TOKENS = 8000`. Replaced with
`MemoGenerator.resolve_max_output_tokens()`, which reads `MEMO_MAX_OUTPUT_TOKENS`
(default 8000). Invalid or non-positive values fall back to the default, so a
bad override can never silently truncate synthesis. Cost tracking is unaffected
— token accounting still flows from the provider-reported usage.

### P4 — Runtime shim boundary (analysis)
See §7 and §8.

---

## 3. Files Changed

### Application code
| File | Change |
|------|--------|
| apps/api/services/llm_provider_runtime.py | `_extract_json` + `_FENCE_RE`; `ExecutionResult` provenance fields; `execute(requested_model=...)`; `_execute_with_retry` returns `model_used` |
| apps/api/services/research_intelligence.py | `MemoGenerator.resolve_max_output_tokens()`; `_execute_one_perspective` passes `requested_model` + records `result.actual_model/provider`; `_store_analysis` writes provenance columns |
| apps/api/services/research_pipeline.py | `PERSPECTIVES` growth → `gpt-4o` (formalizes the validation-run config) |
| apps/api/mutation_gate.py | `EXPECTED_HEAD` → `0033_perspective_provenance` |
| apps/api/services/health_service.py | `EXPECTED_MIGRATION_HEAD` → `0033_perspective_provenance` |

### Migration
| File | Change |
|------|--------|
| migrations/versions/0033_perspective_provenance.py | NEW — additive provenance columns |

### Tests
| File | Change |
|------|--------|
| tests/test_llm_provider_runtime.py | +6 ResponseValidator robustness tests; +3 `TestModelProvenance` unit tests |
| tests/test_research_intelligence.py | mock executor signatures updated; +1 `TestModelProvenance` integration test; +5 `TestMemoTokenConfig` tests |
| 19 test files | `HEAD_REVISION` / head-assertion strings updated to `0033_perspective_provenance` |

### Docs / config
| File | Change |
|------|--------|
| .env.example | added `MEMO_MAX_OUTPUT_TOKENS=8000` |
| docs/CHANGELOG.md | M5-003 entry |
| docs/M5_003_PRODUCTION_HARDENING_REPORT.md | this report (NEW) |

---

## 4. Database Migrations

**Changed.** One additive migration added:

`0033_perspective_provenance` (revises `0032_decision_lifecycle_hardening`)

Adds four nullable TEXT columns to `perspective_analyses`:
- `requested_model`
- `resolved_model`
- `provider`
- `actual_model`

No new tables. No destructive changes. No data migration. Downgrade drops the
four columns. The legacy `model` column remains and now stores the actual
(served) model for backward compatibility. `mutation_gate.py` and
`health_service.py` HEAD constants were updated to match.

---

## 5. Tests

All tests run against a real PostgreSQL 16 test database
(`compoundos_test`) via the compose network; no real AI API calls.

New tests:
- ResponseValidator: raw JSON, fenced JSON, fenced (uppercase language tag),
  prose-wrapped JSON, invalid JSON, unbalanced braces.
- Model provenance: `requested_model` drives routing; alias resolution;
  fallback records actual (not primary); growth→gpt-4o DB row records the real
  result.
- Memo token cap: default value, env override, invalid fallback, non-positive
  fallback, token cap passed through to executor.

Targeted run (both touched modules):
`74 passed` (test_llm_provider_runtime.py + test_research_intelligence.py).

Full `tests/` suite:
`1322 passed, 2 skipped, 3 failed`.

The 3 failures are PRE-EXISTING and unrelated to M5-003 (verified: none touch
M5-003 code paths):

| Failing test | Cause | M5-003 related? |
|--------------|-------|-----------------|
| test_portfolio_trigger_and_confirm.py::test_alembic_revision_chain_valid | pre-existing 33-char revision id `0032_decision_lifecycle_hardening` (PR #97, 2026-08-10) violates the ≤32 limit; M5-003's `0033_perspective_provenance` is 27 chars and compliant | No |
| test_committee_persistence.py::test_evidence_confidence_constraint | pre-existing CHECK-constraint test expects a raise that does not occur | No |
| test_portfolio_intelligence.py::test_small_position_no_warning | pre-existing test data (21%/24% positions) exceeds the 20% concentration threshold | No |

Validation:
- `ruff check apps tests` — clean for all M5-003 files; one pre-existing `I001`
  (import order) in `apps/api/main.py` is unrelated to this work (file unmodified).
- `ruff check migrations/versions/0033_perspective_provenance.py` — clean.

---

## 6. Security Review

- No secrets, API keys, or credentials added.
- No `.env` staged or created (only `.env.example` documented, no values).
- No broker integration, no trading, no investment-policy change.
- No Decision created, no Investment Policy modified.
- Fail-closed behavior preserved: missing provider credentials still raise
  `ConfigurationError`; invalid LLM JSON still fails validation.
- New DB columns are additive and nullable — no privilege or constraint
  weakening.

---

## 7. Remaining Architecture Gaps

These are recorded, not implemented (out of scope for this sprint):

1. **Full Governance Layer (not implemented).** `PermissionGate`,
   `PromptGovernor`, `CostTracker` exist only as test mocks / design docs.
   `GovernedLLMExecutor` accepts them as optional params and no-ops when absent.
   Consequence: without a governor the model is caller-supplied (now correct);
   without a cost tracker `llm_execution_log` is not written.
2. **HTTP entry point is a simulation.** `pipeline_async.execute_pipeline` is
   `asyncio.sleep` + hardcoded values; it does not call
   `ResearchIntelligencePipeline`. The governed pipeline is service-layer only.
3. **Legacy mock path.** `apps/api/routers/research_pipeline.py` still wires the
   Sprint-012 `ResearchPipeline` + `PerspectiveExecutor` (mock analysis), not the
   governed `ResearchIntelligencePipeline`. Its `perspective_analyses` inserts
   leave the new provenance columns NULL (correct for a mock, but no real
   provenance).
4. **`investment_memos.synthesis_model`** is still hardcoded to the literal
   `'synthesis'` rather than the resolved/actual synthesis model.
5. **Learning Loop / model-evaluation consumers** do not yet read the new
   provenance columns.

### Runtime shim boundary classification (P4)

| Component | Classification |
|-----------|----------------|
| `ProviderRouter`, adapters, `GovernedLLMExecutor` | Production runtime |
| `ResponseValidator` + `_extract_json` | Production runtime (promoted) |
| `MemoGenerator.resolve_max_output_tokens` | Production runtime (config) |
| Inline mock `PermissionGate`/`PromptGovernor`/`CostTracker` (tests only) | Temporary validation helper |
| In-script shims from the FULL_AAPL validation run | Temporary validation helper (now superseded by production fixes) |
| Full PermissionGate / PromptGovernor / CostTracker | Future governance roadmap |

**Minimal correction performed:** the production `execute()` path no longer
depends on a PromptGovernor shim to route the correct model — the caller's
`requested_model` drives routing, and provenance is recorded from the real
result.

---

## 8. Recommendation for M6

1. Implement the Governance Layer for real: `PermissionGate` (ActionMatrix),
   `PromptGovernor.require_active`, `CostTracker.log_execution` wired into
   `GovernedLLMExecutor` with the `llm_execution_log` write made unconditional.
2. Wire `ResearchIntelligencePipeline` into the async HTTP entry point
   (`pipeline_async.execute_pipeline`), retiring the simulation.
3. Replace the Sprint-012 `PerspectiveExecutor` mock path with the governed
   path in `apps/api/routers/research_pipeline.py`.
4. Persist the real `synthesis_model` on `investment_memos`.
5. Point Learning Loop / model-evaluation queries at the new provenance
   columns.
