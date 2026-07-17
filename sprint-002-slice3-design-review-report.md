# Sprint 002 Slice 3 Technical Design Review Report

- Date: 2026-07-15
- Review type: Independent read-only Technical Design Review
- Branch: `planning/sprint-002-slice-3-decision-journal`
- Base: `main` at `18697b4757be96f82aa1a7f62453a7751e148cc5`
- Head: `043c07d9791b2031fa4ca94271a2521c5139756b`
- PR: #10 — OPEN, Draft
- Conclusion: **REQUEST CHANGES**

---

## Verification of Pre-Flight State

```
git rev-parse HEAD
→ 043c07d9791b2031fa4ca94271a2521c5139756b

git rev-parse origin/planning/sprint-002-slice-3-decision-journal
→ 043c07d9791b2031fa4ca94271a2521c5139756b
```

Local and remote HEAD are identical. HEAD prefix matches expected `043c07d`.

```
gh pr view 10 --json number,state,isDraft,mergeable,baseRefName,headRefName,headRefOid,url
→ {"number":10,"state":"OPEN","isDraft":true,"mergeable":"MERGEABLE",
   "baseRefName":"main","headRefName":"planning/sprint-002-slice-3-decision-journal",
   "headRefOid":"043c07d9791b2031fa4ca94271a2521c5139756b"}
```

Tracked/staged diff: empty. Working tree clean except for 23 untracked review files (preserved) and 3 new review files (untracked).

CI: both push (run 29468125638) and pull_request (run 29468145349) workflows completed with `success`. All 6 checks (infrastructure, backend, frontend × 2 events) passed.

---

## Scope Summary

The diff contains exactly 2 tracked files:

- `docs/MASTER_PLAN.md`: +38/-3 lines (Current Sprint, Planning, In Progress, Review, Decision Log updated)
- `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`: +1703 lines (new, 18 sections)

No code, tests, migrations, schemas, dependencies, Compose, CI, or environment configuration changes.

`git diff --check`: passed, no whitespace errors.

---

## Approved-Boundary Parity

### Compliant

The design correctly preserves all approved Sprint 002 product boundaries:

- Lifecycle: Draft → Confirmed → Archived (§2.1)
- Confirmed must reference Published Policy Version (§2.2)
- Confirmed must not be silently modified or physically deleted (§2.2)
- Correction is independent, append-only, immutable; not a lifecycle state (§2.3)
- Actor: fixed `local-owner` (§2.4)
- Single Household, local-only, non-production (§2.5)
- No holdings/accounts/amounts/prices/trades (§2.6)
- No recommendation/suitability/eligibility/score (§2.6)
- No AI/Guardian/Broker/trading (§2.6)
- No export, no general hard delete (§2.6)
- No structured financial fields in the Decision schema (§4.3)

### Boundary concerns (findings below)

- `unarchive` is marked "Recommended — Owner Approval Required" (§4.7) — compliant.
- Archived+Correction is stated as approved behavior in §4.7 but the review criteria require it remain open — see M-4.
- Combined Household timeline change is recommended without acknowledging it modifies an existing resource boundary — see M-5.

---

## Findings

### M-1: Draft Discard leaves decision identity in undefined state (HIGH)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Sections:** §4.6, §6.3, §8.5, §10

The design defines the Discard Draft transaction as:

> SELECT FOR UPDATE decision + draft → validate revision → DELETE draft → UPDATE decision status → INSERT AuditEvent (§8.5 line 1248)

And the retention boundary as:

> Drafts may be explicitly discarded (which deletes the Draft row and updates the decision identity status) (§10 lines 1455-1456)

But the design **never specifies what the target status is** after discard. The identity lifecycle trigger (§6.3 lines 979-987) permits exactly three transitions:

- `draft` → `confirmed` (at confirm time)
- `confirmed` → `archived` (at archive time)
- `archived` → `confirmed` (at unarchive time, if approved)

There is **no valid status transition for discard**. The trigger explicitly forbids `confirmed → draft` and `archived → draft`. This creates an impossible state:

1. **If the identity is kept with status='draft'**: the decision has no Draft row but claims to be in draft status. This is an orphan identity that would appear in `GET /api/decisions?status=draft` with no editable content. The API's Draft Detail endpoint (§8.3) would return 404 for a decision that claims to be in draft status.

2. **If the identity is physically deleted**: this contradicts the statement "No physical deletion at any stage" (§10), though that statement specifically lists confirmed/archived/corrections/audit-events as non-deletable and does not explicitly include draft decisions.

