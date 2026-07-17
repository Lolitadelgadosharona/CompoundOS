# Sprint 002 Slice 3 Technical Design Gate — Final Report

**Date:** 2026-07-15
**Task:** Decision Journal and Append-Only Corrections — Technical Design Only
**Status:** COMPLETE — Draft PR created, CI passed, implementation NOT authorized

---

## 1. Baseline and Branch Information

| Item | Value |
|---|---|
| Initial branch | `main` |
| Initial HEAD SHA | `18697b4757be96f82aa1a7f62453a7751e148cc5` |
| Final branch | `planning/sprint-002-slice-3-decision-journal` |
| Final HEAD SHA | `043c07d` (short) |
| Commit message | `docs: propose Sprint 002 Decision Journal design` |

---

## 2. Files Created and Modified

### Created (1 file)

| File | Lines | Notes |
|---|---|---|
| `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md` | ~1703 | 18 sections, full design proposal |

### Modified (1 file)

| File | Changes |
|---|---|
| `docs/MASTER_PLAN.md` | +38/-3 lines: Current Sprint, Planning, In Progress, Review, Decision Log updated |

### Not Modified (verified)

No frontend code, backend code, tests, migrations, schemas, Python/npm dependencies, package-lock, Compose, CI, environment configuration, API endpoints, database triggers, ADR files, README, Investment Rulebook, or Guardian threshold files were touched.

---

## 3. Recommended Data Model

**Approach C: Stable Decision Identity + Draft + Confirmed Version**

Four tables:

1. `decisions` — stable identity with lifecycle metadata (`status`, `archived_at`, `archive_reason`, `created_at`)
2. `decision_drafts` — mutable Draft content (at most one per decision, enforced by UNIQUE constraint)
3. `decision_confirmed_snapshots` — immutable Confirmed snapshot (at most one per decision, INSERT-only trigger)
4. `decision_corrections` — append-only full replacement snapshot corrections

Compared against:

- **Approach A** (single-table lifecycle): rejected due to complex conditional triggers combining content immutability with archive metadata mutability
- **Approach B** (split Draft/Confirmed tables): rejected due to entity_id change between Draft and Confirmed, requiring bridging audit events

**Status: Recommended — Owner Approval Required**

---

## 4. Lifecycle Design

```
Draft → Confirmed → Archived
                     ↕ (unarchive)
```

- Draft: editable, optimistic revision control
- Confirmed: immutable snapshot, no edits, correctable via append-only DecisionCorrection
- Archived: hidden from default list, still readable, still correctable, can be unarchived
- No physical deletion at any stage

---

## 5. Confirm Transaction Design

12-step atomic transaction:

1. SELECT FOR UPDATE on decision identity
2. SELECT FOR UPDATE on Draft
3. Validate `expected_revision`
4. Validate `status = 'draft'`
5. Validate required fields (title, decision_summary, rationale, decision_date)
6. Fetch current Published Policy Version
7. Validate Version exists and `status = 'published'`
8. INSERT into `decision_confirmed_snapshots`
9. DELETE Draft
10. UPDATE decision identity `status = 'confirmed'`
11. INSERT AuditEvent
12. Commit

Response constructed from transaction-scoped scalar values — no post-commit read.

---

## 6. Archive Design

- Archive = hide from default list (not deletion)
- Optional `archive_reason` (text, max 4000 chars)
- `archived_at` (TIMESTAMPTZ, system-set)
- Unarchive allowed (clears `archived_at` and `archive_reason`)
- Archived decisions remain fully readable and correctable
- Archive and unarchive each create AuditEvents

---

## 7. DecisionCorrection Design

**Recommended model: Full replacement snapshot (Approach A)**

Each Correction stores all correctable fields as they should appear after correction. The effective view is the latest Correction's snapshot.

- `corrected_entry_id` FK to confirmed snapshot
- `correction_reason` (required, 1-8000 chars)
- `correction_number` (IDENTITY ALWAYS, per-decision)
- `created_at` (system-set)
- `actor` = `local-owner`
- INSERT-only trigger forbids UPDATE/DELETE
- Multiple corrections allowed; latest is effective view
- `selected_policy_version_id` NOT correctable
- No correction-of-correction

---

## 8. AuditEvent Design

7 candidate action names: `decision.draft.created`, `decision.draft.updated`, `decision.draft.discarded`, `decision.confirmed`, `decision.archived`, `decision.unarchived`, `decision.correction.appended`

- Uses existing `audit_events` table with `entity_type = "Decision"`
- Stable `entity_id` = decision identity UUID across all lifecycle events
- Metadata allowlist: `changed_fields`, `draft_revision`, `policy_version_number`, `correction_count`
- Redaction: no decision text, correction text, Policy text, or financial data
- Cursor-based pagination (`before_sequence_number` + `limit`)
- Both Decision-filtered endpoint and combined Household timeline

---

