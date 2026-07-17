# CompoundOS Sprint 002 Slice 2B Incremental Fix Review

## Final conclusion

**APPROVE WITH NON-BLOCKING FOLLOW-UP**

M-1 and M-2 are resolved. L-1 is partially resolved: omitted bodies, `{}`, non-empty
objects, scalars, and arrays behave as intended, but explicit JSON `null` is accepted
as the default empty request and reaches the create operation. This is a LOW contract
gap, not a data-integrity, privacy, or transaction-safety defect, and is non-blocking
for this local-only slice. It should be corrected in a focused follow-up together with
an API-level regression test and the currently over-broad documentation statement
that all non-object JSON is rejected.

No new findings were identified. The remaining issue is the unresolved portion of
the original L-1 finding.

## Review identity

- Repository: `Lolitadelgadosharona/CompoundOS`
- Pull request: #8 — Sprint 002 Slice 2B: Policy Backend Workflow and API
- PR URL: https://github.com/Lolitadelgadosharona/CompoundOS/pull/8
- Base branch / SHA: `main` / `a90db80cdc446f78c3ce8d10c52ed89daf7af247`
- Head branch: `sprint/002-policy-api`
- Original reviewed HEAD: `26780e2e702cfe1680fab743772b8a6fbc7bf985`
- Current reviewed HEAD: `5adfc3cd878f315be20cbb96721697d0d30ca560`
- Fix commits:
  - `46ff4ef86c9ad416de624760f789d6453a3d0a1b`
  - `5adfc3cd878f315be20cbb96721697d0d30ca560`
- PR state at completion: OPEN, Draft, MERGEABLE
- Tracked/staged state at review start: clean
- Existing untracked review artifacts at review start: 17; SHA-256 recorded

## CI status for current HEAD

All six checks for `5adfc3cd878f315be20cbb96721697d0d30ca560` succeeded.

| Event | Run ID | Job | Job ID | Conclusion |
|---|---:|---|---:|---|
| push | 29382407094 | infrastructure | 87248678457 | SUCCESS |
| push | 29382407094 | backend | 87248678487 | SUCCESS |
| push | 29382407094 | frontend | 87248678467 | SUCCESS |
| pull_request | 29382409179 | infrastructure | 87248684496 | SUCCESS |
| pull_request | 29382409179 | backend | 87248684580 | SUCCESS |
| pull_request | 29382409179 | frontend | 87248684539 | SUCCESS |

Each backend run reported Ruff success, `43 passed, 74 deselected` for the
non-PostgreSQL selection, and `74 passed, 43 deselected, 7 warnings` for the required
real-PostgreSQL selection. No PostgreSQL test was skipped. Each frontend run passed
lint, type-check, 2 Vitest files / 10 tests, Next.js build, and production audit with
zero vulnerabilities. Each infrastructure run passed Compose expansion and the
localhost-only binding check.

## Resolution matrix

| Finding | Resolution | Review conclusion |
|---|---|---|
| M-1 PATCH response race | **RESOLVED** | The locked transaction reads allocations and materializes a complete `PolicyDraftResponse` before commit. Only Pydantic scalar/nested DTO values survive the transaction; the service returns that snapshot after successful commit without a post-commit SELECT, refresh, lazy relationship, or ORM serialization. |
| M-2 blocking test-matrix gaps | **RESOLVED** | The added real-PostgreSQL tests credibly cover the named lifecycle races, replacement and allocation rollback, unrelated integrity failures and session reuse, audit latest-window semantics, all ten text boundaries, exact Decimal totals, and the M-1 response race. |
| L-1 strict empty-body contract | **PARTIALLY RESOLVED** | Omitted body and `{}` return 201; non-empty objects, scalars, and arrays return 422 before persistence; extra fields are forbidden; OpenAPI declares an optional empty-object schema. Explicit JSON `null`, however, is converted to the default model and returns 201. |

## M-1 detailed review

- `update_draft_text` locks Policy then Draft, validates the revision, mutates text,
  flushes the update and audit event, and reads allocations before leaving
  `session.begin()`.
- Snapshot construction enumerates `PolicyDraftResponse.model_fields`, reads Draft
  scalar values while the transaction is live, converts each allocation to an
  `AllocationResponse`, and validates the complete response DTO before commit.
- The returned object contains UUID, datetime, integer, string, and nested Pydantic
  values only. It retains no SQLAlchemy entity, `InstrumentedList`, lazy relationship,
  or expired attribute.
- A commit failure exits by exception and cannot return the success snapshot.
- Router serialization occurs after the service transaction and operates only on the
  Pydantic response. `expire_on_commit=False` is not needed to make the response work.
- Revision, text, allocation content, and sort order are therefore taken from one
  transaction snapshot.

