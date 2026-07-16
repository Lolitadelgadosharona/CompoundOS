# Sprint 002 Slice 3 Technical Design: Decision Journal and Append-Only Corrections

- Date: 2026-07-15
- Status: **Approved Technical Design — Implementation Not Authorized**
- Authorization: Slice 3 Technical Design Gate only; implementation is **Not Authorized**
- Branch: `planning/sprint-002-slice-3-decision-journal`
- Baseline: `main` at `18697b4757be96f82aa1a7f62453a7751e148cc5`

---

## 1. Scope

This document proposes the technical design for the Decision Journal feature
authorized by the Sprint 002 Proposal. The Decision Journal records user-entered
investment decisions, their confirmation against a Published Investment Policy
Version, archival, and append-only corrections.

Slice 3 adds no recommendation, evaluation, scoring, suitability, eligibility,
compliance, AI, Guardian, Broker, market data, actual holdings, trading, or
export behavior. The Decision Journal records only what the user types,
confirms, archives, and corrects.

Merging this technical design does **not** authorize Slice 3 implementation.
Each implementation slice (3A, 3B, 3C) requires separate explicit authorization.

---

## 2. Approved Product Boundaries (Inherited)

The following product decisions are already approved and must not be changed by
this design:

### 2.1 Decision Journal Lifecycle

Draft → Confirmed → Archived

### 2.2 Confirmed Decision

- Must reference the Published InvestmentPolicyVersion selected by the user at
  confirmation time.
- Confirmed content must not be silently modified in place.
- Confirmed records must not be physically deleted.
- Corrections are made only through independent, append-only, immutable
  DecisionCorrection records.

### 2.3 DecisionCorrection

- Independent record, not a Decision lifecycle state.
- Append-only and immutable.
- Minimum fields: `corrected_entry_id`, `correction_reason`, `created_at`,
  `actor`.

### 2.4 Actor

Fixed constant `local-owner`. This is a local MVP audit identifier, not an
authenticated identity.

### 2.5 Product Boundaries

- Single Household, local-only, non-production
- No authentication, no authorization, no multi-user, no tenancy
- Default localhost binding

### 2.6 Prohibited Behavior

No AI generation, summarization, scoring, or recommendation; no AI Agent or AI
Investment Committee; no Guardian logic, threshold, monitoring, alert, or
notification; no Broker integration; no market data; no actual holdings,
accounts, balances, quantities, amounts, prices, costs, or returns; no
suitability, eligibility, or compliance conclusions; no trading, order
preparation, or execution; no Redis product logic; no export; no general hard
delete.

### 2.7 Decision Journal Purpose

Records only user input, confirmation, archival, corrections, and audit
history. Does not interpret, evaluate, or automatically enforce Investment
Policy, Investment Rulebook, or Guardian rules.

---

## 3. Data Model Comparison

### 3.1 Approach A: Single-Table Lifecycle

One `decision_entries` table holds Draft, Confirmed, and Archived rows. A
`status` column distinguishes lifecycle states. Draft fields are editable;
Confirmed content is protected by PostgreSQL triggers that forbid UPDATE on
content columns; Archived only permits the narrow set of state changes
(unarchive if approved, correction append).

**User mental model.** One table, one concept. The user sees "my decisions"
without understanding separate storage. This is simple for list views.

**Schema complexity.** Low column count but a wide nullable schema: Draft-only
fields (`revision`, `updated_at`) coexist with Confirmed-only fields
(`confirmed_at`, `selected_policy_version_id`) and archive metadata
(`archived_at`, `archive_reason`). Every column that transitions from mutable
to immutable requires careful trigger logic.

**API complexity.** Moderate. The same endpoint serves Draft and Confirmed
views with different allowed mutations. Status-based filtering is
straightforward.

**UI complexity.** Low. One list, one detail view with conditional edit
controls.

**Direct SQL immutability.** The trigger must distinguish "this row is
Confirmed, reject content UPDATE" from "this row is Archived, allow only
archive metadata changes." The trigger logic is complex because it must
understand three lifecycle states and which columns each state may touch.
Combining content immutability with archive metadata mutability in one trigger
increases the risk of overlooked edge cases.

**Confirm/Archive/Correction transaction.** Confirm is an in-place UPDATE
(`status = 'confirmed'`, set `confirmed_at`, set `selected_policy_version_id`).
Archive is another UPDATE. Correction is an INSERT into a separate table.

**Concurrency.** Concurrent Draft edits use optimistic revision. Concurrent
Confirm and Archive must serialize via `SELECT FOR UPDATE` on the same row.
Because the row identity never changes, there is no cross-table race.

**Provenance.** The Draft-to-Confirmed transition modifies the same row. The
original Draft content and the Confirmed snapshot are the same physical record.
There is no explicit "what was the Draft at the moment of confirmation"
artifact beyond the Confirmed row itself.

**Audit.** AuditEvent records status transitions. The entity_id is stable
across all lifecycle states.

**Future extension risk.** If a future product decision requires Draft history
(multiple Draft revisions before confirmation), the single-table approach would
need either a separate Draft-revision table or destructive overwrite, neither
of which is clean.

**Hidden multi-version risk.** None, because there is only one row per
decision.

---

### 3.2 Approach B: Draft and Confirmed Split Tables

`decision_entry_drafts` holds editable Draft content.
`confirmed_decision_entries` holds immutable Confirmed snapshots. Confirm
consumes the Draft (DELETE) and creates a Confirmed row (INSERT). Archive
changes only metadata on the Confirmed row (or moves to an archive metadata
table). DecisionCorrection is a separate append-only table.

**User mental model.** The user still sees "my decisions" but the backend has
two tables. This is invisible to the user unless the Draft and Confirmed
entities have different IDs, which would complicate the audit trail and
correction references.

**Schema complexity.** Higher. Two full-width tables with overlapping text
columns. The Draft table has `revision`, `updated_at`; the Confirmed table has
`confirmed_at`, `selected_policy_version_id`, archive metadata. Column
definitions must be kept in sync manually or via shared domain types.

**API complexity.** Moderate to high. Draft endpoints query one table;
Confirmed list/detail endpoints query another. The API must either unify the
response shape or expose two distinct resource types.

**UI complexity.** Moderate. The list view must combine Draft and Confirmed
entries from two tables. The transition from Draft editor to Confirmed detail
involves a resource identity change if IDs differ.

**Direct SQL immutability.** Strong. The Confirmed table can have a simple
trigger: forbid all UPDATE and DELETE. No need to distinguish lifecycle states
within the trigger. This is simpler and more robust than Approach A's
conditional trigger.

**Confirm transaction.** DELETE Draft + INSERT Confirmed + INSERT AuditEvents
in one transaction. If the Draft and Confirmed have different IDs, the
AuditEvent must reference both.

**Concurrency.** Draft edits are isolated. Confirm races with Draft discard
naturally: if the Draft is deleted first, Confirm fails with not-found.

**Provenance.** The Confirmed row is a distinct snapshot created at confirm
time. The Draft is consumed. The original Draft content is no longer in the
database unless the confirm transaction also preserves a copy.

**Audit.** The entity_id changes between Draft and Confirmed if IDs differ.
This complicates the audit timeline: Draft events reference the Draft ID,
Confirmed events reference the Confirmed ID. A bridging audit event is needed.

**Future extension risk.** If Draft revision history is needed later, the Draft
table already supports it. But if the product later requires "view the Draft
as it was when confirmed," the consumed-Draft model requires an additional
snapshot mechanism.

**Hidden multi-version risk.** If the Draft ID is not preserved, and the
Confirmed row gets a new ID, there is a risk of accidentally supporting
"confirm Draft A, create new Draft B, confirm Draft B" for the same decision
concept, producing two Confirmed records where one was expected.

---

### 3.3 Approach C: Stable Decision Identity + Draft + Confirmed Version

A `decisions` table provides a stable identity (the "decision folder"). A
`decision_drafts` table holds the current editable Draft content (at most one
per decision). A `decision_confirmed_snapshots` table holds the immutable
Confirmed snapshot (at most one per decision). DecisionCorrection is a
separate append-only table referencing the Confirmed snapshot.

The decision row itself holds only lifecycle metadata: `status` (draft,
confirmed, archived), `created_at`, and archive metadata. The actual content
lives in the draft or snapshot table.

**User mental model.** "I have a decision" is the stable identity. The Draft
is "what I'm writing" and the Confirmed snapshot is "what I confirmed." This
matches how users think about decisions: the decision is the concept, the Draft
and Confirmed are different representations of the same concept.

**Schema complexity.** Three tables (identity + draft + snapshot) plus
correction. Higher DDL count but each table is focused: identity holds
lifecycle metadata, draft holds mutable text, snapshot holds immutable text.
No nullable-to-non-nullable transitions across lifecycle states.

**API complexity.** Moderate. The stable decision ID is the resource identifier
across all states. Draft endpoints mutate the draft sub-resource; confirm
creates the snapshot sub-resource; archive updates the identity metadata. The
API presents one resource with sub-resources.

**UI complexity.** Low to moderate. The decision ID is stable throughout the
lifecycle. The list view queries the identity table joined with draft or
snapshot for display. The detail view conditionally renders draft or snapshot
content.

**Direct SQL immutability.** Strong. The snapshot table can have the same
trigger pattern as the existing `investment_policy_versions`: forbid all UPDATE
and DELETE. The draft table has no immutability constraints. Clear separation
of concerns.

**Confirm transaction.** Lock Policy FOR UPDATE → validate Published Version →
lock decision FOR UPDATE → lock draft FOR UPDATE → validate → INSERT snapshot
→ DELETE draft → UPDATE decision status → INSERT AuditEvents. All in one
transaction. The decision ID is stable throughout.

**Draft discard.** Discarding a never-Confirmed Draft atomically deletes
both the Draft row and the decision identity row in the same transaction
(OD-S3-13 Option A). An AuditEvent with the stable Decision UUID is written
before deletion. Confirmed, Archived, and Corrected decisions are never
hard-deleted.

**Correction numbering.** Corrections use per-decision sequential numbering:
the append transaction locks the decision identity row, computes
`MAX(correction_number) + 1` within the lock, and inserts with an explicit
value. Enforced by `UNIQUE(decision_id, correction_number)` (OD-S3-14 Option A).

**Concurrency.** Draft edits use optimistic revision on the draft table.
Confirm serializes via FOR UPDATE on decision + draft. The snapshot is created
inside the transaction and immediately sealed.

**Provenance.** The snapshot is a distinct immutable record created at confirm
time. The Draft is consumed (deleted). The decision ID ties them together. The
snapshot can store `confirmed_at`, `selected_policy_version_id`, and a copy of
all decision fields at confirmation time.

**Audit.** The entity_id is the stable decision ID across all lifecycle events.
Draft, confirm, archive, and correction events all reference the same decision
ID. This simplifies the audit timeline.

**Future extension risk.** The draft table could be extended to support
revision history without affecting the snapshot or identity tables. The
snapshot table could support multiple confirmed versions (like Policy versions)
if the product ever requires decision versioning, but this is explicitly not
introduced now.

**Hidden multi-version risk.** The design must ensure at most one draft and at
most one snapshot per decision. If both constraints are enforced by database
constraints (UNIQUE on `decision_id` in both draft and snapshot tables), there
is no risk of accidental multi-version semantics.

---

### 3.4 Comparison Matrix

| Criterion | A: Single Table | B: Split Tables | C: Identity + Draft + Snapshot |
|---|---|---|---|
| User mental model | Simple | Moderate (ID change) | Simple (stable ID) |
| Schema complexity | Low (wide nullable) | Moderate (overlap) | Higher (3 tables, focused) |
| API complexity | Moderate | Moderate-high | Moderate |
| UI complexity | Low | Moderate | Low-moderate |
| Direct SQL immutability | Complex trigger | Simple trigger | Simple trigger |
| Confirm transaction | In-place UPDATE | DELETE + INSERT | INSERT snapshot + DELETE draft |
| Concurrency | Straightforward | Natural isolation | Straightforward |
| Provenance | Same row | Different IDs | Stable ID, separate snapshot |
| Audit | Stable entity_id | Bridging needed | Stable entity_id |
| Future extension risk | Draft history awkward | Moderate | Clean extension path |
| Hidden multi-version risk | None | Possible if IDs differ | None (constrained) |