## 9. PostgreSQL Immutability Design

Three layers:

1. **Service validation**: lifecycle transitions, field rules, revision checks
2. **PostgreSQL triggers**:
   - `fn_decision_confirmed_snapshot_immutability()`: forbids all UPDATE/DELETE on snapshots
   - `fn_decision_correction_immutability()`: forbids all UPDATE/DELETE on corrections, validates FK on INSERT
   - `fn_decision_identity_lifecycle()`: restricts status transitions (draft→confirmed→archived↔confirmed)
3. **Physical table separation**: mutable tables (decisions, decision_drafts) separate from immutable tables (decision_confirmed_snapshots, decision_corrections)

Named CHECK/UNIQUE/FK constraints cover field lengths, Draft cardinality, and snapshot/correction references.

---

## 10. Concurrency and Lock Order

**Lock ordering: Household → Policy → Policy Version → Decision → Draft → Snapshot/Correction**

Deadlock analysis: Decision confirm acquires Policy lock first (consistent with Policy publish), then Decision, then Draft. No cycle possible with existing Policy operations.

| Scenario | Mechanism | Outcome |
|---|---|---|
| Concurrent Draft create | No singleton constraint | Both succeed independently |
| Concurrent Draft update | FOR UPDATE + revision check | Second gets 409 |
| Concurrent Confirm | FOR UPDATE on identity | Second gets 409 |
| Confirm vs Discard race | FOR UPDATE on identity | Loser gets 404 or 409 |
| Confirm vs Policy supersession | FOR UPDATE on Policy | Confirm re-validates Version status |
| Archive vs Correction | Different tables | Both proceed independently |
| Concurrent Corrections | INSERT with IDENTITY | Both succeed with distinct numbers |

---

## 11. Proposed API Table

| Method | Path | Status | Description |
|---|---|---|---|
| POST | `/api/decisions` | 201 | Create Decision Draft |
| GET | `/api/decisions` | 200 | Decision list (filterable by status) |
| GET | `/api/decisions/{id}/draft` | 200 | Draft detail |
| PATCH | `/api/decisions/{id}/draft` | 200 | Update Draft text |
| POST | `/api/decisions/{id}/draft/discard` | 204 | Discard Draft |
| POST | `/api/decisions/{id}/draft/confirm` | 201 | Confirm Draft |
| GET | `/api/decisions/{id}` | 200 | Decision detail (snapshot + metadata) |
| POST | `/api/decisions/{id}/archive` | 200 | Archive |
| POST | `/api/decisions/{id}/unarchive` | 200 | Unarchive |
| POST | `/api/decisions/{id}/corrections` | 201 | Append Correction |
| GET | `/api/decisions/{id}/corrections` | 200 | Correction list |
| GET | `/api/decisions/{id}/audit-events` | 200 | Decision audit (paginated) |

Error codes: 400, 404, 409, 422 per endpoint specification.
No hard-delete, recommendation, evaluation, scoring, AI, Guardian, or trading endpoints.

---

## 12. Proposed UI States

24 catalogued states: Missing Household, Missing Published Policy, Decision list, Empty Journal, New Draft, Draft editor, Save, Revision conflict, Dirty-state reload protection, Confirm review, Policy Version context, Confirmed immutable detail, Archive confirmation, Archived filter/view, Append Correction, Original view, Effective corrected view, Correction history, Audit timeline, Independent auxiliary errors, Stale-response guards, explicit Save (no autosave), explicit Confirm (non-advisory copy), Correction acknowledgement (original preserved).

Route: `/decisions`

---

## 13. Open Decisions Summary (OD-S3-1 through OD-S3-12)

All items: **Open — Owner Decision Required**

| ID | Decision | Recommendation |
|---|---|---|
| OD-S3-1 | Draft cardinality | Multiple independent Drafts |
| OD-S3-2 | Minimum fields and Confirm required | title, decision_summary, rationale, decision_date required |
| OD-S3-3 | Classification/tags | None initially |
| OD-S3-4 | decision_date type/backdating | DATE, allow backdating, allow future |
| OD-S3-5 | Policy Version reference | Current Published only |
| OD-S3-6 | Confirm semantics | Consume Draft, create snapshot |
| OD-S3-7 | Archive/unarchive | Allow unarchive, optional reason |
| OD-S3-8 | Correction model | Full replacement snapshot |
| OD-S3-9 | Correction rules | All text+dates correctable, Policy Version not correctable |
| OD-S3-10 | Audit pagination | Cursor-based for Decision audit |
| OD-S3-11 | UI copy | Mechanical/non-advisory |
| OD-S3-12 | Implementation splitting | 3A/3B/3C |

---

## 14. Recommended Implementation Splitting

- **Slice 3A**: Decision persistence and immutability (migration, ORM, constraints, triggers, tests)
- **Slice 3B**: Decision backend workflow and API (service, repository, Pydantic, router, concurrency tests)
- **Slice 3C**: Decision frontend workflow (page, API client, state management, conflict handling, tests)

