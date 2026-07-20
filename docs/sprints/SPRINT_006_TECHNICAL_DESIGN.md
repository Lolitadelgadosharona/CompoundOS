# Sprint 006 — Technical Design Gate

> **STATUS: Owner Decisions Required — Implementation Not Authorized**
>
> Sprint 006 slices must receive separate explicit Owner authorization.
> This document provides the analysis, comparison, and Owner Decisions
> needed before any implementation begins.

## Executive Summary

**Recommended candidate: AI Investment Committee Foundation (A)** with a
prerequisite lightweight Market Data & Evidence ingestion (B) in the same
sprint as a combined evidence+committee foundation.

Rationale: the Committee is the highest-owner-value, most Vision-aligned
candidate. It directly consumes all Foundation data already built across
Sprints 001–005. However, without an evidence contract (who said what,
when, with what confidence), the Committee would generate opinions from
model training data rather than from Owner's actual financial context.
A minimal evidence pipeline (CompoundOS internal facts + Owner-provided
claims, no external price feeds) must ship alongside the Committee.

The combined sprint delivers: the Owner can submit a proposal with
supporting evidence, the system runs a multi-perspective analysis using
deterministic facts from CompoundOS plus Owner-provided context, and
produces a balanced report with supporting arguments, opposing arguments,
risks, and policy alignment — never a one-sided recommendation.

---

## 1. Predecessor Verification

| Sprint | Status | Key Deliverables |
|--------|--------|-----------------|
| 001 | Done | Foundation, health endpoints, CI |
| 002 | Done | Household, Policy (Draft/Version/Allocations), Decision Journal |
| 003 | Done | Portfolio Snapshot + Holdings |
| 004 | Done | Guardian (Checks, Evaluation, Events) |
| 005 | Done | Orchestration (Worker, Schedules, Runs, Leases), Automation Frontend |

All 11 migrations intact. 431 PG / 136 non-PG / 217 frontend test baseline.
Personal-use-only boundary in canonical docs. main @ 790e33e, CI green.

**PREDECESSOR VERIFIED — Sprint 006 Technical Design Gate may proceed.**

---

## 2. Candidate Analysis

### Candidate A — AI Investment Committee Foundation

**Goal:** Owner submits an investment proposal. System analyzes from multiple
complementary perspectives: long-term compounding, risk/capital preservation,
policy alignment, and devil's advocate. Produces balanced report with
supporting arguments, opposing arguments, key risks, evidence citations,
and policy consistency check. Owner reviews and decides — no autonomous action.

**Inputs available today:**
- Household profile (horizon, liquidity, risk statement)
- Published Investment Policy (objectives, allocations, constraints)
- Portfolio Snapshot (holdings, valuation, categories)
- Decision Journal (past decisions, corrections, rationale)
- Guardian Events (exceeded thresholds, drift, staleness)
- Automation Runs (evaluation history)

**Owner Direct Value:** High. Every investment decision the Owner considers
would benefit from structured multi-perspective analysis leveraging all
accumulated Foundation data. This is the first feature that genuinely
feels like an "AI Family Office."

**Dependencies:** All Foundation data present. Missing: real-time market
data (prices, indices). Mitigation: V1 limits analysis to Owner-provided
proposal + CompoundOS internal evidence. External price feeds deferred.

**Data Model Complexity:** Medium. 3-4 new tables: sessions, proposals,
role opinions, synthesis reports, evidence citations.

**External Services:** LLM API required (OpenAI, Anthropic, or DeepSeek).
This is the first external dependency. Requires credential management,
provider abstraction, cost tracking, and data minimization.

**Financial/Safety Risk:** HIGH. LLM outputs could be misinterpreted as
investment advice. Hallucination risk is real. Prompt injection via
Owner-authored Policy/Decision text. Mitigation: deterministic evidence
pipeline, citation requirements, mandatory opposing arguments, neutral
language enforcement.

