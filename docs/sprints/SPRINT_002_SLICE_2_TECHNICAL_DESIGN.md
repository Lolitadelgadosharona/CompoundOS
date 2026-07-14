# Sprint 002 Slice 2 Technical Design: Investment Policy Foundation

## Status

**Proposed — Implementation Not Authorized**

- Design date: 2026-07-14
- Baseline: Sprint 002 Slice 1 at merge commit
  `a06ebb917570672cb38c01fb7defad4c62ed5605`
- Purpose: define a reviewable Policy-only implementation specification
- This document creates no schema, migration, endpoint, UI, dependency, or product
  behavior. Project-owner approval is required before implementation.

## 1. Scope and boundaries

### Proposed Slice 2 scope

- One stable `InvestmentPolicy` for the sole existing `HouseholdProfile`.
- At most one editable `InvestmentPolicyDraft` for that Policy.
- Ten user-authored free-text policy categories.
- Structured user-authored target asset allocation percentages.
- Atomic publication into an immutable `InvestmentPolicyVersion` snapshot.
- `Published` and `Superseded` version history.
- Policy lifecycle `AuditEvent` records with non-sensitive metadata.
- One minimal local-only `/policy` workflow.

### Explicit non-goals

- Decision Journal, DecisionCorrection, or Slice 3.
- AI, AI Investment Committee, generation, summarization, scoring, or agents.
- Guardian logic, thresholds, monitoring, alerts, or escalation.
- Brokers, market data, actual holdings, accounts, balances, amounts, prices,
  performance, drift, or rebalancing calculations.
- Recommendations, default allocations, templates, suitability conclusions,
  compliance judgments, policy evaluation, or rule execution.
- Trading, order preparation, or execution.
- Authentication, authorization, multiple households, multiple users, or tenancy.
- Export, general hard delete, public deployment, or production-readiness claims.

Policy category names are neutral recordkeeping structure. Their presence does not
make them system-authored investment rules, and their contents are never parsed
into Guardian thresholds or trading instructions.

## 2. Policy and Draft cardinality

### Stable Policy identity

The recommended model permits each `HouseholdProfile` to own at most one stable
`InvestmentPolicy`. The Policy row contains identity and timestamps, not mutable
policy content. Drafts and immutable Versions belong to that identity.

PostgreSQL enforces cardinality with:

- a non-null `investment_policies.household_id` foreign key;
- `UNIQUE (household_id)` on `investment_policies`;
- no endpoint for a second Policy, Policy replacement, or Policy deletion; and
- named-constraint handling that converts only the Policy singleton race to 409.

Two concurrent create requests may both pass a pre-read, but only one can satisfy
the unique constraint. The winner creates the stable Policy and initial Draft;
the loser rolls back its entire transaction and receives 409.

### Draft cardinality comparison

| Option | Benefits | Costs and risks | Recommendation |
|---|---|---|---|
| A. One editable Draft per Policy | Smallest state model; no branch selection or merge; clear UI; simple locking | User must finish or discard the current Draft before starting another | **Recommended** |
| B. Multiple parallel Drafts | Supports experiments and collaboration | Requires names, ownership, selection, merge/conflict semantics, and more audit/UI states | Reject for this Slice |

`UNIQUE (policy_id)` on `investment_policy_drafts` enforces Option A. Creating a
Draft when one exists returns 409, including concurrent attempts. A new Draft may
be blank or copied from the current Published version. Draft existence represents
the `Editable` lifecycle state; no Draft status column is needed.

Initial Policy creation should create both the stable Policy and a blank Draft in
one transaction and emit `policy.created` and `policy.draft.created`. If either
write or either audit event fails, no Policy remains.

## 3. Policy fields and technical limits

Only the following user-authored free-text fields are proposed:

| Field | Proposed maximum characters | Rationale |
|---|---:|---|
| `objectives` | 4,000 | Allows several goals without unbounded payloads |
| `time_horizon` | 2,000 | Matches the existing household horizon safety limit |
| `liquidity` | 4,000 | Allows detailed context without structured amounts |
| `diversification` | 4,000 | User statement only; no evaluation |
| `contribution_policy` | 4,000 | Allows a descriptive process without monetary modeling |
| `rebalancing_policy` | 4,000 | Records user wording without calculating rebalancing |
| `prohibited_assets` | 4,000 | Free text only; not an eligibility engine |
| `leverage_policy` | 4,000 | Free text only; not a Guardian threshold |
| `decision_process` | 4,000 | Allows a documented owner process |
| `notes` | 8,000 | Provides bounded supplementary context |

API validation strips leading/trailing whitespace, rejects undeclared fields,
and measures Unicode characters rather than encoded bytes. Named PostgreSQL
`char_length` checks independently enforce the same maxima. Draft values may be
empty while work is incomplete. The publish-time minimum-content rule remains a
blocking owner decision in Section 16.

The UI and API must not offer suggested text, recommended values, generated
content, “good/bad” judgments, or an indication that a category complies with a
long-term plan. These limits are input-safety limits, not investment rules.

## 4. Target Asset Allocation

### Data and normalization

Each allocation item contains only:

- `asset_class_name`: user-authored display text, proposed 1–200 characters after
  trimming; and
- `target_percentage`: an exact decimal value.

No default asset class, recommended percentage, actual holding, drift value, or
rebalancing result exists.

Before validation, the application computes a canonical comparison key by:

1. applying Unicode NFKC normalization;
2. trimming leading and trailing Unicode whitespace;
3. collapsing every internal Unicode whitespace run to one ASCII space; and
4. applying Unicode case folding.

The original normalized display name and the canonical key are stored separately.
Named unique constraints on `(draft_id, normalized_asset_class_name)` and
`(version_id, normalized_asset_class_name)` reject names such as `Cash`, ` cash `,
and `CASH` in the same collection. The service is the canonical-key producer;
PostgreSQL enforces uniqueness of the stored key without requiring a locale- or
extension-dependent case-insensitive type. Tests must cover ASCII and Unicode
space/case examples.

### Draft and publish validation

- A Draft may have no allocation items.
- A Draft may have items whose total is not 100%; this is visibly “incomplete,”
  not “invalid investment policy.”
- Each saved item must already have a non-empty unique name and percentage greater
  than 0 and no greater than 100. Draft incompleteness is represented by missing
  items or a non-100 total, not zero/negative placeholders.
- Publish requires at least one item and an exact total of `100.0000` (displayed as
  100%). This is a record-completeness check, not endorsement of the allocation.
- The sum is performed by PostgreSQL `NUMERIC`/Python `Decimal`, never binary float.

### Precision comparison

| Type | User experience | Exact total | Future flexibility | Assessment |
|---|---|---|---|---|
| `NUMERIC(5,2)` | Familiar hundredths; simpler display | Exact `100.00` | Cannot preserve basis-point fractions below 0.01% | Adequate but restrictive |
| `NUMERIC(7,4)` | Allows up to four decimal places; UI can omit trailing zeros | Exact `100.0000` | Preserves finer user-entered targets without schema change | **Recommended** |

The recommendation is `NUMERIC(7,4)` with checks `target_percentage > 0` and
`target_percentage <= 100`. It accepts values such as `12.3456` while exact
decimal arithmetic still makes the publication total deterministic. The UI must
state the accepted precision and must not silently round. Approval of this choice
is a blocking decision.

### Collection mutation comparison

| API style | Benefits | Risks |
|---|---|---|
| Independent item CRUD endpoints | Small payloads; individual item identity | More requests, partial-save UX, more race paths, item ordering complexity |
| Atomic collection replacement | One Draft revision, simple editor state, duplicate and total checks together, easy rollback | Sends the complete small collection on each explicit save |

Atomic collection replacement is recommended for the MVP. One `PUT` validates
the entire collection, obtains the Draft lock, compares the expected revision,
replaces Draft allocation rows, increments the Draft revision once, and emits one
`policy.draft.updated` event. It is not autosave. A byte-for-byte/semantic no-op
returns 400 and emits no event.

