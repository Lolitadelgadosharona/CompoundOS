# Sprint 006 — Open Questions

> **ALL 15 OWNER DECISIONS RESOLVED (2026-07-20).**
>
> Implementation remains NOT AUTHORIZED.  All slices require separate
> explicit Owner authorization.  See `SPRINT_006_TECHNICAL_DESIGN.md`
> for the resolved design and Owner decisions.

## Resolution Summary

| ID | Question | Resolution | Resolved |
|----|----------|------------|----------|
| OD-6-1 | Sprint 006 candidate | **A**: AI Committee + internal Evidence Pipeline. No Market Data/Notifications/Family Goals in Sprint 006. | 2026-07-20 |
| OD-6-2 | External LLM provider | **A, V1-limited**: Provider-neutral interface; DeepSeek adapter only. Model ID configured. | 2026-07-20 |
| OD-6-3 | Data sent to provider | **A**: Minimized structured facts only. Privacy Preview required. No raw Policy/Portfolio text. | 2026-07-20 |
| OD-6-4 | Evidence foundation | **A**: Combined sprint. No LLM call without Evidence Packet. | 2026-07-20 |
| OD-6-5 | Committee design | **A**: Deterministic evidence + one structured LLM call. | 2026-07-20 |
| OD-6-6 | Committee roles | **B, single-call**: All 7 perspectives in one call. Macro declares insufficient evidence. | 2026-07-20 |
| OD-6-7 | Data model | **A + Outcome entity**: Sessions, Evidence, Reports (immutable), Outcomes (append-only). | 2026-07-20 |
| OD-6-8 | Report language | **B, restricted**: recommended_direction with approved enum. No Buy/Sell/Hold. | 2026-07-20 |
| OD-6-9 | Owner outcome | **B, Draft-only**: Accept/Reject/Defer → Outcomes → optionally creates Decision Draft only. | 2026-07-20 |
| OD-6-10 | Version retention | **A**: Every Report stores provider/model/prompt/schema/temperature/tokens/cost. | 2026-07-20 |
| OD-6-11 | Token/cost cap | **A, explicit defaults**: 50K/8K/$1.00 per session. Configurable by Owner. | 2026-07-20 |
| OD-6-12 | Provider failure | **B, explicit retry**: All-or-nothing, max 1 retry (transient only). No partial report. | 2026-07-20 |
| OD-6-13 | Response logging | **A, clarified**: No raw prompt/response persisted. Normalized immutable Report required for history. | 2026-07-20 |
| OD-6-14 | Credential storage | **A**: macOS Keychain. CI uses env var. Plaintext config forbidden. | 2026-07-20 |
| OD-6-15 | Market data in V1 | **A**: Deferred. CompoundOS internal data only. External source_type reserved, unused. | 2026-07-20 |

## Additional Owner Constraints

- **Manual-only**: Committee is completely manual-only.  No Schedule,
  Guardian Event, Portfolio Confirm, or Automation Worker may trigger it.
  Future automation requires a new Owner Decision.
- **V1 temperature**: 0 or lowest deterministic value available.
- **Decision Journal integration**: Creates Draft only; never auto-confirms.
  Existing Decision lifecycle unchanged.

## Implementation Status

- **Sprint 006 Implementation: NOT AUTHORIZED.**
- All slices require separate explicit Owner authorization.
- This document is complete pending independent technical design review.

## Dependencies

- Sprint 001–005: Done.
- External: DeepSeek API (V1 provider).  No other external dependencies.
- CI: N/A (docs-only at this stage).
