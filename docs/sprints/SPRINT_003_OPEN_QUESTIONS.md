# Sprint 003 Open Questions — Owner Decision Required

- Date: 2026-07-17
- Status: All Open — Owner Decision Required

| ID | Question | Option A | Option B | Option C | Recommendation | Rationale |
|----|----------|----------|----------|----------|----------------|-----------|
| OD-S3-001 | Candidate direction | A: Manual Portfolio Snapshot + Holdings Foundation | B: Guardian Data Readiness | C: Notification Infrastructure | A | Directly serves "protect capital"; foundation for B and C |
| OD-S3-002 | Data model approach | A: Current mutable holdings (simple, no history) | B: Immutable portfolio snapshots only (always append) | C: Stable identity + Draft + Immutable Snapshot (Policy/Decision pattern) | C | Auditable history, user corrections, proven immutability pattern |
| OD-S3-003 | Portfolio cardinality | A: One Portfolio per Household (single, stable) | B: Multiple named Portfolios | — | A | Single-household scope; simpler than multi-portfolio naming |
| OD-S3-004 | Account entity in MVP | A: No Account entity — holdings are flat under Portfolio | B: Optional user-named Account labels — local logical container | C: Full Account entity with institution metadata | B | User labeling without financial identifiers; defers institution |
| OD-S3-005 | Holding minimum fields | A: asset_name + quantity + total_value only | B: + unit_price + valuation_date + asset_category | C: + account + currency + notes | B | Minimal but meaningful; price enables policy comparison |
| OD-S3-006 | Quantity and value semantics | A: User enters only total_value (no quantity/price) | B: User enters quantity + unit_price; total = quantity × price (authoritative) | C: User may enter any subset; system computes what's missing | B | Single authoritative computation prevents inconsistency |
| OD-S3-007 | Manual price allowed | A: Yes — user enters unit price (no market data) | B: No — only total_value, no price decomposition | — | A | Price decomposition needed for future policy allocation comparison |
| OD-S3-008 | Currency and precision | A: Single currency (Household base_currency), no conversion | B: Multi-currency with user-entered exchange rate | C: Multi-currency, no conversion | A | Single currency avoids conversion risk; defers multi-currency |
| OD-S3-009 | Snapshot lifecycle | A: Draft → Confirmed only (simpler) | B: Draft → Confirmed → Superseded (Policy pattern) | C: Draft → Confirmed → Archived → Corrected (Decision pattern) | A | Portfolio snapshots are discrete points-in-time; supersession adds complexity without clear benefit for a manual process |
| OD-S3-010 | Correction model | A: New Snapshot (always append) | B: Correction record amending prior Snapshot | — | A | Simpler audit trail; each snapshot is self-contained |
| OD-S3-011 | Confirm required fields | A: At least one holding required | B: Zero holdings allowed (empty portfolio confirmable) | — | B | User may want to record an empty/cash-only state |
| OD-S3-012 | Cash position | A: Cash as a special holding type | B: Cash as a separate field on Portfolio | C: Cash not tracked in MVP | A | Cash is a holding; consistent data model without special treatment |
| OD-S3-013 | Private assets | A: Allowed — any asset name accepted (no validation) | B: Allowed — with "private" asset category | C: Not allowed in MVP | A | User defines what they hold; no regulatory classification |
| OD-S3-014 | Audit metadata boundary | A: changed_fields only (Policy pattern) | B: + snapshot_version_number + holding_count | C: + full holding names | A | Minimal metadata; no financial values in audit |
| OD-S3-015 | Implementation slices | A: Slice A (DB) → Slice B (API) → Slice C (Frontend) | B: Combined slice — persistence, API, and frontend together | C: Slice A (DB+API) → Slice B (Frontend) | A | Proven decomposition from Sprint 002; each slice independently reviewable |

## Recommendation Summary

All 15 Owner Decisions recommend Option A or the closest safe default.
None introduce market data, broker integration, trading, AI recommendations,
Guardian thresholds, or authentication. Each decision errs toward simplicity
and the "protect capital" principle.
