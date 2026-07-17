# Sprint 002 Slice 3 Technical Design — Incremental Fix Re-Review Report

- **Date:** 2026-07-16
- **Branch:** `planning/sprint-002-slice-3-decision-journal`
- **Original reviewed HEAD:** `043c07d9791b2031fa4ca94271a2521c5139756b`
- **Current HEAD:** `1cecef9ba5cb6f4db06cdf419c41ff5d930c29c6`
- **PR:** #10 (OPEN, Draft, MERGEABLE)
- **Original conclusion:** REQUEST CHANGES
- **Original findings:** HIGH: M-1, M-2; MEDIUM: M-3, M-4, M-5; LOW: L-1, L-2, L-3
- **CI:** All 6 checks pass (push + pull_request × infrastructure/backend/frontend)

---

## 1. Resolution Matrix

### M-1 — Draft Discard Identity Semantics (HIGH)

**Status: RESOLVED**

- OD-S3-13 exists in §12 and is **Open — Owner Decision Required**.
- Three options fairly compared: (A) atomic identity deletion for never-Confirmed decisions, (B) discarded status preserving identity, (C) orphan state — marked **Not Recommended**.
- No undefined `UPDATE decision status` remains in discard context. The only two `UPDATE decision status` occurrences are in the Confirm transaction (§3.3 line 238, §8.6 line 1517), where the target status is clearly `confirmed`.
- All discard behavior is conditional on OD-S3-13 across: §3.3, §4.6, §7.2, §8.5, §10, §11.2, §11.3, §11.4.
- The committed orphan state (`status = 'draft'` with no Draft row) is explicitly prohibited in §7.2, §8.5, and §10.
- Option A correctly limits identity deletion to never-Confirmed decisions. Confirmed/Archived/Correction/AuditEvent remain never hard-deleted. AuditEvent `entity_id` (UUID, no FK) is preserved even if identity is deleted — §6.9 documents this explicitly.
- Option B correctly identifies `discarded` as a lifecycle extension requiring Owner approval.
- §8.5 Discard API table includes an explicit `Identity handling (pending OD-S3-13)` row describing both options.
- §7.7 Expected 409 Responses includes conditional discard loser response.
- Test matrix covers: standalone discard, no orphan, discard rollback, Confirm/Discard race (both options), list/detail boundary.

**Non-blocking follow-up (NBF-2):** §6.3 Decision identity lifecycle trigger (`fn_decision_identity_lifecycle()`) lists only three transitions (`draft→confirmed`, `confirmed→archived`, `archived→confirmed`). If OD-S3-13 Option B is chosen, a `draft → discarded` transition would be needed. This dependency is not noted in the trigger description. The OD-S3-13 description itself mentions "trigger rules" impact, so the dependency is traceable, but a conditional note in §6.3 would improve consistency.

### M-2 — Correction Numbering Mechanism (HIGH)

**Status: RESOLVED**

- No instance of `IDENTITY ALWAYS per Decision` remains in the document.
- §6.5 explicitly states: "PostgreSQL `GENERATED ALWAYS AS IDENTITY` is a **table-level** sequence. It produces globally unique, monotonically increasing integers across all rows in the table, not per-decision sequential numbering."
- OD-S3-14 exists in §12 and is **Open — Owner Decision Required**.
- Three options technically feasible and fairly described:
  - Option A: Decision row `FOR UPDATE` + `MAX(correction_number)+1` + `UNIQUE(decision_id, correction_number)`. Concurrent Corrections serialize through Decision lock. Rollback leaves no committed gap.
  - Option B: Global `correction_sequence_number BIGINT GENERATED ALWAYS AS IDENTITY`. Gaps permitted. Not per-decision contiguous.
  - Option C: UUID identity + `created_at` ordering. No human numbering.
- Recommended Option A with explicit note: "The design must not claim that two concurrent Corrections can proceed without any shared lock."
- All sections conditional on OD-S3-14: §6.5, §7.1, §7.2, §8.10, §8.11, §9.2, §11.2, §11.3.
- §7.1 includes conditional Correction append lock order paragraph.
- §7.2 Concurrent Corrections correctly describes per-option concurrency model.
- §5.3 replaces `correction_count` with `correction_number` (individual, not total).
- Test matrix covers: numbering across two Decisions, concurrent Corrections, rollback/gaps.

### M-3 — Confirm Lock Order Inconsistency (MEDIUM)

**Status: RESOLVED**

Lock order matrix across all sections:

| Section | Lock Order |
|---|---|
| §3.3 summary | Lock Policy FOR UPDATE → validate → lock decision → lock draft |
| §4.6 step-by-step (13 steps) | Step 2: Policy FOR UPDATE → Step 3: validate Published Version → Step 4: Decision FOR UPDATE → Step 5: Draft FOR UPDATE |
| §7.1 recommended | `Household → Policy → Policy Version → Decision → Draft → Snapshot/Correction` |
| §7.1 detail | `investment_policies` (FOR UPDATE) → `decisions` (FOR UPDATE) → `decision_drafts` (FOR UPDATE) |
| §8.6 API table | Lock Policy → lock decision → lock draft → validate → INSERT snapshot → DELETE draft → UPDATE decision status → INSERT AuditEvents |
| §7.2 deadlock analysis | Decision confirm: locks Policy → locks Decision → locks Decision Draft |

All sections use the same order: Policy first, then Decision, then Draft. No `lock decision → lock draft → fetch Policy` pattern exists.

- No Decision→Policy reverse lock order exists.
- Consistent with existing Policy publish lock order (Policy → Draft).
- Policy supersession race: both lock Policy first; one waits; re-validation after lock.
- OD-S3-5 historical Version: §4.6 step 3 notes conditional re-validation.
- No unnecessary Household lock.
- Unrelated IntegrityError: §7.8 explicitly states no mis-mapping to 409.
- Response: §8.6 "Constructed from transaction-scoped scalar values, no post-commit read."
- Rollback: §7.9 "All transactions use session.begin() which automatically rolls back on exception."

### M-4 — Archived Correction Eligibility (MEDIUM)

**Status: RESOLVED**

- OD-S3-15 exists in §12 and is **Open — Owner Decision Required**.
- OD-S3-7 no longer includes "archived Decisions still correctable" — the Recommended column now reads "Archive = list hiding, allow unarchive, optional archive_reason" without the correction eligibility claim.
- §4.7 Archived+Correction is fully conditional: two branches (may/may not receive Corrections) with trigger, API, UI, and concurrency implications for each.
- §8.10 Append Correction API: status check is "correctable per OD-S3-15".
- §7.2 Archive vs Correction race: conditional on OD-S3-15.
- §9.2 UI: Append Correction availability conditional on OD-S3-15.
- §11.2 and §11.3 test matrix covers both options.
- OD-S3-15 Option B correctly notes dependency on OD-S3-7 for unarchive.

**Non-blocking follow-up (NBF-1):** §6.3 Correction INSERT trigger (`fn_decision_correction_immutability()`) validates only that `corrected_entry_id` references a valid Confirmed snapshot. It does not validate the decision's current status for correctability. The service-level check (§8.10) is conditional on OD-S3-15, but without a trigger-level status check, a direct SQL INSERT could bypass the service and insert a Correction on a Decision whose status does not permit it. The trigger description should note this conditional dependency.

### M-5 — Household Audit Resource Boundary (MEDIUM)

**Status: RESOLVED**

- §5.5 now includes an "Existing Household audit endpoint analysis" paragraph documenting:
  - The current repository query filters by `household_id` only, without restricting `entity_type`.
  - Decision events will naturally appear once written.
  - This is a user-visible resource content expansion, not "no change."
- OD-S3-10 expanded to cover: Decision-filtered endpoint, Household timeline Decision event inclusion, and response size/pagination impact.
- Three options compared: (A) Decision-filtered + Household timeline includes, (B) Decision-filtered only + restrict Household timeline, (C) New combined activity endpoint.
- Option B correctly notes code modification required.
- Option C correctly introduces a new endpoint with overlapping purpose.
- Recommended Option A with "Owner Approval Required" label.
- Verified against actual code: `list_audit_events` in `repositories/households.py` (lines 46-52) filters only by `household_id`. The design accurately describes the current behavior.

### L-1 — Decision Detail Original/Effective Response (LOW)

**Status: RESOLVED**

- §8.7 response shape is explicit: `original_snapshot`, `effective_snapshot`, `latest_correction_metadata`, `corrections_count`.
- No-Correction effective semantics: "return the original snapshot content in this field (not null)."
- With-Correction effective depends on OD-S3-8 (full replacement, field patch, explanatory only).
- `selected_policy_version_id` is not correctable (OD-S3-9), and the effective view description doesn't imply replacement.
- §9.2 UI: "Original view displays `original_snapshot`. Effective view displays `effective_snapshot`."
- §11.4 frontend test: "Original/effective view consistency" test added.

### L-2 — Confirm/Discard Loser Response (LOW)

**Status: RESOLVED**

- §7.2 Confirm vs Discard race is fully conditional on OD-S3-13.
- Option A (identity deletion): discard winner → confirm 404; confirm winner → discard 409.
- Option B (discarded status): discard winner → confirm 409; confirm winner → discard 409.
- Unrelated missing decision ID always returns 404.
- §7.7 Expected 409 Responses includes both conditional scenarios.
- No hardcoded "discard wins → confirm 404" without the alternative.