**Privacy/Security:** HIGH. Portfolio holdings, Policy allocations, and
Guardian thresholds would be sent to external LLM providers. Sensitive
financial data leaves the local machine.

**Testability:** Medium. Non-deterministic LLM outputs. Mock-based tests
validate structure not content. Evidence pipeline is fully testable.

**Local-only Feasibility:** Low. No high-quality local models exist for
this use case. External provider is a hard dependency for V1. A
provider-neutral abstraction supports future local model migration.

**Estimated Slices:** 3 slices (A: Persistence + Evidence, B: Provider +
Orchestration + API, C: Frontend). R2/R2/R1.

**Future Unlocks:** High. Committee is the gateway to all future AI-driven
decision support. Enables AI-assisted Policy drafting, Portfolio review,
Guardian response planning.

### Candidate B — Market Data & Evidence Ingestion

**Goal:** Ingestion pipeline for prices, indices, exchange rates, macro
data. Quality checks, timestamps, provenance, failure visibility.

**Owner Direct Value:** Medium. Enables data-driven Committee analysis
but doesn't directly answer investment questions. Foundation capability.

**Dependencies:** External data providers (Alpha Vantage, Yahoo Finance,
etc.). API keys, rate limits, cost.

**Data Model Complexity:** Low-Medium. ~2 tables: data_sources,
market_observations with provenance and quality metadata.

**External Services:** Required. Provider API keys, rate limiting,
retry, caching.

**Financial/Safety Risk:** Low. Read-only data ingestion. Risk: stale
or incorrect data presented as current.

**Testability:** High. Deterministic ingestion pipeline, mock providers.

**Local-only Feasibility:** Medium. External APIs needed but data is
read-only and cacheable.

**Estimated Slices:** 1-2 slices.

**Verdict:** Should be built as **prerequisite evidence pipeline for
Candidate A**, not as standalone Sprint. The evidence contract (who
said what, when, with what confidence) is needed for the Committee.

### Candidate C — Notification Escalation

**Goal:** Guardian/Automation events escalate to Owner via local inbox
or future channels (email, SMS). No investment action taken.

**Owner Direct Value:** Medium. Useful when evaluations are automated
and Owner doesn't actively check /guardian. But current Automation
runs already provide history visibility.

**Dependencies:** All present. Guardian Events + Automation Runs exist.

**Data Model Complexity:** Low. ~2 tables: notifications, acknowledgments.

**External Services:** None for V1 (local inbox only). Future: email/SMS.

**Financial/Safety Risk:** Low. Read-only notification. Risk: severity
labels misinterpreted — mitigated by neutral language.

**Testability:** High. No external dependencies.

**Estimated Slices:** 1 slice.

**Verdict:** DEFER. Automation Frontend already provides run history and
event visibility. Notification adds value only when there are multiple
automated workflows generating events that need triage. Premature for
a single workstream (Guardian only).

### Candidate D — Family Goals & Reporting

**Goal:** Education, retirement, charity, cash reserve goals tracked
with monthly/quarterly/annual reports against Portfolio+Policy.

**Owner Direct Value:** High for long-term planning. Provides the "why"
behind asset allocation and decisions.

**Dependencies:** Portfolio Snapshot + Policy exist. Missing: goal
tracking models, projection logic, report generation.

**Data Model Complexity:** Medium. ~3 tables: goals, goal_allocations,
reports/snapshots.

**External Services:** None required for V1.

**Financial/Safety Risk:** Low-Medium. Projections could be misinterpreted
as guarantees. Mitigation: explicit "projections are not predictions."

**Testability:** High. Deterministic calculations.

**Estimated Slices:** 2-3 slices.

**Verdict:** DEFER. While valuable, Family Goals is a consumer of the
Committee (Owner discusses goals → Committee analyzes → Owner decides).
Building Committee first creates the decision infrastructure that Goals
would feed into. Also needs Portfolio projections which aren't built yet.

### Candidate Comparison Matrix

