# Sprint 006 — Technical Design Gate

> **STATUS: OWNER DECIDED — 15/15 Resolved (2026-07-20). Implementation Not Authorized.**
>
> All Sprint 006 slices require separate explicit Owner authorization.
> This document reflects Owner decisions.  No implementation is authorized.
> PR #50 must complete independent review and squash merge before any Slice
> may be authorized.

## Executive Summary

**Approved candidate: AI Investment Committee Foundation with internal Evidence Pipeline.**

Sprint 006 delivers three capabilities in one sprint:

1. **Evidence Pipeline** — deterministic extraction of structured facts from
   CompoundOS internal data (Household, Policy, Portfolio, Decisions,
   Guardian Events) plus Owner-provided claims.  Every fact carries a
   citation reference.  No external market data in V1.

2. **AI Investment Committee** — Owner submits a proposal.  A single
   structured LLM call returns all seven approved perspectives plus a
   Synthesis.  The LLM receives only minimal structured facts
   (never raw financial text).  Output is validated through schema,
   citation, safety, and language checks before becoming an immutable
   Committee Report.

3. **Committee Outcomes** — Owner records Accept/Reject/Defer with
   rationale in append-only `committee_outcomes`.  Outcome can optionally
   create a Decision Journal Draft (never auto-confirmed).

**Architecture: Deterministic evidence pipeline + one structured LLM call.**

The LLM is a narrator, not an analyst.  Facts come from CompoundOS.
The LLM organizes, explains, and provides perspectives — but every
factual claim must cite an evidence ID or be rejected as invalid.

**Manual only.** No Schedule, no Guardian Event, no Portfolio Confirm,
no Automation Worker may trigger the Committee.  Owner initiates every
session explicitly.

---

## 1. Predecessor Verification

| Sprint | Status | Key Deliverables |
|--------|--------|-----------------|
| 001 | Done | Foundation, health endpoints, CI |
| 002 | Done | Household, Policy, Decision Journal |
| 003 | Done | Portfolio Snapshot + Holdings |
| 004 | Done | Guardian (Checks, Evaluation, Events) |
| 005 | Done | Orchestration (Worker, Schedules, Runs, Automation Frontend) |

All 11 migrations intact. 431 PG / 136 non-PG / 217 frontend test baseline.
Personal-use-only boundary in canonical docs. main @ 790e33e.

**PREDECESSOR VERIFIED.**

---

## 2. Candidate Analysis (Resolved)

Four candidates were compared (see original gate analysis for full details).

| Candidate | Decision | Rationale |
|-----------|----------|-----------|
| A: AI Investment Committee + Evidence | **SELECTED** | Highest Owner value, uses all Foundation data |
| B: Market Data & Evidence | DEFERRED | Needed as internal pipeline (combined with A in V1), no external data |
| C: Notification Escalation | DEFERRED | Premature for single consumer (Guardian only) |
| D: Family Goals & Reporting | DEFERRED | Consumer of Committee, not predecessor |

Evidence Pipeline in Sprint 006 V1 is **internal only** — CompoundOS facts
and Owner-provided claims.  No external price, index, rate, or macro feeds.
External market data is a Sprint 007 candidate, not in Sprint 006 scope.

---

## 3. Design Approach (Resolved)

**Approved: Deterministic evidence pipeline + one structured LLM call.**

V1 uses a single provider call — not multiple independent role calls.
That single call returns all seven perspectives and a Synthesis in a
structured JSON response.

### Execution Flow

```
1. Deterministic evidence extraction
   ├── Query CompoundOS entities (Policy, Portfolio, Guardian, Decisions)
   ├── Extract relevant structured facts
   ├── Assign evidence IDs, citations, freshness, confidence
   └── Build evidence packet
2. Privacy / redaction preview
   ├── Owner reviews exactly what will be sent to provider
   ├── No raw financial text in evidence packet
   └── Only category-level aggregates, constraint summaries, structured facts
3. Explicit Owner confirmation
   ├── Display estimated token count and cost
   ├── Owner must explicitly click "Run Committee"
   └── No auto-run, no schedule, no event trigger
4. Single provider call
   ├── Evidence packet + proposal text + role instructions
   ├── All seven perspectives + Synthesis in one response
   └── Single API call; no multi-call fan-out
5. Provider Output Validation
   ├── JSON schema validation (required sections, types, bounds)
   ├── Citation validation (factual claims must cite evidence_id)
   ├── Safety/language validation (no trading language, neutral tone)
   └── Token/cost metadata consistency check
6. Immutable report persistence
   ├── Normalized immutable committee_report row
   ├── Metadata: provider, model, prompt/schema version, temperature, tokens, cost
   └── Content hash for integrity
```

