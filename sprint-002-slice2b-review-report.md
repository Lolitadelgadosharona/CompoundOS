# CompoundOS Sprint 002 Slice 2B Independent Review

## Final conclusion

**REQUEST CHANGES**

The implementation is narrowly scoped and its core transaction, locking, normalization, immutable publication, ownership filtering, and audit-redaction approach largely matches the approved design. However, two MEDIUM findings remain: one concrete post-commit response race and one material gap against the approved blocking test matrix. Under the review rules, either MEDIUM finding requires REQUEST CHANGES.

## Review identity

- Repository: `Lolitadelgadosharona/CompoundOS`
- Pull request: #8 — Sprint 002 Slice 2B: Policy Backend Workflow and API
- PR URL: https://github.com/Lolitadelgadosharona/CompoundOS/pull/8
- Base branch: `main`
- Base SHA: `a90db80cdc446f78c3ce8d10c52ed89daf7af247`
- Head branch: `sprint/002-policy-api`
- Head SHA: `26780e2e702cfe1680fab743772b8a6fbc7bf985`
- PR state at review: OPEN, Draft, MERGEABLE
- Tracked/staged state at review start: clean
- Existing untracked review files at review start: 13; hashes recorded before review

## CI status

All checks for the reviewed head completed successfully.

| Event | Run ID | Job | Job ID | Conclusion |
|---|---:|---|---:|---|
| push | 29330491438 | infrastructure | 87076987602 | SUCCESS |
| push | 29330491438 | backend | 87076987645 | SUCCESS |
| push | 29330491438 | frontend | 87076987627 | SUCCESS |
| pull_request | 29330493605 | infrastructure | 87076995104 | SUCCESS |
| pull_request | 29330493605 | backend | 87076995181 | SUCCESS |
| pull_request | 29330493605 | frontend | 87076995055 | SUCCESS |

For each backend run, Ruff passed, the non-PostgreSQL suite reported `26 passed, 47 deselected`, and the required real PostgreSQL suite reported `47 passed, 26 deselected, 7 warnings`. The PostgreSQL suite had zero skips. Each frontend run passed lint, type-check, 2 Vitest files/10 tests, Next.js build, and production audit with zero vulnerabilities. Infrastructure validated Compose configuration and localhost-only host bindings.

## Scope summary

The diff adds only the approved Slice 2B backend Policy schemas, repository, service, router, tests, ADR, and documentation. It does not change migrations, dependencies, Compose, CI, environment configuration, or frontend product code.

Confirmed absent:

- Policy frontend or frontend API client
- Slice 2C, Slice 3, Decision Journal, or DecisionCorrection
- AI, AI Agent, AI Investment Committee, Guardian, Broker, market data, or Redis product behavior
- recommendations, suitability, eligibility, scores, rankings, or investment-rule execution
- trading, holdings, accounts, quantities, balances, or monetary amounts
- authentication, authorization, public deployment, or multi-household behavior
- changes to migrations 0001/0002 or new migrations
- dependency, Compose, or workflow changes
- unapproved investment rules or Guardian thresholds

CORS adds only the required `PUT` method and retains the two localhost origins, no credentials, and the existing limited headers.

## Actual endpoint contract

| Method/path | Actual request | Actual success response | Actual errors / notes | Design parity |
|---|---|---|---|---|
| POST `/api/policies` | No declared request model; body is ignored by FastAPI | 201, Policy plus initial blank Draft | 404 missing Household; 409 singleton conflict | Partial: success/lifecycle match, but strict empty-body contract is not enforced (L-1) |
| GET `/api/policies/current` | None | 200 Policy metadata | 404 missing Household/Policy | Match |
| GET `/api/policies/current/draft` | None | 200 Draft, revision, text, allocations | 404 missing Policy/Draft | Match |
| PATCH `/api/policies/current/draft` | `expected_revision` plus supplied text fields; extras/null rejected | 200 Draft snapshot | 400 empty/no-op; 404 missing; 409 stale/lifecycle; 422 contract/length | Contract matches; response snapshot has M-1 race |
| PUT `/api/policies/current/draft/allocations` | `expected_revision`, complete ordered `items`; percentage strings only | 200 Draft snapshot | 400 no-op; 404 missing; 409 stale/lifecycle; 422 shape/duplicate/precision/range | Match |
| POST `/api/policies/current/draft/discard` | `expected_revision` | 204 empty response | 404 missing; 409 stale/lifecycle; 422 malformed | Match |
| POST `/api/policies/current/draft` | Optional current-Published `source_version_id`; omitted body means blank | 201 Draft with provenance | 404 Policy missing; 409 Draft exists or invalid source lifecycle; 422 malformed/extra | Match |
| POST `/api/policies/current/draft/publish` | `expected_revision`, literal `confirmation: true` | 201 immutable Version snapshot | 400 incomplete text/allocation; 404 missing Policy; 409 stale/consumed/conflict; 422 malformed | Match |
| GET `/api/policies/current/published` | None | 200 current Published Version | 404 none | Match |
| GET `/api/policies/current/versions` | `before_version_number >= 1`; `limit` default 20, max 100 | 200 newest-first summaries and next cursor | 404 Policy missing; 422 invalid pagination | Match |
| GET `/api/policies/current/versions/{version_number}` | Positive integer path | 200 immutable Version detail | 404 absent; 422 malformed/non-positive | Match |
| GET `/api/policies/current/audit-events` | `limit` default 50, range 1–100, no cursor | 200 latest-N window returned sequence ascending | 404 Policy missing; 422 invalid limit | Match |