| Dimension | A: AI Committee | B: Market Data | C: Notifications | D: Family Goals |
|-----------|:-:|:-:|:-:|:-:|
| Owner value | ★★★★★ | ★★★ | ★★ | ★★★★ |
| Deps satisfied | ✓ (all Foundation) | ✓ (ext APIs needed) | ✓ | ✓ (projections needed) |
| Personal V1 importance | ★★★★★ | ★★★★ | ★★ | ★★★ |
| Data model complexity | Med | Low-Med | Low | Med |
| External services | LLM API required | Data APIs required | None (V1) | None |
| Financial/safety risk | HIGH | Low | Low | Low-Med |
| Hallucination risk | HIGH | None | None | None |
| Testability | Med | High | High | High |
| Local-only viable | Low | Med | High | High |
| Explainability | ★★★ (citations needed) | ★★★★★ | ★★★★★ | ★★★★★ |
| Feedback loop | Owner decides | Data drives decisions | Owner acknowledges | Owner tracks |
| Implementation slices | 3 | 1-2 | 1 | 2-3 |
| Future unlocks | ★★★★★ | ★★★★ | ★★ | ★★★ |
| Estimated time | 3-4 weeks | 1-2 weeks | 1 week | 2-3 weeks |

### Recommendation

**Sprint 006 = AI Committee Foundation (A) + Evidence Pipeline (B), combined.**

The evidence pipeline is a prerequisite — the Committee needs an evidence
contract to distinguish "this is a fact from your Portfolio" from "this
is the model's opinion." Without it, the Committee is just a chat interface
with no audit trail.

V1 scope: Owner-initiated proposals with CompoundOS internal evidence
(Household, Policy, Portfolio, Decisions, Guardian Events). External market
data deferred to a future evidence source integration.

---

## 3. AI Committee Design Approach Comparison

### Approach 1 — Single-model structured multi-perspective analysis

One LLM call. Prompt includes all context (Policy, Portfolio, proposal).
Model outputs structured JSON with all role perspectives in one response.

| Aspect | Assessment |
|--------|-----------|
| Correctness | Low. Single model has no adversary. No disagreement. |
| Explainability | Medium. All output from one source — hard to attribute. |
| Token/cost | Low. One call. |
| Latency | Low. One round trip. |
| Failure isolation | None. One failure = all perspectives lost. |
| Provider portability | Medium. Single prompt, easy to swap. |
| Reproducibility | Low. Non-deterministic. |
| Prompt injection | High risk. All context in one prompt. |
| Testability | Low. Mock validates structure only. |
| Owner experience | Clean but shallow. No visible deliberation. |

### Approach 2 — Multi-call role-separated committee