3. **If a new 'discarded' or 'abandoned' status is introduced**: this expands the approved lifecycle beyond Draft → Confirmed → Archived without owner approval.

**Impact:** The discard endpoint (§8.5) is fully specified as an API contract (path, method, request, response, errors, transaction, audit) but the underlying database state after discard is undefined. An implementer cannot determine what happens to the decision identity row. The test matrix (§11.2, §11.3) includes "Confirm/Discard race" but does not include a standalone discard-semantics test.

**Recommendation:** Add a new section or extend §4.6/§8.5 to explicitly define the post-discard decision identity behavior. The options are:
- (a) Physically delete the decision identity row (and explicitly exempt draft decisions from the "no physical deletion" rule, noting that only confirmed/archived/corrections/audit-events are protected).
- (b) Add a `discarded` status to the lifecycle and the identity trigger.
- (c) Keep the identity as status='draft' but define how the API handles an orphan identity.

Each option has different schema, trigger, API, and UI implications that the owner must evaluate. Record as a new owner decision.

---

### M-2: correction_number per-decision sequencing mechanism is technically incorrect (HIGH)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Section:** §6.5 (lines 1006-1018)

The design recommends:

> add `correction_number` (IDENTITY ALWAYS, UNIQUE per decision_id) to the corrections table (§6.5 lines 1017-1018)

And describes the purpose:

> a database-generated integer `correction_number` (IDENTITY ALWAYS) per Decision, to provide a stable human-readable ordering (correction 1, 2, 3...) (§6.5 lines 1012-1014)

**PostgreSQL `GENERATED ALWAYS AS IDENTITY` is a table-level sequence, not per-decision.** The IDENTITY column is backed by a single sequence object shared across all rows in the `decision_corrections` table. This produces globally unique, monotonically increasing integers — but they are NOT numbered 1, 2, 3 per decision.

Example: Decision A gets corrections numbered 1, 2, 5. Decision B gets corrections numbered 3, 4, 6. The numbers are globally sequential and unique, but neither decision sees "1, 2, 3."

The design also describes this as "analogous to `sequence_number` on AuditEvents but scoped per Decision" (line 1014-1015). The AuditEvent `sequence_number` is explicitly described as a **global** insertion sequence (§4.4 line 496-498). The design incorrectly claims the correction_number would be scoped per-decision when the mechanism it specifies is table-level.

**Additional concerns:**

- The UNIQUE constraint on `(decision_id, correction_number)` prevents duplicate numbers within a decision, but does not enforce per-decision sequential numbering.
- Under concurrent Corrections (§7.2 line 1134-1136), the design states "two simultaneous Correction appends both INSERT… The `correction_number` IDENTITY generates distinct values. Both succeed." This is correct for global IDENTITY, but the resulting numbers are not per-decision sequential.
- Rollback gaps in the IDENTITY sequence would produce non-contiguous numbering, which is acceptable for global sequences but confusing for per-decision display.

**Impact:** If the owner chooses per-decision sequential numbering, the design must specify a different mechanism:
- Application-level: lock decision row, compute `MAX(correction_number) + 1` for this decision_id, insert with explicit value.
- Trigger-based: per-decision sequence objects or a counter table.
- Accept global numbering: use IDENTITY ALWAYS but describe the numbering as "globally unique, monotonically increasing" rather than "correction 1, 2, 3 per decision."

**Recommendation:** Correct the technical description to match the actual PostgreSQL behavior. If per-decision sequential numbering is desired, specify the correct mechanism. If global numbering is acceptable, update the description. This should be reflected in OD-S3-9 or a new owner decision.

---

### M-3: Confirm transaction omits Policy lock, inconsistent with recommended lock order (MEDIUM)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Sections:** §4.6 (lines 580-595), §7.1 (lines 1062-1074), §8.6 (line 1260)

Three sections describe the confirm transaction's lock behavior with conflicting detail:

**§4.6 (12-step confirm transaction):** Steps 1-2 lock decision identity and Draft. Step 6 "Fetch the current Published Policy Version for this Household" does not specify `SELECT FOR UPDATE`. The Policy lock is absent from all 12 steps.

**§7.1 (Lock ordering):** Explicitly specifies:
> `Household → Policy → Policy Version → Decision → Draft → Snapshot/Correction`
> 1. `investment_policies` (FOR UPDATE) — when confirm needs to validate the Policy Version.

And the deadlock analysis:
> Decision confirm: locks Policy → locks Decision → locks Decision Draft.