Fixed routes are registered before `/current/versions/{version_number}`, so the dynamic route does not swallow `/current/versions`, `/current/published`, `/current/draft`, or `/current/audit-events`.

Responses omit `normalized_asset_class_name` and `sealed_at`. Unrelated database exceptions are re-raised rather than converted to successful or expected business responses. FastAPI's validation handler emits locations/messages/types without request input values.

## Findings

### BLOCKER

None.

### HIGH

None.

### MEDIUM

#### M-1 — PATCH response can combine a committed old Draft revision with allocations from a later transaction

- File/location: `apps/api/services/policies.py:176-201`
- Evidence: `update_draft_text` ends its locked transaction at line 200, then calls `list_draft_allocations(session, draft.id)` at line 201. That query starts after the Policy/Draft locks and mutation transaction have been released.
- Impact: a concurrent allocation replacement, publish, or discard can commit between those points. The PATCH response can therefore contain the earlier cached Draft/revision together with later allocation rows or an empty allocation list. This violates the endpoint's updated-Draft snapshot semantics and can give a future client a response that never existed atomically.
- Suggested fix: load and retain the Draft allocations while still inside the Policy-then-Draft locked transaction, commit, then serialize those retained values. Add an independent-session barrier test proving the response cannot mix transactions. Do not keep the transaction open through HTTP serialization.

#### M-2 — Required blocking transaction and boundary coverage is materially incomplete

- File/location: `tests/api/test_policy_api.py:90-432`, `tests/api/test_policy_schemas.py:18-95`
- Evidence: the new tests cover core happy paths, concurrent Policy creation, concurrent publish, allocation/publish race, first-publish rollback, basic normalization, decimal rejection, and audit redaction. They do not cover several items explicitly listed in section 12, “Blocking test matrix,” of the approved technical design.
- Material missing coverage includes:
  - concurrent new-Draft creation and discard/new-Draft/publish lifecycle races;
  - replacement-publish failure after superseding an existing Published Version, proving rollback of supersession, new snapshot, Draft deletion, and both events;
  - database-stage allocation replacement failure preserving the prior collection;
  - unrelated `IntegrityError` propagation plus post-rollback session reuse;
  - Policy audit latest-50/max-100 window behavior and proof that older events are currently inaccessible;
  - all Policy text boundary/Unicode character-length contracts;
  - publication totals below and above exactly 100.00;
  - the post-commit PATCH response race in M-1;
  - strict rejection of a non-empty Policy-create body.
- Impact: CI success does not yet substantiate several transaction, concurrency, rollback, redaction-window, and strict-contract guarantees that the approved design made merge-blocking. Regressions in these areas could pass the current suite.
- Suggested fix: add focused real-PostgreSQL tests with independent sessions and deterministic synchronization for races; add failure injection at the named transaction stages; add small schema/API boundary parametrizations. Keep changes within Slice 2B.

### LOW

#### L-1 — Policy creation does not enforce its empty request contract

- File/location: `apps/api/routers/policies.py:99-108`
- Evidence: `create` declares only the session dependency and no body model. OpenAPI reports `requestBody=False`. FastAPI therefore does not validate a supplied JSON body for this operation, while the approved table specifies an empty body and the design requires strict request models with undeclared fields rejected.
- Impact: clients can send arbitrary ignored fields and still create the Policy, which weakens the strict API boundary and can mislead clients into believing supplied data was accepted.
- Suggested fix: add a strict empty request model with `extra="forbid"`, while preserving the intended ability to omit the body, and test that non-empty JSON returns 422 without echoing values.

### NON-BLOCKING

#### NB-1 — Full local Docker runtime/browser validation remains unavailable

- Evidence: Docker CLI is not installed in the review environment. GitHub infrastructure checks validate Compose expansion and localhost bindings, but do not replace a full local container/browser path.
- Status: known Backlog item; non-blocking for this local-only Slice.

