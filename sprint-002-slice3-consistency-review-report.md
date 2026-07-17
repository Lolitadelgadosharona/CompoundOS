# Sprint 002 Slice 3 — Final Owner Decision Consistency Review Report

- **Date:** 2026-07-16
- **Branch:** `planning/sprint-002-slice-3-decision-journal`
- **Base:** `main` at `18697b4757be96f82aa1a7f62453a7751e148cc5`
- **HEAD:** `a264b552ec734ffe06c3d19353fc4b68d64239cc`
- **PR:** #10 — OPEN, Draft, MERGEABLE
- **Review type:** Independent read-only Final Owner Decision Consistency Review
- **Conclusion:** **APPROVE WITH ONE MEDIUM FINDING**

---

## 1. Pre-Flight Verification

```
git branch --show-current → planning/sprint-002-slice-3-decision-journal
git rev-parse HEAD → a264b552ec734ffe06c3d19353fc4b68d64239cc
git rev-parse origin/planning/... → a264b552ec734ffe06c3d19353fc4b68d64239cc
git rev-parse origin/main → 18697b4757be96f82aa1a7f62453a7751e148cc5
git diff --name-only → (empty)
git diff --cached --name-only → (empty)
gh pr view 10 → OPEN, Draft, MERGEABLE
gh pr checks 10 → all 6 pass (infrastructure/backend/frontend × push + pull_request)
git diff --check → clean
git diff --check main...HEAD → clean
```

OD increment diff (`1cecef9...a264b55`): 2 files changed, 416 insertions, 378 deletions. Only `docs/MASTER_PLAN.md` and `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`.

Full PR diff (`main...HEAD`): same 2 files. No code, schema, migration, tests, dependencies, Compose, CI, or environment changes.

Design document: 2078 lines, 18 sections.

---

## 2. Untracked File Inventory (33 files, SHA-256 verified)

All 33 untracked files preserved. SHA-256 hashes recorded at session start and verified unchanged. No existing untracked file was modified, deleted, or staged.

---

## 3. Context Documents Read

Design and planning documents read in full:

- `docs/MASTER_PLAN.md`
- `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md` (2078 lines)
- `docs/sprints/SPRINT_002_PROPOSAL.md`
- `docs/sprints/SPRINT_002_OPEN_QUESTIONS.md`
- `docs/sprints/SPRINT_002_SLICE_2_TECHNICAL_DESIGN.md`
- `docs/ARCHITECTURE.md`
- `docs/PRD.md`
- `docs/INVESTMENT_RULEBOOK.md`
- `docs/ADR/0002-postgresql-persistence-and-transactions.md`
- `docs/ADR/0003-immutable-investment-policy-snapshots.md`
- `docs/ADR/0004-investment-policy-backend-transactions.md`
- `sprint-002-slice3-design-review-report.md`
- `sprint-002-slice3-design-fix-review-report.md`
- `sprint-002-slice3-decisions-review.diff`
- `chatgpt-briefing-slice3-decisions.md`

Existing code implementations read:

- `apps/api/models.py` (AuditEvent, InvestmentPolicyVersion, FK definitions)
- `apps/api/repositories/households.py` (list_audit_events: household_id only, no entity_type filter)
- `apps/api/repositories/policies.py` (get_policy with FOR UPDATE, get_current_published, list_policy_audit_events)
- `apps/api/services/policies.py` (publish_draft: 12-step transaction, lock order Policy → Draft)
- Migration `0002` (immutability triggers, sequence_number IDENTITY, FK ON DELETE behaviors)

---

## 4. Per-OD Consistency Results

### OD-S3-1 — Multiple independent Drafts: CONSISTENT

- Multiple independent Drafts allowed (§4.1, L357-362)
- Each Draft creates independent Decision identity (§4.1, L342, L358-359)
- At most one Draft per Decision: UNIQUE on decision_id (§6, L1066)
- No Household-level singleton (§4.1, L347, L357-358)
- API uses Decision ID, not `current/draft` (§4.1, L349-351, L360)
- UI provides Draft list and detail (§4.1, L353-355, §9)
- Concurrent Draft creation: no conflict, both succeed (§7, L1279-1283, §11.2 L1862)
- Constraints, indexes, test matrix consistent

### OD-S3-2 — Confirm required fields: CONSISTENT

- Required: title, decision_summary, rationale, decision_date (§4.3, L413-422, L444)
- Other fields optional (§4.3, L416-421, L454-456)
- Only mechanical validation: presence, type, date, length (§4.3, L451-452)
- No semantic quality, appropriateness, or risk judgment (§4.3, L451-452, L639)
- Consistent across schema, Pydantic, PostgreSQL CHECK, confirm transaction, API errors, UI, tests

### OD-S3-3 — No classification/tags: CONSISTENT