**§8.6 (API table):** The transaction column states:
> Lock Policy → lock decision → lock draft → validate → INSERT snapshot → DELETE draft → UPDATE decision status → INSERT AuditEvents

§7.1 and §8.6 are consistent (Policy lock first). §4.6 omits it entirely.

**Impact:** Without the Policy lock in step 6, a concurrent Policy publish could supersede the Published Version after the confirm reads it but before the confirm commits. The confirm would then reference a superseded Version in the snapshot. With the Policy lock, the confirm waits for the publish to commit and then re-checks the Version status.

The design's concurrency section (§7.2 line 1116-1123) correctly describes the Policy supersession race and the expected 409 response, implying the Policy lock IS held. But the step-by-step in §4.6 does not include it.

**Recommendation:** Add a Policy lock step to §4.6 before step 6. For example, insert a new step between 5 and 6:
> 5.5. Acquire `SELECT FOR UPDATE` on the `investment_policies` row for this Household.

Then renumber subsequent steps. This makes §4.6 consistent with §7.1 and §8.6.

---

### M-4: Archived+Correction stated as approved behavior despite being an open decision (MEDIUM)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Sections:** §4.7 (lines 672-678), §8.10 (line 1307), OD table (OD-S3-7 line 1570)

§4.7 states definitively:

> **Archived + Correction.** Archived Decisions may still receive appended Corrections. Archive does not seal the Decision against corrections — it only hides it from the default list. The Correction table's INSERT trigger validates that the referenced Decision has `status = 'confirmed'` or `status = 'archived'` (both are post-confirmation states).

§8.10 (Append Correction API) states the transaction validates:
> status = confirmed or archived

These are written as approved, implemented behavior. However:

- OD-S3-7's "Recommended" column includes "archived Decisions still correctable" as one of several bundled sub-decisions.
- The review criteria specifically require that "Archived后是否允许Correction也必须保持open decision状态."
- Whether archived decisions can receive corrections is a substantive product decision: it determines whether archive is purely a list-hiding mechanism or also limits the correction surface.

**Impact:** The Correction INSERT trigger design (§6.3 lines 970-975) and the Correction append API (§8.10) both assume archived decisions are correctable. If the owner decides archived decisions should NOT receive corrections, the trigger, API, test matrix, and UI would all need revision.

**Recommendation:** Either:
- (a) Split OD-S3-7 into separate owner decisions: one for archive/unarchive mechanics, and one specifically for whether archived decisions may receive corrections.
- (b) Change the §4.7 and §8.10 text to mark this as "Recommended — Owner Approval Required" with an explicit note that the trigger and API assume this behavior.

---

### M-5: Combined Household timeline change not acknowledged as resource boundary modification (MEDIUM)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Section:** §5.5 (lines 880-901)

The design recommends:

> **Recommended — Owner Approval Required: both.** Provide the Decision-filtered endpoint for the Decision detail view, and Decision events naturally appear in the combined Household timeline. This matches the existing Policy pattern.

The claim that Decision events "naturally appear" in the existing Household audit endpoint (`GET /api/households/current/audit-events`) implies that the existing endpoint's implementation would include Decision events without modification. However:

- The existing Household audit repository query filters by `household_id` only. Decision events with `entity_type = "Decision"` would indeed appear in the results. This IS consistent with the existing Policy pattern, where Policy events also appear in the Household timeline.
- But the design does not explicitly state whether the existing endpoint needs any code change to include Decision events. If the current implementation filters by `entity_type IN ('HouseholdProfile', 'InvestmentPolicy')`, Decision events would be excluded. If it has no entity_type filter, they would be included automatically.
- Adding Decision events to the Household timeline increases the response size, which the design acknowledges as a scalability concern and defers as a "non-blocking Backlog item" (§5.6 lines 910-914).

**Impact:** The owner needs to know whether the combined timeline recommendation requires modifying the existing Household audit endpoint (even if only to ensure no entity_type filter excludes Decision events) or if it works automatically. This affects the scope of Slice 3B.

**Recommendation:** Add an explicit note in §5.5 stating whether the existing Household audit endpoint requires implementation changes to include Decision events, and record this as part of OD-S3-10 or a new owner decision.

---

### L-1: API detail endpoint ambiguous between original and effective view (LOW)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Section:** §8.7 (line 1270)

The Confirmed Decision Detail endpoint (§8.7) response is:

> decision identity, confirmed snapshot (all fields, `confirmed_at`, `selected_policy_version_id`), archive metadata, latest correction summary