### Important Safety Qualification

> The LLM may hallucinate.  Any factual claim not citing an evidence_id
> must be rejected by the Provider Output Validator or explicitly marked
> as model inference.  When automatic distinction is impossible, the
> entire response validation fails.  This design mitigates hallucination
> risk through strict validation — it does not eliminate it.

---

## 4. Committee Roles (Resolved — 7 perspectives, single call)

All seven perspectives are returned by one structured LLM call.
No separate API calls per role.

| # | Role | Purpose | No-Evidence Behavior |
|---|------|---------|---------------------|
| 1 | Long-Term Compounding | Alignment with compounding strategy, drift assessment | Uses Policy + Portfolio evidence |
| 2 | Index / Passive Investing | Alternative: what would a passive approach look like? | Uses Policy + Portfolio evidence |
| 3 | Macroeconomic Context | Macro landscape relevant to proposal | Must state: "Insufficient current macro evidence — no external market data in V1" |
| 4 | Risk / Capital Preservation | Risk exposure, concentration, capital preservation | Uses Portfolio + Guardian evidence |
| 5 | Devil's Advocate | Strongest opposing arguments | Must be non-empty. Must challenge the proposal. |
| 6 | Policy Alignment | Proposal vs. Policy objectives, constraints, prohibitions | Uses Policy evidence |
| 7 | Synthesis / Chair | Balanced summary, preserves minority opinion, does not erase disagreement | Aggregates all role outputs |

### Constraints

- Macro (role 3) has no external market data in V1 — must declare insufficient evidence.
- Must not use model training knowledge to impersonate real-time macro data.
- Devil's Advocate (role 5) and Opposing Arguments must be non-empty.
- Synthesis (role 7) must preserve minority opinions and disagreements — no forced consensus.

---

## 5. Data Model (Resolved)

### Entities (Migration 0012 — additive only, never modifies 0001–0011)

```
committee_sessions
  id (UUID PK)
  household_id (FK → household_profiles.id)
  parent_session_id (FK self, nullable — for re-runs)
  title (text, NOT NULL)
  proposal_text (text, NOT NULL — what the Owner typed)
  status (text: draft | queued | running | completed | failed)
  created_at (timestamptz)
  updated_at (timestamptz)

committee_evidence_items
  id (UUID PK)
  session_id (FK → committee_sessions.id, CASCADE)
  source_type (text: portfolio_snapshot | policy_version | guardian_event |
    decision | owner_claim — external reserved, unused in V1)
  source_id (UUID — CompoundOS entity)
  source_title (text)
  as_of (timestamptz)
  content_hash (text — SHA256)
  structured_facts (JSONB — key-value extracted deterministically)
  provenance (text: compoundos_internal | owner_provided)
  freshness (text)
  confidence (text: high | medium)
  citation_ref (text — human-readable ref, e.g. "Policy v3 §Allocations")
  created_at (timestamptz)

committee_reports
  id (UUID PK)
  session_id (FK → committee_sessions.id, CASCADE, UNIQUE)
  provider (text — e.g. "deepseek")
  model_id (text — e.g. "deepseek-v3")
  model_version (text)
  prompt_version (text)
  schema_version (text)
  temperature (numeric)
  provider_params (JSONB)
  input_tokens (int)
  output_tokens (int)
  estimated_cost (numeric)
  report_content (JSONB — normalized, validated, immutable)
    ├── supporting_arguments
    ├── opposing_arguments
    ├── risks
    ├── policy_alignment
    ├── minority_opinions
    ├── evidence_citations
    ├── limitations
    ├── recommended_direction (enum, see §6)
    └── sections (role-by-role output)
  content_hash (text — SHA256 of normalized report)
  generated_at (timestamptz)
  created_at (timestamptz)
  -- Reports are immutable.  No UPDATE allowed after creation.
  -- Re-runs create new sessions (parent_session_id links to origin).

committee_outcomes
  id (UUID PK)
  session_id (FK → committee_sessions.id, CASCADE)
  report_id (FK → committee_reports.id)
  outcome (text: accepted | rejected | deferred)
  owner_rationale (text)
  decision_draft_id (UUID, nullable — FK to decision_drafts)
  recorded_at (timestamptz)
  -- Append-only.  No UPDATE, no DELETE.
```