## 5. Lifecycle and publication transaction

### Editable Draft

- Draft content is editable only through explicit saves.
- Each real text or allocation save increments `revision` and creates one
  `policy.draft.updated` AuditEvent in the same transaction.
- Empty and semantic no-op saves return 400, do not increment `revision`, and do
  not emit an AuditEvent.
- A Draft may be discarded. Discard deletes Draft allocation rows and the Draft,
  emits `policy.draft.discarded` atomically, and leaves the stable Policy and all
  Versions intact.
- A discarded Draft is not formal version history.

### Published and Superseded Versions

- Publication creates a new immutable Version snapshot; it never converts the
  Draft row in place.
- A Version's content and allocation snapshot are immutable after sealing.
- The only permitted lifecycle transition is `Published → Superseded`.
- Superseded content remains immutable and cannot be physically deleted.
- Changes require a new Draft and a new Version number.

### Atomic publish algorithm

Within one synchronous SQLAlchemy service transaction at PostgreSQL `READ
COMMITTED`:

1. Lock the stable Policy row with `SELECT ... FOR UPDATE`.
2. Lock the Draft row and verify `expected_revision`; stale input returns 409.
3. Validate publish-time free-text completeness once approved.
4. Read and validate the locked Draft allocation collection: at least one item,
   unique normalized names, each `(0, 100]`, and exact sum `100.0000`.
5. Compute `version_number = max(existing version_number) + 1` while the Policy
   lock serializes competing publishers.
6. If a current Published version exists, change only its status to Superseded and
   set `superseded_at`; emit `policy.superseded`. This occurs before inserting the
   replacement so the partial unique current-Published index remains satisfied.
7. Insert an unsealed internal Version row and copy all policy fields.
8. Insert the complete immutable allocation snapshot.
9. Seal the new Version inside the transaction.
10. Delete the consumed Draft and Draft allocations.
11. Emit `policy.published` with only non-sensitive metadata.
12. Commit all changes together.

Any failure rolls back the new Version, snapshot, previous-version status change,
Draft consumption, and AuditEvents. The API returns the new immutable Version with
201 only after commit.

## 6. Immutability options

| Option | Protection | Migration/testing impact | Assessment |
|---|---|---|---|
| A. Service/repository checks only | Protects approved application paths | Simple, but defects or direct SQL can rewrite history | Insufficient alone |
| B. PostgreSQL triggers | Database rejects forbidden updates/deletes regardless of application path | Requires functions, trigger ordering, rollback and downgrade tests | **Recommended** |
| C. Separate database roles/permissions | Strong operational boundary | Requires credential/role lifecycle not present in local MVP | Defer to production hardening |
| D. Append-only schema structure | Separates Drafts from snapshots and avoids normal update paths | Does not by itself prevent direct UPDATE/DELETE/late child INSERT | Useful structure, insufficient alone |

The minimum credible local-MVP recommendation is **Option B applied to the
append-only Version structure**:

- a Version is inserted internally with `sealed_at = NULL` only inside publish;
- allocation INSERT is permitted only while its parent Version is unsealed;
- allocation UPDATE and DELETE always raise;
- publish sets `sealed_at` before commit;
- a deferred constraint trigger rejects any transaction that would commit an
  unsealed Version;
- after sealing, a Version trigger rejects DELETE and every UPDATE except the
  exact `Published → Superseded` status transition plus `superseded_at`;
- all policy text, identity, version number, publication time, and sealing time
  must remain unchanged during supersession; and
- Version allocation rows cannot be added after sealing.

The internal unsealed interval is not a product lifecycle state and is never
visible outside the atomic transaction. Trigger functions should raise named,
stable SQLSTATE/error messages that tests can distinguish from ordinary unique or
validation failures.

Migration impact: the new revision creates tables first, then functions, then
triggers. Downgrade drops triggers before functions and tables. Tests must attempt
direct SQL/ORM mutation, deletion, late allocation insertion, and an unsealed
commit. This design is more work than service-only checks but is narrowly focused
on the stated immutable-history guarantee.