#### NB-2 — Seven Alembic deprecation warnings remain

- Evidence: all seven CI warnings come from the migration test repeatedly loading Alembic without `path_separator = os`.
- Status: exactly matches the existing independent-maintenance Backlog item; no new warning source was found.

## Transaction and locking matrix

| Mutation | Transaction owner | Lock/order | Business + audit atomic | Review |
|---|---|---|---|---|
| Policy create | service `session.begin()` | No Policy row exists; named household uniqueness resolves race | Policy, Draft, two events in one transaction | Correct |
| Draft text PATCH | service | Policy FOR UPDATE → Draft FOR UPDATE | revision/text + one event | Write is correct; returned allocations are queried after commit (M-1) |
| Allocation PUT | service | Policy FOR UPDATE → Draft FOR UPDATE | delete/insert collection, revision + event | Correct; request normalized before lock, revision rechecked after lock |
| Draft discard | service | Policy FOR UPDATE → Draft FOR UPDATE | Draft/children deletion + event | Correct |
| New Draft | service | Policy FOR UPDATE; absence checked under Policy lock; named unique guard | Draft/copy + event | Correct |
| Publish | service | Policy FOR UPDATE → Draft FOR UPDATE | supersession, events, snapshot, seal, Draft consumption | Correct by inspection; replacement rollback coverage incomplete |
| Reads | request-scoped session | No row locks | Read-only | Ownership filters correct; PATCH response follow-up read is not merely a read endpoint and causes M-1 |

Repository functions flush but do not commit. Services own commits and rollback. All mutations touching Policy and Draft use a consistent Policy-before-Draft order. Concurrent tests use separate SQLAlchemy Sessions/connections rather than serial calls.

## Publish algorithm review

The implementation follows the approved order:

1. lock current Policy;
2. lock Draft and validate revision;
3. require the three approved non-whitespace text fields;
4. require at least one allocation and exact Decimal 100.00;
5. calculate next version while holding Policy lock;
6. supersede current Published and write `policy.superseded`;
7. insert an unsealed complete Version;
8. insert allocation snapshot;
9. seal Version;
10. delete consumed Draft;
11. write `policy.published`;
12. commit once.

The two audit events are flushed in transaction order and receive ascending insertion sequence numbers within that transaction. No code treats sequence number as commit time or complete cross-transaction causality. Failures use transaction rollback rather than explicit Version deletion. Database triggers from Slice 2A remain unchanged.

## Error mapping matrix

| Condition | Domain handling | HTTP |
|---|---|---:|
| No Household / Policy / Draft / Published / Version | specific not-found exceptions | 404 |
| Empty PATCH, semantic no-op | `NoPolicyChangesError` | 400 |
| Publication text/allocation incomplete | `PolicyIncompleteError` | 400 |
| Policy or Draft singleton | explicit/named-constraint conflict | 409 |
| Stale revision, consumed Draft, invalid source lifecycle | `DraftConflictError` | 409 |
| Request shape/type/extra/length/decimal/name/query/path | Pydantic/FastAPI validation | 422 |
| Named current-Published or version-number invariant conflict | mapped after rollback | 409 |
| Unrelated `IntegrityError` or runtime failure | re-raised | 500/generic server behavior |

SQL constraint messages are not directly placed into HTTP detail. The global request-validation handler excludes input values. Unhandled server exceptions may still be present in server-side framework logs; dynamic log-redaction behavior was not exercised locally.

## Decimal-string and normalization review

Confirmed:

- JSON numbers, Python numeric objects, null, NaN, negative values, zero, and values above 100 are rejected.
- Scientific notation, signs, trailing decimal points, and more than two decimal places are rejected by the full-match grammar.
- Decimal parsing uses `Decimal`, not float, and responses format two decimal places.
- Leading/trailing zeros are accepted as decimal strings and canonicalized to two decimal places.
- NFKC occurs before Unicode whitespace trimming/collapse; internal whitespace runs become one ASCII space.
- Display value and casefolded canonical key are separate.
- Client input cannot set canonical names, IDs, ordering, audit actor, or sequence number.
- Duplicate canonical names return 422 before mutation.
- Copying current Published creates new allocation UUIDs while preserving business content and order.
- Publish performs only mechanical presence and exact-total checks; there is no advisory or semantic-quality logic.

## Audit metadata and redaction review

All Policy events use actor `local-owner`, entity type `InvestmentPolicy`, stable Policy ID, and the current household ID. Emitted metadata uses only:

- `changed_fields`
- `draft_revision`
- `source_version_number`
- `version_number`
- `allocation_item_count`

No Policy text, allocation name, percentage, normalized name, recommendation, score, or complete allocation is written by the reviewed paths. The Policy audit read filters household ID, entity type, and current Policy ID. It selects latest N by descending sequence and reverses the selected window to ascending order. The Household audit endpoint/resource boundary is unchanged by this diff.