- No decision_type, category, label/tag table, AI classification, or fixed classification anywhere
- `decision_type` grep: 0 matches; `category` grep: 0 matches
- Future classification explicitly deferred (§4.2, L399: "requires separate approved Sprint")

### OD-S3-4 — Date semantics: CONSISTENT

- decision_date: DATE type (§4.4, L422, L488-490)
- Past and today allowed (§4.4, L494-496, L501)
- **Future FORBIDDEN** (§4.4, L500: "**forbidden**", L504: "decision_date <= CURRENT_DATE")
- All old "allow future" recommendations replaced (grep confirms only review_date references)
- review_date: optional DATE, allows future, does NOT trigger notification (§4.4, L421, L509-513)
- created_at/confirmed_at: system TIMESTAMPTZ (§4.4, L429-432, L476-478)
- API: strict ISO YYYY-MM-DD (§4.4, L490)
- Correction decision_date follows same rules (§4.8.4, L856-857)

### OD-S3-5 — Current Published Policy Version only: CONSISTENT

- Confirm references only current Published Version after lock (§4.5, L572-577)
- Draft/Superseded/historical rejected (§4.5, L549, L572-576, L616-617)
- Request ID must exactly equal locked current Published ID (§4.5, L580-581)
- Policy row FOR UPDATE first (§4.5, L578; §4.6 step 2, L612; §7.1, L1247)
- Re-read after lock (§4.5, L579; §4.6 step 3, L613)
- Race linearizable (§7.2, L1259-1266, L1339-1345)
- Subsequent supersession does NOT change Confirmed reference (§4.5, L583-584)
- API/UI/tests/error mapping consistent

### OD-S3-6 — Consume Draft on Confirm: CONSISTENT

- 13-step transaction consistent across §4.6, §8.6, OD table
- Lock order: Policy → Decision → Draft (consistent everywhere)
- No post-commit business query (§4.6, L667-668; §8.6, L1497)
- Any step failure: full rollback (§4.6, L654-655; §7.9, L1413-1415)
- No editable Draft after confirm (§4.6, L633-634)
- No Confirmed→Draft reopen (§4.6, L634-636; §6.3 trigger, L1037)
- Unrelated IntegrityError NOT mapped to 409 (§7.8, L1406-1409)

### OD-S3-7 — Archive/unarchive: CONSISTENT

- confirmed→archived and archived→confirmed (§4.7; §6.3 trigger; §8.8/8.9)
- reason optional, max 4000 Unicode chars (§4.7, L698-699; §8.8, L1544)
- archived_at system-generated, unarchive clears reason and time
- Snapshot/Correction unchanged; no Archived→Draft; no hard delete
- Both audited; lifecycle concurrency: SELECT FOR UPDATE
- IS DISTINCT FROM for nullable metadata (§6.10, L1176-1178; §11.2 test, L1833-1836)

### OD-S3-8 — Full replacement Correction: CONSISTENT

- Original snapshot never changes (§4.8.1; §8.7; §6.3 trigger)
- Each Correction: complete effective replacement of all correctable fields
- Latest correction = effective snapshot; no Correction: effective = original
- Detail API returns: original_snapshot, effective_snapshot, latest_correction_metadata, corrections_count
- No field-patch chain or explanatory-only remnants

### OD-S3-9 — Correctable fields: CONSISTENT

- Correctable set identical across all sections (11 fields listed at §4.8.4, OD table, §8.10)
- Never correctable: Decision/Household ID, selected_policy_version_id, created_at, confirmed_at, actor, Archive metadata, AuditEvent, prior Corrections
- Multiple Corrections allowed; no correction-of-correction
- Each Correction references original snapshot/stable Decision
- correction_reason required; date rules reuse OD-S3-4

### OD-S3-10 — Audit endpoints: INCONSISTENT (MEDIUM)

- Decision-filtered endpoint: before_sequence_number cursor, DB selects DESC returns ASC
- Decision events enter Household timeline (explicitly approved resource expansion)
- Repository description matches code (verified against `repositories/households.py:46-52`)
- Policy audit boundary unchanged; Household pagination: Backlog
- sequence_number: not commit order, gaps allowed
- Metadata: no free text, no correction_count
- Household timeline UI/test: future Slice scope

**Finding M-1:** §8.12 (L1591) specifies `limit (1-100, default 20)`. §5.6 (L967) and OD-S3-10 table (L1942) both specify `default 50`. The Owner Decision is default 50; the API detail table disagrees.

### OD-S3-11 — Provisional copy: CONSISTENT

- Three approved copy texts present (§9.3, L1707-1722)
- local-only, non-production, no authentication
- No legal-review claim, no consent persistence
- Shown before Confirm and Correction
- No recommendation, scoring, or approval implications

### OD-S3-12 — 3A/3B/3C split: CONSISTENT