## 7. Proposed tables (design only)

No table in this section exists until a separate implementation approval.

### `investment_policies`

- `id UUID PRIMARY KEY`, server/application generated.
- `household_id UUID NOT NULL REFERENCES household_profiles(id) ON DELETE RESTRICT`.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` for Draft lifecycle metadata
  only; no policy content is stored here.
- `UNIQUE (household_id)` named `uq_investment_policies_household_id`.
- Index on `household_id` is supplied by the unique constraint.

### `investment_policy_versions`

- `id UUID PRIMARY KEY`.
- `policy_id UUID NOT NULL REFERENCES investment_policies(id) ON DELETE RESTRICT`.
- `version_number INTEGER NOT NULL CHECK (version_number > 0)`.
- `status TEXT NOT NULL CHECK (status IN ('published', 'superseded'))`; constrained
  text is preferred over a PostgreSQL enum for simpler migration evolution.
- The ten policy text columns, all non-null with named `char_length` checks.
- `published_at TIMESTAMPTZ` and internal `sealed_at TIMESTAMPTZ`; both must be
  non-null by deferred commit-time enforcement.
- `superseded_at TIMESTAMPTZ NULL`, with a check requiring null for Published and
  non-null for Superseded.
- `UNIQUE (policy_id, version_number)`.
- Partial unique index on `policy_id WHERE status = 'published'` so at most one
  current Published version exists.
- Index `(policy_id, version_number DESC)` for history.
- Trigger-enforced immutable content and no physical delete after sealing.

Versions are created before Drafts in the migration so a Draft may safely hold an
optional source-Version foreign key without a table-creation cycle.

### `investment_policy_drafts`

- `id UUID PRIMARY KEY`.
- `policy_id UUID NOT NULL REFERENCES investment_policies(id) ON DELETE RESTRICT`.
- `source_version_id UUID NULL REFERENCES investment_policy_versions(id) ON DELETE RESTRICT`.
- `revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0)` for optimistic concurrency.
- The ten non-null policy text columns with named maximum-length checks; empty
  strings are permitted while editable.
- `created_at` and `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `UNIQUE (policy_id)` enforces one editable Draft.
- Index on `source_version_id` for provenance lookup.

### `investment_policy_draft_allocations`

- `id UUID PRIMARY KEY`.
- `draft_id UUID NOT NULL REFERENCES investment_policy_drafts(id) ON DELETE CASCADE`.
- `asset_class_name TEXT NOT NULL` with `char_length BETWEEN 1 AND 200`.
- `normalized_asset_class_name TEXT NOT NULL` with the same bound.
- `target_percentage NUMERIC(7,4) NOT NULL CHECK (> 0 AND <= 100)`.
- `sort_order INTEGER NOT NULL CHECK (sort_order >= 0)`.
- `UNIQUE (draft_id, normalized_asset_class_name)`.
- `UNIQUE (draft_id, sort_order)`.
- Index on `draft_id`; Draft discard intentionally cascades to these editable rows.

### `investment_policy_version_allocations`

- `id UUID PRIMARY KEY`.
- `version_id UUID NOT NULL REFERENCES investment_policy_versions(id) ON DELETE RESTRICT`.
- The same name, normalized-name, percentage, and order columns/checks as Draft
  allocations.
- `UNIQUE (version_id, normalized_asset_class_name)`.
- `UNIQUE (version_id, sort_order)`.
- Index `(version_id, sort_order)` for stable snapshot display.
- Trigger-enforced insert-only-during-unsealed-publish and no UPDATE/DELETE.

No Journal, Guardian, AI, Broker, Account, Holding, User, or tenancy table is
proposed.

## 8. AuditEvent expansion

Proposed action names:

- `policy.created`
- `policy.draft.created`
- `policy.draft.updated`
- `policy.draft.discarded`
- `policy.published`
- `policy.superseded`

