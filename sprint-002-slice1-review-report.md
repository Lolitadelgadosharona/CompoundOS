# CompoundOS Sprint 002 Slice 1 — Independent Read-Only Review

## Review metadata

- Pull request: [#5 — Sprint 002: Household and Persistence Foundation](https://github.com/Lolitadelgadosharona/CompoundOS/pull/5)
- State at review: `OPEN`, `Draft`, `MERGEABLE`
- Base: `main` at `1c00f26ac8078a54ab281231aeabb30d8a087e09`
- Head: `sprint/002-household-foundation` at `44249ceb20b726af24541c2ca5262dcbd7ba379c`
- Review scope: the complete diff between the two SHAs above
- Review mode: read-only; no tracked project file, commit, branch, or pull request was changed

## Executive summary

The implementation stays within the approved Household and Persistence Foundation slice. It adds one household profile, PostgreSQL-backed persistence, append-only audit events for household create/update operations, and a household UI. It does not implement investment policy, target allocation, decision journal, AI, Guardian, broker, trading, authentication, or Redis-backed product behavior.

The architecture is generally disciplined: Alembic owns schema creation, repositories flush but do not commit, services define transaction boundaries, and the API and UI expose the approved local-only/non-advisory boundaries. The current GitHub Actions runs are green and the backend run executed all 24 tests against the PostgreSQL service.

Three issues should be resolved before merge: CI can silently pass if PostgreSQL tests are skipped because `TEST_DATABASE_URL` is absent; several API-enforced safety constraints are not enforced by PostgreSQL; and a successful write followed by a failed audit refresh can leave the UI showing inconsistent state without a visible recovery path. Two lower-severity issues and two explicit follow-ups are also documented below.

## GitHub Actions

All six check runs attached to the reviewed head SHA completed successfully.

| Event | Workflow run | Job | Job ID | Result |
|---|---:|---|---:|---|
| `push` | `29235048618` | `infrastructure` | `86767681752` | `SUCCESS` |
| `push` | `29235048618` | `backend` | `86767681735` | `SUCCESS` |
| `push` | `29235048618` | `frontend` | `86767681718` | `SUCCESS` |
| `pull_request` | `29235088610` | `infrastructure` | `86767807662` | `SUCCESS` |
| `pull_request` | `29235088610` | `backend` | `86767807561` | `SUCCESS` |
| `pull_request` | `29235088610` | `frontend` | `86767807637` | `SUCCESS` |

Observed current PR-run results include:

- Infrastructure: Docker Compose v2.38.2 available; Compose configuration and localhost-binding checks passed.
- Backend: Alembic reported `0001_household_persistence (head)`; Ruff reported `All checks passed!`; Pytest reported `24 passed in 0.46s`.
- Frontend: Vitest reported 2 test files and 7 tests passed; production build completed successfully; `npm audit` reported 0 vulnerabilities.

CI success is evidence for the reviewed commit, but it does not remove the gate weakness described in Finding M-1 or replace Docker runtime testing.

## A. Scope

- **Approved scope:** Yes. The implementation is limited to `HouseholdProfile`, PostgreSQL persistence, `AuditEvent` records for household creation/update, and the household UI plus supporting tests/configuration.
- **Unapproved logic:** No investment-policy engine, target-allocation engine, decision journal, AI agent, Guardian thresholds or alerting, broker integration, trading, authentication, or Redis product logic was found. References to these concepts are boundary statements, notices, planning documentation, or negative tests rather than implementations.
- **Speculative abstractions:** No material speculative future-module framework was introduced. The router/service/repository split is small and directly supports the implemented transaction and test boundaries.
- **Conclusion:** Scope is compliant with Slice 1 and Slice 2 remains unimplemented.

## B. Database and migration

- **Tables created:** Migration `0001_household_persistence.py` creates only `household_profiles` and `audit_events`; Alembic may create its normal `alembic_version` table. No other application tables are introduced.
- **Schema ownership:** The application avoids `metadata.create_all`; Alembic is the schema authority.
- **Database URL:** `migrations/env.py:9-10` loads `get_database_url()` and applies it to Alembic configuration, so migrations use the configured `DATABASE_URL`.
- **Singleton constraints:** PostgreSQL enforces both the `singleton_key IS TRUE` check and the unique constraint on `singleton_key`. Because all valid rows use `TRUE`, the unique index limits the table to one household. Concurrent inserts race at the unique constraint; one can commit and the other receives an integrity error rather than creating two rows.
- **Model alignment:** Entity names, nullability, primary/foreign keys, and principal string lengths align. However, database-level constraints do not fully match the Pydantic limits or currency format; see Finding M-2.
- **Relationships and types:** `audit_events.household_id` uses a restrictive foreign key, which is suitable because deletion is outside this slice. The `(household_id, occurred_at, id)` access pattern is supported by indexes/order keys. Time-zone-aware timestamps and JSONB metadata are suitable PostgreSQL choices.
- **Migration behavior:** The migration is explicit and reversible in dependency order. Its defaults are limited to the singleton invariant. No data-destructive upgrade or unexpected table creation was found.

## C. Transaction correctness

- **Session lifecycle:** `apps/api/database.py:8-15` supplies one request-scoped session and closes it after the request. Services own transaction blocks; repositories call `flush()` to obtain IDs but do not commit; routers do not commit.
- **Atomicity:** Household creation/update and its audit event occur inside the same service transaction, so an audit insert failure rolls back the household mutation. The PostgreSQL tests exercise these failure paths.
- **Integrity mapping:** `apps/api/services/households.py:30-54` maps only the named singleton constraint to the domain conflict path. Other `IntegrityError` instances are re-raised and are not mislabeled as HTTP 409.
- **Rollback reuse:** SQLAlchemy's transaction context rolls back before the service's explicit rollback. The additional rollback is redundant but safe; tested sessions remain usable afterward.
- **No-op PATCH:** An empty patch or a patch that does not change persisted values is rejected before an audit event is written. Tests verify no new event is created.
- **Concurrency/failure coverage:** Tests run against a real PostgreSQL URL and cover conflicting creation plus transaction rollback after audit failure. The CI skip weakness is separately identified in Finding M-1.

## D. Singleton behavior

- **Client-controlled internal fields:** Pydantic schemas forbid extra fields, so clients cannot set `id`, `singleton_key`, `actor`, or timestamps through POST/PATCH contracts.
- **Maximum cardinality:** The database check requires the singleton key to be true, and the unique constraint permits only one true row. Supplying a different profile ID does not bypass the invariant.
- **Bypass analysis:** Product routes and repositories provide no delete, replacement, archive, or raw-SQL path. A database administrator or test code with direct SQL privileges can of course delete/truncate data, but that is outside the application contract and does not constitute a product bypass.
- **Unapproved lifecycle:** No `active`, archive, delete, or replacement behavior was introduced.

## E. Validation and privacy

- **Extra fields and trimming:** Extra fields are rejected. Shared Pydantic configuration strips surrounding whitespace consistently before length checks.
- **Currency:** API validation requires exactly three uppercase ASCII letters. PostgreSQL itself currently only enforces the column length; see Finding M-2.
- **Maximum lengths:** API schemas apply technical limits. Several text limits are not mirrored as database checks, which allows non-API writers or defects to bypass them; see Finding M-2.
- **HTTP errors:** The validation handler removes the raw `input` from validation details. Domain and generic error messages do not echo the full household content.
- **Logs and audit metadata:** Audit metadata records changed field names rather than the full values of `risk_statement`, `liquidity_needs`, or `notes`. No sensitive payload logging was found.
- **Response isolation:** Response schemas expose approved household and audit fields but omit `singleton_key` and other internal database mechanics.
- **Network scope:** CORS is restricted to localhost/127.0.0.1 development origins, and all Compose host ports bind to `127.0.0.1`. No public-network default was introduced.

## F. API contracts

- **Status behavior:** POST returns 201; missing current household returns 404; a second create returns 409; Pydantic input failures return 422; semantically empty/no-op PATCH returns 400. These contracts are covered by tests.
- **Current and audit reads:** The current-profile query is deterministic under the singleton invariant. Audit events are ordered by `occurred_at` and then `id`, giving stable ordering even when timestamps match.
- **ORM isolation:** API responses are validated through response schemas rather than serializing ORM internals directly.
- **Pagination:** The audit route currently returns the complete event history. That is acceptable for this local, single-household foundation slice, but unbounded growth needs a future pagination decision; see Follow-up N-1.
- **PATCH semantics:** Empty objects and effective no-op updates are explicitly rejected and do not create audit records.
- **Health:** The health endpoint does not query PostgreSQL. Engine construction is configuration-time/lazy and does not turn `/health` into a database readiness probe, consistent with the documentation.

## G. Frontend

- **API URL:** The adapter reads `NEXT_PUBLIC_API_URL` with a localhost fallback. The fallback works for a browser opening the default Compose-hosted UI, but Compose runtime overrides do not alter an already-built public bundle; see Finding L-1.
- **Error handling:** 404 is handled as the initial empty state. String `detail` responses such as 409 are displayed. Structured 422 responses degrade to a generic status message rather than unsafe serialization; network failures are caught. Field-level 422 UX is not required by this slice.
- **Initial loading:** Profile and audit requests run in parallel. The active flag prevents state updates after unmount, and no duplicate request-driven overwrite was found.
- **Write consistency:** The profile is committed to React state before the post-write audit refresh resolves. A refresh failure can therefore produce a stale/empty timeline and lose the visible error path, especially when the create form unmounts; see Finding M-3.
- **Form behavior:** Failed creates retain input because the form stays mounted. Create and edit modes are visibly distinct, with cancel behavior for edits.
- **Boundary notices:** The screen states that it is local-only and not investment advice. It does not present recommendations or actions as advice.
- **Accessibility/security:** Inputs have labels, controls use buttons, loading/error text is present, and no `dangerouslySetInnerHTML`, XSS-prone rendering, or sensitive console logging was found.
- **Tests:** Tests render the real page/client components and exercise the real API adapter with mocked `fetch`; they are not merely tests of mock functions. They do not cover a successful mutation followed by an audit-refresh failure, which is part of Finding M-3.

## H. Compose and Docker

- **Bindings:** Web, API, PostgreSQL, and Redis ports all bind to `127.0.0.1` by default.
- **Startup order:** `migrate` waits for healthy PostgreSQL; API waits for successful migration and healthy PostgreSQL/Redis; web waits for API health. The declared order is coherent.
- **API image contents:** The API build includes requirements, application sources, migrations, and `alembic.ini`, and has the dependencies needed to run migrations and Uvicorn.
- **Frontend connectivity:** The default browser URL `http://127.0.0.1:8000` is appropriate because browser JavaScript runs on the host. A custom Compose `NEXT_PUBLIC_API_URL` supplied only at container runtime is ineffective for a Next.js public build; see Finding L-1.
- **Credentials:** PostgreSQL credentials are explicitly local-development defaults and not production secrets.
- **Runtime gap:** CI validates Compose syntax and bindings but does not build or start the stack. Full runtime validation could still reveal image build-context errors, migration-container startup failures, health-check timing problems, service command issues, or browser-to-API connectivity/CORS defects. This remains Follow-up N-2.

## I. CI and tests

- **PostgreSQL use:** CI starts PostgreSQL, exports `TEST_DATABASE_URL`, runs Alembic before Pytest, and the database fixtures connect to that URL. The observed 24-test run therefore includes real PostgreSQL integration tests rather than only mocks.
- **Migration order:** Alembic upgrade and head verification occur before backend tests.
- **Skip behavior:** `tests/conftest.py` skips PostgreSQL tests when `TEST_DATABASE_URL` is absent, and CI does not fail on skipped integration tests. This could allow a configuration regression to turn the database suite green without executing it; see Finding M-1. The reviewed run itself reported 24 passed and no skips.
- **Frontend count:** The observed 2 files / 7 tests matches the repository suite: six household tests plus the health-route test.
- **Compose check:** The localhost-binding test parses rendered Compose JSON/YAML data rather than merely grepping source text.
- **Audit semantics:** `npm audit` is executed without suppressing its nonzero exit, so actionable audit findings fail the job. The reviewed run reported zero vulnerabilities.
- **Missing blocking tests/gates:** Add a CI no-skip guarantee for PostgreSQL integration tests, database-level constraint tests for text/currency invariants, and a frontend test for successful mutation followed by failed audit refresh.

## J. Dependencies and security

- **Necessity:** SQLAlchemy, Alembic, Pydantic settings, and Psycopg directly support the approved PostgreSQL foundation. HTTP/test/lint packages support existing validation workflows. No AI, broker, trading, authentication, or unnecessary client-state framework dependency was added.
- **Pinning and compatibility:** Python requirements are exactly pinned and the Node lockfile pins transitive packages. The selected FastAPI/Pydantic/SQLAlchemy/Psycopg stack is internally consistent in the passing CI environment.
- **Runtime/development separation:** Runtime and test/lint packages are combined in `requirements.txt` and installed in the API runtime image; see Finding L-2.
- **Psycopg packaging:** `psycopg[binary]` is practical for the current local, CI, and Docker foundation. A production deployment may later choose a compiled/system-library strategy, but production deployment is outside this slice.
- **Known risk signal:** `npm audit` reported zero vulnerabilities, and CI/lint/test output did not expose a known blocker. This is not a substitute for ongoing dependency maintenance.
- **Secrets:** No real secret was found in source, lockfiles, logs, or fixtures. CI and Compose passwords are recognizable local/test placeholders.

## K. Documentation consistency

- **README:** Commands correspond to the repository structure and CI workflow. The environment-export step is explicit. Docker commands remain accurately labeled as not runtime-verified in the originating local environment.
- **Architecture/PRD/ADR:** These documents align with the household singleton, PostgreSQL/Alembic ownership, service transaction boundary, append-only audit behavior, and local-only limits. The documented API field constraints are stronger than the current database checks, as noted in Finding M-2.
- **Planning state:** `docs/MASTER_PLAN.md` keeps Sprint 001 Done and Sprint 002 In Progress for the approved Slice 1. It does not mark Sprint 002 Done.
- **Authorization boundary:** Slice 2 remains unapproved and unimplemented.
- **Verification disclosure:** Docker runtime/browser verification limitations are disclosed rather than represented as completed. The Compose public-environment override caveat in Finding L-1 should be clarified or fixed.

## L. Findings

### BLOCKER

None.

### HIGH

None.

### MEDIUM

#### M-1 — CI can pass when PostgreSQL integration tests are skipped

- **Files/lines:** `tests/conftest.py:18-20`; `.github/workflows/ci.yml:60-79`
- **Issue:** The database fixture calls `pytest.skip()` when `TEST_DATABASE_URL` is absent, while the CI Pytest command does not assert that integration tests ran or that the skip count is zero.
- **Trigger:** A workflow refactor, misspelled/empty environment variable, or fixture configuration regression removes `TEST_DATABASE_URL` while leaving the Pytest step active.
- **Impact:** The backend job may report success while database constraints, migrations, transaction rollback, and concurrency behavior were not tested. This weakens the main safety gate for the persistence slice.
- **Suggested fix:** Make absence of `TEST_DATABASE_URL` a hard failure in CI (for example through a CI-specific environment flag), or mark integration tests and add an explicit CI assertion that the full PostgreSQL suite ran with zero skips.
- **Blocks merge:** **Yes.** The current run genuinely executed 24 tests, but the gate should reliably enforce that property for future commits.

#### M-2 — PostgreSQL does not enforce all documented input safety constraints

- **Files/lines:** `apps/api/schemas.py:9-24`; `apps/api/models.py:37-42`; `migrations/versions/0001_household_persistence.py:25-30`
- **Issue:** Pydantic limits `investment_horizon`, `liquidity_needs`, `risk_statement`, and `notes`, and requires `base_currency` to match three uppercase ASCII letters. The database uses unconstrained `TEXT` for those narrative fields and only a length-limited `VARCHAR(3)` for currency.
- **Trigger:** A repository defect, migration/data repair, direct SQL import, or future internal writer bypasses the HTTP validation layer.
- **Impact:** Persisted rows can violate the documented schema, create unexpectedly large sensitive records, or store lowercase/non-letter currency values. Later reads may fail response validation or expose inconsistent behavior between write paths.
- **Suggested fix:** Add named PostgreSQL `CHECK` constraints for the documented maximum lengths and the currency format, keep ORM metadata and Alembic migration definitions aligned, and add real-PostgreSQL tests for rejected invalid rows.
- **Blocks merge:** **Yes.** These are core persistence invariants for the schema being introduced.

#### M-3 — Post-write audit refresh failure can leave inconsistent UI state without a reliable error

- **Files/lines:** `frontend/app/household/household-client.tsx:242-252`; `frontend/app/household/page.test.tsx`
- **Issue:** Create/update handlers set the returned profile before awaiting the audit refresh. If the write succeeds but the subsequent audit GET fails, profile and timeline state diverge. On create, setting the profile unmounts the create form, so the caught error can be written to state owned by a component that is no longer visible.
- **Trigger:** POST/PATCH returns success, followed by a transient network failure or 5xx response from `GET /api/household/audit`.
- **Impact:** A user can see a successfully saved profile with an empty or stale audit history and no clear indication/retry path, undermining the slice's auditability promise. Retrying the mutation could also produce confusing conflict/no-op responses because the write already committed.
- **Suggested fix:** Model mutation success and audit-refresh failure separately, keep a visible page-level audit error with a retry action, and add create/update tests for the “write succeeded, refresh failed” sequence.
- **Blocks merge:** **Yes.** The issue affects the consistency and explainability of the primary end-to-end flow.

### LOW

#### L-1 — Compose runtime API URL override does not affect the built browser bundle

- **Files/lines:** `frontend/lib/household-api.ts:27`; `frontend/Dockerfile:11-12`; `compose.yaml:6-7`
- **Issue:** `NEXT_PUBLIC_API_URL` is read at Next.js build time, but Compose supplies it only to the running web container. The Docker build has no matching build argument/environment declaration.
- **Trigger:** A developer changes `NEXT_PUBLIC_API_URL` in `.env` expecting the Compose-built frontend to call a non-default API URL.
- **Impact:** Browser requests continue using the compiled fallback/default, causing confusing connectivity failures outside the exact default localhost topology.
- **Suggested fix:** Pass a documented build argument into the frontend image and set it before `npm run build`, or explicitly declare the image's API origin fixed for this local-only slice and remove the ineffective runtime override.
- **Blocks merge:** **No**, because the default local URL is valid and public deployment is prohibited.

#### L-2 — API runtime image includes development-only dependencies

- **Files/lines:** `requirements.txt:1-9`; `apps/api/Dockerfile`
- **Issue:** Pytest, Ruff, and other test tooling share the runtime requirements file and are installed into the API image.
- **Trigger:** Every API image build.
- **Impact:** The image is larger and carries more packages than required to serve the API, modestly increasing build time and maintenance/security surface.
- **Suggested fix:** Split runtime and development requirements when production/container hardening is approved, while keeping CI reproducible.
- **Blocks merge:** **No.** It is acceptable for this local-development foundation.

### NON-BLOCKING

#### N-1 — Audit history is unpaginated

- **Files/lines:** `apps/api/repositories/households.py:46-52`; `apps/api/routers/households.py:53-59`
- **Issue:** The endpoint returns all audit events in one response.
- **Trigger:** A household accumulates a long history of profile changes.
- **Impact:** Query, serialization, and browser rendering costs grow without a bound.
- **Suggested fix:** Record a backlog decision for cursor pagination and introduce it before the journal or other high-volume event sources are authorized.
- **Blocks merge:** **No.** A single local household in Slice 1 has low event volume.

#### N-2 — Docker runtime and browser path remain unverified

- **Files/lines:** `.github/workflows/ci.yml:9-42`; `docs/MASTER_PLAN.md`; `docs/CHANGELOG.md`
- **Issue:** CI validates rendered Compose configuration and bindings but does not run `docker compose build`/`up` or exercise both health endpoints in containers.
- **Trigger:** A latent image, command, migration orchestration, health timing, or browser-connectivity issue that static Compose validation cannot reveal.
- **Impact:** The documented full-stack local startup could fail even though CI is green.
- **Suggested fix:** Complete the existing Docker-enabled backlog validation and record exact results; add runtime CI only if its cost and reliability are approved.
- **Blocks merge:** **No.** The limitation is accurately disclosed and was already accepted as a non-blocking backlog item.

## Finding totals

| Severity | Count |
|---|---:|
| BLOCKER | 0 |
| HIGH | 0 |
| MEDIUM | 3 |
| LOW | 2 |
| NON-BLOCKING | 2 |

## Final conclusion

**REQUEST CHANGES**

The reviewed slice is appropriately scoped and its current CI runs are successful, but Findings M-1, M-2, and M-3 should be resolved and covered by tests before PR #5 is merged. The Docker runtime gap, audit pagination, public-environment build behavior, and dependency separation can remain explicit follow-ups within their stated boundaries. This conclusion does not authorize Slice 2.

---

This file is an untracked, local, read-only review artifact. It is not part of the pull request and was not staged, committed, pushed, or used to modify PR #5.
