# CompoundOS Sprint 002 Slice 2A — Independent Read-Only Review

## Final conclusion

**APPROVE WITH NON-BLOCKING FOLLOW-UP**

No BLOCKER, HIGH, MEDIUM, or LOW implementation defect was found. The approved
Slice 2A persistence boundary is implemented consistently and the database
immutability invariants are enforced by PostgreSQL rather than relying only on
future application code. Two non-blocking follow-ups are recorded below.

## Review identity and repository state

- Repository: `Lolitadelgadosharona/CompoundOS`
- Pull request: #7 — `Sprint 002 Slice 2A: Policy Persistence Foundation`
- PR URL: https://github.com/Lolitadelgadosharona/CompoundOS/pull/7
- PR state at final verification: OPEN, Draft, MERGEABLE
- Base branch: `main`
- Base SHA: `60be3ed979ccde85dc0ed88ff2a942cccdbc4540`
- Head branch: `sprint/002-policy-persistence`
- Head SHA: `8894b0cc0abf2f1a430399739f062f861ebdd77c`
- Initial tracked/staged state: clean
- Initial untracked state: the ten pre-existing review artifacts listed in the
  final status section; none was modified, staged, committed, or deleted.

## GitHub Actions status

All six checks for the reviewed head SHA completed successfully.

### Push run `29314697291`

| Job | Job ID | Conclusion | Material result |
|---|---:|---|---|
| backend | `87025932752` | SUCCESS | Alembic head installed; Ruff passed; non-PostgreSQL `12 passed, 36 deselected`; real PostgreSQL `36 passed, 12 deselected, 7 warnings` |
| infrastructure | `87025932755` | SUCCESS | Compose config and localhost-only binding checks passed |
| frontend | `87025932778` | SUCCESS | lint/type-check passed; Vitest 2 files and 10 tests passed; build passed; audit found 0 vulnerabilities |

### Pull-request run `29314698714`

| Job | Job ID | Conclusion |
|---|---:|---|
| infrastructure | `87025936871` | SUCCESS |
| frontend | `87025936931` | SUCCESS |
| backend | `87025936942` | SUCCESS |

## Scope summary

The diff contains 14 files, 1,615 insertions, and 20 deletions. It adds one
Alembic revision, five approved Policy persistence tables, matching SQLAlchemy
models, AuditEvent insertion sequencing, PostgreSQL immutability functions and
triggers, real-PostgreSQL tests, and documentation updates. It does not add a
Policy use case, write repository, router, endpoint, Policy request contract, or
frontend workflow.

## Findings

### BLOCKER

None.

### HIGH

None.

### MEDIUM

None.

### LOW

None.

### NON-BLOCKING

#### NB-1 — Database regression assertions can cover more of the already-correct schema and trigger matrix

- Files/locations: `tests/api/test_policy_persistence.py:177-242`,
  `tests/api/test_policy_persistence.py:245-474`
- Evidence: schema inspection verifies named check constraints, foreign keys,
  the principal Policy/Draft/version unique constraints, function names, and
  trigger names. Functional tests verify the central trigger transitions.
  However, the test suite does not independently inspect every allocation unique
  constraint/index predicate, nor directly exercise combined seal-plus-content
  mutation, repeated superseded mutation, or a multi-row forbidden statement.
- Impact: this is a regression-detection gap, not a demonstrated implementation
  defect. The migration and ORM definitions were inspected and match; the row-level
  trigger SQL rejects these paths through `IS NOT DISTINCT FROM` comparisons and
  unconditional allocation UPDATE/DELETE rejection.
- Suggested follow-up: extend real-PostgreSQL tests to inspect every named
  allocation unique/index definition and add direct-SQL cases for the combined,
  repeated, and multi-row paths. This can be done without changing product scope.

#### NB-2 — Alembic emits an existing `path_separator` deprecation warning

- File/location: `alembic.ini` configuration consumed by
  `tests/test_policy_migrations.py:29-148`
- Evidence: the real PostgreSQL CI suite passed with seven identical warnings:
  `No path_separator found in configuration; falling back to legacy splitting...`.
- Impact: no current correctness failure; Alembic upgrade, downgrade, and
  re-upgrade all succeeded. A future Alembic release may remove the legacy
  fallback.
- Suggested follow-up: add the supported `path_separator = os` configuration in
  a separately reviewed maintenance change and confirm offline plus PostgreSQL
  migration tests remain green.

## Migration safety review