All actions retain actor `local-owner`, use the existing household foreign key,
and use stable `InvestmentPolicy` identity as `entity_type`/`entity_id`. Metadata
may contain only:

- sorted changed field names;
- Draft revision;
- source version number;
- published or superseded version number; and
- allocation item count.

Metadata must not contain full policy text, asset-class names, percentages, or the
complete allocation collection. Audit insertion belongs to the same transaction
as the business mutation. No audit event is written for validation failure, stale
409, or no-op save.

### Audit read comparison

| Choice | Benefits | Risks |
|---|---|---|
| Expand the existing Household timeline | One chronological stream | Mixes profile and Policy semantics; requires immediate UI label changes; harder focused review |
| Add a Policy-filtered read | Keeps Slice 1 behavior stable; focused Policy history; simple entity filter | Two endpoints can show overlapping household history later |

Recommend retaining the Slice 1 HouseholdProfile audit contract and adding a
Policy-filtered endpoint. The repository query should filter by household,
`entity_type = 'InvestmentPolicy'`, and stable Policy ID, ordered by
`occurred_at, id`. Any future combined household-wide activity feed requires its
own pagination and presentation decision.

## 9. Proposed API contracts (not implemented)

All request models forbid extra fields and all responses omit internal normalized
keys, trigger/sealing mechanics, and recommendation-like fields.

| Method and path | Request | Success | Error behavior and transaction |
|---|---|---|---|
| `POST /api/policies` | Empty body | `201` stable Policy plus initial blank Draft | `404` no Household; `409` Policy exists/race. Policy, Draft, and two audit events are atomic. |
| `GET /api/policies/current` | None | `200` Policy metadata | `404` no Policy. Read-only. |
| `GET /api/policies/current/draft` | None | `200` Draft, revision, fields, allocations | `404` no Policy or Draft. Read-only. |
| `PATCH /api/policies/current/draft` | `expected_revision` plus any proposed text fields | `200` updated Draft | `400` empty/no-op; `404` missing; `409` stale/lifecycle; `422` shape/length. Update and audit are atomic. |
| `PUT /api/policies/current/draft/allocations` | `expected_revision`, complete ordered `items` collection | `200` updated Draft snapshot | `400` semantic no-op; `404` missing; `409` stale/publish race; `422` duplicate/invalid item. Replacement and audit are atomic. |
| `POST /api/policies/current/draft/discard` | `expected_revision` | `204` | `404` missing; `409` stale/publish race. Draft deletion and audit are atomic. |
| `POST /api/policies/current/draft` | Optional `source_version_number`; omit for blank | `201` Draft | `404` Policy/source missing; `409` Draft exists or source lifecycle conflict; `422` invalid request. Copy and audit are atomic. |
| `POST /api/policies/current/draft/publish` | `expected_revision`, `confirmation: true` | `201` immutable Version snapshot | `400` incomplete text/allocation total; `404` missing; `409` stale/already consumed/concurrent lifecycle; `422` malformed input. Entire publish algorithm is one transaction. |
| `GET /api/policies/current/published` | None | `200` current Published Version and allocation snapshot | `404` no current Published version. Read-only. |
| `GET /api/policies/current/versions` | Optional `before_version_number`; `limit` defaults 20, maximum 100 | `200` version metadata newest first plus next cursor | `404` no Policy; `422` invalid pagination. Read-only. |
| `GET /api/policies/current/versions/{version_number}` | Positive integer path value | `200` immutable Version and allocation snapshot | `404` missing; `422` malformed number. Read-only. |
| `GET /api/policies/current/audit-events` | Optional opaque `(occurred_at, id)` cursor; `limit` defaults 50, maximum 100 | `200` policy events in stable order plus next cursor | `404` no Policy; `422` invalid pagination. Read-only. |

Status principles:

- `201` means a new Policy, Draft, or immutable Version was committed.
- `200` means retrieval or a real Draft mutation succeeded.
- `204` is used only for successful Draft discard.
- `400` means the structurally valid request cannot perform work, such as no-op or
  publication incompleteness.