### 3.5 Recommendation

**Selected: Approach C (Stable Decision Identity + Draft + Confirmed Version)**

Rationale:

- The stable decision ID provides a consistent audit entity_id across all
  lifecycle states without bridging events.
- The snapshot table can reuse the same immutability trigger pattern already
  proven for `investment_policy_versions` in Slice 2A.
- The draft table is free to be mutable without trigger complexity.
- The confirm transaction is clean: create snapshot, consume draft, update
  identity — all inside one `session.begin()`.
- The approach avoids the wide nullable schema of Approach A and the ID-change
  complexity of Approach B.
- Future extension to Draft revision history or decision versioning is possible
  without schema restructuring, though neither is proposed now.

Resolved by Project Owner — 2026-07-16. Approach C is the approved data model.

---

## 4. Domain Design Questions

### 4.1 Draft Cardinality

**Option A: At most one Decision Draft per Household.**

Mirrors the existing Policy Draft rule (one `investment_policy_drafts` row per
`investment_policies` row enforced by `UNIQUE(policy_id)`). The user can only
work on one decision at a time. Creating a new Draft requires confirming or
discarding the current one.

Analysis: This is simple but overly restrictive for a journal. A user may
legitimately want to record multiple independent decisions in parallel — for
example, a portfolio rebalancing decision and an insurance coverage decision
are conceptually separate. Blocking parallel Drafts would force the user to
confirm or discard one before starting another, which does not match the
journal metaphor.

**Option B: Allow multiple independent Decision Drafts.**

Each Draft is a separate row with its own ID, created_at, and revision. The
Draft list endpoint returns all open Drafts. The UI shows a list of Drafts with
the ability to open, edit, confirm, or discard each one independently.

Analysis: This better matches the journal use case. The user may be
considering several decisions simultaneously. Each Draft is independently
editable, confirmable, and discardable. The stable decision ID (Approach C)
naturally supports this: each Draft has its own decision identity. The Draft
list is a query on the `decisions` table filtered to `status = 'draft'`.

Concurrency: concurrent Draft creation is straightforward because each Draft
gets its own identity row. No singleton constraint is needed.

List/detail API: `GET /api/decisions?status=draft` returns all Drafts.
`GET /api/decisions/{decision_id}/draft` returns one Draft's content. This is
more natural than `/current/draft` which implies a singleton.

UI complexity: the Draft list view replaces the singleton editor. The user
sees a list of in-progress decisions and selects one to edit. This is standard
list-detail navigation.

**Selected: Option B (multiple independent Drafts).** The singleton Draft
rule works for Policy because there is exactly one Policy per Household, but
the Decision Journal is inherently multi-entry. Each Draft creates an
independent Decision identity. The API uses Decision ID, not an ambiguous
`current/draft` path. The UI provides a Draft list and individual Draft
detail. Concurrent creation of different Decision Drafts is allowed.

This is recorded as **OD-S3-1** — Resolved by Project Owner — 2026-07-16.

---

### 4.2 Decision Classification

**Option A: Free text, no classification.**

Every decision is just a title and text fields. No category, tag, or label.
The user relies on title text and free-text search to find decisions.

**Option B: Small fixed neutral categories.**

A predefined set of neutral, non-evaluative labels such as "allocation",
"insurance", "tax", "estate", "liquidity", "other". The category is metadata,
not evaluation. It does not produce a recommendation, score, or compliance
conclusion.

**Option C: User-defined tags.**

The user can create and assign freeform text tags. Tags are stored as text
with length limits. No tag taxonomy is imposed.

Analysis: Option A is simplest but makes filtering and organization difficult
as the journal grows. Option B provides structure without evaluation, but the
fixed taxonomy may not cover all decision types. Option C is flexible but
introduces tag management complexity (creation, deletion, deduplication) that
may be premature for a local MVP.

None of these options produce recommendations, scores, pass/fail, suitability,
eligibility, compliance, or approval conclusions. They are purely
organizational metadata.

**Selected: no classification for Slice 3 MVP.** No fixed types, no user
tags, no system classification, no AI classification. If classification is
needed in the future, it must be designed in a separate approved Sprint.

This is recorded as **OD-S3-3** — Resolved by Project Owner — 2026-07-16.

---

### 4.3 Minimum Fields

The Sprint 002 Proposal defines 14 minimum fields for the Decision Journal.
This section assigns each field to a storage type, nullable rules, and length
limits.

| Field | Type | Draft nullable | Confirm required | Max length | Notes |
|---|---|---|---|---|---|
| `title` | Text | No (required at create) | Yes | 500 chars | Short decision identifier |
| `decision_summary` | Text | Yes | Yes | 8000 chars | What was decided |
| `rationale` | Text | Yes | Yes | 8000 chars | Why this was decided |
| `alternatives_considered` | Text | Yes | No | 8000 chars | Other options evaluated |
| `risks_and_uncertainties` | Text | Yes | No | 8000 chars | Known risks |
| `evidence_or_sources` | Text | Yes | No | 8000 chars | Supporting information |
| `expected_outcome` | Text | Yes | No | 4000 chars | What the user expects |
| `review_trigger` | Text | Yes | No | 4000 chars | Conditions for review |
| `review_date` | DATE | Yes | No | — | Optional future review date |
| `decision_date` / `occurred_at` | DATE | Yes | Yes | — | User-claimed decision date |
| `notes` | Text | Yes | No | 8000 chars | Additional free text |
| `selected_policy_version_id` | UUID FK | No (not in Draft) | Yes | — | System-set at confirm |

System timestamps (not user-editable):

| Field | Type | Notes |
|---|---|---|
| `created_at` | TIMESTAMPTZ | Database row creation time |
| `updated_at` | TIMESTAMPTZ | Draft last update time |
| `confirmed_at` | TIMESTAMPTZ | System confirmation time |
| `archived_at` | TIMESTAMPTZ | System archive time |
| `correction.created_at` | TIMESTAMPTZ | Correction append time |

Draft field nullability:

- `title` is required at Draft creation (cannot be empty or blank after trim).
- All other text fields are optional during Draft editing.
- The user may save a Draft with only a title and fill in other fields later.

Confirm mechanical required fields:

- `title`, `decision_summary`, `rationale`, and `decision_date` are
  mechanically required at confirm time.
- The server validates non-blank content for `title`, `decision_summary`, and
  `rationale` after trim.
- `decision_date` must be a valid DATE value (strict ISO `YYYY-MM-DD`).
- `selected_policy_version_id` is set by the system from the current
  Published Policy Version at confirm time (not user-supplied).
- The server does **not** evaluate text quality, meaning, completeness,
  appropriateness, risk level, or compliance.
- No amount, position, trade, or score fields are added.
- All other approval fields remain optional at confirm time, including
  `alternatives_considered`, `risks_and_uncertainties`, `evidence_or_sources`,
  `expected_outcome`, `review_trigger`, `review_date`, and `notes`.
- Drafts may be incomplete during editing; only presence, type, date, and
  length validation is enforced.

Character length limits follow the same pattern as the existing Policy text
fields: PostgreSQL `character_length()` semantics (code points, not bytes),
enforced independently in both Pydantic and named CHECK constraints.

No structured financial fields: no amount, quantity, price, cost, return,
percentage, position, account, or balance fields. The Decision Journal records
only user-entered text and dates.

This is recorded as **OD-S3-2** — Resolved by Project Owner — 2026-07-16.

---

### 4.4 Time Semantics

| Timestamp | Type | Source | Mutable | Notes |
|---|---|---|---|---|
| `created_at` | TIMESTAMPTZ | `now()` | No | Database row creation |
| `updated_at` | TIMESTAMPTZ | `now()` on UPDATE | Yes (auto) | Draft technical update |
| `confirmed_at` | TIMESTAMPTZ | `now()` at confirm | No | System confirmation time |
| `decision_date` | DATE | User input | Yes (in Draft) | User-claimed decision date |
| `review_date` | DATE | User input | Yes (in Draft) | Optional future date |
| `archived_at` | TIMESTAMPTZ | `now()` at archive | No | System archive time |
| `correction.created_at` | TIMESTAMPTZ | `now()` at append | No | Correction creation |

**decision_date: DATE vs TIMESTAMPTZ.**

The Proposal uses `decision_date` to mean "when the user says they made this
decision." This is a calendar date, not a precise timestamp. The user is
unlikely to say "I decided at 14:37:22 UTC." DATE is the appropriate type.

**Selected: DATE for decision_date.** API uses strict ISO `YYYY-MM-DD` strings.

**Backdating.**

The user may set `decision_date` to any past or present date. Backdating is
legitimate: the user may record a decision days after making it. The
`created_at` and `confirmed_at` timestamps provide the actual system timeline.

**Future decision_date.**

Future `decision_date` values are **forbidden**. The user may set
`decision_date` to today or any past date (backdating is legitimate — the
user may record a decision days after making it). The `created_at` and
`confirmed_at` timestamps provide the actual system timeline. The system
validates `decision_date <= CURRENT_DATE` at both Draft save and Confirm time.
This is a record integrity rule, not an investment rule.

**review_date.**

`review_date` is a user-entered optional DATE. It may be set to any date
including future dates. It records a date the user would like to review the
decision. It does **not** trigger any notification, alert, Guardian action,
or automated behavior. Whether the date has arrived produces no system
judgment or reminder. It is purely informational.

**AuditEvent ordering.**

AuditEvent continues to use `sequence_number` (IDENTITY ALWAYS) for
deterministic insertion ordering. `sequence_number` is not a global commit
order and may contain rollback gaps. Decision audit events use the same
`audit_events` table and the same ordering mechanism.

**User input time vs audit time.**

`decision_date` (user-claimed) is stored separately from `confirmed_at`
(system). The UI must display both to make the distinction clear. User input
times must never be used as audit or system timestamps.

This is recorded as **OD-S3-4** — Resolved by Project Owner — 2026-07-16.

---

### 4.5 Policy Version Reference

**Option A: Confirm may only reference the current Published Version.**

At confirm time, the server fetches the current `published` Investment Policy
Version and stores its ID. If the Policy is superseded between Draft creation
and confirm, the confirm fails and the user must re-confirm with the new
current Version.

**Option B: Confirm may reference any ever-Published immutable Version.**

The user selects from a list of all Published (and possibly Superseded)
Versions. The confirm stores the selected Version ID regardless of whether it
is currently current.

Analysis:

- Draft Policy must never be referenced — only Published (or Superseded)
  immutable Versions are eligible.
- The Version must belong to the current Household's Policy (ownership
  validation).
- Under Option A, the confirm transaction re-validates that the referenced
  Version is still `status = 'published'` at confirm time. If the Policy was
  superseded during Draft editing, the confirm fails with 409 and the user
  must re-select.
- Under Option B, the confirm transaction validates that the referenced
  Version exists and belongs to the Household's Policy, regardless of current
  status. This is less strict but introduces the risk of the user
  accidentally selecting an outdated Version.
- No lock on the Policy or Version is needed during Draft editing — the
  reference is only validated at confirm time.
- Policy supersession and Decision confirm can race: under Option A, the
  confirm transaction detects the race (Version is no longer `published`) and
  fails. Under Option B, there is no race because any Version is accepted.
- UI display: under Option A, the current Published Version summary is shown
  beside the Draft (similar to the existing Policy `CurrentPublishedSummary`).
  Under Option B, a version selector dropdown is needed.
- Historical Version selection increases the risk of the user choosing the
  wrong Version, especially in a local MVP with no undo.

**Selected: Option A (current Published Version only).** This is simpler,
avoids historical Version selection UI complexity, and matches the existing
Policy Draft sourcing rule (blank or current Published only). If the Policy
is superseded during Draft editing, the confirm fails with 409 and the user
re-confirms with the new current Version.