## API/design parity conclusion

Core API, decimal, normalization, lifecycle, locking, publication, immutability, audit, ownership filtering, pagination, and local-only scope align with the approved design. Exceptions are the concrete PATCH response race (M-1), incomplete blocking evidence (M-2), and non-empty create-body acceptance (L-1).

## Test credibility and coverage gaps

Credible coverage:

- schema-level decimal-string and Unicode normalization checks;
- real PostgreSQL API and repository operations;
- independent-session concurrent Policy create and publish;
- independent-session allocation/publish race;
- atomic first-publish failure injection;
- copied allocation UUID separation after the initial CI assertion correction;
- real PostgreSQL CI gate with zero skips;
- existing Slice 2A trigger/migration suite.

The allocation UUID correction changes only test comparison semantics. It compares display name, percentage, and sort order while separately requiring source/copy UUID sets to be disjoint; it does not mask a product defect.

Coverage gaps are recorded in M-2.

### Local/CI count explanation

The earlier local command targeted only `tests/api`, which collects 68 tests and reports `22 passed, 46 deselected` for `-m "not postgres"`. CI runs pytest from the repository root, which collects 73 tests. The five additional root-level tests are:

- one PostgreSQL migration test in `tests/test_policy_migrations.py`;
- one non-PostgreSQL `create_all` guard in that file;
- three non-PostgreSQL gate tests in `tests/test_postgres_gate.py`.

Therefore the full-root local command and CI both report `26 passed, 47 deselected` for non-PostgreSQL selection, while CI's PostgreSQL selection reports `47 passed, 26 deselected`. The discrepancy is command scope, not different code or an unexplained collection failure.

## Documentation consistency

README, MASTER_PLAN, CHANGELOG, ARCHITECTURE, PRD, ADR 0004, and the implementation consistently state:

- Slice 2B is in Review;
- Slice 2C and Slice 3 are unauthorized and Not Started;
- no Policy frontend or complete Policy UX exists;
- Slice 2A and existing Backlog items remain intact;
- no production-readiness claim is made.

## Exact commands and results

Read-only commands executed included:

- `git status --short --branch` — expected branch; only 13 pre-existing untracked review files.
- `git branch --show-current` — `sprint/002-policy-api`.
- `git rev-parse HEAD origin/main origin/sprint/002-policy-api` — expected SHAs.
- `gh pr view 8 --json ...` — OPEN, Draft, MERGEABLE, six SUCCESS checks.
- `git diff --stat`, `git diff --name-status`, and full binary diff — 14 changed files, 1814 insertions, 18 deletions.
- `git diff --check origin/main...origin/sprint/002-policy-api` — passed.
- `.venv/bin/python -m pytest --collect-only -q tests/api` — 68 collected.
- `.venv/bin/python -m pytest tests/api -m "not postgres" -q` — 22 passed, 46 deselected.
- `.venv/bin/python -m pytest --collect-only -q` — 73 collected.
- `.venv/bin/python -m pytest -m "not postgres" -q` — 26 passed, 47 deselected.
- `.venv/bin/ruff check apps/api tests/api` — All checks passed.
- `.venv/bin/python -m compileall -q apps/api` — passed.
- `.venv/bin/alembic heads` — `0002_investment_policy_foundation (head)`.
- `.venv/bin/alembic history` — expected 0001 → 0002 chain.
- `.venv/bin/alembic upgrade head --sql` — passed; 336 SQL lines generated outside the repository.
- `gh run view 29330491438 ...` and `gh run view 29330493605 ...` — all six jobs SUCCESS.
- warning-log inspection — seven identical Alembic `path_separator` deprecations.
- Docker availability check — Docker command not found.
- OpenAPI inspection — 12 Policy operations; POST Policy has no declared request body.
- scope searches/diffs — no frontend, migration, dependency, Compose, or CI changes.
- existing untracked file SHA-256 recording — completed before generation.

## Unverified items

- Full Docker runtime and browser-path behavior: Docker CLI unavailable.
- Local real PostgreSQL execution: no local test database was configured; reviewed-head CI ran all 47 PostgreSQL-selected tests with zero skips.
- M-1 was established by transaction-boundary inspection; no new reproducer was created because this task forbids modifying tests/project files.
- Framework/server log redaction on an intentionally forced unrelated 500 was not dynamically exercised.
- Production, remote deployment, authentication, authorization, and compliance remain explicitly outside scope.

## Review-file declaration

This report, the critical-files bundle, and the binary diff are local read-only review artifacts. They must remain untracked and must not be committed, pushed, or attached to PR #8 by this task.