### L-3 — correction_count Audit Metadata (LOW)

**Status: RESOLVED**

- `correction_count` removed from §5.3 Metadata Allowlist.
- Replaced with `correction_number` (individual Correction's number, conditional on OD-S3-14).
- Explicit exclusion note: "correction_count is not included in AuditEvent metadata."
- §8.10 Audit metadata: `{ "correction_number": N }` with cross-reference to §5.3.
- Read-time computation from Correction list query noted in §8.7 and §8.11.
- No Decision or Correction text in metadata (redaction rules unchanged).

---

## 2. New Findings

### NBF-1 — §6.3 Correction INSERT trigger omits decision status validation (LOW)

**Location:** §6.3, lines 1042-1049.

**Problem:** The `fn_decision_correction_immutability()` trigger INSERT validation only checks that `corrected_entry_id` references a valid Confirmed snapshot belonging to the same Household. It does not validate that the decision's current status permits Correction. The service-level check (§8.10) is conditional on OD-S3-15, but without a trigger-level status check, a direct SQL INSERT into `decision_corrections` could insert a Correction on a Decision whose status does not permit it (e.g., a draft Decision, or an archived Decision under OD-S3-15 Option B).

**Impact:** Low. The design document is not yet implemented. The gap is traceable from OD-S3-15 and §6.12. Adding a conditional note to the trigger description would close the gap.

**Recommended fix:** Add to §6.3 Correction INSERT trigger: "Also validate that the referenced Decision's current status permits Correction append (conditional on OD-S3-15: `confirmed` only, or `confirmed`/`archived`)."

### NBF-2 — §6.3 lifecycle trigger omits conditional `draft → discarded` transition (LOW)

**Location:** §6.3, lines 1051-1061.

**Problem:** The `fn_decision_identity_lifecycle()` trigger lists three allowed transitions: `draft → confirmed`, `confirmed → archived`, `archived → confirmed`. If OD-S3-13 Option B is chosen, a `draft → discarded` transition would be needed. This dependency is not noted in the trigger description.

**Impact:** Low. OD-S3-13 itself documents that the choice affects "trigger rules" and "lifecycle trigger rules." The §6.12 section notes the trigger dependency. But the §6.3 trigger table doesn't include the conditional transition.

**Recommended fix:** Add to §6.3: "If OD-S3-13 Option B is approved, also allow `draft → discarded` (at discard time). Whether `discarded → draft` (reopen) is allowed depends on Owner decision."

---

## 3. Open Decisions Verification

| ID | Status | Notes |
|---|---|---|
| OD-S3-1 | Open | Draft cardinality |
| OD-S3-2 | Open | Minimum fields |
| OD-S3-3 | Open | Classification/tags |
| OD-S3-4 | Open | decision_date |
| OD-S3-5 | Open | Policy Version reference |
| OD-S3-6 | Open | Confirm transition model |
| OD-S3-7 | Open | Archive/unarchive semantics — correction eligibility moved to OD-S3-15 |
| OD-S3-8 | Open | Correction data model |
| OD-S3-9 | Open | Correction correctable fields |
| OD-S3-10 | Open | Expanded: Decision-filtered endpoint, Household timeline scope, pagination |
| OD-S3-11 | Open | UI copy |
| OD-S3-12 | Open | Implementation splitting |
| OD-S3-13 | Open | **NEW** — Draft discard identity semantics |
| OD-S3-14 | Open | **NEW** — Correction numbering and ordering |
| OD-S3-15 | Open | **NEW** — Correction eligibility for Archived Decisions |

All 15 ODs are **Open — Owner Decision Required**. None are marked Resolved, Approved, or Final.

**Dependency check:**
- OD-S3-15 Option B depends on OD-S3-7 (unarchive). Documented.
- OD-S3-13 Option A depends on OD-S3-6 (confirm model) for the "never Confirmed" condition. No circular dependency.
- OD-S3-14 affects Correction API locking, UI labels, and audit metadata. All documented.
- OD-S3-8 covers effective response shape. §8.7 correctly notes conditional dependency.
- No missing Owner Decisions identified. No two independent issues unreasonably bundled.

---

## 4. Database Consistency Review

**FK Delete Behavior (§6.9):** All cross-table FKs use `ON DELETE RESTRICT` for immutable relationships. AuditEvent `entity_id` has no FK by design. Draft FK conditional on OD-S3-13.

**Trigger Comparison Safety (§6.10):** `IS DISTINCT FROM` mandated for nullable metadata. Status `NOT NULL` with CHECK. Multi-row tests specified.

**Cross-Household Ownership (§6.11):** `decisions.household_id` FK → `household_profiles.id`. Ownership inheritance through `decision_id` FK chain. Service validation for Policy Version ownership.

**Committed Lifecycle Consistency (§6.12):** Deferred constraint trigger recommended. Covers all required invariant checks. Analogous to existing `fn_investment_policy_version_require_sealed()`.

---

## 5. Test Matrix Completeness

All required tests are present:

- Standalone discard (§11.2), no orphan (§11.2), discard rollback (§11.2)
- Confirm/Discard race with both options (§11.3)
- Correction numbering across Decisions (§11.2, §11.3)
- Concurrent Corrections per option (§11.3)
- Correction rollback/gaps (§11.2, §11.3)
- Archived Correction eligibility (§11.2)
- Archive/Correction race (§11.2, §11.3)
- Household timeline inclusion/exclusion (§11.2)
- Decision-filtered audit (§11.2)
- Original/effective response (§11.2, §11.4)
- FK RESTRICT (§11.2)
- Direct SQL lifecycle bypass (§11.2)
- IS DISTINCT FROM (§11.2)
- Cross-Household Policy Version (§11.2)
- Confirm/Policy publish race (§11.3)
- Unrelated IntegrityError (§11.3)
- Session reuse (§11.3, §11.4)
- Lifecycle consistency deferred checks (§11.3)

Tests are correctly conditional per Owner choice, not requiring simultaneous implementation of mutually exclusive options.

---

## 6. Contradiction Search Results

| Check | Result |
|---|---|
| Recommended vs Approved混用 | None found |
| Open Decision写成固定行为 | None found |
| Option A/B/C编号错位 | None found |
| Status值与trigger不一致 | NBF-2 |
| API endpoint数量不一致 | 12 endpoints consistent |
| UI要求不存在的endpoint | None found |
| Lock order逆序 | None found |
| Per-Decision编号错误使用identity | None found |
| Identity deletion与FK RESTRICT冲突 | Addressed in §6.9 |
| AuditEvent保留与identity deletion冲突 | Addressed in §6.9 |
| Full replacement effective提前固定 | Conditional on OD-S3-8 |
| Archive Correction提前允许 | Conditional on OD-S3-15 |
| Combined Household timeline提前批准 | OD-S3-10 covers |
| Discard引入未批准lifecycle状态 | NBF-2 |

---

## 7. Scope and MASTER_PLAN

**Diff scope:** Only `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md` and `docs/MASTER_PLAN.md`. No code, schema, migration, tests, dependencies, Compose, CI, or environment changes.

**MASTER_PLAN:** Accurately records REQUEST CHANGES, fix revision, new ODs, all 15 ODs Open, PR #10 Draft, Slice 3 Implementation Not Authorized, 3A/3B/3C Not Started. No APPROVE or Done written. Existing Backlog preserved.

---

## 8. Verification Commands

```
git branch --show-current → planning/sprint-002-slice-3-decision-journal
git rev-parse HEAD → 1cecef9ba5cb6f4db06cdf419c41ff5d930c29c6
git rev-parse origin/planning/... → 1cecef9ba5cb6f4db06cdf419c41ff5d930c29c6
git diff --name-only → (empty)
git diff --cached --name-only → (empty)
gh pr view 10 → OPEN, Draft, MERGEABLE
gh pr checks 10 → all 6 pass
git diff --check → clean
git diff main...HEAD --check → clean
git diff --name-only main...HEAD → 2 files (design + master plan)
grep "IDENTITY ALWAYS per Decision" → 0 matches
grep "OD-S3-1 through OD-S3-12" → 0 matches
grep "OD-S3-1 through OD-S3-15" → 2 matches
```

---

## 9. Unverified Items

None.

---

## 10. Final Conclusion

**APPROVE WITH NON-BLOCKING FOLLOW-UP**

All 8 original findings are **RESOLVED**:

| Finding | Severity | Status |
|---|---|---|
| M-1 | HIGH | RESOLVED |
| M-2 | HIGH | RESOLVED |
| M-3 | MEDIUM | RESOLVED |
| M-4 | MEDIUM | RESOLVED |
| M-5 | MEDIUM | RESOLVED |
| L-1 | LOW | RESOLVED |
| L-2 | LOW | RESOLVED |
| L-3 | LOW | RESOLVED |

Two new **LOW** non-blocking follow-ups (NBF-1, NBF-2) identified in §6.3 trigger descriptions. Neither blocks the design.

The design is sufficiently clear, internally consistent, and technically feasible to serve as the basis for Owner decisions on OD-S3-1 through OD-S3-15. No implementation is authorized. PR #10 remains Draft.

---

*End of Incremental Fix Re-Review Report.*