- 3A persistence/immutability, 3B backend/API, 3C frontend
- Independent authorization, branch, Draft PR, CI, review
- TD merge does NOT authorize 3A (4 separate statements)
- No premature implementation content

### OD-S3-13 — Atomic discard deletion: CONSISTENT

- Only status=draft AND never-Confirmed can be Discarded
- Locks Decision and Draft; expected_revision check
- Same transaction: INSERT AuditEvent → DELETE Draft → DELETE identity
- No committed orphan possible; no discarded status; no draft→discarded transition
- Confirmed/Archived DELETE forbidden (fn_decision_identity_delete_guard)
- Snapshot/Correction/AuditEvent DELETE forbidden
- AuditEvent has NO Decision FK (entity_id is UUID, no FK)
- **Ordering verified**: AuditEvent written BEFORE identity deletion. entity_id is UUID with no FK, so INSERT succeeds while identity exists, and subsequent DELETE does not cascade to AuditEvent. Implementable and non-contradictory.
- FK ON DELETE CASCADE on Draft→Decision: safety net, service drives order
- DELETE guard blocks direct SQL and multi-row DELETE
- Rollback restores all; Confirm/Discard race: 404/409 as specified
- Unrelated missing ID always 404

### OD-S3-14 — Per-Decision correction numbering: CONSISTENT

- Does NOT use GENERATED ALWAYS AS IDENTITY (explicit at §6.5, L1075-1076)
- Uses SELECT FOR UPDATE + MAX+1 + UNIQUE (§6.5, L1079-1085; §8.10, L1571)
- Concurrent Corrections serialize through Decision row lock
- Rollback: number not committed, retry recomputes (no committed gap)
- Per-decision sequential 1, 2, 3
- correction_count excluded from audit metadata; corrections_count computed at read time
- API/UI/audit/test all consistent

### OD-S3-15 — Archived Decision Correction eligibility: CONSISTENT

- Selected: Archived may receive Corrections (§4.7, L713-714)
- Trigger: status IN ('confirmed', 'archived') (§6.3, L1022-1026)
- Service: status IN ('confirmed', 'archived') (§8.10, L1571; §7.2, L1353-1355)
- OD-S3-7 does NOT claim archived correctability (cleanly separated)
- §4.7 resolved, not conditional
- Archive/Correction race: both can proceed regardless of ordering
- UI: Correction available for archived Decisions
- No contradiction with OD-S3-8

---

## 5. Summary Table

| OD | Decision | Verdict |
|---|---|---|
| OD-S3-1 | Multiple independent Drafts | CONSISTENT |
| OD-S3-2 | Confirm required fields (mechanical only) | CONSISTENT |
| OD-S3-3 | No classification/tags | CONSISTENT |
| OD-S3-4 | DATE type, forbid future decision_date | CONSISTENT |
| OD-S3-5 | Current Published Policy Version only | CONSISTENT |
| OD-S3-6 | 13-step confirm, consume Draft | CONSISTENT |
| OD-S3-7 | Archive/unarchive | CONSISTENT |
| OD-S3-8 | Full replacement Correction | CONSISTENT |
| OD-S3-9 | Correctable fields | CONSISTENT |
| OD-S3-10 | Audit endpoints and Household timeline | **INCONSISTENT** |
| OD-S3-11 | Provisional UI copy | CONSISTENT |
| OD-S3-12 | 3A/3B/3C implementation split | CONSISTENT |
| OD-S3-13 | Atomic discard deletion | CONSISTENT |
| OD-S3-14 | Per-Decision correction numbering | CONSISTENT |
| OD-S3-15 | Archived Decision correction eligibility | CONSISTENT |

**14 of 15 ODs: CONSISTENT. 1 OD: INCONSISTENT (one pagination default mismatch).**

---

## 6. Findings

### M-1 — §8.12 pagination default contradicts §5.6 and OD table (MEDIUM)

**Location:** §8.12 line 1591 vs §5.6 line 967 vs OD-S3-10 table line 1942.

**Problem:** §8.12 (Decision-Filtered Audit Events API table) specifies `limit (1-100, default 20)`. §5.6 (line 967) and the OD-S3-10 summary table (line 1942) both specify `default 50, max 100`. The Owner Decision is default 50. The API detail table was not updated to match.

**Impact:** An implementer following the API table would use default 20 instead of the Owner-approved default 50. This is a mechanical inconsistency, not a design flaw.

**Recommended fix:** Change §8.12 line 1591 from `limit (1-100, default 20)` to `limit (1-100, default 50)`.

---

## 7. Non-Blocking Follow-Up Items

### NBF-1 — §5.1 AuditEvent action names remain "pending technical review" (LOW)

**Location:** §5.1 lines 886-887.