- `down_revision` is exactly `0001_household_persistence`.
- The merged `0001` migration is unchanged by the PR.
- The migration is transactional under PostgreSQL. A failed DDL step rolls back
  instead of leaving a partially installed Slice 2A schema.
- The Alembic version column is widened from 32 to 64 before Alembic writes the
  descriptive revision ID. Retaining width 64 during downgrade is intentional:
  Alembic must first replace the long 0002 value with the shorter 0001 value.
- Incremental migration preserves HouseholdProfile and AuditEvent rows. Existing
  AuditEvents receive non-null identity values; subsequent values advance beyond
  them. The identity is `GENERATED ALWAYS`, so ordinary application/client inserts
  cannot supply it.
- Downgrade drops triggers before functions and child tables before parent tables,
  then removes the new AuditEvent index, unique constraint, and identity column,
  and restores the original Slice 1 audit index.
- The migration necessarily takes strong PostgreSQL locks while altering
  `audit_events` and adding/backfilling the identity column. That is acceptable for
  the approved local-only MVP; production migration planning remains outside this
  Slice.
- No application path calls `create_all`.

## Migration/ORM parity conclusion

**PASS.** Manual column-by-column comparison found the migration and SQLAlchemy
models aligned for SQL types, nullability, UUID foreign keys, deletion behavior,
server defaults, named checks/uniques, indexes, partial current-published index,
`NUMERIC(5,2)`, positive revision/version/order rules, status/timestamp rules,
provenance FK, and `AuditEvent.sequence_number` identity mapping.

The Policy ORM classes are internal persistence models only. No Pydantic request
model exposes their IDs, normalized names, status, sealing timestamps, version
numbers, or sequence numbers for client control. `AuditEventResponse` exposes
`sequence_number` only as response metadata; direct explicit database insertion
is rejected by `GENERATED ALWAYS`.

## Cardinality and conflict identity

- One Policy per Household: named `uq_investment_policies_household_id`.
- One Draft per Policy: named `uq_investment_policy_drafts_policy_id`.
- One current Published version per Policy: named partial unique index
  `uq_investment_policy_versions_current_published`.
- Version number per Policy: named
  `uq_investment_policy_versions_policy_version`.
- Allocation canonical name and sort order: named unique constraints on both
  Draft and Version allocation tables.

These names are specific enough for later code to map only expected conflicts;
Slice 2A correctly contains no conflict-to-HTTP mapping or service workflow.

## Trigger invariant matrix

| Invariant | SQL behavior | Review result |
|---|---|---|
| Version INSERT completeness | Requires positive version, `published`, non-null `published_at`, all ten text values, null `sealed_at`, and null `superseded_at`; table constraints handle remaining non-null/FK rules | PASS |
| Seal transition | When old row is unsealed, only `sealed_at NULL -> non-NULL` is accepted; every other compared column must be `IS NOT DISTINCT FROM` its old value | PASS |
| Seal plus content mutation | Row comparison includes IDs, policy, version, status, every text field, and lifecycle timestamps | REJECTED as required |
| Published supersession | Only sealed `published -> superseded` with `superseded_at NULL -> non-NULL`; every other field, including `sealed_at`, must remain identical | PASS |
| Superseded update/reverse/repeat | No branch permits update when old status is `superseded` | REJECTED as required |
| Version DELETE | DELETE branch always raises `policy_version_delete_forbidden`, sealed or unsealed | REJECTED as required |
| Allocation INSERT | Parent Version must be visible and unsealed | PASS before seal; rejected after seal |
| Allocation UPDATE/DELETE | Unconditionally raises stable operation-specific errors | REJECTED as required |
| Commit with unsealed Version | Initially deferred constraint trigger queries final transaction-visible state and raises `policy_version_unsealed_at_commit` if any row remains unsealed | REJECTED as required |
| Same-transaction insert then seal | Both deferred events observe the final sealed row, so a completed transaction is not falsely rejected | PASS |
| Failed publish cleanup | Version deletion is forbidden; PostgreSQL transaction rollback removes the attempted snapshot and children | PASS |
| Multi-row mutation | BEFORE trigger is `FOR EACH ROW`; one forbidden row aborts the statement/transaction | PASS by SQL semantics |

Stable trigger errors use SQLSTATE `55000` for forbidden object-state operations
and `23514` for invalid insert/unsealed-at-commit checks, with distinct stable
message identifiers.

## AuditEvent sequence review

- It is documented and implemented only as a unique, monotonically allocated
  PostgreSQL insertion sequence.