- `404` means the addressed prerequisite/resource does not exist.
- `409` means cardinality, lifecycle, stale revision, or concurrency conflict.
- `422` means request shape, type, precision, name normalization, or technical
  safety validation failed.

No endpoint returns a recommendation, evaluation, score, suitability statement,
compliance status, allocation comparison, or trade action.

## 10. Minimal frontend flow

One route, `/policy`, is proposed with these states:

1. **Missing Household:** explain the prerequisite and link to `/household`.
2. **Empty Policy:** state that no Policy exists and offer “Create policy draft.”
3. **Draft editor:** ten plain free-text fields, explicit Save, revision-conflict
   messaging, and Discard Draft.
4. **Allocation editor:** add/remove/reorder local rows, exact decimal inputs, one
   explicit atomic Save, current sum display, and neutral completeness text.
5. **Publish review/confirmation:** read-only Draft snapshot, exact total, required
   confirmation, and the approved non-advisory copy immediately before publish.
6. **Current Published version:** immutable label, publication/version metadata,
   policy text and allocation snapshot, plus “Create new Draft” rather than edit.
7. **Version history:** Published/Superseded metadata and immutable detail views.
8. **Policy audit timeline:** policy-filtered events and independent retry behavior
   consistent with the Slice 1 audit failure UX.

The UI must state:

- every percentage and asset-class name was entered by the user;
- the 100% check verifies record completeness only and is not system approval;
- Published and Superseded Versions cannot be edited;
- changes require a new Draft; and
- the application is local-only, has no authentication, and must not be publicly exposed.

Immediately before publish, display exactly:

> CompoundOS records information you enter. It does not evaluate whether an
> investment policy or decision is suitable, appropriate, or likely to succeed.
> Policy links and validations are for recordkeeping only and do not constitute
> investment, tax, or legal advice.

No recommendation button, AI generation, template picker, risk score, compliance
badge, buy/sell language, or actual-versus-target view is designed.

## 11. Concurrency design

The recommended minimum combination is:

- named unique constraints for Policy, Draft, current Published version, version
  number, and normalized allocation names;
- optimistic `revision` on editable Draft mutations;
- `SELECT ... FOR UPDATE` on Policy and Draft during publish and on Draft during
  allocation replacement/discard; and
- PostgreSQL `READ COMMITTED`, relying on explicit locks rather than a broader
  isolation level that would add retry complexity.

| Race | Enforcement | Expected losing response |
|---|---|---|
| Two requests create Policy | `UNIQUE (household_id)`; atomic Policy/Draft/audit transaction | `409 Policy already exists` |
| Two requests create Draft | `UNIQUE (policy_id)` | `409 Draft already exists` |
| Two requests publish one Draft | Both lock Policy then Draft in the same order; first consumes Draft | `409 Draft already published or changed` |
| Stale Draft text update | Conditional revision check/increment | `409 Draft revision is stale` |
| Version-number competition | Policy row lock serializes `max + 1`; unique constraint is final guard | `409` if invariant guard is reached |
| Allocation replace vs publish | Both lock Draft and require expected revision; publish snapshots only after lock | Stale operation receives `409`, never partial snapshot |

Lock order is always Policy then Draft when both are needed, preventing inversion.
Expected conflicts are translated only from named constraints or explicit
revision/lifecycle checks; unrelated `IntegrityError` instances must propagate.

## 12. Blocking test matrix

### Migration and schema

- Upgrade an existing database from `0001_household_persistence` to the proposed
  new revision while preserving HouseholdProfile and AuditEvent rows.
- Upgrade a fresh PostgreSQL database from base to head.
- Verify exactly the five proposed product tables, constraints, indexes, trigger
  functions, and triggers are added; no prohibited table appears.
- Development downgrade from the new revision to 0001 drops triggers/functions in
  safe order and leaves Slice 1 tables/data intact.
- Confirm the application still never calls `create_all`.

### Cardinality, Draft, and allocation