Confirm first locks the `investment_policies` row (`SELECT FOR UPDATE`), then
re-reads the current Published Version within the lock. If the request carries
a `selected_policy_version_id`, it must exactly equal the locked current
Published Version ID; otherwise the confirm returns 409. If the Version has
been superseded or the Policy changed concurrently, the confirm returns 409.
The Confirmed snapshot permanently stores that Version reference. Subsequent
Policy supersession does not alter the Decision's stored reference. Future
historical Version reference, if needed, must be separately approved.

This is recorded as **OD-S3-5** — Resolved by Project Owner — 2026-07-16.

---

### 4.6 Confirm Semantics

**Option A: Draft in-place transition to Confirmed.**

The Draft row is updated: `status = 'confirmed'`, `confirmed_at = now()`,
`selected_policy_version_id = <version>`. The row identity is preserved.

**Option B: Consume Draft, create immutable Confirmed snapshot.**

The Draft row is deleted. A new row is inserted into the snapshot table with
all confirmed field values, `confirmed_at = now()`, and
`selected_policy_version_id = <version>`. The decision identity row is updated
to `status = 'confirmed'`.

Under Approach C (selected data model), Option B is the natural choice:
the Draft is consumed and the snapshot is created. The decision identity
remains stable.

**Confirm transaction design (under Approach C + Option B):**

1. Locate the sole Household and its InvestmentPolicy.
2. Acquire `SELECT FOR UPDATE` on the `investment_policies` row.
3. Within the Policy lock, fetch and validate the current Published Policy
   Version (`status = 'published'`). If the request carries a
   `selected_policy_version_id`, it must exactly equal the locked current
   Published Version ID. A mismatch, superseded Version, or concurrent
   Policy change returns 409 lifecycle conflict.
4. Acquire `SELECT FOR UPDATE` on the decision identity row.
5. Acquire `SELECT FOR UPDATE` on the Draft row.
6. Validate `expected_revision` matches the Draft's current revision.
7. Validate `status = 'draft'` on the decision identity.
8. Validate required fields: `title`, `decision_summary`, `rationale`
   non-blank after trim; `decision_date` non-null.
9. INSERT into `decision_confirmed_snapshots` with all field values from the
   Draft, `confirmed_at = now()`, `selected_policy_version_id` from step 3.
10. DELETE the Draft row.
11. UPDATE decision identity: `status = 'confirmed'`.
12. INSERT AuditEvents: `decision.confirmed` with metadata
    `{ "policy_version_number": N }`.
13. Commit transaction.

**Explicit confirmation.** The confirm request must include
`confirmation: true` (literal boolean). The server does not auto-confirm.
After confirm, no editable Draft remains. There is no Confirmed→Draft or
reopen-for-editing capability. Changes are only possible through
DecisionCorrection.

**Non-advisory copy.** The confirm response and UI copy must not imply
recommendation, evaluation, or compliance. The confirmation is a mechanical
record that the user chose to save this decision against a specific Policy
Version.

**Draft consumption.** The Draft is deleted upon successful confirm. If
confirm fails (validation, conflict, or database error), the Draft remains
intact and editable.

**AuditEvent.** The confirm AuditEvent records `action = "decision.confirmed"`,
`entity_type = "Decision"`, `entity_id = <decision_id>`, metadata includes
`policy_version_number` but no decision text content.

**Database immutability.** The snapshot row is immediately sealed. The
immutability trigger forbids any subsequent UPDATE or DELETE on the snapshot.

**Rollback.** If any step fails, the entire transaction rolls back. The Draft
remains unchanged. The decision identity remains `status = 'draft'`.

**Concurrent confirm.** Two simultaneous confirm requests serialize through
the FOR UPDATE lock on the decision identity. The second request finds
`status != 'draft'` and returns 409.

**Confirm failure and Draft state.** If confirm fails for any reason
(validation, conflict, database error), the Draft remains in its current state.
No partial confirm is possible.

**Confirmed response.** The API returns the confirmed snapshot with all
fields, `confirmed_at`, `selected_policy_version_id`, and the decision ID.
The response is constructed from scalar values captured inside the locked
transaction, with no post-commit query.

This is recorded as **OD-S3-6** — Resolved by Project Owner — 2026-07-16.

---

### 4.7 Archive Semantics

**Archive as default-list hiding.**

Archiving a Confirmed Decision hides it from the default list view
(`GET /api/decisions` returns only non-archived by default). The archived
Decision is still accessible via `GET /api/decisions?include_archived=true` or
`GET /api/decisions/{decision_id}`.

**Archived readability.**

Archived Decisions remain fully readable. The snapshot, corrections, and audit
timeline are all accessible.

**Unarchive.**

**Selected: allow unarchive.** Archive is a soft-hide, not a permanent seal.
The user may unarchive to bring a Decision back to the default list
(`archived → confirmed`). Unarchive sets `archived_at = NULL` and clears
`archive_reason`. Unarchive is itself an auditable action. Archived→Draft is
not allowed.

**Archive reason.**

`archive_reason` is an optional user-entered text field (max 4000 chars). It
is stored on the decision identity row, not on the immutable snapshot.

**Archive metadata.**

`archived_at` (TIMESTAMPTZ, system-set) and `archive_reason` (nullable text)
are stored on the decision identity row.

**Actor.** `local-owner`.

**AuditEvent.** Archive creates a `decision.archived` AuditEvent. Unarchive
creates a `decision.unarchived` AuditEvent.

**Archived + Correction.**

Archived Decisions **may** receive appended Corrections (OD-S3-15 Option A).
Archive only affects default list visibility and does not close the factual
correction capability. The Correction INSERT trigger accepts
`status = 'confirmed'` or `'archived'` on the referenced Decision. Archive
and Correction can proceed independently (they touch different tables but
both lock the same decision identity row and serialize through it). A
Correction appended to an Archived Decision does **not** change the archived
status, `archived_at`, or `archive_reason`. The Correction trigger re-validates
`status IN ('confirmed', 'archived')` after acquiring the Decision lock.

**No physical deletion.**

Archive does not DELETE any row. The decision identity, snapshot, corrections,
and audit events all remain in the database.

This is recorded as **OD-S3-7** — Resolved by Project Owner — 2026-07-16.

---

### 4.8 DecisionCorrection Semantics

#### 4.8.1 Correction Data Model Comparison

**Approach A: Full replacement snapshot correction.**

Each Correction stores a complete "corrected view" of the Decision — all
fields as they should appear after correction. The effective view is the
latest Correction's full snapshot. The original Confirmed snapshot is never
modified.

- Explainability: high — the latest Correction is the complete current view.
- Immutability: each Correction is itself immutable.
- API complexity: high — the Correction request must include all correctable
  fields, even unchanged ones.
- UI complexity: moderate — the correction editor must present all fields.
- Multiple corrections: each Correction is a full snapshot; the latest wins.
- Original view: the Confirmed snapshot table.
- Effective view: the latest Correction's snapshot.
- Correction chain: query Corrections ordered by `created_at`, take the last.
- Audit: simple — each Correction is one event.
- Direct SQL protection: Correction table has INSERT-only trigger (same as
  snapshot).

**Approach B: Field-level patch correction.**

Each Correction stores only `changed_fields` (JSONB or structured columns) and
their replacement values. The effective view requires replaying the Correction
chain from the original snapshot.

- Explainability: moderate — must reconstruct the effective view.
- Immutability: each Correction is immutable.
- API complexity: moderate — the Correction request includes only changed
  fields.
- UI complexity: higher — the UI must show a diff view and reconstruct the
  effective view.
- Multiple corrections: the chain must be replayed in order.
- Original view: the Confirmed snapshot table.
- Effective view: reconstructed by applying Corrections in order.
- Correction chain: ordered by `created_at`.
- Audit: each Correction records `changed_fields` names only.
- Direct SQL protection: same INSERT-only trigger.

**Approach C: Explanatory correction only.**

Each Correction stores `correction_reason` (why the correction is needed) and
`corrected_text` (free-text description of what should change). No structured
replacement snapshot or field-level patch.

- Explainability: low for machine consumption, high for human reading.
- Immutability: each Correction is immutable.
- API complexity: low — only two text fields.
- UI complexity: low — a text form.
- Multiple corrections: each is independent; the reader must understand all.
- Original view: the Confirmed snapshot table.
- Effective view: no machine-readable effective view exists.
- Correction chain: list of explanatory notes.
- Audit: simple.
- Direct SQL protection: same INSERT-only trigger.

#### 4.8.2 Comparison Matrix

| Criterion | A: Full snapshot | B: Field patch | C: Explanatory |
|---|---|---|---|
| Explainability | High | Moderate | Low (machine) / High (human) |
| Immutability | Strong | Strong | Strong |
| API complexity | High | Moderate | Low |
| UI complexity | Moderate | Higher | Low |
| Multiple corrections | Latest wins | Chain replay | Independent notes |
| Current effective view | Latest Correction | Reconstructed | Not machine-readable |
| Original view | Snapshot table | Snapshot table | Snapshot table |
| Correction chain | Simple query | Ordered chain | Simple list |
| Audit | Simple | Changed-field names | Simple |
| Direct SQL protection | INSERT-only trigger | INSERT-only trigger | INSERT-only trigger |

#### 4.8.3 Recommendation

**Selected: Approach A (full replacement snapshot correction).**

Rationale:

- The full snapshot approach provides the clearest "current effective view"
  without requiring chain replay or interpretation.
- The API and storage cost is higher (each Correction stores all correctable
  fields) but Decision records are text-only with no financial data, so the
  storage cost is modest.
- The UI can show "Original" and "Current (corrected)" side by side with no
  reconstruction logic.
- Each Correction is independently immutable and self-contained.
- The correction INSERT trigger can follow the same pattern as the snapshot
  INSERT trigger.

This is recorded as **OD-S3-8** — Resolved by Project Owner — 2026-07-16.

#### 4.8.4 Owner Decisions on Correction Behavior

**Correctable fields.**

**Selected: the following user-input fields may be corrected:**
`title`, `decision_summary`, `rationale`, `alternatives_considered`,
`risks_and_uncertainties`, `evidence_or_sources`, `expected_outcome`,
`review_trigger`, `decision_date`, `review_date`, `notes`.

The following must **not** be corrected:
- Decision ID, Household ID
- `selected_policy_version_id` — the Policy Version reference is a
  point-in-time record of what was current when the user confirmed. Correcting
  it would retroactively change the Policy context, which is a historical
  fact.
- `created_at`, `confirmed_at`, `actor`
- AuditEvent records
- Archive lifecycle metadata (`archived_at`, `archive_reason`) — these live
  on the decision identity row, not on the snapshot. If the user wants to
  change `archive_reason`, they unarchive and re-archive with a new reason.
- Prior Correction records — each Correction is immutable.

**correction_reason** is required on every Correction.

**Multiple corrections** are allowed on the same Decision. Each Correction
must be based on the current effective snapshot and create a complete
replacement snapshot. A new Correction does not overwrite or modify old
Corrections. There is no correction-of-correction reference; all Corrections
reference the original Confirmed snapshot and the stable Decision identity.

**Correcting `decision_date`.** Allowed. The corrected `decision_date` must
still comply with the date rules in OD-S3-4 (no future dates).

**Original view** displays the Confirmed snapshot. **Effective view** displays
the latest Correction's full replacement snapshot, or the original if no
Corrections exist. Both views are always visible. The latest Correction forms
the effective view.

**No UPDATE or DELETE on Corrections.** The Correction table has a trigger
that forbids all UPDATE and DELETE operations. Corrections are append-only,
immutable, and cannot be deleted.

This is recorded as **OD-S3-9** — Resolved by Project Owner — 2026-07-16.

---

## 5. AuditEvent Design

### 5.1 Candidate Action Names