The deterministic test uses a dedicated Session/connection for the PATCH and another
Session/connection for the allocation replacement. An `after_commit` listener blocks
the service thread after the database commit but before service return. The competing
transaction then completes a different allocation replacement. A `do_orm_execute`
listener records SELECTs in the post-commit window. The test asserts the old atomic
snapshot, the later database revision, and zero post-commit SELECTs. The old
implementation would deterministically issue the recorded SELECT and return the later
allocation collection. Both waits and the Future use ten-second timeouts, the release
event is set in `finally`, and both listeners are removed, so the test neither relies
on sleep/probability nor leaves a production hook or persistent listener.

## L-1 detailed review

The new `EmptyPolicyCreateRequest` correctly uses `extra="forbid"`. The route's
`Body(default_factory=EmptyPolicyCreateRequest)` makes the OpenAPI request body
optional and references the empty-object schema. API tests prove that a non-empty
object, string, number, and array return 422 without Policy/Draft creation and without
echoing `secret-marker`; omitted bodies and `{}` retain 201 behavior.

A read-only TestClient probe with the database dependency and create operation replaced
by inert local fakes produced these results:

| JSON body | Status | Create operation called |
|---|---:|---|
| omitted | 201 | yes |
| `{}` | 201 | yes |
| `null` | 201 | yes |
| non-empty object | 422 | no |
| scalar | 422 | no |
| array | 422 | no |

Pydantic itself rejects `EmptyPolicyCreateRequest.model_validate(None)`, but FastAPI
applies the body default before model validation when the decoded value is `null`.
Consequently the schema-level `None` assertion does not cover the actual endpoint.
This does not alter the existing 201/404/409 behavior or accept client fields, but it
does not meet the approved strict empty-object boundary. Because `null` carries no
accepted user data and is operationally equivalent to omission, the residual LOW
issue is classified as non-blocking.

## M-2 test-matrix credibility

### Concurrency and lifecycle races

- Concurrent new-Draft creation starts two independent Sessions at one barrier, catches
  only the expected lifecycle exception, and proves one winner, one loser, one Draft,
  copied allocations, and the expected audit count.
- Discard/new-Draft and publish/new-Draft use the same production lock order and permit
  exactly the two valid linearizations. Final Draft/allocation/version/current-Published
  counts and event counts reject partial states, orphan allocations, duplicate Drafts,
  mixed snapshots, and spurious lifecycle outcomes.
- The PATCH response-race test is deterministic as described under M-1.

### Rollback and error behavior

- Replacement-publish injection raises while adding `policy.published`, after the old
  Version has been temporarily superseded, its event flushed, the new Version and
  allocation snapshot created and sealed, and the Draft deletion flushed. Assertions
  prove rollback restores the prior Published row and `superseded_at`, retains the
  Draft and allocations, removes the attempted new snapshot and both attempted events,
  and leaves the Session reusable.
- Allocation replacement injection deletes and flushes the old collection, then causes
  a real PostgreSQL constraint `IntegrityError`. Assertions prove the old collection,
  revision, and audit history return, and a later legal replacement succeeds after the
  scoped monkeypatch is removed.
- The unrelated integrity test violates a foreign key unrelated to the approved named
  lifecycle constraints. It proves the exception is not mapped to 409, the transaction
  rolls back, the Session can perform a later successful create, and the API returns a
  generic redacted 500 without the marker.

### Audit, text, and totals

- The audit test inserts more than 100 matching rows, creates a permitted sequence gap,
  mixes wrong entity types and wrong Policy IDs, compares the API to an independent
  descending database selection, and proves default 50 / maximum 100 are returned
  ascending within the latest window. Older rows are absent; 0, -1, and 101 return 422;
  no assertion assumes contiguous sequence values.
- All ten Policy text fields are parameterized at their individual maximums and one
  character beyond, using Unicode characters and surrounding whitespace. Both schema
  and real-PostgreSQL API paths are covered. Blank Draft text remains allowed, and
  publication is proven with only the three approved fields populated.
- `99.99` and `50.00 + 50.01` save as Draft data but fail publication without consuming
  the Draft or adding a Version/event. `33.33 + 33.33 + 33.34` succeeds. Payloads remain
  decimal strings and application arithmetic uses `Decimal`.

The parametrization adds useful cases without obscuring field identity or creating
unnecessary transaction loops beyond the required real-database boundary coverage.

## Second fix commit

`5adfc3c test: compare restored draft UUID consistently` changes one test assertion
only: the ORM UUID is converted to its canonical string before comparison with the API
JSON Draft ID. The assertion still checks exact identity and would fail for `NULL`, a
different UUID, or an absent/duplicate Draft; the same test independently verifies
revision and the complete restored allocation business content. No product code,
documentation, migration, dependency, Compose, CI, or environment file changed in
this commit.

## Regression and scope review