- Policy singleton under sequential and concurrent creation.
- Draft singleton under sequential and concurrent creation.
- Initial Policy + Draft + AuditEvents atomic rollback.
- Draft text save increments revision and audits changed field names only.
- Empty/no-op text and allocation saves return 400 with no revision/event.
- Every free-text maximum is enforced by Pydantic and named PostgreSQL checks.
- Decimal parsing rejects float artifacts, excess scale, zero, negative, and >100.
- Unicode name normalization and duplicate canonical-name rejection.
- Draft totals below/above 100 may save; publish rejects them.
- Publish requires at least one item and exact `100.0000`.

### Publication, immutability, and concurrency

- First publish creates Version 1 and consumes Draft atomically.
- Later publish creates the next number and supersedes exactly one prior Published version.
- Failure at each publish step rolls back Version, snapshot, supersession, Draft
  deletion, and AuditEvents.
- Direct UPDATE/DELETE of sealed Version content fails.
- Direct UPDATE/DELETE or late INSERT of Version allocations fails.
- A transaction cannot commit an unsealed Version.
- `Published → Superseded` succeeds once; every reverse/other transition fails.
- Two simultaneous publishes yield one success and one 409.
- Stale text/allocation/discard/publish operations return 409.
- Allocation replacement racing publish cannot create a mixed snapshot.

### Audit, API, UI, and regressions

- All six Policy audit action types, stable ordering, actor `local-owner`, and
  atomic business-write behavior.
- Audit metadata contains only allowed keys and never policy text, class names,
  percentages, or complete allocations.
- All proposed 200/201/204/400/404/409/422 contracts and sensitive-input redaction.
- `/policy` empty, Draft, allocation, publish-confirmation, current version,
  history, and audit states.
- Non-advisory copy appears at Policy flow entry and immediately before publish.
- UI contains no recommendation, template, AI, Guardian, score, compliance,
  trading, holdings, or actual-versus-target surface.
- Real PostgreSQL CI runs with zero skipped PostgreSQL tests.
- Existing Slice 1 API, transaction, frontend, health, lint, type-check, build,
  audit, Compose, and localhost-binding tests remain green.

## 13. Security and privacy

- Policy fields are sensitive user-authored planning data. They must not enter
  application logs, exception messages, validation responses, or Audit metadata.
- Allocation names/percentages are returned only through Policy contracts and are
  not copied into Audit metadata.
- Validation errors report locations and neutral messages without echoing full input.
- CORS remains limited to existing localhost origins; no origin or method expands
  until the specific Policy routes are implemented and reviewed.
- Web, API, PostgreSQL, and Redis host ports remain bound to `127.0.0.1`.
- There is no authentication. Localhost binding is not access control; remote or
  shared deployment remains prohibited.
- Development reset may clear all local data. It is not a product delete feature.
- No export, Policy/Version hard-delete API, backup feature, or encryption claim is added.
- Published/Superseded history and AuditEvents are retained for the local MVP.
- This design does not claim production security, privacy, compliance, fiduciary,
  or advisory readiness.

## 14. Migration strategy

- Proposed revision ID: `0002_investment_policy_foundation`.
- `down_revision` must be `0001_household_persistence`.
- The merged 0001 revision is immutable and must not be edited.
- Upgrade order: Policy table → Version table → Draft table → Draft allocations →
  Version allocations → indexes → trigger functions → triggers.
- Trigger functions use schema-qualified table references where appropriate and
  stable names suitable for inspection tests.
- Downgrade order: drop triggers → drop trigger functions → drop allocation tables
  → drop Draft table → drop Version table → drop Policy table.
- The downgrade is development support, not a production rollback promise; it
  necessarily removes Slice 2 Policy data while preserving Slice 1 tables.
- CI must test both fresh `alembic upgrade head` and incremental
  `upgrade 0001`, seed Slice 1 data, then `upgrade head`.
- A downgrade test must verify return to 0001 and successful re-upgrade.
- No application startup path calls `create_all`.

No migration is created by this design gate.

## 15. Acceptance criteria and Definition of Done