Separate LLM calls for each role (Long-Term, Risk, Policy Alignment,
Devil's Advocate). Each receives role-specific context and instructions.
Synthesis call aggregates all role outputs.

| Aspect | Assessment |
|--------|-----------|
| Correctness | Medium. Multiple perspectives reduce blind spots. |
| Explainability | High. Each role attributable. No synthesis can erase minority. |
| Token/cost | High. N roles × context. Synthesis adds more. |
| Latency | High. Sequential or parallel calls. |
| Failure isolation | Good. One role fails → others complete → partial report. |
| Provider portability | Medium. Per-role prompts, more surface area. |
| Reproducibility | Low. Each call non-deterministic. |
| Prompt injection | Medium. Each role gets limited context. |
| Testability | Medium. Mock per-role, validate synthesis structure. |
| Owner experience | Rich. Visible multi-perspective deliberation. |

### Approach 3 — Deterministic evidence pipeline + optional LLM narration

Deterministic rules query CompoundOS for facts. Evidence packet built
with citations (Policy §X, Portfolio holding Y, Guardian Event Z).
LLM receives facts only — no raw data. LLM organizes and explains but
cannot invent facts. Every claim must cite an evidence ID or be marked
"model inference."

| Aspect | Assessment |
|--------|-----------|
| Correctness | Highest. Facts are deterministic. LLM cannot fabricate. |
| Explainability | Highest. Every claim traceable to evidence or model inference. |
| Token/cost | Medium. Evidence packet is compact. LLM narrates only. |
| Latency | Low-Medium. Evidence query + LLM narration. |
| Failure isolation | Excellent. Evidence fails → no LLM call. LLM fails → facts still available. |
| Provider portability | High. Evidence is provider-independent. LLM is swappable. |
| Reproducibility | High. Evidence is deterministic. LLM output varies but facts are stable. |
| Prompt injection | Lowest. LLM receives structured facts, not raw user text. |
| Testability | Highest. Evidence pipeline fully testable. LLM narration tested for structure. |
| Owner experience | Best. Facts you can verify. Opinions clearly labeled. |

### Recommendation

**Approach 3 — Deterministic evidence pipeline + LLM narration.**

V1 should use a single LLM call for narration (cost-effective) but with
deterministic evidence as the sole factual input. If Approach 2's
multi-role deliberation is desired, it can be layered on top of the
evidence pipeline in a future sprint — the evidence contract doesn't
change.

Combination: Evidence Pipeline (deterministic) → structured facts →
LLM narration (one call, structured output with mandatory opposing views).

---

## 4. Data Model Approaches

### Candidate A — Committee Session + immutable Report

```
committee_sessions (id, household_id, title, proposal_text, status, created_at)
  ├── evidence_items (id, session_id, source_type, source_id, content, citation_ref)
  └── committee_reports (id, session_id, model_provider, model_version,
       prompt_version, temperature, token_count, cost_estimate,
       supporting_arguments, opposing_arguments, risks, policy_alignment,
       minority_opinions, evidence_citations, model_inference_labels,
       insufficient_evidence_flags, report_text, generated_at)
```

All reports immutable. Re-run creates new session + new report.
Status: draft → queued → running → completed / partial_failure / failed.

### Candidate B — Proposal + Run + Role Opinion + Synthesis

```
proposals (id, household_id, title, body, status)
runs (id, proposal_id, model_provider, started_at, completed_at, status)
role_opinions (id, run_id, role_name, opinion_text, evidence_refs, generated_at)
synthesis_reports (id, run_id, report_text, conflict_flags, generated_at)
```

More granular but duplicates orchestration patterns from Sprint 005.
Confusing overlap with automation "runs" namespace.

### Candidate C — Reuse Decision Journal

Add AI-generated analysis as a new Decision Journal entity type.
Decisions already have confirmed snapshots and corrections. AI analysis
becomes a non-confirmed append-only record attached to Decision identity.

Avoids new domain. But conflates "Owner's actual decision" with
"AI's analysis of a proposal." Different semantics, different lifecycle.

### Recommendation

**Candidate A — Committee Session + immutable Report.**

Clean separation from Decision Journal (analysis ≠ decision).
Session groups evidence + report. Report is immutable (no edits, only
re-run to create new session). Evidence items cite CompoundOS entities
by ID (portfolio_snapshot, policy_version, guardian_event).

Decision Journal handoff: when Owner accepts/rejects based on report,
a Decision Journal entry is created referencing the committee_session_id
as its evidence source. The Committee doesn't mutate Decisions.

---

## 5. Safety Model

### Core Safety Rules

1. AI output is **decision support**, not investment advice.
2. No autonomous trading, order generation, or execution.
3. No automatic Portfolio, Policy, Guardian, or Schedule mutation.
4. No automatic Decision confirmation or creation.
5. Owner explicitly initiates every session.
6. Owner explicitly accepts/rejects/records outcome in Decision Journal.
7. Supporting AND opposing arguments must both be present.
8. No one-sided recommendation allowed.
9. When evidence is insufficient, report must say "insufficient evidence."
10. Never claim real-time market data unless source and timestamp are verifiable.
11. Model/provider/prompt version must be recorded and traceable.
12. Temperature and parameters recorded per approved policy.
13. External provider failure must not fabricate results.
14. Partial role failure (if multi-role) must be clearly displayed.
15. All output uses neutral, non-advisory language.

### Prompt Injection & Data Security

- Owner Policy/Decision/Portfolio text is **untrusted data** — treated as input, not instruction.
- Evidence content must not change system policy or evaluation rules.
- Provider allowlist (only approved LLM APIs; no arbitrary URL fetch).
- No code execution via LLM output or evidence content.
- No secret, API key, or credential in prompts, DB, logs, or audit metadata.
- Financial data minimization: only send what's needed for the specific session.
- Redact unnecessary identifiers before sending to provider.
- Provider request/response logging: store metadata (provider, model, tokens, cost),
  not full prompt text (contains financial data). Configurable retention.
- Local encrypted credential storage (keyring or env-based; compare approaches).
- Timeout, retry, rate-limit, circuit breaker on provider calls.
- Token/cost budget per session and per billing period.
- Provider data-retention/privacy terms reviewed.
- Offline/unavailable state: show cached past reports, disable new sessions.

### Provider Abstraction

Single `AIModelProvider` interface with implementations for:
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude Sonnet)
- DeepSeek (DeepSeek-V3)