- Full incremental diff: 9 files, 709 insertions, 7 deletions before the one-line test
  correction; no migration, frontend, dependency, Compose, CI, or environment change.
- Migrations 0001 and 0002 are unchanged.
- Existing Policy API behavior is not otherwise refactored.
- Alembic `path_separator = os` remains a Backlog-only maintenance item.
- Documentation accurately says the changes await incremental review and PR #8 remains
  Draft. The only inaccurate statement is the L-1 claim that all non-object JSON is
  rejected, because explicit `null` is accepted.
- No Slice 2C, Slice 3, frontend Policy flow, AI, Guardian, Broker, recommendation,
  trading, authentication, or unapproved investment-rule behavior was introduced.

## New findings

| Severity | Count |
|---|---:|
| BLOCKER | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 0 new; one residual portion of original L-1 |
| NON-BLOCKING | 0 new |

Known non-blocking items remain full Docker/browser runtime validation and seven
Alembic `path_separator` deprecation warnings.

## Exact validation commands and results

Commands executed during this incremental review included:

```text
git status --short --branch
git branch --show-current
git rev-parse HEAD origin/main origin/sprint/002-policy-api
git remote -v
gh pr view 8 --json number,title,state,isDraft,mergeable,baseRefName,headRefName,headRefOid,url,statusCheckRollup
git log --oneline --decorate -5
git diff --stat 26780e2...5adfc3c
git diff --name-status 26780e2...5adfc3c
git diff --check 26780e2...5adfc3c
git diff --binary 26780e2...5adfc3c
git show --stat --oneline 46ff4ef
git show --stat --oneline 5adfc3c
git diff 46ff4ef 5adfc3c
cmp sprint-002-slice2b-fix-review.diff <(git diff --binary 26780e2...5adfc3c)
.venv/bin/pip check
.venv/bin/ruff check apps/api tests/api
.venv/bin/python -m compileall -q apps/api
.venv/bin/python -m pytest --collect-only -q
.venv/bin/python -m pytest -m 'not postgres' -q
.venv/bin/alembic heads
.venv/bin/alembic history
.venv/bin/alembic upgrade head --sql | wc -l
npm run lint
npm run type-check
npm test -- --run
npm run build
npm audit --omit=dev
python YAML safe-load of .github/workflows/ci.yml and compose.yaml
gh run list --branch sprint/002-policy-api --limit 10 --json ...
gh run view 29382409179 --json ...
gh run view 29382407094 --json ...
gh run view 29382409179 --log
gh run view 29382407094 --log
read-only TestClient body-contract probe
SHA-256 verification of all review artifacts
```

Results:

- `git diff --check`: passed.
- Existing fix diff byte comparison: exact match.
- `pip check`: `No broken requirements found.`
- Ruff: `All checks passed!`
- Python compileall: passed.
- Pytest collection: 117 tests.
- Local non-PostgreSQL suite: 43 passed, 74 deselected.
- Local real PostgreSQL suite: not run; `TEST_DATABASE_URL` is unset.
- Current-head CI real PostgreSQL suite: 74 passed, 43 deselected, 0 skipped,
  7 known Alembic warnings, on both push and pull_request runs.
- Alembic: `0002_investment_policy_foundation (head)`; expected 0001 → 0002
  history; offline upgrade generated 336 SQL lines successfully.
- Frontend ESLint: passed with zero errors/warnings.
- TypeScript: passed with zero errors.
- Vitest: 2 files and 10 tests passed.
- Next.js production build: passed.
- `npm audit --omit=dev`: 0 vulnerabilities.
- CI and Compose YAML parsing: passed.
- Local Docker CLI / Compose runtime: unavailable.
- Common credential-pattern scan: no matches in scoped project files.
- GitHub Actions: all six current-head jobs succeeded.

The local Next.js process emitted a warning that the inherited environment has
`NODE_TLS_REJECT_UNAUTHORIZED=0`. This variable was not added or changed by the PR;
the build and audit still completed successfully.

## Unverified items

- Full local Docker runtime and browser-path behavior: Docker CLI is unavailable.
- Local real-PostgreSQL execution: no local `TEST_DATABASE_URL` is configured; both
  current-head GitHub backend runs executed all 74 PostgreSQL-selected tests with zero
  skips.
- No remote/public deployment, authentication, authorization, production security,
  or compliance behavior was reviewed because those remain explicitly outside scope.

## Artifact integrity and final state

- `sprint-002-slice2b-fix-review.diff` remained byte-identical to the requested
  `26780e2...5adfc3c` binary diff.
- All 17 pre-existing untracked review artifacts remained unmodified and untracked.
- This report is the only newly created file and remains untracked.
- Tracked and staged diffs remain empty.
- PR #8 remains OPEN, Draft, MERGEABLE, and unmerged.
- Slice 2C and Slice 3 remain unauthorized and were not started.