### Proposed acceptance criteria

- The sole Household can create at most one stable Policy and one editable Draft.
- Policy and initial Draft creation is atomic with non-sensitive AuditEvents.
- Draft text and allocation saves are explicit, revisioned, atomic, and no-op safe.
- Draft allocation may be incomplete, while publication requires at least one
  unique item and exact 100% using approved decimal precision.
- Publication atomically produces an immutable snapshot, supersedes the prior
  Published version, consumes the Draft, and creates allowed AuditEvents.
- Published and Superseded content cannot be updated or physically deleted,
  including through direct database writes.
- Version history and Policy audit reads are stable and expose no internal sealing
  or normalized-name fields.
- The `/policy` flow covers empty, Draft, publish review, Published, history, and
  audit states with local-only and non-advisory notices.
- APIs/UI provide no recommendation, evaluation, score, rule result, Guardian/AI
  output, broker/market/holding data, rebalancing calculation, or trade behavior.
- Concurrency and stale operations return deterministic 409 responses without
  partial writes.
- Existing Slice 1 behavior remains unchanged and its regression suite passes.

### Proposed Definition of Done

- This technical design and its blocking decisions receive explicit owner approval.
- A new 0002 migration, models, strict schemas, repositories, service transaction
  boundaries, API contracts, and minimal UI are implemented only after approval.
- Fresh and incremental migrations, downgrade, constraints, triggers, lifecycle,
  immutability, concurrency, rollback, privacy, API, and frontend tests pass.
- Real PostgreSQL CI executes the Policy integration suite with zero skips.
- Ruff, frontend lint, TypeScript, Vitest, Next.js build, npm audit, Compose config,
  and localhost-binding checks pass.
- Required PRD, Architecture, ADR, README, Changelog, Master Plan, API, privacy,
  and test documentation is current.
- Independent code review approves the implementation.
- Docker runtime/browser validation is run when available; otherwise the gap is
  accurately disclosed and retained as a follow-up.
- Sprint 002 remains In Progress until separately completed.
- Slice 3 remains unauthorized.

## 16. Open decisions requiring project-owner approval

These decisions block implementation. Approving the planning PR alone does not
implicitly approve them unless the approval explicitly adopts the recommendations.

| ID | Decision | Recommended answer | Alternatives | Impact | Blocks implementation |
|---|---|---|---|---|---|
| OD-1 | Publish-time free-text completeness | Require all ten approved categories to contain user-entered non-whitespace text; Drafts may remain incomplete | Require a smaller named subset, or allow empty categories at publish | Changes publish validation, UI checklist, and tests; it must not assess semantic quality | Yes |
| OD-2 | Percentage precision | `NUMERIC(7,4)` with exact `100.0000` publication sum | `NUMERIC(5,2)` with exact `100.00` | Fixes storage/API precision and rounding UX | Yes |
| OD-3 | Database immutability | PostgreSQL triggers with an internal unsealed publish interval and deferred sealing check | Service-only; permissions; append-only structure without triggers | Determines migration functions/triggers, direct-write guarantees, and downgrade tests | Yes |
| OD-4 | Allocation mutation contract | Atomic whole-collection replacement with expected Draft revision | Independent item CRUD endpoints | Determines API shape, editor save behavior, audit granularity, and race surface | Yes |
| OD-5 | Policy audit read | Preserve the Slice 1 profile audit contract and add Policy-filtered read | Expand one household-wide mixed timeline | Determines repository filters, UI labels, and later pagination path | Yes |
| OD-6 | New Draft source | Blank or current Published Version only; reject Superseded source with 409 | Allow any immutable historical Version as source | Changes provenance contract and history UX | Yes |

Non-blocking for this local-only design but blocking before any remote/production
use: jurisdiction/legal review, authentication and authorization, production
retention/export/deletion, backup, encryption, and final legal copy.

## Design gate conclusion

This document is ready for technical review as a proposal. It does not authorize
implementation, does not start Slice 2, and grants no authority for Slice 3.
