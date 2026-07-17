# Sprint 004 Open Questions — Owner Decisions Required

- Date: 2026-07-17
- Status: 13 Open — Owner Decision Required
- Baseline: main @ 759a556

## Owner Decisions

| ID | Question | Option A | Option B | Option C | Recommended | Rationale |
|----|----------|----------|----------|----------|-------------|-----------|
| OD-S4-001 | Auto-evaluate after Portfolio Confirm? | Yes — evaluate all Confirmed Checks immediately after each Portfolio Confirm | No — evaluation is manual only, Owner triggers explicitly | — | A | Immediate feedback after Confirm closes the loop. No scheduler needed. The Confirm transaction already locks Household → Portfolio; evaluation can follow in the same request or a synchronous follow-up. |
| OD-S4-002 | What to do when Policy has no Current Published Version? | Skip evaluation — return "No published Policy" | Evaluate against empty Policy (all drift = 100%) | Fail with 409 — require published Policy | A | Evaluating against empty Policy produces 100% drift for every category — noise, not signal. Skip is cleaner and matches the Decision Journal pattern (requires current Published Version). |
| OD-S4-003 | GuardianEvent PASS records — should events be written when threshold is NOT exceeded? | Yes — write an event with passed=true for every evaluation | No — only write events when threshold IS exceeded | — | A | A pass record proves evaluation ran and found nothing. Audit trail completeness. Without it, "no events" could mean "not evaluated" or "evaluated and passed." |
| OD-S4-004 | Concentration check: allow "all holdings" as target? | Yes — concentration against total portfolio (any single holding > threshold) | No — only category-level checks | — | B | Category-level is simpler, matches Policy allocation categories, and avoids the "which holding is the problem?" ambiguity. If the Owner wants single-holding monitoring, they can create a category check with that category. |
| OD-S4-005 | Staleness check: what if there is no Portfolio Snapshot at all? | Skip — return "No snapshot" with zero events | Create an event — treat absence as infinite staleness | — | A | "No snapshot" is a distinct state from "stale snapshot." The Wallet UI already shows the empty-portfolio state. Guardian should not fabricate events for missing data. |
| OD-S4-006 | Check naming: enforce uniqueness? | Yes — UNIQUE constraint on guardian_checks.name (per household) | No — allow duplicate names | — | A | Matches the Policy allocation-name pattern (NFKC + trim + case-insensitive). Owner should be able to distinguish "Equity drift > 5%" from "Equity concentration > 30%." |
| OD-S4-007 | Evaluation scope: all checks or individual? | Individual — evaluate one Check at a time | All — always evaluate all Confirmed Checks together | Both — support individual and "evaluate all" | C | Individual is useful for testing a new rule. "Evaluate all" is the normal workflow. The API should support both: POST /api/guardian/evaluate (all) and POST /api/guardian/checks/{id}/evaluate (single). |
| OD-S4-008 | Drift check: what if Policy has allocation for a category but Portfolio has zero holdings in that category? | drift = policy_pct (100% of target is missing) | drift = 0 (zero holdings, zero drift) | skip that category | A | If Policy says 20% equities and Portfolio has 0% equities, the drift is 20 percentage points — that's the mechanical truth. Treating zero holdings as "no drift" hides a meaningful condition. |
| OD-S4-009 | Severity label: who decides? | Owner-defined per Check (dropdown: info/warning/critical) | System-computed from threshold magnitude | — | A | Severity is organizational, not mathematical. A 5% drift for one Owner is critical; for another it's informational. The threshold is the mathematical boundary; severity is the Owner's label for it. |
| OD-S4-010 | Guardian Check Draft discard: before-first-Confirm vs after-Confirm? | Identity deletion (like Policy/Decision) for never-Confirmed; Draft-only deletion for after-Confirm | Always only delete Draft — identity persists | — | A | Matches Policy and Decision discard pattern. Never-confirmed = atomic identity deletion. After-confirm = delete draft only, identity and confirmed versions preserved. |
| OD-S4-011 | GuardianEvent deduplication: prevent duplicate events for same (Check, Policy Version, Portfolio Snapshot) combination? | Yes — UNIQUE constraint on (check_version_id, policy_version_id, portfolio_snapshot_id) | No — each evaluation run writes independent events, even if inputs unchanged | — | A | Duplicate events add noise. If nothing changed (same Policy Version + same Portfolio Snapshot), re-evaluating produces the same result. A UNIQUE constraint with ON CONFLICT DO NOTHING is clean. |
| OD-S4-012 | Guardian UI: show evaluation results inline or as separate page? | Separate /guardian page with tabs (Checks, Events, Audit) | Inline on /portfolio page — drift shown next to holdings | — | A | Guardian is a distinct concept from Portfolio. A separate page keeps Portfolio focused on holdings and Guardian focused on monitoring. The homepage nav already has room for another link. |
| OD-S4-013 | Should the evaluation endpoint return a summary or individual events? | Summary only — {checks_evaluated: N, passed: N, exceeded: N} with event IDs | Individual events array — caller aggregates | Both — summary + events array | C | Summary for the UI dashboard, individual events for detail view. The response can include both: {summary: {...}, events: [...]}. Matches the snapshot history response pattern. |

## Additional Owner Constraints

1. **No scheduled/cron evaluation in Sprint 004**: All evaluation is manual or on-demand (OD-S4-001 auto-evaluate after Confirm is still synchronous within the same HTTP request, not a background job).

2. **No notification delivery**: Guardian Events are viewable in the UI only. No email, SMS, push, or platform notification.

3. **No AI-generated rules**: All Guardian Checks are Owner-authored. The system never suggests thresholds, categories, or severities.

4. **No trading**: Guardian Events are informational only. They cannot trigger orders, rebalancing, or any financial action.

5. **Local-only**: No external services. Evaluation uses only local PostgreSQL data (Policy, Portfolio).

6. **Audit metadata redaction**: GuardianEvent audit records contain check_id, version_number, policy_version_number, portfolio_snapshot_version, passed, and drift_percentage. No financial values (quantities, prices, total_values) in audit metadata.
