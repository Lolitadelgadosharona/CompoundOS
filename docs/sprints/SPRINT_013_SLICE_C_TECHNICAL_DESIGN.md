# Sprint 013 Slice C — Technical Design
# Active Research Intelligence Loop

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 013 Slice A (LLM Runtime): DONE (4fe15ea, PR #95)
> Sprint 013 Slice B (Evidence Layer): DONE (001b42f)
> Sprint 013 Slice C: DESIGN ONLY

---

## 1. Objective

Slice A proved governed LLM calls work. Slice B added real market evidence.
Slice C **activates the full loop**: connects the evidence pipeline to
the perspective execution engine, validates every LLM output, synthesizes
the investment memo, and computes confidence — all through existing
governed infrastructure.

No new tables. No new providers. Slice C is purely an integration and
orchestration layer that wires together components already built in
Sprints 009-013B.

---

## 2. Architecture

### 2.1 Component Map

```
POST /api/research/start (Sprint 012-B)
        │
        ▼
ResearchPipeline._execute()
        │
        ├── 1. EvidenceCollector.collect()         ← Sprint 013-B (Alpha Vantage + Knowledge)
        │       └── Returns: EvidenceBundle
        │
        ├── 2. PerspectiveExecutor.execute_all()   ← Sprint 012-B (parallel LLM)
        │       └── Calls GovernedLLMExecutor.execute() ← Sprint 013-A
        │           ├── PermissionGate.check()
        │           ├── PromptGovernor.require_active()
        │           ├── ProviderRouter.route()
        │           ├── Provider.generate()
        │           ├── ResponseValidator.validate()
        │           └── CostTracker -> llm_execution_log
        │       └── Stores: perspective_analyses rows
        │
        ├── 3. MemoGenerator.generate()            ← NEW (Slice C integration)
        │       └── Calls GovernedLLMExecutor (synthesis perspective)
        │       └── Stores: investment_memos row
        │
        └── 4. ConfidenceEngine.calculate()        ← Sprint 012-B (existing)
                └── Deterministic, not LLM-generated
                └── Updates: investment_memos row
```

### 2.2 Ownership Boundaries

| Component | Owned By | Slice |
|---|---|---|
| Evidence collection | EvidenceCollector + AlphaVantageProvider | 013-B |
| LLM execution | GovernedLLMExecutor + adapters | 013-A |
| Perspective storage | PerspectiveExecutor | 012-B / 013-C |
| Memo synthesis | MemoGenerator | 013-C (NEW) |
| Confidence | ConfidenceEngine (deterministic) | 012-B |
| Evidence snapshots | EvidenceSnapshot | 013-B / 013-C |
| Execution logging | llm_execution_log (CostTracker) | 012-A |

Slice C introduces ONE new component: `MemoGenerator`. Everything else
is integration of existing components.

---

## 3. MemoGenerator

### 3.1 Purpose

Synthesizes 6 perspective analyses into a structured investment memo
using the 11-section schema from Sprint 011 TD.

### 3.2 Flow

```python
class MemoGenerator:
    def __init__(self, executor: GovernedLLMExecutor): ...

    def generate(self, session, run_id, perspectives,
                 evidence) -> dict:
        # 1. Build synthesis prompt from 6 perspective outputs
        # 2. Execute governed LLM call (synthesis perspective)
        # 3. Validate response against memo schema
        # 4. Store investment_memos row
        # 5. Return memo dict
```

### 3.3 Memo Schema

From Sprint 011 Slice D (0030_investment_memo):

| Section | Source |
|---|---|
| thesis | Synthesized from perspective consensus |
| evidence | EvidenceBundle.provenance |
| bull_case | Value + Growth consensus |
| bear_case | Risk perspective |
| risks | Risk + Policy perspectives |
| valuation | Value + Growth metrics |
| portfolio_impact | Portfolio Construction perspective |
| guardian_impact | Policy perspective |
| committee | All 6 perspective votes |
| decision_context | Research request context |
| invalidation_conditions | Risk + Policy conditions |

### 3.4 Validation

MemoGenerator output is validated by `ResponseValidator` (key fields:
thesis). The memo is also validated against investment_memos schema
(perspective_analyses stores structured JSONB, memos store full memo).

---

## 4. Data Flow

### 4.1 Evidence → Perspective

Each perspective receives a prompt built from `EvidenceBundle`:

```
System: "You are the {perspective} analyst for CompoundOS..."
User:   "Analyze {symbol} from a {perspective} perspective.
         Evidence: {evidence.market_data}
         Portfolio context: {evidence.portfolio_context}
         Guardian status: {evidence.guardian_status}
         Historical context: {evidence.knowledge_memory}
         Missing: {evidence.missing_sources}"
```

Evidence is passed through, not embedded — the LLM receives structured
context, not raw API responses.

### 4.2 Perspective → Memo

Six validated `perspective_analyses` → `MemoGenerator`:

```
User: "Synthesize the following 6 perspectives into an investment memo:
       [Value output], [Growth output], [Risk output], ..."
```

### 4.3 Provenance Chain

```
AlphaVantage → market_data_cache → EvidenceBundle
    └── ProvenanceEnvelope(source="alpha_vantage", ...)
        │
        ▼
PerspectiveExecutor → GovernedLLMExecutor
    └── llm_execution_log (model, tokens, cost, prompt_version)
    └── perspective_analyses (analysis, conviction_score, model)
        │
        ▼
MemoGenerator → GovernedLLMExecutor (synthesis)
    └── llm_execution_log (synthesis call)
    └── investment_memos (full memo JSONB, confidence, recommendation)
```

Every artifact is traceable: memo → perspectives → executions → evidence.

---

## 5. Failure Handling

### 5.1 Partial Perspective Failure

Per Sprint 012-B design (OD-12-B-4): if some perspectives fail,
preserve successful ones, skip memo generation, mark run completed
with partial results.

### 5.2 Memo Generation Failure

If synthesis LLM call fails (timeout, validation, provider error):
- Mark run `failed`
- Preserve completed perspectives
- Log error in research_run.error_message

### 5.3 Confidence on Partial Data

ConfidenceEngine reduces score proportionally:
- 3/6 perspectives → ~50% evidence_quality
- Missing market data → further reduction

No LLM-generated confidence penalty. System code owns the calculation.

### 5.4 No Fabricated Outputs

This is invariant across all slices:
- Missing data → `missing_sources` populated
- Failed perspective → error logged, not guessed
- Failed memo → run failed, no synthetic memo

---

## 6. AI Authority

| Action | Classification | Enforced By |
|---|---|---|
| Collect evidence | AUTO | PermissionGate |
| Execute perspective LLM | AUTO | PermissionGate |
| Generate memo | AUTO | PermissionGate |
| Calculate confidence | AUTO | ConfidenceEngine (system) |
| Store results | AUTO | ResearchPipeline |
| Approve investment | OWNER | PermissionGate + API auth |
| Modify policy | NEVER | PermissionGate + triggers |
| Execute trade | NEVER | PermissionGate |
| Connect broker | NEVER | Never implemented |

---

## 7. Database Impact

No new tables. Slice C operates on existing schema:

| Table | Slice C Usage |
|---|---|
| research_runs | Status updates (collecting → analyzing → generating → completed) |
| perspective_analyses | Written by PerspectiveExecutor after each governed call |
| investment_memos | Written by MemoGenerator after synthesis |
| llm_execution_log | Written by GovernedLLMExecutor for every LLM call |
| committee_evidence_items | Written by EvidenceSnapshot for immutable evidence |
| market_data_cache | Read/write by EvidenceCollector (cache-before-provider) |

---

## 8. API Impact

No new API endpoints. The existing POST /api/research/start (Sprint 012-B)
triggers the full Slice C pipeline. GET /progress and /results endpoints
already support the enhanced output.

---

## 9. Test Strategy

| Test Area | Count | Description |
|---|---|---|
| Evidence → Perspective | 3 | EvidenceBundle passed, research_run_id preserved |
| Six perspectives executed | 2 | All 6 complete, intermediate failures handled |
| Validator enforcement | 2 | Bad perspective output rejected |
| Memo generator | 4 | Full synthesis, partial-fail skip, provenance, schema |
| Confidence calculation | 2 | Deterministic, not LLM-generated |
| Provenance | 2 | Full chain: evidence → perspective → memo → log |
| Failure handling | 3 | Partial failure, memo fail, no fabrication |
| Authority | 1 | NEVER actions still blocked |
| **Total** | **~19** | |

---

## 10. Dependencies

Slice C depends on all prior Sprint 013 components being available:
- GovernedLLMExecutor (Slice A)
- AlphaVantageProvider, EvidenceCollector (Slice B)
- PerspectiveExecutor, ConfidenceEngine (Sprint 012-B)
- ResponseValidator (Slice A, hardened)
- PermissionGate, PromptGovernor (Sprint 012-D)

---

## 11. Estimate

| Component | Lines | Tests |
|---|---|---|
| MemoGenerator | ~100 | 4 |
| Pipeline integration | ~80 | 3 |
| Evidence → Perspective wiring | ~60 | 3 |
| Failure + provenance | ~50 | 5 |
| Authority | ~10 | 1 |
| **Total** | **~300** | **~16** |

---

## 12. Owner Decisions

**No new Owner Decisions required.** All architecture decisions are
resolved by prior approvals:
- OD-13-1: Multi-provider LLM (Claude + GPT-4o + Gemini)
- OD-13-5: Log-only cost thresholds
- OD-13-6: Mandatory inline citations
- OD-13-7: AI advisory, Owner decides
- OD-13-8: Graceful degradation

---

## 13. Acceptance Criteria

Slice C is successful when:

1. A research run collects evidence from Alpha Vantage + knowledge memory
2. Six perspective analyses are executed through governed LLM calls
3. Each analysis is validated and stored with provenance
4. MemoGenerator synthesizes all 6 perspectives into a memo
5. ConfidenceEngine calculates deterministic confidence score
6. Full provenance chain is preserved: evidence → execution → memo
7. Partial failures preserve evidence, don't fabricate results

**This is the first complete end-to-end AI investment research workflow
in CompoundOS.**