Provider selection per configuration, not hardcoded. Default: DeepSeek
(cost-effective, strong reasoning). Owner can configure.

---

## 6. Evidence Contract

### Evidence Item Schema

```json
{
  "id": "evt-<uuid>",
  "source_type": "portfolio_snapshot | policy_version | guardian_event | decision | owner_claim | external",
  "source_id": "<CompoundOS entity UUID or external identifier>",
  "source_title": "Q2 2026 Portfolio Snapshot v3",
  "observed_at": "2026-07-15T00:00:00Z",
  "as_of": "2026-06-30",
  "content_hash": "sha256:abc123...",
  "structured_facts": {
    "total_value": "1,500,000.00",
    "equity_allocation_pct": "65.0",
    "cash_allocation_pct": "5.0"
  },
  "provenance": "compoundos_internal",
  "freshness": "current",
  "confidence": "high",
  "citation_ref": "Portfolio Snapshot v3 §Holdings",
  "model_inference": false
}
```

### Evidence Source Types

| Type | Origin | Freshness | Confidence |
|------|--------|-----------|------------|
| portfolio_snapshot | CompoundOS | as_of date | high (immutable) |
| policy_version | CompoundOS | sealed_at | high (immutable) |
| guardian_event | CompoundOS | detected_at | high (immutable) |
| decision | CompoundOS | decision_date | high (confirmed) |
| automation_run | CompoundOS | completed_at | high (immutable) |
| owner_claim | Owner-provided | stated by Owner | medium (unverified) |
| external | External source | as reported | variable (unverified) |

### Citation Rules

Every factual claim in the report must:
- Cite at least one evidence_id, OR
- Be explicitly marked "[model inference — not based on provided evidence]"

No claim may present model training knowledge as real-time evidence.

---

## 7. Committee Roles (V1 Minimum)

### Recommended: 3 roles + Synthesis

| Role | Input | Output | Prohibitions |
|------|-------|--------|-------------|
| **Long-Term Compounding** | Policy allocations, Portfolio holdings, Decision history | Analysis of alignment with long-term compounding strategy, drift assessment | No market timing advice, no short-term trading suggestions |
| **Risk & Capital Preservation** | Household risk statement, liquidity needs, Portfolio composition | Risk exposure analysis, concentration warnings, capital preservation assessment | No panic-selling language, no "safe" guarantees |
| **Policy Alignment** | Current Published Policy, Guardian Events, Portfolio allocations | Check proposal against Policy objectives, constraints, and prohibitions | No Policy interpretation beyond literal text |
| **Synthesis** | All role outputs | Balanced summary, supporting arguments, opposing arguments, key risks, minority opinions preserved | No elimination of minority views, no single recommendation |