Mirrors the proven 2A/2B/2C pattern. Each slice requires separate authorization and independent review.

---

## 15. Commands Executed

```bash
# Pre-flight verification
git branch --show-current           # → main
git log --oneline -1                # → 18697b4
git status                          # → clean, 23 untracked files
git stash list                      # → empty

# Branch creation
git checkout -b planning/sprint-002-slice-3-decision-journal main

# Commit and push
git add docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md docs/MASTER_PLAN.md
git commit -m "docs: propose Sprint 002 Decision Journal design"
git push -u origin planning/sprint-002-slice-3-decision-journal

# Draft PR creation
gh pr create --draft --title "Planning: Sprint 002 Slice 3 Decision Journal" --base main

# Verification
git diff --check                    # → no issues
git diff main...HEAD --check        # → no issues
git diff main...HEAD --stat         # → 2 files changed, +1741/-3
gh pr view 10                       # → OPEN, Draft
gh pr checks 10 --watch             # → all 6 checks pass
```

---

## 16. Git Diff Check Results

- `git diff --check`: **passed** (no whitespace errors)
- `git diff main...HEAD --check`: **passed**
- Tracked diff: **2 files only** — `docs/MASTER_PLAN.md` (+38/-3) and `docs/sprints/SPRINT_002_SLICE_3_TECHNICAL_DESIGN.md` (+1703)
- No frontend, backend, test, migration, dependency, Compose, CI, or environment changes

---

## 17. GitHub Actions Results

| Event | Run ID | infrastructure | backend | frontend | Overall |
|---|---|---|---|---|---|
| **push** | 29468125638 | pass (7s) | pass (40s) | pass (49s) | success |
| **pull_request** | 29468145349 | pass (5s) | pass (32s) | pass (1m2s) | success |

All 6 checks passed. No warnings or failures.

---

## 18. Untracked Review File Status

All 23 untracked review files verified — SHA-256 hashes unchanged from pre-task baseline:

| File | SHA-256 |
|---|---|
| sprint-001-critical-files.txt | `88e84a1a...` |
| sprint-001-review-report.md | `1b8cf4eb...` |
| sprint-001-review.diff | `7ed80f77...` |
| sprint-002-planning-fix-review.diff | `0da043de...` |
| sprint-002-planning-review.md | `0e972f5e...` |
| sprint-002-slice1-critical-files.txt | `2910a461...` |
| sprint-002-slice1-fix-review.diff | `d8f59ad2...` |
| sprint-002-slice1-review-report.md | `5ab69d57...` |
| sprint-002-slice1-review.diff | `bf1a0a8e...` |
| sprint-002-slice2-design-fix-review.diff | `4ca9b43a...` |
| sprint-002-slice2a-critical-files.txt | `a2a4613d...` |
| sprint-002-slice2a-review-report.md | `31f4ff0f...` |
| sprint-002-slice2a-review.diff | `068bf8ed...` |
| sprint-002-slice2b-critical-files.txt | `3e7a1a5b...` |
| sprint-002-slice2b-fix-review-report.md | `11b8be54...` |
| sprint-002-slice2b-fix-review.diff | `4b7ef6f5...` |
| sprint-002-slice2b-review-report.md | `69358ab2...` |
| sprint-002-slice2b-review.diff | `555b6e54...` |
| sprint-002-slice2c-critical-files.txt | `17e592d3...` |
| sprint-002-slice2c-fix-review-report.md | `730fa0ae...` |
| sprint-002-slice2c-fix-review.diff | `1623b828...` |
| sprint-002-slice2c-review-report.md | `ece024f4...` |
| sprint-002-slice2c-review.diff | `91c1d83a...` |

No review file was modified, deleted, staged, or committed.

---

## 19. Draft PR

| Item | Value |
|---|---|
| URL | https://github.com/Lolitadelgadosharona/CompoundOS/pull/10 |
| Title | Planning: Sprint 002 Slice 3 Decision Journal |
| Number | #10 |
| Base | `main` |
| Head | `planning/sprint-002-slice-3-decision-journal` |
| State | **OPEN** |
| Draft | **Yes** (not converted to Ready, not merged) |

---

## 20. Unresolved Issues

None. The task completed as specified.

---

## 21. Authorization Statement

**Slice 3 Implementation remains Not Authorized.**

The Draft PR contains only a technical design proposal. No code, migration, schema, API, UI, dependency, or configuration changes are included. Merging the design PR does not authorize any implementation slice.

Next steps (in order):

1. Independent Technical Design Review
2. Project owner answers OD-S3-1 through OD-S3-12
3. Design revisions based on review and owner decisions
4. Merge approved design into `main`
5. Separate explicit decision on whether to authorize Slice 3A

**No implementation will begin without separate explicit authorization.**