**Observation:** The seven AuditEvent action names are marked "Status: pending technical review. The owner must approve the final action names." This is not an Owner Decision but a separate technical review item. It was not part of the OD-S3-1 through OD-S3-15 resolution scope.

**Impact:** Low. The action names follow the existing Policy pattern (`policy.created`, `policy.draft.created`, `policy.published`, etc.).

### NBF-2 — §11.2 test matrix lacks explicit decision_date boundary test (LOW)

**Location:** §11.2 test matrix section.

**Observation:** The validation rule `decision_date <= CURRENT_DATE` is clearly specified at §4.4 (L504). However, the test matrix does not include an explicit test item for decision_date boundary values: yesterday (allowed), today (allowed), tomorrow (forbidden), invalid date string (rejected).

**Impact:** Low. The rule is unambiguous; the gap is in test matrix documentation.

---

## 8. Contradiction Search Results

| Check | Result |
|---|---|
| "conditional on OD-S3-X" | 0 matches |
| "pending OD-S3-X" | 0 matches |
| "Open.*Decision.*Required" | 0 matches |
| "Owner Approval Required" | 0 matches |
| "Recommended.*Owner" | 0 matches |
| "IDENTITY ALWAYS per Decision" | 0 matches |
| IDENTITY ALWAYS (any context) | 2 matches — both AuditEvent sequence_number (L517, L900), correct |
| "allow future" (decision_date) | 0 matches in active design; only review_date references |
| "discarded" status | 0 as lifecycle status; all are audit event names or explanatory text |
| correction_count in metadata | Excluded at L915 and L1812, consistent |
| decision_type field | 0 matches |
| category field | 0 matches |
| Lock order reversal | 0 — all use Policy → Decision → Draft |
| Confirmed→Draft reopen | 0 — explicitly forbidden |
| Archived→Draft | 0 — explicitly forbidden |
| Post-commit read | 0 — explicitly excluded |

---

## 9. Cross-Reference with Existing Code

| Design claim | Code verification |
|---|---|
| Household audit query filters by household_id only | `repositories/households.py:46-52` — confirmed, no entity_type filter |
| Policy lock order: Policy first, then Draft | `services/policies.py` — `_require_policy(for_update=True)` before `get_draft(for_update=True)` |
| Current Published Version: partial unique index | `models.py:176-181` — `uq_investment_policy_versions_current_published` WHERE `status = 'published'` |
| AuditEvent sequence_number: IDENTITY ALWAYS | `models.py:96-99` — `BigInteger, Identity(always=True)`, never set in code |
| FK ON DELETE RESTRICT (immutable) | All version/household FKs use RESTRICT; only draft_allocations use CASCADE |
| Existing lock pattern: plain FOR UPDATE | `repositories/policies.py:27,43` — `with_for_update()` without arguments |
| Publish transaction: one session.begin() | `services/policies.py:361` — `with session.begin()` |

All design claims accurately describe the existing code.

---

## 10. Implementation Status Verification

- Slice 3 Implementation: **Not Authorized** (§13.4, L1988-1993; §18, L2073; document header, L5)
- Slice 3A, 3B, 3C: **Not Started** (§13.4, L1993)
- PR #10: **Draft**, not merged
- No code, schema, migration, test, or dependency changes in the diff
- TD merge explicitly does NOT authorize 3A (4 separate statements)

---

## 11. MASTER_PLAN Consistency

`docs/MASTER_PLAN.md` accurately records:

- OD-S3-1 through OD-S3-15: "Resolved by Project Owner — 2026-07-16"
- Incremental re-review: APPROVE WITH NON-BLOCKING FOLLOW-UP
- NBF-1 and NBF-2 from incremental re-review: resolved
- All 15 OD decisions recorded
- Global consistency revision recorded
- PR #10: Draft, not merged
- Slice 3 Implementation: Not Authorized
- Slice 3A/3B/3C: Not Started

No premature APPROVE or Done written. Existing Backlog preserved.

---

## 12. Final Conclusion

**APPROVE WITH ONE MEDIUM FINDING**

14 of 15 Owner Decisions are **fully consistent** across the data model, lifecycle, transaction design, concurrency model, API contracts, UI design, test matrix, and Owner Decision summary table. No residual conditional, pending, or Open language remains from the OD resolution process. No contradictions exist between resolved decisions.

One MEDIUM finding (M-1: §8.12 pagination default 20 vs §5.6/OD table default 50) requires a one-line correction before the design can serve as a fully consistent implementation reference.

Two non-blocking follow-up items (NBF-1: action names pending marker; NBF-2: missing explicit date boundary test) are documentation hygiene items that do not affect design correctness.

The design document is otherwise ready to serve as the basis for Slice 3A implementation authorization once M-1 is corrected and the Owner approves.

---

*End of Final Owner Decision Consistency Review Report.*