The phrase "latest correction summary" is ambiguous. It could mean:
- (a) A brief summary of the latest correction (correction_number, created_at, correction_reason) without the corrected field values.
- (b) The full corrected field values from the latest correction (the effective view).

The UI design (§9.2) clearly distinguishes "Original view" (the confirmed snapshot) from "Effective corrected view" (the latest Correction's full snapshot). But the API response shape does not make this distinction explicit.

**Impact:** An implementer cannot determine from the API specification alone whether the detail endpoint returns the original snapshot, the effective corrected view, or both.

**Recommendation:** Specify the response shape explicitly: either "returns original snapshot + latest correction summary (metadata only)" or "returns both original snapshot and effective corrected snapshot."

---

### L-2: Concurrent Confirm vs Discard loser response ambiguity (LOW)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Section:** §7.2 (lines 1109-1113)

The design states:

> **Confirm vs Discard race.** Both acquire `SELECT FOR UPDATE` on the decision identity. The first to acquire the lock proceeds; the second finds the state has changed. If discard wins, confirm returns 404 (Draft not found). If confirm wins, discard returns 409 (Decision no longer in draft status).

The "confirm returns 404" case is ambiguous. It depends on whether discard deletes only the Draft row (leaving the decision identity) or also deletes the decision identity. This is directly related to M-1.

If the identity is preserved after discard, a concurrent confirm would find the decision identity exists with a non-draft status. The appropriate response would be 409 (lifecycle conflict), not 404.

If the identity is physically deleted, 404 is correct.

**Impact:** The loser response code depends on the unresolved discard semantics (M-1).

**Recommendation:** Resolve M-1 first, then update this section to specify the correct loser response based on the chosen discard behavior.

---

### L-3: correction_count audit metadata accuracy under concurrency (LOW)

**File:** `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`
**Sections:** §5.3 (line 867), §8.10 (line 1308)

The audit metadata allowlist includes `correction_count` (§5.3) and the Correction append API inserts this into the AuditEvent metadata (§8.10). Under concurrent Correction appends (§7.2), two Corrections could be inserted in overlapping transactions. Each transaction captures the count at the time of its query, potentially producing:
- Transaction A reads count = N, inserts Correction, inserts AuditEvent with `correction_count: N+1`.
- Transaction B reads count = N (before A commits), inserts Correction, inserts AuditEvent with `correction_count: N+1`.

Both AuditEvents would report the same count.

**Impact:** The `correction_count` metadata may not accurately reflect the total number of corrections after both transactions commit. The actual count would be N+2, but both AuditEvents report N+1.

**Recommendation:** This is a minor metadata accuracy issue, not a correctness issue. The design could note that `correction_count` is a snapshot at audit-insertion time and may not reflect the post-commit total under concurrent appends. Alternatively, compute the count from the Correction list at read time rather than storing it in audit metadata.

---

## Data-Model Consistency Matrix

| Property | Approach C design claim | Review assessment |
|---|---|---|
| At most one Draft per Decision | UNIQUE on decision_id in drafts | Correct — implementable |
| At most one snapshot per Decision | UNIQUE on decision_id in snapshots | Correct — implementable |
| Multiple independent Drafts | Multiple decision identities | Correct — no singleton constraint |
| Draft discard → identity status | "UPDATE decision status" | **UNDEFINED** — see M-1 |
| status=draft with no Draft row | Not addressed | **Possible orphan state** |
| status=confirmed with no snapshot | Not addressed | Trigger prevents if snapshot UNIQUE enforced |
| status=archived with no snapshot | Not addressed | Same as confirmed |
| Draft + snapshot simultaneously | Not addressed | UNIQUE constraints prevent if both exist |
| Confirmed → new Draft | Not addressed | Trigger forbids archived→draft but what about confirmed→draft? |
| Household ownership | Service-level only | **No database constraint** linking decisions to household_profiles |
| selected_policy_version_id ownership | FK + service check | FK ensures Version exists; service ensures same Household |

---

## Lifecycle / Orphan-State Matrix

| Transition | Trigger allows | Design specifies | Assessment |
|---|---|---|---|
| draft → confirmed | Yes (§6.3) | Yes (§4.6) | Consistent |
| confirmed → archived | Yes (§6.3) | Yes (§4.7) | Consistent |
| archived → confirmed | Yes (§6.3, if approved) | Yes (§4.7) | Consistent |
| confirmed → draft | Forbidden (§6.3) | Not addressed | Consistent but should note |
| archived → draft | Forbidden (§6.3) | Not addressed | Consistent but should note |
| draft → discarded | **NOT in trigger** | **UNDEFINED** (§8.5, §10) | **M-1: Gap** |
| Any → deleted (identity) | Not addressed | "No physical deletion" (§10) | Ambiguous for draft |

---

## Correction Model / Numbering Review

| Aspect | Design claim | PostgreSQL reality | Assessment |
|---|---|---|---|
| correction_number generation | IDENTITY ALWAYS per decision | Table-level sequence | **M-2: Incorrect** |
| Per-decision 1,2,3 ordering | Claimed | Not achievable with IDENTITY | **M-2: Incorrect** |
| UNIQUE per decision_id | Recommended | Implementable | Correct |
| Concurrent correction numbers | Both succeed, distinct | True for global, not per-decision | Partially correct |
| Rollback gaps | Not addressed | IDENTITY has gaps | Non-blocking |
| correction_number for ordering | "correction_number ASC" (§8.11) | Works for global ordering | Correct |
| Effective view = latest | ORDER BY created_at (§4.8.1) | Implementable | Correct |
| "Latest" under concurrency | Not deterministic | created_at = now() may tie | Non-blocking |

---

## Confirm Transaction / Lock-Order Review

| Section | Step 1 | Step 2 | Step 6 (Policy) | Consistent? |
|---|---|---|---|---|
| §4.6 (12 steps) | Lock decision | Lock draft | Fetch Version (no FOR UPDATE) | **M-3: Inconsistent** |
| §7.1 (Lock order) | Lock Policy | Lock decision | N/A (already locked) | Consistent |
| §8.6 (API table) | Lock Policy | Lock decision | Implied | Consistent |

The 12-step confirm in §4.6 is the only section that omits the Policy lock. §7.1 and §8.6 both include it. The concurrency analysis in §7.2 assumes the Policy lock is held ("The confirm transaction locks the Policy row FOR UPDATE").

---

## Archive / Correction Concurrency Review

The design states Archive and Correction "touch different tables and do not conflict" (§7.2 lines 1127-1130). This is technically correct: Archive UPDATEs the `decisions` identity row, Correction INSERTs into `decision_corrections`. However:

- The Correction INSERT trigger reads the decision's `status` column. Under READ COMMITTED, the trigger sees the latest committed state. If Archive commits first, the trigger sees `status='archived'` (valid). If Correction commits first, Archive sees no change to the decision row.
- No deadlock is possible because the two operations don't acquire locks on each other's tables.
- The correction trigger (§6.3 line 972-973) validates `status = 'confirmed'` or `'archived'`. If the decision is mid-archive (status transitioning from confirmed to archived), the Correction trigger sees the pre-commit status under READ COMMITTED. This is fine because both statuses are valid for correction.

**Assessment:** The design's claim that Archive and Correction can proceed independently is correct under READ COMMITTED, provided the Correction trigger accepts both `confirmed` and `archived` statuses. However, whether archived decisions should accept corrections is an open decision (M-4).

---

## PostgreSQL Enforceability Review

| Design element | PostgreSQL mechanism | Implementable? | Assessment |
|---|---|---|---|
| Snapshot immutability (no UPDATE/DELETE) | BEFORE trigger, return NULL + RAISE | Yes | Correct |
| Correction immutability (no UPDATE/DELETE) | BEFORE trigger, return NULL + RAISE | Yes | Correct |
| Decision lifecycle transitions | BEFORE UPDATE trigger, check OLD/NEW status | Yes | Correct |
| At most one Draft per Decision | UNIQUE constraint | Yes | Correct |
| At most one snapshot per Decision | UNIQUE constraint | Yes | Correct |
| Correction ownership validation | INSERT trigger, check FK + household | Yes | Correct |
| correction_number per-decision | IDENTITY ALWAYS | **No** — table-level | **M-2** |
| Discard identity status change | BEFORE UPDATE trigger | **No** — no valid target | **M-1** |
| Household ownership of decisions | No constraint specified | Service-only | Non-blocking but noted |
| IS DISTINCT FROM in triggers | Not specified | Should be added | Non-blocking |

The design does not mention `IS DISTINCT FROM` for trigger comparisons. PostgreSQL NULL comparison semantics (`NULL != NULL`) could allow trigger bypass if a status column is NULL. Since status is `NOT NULL` in practice, this is a non-blocking robustness improvement.

The design does not specify ON DELETE behavior for FK relationships between corrections → snapshots, drafts → decisions, or snapshots → decisions. The design should specify `ON DELETE RESTRICT` (or equivalent) for all cross-table FK references to prevent cascade deletion from bypassing immutability triggers.

---

## API / UI / Design Parity

| Aspect | API | UI | Data model | Consistent? |
|---|---|---|---|---|
| Multiple Drafts | §8.1-8.5 (per-decision paths) | §9.2 (list view) | §4.1 (Option B) | Yes |
| Draft Detail | §8.3 (per-decision) | §9.2 (editor) | decision_drafts | Yes |
| Confirm | §8.6 | §9.2 (confirm review) | §4.6 | Yes (after M-3 fix) |
| Discard | §8.5 | §9.2 (discard confirm) | §8.5 | **M-1: Undefined** |
| Archive | §8.8 | §9.2 (archive dialog) | §4.7 | Yes |
| Unarchive | §8.9 | §9.2 (implicit) | §4.7 | Yes |
| Correction append | §8.10 | §9.2 (append form) | §4.8 | **M-4: Open** |
| Detail view | §8.7 | §9.2 (original + effective) | §4.8 | **L-1: Ambiguous** |
| Correction list | §8.11 | §9.2 (history) | §4.8 | Yes |
| Audit timeline | §8.12 | §9.2 (timeline) | §5 | Yes |
| Stale-response guards | N/A | §9.2 (AbortController) | N/A | Yes |
| No autosave | N/A | §9.3 (explicit save) | N/A | Yes |
| No AI/Guardian/trading UI | §8.13 (forbidden) | §9.3 (no elements) | §2.6 | Yes |

---

## Audit Resource-Boundary Review

| Aspect | Assessment |
|---|---|
| New Decision-filtered endpoint | Correct — matches Policy pattern |
| Combined Household timeline | **M-5: Resource boundary change not acknowledged** |
| entity_id stability | Correct — same decision UUID across all events |
| Draft discard entity_id | The discard AuditEvent references the decision identity. If M-1 results in identity deletion, the entity_id becomes a dangling reference. The AuditEvent remains valid (FK RESTRICT would block deletion, but the design doesn't specify FK behavior). |
| Metadata redaction | Correct — only changed_fields, draft_revision, policy_version_number, correction_count |
| correction_count concurrency | **L-3: May be inaccurate under concurrent appends** |
| sequence_number ordering | Correct — IDENTITY ALWAYS, not commit order |
| Pagination | Correct — before_sequence_number + limit, consistent with Policy version history |

---

## Blocking Test-Matrix Gaps

| Design guarantee | Test specified? | Gap |
|---|---|---|
| Discard semantics | §11.3: "Confirm/Discard race" | **Missing**: standalone discard test (what happens to identity?) |
| Orphan identity | Not specified | **Missing**: test that discarded Draft leaves no orphan |
| Per-decision correction numbering | §11.3: "distinct correction_number" | **Missing**: test that numbering is per-decision (but design is wrong about mechanism) |
| Household ownership of decisions | Not specified | **Missing**: test that decisions belong to the sole Household |
| ON DELETE RESTRICT for cross-table FKs | Not specified | **Missing**: test that deleting a decision identity doesn't cascade |
| Trigger IS DISTINCT FROM | Not specified | Non-blocking |
| Unarchive transition | §11.2: "only archived can be unarchived" | Covered |
| Policy Version ownership at confirm | §11.2: "validates Published Version belongs to Household's Policy" | Covered |
| Concurrent Correction numbering | §11.3: "distinct correction_number values" | Covered but numbering mechanism is wrong (M-2) |

---

## OD-S3-1 through OD-S3-12 Quality Review

| OD | Status | Recommendation fair? | Alternatives fair? | Missing? |
|---|---|---|---|---|
| OD-S3-1 | Open | Yes | Yes | No |
| OD-S3-2 | Open | Yes | Yes | No |
| OD-S3-3 | Open | Yes | Yes | No |
| OD-S3-4 | Open | Yes | Yes | No |
| OD-S3-5 | Open | Yes | Yes | No |
| OD-S3-6 | Open | Yes | Yes | No |
| OD-S3-7 | Open | Partial — bundles archive + unarchive + correction | Yes | **Should split archived+correction into separate OD (M-4)** |
| OD-S3-8 | Open | Yes | Yes | No |
| OD-S3-9 | Open | Partial — correction_number mechanism is wrong (M-2) | Yes | **Should note mechanism correctness** |
| OD-S3-10 | Open | Yes | Yes | **Missing: Household timeline resource boundary change (M-5)** |
| OD-S3-11 | Open | Yes | Yes | No |
| OD-S3-12 | Open | Yes | Yes | No |

### Suggested new or split owner decisions

1. **Draft discard identity semantics** (new): After discarding a Draft, what happens to the decision identity row? Options: physical deletion, new discarded status, orphan identity. This is the most critical missing decision.

2. **Per-decision correction numbering mechanism** (split from OD-S3-9): Whether to use application-level max+1, per-decision sequences, or accept global numbering. The current recommendation (IDENTITY ALWAYS) cannot deliver per-decision numbering.

3. **Archived Decision correction eligibility** (split from OD-S3-7): Whether archived Decisions may receive Corrections. Currently bundled with archive/unarchive mechanics.

4. **Combined Household audit timeline scope** (add to OD-S3-10 or new): Whether adding Decision events to the existing Household audit endpoint requires implementation changes and whether the owner approves this resource boundary expansion.

5. **Concurrent Discard/Confirm loser response** (new or add to OD-S3-6): Whether the loser gets 404 (identity deleted) or 409 (identity preserved, status changed). Depends on discard identity semantics.

---

## Scope Exclusion Confirmation

The diff contains only `docs/MASTER_PLAN.md` and `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md`. No schema, migration, code, test, dependency, Compose, CI, environment, or implementation changes are present. No AI, Guardian, Broker, trading, recommendation, or investment rule changes are included. Slice 3 implementation is not present or implied by code changes.

**Confirmed: scope is design-only.**

---

## Exact Commands and Results

```bash
git rev-parse HEAD
# 043c07d9791b2031fa4ca94271a2521c5139756b

git rev-parse origin/planning/sprint-002-slice-3-decision-journal
# 043c07d9791b2031fa4ca94271a2521c5139756b

gh pr view 10 --json number,state,isDraft,mergeable,baseRefName,headRefName,headRefOid,url
# {"number":10,"state":"OPEN","isDraft":true,"mergeable":"MERGEABLE",
#  "baseRefName":"main","headRefName":"planning/sprint-002-slice-3-decision-journal",
#  "headRefOid":"043c07d9791b2031fa4ca94271a2521c5139756b"}

git diff --stat HEAD
# (empty — no tracked changes)

git diff --cached --stat
# (empty — nothing staged)

git diff --binary origin/main...origin/planning/sprint-002-slice-3-decision-journal --stat
# docs/MASTER_PLAN.md                                |   41 +-
# docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md | 1703 ++++++++++++++++++++
# 2 files changed, 1741 insertions(+), 3 deletions(-)

git diff --check
# (no output — no whitespace errors)
```

---

## Unverified Items

None. All review items were verified against the actual document text and repository state.

---

## Untracked Review File Verification

All 23 pre-existing review files verified with matching SHA-256 hashes:

| File | SHA-256 |
|---|---|
| sprint-001-critical-files.txt | `88e84a1a0d3c258f730b60f2187d33972a72e2daa4ac98daeab75e1b7801e00c` |
| sprint-001-review-report.md | `1b8cf4eb02a57ec76b14db3f5c24b7ba10378007e055a78be7dc73fdef79332c` |
| sprint-001-review.diff | `7ed80f777ae1ae555d936832e02f5841c4ebf80704d5a8092acd7d4fb5d0da89` |
| sprint-002-planning-fix-review.diff | `0da043de25b888b17f98943a55aacbfe7532046cef65a1d94d3ab6e58827d1c8` |
| sprint-002-planning-review.md | `0e972f5ebcce84a912f9b7d7609734b00330cc88a3d0df410636ff0b7b1a2b80` |
| sprint-002-slice1-critical-files.txt | `2910a461f6bffe30aa7f7b5e5e104b017cdf70af1cd72e275caeffdcfa6b8614` |
| sprint-002-slice1-fix-review.diff | `d8f59ad29999d4029efa4a13e1ce9f6b400a6ef93b46ccdf5570c31bcbd4430c` |
| sprint-002-slice1-review-report.md | `5ab69d57e458d2aaf3392886ffd4e884b59c51ac20046d940696f43405f3e9fd` |
| sprint-002-slice1-review.diff | `bf1a0a8ebfea70cf0a3f6ba67b9b520b285b325aa9c69a251529e3f18f71b488` |
| sprint-002-slice2-design-fix-review.diff | `4ca9b43ac23cf2c4c5df44f47a6add1eb186bb623d971c916ee18a6d0039423d` |
| sprint-002-slice2a-critical-files.txt | `a2a4613d359c7786122029c49e6f6922fbf2c4f72a69570681c9e9c69ef45491` |
| sprint-002-slice2a-review-report.md | `31f4ff0f51cfed30ffa8ca088c37e5b9d121be27b1095556a570f6e6381327bf` |
| sprint-002-slice2a-review.diff | `068bf8ed53639bef3196e72d16a00e24c03cdf4d692bef98805d56c04294527e` |
| sprint-002-slice2b-critical-files.txt | `3e7a1a5bd1be579ec19e9ab54bc69239b37211df4b8fa760bf8ee97a6fdb7139` |
| sprint-002-slice2b-fix-review-report.md | `11b8be5422710594781141300356c481010cb58b0de26a99e05be5157a669b2e` |
| sprint-002-slice2b-fix-review.diff | `4b7ef6f5945b825ef81286206125c9fdf450041d4cff42eb6e3c9cc790eec8b1` |
| sprint-002-slice2b-review-report.md | `69358ab26e1aec6d60fc65147b7ec18142316b604d5e754f7655cb431fc399dc` |
| sprint-002-slice2b-review.diff | `555b6e541d0aea03acfcf339c6cdf10007379f42f6244a9d9c0832a99943dd5d` |
| sprint-002-slice2c-critical-files.txt | `17e592d301e81c44f0a7590cfc12084c01395a96ae853dc751b8a7c7aef8aa6a` |
| sprint-002-slice2c-fix-review-report.md | `730fa0aeea0b90f40bb623fdd172732028ca7c21f2c019ba2485c6617750e1d2` |
| sprint-002-slice2c-fix-review.diff | `1623b82801b3b36547cfb195ee0b33bea5a54cd14227e64b11bffc328d52e4ac` |
| sprint-002-slice2c-review-report.md | `ece024f43da22c0d786fa7b07bcbd6281385ce94d6d03b4565d28aa643da5c07` |
| sprint-002-slice2c-review.diff | `91c1d83a4ad545f13ea56a5e266c6f4cb80fb5859fe5ca3223282a7a4b093fcf` |

No review file was modified, deleted, staged, or committed.

---

## Finding Summary

| Severity | Count | IDs |
|---|---|---|
| BLOCKER | 0 | — |
| HIGH | 2 | M-1, M-2 |
| MEDIUM | 3 | M-3, M-4, M-5 |
| LOW | 3 | L-1, L-2, L-3 |
| **Total** | **8** | |

---

## Suggested New Owner Decisions

1. Draft discard identity semantics (HIGH priority — blocks M-1 and L-2)
2. Per-decision correction numbering mechanism (HIGH priority — blocks M-2)
3. Archived Decision correction eligibility (split from OD-S3-7, MEDIUM priority — blocks M-4)
4. Combined Household audit timeline scope (add to OD-S3-10, MEDIUM priority — blocks M-5)
5. Concurrent Discard/Confirm loser response code (LOW priority — depends on M-1 resolution)

---

## Final Conclusion

**REQUEST CHANGES**

The design is comprehensive, well-structured, and demonstrates strong understanding of PostgreSQL immutability patterns, transaction isolation, and API design. The three-approach data model comparison is fair and thorough. The 12-step confirm transaction, lock ordering, and concurrency analysis are largely correct and consistent with the existing Policy patterns.

However, two HIGH findings block approval:

**M-1 (Draft discard identity semantics):** The most critical lifecycle operation — discarding a Draft — leaves the decision identity in an undefined state. The design specifies "UPDATE decision status" without naming the target status, and the identity lifecycle trigger has no valid transition for this case. An implementer cannot determine what happens to the decision identity after discard. This is a missing lifecycle semantic that must be resolved before implementation.

**M-2 (correction_number mechanism):** The recommended PostgreSQL mechanism (`GENERATED ALWAYS AS IDENTITY`) cannot deliver the described per-decision sequential numbering. This is a technically incorrect design statement. The owner must choose between accepting global numbering, using a different mechanism, or removing per-decision numbering from the design.

Three MEDIUM findings (M-3 confirm lock order inconsistency, M-4 archived+Correction treated as approved, M-5 Household timeline boundary change) and three LOW findings (L-1 API detail ambiguity, L-2 loser response ambiguity, L-3 correction_count concurrency) provide additional refinement opportunities.

The design should be revised to resolve M-1 and M-2, correct M-3, clarify M-4 and M-5, and optionally address the LOW findings. After revision, the design should be ready for independent re-review.

PR #10 remains **OPEN, Draft, not merged**.
Slice 3 implementation remains **Not Authorized**.
