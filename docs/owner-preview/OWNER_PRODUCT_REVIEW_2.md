# Owner Product Review Sprint 2

Scope: local `codex/compoundos-owner-preview` only. No production deployment,
provider connection, broker execution, threshold change or migration was added.

## Strategy and ledger

`investment_configurations` remains the append-only strategy/contribution version,
bound to the published Policy. Explicit configuration submission is Owner approval
of the DEMO strategy; configuration is not derived from positions. Positive targets
must sum exactly to 100%; duplicates and invalid weights are rejected by the existing
configuration and deterministic engine. Omitted instruments have strategic weight zero.
They remain in valuation and the native ledger but are not purchase or automatic sale targets.

The user-authorized fictional strategy is VTI 50 / QQQ 30 / VXUS 10 / SGOV 10;
AAPL and BRK.B zero. It exists only in Preview seed/UI. The seed appends a new
configuration once, preserving old configurations, holdings, cash, Policy and decisions.
The historical marker makes restarts preserve subsequent explicit Owner edits.
No engine algorithm or global strategy default changed.

Conceptual DEMO classifications distinguish equity, geography, style and Treasury
fixed income. These are not verified live provider metadata or precise sector weights.
ETFs require look-through; no diversified ETF is classified as a single stock sector.

## Guardian semantics

Preview sector evaluation skips unknown classifications as risk facts, uses the full
position denominator for known sector lower-bound violations, and emits NOT_EVALUATED
for missing classifications/look-through. Known violations retain published severity
and thresholds. Missing required sector coverage prevents recommendation readiness,
Committee governance entry and approval; it never silently passes.

LIVE behavior follows the pre-existing code path. The unchanged contribution engine,
common valuation, real Policy and real Guardian concentration/exploration checks remain
authoritative. Risk cards separate detected risks from missing evidence.

With the current fictional ledger, the real engine assigns approximately USD 1,061.77
to VTI and USD 366.80 to QQQ. The projected positions-only concentration is 20.77%
and 20.08%, so the published 20% critical rule blocks the candidate. Allocation-table
weights include cash; Guardian concentration uses positions-only scope. These distinct
existing scopes are disclosed rather than changed to obtain a pass.

## Lifecycle and Committee

The read model maps existing candidate, Committee and Journal states to CANDIDATE,
REVIEWING, READY_FOR_DECISION, APPROVED, REJECTED and BLOCKED. Missing prerequisites
show NOT EVALUATED; insufficient Committee opinion shows HOLD. This is not a new
persisted lifecycle. Only a completed aligned review plus fresh authoritative validation
can lead to an approvable draft. Context-valid blocked candidates remain visible after
reload; readability does not confer approval readiness.

Six simulated analytical perspectives use existing role sections: long-term, index,
risk, macro, quant and devil's advocate. All real provider-output, provenance/citation,
numeric assertion, exact-context, expiry and duplicate-call validators remain intact.
The internal qualitative confidence required by the legacy validator is not a calibrated
confidence methodology; Owner UI always shows NOT AVAILABLE.

A read-only simulated discussion remains available for blocked/unreviewed candidates.
It explicitly says DISCUSSION ONLY / GOVERNANCE REVIEW INCOMPLETE. Its references
point to a hash of the supplied deterministic DEMO analysis; it is not a persisted
Committee report and cannot authorize approval. Macro has no supplied evidence and
is NOT EVALUATED. Supporting/opposing arguments, known risks, limitations, alternatives
and what changes the view are visible. Ask Committee answers are local deterministic
responses drawn from supplied calculation/evidence, with no external calls.

Contribution overrides are deliberately deferred. Owner strategy edits create another
configuration; a new candidate and Quant/Policy/Guardian/Committee review are mandatory.
Neither alternatives nor discussion replace immutable candidate evidence.

## Owner review

Open http://localhost:3802. Inspect ACTION REQUIRED, the strategic targets and current
holdings separately, then Investment Plan and Committee. Verify known concentration
blocks and unknown sector/macro coverage, ask the sample questions, and inspect Decisions.
Evidence/calculation/audit disclosures stay collapsed. Approval never executes a trade.

This sprint is ready for local product review, not production launch. No real provider,
macro, overlap, calibrated confidence or optimizer readiness is asserted.

## Rollback

Stop Preview before restoring the prior source in a separate worktree. Preserve the
Preview volume and review evidence. Do not delete historical strategy/Committee/Journal
records or rewrite Policy. No production schema or dependency change requires rollback.
The prior application can read existing configuration JSON; use a separately appended
Owner-approved configuration if historical strategy selection is required. No automatic
rollback or reset of Owner data is performed.