### Lifecycle

```
Session: draft → queued → running → completed | failed
  completed: report generated and validated
  failed: provider failure (2 attempts exhausted) or validation failure

Outcome: recorded after completed session
  accepted/rejected/deferred — append-only, Owner rationale required

Decision Journal: when Owner explicitly creates a Decision from Outcome:
  → creates Decision Draft (never auto-confirmed)
  → Draft references committee_outcomes.id
  → Existing Decision lifecycle unchanged
```

### Constraints

- `committee_reports.content` is immutable after creation (trigger-enforced).
- `committee_outcomes` is append-only (no UPDATE, no DELETE).
- Re-runs create new sessions with `parent_session_id` linking to origin.
  Old reports are never overwritten.
- Household isolation: all queries filtered by `household_id`.
- Evidence items cascade-delete with session.
- Reports cascade-delete with session (re-run creates new session + new report).

---

## 6. Report Language & recommended_direction (Resolved)

`recommended_direction` is an allowed field with these exact enum values:

| Value | Meaning |
|-------|---------|
| `aligned_with_policy` | Proposal is consistent with Policy objectives |
| `not_aligned_with_policy` | Proposal conflicts with Policy |
| `conditionally_aligned` | Aligned IF certain conditions are met |
| `insufficient_evidence` | Cannot determine — not enough data |

The field must NEVER contain: "buy", "sell", "hold", trade instructions,
ticker symbols, price targets, or any language that could be interpreted
as investment advice or trading instructions.

### Required Report Sections (all mandatory)

- `supporting_arguments` — must be non-empty
- `opposing_arguments` — must be non-empty
- `risks` — must be non-empty
- `policy_alignment` — Policy sections cited
- `minority_opinions` — preserved from Synthesis
- `evidence_citations` — linked to evidence_ids
- `limitations` — what this report cannot address
- `recommended_direction` — one of the four enum values
- `sections` — per-role output (7 sections)

---

## 7. Safety Model (Resolved + Mandatory Corrections)

### Core Safety Rules (unchanged from original gate)

1. AI output is DECISION SUPPORT, not investment advice.
2. No autonomous trading, order generation, or execution.
3. No automatic Portfolio, Policy, Guardian, or Schedule mutation.
4. No automatic Decision confirmation or creation.
5. Owner explicitly initiates every session.
6. Owner explicitly records outcome.
7. Supporting AND opposing arguments both mandatory.
8. `recommended_direction` uses approved enum only — no Buy/Sell/Hold.
9. When evidence insufficient: state "insufficient evidence."
10. Never claim real-time market data unless source/timestamp verifiable.
11. Model/provider/prompt version recorded and traceable.
12. Temperature set to 0 or lowest deterministic value available.
13. External provider failure must not fabricate results.

### Hallucination Acknowledgment (Mandatory Correction)

> The LLM may hallucinate.  This design does not claim to prevent
> hallucination.  Instead, it mitigates risk through:
>
> 1. **Strict JSON schema validation** — hallucinated fields with wrong
>    types or missing sections are rejected.
> 2. **Citation validation** — any factual claim not citing an evidence_id
>    is rejected unless marked as model inference.
> 3. **Provider Output Validator** — post-response validation pipeline
>    that rejects the entire response when violations are detected.
> 4. **No raw financial text in evidence packet** — the LLM receives
>    structured facts only, reducing hallucination surface area.

### Provider Output Validator

```python
def validate_provider_output(response: dict, evidence_ids: set) -> ValidationResult:
    """Reject or accept LLM output.  Never silently accept invalid output."""
    errors = []

    # 1. JSON schema validation
    schema_errors = validate_json_schema(response, COMMITTEE_OUTPUT_SCHEMA)
    errors.extend(schema_errors)

    # 2. Required sections present and non-empty
    for section in REQUIRED_SECTIONS:
        if not response.get(section):
            errors.append(f"Missing required section: {section}")

    # 3. Opposing arguments must be non-empty
    if not response.get("opposing_arguments"):
        errors.append("opposing_arguments must be non-empty")

    # 4. Citation validation — every factual claim must cite evidence_id
    for claim in extract_factual_claims(response):
        if not claim.get("evidence_ref"):
            if not claim.get("model_inference"):
                errors.append(
                    f"Factual claim without evidence citation or inference label"
                )

    # 5. Forbidden language detection
    if contains_trading_language(response):
        errors.append("Response contains trading/investment-advice language")

    # 6. Neutral language check
    if not uses_neutral_language(response):
        errors.append("Response language is not neutral/advisory")

    # 7. Token/cost metadata consistency
    if not metadata_consistent(response):
        errors.append("Token/cost metadata inconsistent")

    if errors:
        return ValidationResult.rejected(errors)
    return ValidationResult.accepted()
```