- It is not described as concurrent transaction commit order or complete causal
  ordering.
- Rollback gaps are documented and tested.
- The Household audit repository orders `sequence_number ASC`.
- Existing responses gain additive read-only sequence metadata; request schemas
  do not accept it.
- Tests compare insertion order and explicitly demonstrate a rollback gap; they
  do not assume continuity or equate the sequence with commit time.

## Test credibility and coverage gaps

- Required PostgreSQL mode fails rather than skips when `TEST_DATABASE_URL` is
  absent; CI sets `COMPOUNDOS_REQUIRE_POSTGRES_TESTS=1`.
- CI uses a real PostgreSQL 16 service and completed all 36 PostgreSQL-marked
  tests with zero skips.
- Fresh, incremental, downgrade, and re-upgrade paths use Alembic against the real
  database and preserve seeded Slice 1 data.
- Trigger tests commit where the deferred constraint must fire and roll back after
  expected failures; subsequent queries demonstrate session/connection reuse.
- The Alembic revision-width regression test inspects the actual version column
  and would catch the original `VARCHAR(32)` failure.
- The function/trigger implementation is tested behaviorally, not only by string
  matching. NB-1 records the remaining assertion-strength opportunities.

## Scope exclusion confirmation

Confirmed absent from the diff:

- Policy service or business workflow
- Policy repository write flow
- Policy API/router or Policy Pydantic request contract
- frontend `/policy`
- publish orchestration or allocation editor
- Decision Journal or Slice 3 implementation
- AI, Guardian, Broker, recommendation, scoring, eligibility, or trading logic
- authentication, multi-household tenancy, holdings, accounts, or market data
- new investment rules or Guardian thresholds

Slice 2A remains in Review. Slice 2B, Slice 2C, and Slice 3 remain unauthorized.

## Documentation consistency

`MASTER_PLAN`, `CHANGELOG`, `ARCHITECTURE`, `PRD`, ADR 0003, and the technical
design accurately describe the implemented persistence-only boundary. They do
not claim a complete Policy product workflow or production readiness. Existing
Backlog items, including Docker/browser runtime validation and AuditEvent
pagination, remain present.

## Exact validation commands and results

- `git diff --check origin/main...origin/sprint/002-policy-persistence` — PASS.
- `.venv/bin/ruff check apps tests` — `All checks passed!`.
- `.venv/bin/ruff check migrations/versions/0002_investment_policy_foundation.py` — `All checks passed!`.
- `.venv/bin/pytest -q -m 'not postgres'` — `12 passed, 36 deselected in 0.04s`.
- `.venv/bin/pytest -q -m postgres -ra` — locally `36 skipped, 12 deselected` because no `TEST_DATABASE_URL`; CI real PostgreSQL gate passed all 36.
- `npm --prefix frontend run lint` — PASS, zero warnings/errors.
- `npm --prefix frontend run type-check` — PASS.
- `npm --prefix frontend test` — 2 test files and 10 tests passed.
- `npm --prefix frontend run build` — PASS; Next.js 16.2.10 production build compiled successfully.
- `npm --prefix frontend audit --omit=dev` — 0 vulnerabilities.
- `.venv/bin/alembic heads` — `0002_investment_policy_foundation (head)`.
- `.venv/bin/alembic history` — base -> 0001 -> 0002 history is linear and correct.
- `.venv/bin/alembic upgrade head --sql` — PASS, generated 336 lines.
- `.venv/bin/alembic downgrade 0002_investment_policy_foundation:base --sql` — PASS, generated 60 lines.
- `gh pr view 7 ...`, `gh run view ...`, and `gh pr checks 7` — read-only metadata/log inspection; all six checks successful.

## Unverified items

- The local machine has no Docker CLI, so full Docker runtime/browser-path
  validation was not repeated. GitHub validated Compose configuration and host
  bindings, not the full application runtime stack.
- The local machine has no configured PostgreSQL test database. Real PostgreSQL
  behavior was verified by both successful GitHub workflow events rather than a
  second local database execution.
- The local environment sets `NODE_TLS_REJECT_UNAUTHORIZED=0`, producing a Node
  warning during build/audit. This was not introduced by the repository diff and
  no repository file was changed to suppress it.

## Read-only artifact statement

This report, `sprint-002-slice2a-review.diff`, and
`sprint-002-slice2a-critical-files.txt` are local untracked review artifacts only.
No tracked project file, branch, commit, remote, PR state, or merge state was
changed during this review.