| Action | Triggered by | Notes |
|---|---|---|
| `decision.draft.created` | POST decision draft | New Draft |
| `decision.draft.updated` | PATCH decision draft | Text field save |
| `decision.draft.discarded` | POST discard | Explicit discard |
| `decision.confirmed` | POST confirm | Draft → Confirmed |
| `decision.archived` | POST archive | Confirmed → Archived |
| `decision.unarchived` | POST unarchive | Archived → Confirmed (list) |
| `decision.correction.appended` | POST correction | New Correction |

**Status: Accepted for Slice 3 implementation design.** These seven action
names are final for the Decision Journal technical design. They follow the
existing Policy audit pattern (`policy.created`, `policy.draft.created`,
`policy.published`, etc.). All API transactions, audit sections, service
layers, UI label mappings, and test matrices must use these exact strings.
No additional action names are permitted in Slice 3. The names carry no
recommendation, score, approval, or trade meaning. Any future rename or
addition requires a migration and API compatibility review.

### 5.2 AuditEvent Fields

Every Decision AuditEvent uses the existing `audit_events` table:

- `household_id`: the sole Household's ID.
- `entity_type`: `"Decision"` (distinct from `"HouseholdProfile"` and
  `"InvestmentPolicy"`).
- `entity_id`: the stable decision identity UUID.
- `actor`: `"local-owner"`.
- `action`: one of the candidate action names above.
- `occurred_at`: `now()` at insertion time.
- `sequence_number`: database-generated IDENTITY ALWAYS.
- `metadata`: JSONB, restricted by the allowlist below.

### 5.3 Metadata Allowlist

Audit metadata may contain only:

- `changed_fields`: sorted list of field names that changed (for draft updates)
- `draft_revision`: integer Draft revision number (for draft events)
- `policy_version_number`: integer Policy Version number (for confirm events)
- `correction_number`: per-decision sequential integer assigned to this
  Correction at insert time (per OD-S3-14: Decision row lock +
  `MAX(correction_number) + 1`). This records the number assigned to the
  individual Correction being audited, **not** a running total.

**Excluded from audit metadata.** `correction_count` (total Correction count
for the Decision) is **not** included in AuditEvent metadata. In concurrent
scenarios, a total computed inside the Correction transaction may not reflect
committed Corrections from other transactions. The Correction count is
computed at read time from the Correction list query, not stored in audit
metadata.

### 5.4 Metadata Redaction

Audit metadata must **not** contain:

- Decision free text (title, summary, rationale, etc.)
- Correction text (correction_reason, corrected fields)
- Policy text (objectives, time_horizon, etc.)
- Asset-class names, percentages, or allocation data
- Recommendations, scores, or evaluations
- Complete Decision snapshots

### 5.5 Audit Read: Decision-Filtered vs Combined Household Activity

**Existing Household audit endpoint analysis.**

The existing `GET /api/households/current/audit-events` endpoint returns all
AuditEvent rows for the Household. The current repository query filters by
`household_id` only, without restricting `entity_type`. This means Decision
audit events (`entity_type = 'Decision'`) will **naturally appear** in the
existing Household timeline once Decision audit events are written, even
without modifying the existing query code.

This is a user-visible resource content expansion: the Household timeline
grows to include Decision lifecycle events alongside existing Household and
Policy events. This should not be described as "no change" — it expands the
scope of an existing endpoint's response.

**Selected: Option A** (resolved by Project Owner — 2026-07-16). The design
provides a Decision-filtered endpoint and allows Decision events to naturally
appear in the combined Household timeline, as detailed in §5.5 above.

### 5.6 Pagination

The existing Household audit endpoint returns all events without pagination.
This is acceptable for Slice 1 volumes but will not scale as Decision events
are added. The Decision audit endpoint should support cursor-based pagination
using `sequence_number` as the cursor, matching the Policy version history
pattern (`before_sequence_number` + `limit`).

However, this introduces a pagination design decision that affects the
existing Household audit endpoint as well. The owner must decide whether to
introduce pagination for Decision audit only (and later retrofit Household
audit) or to design a unified pagination approach now.

**Selected: cursor-based pagination for the Decision audit endpoint from the
start, using `before_sequence_number` + `limit` (default 50, max 100).** The
existing Household audit endpoint remains unpaginated as a non-blocking
Backlog item.

---

## 6. PostgreSQL Immutability Design

### 6.1 Approach Comparison

**Service-only validation.** The service layer validates lifecycle transitions
and rejects invalid mutations. This is the weakest protection: a bug in the
service or a direct SQL session can bypass it.

**PostgreSQL triggers.** Triggers on the snapshot and correction tables enforce
immutability at the database level. This is the pattern established by
Slice 2A for `investment_policy_versions` and
`investment_policy_version_allocations`.

**Separate immutable table.** The snapshot and correction tables are
structurally separate from the mutable Draft and identity tables. This is
inherent in Approach C.

**Append-only table + triggers.** The correction table permits only INSERT.
UPDATE and DELETE are forbidden by trigger. This is the standard append-only
pattern.

### 6.2 Recommendation

**Selected: combine all four layers.**

- Service layer validates lifecycle transitions and field rules.
- PostgreSQL triggers enforce immutability on snapshot and correction tables.
- Snapshot and correction tables are physically separate from mutable tables.
- Correction table is append-only with INSERT-only trigger.

### 6.3 Trigger Coverage

**Confirmed snapshot immutability:**

- `fn_decision_confirmed_snapshot_immutability()`: BEFORE INSERT/UPDATE/DELETE
  on `decision_confirmed_snapshots`.
  - INSERT: validate all required fields are non-NULL, `confirmed_at` is set.
  - UPDATE: **forbid all** (return NULL, raise exception).
  - DELETE: **forbid all** (return NULL, raise exception).

This is simpler than the Policy Version trigger because Decision snapshots
have no sealing interval or status transitions. Once inserted, a snapshot is
immediately and permanently immutable.

**Correction append-only:**

- `fn_decision_correction_immutability()`: BEFORE INSERT/UPDATE/DELETE on
  `decision_corrections`.
  - INSERT: validate `corrected_entry_id` references a valid Confirmed
    snapshot belonging to the same Household. **Also validate that the
    referenced Decision's current status is `confirmed` or `archived`**
    (per OD-S3-15: Archived Decisions may receive Corrections; other
    statuses are rejected). Use a stable SQLSTATE and error identifier for
    each rejection path.
  - UPDATE: **forbid all** (return NULL, RAISE with stable error identifier).
  - DELETE: **forbid all** (return NULL, RAISE with stable error identifier).

**Decision identity lifecycle:**

- `fn_decision_identity_lifecycle()`: BEFORE UPDATE on `decisions`.
  - Allow only these status transitions:
    - `draft` → `confirmed` (at confirm time)
    - `confirmed` → `archived` (at archive time)
    - `archived` → `confirmed` (at unarchive time)
  - Forbid `confirmed` → `draft` and `archived` → `draft`.
  - No `discarded` status exists (OD-S3-13 Option A: discard uses DELETE,
    not status UPDATE).
  - Allow `archived_at` and `archive_reason` to be set/cleared only during
    archive/unarchive transitions.
  - Forbid changes to `created_at`.

- `fn_decision_identity_delete_guard()`: BEFORE DELETE on `decisions`.
  - **Allow only when `status = 'draft'`** (never-Confirmed Draft discard
    per OD-S3-13 Option A).
  - **Forbid DELETE when `status = 'confirmed'` or `'archived'`**
    (return NULL, RAISE with stable error identifier).
  - The approved discard transaction atomically cleans the Draft row and the
    identity row within the same transaction. Direct SQL DELETE on a
    confirmed or archived identity is rejected.
  - Multi-row DELETE tests must verify the guard fires for each affected row.

### 6.4 Constraint Coverage

| Rule | Layer | Mechanism |
|---|---|---|
| Draft title non-blank | Pydantic + service | Trim + min_length |
| Draft text field lengths | Pydantic + CHECK | Named constraints |
| Confirm required fields | Service | Non-blank validation |
| Snapshot immutability | Trigger | BEFORE UPDATE/DELETE → forbid |
| Correction immutability | Trigger | BEFORE UPDATE/DELETE → forbid |
| Correction references valid Confirmed | Trigger + FK | FK + INSERT trigger check |
| Correction same Household | Trigger | INSERT trigger check |
| Decision lifecycle transitions | Trigger | BEFORE UPDATE status check |
| At most one Draft per Decision | UNIQUE | `decision_id` in drafts table |
| At most one snapshot per Decision | UNIQUE | `decision_id` in snapshots table |
| `decision_date` is valid DATE | Pydantic + type | PostgreSQL DATE type |
| `selected_policy_version_id` is valid | FK + service | FK to versions + service check |

### 6.5 Correction Numbering

**Selected: per-decision sequential numbering (OD-S3-14 Option A).**

Each Decision displays its Corrections numbered 1, 2, 3, etc. This is NOT
generated by `GENERATED ALWAYS AS IDENTITY` (which is a table-level sequence).
Instead, the Correction append transaction:

1. Acquires `SELECT FOR UPDATE` on the decision identity row.
2. Within the lock, computes `MAX(correction_number) + 1` filtered to the
   current `decision_id`.
3. INSERTs the Correction with the explicit `correction_number` value.
4. The first Correction for a Decision is numbered 1.

Enforced by `UNIQUE(decision_id, correction_number)`.

**Concurrency:** Concurrent Corrections on the same Decision are serialized
through the Decision row lock. Corrections on different Decisions proceed
independently and concurrently.

**Rollback:** If the transaction fails, the number is not committed. A retry
recomputes `MAX(correction_number) + 1` within a new lock acquisition.
Rollback leaves no committed gap.

**Ordering:** Correction list is ordered by `correction_number ASC`. The
latest effective snapshot is the Correction with the maximum
`correction_number`.

**Audit:** AuditEvent may record the `correction_number` for the individual
Correction being audited. It must not record or claim it as the final
`corrections_count`. The `corrections_count` is computed at read time only.

**Distinction:** `correction_number` is not the AuditEvent `sequence_number`
and is not commit time.

This is recorded as **OD-S3-14** — Resolved by Project Owner — 2026-07-16.

### 6.6 Deferred Sealing

Unlike Policy Versions, Decision snapshots do not have an unsealed interval.
The snapshot is fully populated and immutable from the moment of insertion.
No deferred sealing trigger is needed.

### 6.7 Direct SQL Tests

Implementation must include tests that connect to real PostgreSQL and verify:

- Direct SQL UPDATE on a confirmed snapshot is rejected by trigger.
- Direct SQL DELETE on a confirmed snapshot is rejected by trigger.
- Direct SQL UPDATE on a correction is rejected by trigger.
- Direct SQL DELETE on a correction is rejected by trigger.
- Direct SQL UPDATE on decision identity with invalid status transition is
  rejected.
- All trigger error identifiers are stable and match expected patterns.

### 6.8 Downgrade

A future migration downgrade must:

1. Drop correction table triggers.
2. Drop correction table.
3. Drop snapshot table triggers.
4. Drop snapshot table.
5. Drop draft table.
6. Drop decision identity table.
7. Remove Decision AuditEvents (or leave them — they reference a dropped
   entity_type).

The downgrade must preserve all Household, Policy, and existing AuditEvent
data.

### 6.9 FK Delete Behavior

All cross-table foreign key relationships must use `ON DELETE RESTRICT` (or
the default `NO ACTION`) to prevent cascade deletion from bypassing
immutability triggers:

- `decision_confirmed_snapshots.decision_id` → `decisions.id`: RESTRICT
- `decision_corrections.corrected_entry_id` → `decision_confirmed_snapshots.id`: RESTRICT
- `decision_corrections.decision_id` → `decisions.id`: RESTRICT (if direct FK)
- `decision_confirmed_snapshots.selected_policy_version_id` → `investment_policy_versions.id`: RESTRICT
- `decision_drafts.policy_id` → `investment_policies.id`: RESTRICT
- `decision_drafts.decision_id` → `decisions.id`: ON DELETE CASCADE (the
  approved discard transaction deletes the identity, and the Draft cascades;
  alternatively the service deletes the Draft first within the same transaction).
  This FK must never allow cascade deletion of a confirmed or archived
  identity's Draft — the DELETE guard trigger on `decisions` prevents this.