### Non-Goals for V1

- Devil's Advocate (separate role — can be folded into Risk)
- Macroeconomic Context (no external market data)
- Index/Passive Investing (covered by Long-Term)
- Chair/Synthesis should not override role outputs

---

## 8. API Contract (Future Implementation)

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| POST | /api/committee/sessions | Create new analysis session | 201 |
| GET | /api/committee/sessions | List sessions (pagination) | 200 |
| GET | /api/committee/sessions/{id} | Session detail with report | 200 |
| POST | /api/committee/sessions/{id}/run | Start analysis run | 201 |
| GET | /api/committee/runs/{id} | Run status + partial results | 200 |
| GET | /api/committee/reports/{id} | Full immutable report | 200 |
| GET | /api/committee/evidence/{session_id} | Evidence items for session | 200 |
| GET | /api/committee/audit | Committee audit timeline | 200 |

All POST endpoints require explicit Owner confirmation. No auto-run.
Session → Run → Report lifecycle is immutable after completion.

---

## 9. UI States (Future Implementation)

- Loading, no household, no Published Policy, no Portfolio Snapshot
- Empty proposals list, proposal editor, local validation
- Evidence review (what will be sent to provider)
- Privacy/redaction review before run
- Explicit run confirmation with cost estimate
- Queued/running with role progress indicators
- Partial role failure display
- Provider unavailable / timeout / rate limit states
- Insufficient evidence warning
- Completed balanced report with:
  - Supporting arguments
  - Opposing arguments (mandatory)
  - Key risks
  - Minority opinions (preserved)
  - Evidence citations (linked)
  - Stale evidence warnings
  - Model inference labels
- Owner accept/reject/defer actions
- Decision Journal handoff (create Decision from report)
- History/detail, audit timeline
- Conflict/dirty state preservation
- Retry reads vs explicit rerun distinction

---

## 10. Test Strategy

### Persistence (Slice A)
- Migration lifecycle (00012 + additive)
- Immutability: reports uneditable after generation
- Household isolation: sessions/reports filtered
- Evidence provenance tracking
- Model/prompt version stored per report
- Corrections via re-run (new session)
- Token/cost tracking per session

### Provider Abstraction (Slice B)
- Mock provider only in CI (no live LLM calls)
- Schema validation for provider output
- Timeout enforcement
- Rate limit handling
- Malformed/missing output handling
- Partial response handling
- Provider unavailable → graceful degradation
- Token/cost cap enforcement
- No secrets in logs or error messages

### Committee Orchestration (Slice B)
- Role isolation (if multi-role)
- Deterministic evidence packet construction
- Citation validation (every claim must cite)
- Minority opinion preservation in synthesis
- Synthesis cannot invent evidence
- No evidence → "insufficient evidence" flag
- Partial role failure → partial report
- Idempotency (re-run = new session)
- Session failure → full rollback

### Safety (Slice B)
- Prompt injection resistance
- Malicious evidence rejection
- Fabricated citation detection
- Stale evidence warning
- No trading/tool call generation
- No mutation of Policy/Portfolio/Guardian
- Neutral language enforcement
- Owner confirmation required

### Frontend (Slice C)
- All approved UI states
- Accessibility (labels, roles, keyboard)
- Dirty/conflict preservation
- No auto-run on page load
- No mutation retry
- Evidence/citation display with links

---

## 11. Slice Decomposition (R2/R2/R1)

### Slice A — Persistence + Evidence Contracts (R2)
- Migration 0012: committee_sessions, evidence_items, committee_reports
- ORM models, named constraints, immutability triggers
- Evidence packet builder (deterministic queries against CompoundOS entities)
- Citation reference generation
- Source type registry
- 80+ PostgreSQL tests
- No API, no LLM, no frontend

