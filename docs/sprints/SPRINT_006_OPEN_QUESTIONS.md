# Sprint 006 — Open Questions

> **All 15 Owner Decisions require explicit Owner resolution before any
> Sprint 006 slice is authorized for implementation.**

| ID | Question | Status |
|----|----------|--------|
| OD-6-1 | Sprint 006 candidate: AI Committee + Evidence (A), Market Data only (B), or Notifications only (C)? | **Owner Decision Required** |
| OD-6-2 | External LLM provider: provider-neutral abstraction (A), DeepSeek only (B), or OpenAI only (C)? | **Owner Decision Required** |
| OD-6-3 | Send financial data to external LLM: minimized structured facts only (A), full Policy/Portfolio text (B), or no external LLM — local only (C)? | **Owner Decision Required** |
| OD-6-4 | Evidence foundation: combined sprint with committee (A), separate evidence sprint first (B), or committee without evidence (C)? | **Owner Decision Required** |
| OD-6-5 | Committee design: deterministic evidence + LLM narration (A), multi-role separate LLM calls (B), or single structured prompt (C)? | **Owner Decision Required** |
| OD-6-6 | Minimum V1 roles: Long-Term + Risk + Policy Alignment + Synthesis (A), all 7 roles (B), or single role only (C)? | **Owner Decision Required** |
| OD-6-7 | Data model: Committee Session + Report (A), Proposal + Run + Roles (B), or reuse Decision Journal (C)? | **Owner Decision Required** |
| OD-6-8 | Report language: balanced with mandatory opposing views (A), recommendation allowed (B), or narrative without structure (C)? | **Owner Decision Required** |
| OD-6-9 | Owner outcome: Accept only → Decision Journal (A), Accept/Reject/Defer → Journal (B), or report only — no Decision (C)? | **Owner Decision Required** |
| OD-6-10 | Model/prompt version: store per report immutable (A), store latest only (B), or don't store (C)? | **Owner Decision Required** |
| OD-6-11 | Token/cost cap: per-session budget (A), monthly only (B), or no cap (C)? | **Owner Decision Required** |
| OD-6-12 | Provider failure: partial report with succeeded roles (A), full retry or nothing (B), or silent fallback (C)? | **Owner Decision Required** |
| OD-6-13 | Raw provider response: metadata only — no financial data in logs (A), full prompt + response (B), or nothing (C)? | **Owner Decision Required** |
| OD-6-14 | Credential storage: system keyring — macOS Keychain (A), env var only (B), or config file (C)? | **Owner Decision Required** |
| OD-6-15 | External market data in V1: deferred — CompoundOS internal only (A), minimal free tier (B), or full provider integration (C)? | **Owner Decision Required** |

## Resolution Process

1. Owner reviews each OD in the Technical Design document.
2. Owner selects one option per OD (or provides an alternative).
3. All decisions are recorded in this document with resolution date and rationale.
4. Technical Design is updated to reflect resolved decisions.
5. Only after ALL 15 ODs are resolved may any Slice be authorized.

## Implementation Status

- **Sprint 006 Implementation: NOT AUTHORIZED**
- All slices require separate explicit Owner authorization after OD resolution.

## Dependencies

- Sprint 001–005: Done (all Foundation capabilities available)
- External: None required for design gate
- CI: N/A (docs-only at this stage)