**AuditEvent:** The existing `audit_events.household_id` FK uses `ON DELETE
RESTRICT`. Decision AuditEvents reference the decision identity via
`entity_id` (UUID, no FK). When OD-S3-13 Option A deletes the decision identity
on discard, the AuditEvent `entity_id` becomes a dangling UUID reference. This
is acceptable because AuditEvents are immutable records — the `entity_id`
documents what entity was affected at the time, and the entity may no longer
exist. No FK constraint exists on `entity_id` by design.

**Draft FK (OD-S3-13 Option A):** The approved discard transaction explicitly
deletes the Draft row before deleting the decision identity row within the
same transaction. The `decision_drafts.decision_id` FK uses ON DELETE CASCADE
as a safety net, but the service drives the deletion order. The DELETE guard
trigger on `decisions` prevents any DELETE on confirmed or archived identities,
so cascade never reaches a Draft belonging to a non-draft Decision.

### 6.10 Trigger Comparison Safety

- All lifecycle trigger comparisons involving nullable metadata
  (`archived_at`, `archive_reason`) must use `IS DISTINCT FROM` to prevent
  NULL three-valued logic bypass.
- The `status` column on `decisions` must be `NOT NULL` with a CHECK
  constraint limiting values to the approved lifecycle states.
- Direct SQL tests must verify that setting status to NULL is rejected.
- Multi-row UPDATE/DELETE statements on mutable tables must be tested to
  verify triggers fire for each affected row.

### 6.11 Cross-Household Ownership

All Decision tables must enforce that they belong to the sole Household:

- `decisions.household_id` FK → `household_profiles.id`: RESTRICT
- `decision_drafts` inherits ownership through `decision_id` FK → `decisions.id`
- `decision_confirmed_snapshots` inherits ownership through `decision_id` FK
- `decision_corrections` inherits ownership through `decision_id` FK
- `selected_policy_version_id` must reference a Version belonging to the same
  Household's Policy. Validated at the service level (the FK guarantees the
  Version exists; the service verifies it belongs to the Household's Policy).

**Recommended approach:** Composite FK is not needed because the singleton
Household constraint guarantees all entities share the same Household. Service
validation at confirm time verifies `selected_policy_version_id` ownership.
The Correction INSERT trigger validates that the referenced snapshot belongs
to the same decision (and therefore the same Household).

### 6.12 Committed Lifecycle Consistency

The database must prevent invalid committed states:

- `status = 'draft'` with no Draft row: prevented by OD-S3-13 resolution.
  If Option A (identity deletion), this state cannot exist. If Option B
  (discarded status), the trigger must forbid `status = 'draft'` after Draft
  deletion.
- `status = 'confirmed'` with no snapshot: the confirm transaction creates the
  snapshot and updates status atomically. A deferred constraint trigger can
  verify at commit time that every confirmed/archived decision has a snapshot.
- `status = 'confirmed'` with a Draft: the confirm transaction deletes the
  Draft and updates status atomically. The `UNIQUE(decision_id)` on the Draft
  table and the trigger together prevent this state.
- Draft and snapshot simultaneously: prevented by the confirm transaction's
  atomic DELETE draft + INSERT snapshot within one transaction.
- Correction referencing a non-existent snapshot: FK RESTRICT prevents this.
- Invalid `status`/time combinations: the identity lifecycle trigger validates
  that `archived_at` is set only during archive transitions and cleared only
  during unarchive.

**Selected: add a deferred constraint trigger**
`fn_decision_lifecycle_consistency()` that verifies at commit time:

- Every `status = 'confirmed'` or `'archived'` decision has exactly one
  snapshot.
- No `status = 'draft'` decision has a snapshot.
- No decision has both a Draft and a snapshot simultaneously.

This is analogous to the existing `fn_investment_policy_version_require_sealed()`
deferred trigger from Slice 2A.

---

## 7. Transaction and Concurrency Design

### 7.1 Lock Ordering

**Selected:**

`Household → Policy → Policy Version → Decision → Draft → Snapshot/Correction`

The Decision lock order extends the existing Policy lock order:

1. `investment_policies` (FOR UPDATE) — when confirm needs to validate the
   Policy Version.
2. `decisions` (FOR UPDATE) — the decision identity row.
3. `decision_drafts` (FOR UPDATE) — the Draft row.

The Policy lock is acquired first because confirm must validate the Policy
Version before proceeding with the Decision. If two transactions both need
Policy + Decision locks, they acquire them in the same order, preventing
deadlock.

**Deadlock analysis with existing Policy operations:**

- Policy publish: locks Policy → locks Policy Draft. Does not touch Decision
  tables. No deadlock risk.
- Decision confirm: locks Policy → locks Decision → locks Decision Draft.
  Policy is locked first, consistent with Policy publish.
- Concurrent Policy publish + Decision confirm: both lock Policy first. One
  waits. After the first commits, the second proceeds. No deadlock.
- Concurrent Decision confirms: both lock Policy first (same row), then
  Decision (different rows). The Policy lock serializes them. No deadlock.

**Correction append lock order.**

The Correction append transaction acquires `SELECT FOR UPDATE` on the
decision identity row before computing `MAX(correction_number) + 1` (per
OD-S3-14 Option A). This serializes concurrent Corrections on the same
Decision through the decision row lock. The lock order is:
`decisions` (FOR UPDATE) → INSERT correction. Corrections on different
Decisions proceed independently and concurrently.

### 7.2 Concurrency Scenarios

**Concurrent Draft create.**

Two simultaneous Draft creation requests create separate decision identity
rows and separate Draft rows. No conflict because there is no singleton
constraint on decisions. Both succeed.

**Concurrent Draft update.**

Two simultaneous PATCH requests on the same Draft serialize through
`SELECT FOR UPDATE` on the Draft row. The second request checks
`expected_revision` and finds it stale (the first update already incremented
it). Returns 409.

**Concurrent Confirm.**

Two simultaneous confirm requests on the same Draft serialize through
`SELECT FOR UPDATE` on the decision identity. The second request finds
`status != 'draft'` and returns 409.

**Discard Draft.**

Discard applies only to Decisions with `status = 'draft'` that have never
been Confirmed (OD-S3-13 Option A). The discard transaction:

1. Acquires `SELECT FOR UPDATE` on the decision identity and Draft rows.
2. Validates `expected_revision` and `status = 'draft'`.
3. Verifies the Decision has never been Confirmed (no snapshot exists).
4. INSERTs a `decision.draft.discarded` AuditEvent with the stable Decision
   UUID as `entity_id` (AuditEvent has no FK to the decision identity, so
   the event survives identity deletion).
5. DELETEs the Draft row.
6. DELETEs the decision identity row.
7. Commits the transaction.

This is a narrow exception to the general no-hard-delete rule, limited to
never-Confirmed Drafts only. Confirmed, Archived, Confirmed snapshots,
Corrections, and AuditEvents are never hard-deleted.

The design prohibits the committed orphan state: `status = 'draft'` with no
Draft row. The DELETE guard trigger (`fn_decision_identity_delete_guard`)
rejects DELETE on confirmed or archived identities. No `discarded` or
`abandoned` lifecycle status is introduced. There is no discarded Decision
list, detail, or restore capability.

**Confirm vs Discard race.**

Both acquire `SELECT FOR UPDATE` on the decision identity. The first to
acquire the lock proceeds; the second finds the state has changed:

- When **discard wins** first: the decision identity is atomically deleted.
  A subsequent confirm attempt targeting the same decision ID returns **404**
  (entity no longer exists).
- When **confirm wins** first: the Decision transitions to `status = 'confirmed'`.
  A subsequent discard attempt finds `status != 'draft'` and returns **409**
  (lifecycle conflict).

An unrelated missing decision ID (never existed) always returns **404**.

**Confirm vs Policy supersession race.**

The confirm transaction locks the Policy row FOR UPDATE to validate the
Published Version. If a concurrent Policy publish has already locked the
Policy row, the confirm waits. After the Policy publish commits, the confirm
re-checks: if the Version it intended to reference is now `superseded`, the
confirm returns 409. If the confirm wins the lock first, the Policy publish
waits and then proceeds normally (the Decision confirm does not block Policy
publish — it only reads the Version).

**Archive vs Correction race.**

Archive updates the decision identity row (`status`, `archived_at`).
Correction inserts into the correction table and locks the decision identity
row (`SELECT FOR UPDATE`). Both operations lock the same decision identity
and serialize through that lock. Since Archived Decisions may receive
Corrections (OD-S3-15 Option A), the Correction INSERT trigger accepts
`status = 'confirmed'` or `'archived'`. After the lock is acquired, the
Correction re-validates the status. Archive and Correction can proceed
without conflict regardless of ordering.

**Concurrent Corrections.**

Both Correction appends acquire `SELECT FOR UPDATE` on the decision identity
row (per OD-S3-14 Option A). They serialize through the row lock. Each
computes `MAX(correction_number) + 1` within the lock. Both succeed with
distinct per-decision numbers. Rollback of one does not leave a gap in the
other's committed numbering. A failed-and-retried Correction may receive a
different number on retry. Corrections on different Decisions proceed
independently and concurrently.

### 7.3 Optimistic Revision

The Draft row carries a `revision` integer (default 1, incremented on each
mutation). Every Draft mutation request includes `expected_revision`. After
acquiring FOR UPDATE, the service checks `draft.revision == expected_revision`.
On mismatch, returns 409 Conflict.

### 7.4 Stale Revision

A stale `expected_revision` always returns 409. The client must fetch the
latest Draft and retry.

### 7.5 READ COMMITTED

All transactions use PostgreSQL's default READ COMMITTED isolation level.
FOR UPDATE locks prevent phantom reads within a transaction. No SERIALIZABLE
or REPEATABLE READ is needed.

### 7.6 Session Reuse

Database sessions are request-scoped via SQLAlchemy's `sessionmaker`. Each
HTTP request gets a fresh session. Sessions are not shared across requests.
Connection pool reuse is handled by `pool_pre_ping=True`.

### 7.7 Expected 409 Responses

- Draft update with stale revision.
- Confirm on a Decision that is no longer in draft status.
- Discard on a Decision that is no longer in draft status.
- Confirm with a Policy Version that is no longer published.
- Archive on a Decision that is not confirmed.
- Correction append on a Decision whose status is `draft` (trigger rejects;
  Correction requires `confirmed` or `archived`).
- Confirm loser when discard wins (atomic identity deletion): returns 404
  (entity no longer exists).

### 7.8 Unrelated IntegrityError

Unrelated database errors (e.g., a CHECK constraint violation on a text field
length) must not be mapped to 409. Only explicitly identified named
constraints are mapped to domain conflicts. All other IntegrityError and
database exceptions propagate as 500.

### 7.9 Rollback

All transactions use `session.begin()` which automatically rolls back on
exception. No partial state is possible. Failed Draft creates, updates,
confirms, discards, archives, and corrections are fully rolled back.

---

## 8. API Design

**Status: design only, not implemented.**

All endpoints are under `/api/decisions`. All requests and responses are JSON.
All mutations include `expected_revision` for optimistic concurrency where
applicable.

### 8.1 Create Decision Draft

| | |
|---|---|
| Method | `POST` |
| Path | `/api/decisions` |
| Request | `{ "title": string (1-500 chars, required, non-blank after trim) }` |
| Response | `201` with `{ id, title, revision: 1, status: "draft", created_at, updated_at }` |
| Errors | `400` (blank title), `422` (schema violation) |
| Transaction | INSERT decision identity + INSERT draft + INSERT AuditEvent |
| Audit | `decision.draft.created`, metadata `{ "draft_revision": 1 }` |

### 8.2 Decision List