### Prompt Injection & Data Security (unchanged)

- Owner Policy/Decision/Portfolio text treated as UNTRUSTED DATA.
- Evidence content cannot change system policy or evaluation rules.
- Provider allowlist: only approved LLM APIs.
- No arbitrary URL fetch unless separately authorized.
- No code execution via LLM output or evidence.
- No secret/API key/credential in prompts, DB, logs, or audit metadata.

### Privacy & Data Minimization

What MAY be sent to provider:

- Owner's proposal text (what they typed into this session)
- Structured facts: category-level allocation percentages, relevant
  Policy constraint summaries, Guardian condition summaries,
  relevant prior-decision structured summaries, evidence IDs,
  as_of timestamps, freshness labels.

What must NEVER be sent to provider:

- Household name or personally identifiable information
- Account identifiers
- Full Policy text (objectives, time_horizon, decision_process, etc.)
- Full Portfolio holdings (names, quantities, unit prices, notes)
- Full Decision Journal text
- Full Guardian Event details
- Aggregate value calculations, specific dollar amounts

### Privacy Preview UI

Before the Owner clicks "Run Committee," a preview screen shows exactly
the structured data that will be sent to the provider.  Owner must
explicitly review this before confirming.  No provider call without
preview.

### Manual-Only Constraint (Owner Addition)

The Committee is **completely manual-only** in Sprint 006:

Not scheduleable through Automation
- Not triggerable by Guardian Events
- Not triggerable by Portfolio Confirm
- Not callable by the Automation Worker
- Not runnable from any automated workflow

Only the Owner, through the `/committee` UI, can create a session
and explicitly confirm a provider call.  Future automation requires
a new Owner Decision.

---

## 8. Provider Abstraction & Retry (Resolved)

### Provider Interface

Provider-neutral interface.  V1 implements only a DeepSeek adapter.

- `AIModelProvider` abstract interface
- `DeepSeekProvider` — V1 implementation
- OpenAI/Anthropic adapters NOT implemented in V1
- Model ID configured, not hardcoded
- Adding a new provider requires separate Owner authorization

### Retry Boundary

All-or-nothing valid report.  No partial report display.

Maximum 1 automatic retry, allowed only for:

- Connection timeout
- HTTP 429 (rate limit)
- Transient provider 5xx
- Provider returns explicitly retryable temporary error

Retry is FORBIDDEN for:

- Schema validation failure
- Citation validation failure
- Safety validation failure
- Token/cost cap exceeded
- Prompt injection detection
- Non-transient 4xx

After 2 failures (original + 1 retry):

- Session status → `failed`
- Evidence packet and metadata preserved
- No committee_report created
- UI displays clear "provider failure" state
- Owner can explicitly re-run (creates new session)

### Per-Session Budget (Resolved)

| Cap | Default Value | Enforcement |
|-----|---------------|-------------|
| Max input tokens | 50,000 | Pre-flight estimate; reject if exceeded |
| Max output tokens | 8,000 | Provider parameter |
| Max estimated cost | USD 1.00 | Pre-flight estimate; reject if exceeded |

- Owner may adjust caps in local secure configuration (lower or higher).
- Caps are never auto-increased.
- Actual usage and cost recorded as metadata.
- Provider pricing changes do not silently bypass token cap.

---

## 9. Credential Storage (Resolved)

- **Production (macOS):** macOS Keychain.
- **CI:** Environment variable with fake/test credential.
- API key never enters DB, repository, logs, prompt payload, or frontend.
- Keychain dependency must be minimal and independently reviewed.
- If Keychain is unavailable, production must NOT silently fallback to
  plaintext file.  Environment fallback only with explicit Owner config.
- Plaintext config files for credentials are FORBIDDEN.

---

## 10. Evidence Contract (Unchanged from original gate)

Each evidence item carries:

| Field | Description |
|-------|-------------|
| source_type | portfolio_snapshot, policy_version, guardian_event, decision, owner_claim (external reserved) |
| source_id | CompoundOS entity UUID |
| as_of | Timestamp of source data |
| content_hash | SHA256 for integrity |
| structured_facts | Key-value pairs extracted deterministically |
| provenance | compoundos_internal or owner_provided |
| freshness | current / stale |
| confidence | high / medium |
| citation_ref | Human-readable reference |

### Evidence vs. Inference (Mandatory Correction)

**Evidence** comes from verifiable CompoundOS or Owner-provided sources.
It is stored in `committee_evidence_items`.

**Model inference** exists only in the Committee Report.  It is not evidence.
The `evidence_items` table has no `model_inference` field.  Inference labels
belong to report claims/sections, not to evidence.

Every factual claim in the report must cite an evidence_id OR be explicitly
marked as model inference.  Claims that are neither are rejected by the
Provider Output Validator.

---

## 11. API Contract (Future Implementation — Not Authorized)

| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/committee/sessions | Create new session (draft) |
| GET | /api/committee/sessions | List sessions (pagination) |
| GET | /api/committee/sessions/{id} | Session detail with report + evidence |
| POST | /api/committee/sessions/{id}/run | Start analysis (after privacy preview) |
| GET | /api/committee/runs/{id} | Run status |
| GET | /api/committee/reports/{id} | Immutable report |
| GET | /api/committee/evidence/{session_id} | Evidence items |
| POST | /api/committee/outcomes | Record Owner outcome |
| GET | /api/committee/audit | Committee audit timeline |

All POST endpoints require explicit Owner confirmation.  No auto-run.
Session → Evidence → Run → Report → Outcome lifecycle.

---

## 12. UI States (Future Implementation — Not Authorized)

At minimum: loading, no household, no Published Policy, no Portfolio
Snapshot, empty sessions, session editor, privacy/redaction preview
(mandatory before provider call), explicit run confirmation with cost
estimate, queued/running, provider failure (all-or-nothing — no partial),
insufficient evidence warning, completed report with all sections,
supporting + opposing arguments, risks, minority opinions, evidence
citations, recommended_direction, Owner accept/reject/defer, Decision
Journal handoff (Draft only), history/detail, audit, dirty/conflict
preservation, no auto-run on page load.

---

## 13. Test Strategy (Future Implementation — Not Authorized)

**No live external LLM calls in CI.**  All provider calls mocked.

### Persistence (Slice A)
- Migration 0012 lifecycle (fresh, incremental, downgrade/re-upgrade)
- Report immutability (no UPDATE allowed)
- Outcome append-only (no UPDATE/DELETE)
- Household isolation
- Evidence provenance tracking
- Content hash integrity
- Cascade delete behavior

### Provider Abstraction (Slice B)
- Mock provider validates schema, timeout, rate limit
- Malformed output rejected
- Retry boundary enforced (1 retry, transient errors only)
- Token/cost cap enforcement
- No secrets in error messages or logs

### Provider Output Validator (Slice B)
- Schema validation: required sections, types, bounds
- Citation validation: claims without evidence_id rejected
- Forbidden language detection (Buy/Sell/Hold, trading language)
- Neutral language enforcement
- Evidence/Inference boundary enforced

### Safety (Slice B)
- Prompt injection resistance
- Malicious evidence rejection
- Stale evidence warning
- No trading/tool call in output
- No Policy/Portfolio/Guardian mutation
- Owner confirmation required for all actions
- Manual-only constraint: no automated Committee calls

### Frontend (Slice C)
- All approved UI states
- Privacy Preview state
- Accessibility, dirty/conflict
- No auto-run on load
- No mutation retry
- Evidence citation display

---

## 14. Slice Decomposition (R2/R2/R1 — Not Authorized)

### Slice A — Persistence + Evidence Contracts (R2)
- Migration 0012: sessions, evidence_items, reports, outcomes
- ORM models, named constraints, immutability triggers
- Evidence Packet Builder (deterministic queries against CompoundOS)
- Citation reference generation
- Source type registry (CompoundOS internal + owner_claim only in V1)
- 80+ PostgreSQL tests
- **No API, no LLM, no frontend.**

### Slice B — Provider + Output Validator + API (R2)
- AIModelProvider interface + DeepSeek adapter only
- Credential management (macOS Keychain)
- Provider Output Validator (schema, citation, safety, language)
- Committee orchestration: evidence → privacy preview → provider call →
  validate → persist
