# Sprint 003 Open Questions — Owner Decisions Resolved

- Date: 2026-07-17
- Status: All 15 Resolved by Project Owner
- Resolved by: Project Owner on 2026-07-17

## Owner Decisions

| ID | Question | Selected | Rejected |
|----|----------|----------|----------|
| OD-S3-001 | Candidate direction | A: Manual Portfolio Snapshot + Holdings Foundation | B, C |
| OD-S3-002 | Data model approach | C: Stable identity + Draft + Immutable Snapshot | A, B |
| OD-S3-003 | Portfolio cardinality | A: One Portfolio per Household | B |
| OD-S3-004 | Account entity in MVP | B: Optional user-named Account labels — local logical container, no identifiers | A, C |
| OD-S3-005 | Holding minimum fields | B: asset_name + quantity + unit_price + valuation_date + asset_category | A |
| OD-S3-006 | Quantity and value semantics | B: quantity × unit_price = authoritative total (computed, not stored) | A, C |
| OD-S3-007 | Manual price allowed | A: Yes — user-entered unit price with valuation_date and manual source | B |
| OD-S3-008 | Currency and precision | A: Single currency = HouseholdProfile.base_currency, no conversion | B, C |
| OD-S3-009 | Snapshot lifecycle | A: Draft → Confirmed only, no supersession/archive | B, C |
| OD-S3-010 | Correction model | A: New Snapshot — always append, each self-contained | B |
| OD-S3-011 | Confirm required fields | B: Zero holdings allowed — must display explicit "0 holdings" warning before Confirm | A |
| OD-S3-012 | Cash position | A: Cash as holding — quantity represents cash amount, unit_price fixed at 1.00 | B, C |
| OD-S3-013 | Private assets | A: Allowed — user manual valuation only, no market price implied | B, C |
| OD-S3-014 | Audit metadata boundary | B: changed_fields + snapshot_version_number + holding_count | A |
| OD-S3-015 | Implementation slices | A: Slice A (DB) → Slice B (API) → Slice C (Frontend) | B, C |

## Additional Owner Constraints

1. **Decimal-string API**: All monetary amounts and quantities transmitted as decimal strings through the API boundary. Backend uses Python Decimal. Database uses PostgreSQL NUMERIC. No IEEE 754 floating-point in any authoritative computation. No silent rounding — all rounding is explicit, deterministic, and documented.

2. **Single currency**: Portfolio currency must equal HouseholdProfile.base_currency. No conversion, no exchange rate, no multi-currency support.

3. **Manual price**: Unit price is a user-entered valuation statement. Each holding records valuation_date and source=manual. No automatic price, no market data, no broker feed.

4. **Cash**: Cash is a holding with asset_name recording the description, quantity representing the cash amount, and unit_price fixed at 1.00. Total value equals quantity. This makes cash holdings directly comparable to other assets without special treatment.

5. **Private assets**: Allowed. User manual valuation only. No market price implied, no exchange validation, no ticker lookup. Category "private" is a user label only.

6. **Account**: Local label only. No account numbers, routing numbers, institution identifiers, credentials, or API keys. Purely a user-organizational container.

7. **Empty snapshot**: Zero holdings allowed for Confirm. Before Confirm, the UI must display an explicit "0 holdings — no assets recorded" warning. This is distinct from holding Cash.

8. **Immutable Confirmed Snapshot**: Once Confirmed, snapshots are immutable. Corrections create a new Snapshot — always append, never modify. Previous snapshots are permanently preserved for audit.

## Resolution Summary

All 15 Owner Decisions resolved. Eight additional constraints provide precision on decimal handling, currency, manual price semantics, cash modeling, private assets, accounts, empty snapshots, and immutability. No decision introduces market data, broker integration, trading, AI recommendations, Guardian thresholds, or authentication.