### Slice B — Provider Adapter + Committee Orchestration + API (R2)
- AIModelProvider interface (OpenAI, Anthropic, DeepSeek adapters)
- Credential management (keyring/env)
- Committee orchestration: evidence → prompt → parse → validate → store
- 8 API endpoints under /api/committee
- Provider failure handling, rate limiting, cost tracking
- Deterministic evidence pipeline tests (mock provider)
- Safety tests (prompt injection, citation validation, neutral language)
- No frontend

### Slice C — Committee Frontend (R1)
- /committee page with typed API client
- All UI states from §9
- Evidence review and privacy redaction before run
- Report display with linked citations
- Decision Journal handoff
- Full accessibility and component tests

---

## 12. Owner Decisions Required

| ID | Question | Option A | Option B | Option C | Recommended | Rationale |
|----|----------|----------|----------|----------|-------------|-----------|
| OD-6-1 | Sprint 006 candidate | AI Committee + Evidence | Market Data only | Notifications only | **A** | Highest owner value, uses all Foundation data |
| OD-6-2 | External LLM provider | Provider-neutral abstraction | DeepSeek only | OpenAI only | **A** | Portability, cost flexibility |
| OD-6-3 | Send financial data to external LLM | Minimized structured facts only | Full Portfolio/Policy text | No external LLM (local only) | **A** | Evidence pipeline minimizes exposure |
| OD-6-4 | Evidence foundation first | Combined sprint (evidence + committee) | Evidence sprint before committee | Committee without evidence | **A** | Committee needs citations to be trustworthy |
| OD-6-5 | Committee design approach | Deterministic evidence + LLM narration | Multi-role separate LLM calls | Single structured prompt | **A** | Most testable, explainable, safe |
| OD-6-6 | Minimum V1 roles | Long-Term + Risk + Policy Alignment + Synthesis | All 7 roles | Single role only | **A** | Balanced without over-engineering |
| OD-6-7 | Data model | Committee Session + Report (Candidate A) | Proposal + Run + Roles (Candidate B) | Reuse Decision Journal (Candidate C) | **A** | Clean separation from Decisions |
| OD-6-8 | Report language | Balanced with mandatory opposing views | Recommendation allowed | Narrative without structure | **A** | Safety requirement: no one-sided advice |
| OD-6-9 | Owner outcome lifecycle | Accept → Decision Journal | Accept/Reject/Defer → Journal | Report only (no Decision) | **B** | Full lifecycle without forcing action |
| OD-6-10 | Model/prompt version retention | Store per report (immutable) | Store latest only | Don't store | **A** | Audit trail and reproducibility |
| OD-6-11 | Token/cost cap | Per-session budget | Monthly budget only | No cap | **A** | Prevents surprise costs, per-session is granular |
| OD-6-12 | Provider failure handling | Partial report (roles that succeeded) | Full retry or nothing | Silent fallback | **A** | Transparency — Owner sees what's available |
| OD-6-13 | Raw provider response retention | Metadata only (tokens, model, cost) | Full prompt + response | Nothing | **A** | Financial data in prompts — don't persist |
| OD-6-14 | Credential storage | System keyring (macOS Keychain) | Environment variable only | Config file | **A** | Most secure local option |
| OD-6-15 | External market data in V1 | Deferred — no external data | Minimal (free tier only) | Full provider integration | **A** | V1 works with CompoundOS internal data only |

---

## Predecessors & Dependencies

- Sprint 001–005: Done (Foundation complete)
- All 11 migrations intact
- Guardian/Automation operational
- personal-use-only boundary in canonical docs

## Implementation Status

- **Sprint 006 Implementation: NOT AUTHORIZED**
- All slices require separate explicit Owner authorization
- This document is a design gate deliverable only
- No migration, backend, frontend, or dependency changes are authorized

## Review Status

- Independent technical design review: Pending
- Owner Decisions: 15 pending (OD-6-1 through OD-6-15)
- Resolution required before any Slice authorization