- 9 API endpoints under /api/committee
- Retry, rate-limiting, cost tracking, budget enforcement
- Mock provider for all CI tests
- Safety tests (prompt injection, citation validation, hallucination rejection)
- **No frontend.  No OpenAI/Anthropic adapters.**

### Slice C — Committee Frontend (R1)
- `/committee` page with typed API client
- All approved UI states including Privacy Preview
- Report display with evidence citations
- Decision Journal handoff (Draft only)
- Full accessibility and component tests
- **No auto-run.  Manual-only.**

---

## 15. Owner Decisions — All Resolved

| ID | Question | Resolution |
|----|----------|------------|
| OD-6-1 | Sprint 006 candidate | **A**: AI Committee + internal Evidence Pipeline. No Market Data/Notifications/Family Goals. |
| OD-6-2 | LLM provider | **A, V1-limited**: Provider-neutral interface; only DeepSeek adapter implemented in V1. Model ID configured, not hardcoded. |
| OD-6-3 | Financial data to provider | **A**: Minimized structured facts only. Privacy Preview required. Full Policy/Portfolio/Guardian text never sent. |
| OD-6-4 | Evidence foundation sequencing | **A**: Combined sprint. Committee never calls LLM without evidence packet. |
| OD-6-5 | Design approach | **A**: Deterministic evidence + one structured LLM call. Single call returns all 7 perspectives. |
| OD-6-6 | Committee roles | **B, single-call**: All 7 perspectives in one call. Macro must declare insufficient evidence. |
| OD-6-7 | Data model | **A + Outcome entity**: Sessions, Evidence Items, Reports (immutable), Outcomes (append-only). Separate from Decision Journal. |
| OD-6-8 | Report language | **B, restricted**: recommended_direction with approved enum. Never Buy/Sell/Hold. |
| OD-6-9 | Owner outcome | **B, Draft-only**: Accept/Reject/Defer → append-only Outcomes → optionally creates Decision Draft (never auto-confirmed). |
| OD-6-10 | Version retention | **A**: Every immutable Report stores provider, model, prompt version, schema, temperature, tokens, cost. |
| OD-6-11 | Token/cost cap | **A, explicit defaults**: 50K input / 8K output / $1.00 per session. Configurable by Owner. |
| OD-6-12 | Provider failure | **B, explicit retry**: All-or-nothing report, max 1 retry (transient only). No partial report. |
| OD-6-13 | Response logging | **A, clarified**: No raw prompt/response. Normalized immutable Report must be persisted for history. |
| OD-6-14 | Credential storage | **A**: macOS Keychain. CI uses env var. No plaintext config. |
| OD-6-15 | External market data | **A**: Deferred. V1 CompoundOS internal only. Macro section declares insufficient evidence. |

### Additional Owner Constraints Applied

- **Manual-only**: No Schedule, Guardian Event, Portfolio Confirm, or Automation Worker may trigger Committee.
- **V1 temperature**: 0 or lowest deterministic value available.
- **Decision Journal integration**: Creates Draft only; never auto-confirms.

---

## 16. Mandatory Design Corrections Applied

1. ✅ Architecture unified: deterministic evidence + one structured call.  Multi-call/partial-role-failure removed.
2. ✅ Safety language corrected: LLM can hallucinate.  Mitigation via strict validation, not claimed prevention.
3. ✅ Committee Outcome entity added with append-only lifecycle.
4. ✅ Decision Journal integration: Draft only, never auto-confirmed.  Existing Decision lifecycle unchanged.
5. ✅ Evidence/Inference separation: Evidence = verifiable source.  Inference = report claims only.
6. ✅ Provider Output Validator: schema, citation, safety, language validation pipeline.
7. ✅ Privacy Preview UI state: Owner reviews structured facts before provider call.
8. ✅ External market data scope deleted from Sprint 006.  External source_type reserved but unused in V1.
9. ✅ All API, data model, state machine, test matrix aligned with resolved decisions.

---

## Predecessors & Dependencies

- Sprint 001–005: Done.
- All 11 migrations intact.
- Guardian/Automation operational.
- Personal-use-only boundary in canonical docs.

## Implementation Status

- **Sprint 006 Implementation: NOT AUTHORIZED.**
- All slices require separate explicit Owner authorization.
- This document is the resolved Technical Design Gate deliverable.
- No migration, backend, frontend, or dependency changes are authorized.

## Review Status

- Owner Decisions: 15/15 resolved (2026-07-20).
- Independent technical design review: Pending.
- PR #50: Draft → Ready after review passes.