| | |
|---|---|
| Method | `GET` |
| Path | `/api/decisions` |
| Query | `status` (optional: `draft`, `confirmed`, `archived`), `include_archived` (boolean, default false) |
| Response | `200` with `{ items: [...] }` |
| Items | Each item includes `id`, `title`, `status`, `created_at`, and either draft `updated_at` or confirmed `confirmed_at` |
| Ownership | Filtered to the sole Household |

### 8.3 Draft Detail

| | |
|---|---|
| Method | `GET` |
| Path | `/api/decisions/{decision_id}/draft` |
| Response | `200` with all Draft text fields, `revision`, `created_at`, `updated_at` |
| Errors | `404` (decision not found or not in draft status) |
| Ownership | Validated against the sole Household |

### 8.4 Update Draft

| | |
|---|---|
| Method | `PATCH` |
| Path | `/api/decisions/{decision_id}/draft` |
| Request | `{ expected_revision: int, ...text fields (all optional) }` |
| Response | `200` with updated Draft fields, new `revision` |
| Errors | `404` (not found), `409` (stale revision), `400` (no changes), `422` (schema) |
| Transaction | SELECT FOR UPDATE decision + draft → validate revision → UPDATE fields → INSERT AuditEvent |
| Audit | `decision.draft.updated`, metadata `{ "changed_fields": [...], "draft_revision": N }` |
| Response snapshot | Constructed from transaction-scoped scalar values, no post-commit read |

### 8.5 Discard Draft

| | |
|---|---|
| Method | `POST` |
| Path | `/api/decisions/{decision_id}/draft/discard` |
| Request | `{ expected_revision: int }` |
| Response | `204` No Content |
| Errors | `404` (not found), `409` (stale revision, not in draft status) |
| Transaction | SELECT FOR UPDATE decision + draft → validate revision and never-Confirmed → INSERT AuditEvent → DELETE draft → DELETE decision identity → commit |
| Identity handling | Atomic identity deletion (OD-S3-13 Option A): DELETE decision identity row only when `status = 'draft'` and the Decision has never been Confirmed. The DELETE guard trigger rejects DELETE on confirmed or archived identities. |
| Audit | `decision.draft.discarded`, entity_id = stable Decision UUID (AuditEvent has no FK to decision identity; the event survives identity deletion) |

### 8.6 Confirm Draft

| | |
|---|---|
| Method | `POST` |
| Path | `/api/decisions/{decision_id}/draft/confirm` |
| Request | `{ expected_revision: int, confirmation: true }` |
| Response | `201` with confirmed snapshot (all fields, `confirmed_at`, `selected_policy_version_id`) |
| Errors | `404` (not found), `409` (stale revision, already confirmed, Policy Version superseded), `400` (required fields missing, confirmation not true) |
| Transaction | Lock Policy → lock decision → lock draft → validate → INSERT snapshot → DELETE draft → UPDATE decision status → INSERT AuditEvents |
| Audit | `decision.confirmed`, metadata `{ "policy_version_number": N }` |
| Response snapshot | Constructed from transaction-scoped scalar values, no post-commit read |

### 8.7 Confirmed Decision Detail

| | |
|---|---|
| Method | `GET` |
| Path | `/api/decisions/{decision_id}` |
| Response | `200` with decision identity, `original_snapshot`, `effective_snapshot`, `latest_correction_metadata`, archive metadata |
| Errors | `404` (not found) |
| Ownership | Validated against the sole Household |

**Response shape:**

- `original_snapshot`: always the immutable Confirmed snapshot as created at
  confirm time (all fields, `confirmed_at`, `selected_policy_version_id`).
  This never changes after confirm.
- `effective_snapshot`: the current effective view of the Decision.
  - If no Corrections exist: the effective snapshot equals the original
    snapshot. The recommended approach is to return the original snapshot
    content in this field (not null), so the client always has a usable
    effective view without conditional logic.
  - If Corrections exist: the effective snapshot is the latest Correction's
    complete field replacement snapshot (per OD-S3-8: full replacement model).
- `latest_correction_metadata`: present only when Corrections exist.
  Includes `correction_id` (UUID), `correction_number` (per-decision
  sequential), `created_at`, `correction_reason`. Does **not** include
  correction body fields (those are in `effective_snapshot`).
- `corrections_count`: total number of Corrections, computed at read time
  from the Correction list query (not from audit metadata). This is safe
  because the read query sees a consistent snapshot under READ COMMITTED.
- Archive metadata: `status`, `archived_at`, `archive_reason` (from the
  decision identity row).

The response must not require the client to guess whether the
`effective_snapshot` reflects corrections or not. The presence of
`latest_correction_metadata` disambiguates.

The UI Original view displays `original_snapshot`. The UI Effective view
displays `effective_snapshot`. Both are always consistent with the API.

### 8.8 Archive

| | |
|---|---|
| Method | `POST` |
| Path | `/api/decisions/{decision_id}/archive` |
| Request | `{ archive_reason: string (optional, 0-4000 chars) }` |
| Response | `200` with updated decision identity (status, archived_at, archive_reason) |
| Errors | `404` (not found), `409` (not in confirmed status) |
| Transaction | SELECT FOR UPDATE decision → validate status = confirmed → UPDATE status, archived_at, archive_reason → INSERT AuditEvent |
| Audit | `decision.archived` |

### 8.9 Unarchive

| | |
|---|---|
| Method | `POST` |
| Path | `/api/decisions/{decision_id}/unarchive` |
| Request | `{}` (empty body) |
| Response | `200` with updated decision identity (status = confirmed, archived_at = null) |
| Errors | `404` (not found), `409` (not in archived status) |
| Transaction | SELECT FOR UPDATE decision → validate status = archived → UPDATE status, clear archived_at, clear archive_reason → INSERT AuditEvent |
| Audit | `decision.unarchived` |

### 8.10 Append Correction

