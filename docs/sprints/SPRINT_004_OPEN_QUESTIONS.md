# Sprint 004 Open Questions — Owner Decisions Resolved

- Date: 2026-07-17
- Status: All 13 Resolved by Project Owner
- Resolved by: Project Owner on 2026-07-17

## Owner Decisions

| ID | Question | Selected | Rejected | Key Constraint |
|----|----------|----------|----------|----------------|
| OD-S4-001 | Auto-evaluate after Portfolio Confirm? | B: Manual only — explicit Owner trigger | A | No automatic evaluation. Portfolio Confirm must not be coupled to Guardian. Deferred to Orchestration sprint. |
| OD-S4-002 | No Published Policy → skip or fail? | A: Skip with machine-readable status `no_published_policy` | B, C | No GuardianEvents created. EvaluationRun records skip reason. |
| OD-S4-003 | Write events when within bounds? | B: Only exceeded thresholds → Events. EvaluationRuns track "evaluated and found nothing." | A | New `guardian_evaluation_runs` table proves evaluation happened. Events only for breaches. `exceeded` field always TRUE on Events. |
| OD-S4-004 | Category or individual holding level? | B: Category-level only. Renamed to `category_exposure` | A, C | Single-security concentration deferred. Holding-level belongs in future sprint. |
| OD-S4-005 | No snapshot → skip or infinite stale? | A: Skip, record `no_portfolio_snapshot` in EvaluationRun | B | No synthetic events for missing data. |
| OD-S4-006 | Unique check names? | A: UNIQUE after trim + NFKC + casefold, per household | B | Normalization rules consistent across API, DB constraint, and tests. |
| OD-S4-007 | Evaluate all or individual? | C: Both — shared evaluation service | A, B | POST /api/guardian/evaluate (all) and POST /api/guardian/checks/{id}/evaluate (single). Same computation path. |
| OD-S4-008 | Drift: percentage points or percent-of-target? | A: Absolute percentage points `abs(actual - target)`. Equal-to-threshold NOT exceeded. | B, C | All Decimal with ROUND_HALF_EVEN. target=20%, actual=0% → drift=20pp. |
| OD-S4-009 | Severity: Owner or system? | A: Owner-defined | B | System never auto-upgrades severity. |
| OD-S4-010 | Discard semantics | A: Pattern match — identity deletion if never confirmed, draft-only if confirmed exists | B | Matches Policy/Decision pattern. |
| OD-S4-011 | Event deduplication | A: Deterministic input fingerprint | B | Drift/exposure: (check_version_id, policy_version_id, portfolio_snapshot_id). Staleness: (check_version_id, portfolio_snapshot_id, as_of_date). as_of_date excluded from drift/exposure fingerprint. UNIQUE with ON CONFLICT DO NOTHING. |
| OD-S4-012 | UI: separate page or inline? | A: Separate `/guardian` page | B | Guardian must not be coupled into Portfolio mutation workflow. |
| OD-S4-013 | Evaluation response format | C: Both — summary + events with `evaluation_run_id`, `status`, `skip_reason` | A, B | Machine-readable status, human-readable skip_reason, checks_evaluated, events_created, events array. |

## Mandatory Design Clarifications

1. **Data model**: Five tables — `guardian_checks`, `guardian_check_drafts`, `guardian_check_confirmed`, `guardian_evaluation_runs`, `guardian_events`.

2. **Category matching**: trim + NFKC + casefold exact match between Policy `asset_class_name` and Portfolio `asset_category`. No fuzzy matching, no AI mapping, no silent guessing. Unmatched categories recorded in EvaluationRun.

3. **Actual percentage calculation**: Category `total_value` / all holdings `total_value`. Total value of zero → skip with `zero_total_value`. No division by zero, no fake events.

4. **Staleness**: Explicit `as_of_date` injected by engine. Calendar days (DATE subtraction). Boundary: `>` (strict). No system clock reads during check evaluation.

5. **Terminology**: GuardianEvent = "threshold breach fact." EvaluationRun = "evaluation execution fact." Do not confuse in API, UI, or docs.

6. **Lock order**: Household FOR UPDATE → read only. No write locks on Policy/Portfolio/Checks. No external calls. Pure local computation.

7. **Auto-evaluate prohibited**: OD-S4-001 B. Evaluation is manual only in Sprint 004.

8. **Non-goals**: No trading, no advice, no AI rules, no market data, no notification delivery, no scheduled/cron evaluation, no check retirement/deletion.

## Resolution Summary

All 13 Owner Decisions resolved with detailed constraints. Renamed `concentration` → `category_exposure`. Added `guardian_evaluation_runs` table. Drift uses absolute percentage points with strict `>` boundary. Deduplication uses deterministic input fingerprints with `as_of_date` for staleness. Evaluation is manual-only in Sprint 004.