| | |
|---|---|
| Method | `POST` |
| Path | `/api/decisions/{decision_id}/corrections` |
| Request | Full replacement snapshot: all correctable fields + `correction_reason` (required, 1-8000 chars) |
| Response | `201` with the new Correction record (all fields, `correction_number`, `created_at`) |
| Errors | `404` (decision not found), `409` (decision status is `draft` — Correction requires `confirmed` or `archived`), `422` (schema) |
| Transaction | SELECT FOR UPDATE decision → validate `status IN ('confirmed', 'archived')` → compute `correction_number = MAX(correction_number)+1` for this decision_id → INSERT correction → INSERT AuditEvent |
| Audit | `decision.correction.appended`, metadata `{ "correction_number": N }` (see §5.3 — this is the individual Correction's number, not a total count) |
| Direct SQL | INSERT-only trigger on corrections table |

### 8.11 Correction List

| | |
|---|---|
| Method | `GET` |
| Path | `/api/decisions/{decision_id}/corrections` |
| Response | `200` with `{ items: [...] }` ordered by `correction_number` ASC |
| Errors | `404` (decision not found) |
| Note | `corrections_count` is computed from this list at read time, not from audit metadata |

### 8.12 Decision-Filtered Audit Events

| | |
|---|---|
| Method | `GET` |
| Path | `/api/decisions/{decision_id}/audit-events` |
| Query | `before_sequence_number` (optional cursor), `limit` (1-100, default 50) |
| Response | `200` with `{ items: [...], next_before_sequence_number: int or null }` |
| Errors | `404` (decision not found) |
| Ownership | Filtered by `household_id` + `entity_type = "Decision"` + `entity_id` |

### 8.13 Forbidden Endpoints

The following endpoints are **not** designed, implemented, or planned:

- Hard delete (any Decision, snapshot, Correction, or AuditEvent)
- Recommendation, evaluation, scoring, or compliance endpoints
- AI or Guardian endpoints
- Trading, order, or Broker endpoints
- Automatic mutation retry

---

## 9. UI Technical Design

**Status: design only, not implemented.**

### 9.1 Route

`/decisions`

### 9.2 UI State Catalog

**Missing Household.** If no Household exists, redirect to `/household` with
a message that a Household is required before using the Decision Journal.

**Missing Published Policy.** If no Published Policy Version exists, the user
may create Drafts but cannot confirm them. The UI shows a notice: "Publish an
Investment Policy before confirming decisions." Draft creation and editing
remain available.

**Decision list.** Displays all Decisions grouped by status (Draft, Confirmed,
Archived). Each item shows `title`, `status`, `created_at` or `confirmed_at`.
The list is the navigation hub.

**Empty Journal.** When no Decisions exist, show a prompt: "Record your first
investment decision."

**New Draft.** A form with `title` (required) and all optional text fields.
The form uses explicit Save (no autosave). Save sends PATCH with
`expected_revision`.

**Draft editor.** Opens an existing Draft. Shows all text fields with their
current values. Explicit Save button. The editor tracks text dirty state
(semantic comparison against the last saved snapshot). Save is disabled when
the Draft is clean.

**Revision conflict.** On 409 response, show a dialog: "This decision has been
updated. Reload to see the latest version?" Reload fetches the latest Draft
and replaces the editor state. If the editor is dirty, require explicit
confirmation before discarding local edits.

**Dirty-state reload protection.** If the user has unsaved edits and a reload
is triggered (by conflict, navigation, or manual refresh), show a confirmation
dialog before discarding local edits.

**Confirm review.** A read-only review of the saved Draft snapshot. Shows all
fields, the current Published Policy Version summary, and a confirmation
checkbox with non-advisory copy: "I confirm this decision record. This is a
mechanical record and does not constitute investment advice." Explicit Confirm
button.

**Policy Version context.** The confirm review shows the current Published
Policy Version's key fields (objectives, time_horizon, decision_process) in a
read-only summary. This provides context without evaluation.

**Confirmed immutable detail.** Read-only view of the confirmed snapshot. All
fields are displayed. No edit controls. Shows `confirmed_at` and the Policy
Version number.

**Archive confirmation.** A dialog: "Archive this decision? It will be hidden
from the default list but remain accessible." Optional `archive_reason` text
field. Explicit Archive button.

**Archived filter/view.** A toggle or tab to show/hide archived Decisions in
the list. Archived items are visually distinguished (e.g., muted styling).

**Append Correction.** A form showing the original snapshot fields alongside
editable correction fields. A notice: "The original record will not be
modified. A new correction record will be appended." The `correction_reason`
field is required. Explicit Append button.

**Original view.** Read-only display of the confirmed snapshot as created at
confirm time.

**Effective corrected view.** Display of the latest Correction's full
snapshot. If no Corrections exist, this is identical to the Original view.

**Correction history.** Chronological list of all Corrections, each showing
`correction_number`, `created_at`, `correction_reason`, and the corrected
fields. The "Append Correction" action is available on Confirmed Decisions
and on Archived Decisions.

**Audit timeline.** Chronological list of AuditEvents for this Decision,
showing `action`, `occurred_at`, `sequence_number`, and metadata.

**Independent auxiliary errors.** Correction list, audit timeline, and detail
reads have independent loading and error states. A failure in one auxiliary
read does not hide the successfully loaded primary content.

**Stale-response guards.** AbortController + monotonic generation guards
prevent stale audit or correction list responses from overwriting newer state.
This follows the same pattern established in Slice 2C for Policy history and
audit reads.

### 9.3 UI Copy and Rules

**Provisional non-advisory copy (OD-S3-11).**

The system continues to operate within the local-only, non-production,
no-authentication boundary.

Draft/Confirm flow displays:

> "CompoundOS records information you enter. It does not evaluate whether an
> investment decision is appropriate or suitable. It does not provide
> investment advice, recommendations, or trade instructions."

Before Confirm:

> "Confirming creates an immutable record linked to the current Published
> Investment Policy Version. Future changes require an appended Correction;
> the original record remains unchanged."

Before Correction:

> "Appending a Correction does not replace or delete the original Confirmed
> Decision. The original and every Correction remain visible in the history."

This copy is provisional MVP text. It has not been reviewed by a lawyer.
Production, commercial, or remote use requires legal/compliance review.
No consent persistence or legal conclusion is added.

**UI Rules.**

- Explicit Save for Draft edits. No autosave.
- Explicit Confirm with non-advisory copy. No automatic confirmation.
- No automatic mutation retry.
- Local-only, non-production, no authentication.
- Mutation success and audit refresh failure are separate outcomes.
- Correction append shows explicit notice that the original record is
  preserved.
- No recommendation, scoring, AI, Guardian, Broker, or trading UI elements.

---

## 10. Retention and Deletion Boundaries

The following retention rules are maintained from prior slices:

- Confirmed snapshots must not be hard-deleted.
- Archived Decisions must not be hard-deleted.
- DecisionCorrections must not be hard-deleted.
- AuditEvents must not be hard-deleted.
- Drafts may be explicitly discarded. Discard atomically deletes both the
  Draft row and the decision identity row in the same transaction, only when
  `status = 'draft'` and the Decision has never been Confirmed (OD-S3-13
  Option A). The design prohibits the orphan state where `status = 'draft'`
  exists with no corresponding Draft row. Confirmed, Archived, and Corrected
  decisions must never be hard-deleted.
- Database reset (dropping and recreating all tables) is a development tool,
  not a product deletion feature.
- No export functionality.
- Production retention, compliance deletion, right-to-erasure, and legal hold
  remain deferred.

All deletion, replacement, and restoration semantics are resolved by Project
Owner decisions (OD-S3-1 through OD-S3-15, 2026-07-16).

---

## 11. Blocking Test Matrix

**Status: tests are designed but not created in this planning task.**

### 11.1 Migration Tests

- Fresh upgrade: apply all migrations to an empty database, verify all
  Decision tables, constraints, indexes, functions, and triggers exist.
- Incremental upgrade: apply the new migration on top of the existing
  `0002_investment_policy_foundation`, verify no data loss in Household,
  Policy, or AuditEvent tables.
- Preserve existing data: after migration, verify existing Household, Policy,
  Policy Draft, Policy Version, and AuditEvent rows are unchanged.
- Downgrade and re-upgrade: downgrade the new migration, verify Decision
  tables are removed and Slice 1/2 tables are preserved; re-upgrade and
  verify.
- No `create_all`: the application must not create Decision tables implicitly.
- Constraint inspection: verify all named CHECK, UNIQUE, FK constraints,
  indexes, trigger functions, and triggers exist with expected definitions.

### 11.2 Domain Tests

- Draft cardinality: multiple Drafts per Household, one Draft per Decision.
- Required fields: Draft creation requires non-blank title; confirm requires
  title, decision_summary, rationale, decision_date.
- Unicode length: text field limits enforced at Pydantic and PostgreSQL
  levels using character_length semantics.
- Revision and no-op: stale revision returns 409; identical update returns
  400 (no changes).
- Policy Version ownership: confirm validates the Published Version belongs
  to the Household's Policy.
- Policy Version reference: confirm fails if the Published Version has been
  superseded.
- Confirm atomicity: snapshot creation, Draft deletion, and AuditEvent
  insertion are atomic; failure at any step rolls back everything.
- Immutable Confirmed: direct SQL UPDATE and DELETE on snapshot are rejected
  by trigger.
- Archive transition: only confirmed Decisions can be archived; only archived
  Decisions can be unarchived.
- Append-only Correction: direct SQL UPDATE and DELETE on corrections are
  rejected by trigger.
- Original and effective view: original returns the confirmed snapshot;
  effective returns the latest Correction or the original if none exist.
  The response shape matches §8.7 (`original_snapshot`, `effective_snapshot`,
  `latest_correction_metadata`, `corrections_count`).
- Audit redaction: AuditEvent metadata contains only allowed fields (no
  decision text, no correction text, no Policy text). `correction_count` is
  not present in audit metadata; only `correction_number` (per OD-S3-14).
- Pagination: Decision audit endpoint supports cursor-based pagination with
  `before_sequence_number` and `limit`.
- **Standalone Draft discard**: discard a Draft that has never been Confirmed;
  verify the Draft row and the decision identity row are both deleted in the
  same transaction. Verify the discard AuditEvent retains the stable Decision
  UUID.
- **No orphan Decision identity**: after any discard operation, verify that
  no decision row exists with `status = 'draft'` and no corresponding Draft
  row. This is a direct SQL consistency check.
- **Discard rollback**: a discard transaction that fails partway through
  rolls back completely — Draft row and decision identity are unchanged.
- **FK RESTRICT enforcement**: attempt to delete a decision identity that
  has a Confirmed snapshot, Correction, or AuditEvent referencing it;
  verify the DELETE is rejected by RESTRICT. Attempt to delete a Policy
  Version referenced by a Confirmed snapshot; verify RESTRICT.
- **Direct SQL lifecycle bypass**: attempt direct SQL to set
  `status = 'confirmed'` without a snapshot row, or `status = 'draft'`
  after removing the Draft row, or create a Draft + snapshot simultaneously.
  Verify deferred constraint trigger catches these at commit time.
- **Nullable metadata IS DISTINCT FROM**: verify that lifecycle trigger
  correctly detects changes to nullable fields (e.g., `archived_at`,
  `archive_reason`) using IS DISTINCT FROM, not equality comparison that
  would miss NULL-to-NULL transitions.
- **Cross-Household Policy Version rejection**: attempt to confirm a Decision
  with a `selected_policy_version_id` from a different Household's Policy;
  verify the operation is rejected (by composite FK, trigger, or service
  validation per §6.11).
- **Correction numbering across two Decisions**: append Corrections to two
  different Decisions and verify each Decision's Corrections are numbered
  independently starting from 1 (per-decision sequential).
- **Correction rollback**: a Correction append that fails mid-transaction
  rolls back completely. Verify the correction_number is not committed and
  a retry computes a fresh number under a new lock.
- **Archived Correction eligibility**: verify Correction can be appended to
  an Archived Decision (status = 'archived' is correctable). Verify the
  Correction does not change archived status, archived_at, or archive_reason.
- **Archive/Correction race**: simulate concurrent Archive and Correction;
  verify both can succeed regardless of ordering (both statuses are
  correctable). Verify lock serialization through the decision identity row.
- **Household timeline inclusion**: verify Decision AuditEvents appear in
  the existing Household audit timeline. Verify UI labels and tests safely
  display Decision actions.
- **Decision-filtered audit**: verify the Decision-filtered endpoint
  returns only events for the specified decision_id and respects
  `household_id` ownership.
- **decision_date boundary — Schema/API validation**:
  verify yesterday (allowed), today (allowed), tomorrow (rejected with
  mechanical date validation error), invalid ISO date string (422),
  impossible calendar date such as February 30 (422).
  For Draft: null or missing `decision_date` is permitted.
  For Confirm: null or missing `decision_date` returns a mechanical
  incomplete-field error.
  For Correction: yesterday and today `decision_date` are allowed;
  future `decision_date` is rejected.
- **decision_date boundary — PostgreSQL enforcement**:
  verify Confirmed snapshot and Correction rows both execute
  `decision_date <= CURRENT_DATE` via the named CHECK constraint.
  Direct SQL insertion of a future `decision_date` fails.
  The named CHECK constraint exists on both `decision_confirmed_snapshots`
  and `decision_corrections` tables.
  Timezone does not alter DATE boundary semantics (PostgreSQL DATE type
  is timezone-independent at the storage level).
- **decision_date boundary — UI behavior**:
  verify future `decision_date` displays a neutral technical error message.
  The UI does not send a Confirm or Correction mutation when the date is
  invalid. The date validation is not described as investment advice or
  market timing judgment.

### 11.3 Concurrency Tests

- Concurrent Draft create: two simultaneous creates produce two independent
  Decisions.
- Concurrent Draft update: second update with stale revision returns 409.
- Concurrent Confirm: second confirm returns 409 (decision no longer draft).
- **Confirm/Discard race**: discard winner (atomic identity deletion) causes
  confirm to return 404. Confirm winner causes discard to return 409
  (Decision no longer in draft status).
- Confirm/Policy supersession race: confirm fails with 409 if the Policy
  Version is superseded during the confirm transaction.
- **Archive/Correction race**: verify both proceed without conflict regardless
  of ordering (Archived status is correctable per OD-S3-15 Option A).
- **Concurrent Corrections**: Corrections on the same Decision serialize
  through the Decision row lock and both succeed with distinct per-decision
  numbers. Corrections on different Decisions proceed concurrently.
- **Correction numbering across two Decisions**: verify each Decision's
  Corrections start at 1 and are numbered independently.
- **Correction rollback and session reuse**: a Correction append that fails
  mid-transaction rolls back completely. The database session is reusable
  for subsequent requests without stale state.
- Rollback and session reuse: failed transactions (confirm, discard,
  archive, correction) roll back completely; the database session is
  reusable for subsequent requests.
- **Unrelated IntegrityError**: a CHECK constraint violation on a text field
  is not mapped to 409. Only named constraint violations map to domain
  conflict responses.
- **Lifecycle consistency deferred checks**: verify that deferred constraint
  trigger fires at commit time and catches inconsistent states that bypass
  per-statement triggers (e.g., multi-row UPDATE setting status without
  corresponding snapshot/draft changes).

### 11.4 Frontend Tests

- Dirty confirm gate: Confirm is disabled while the Draft editor has unsaved
  changes.
- Conflict reload protection: 409 response triggers a reload confirmation
  dialog that preserves dirty state.
- Auxiliary read isolation: correction list and audit timeline failures do
  not hide the primary decision detail.
- Stale audit/correction guards: generation + AbortController prevent stale
  responses from overwriting newer state.
- Explicit confirm: the confirm action requires explicit checkbox and button
  click.
- Correction confirmation: appending a Correction requires explicit
  acknowledgment that the original record is preserved.
- Immutable original visibility: the original confirmed snapshot is always
  viewable alongside the effective corrected view.
- No recommendation/AI/trading UI: no elements for recommendation, scoring,
  AI, Guardian, Broker, or trading exist.
- Accessibility: all interactive elements have accessible labels, keyboard
  navigation, and ARIA attributes.
- **Original/effective view consistency**: the UI Original view displays
  `original_snapshot` from the API; the Effective view displays
  `effective_snapshot`. When no Corrections exist, both views show the same
  content. When Corrections exist, the Effective view reflects the latest
  Correction. The UI must not require the client to guess which view is
  active — `latest_correction_metadata` presence disambiguates.
- **List/detail boundary after discard**: verify discarded never-Confirmed
  Decisions do not appear in list or detail (atomic identity deletion leaves
  no record to display).
- **Session reuse after conflict**: after receiving a 409 (stale revision
  or lifecycle conflict), verify the UI can issue a fresh request without
  stale state from the failed attempt.

---

## 12. Resolved Owner Decisions

All items below were **Resolved by Project Owner — 2026-07-16**.

| ID | Decision | Selected | Rejected/Deferred | Status |
|---|---|---|---|---|
| **OD-S3-1** | Draft cardinality | Multiple independent Drafts; each Draft creates independent Decision identity; API uses Decision ID; UI provides Draft list | Singleton Draft per Household | Resolved — 2026-07-16 |
| **OD-S3-2** | Minimum fields and Confirm requirements | Confirm requires: title, decision_summary, rationale, decision_date (trim non-blank, valid date). Other fields optional. Draft allows incomplete. Only presence/type/date/length validation. No amount/position/trade/score fields. | Require all 14 fields | Resolved — 2026-07-16 |
| **OD-S3-3** | Classification and tags | No classification in Slice 3 MVP. No fixed types, no user tags, no system classification, no AI classification. Future classification requires separate approved Sprint. | Fixed categories, user tags | Resolved — 2026-07-16 |
| **OD-S3-4** | Decision date type and rules | DATE type, strict ISO YYYY-MM-DD. Allow today and past dates. **Forbid future decision_date**. created_at and confirmed_at use system TIMESTAMPTZ. User input decision_date must not impersonate system audit time. review_date is optional DATE, may be future, does not trigger notification/Guardian/automated behavior. All date rules are record integrity rules, not investment rules. | Allow future dates, TIMESTAMPTZ | Resolved — 2026-07-16 |
| **OD-S3-5** | Policy Version reference | Confirm only references the current Published Policy Version after locking investment_policies row. No Draft Policy, no Superseded, no arbitrary historical Version. If request carries selected_policy_version_id, it must exactly equal the locked current Published Version ID. Mismatch returns 409. Confirmed snapshot permanently stores that Version reference. Subsequent Policy supersession does not alter Decision reference. Future historical reference requires separate approval. | Any historical Version | Resolved — 2026-07-16 |
| **OD-S3-6** | Confirm semantics | Confirm uses expected_revision + explicit confirmation. Consumes Draft, creates immutable confirmed snapshot. Transaction: lock Policy → re-verify current Published Version → lock Decision → lock Draft → validate revision + required fields → INSERT snapshot → DELETE Draft → UPDATE status to confirmed → INSERT AuditEvent → commit. Rollback on failure. No editable Draft after Confirm. No Confirmed→Draft or reopen. Changes only through DecisionCorrection. | In-place UPDATE | Resolved — 2026-07-16 |
| **OD-S3-7** | Archive and unarchive | Confirmed Decision can Archive. Archive only affects default list visibility, not deletion. Archived remains readable. Unarchive allowed: archived → confirmed. archive_reason optional, max 4000 Unicode chars. archived_at system-generated. Unarchive clears archived_at and archive_reason. Archive and Unarchive each create AuditEvent. Neither modifies Confirmed snapshot or Correction. No Archived→Draft. No hard delete. | No unarchive, permanent archive | Resolved — 2026-07-16 |
| **OD-S3-8** | Correction data model | Full replacement snapshot. Each Correction saves all allowed fields' complete effective values after the Correction. Original Confirmed snapshot never changes. Effective view = latest Correction's full replacement snapshot. No Correction: effective_snapshot = original_snapshot. API returns: original_snapshot, effective_snapshot, latest_correction_metadata, corrections_count (read-time computed). No field patch chain. No explanatory-only model. Correction is append-only, immutable, not deletable. | Field patch, explanatory only | Resolved — 2026-07-16 |
| **OD-S3-9** | Correctable fields and rules | Correctable: title, decision_summary, rationale, alternatives_considered, risks_and_uncertainties, evidence_or_sources, expected_outcome, review_trigger, decision_date, review_date, notes. Not correctable: Decision ID, Household ID, selected_policy_version_id, created_at, confirmed_at, actor, AuditEvent, archive lifecycle metadata, prior Correction records. correction_reason required. Multiple Corrections allowed. Each Correction based on current effective snapshot creating full replacement. No overwrite of old Corrections. No correction-of-correction reference. Original view always visible. Latest Correction = effective view. decision_date correction must follow OD-S3-4 date rules. | Forbid decision_date correction | Resolved — 2026-07-16 |
| **OD-S3-10** | Audit reads and Household timeline | (1) New Decision-filtered audit endpoint: reads only specified Decision's AuditEvents, before_sequence_number cursor, limit default 50 max 100, database selects by DESC returns ASC. (2) Decision AuditEvents enter existing Household timeline — explicitly approved user-visible resource content expansion. Update UI labels/tests in Slice 3 to safely display Decision actions. No change to Policy-filtered audit endpoint. (3) Household timeline full cursor pagination not in Slice 3; existing Backlog preserved. (4) sequence_number is database insertion sequence, not commit order, may have rollback gaps, client cannot set. | Restrict Household timeline, new combined endpoint | Resolved — 2026-07-16 |
| **OD-S3-11** | Provisional UI copy | Local-only, non-production, no-authentication boundary. Three provisional MVP copy texts (Draft/Confirm flow, Confirm notice, Correction notice). Not lawyer-reviewed. Production/commercial/remote use requires legal/compliance review. No consent persistence or legal conclusion added. | Richer educational copy | Resolved — 2026-07-16 |
| **OD-S3-12** | Implementation split | Three independent Slices: 3A (persistence + immutability), 3B (backend workflow + API), 3C (frontend workflow). Each requires separate explicit authorization, independent branch and Draft PR, full CI, independent review, merge after approval. No later Slice starts early. Technical Design merge does not constitute Slice 3A authorization. | Smaller/larger slices | Resolved — 2026-07-16 |
| **OD-S3-13** | Draft discard identity semantics | Option A: Atomic identity deletion for never-Confirmed Draft. Discard only when status=draft and never Confirmed. Same transaction deletes Draft and Decision identity. AuditEvent retains stable Decision UUID (no FK). Confirmed/Archived/snapshot/Correction/AuditEvent never hard-deleted. Discard locks Decision+Draft, checks expected_revision. No discarded/abandoned lifecycle status. No discarded Decision list/detail/restore. Discard wins→Confirm 404. Confirm wins→Discard 409. Unrelated missing ID always 404. DELETE guard trigger allows only status=draft. | Discarded status, orphan identity | Resolved — 2026-07-16 |
| **OD-S3-14** | Correction numbering | Option A: Per-decision sequential. SELECT FOR UPDATE on Decision identity before append. Compute MAX(correction_number)+1 within lock. First Correction = 1. UNIQUE(decision_id, correction_number). Same-Decision concurrent Corrections serialize through Decision row lock. Different-Decision Corrections concurrent. List by correction_number ASC. Latest effective = max correction_number. Failed transaction: number not committed, retry recomputes. AuditEvent may record correction_number but not total count. corrections_count computed at read time only. Not AuditEvent sequence_number, not commit time. | Global IDENTITY, UUID | Resolved — 2026-07-16 |
| **OD-S3-15** | Archived Decision correction eligibility | Option A: Archived Decision still allows appended Correction. Archive only affects default list visibility. Correction trigger allows Decision status confirmed or archived. Archived detail can display Append Correction. Correction does not change archived status, archived_at, or archive_reason. Archive and Correction lock same Decision identity and serialize through it. Correction re-validates status after lock. Future rule change requires separate approval. | Forbidden (must unarchive first), permanently closed | Resolved — 2026-07-16 |

OD-S3-1 through OD-S3-15 are all Resolved by Project Owner — 2026-07-16.

---

## 13. Recommended Implementation Splitting

**Status: proposed, not executed. Each slice requires separate explicit
authorization.**

### 13.1 Slice 3A: Decision Persistence and Immutability

Scope: Alembic migration for Decision tables, SQLAlchemy ORM mappings,
PostgreSQL constraints, immutability triggers, deferred commit checks (if
any), real PostgreSQL migration and trigger tests.

Slice 3A adds no Decision service, API endpoint, or frontend behavior.

### 13.2 Slice 3B: Decision Backend Workflow and API

Scope: Decision service layer (Draft CRUD, confirm, archive, unarchive,
correction), repository queries, Pydantic contracts, API router, AuditEvent
integration, concurrency tests, real PostgreSQL transaction and race tests.

Slice 3B adds no frontend behavior.

### 13.3 Slice 3C: Decision Frontend Workflow

Scope: `/decisions` page, Draft editor, confirm review, confirmed detail,
archive, correction, audit timeline, browser API client, dirty-state
management, conflict handling, auxiliary read isolation.

Slice 3C adds no backend behavior, migration, or dependency changes.

### 13.4 Evaluation

The three-slice split mirrors the proven Slice 2A/2B/2C pattern. Each slice
has a clear boundary and can be independently reviewed. No further splitting
appears necessary, but the owner may request smaller slices if the
implementation complexity warrants it.

**Important:** Merging this Technical Design does **not** constitute Slice 3A
implementation authorization. Each implementation slice requires separate
explicit authorization. Each implementation slice requires independent review
after completion. Slice 3 Implementation remains **Not Authorized**. Slice 3A,
3B, and 3C remain **Not Started**.

---

## 14. Security and Privacy

No authentication or authorization is added. The system remains local-only,
bound to localhost. No sensitive data leaves the local machine.

AuditEvent metadata follows the redaction rules in §5.4. No decision text,
correction text, Policy text, or financial data appears in audit metadata.

No export functionality is provided. Database access is restricted to
localhost connections.

---

## 15. Migration Strategy

### 15.1 Migration Revision

A new Alembic revision `0003_decision_journal` depends on
`0002_investment_policy_foundation`.

### 15.2 New Tables

1. `decisions` — stable decision identity with lifecycle metadata.
2. `decision_drafts` — mutable Draft content (at most one per decision).
3. `decision_confirmed_snapshots` — immutable Confirmed snapshots (at most one
   per decision).
4. `decision_corrections` — append-only Correction records.

### 15.3 Alterations

- `audit_events` — no schema change. Decision events use the existing columns
  with `entity_type = 'Decision'`.

### 15.4 Downgrade

The downgrade drops Decision tables and triggers in reverse order, preserving
all Slice 1 and Slice 2 tables, data, constraints, and triggers.

---

## 16. Dependencies

No new Python or npm dependencies are required for Slice 3. The existing
stack (FastAPI, SQLAlchemy, psycopg, Alembic, Next.js, TypeScript) is
sufficient.

---

## 17. Out of Scope

The following are explicitly out of scope for Slice 3:

- Any form of AI, recommendation, scoring, evaluation, or compliance
- Guardian logic, thresholds, monitoring, alerts, or notifications
- Broker integration, market data, actual holdings, trading
- Authentication, authorization, multi-user, tenancy
- Export, backup, or production retention
- Redis product logic
- Changes to existing Household or Policy behavior
- Changes to existing ADRs or Investment Rulebook
- Changes to Guardian thresholds
- General hard delete of any record type

---

## 18. Document Status

**Approved Technical Design — Implementation Not Authorized**

This document records the approved technical design for the Sprint 002 Slice 3
Decision Journal feature. It was independently reviewed through four review
stages, revised for all findings, and approved for merge.

### 18.1 Review History

1. **Initial Technical Design Review** — REQUEST CHANGES.
   Five MEDIUM findings (M-1 through M-5) and three LOW findings (L-1 through
   L-3). All eight findings addressed in fix revision commit
   `1cecef9ba5cb6f4db06cdf419c41ff5d930c29c6`.

2. **Incremental Technical Design Re-Review** — APPROVE WITH NON-BLOCKING
   FOLLOW-UP. All eight original findings (M-1 through M-5, L-1 through L-3)
   resolved. Two new LOW non-blocking findings recorded: NBF-1 (Correction
   trigger status validation) and NBF-2 (DELETE trigger draft-only guard).
   Both resolved in subsequent Owner Decision integration.

3. **Owner Decision Consistency Review** — APPROVE WITH ONE MEDIUM FINDING.
   14 of 15 Owner Decisions fully consistent across all design sections.
   1 MEDIUM finding (M-1: §8.12 pagination default 20 vs §5.6/OD table
   default 50) and 2 LOW follow-ups (NBF-1: §5.1 action names pending marker;
   NBF-2: §11.2 missing explicit decision_date boundary test). All three
   resolved in fix commit `964bdab27e6ad58421ff27fd0969b13eb87f6e39`.

4. **Final Focused Incremental Re-Review** — APPROVE. M-1, NBF-1, NBF-2 all
   confirmed RESOLVED. Zero new findings. No regressions.

### 18.2 Owner Decisions

OD-S3-1 through OD-S3-15 are all **Resolved — 2026-07-16**. No Open Owner
Decisions remain. Resolved decisions must not be reopened without a separate
approved Sprint.

### 18.3 Implementation Authorization

Merging this technical design into `main` does **not** authorize Slice 3
implementation. Each implementation slice (3A, 3B, 3C) requires separate
explicit authorization by the Project Owner.

- Slice 3 Implementation: **Not Authorized**
- Slice 3A (Decision Persistence and Immutability): **Not Started**
- Slice 3B (Decision Backend Workflow and API): **Not Started**
- Slice 3C (Decision Frontend Workflow): **Not Started**

### 18.4 PR Status

- PR #10: approved for merge
- Technical Design merge does not authorize Slice 3A

---

*End of Sprint 002 Slice 3 Technical Design.*
