# CompoundOS Sprint 002 Slice 2C — Independent Read-Only Review

## Review identity

- Pull request: #9 — `Sprint 002 Slice 2C: Policy Frontend Workflow`
- PR URL: https://github.com/Lolitadelgadosharona/CompoundOS/pull/9
- Base branch / SHA: `main` / `6571e16bfc83687d979e046c7a56a5207a615305`
- Head branch / SHA: `sprint/002-policy-frontend` / `917e64b83bf35363555a388f555a9feff8e36d40`
- PR state at review: OPEN, Draft, MERGEABLE
- Scope state: Slice 2C Review; Slice 3 Not Authorized / Not Started

## CI status

Both workflows target the reviewed head SHA and completed successfully.

| Event | Run ID | Job | Job ID | Result | Relevant result |
|---|---:|---|---:|---|---|
| push | 29386401848 | infrastructure | 87260503881 | SUCCESS | Compose version/config and localhost bindings passed |
| push | 29386401848 | backend | 87260503858 | SUCCESS | Ruff passed; 43 non-PostgreSQL tests passed; 74 real PostgreSQL tests passed |
| push | 29386401848 | frontend | 87260503849 | SUCCESS | 37 tests passed; build passed; audit found 0 vulnerabilities |
| pull_request | 29386430503 | infrastructure | 87260594709 | SUCCESS | Compose version/config and localhost bindings passed |
| pull_request | 29386430503 | backend | 87260594692 | SUCCESS | Ruff passed; 43 non-PostgreSQL tests passed; 74 real PostgreSQL tests passed |
| pull_request | 29386430503 | frontend | 87260594695 | SUCCESS | 37 tests passed; build passed; audit found 0 vulnerabilities |

CI success is not treated as proof of the async state-machine behavior discussed below.

## UI state and transition matrix

| State / transition | Implementation | Review result |
|---|---|---|
| Initial loading | Household and Policy GETs start in one `Promise.all`; stale workspace loads use an AbortController and sequence guard | Implemented, but auxiliary dependent GET isolation is incomplete (M-1) |
| Missing Household | Shows prerequisite and `/household` link; does not call Policy create | Correct |
| Empty Policy | Shows explicit create action; POST omits body; 409 reloads | Correct |
| Draft text | Ten fields, explicit changed-field PATCH, expected revision, no autosave | Core contract correct; dirty-state coordination is missing (M-2, M-3) |
| Draft allocations | Local add/remove/reorder and complete PUT | Core contract correct; display-name no-op comparison is incorrect for case-only edits (L-2) |
| Publish review | Displays the saved Draft snapshot, required-field checks, total, exact approved notice and confirmation | Request contract correct; it remains enabled while editors contain unsaved changes (M-2) |
| Published without Draft | Immutable current Version plus blank/current-Published Draft controls | Correct |
| Published with new Draft | Draft UI is shown, but the loaded current Published Version is not directly distinguished/rendered in this state | Partial (L-5) |
| Version history/detail | Newest-first list, cursor load-more, immutable detail | Core behavior present; stale pagination/refetch responses are not guarded (L-1) |
| Audit loading/error | Server order retained; latest-window disclosure; independent GET retry | Core behavior present; workspace and refresh controllers can race (M-4) |
| Discard | Explicit confirmation, expected revision, server reload, no Policy/Version delete | Contract correct; reload can discard unrelated local edits without warning (M-3) |

## API client contract matrix

| Method and path | Client behavior | Result |
|---|---|---|
| GET `/api/households/current` | AbortSignal propagated; 404 becomes `false` | Correct |
| POST `/api/policies` | No body and no explicit JSON `null` | Correct |
| GET `/api/policies/current` | AbortSignal propagated; 404 becomes `null` | Correct |
| GET `/api/policies/current/draft` | AbortSignal propagated; 404 becomes `null` | Correct |
| PATCH `/api/policies/current/draft` | Changed fields plus `expected_revision` | Correct |
| PUT `/api/policies/current/draft/allocations` | Complete ordered collection plus `expected_revision` | Correct |
| POST `/api/policies/current/draft` | `{}` for blank or current Published `source_version_id` | Correct |
| POST `/api/policies/current/draft/publish` | `expected_revision` plus `confirmation: true` | Correct |
| POST `/api/policies/current/draft/discard` | `expected_revision`; 204 does not call `response.json()` | Correct |
| GET `/api/policies/current/published` | AbortSignal propagated; 404 becomes `null` | Correct |
| GET `/api/policies/current/versions` | Uses server integer `before_version_number` cursor | Correct contract; async consumer race noted in L-1 |
| GET `/api/policies/current/versions/{number}` | Numeric server-provided version path; abortable | Correct |
| GET `/api/policies/current/audit-events` | Abortable; retry remains GET-only | Correct contract; controller coordination issue in M-4 |

`PolicyApiError` retains status for 404/409/422 and ignores untrusted response details. Empty, non-JSON and untrusted error bodies are not parsed, so they cannot leak request content through the UI. Network failures and HTTP 500 currently share the same generic visible message (L-4). No mutation retry or Policy console logging exists. `NEXT_PUBLIC_API_URL` follows the existing convention and does not address the separate Docker build-time backlog.

## Decimal arithmetic review

- Form and API percentage values remain strings.
- The parser accepts only ASCII digits with an optional decimal point and one or two fractional digits.
- It rejects signs, exponent notation, empty strings, multiple decimal points, excess scale, zero and values above 100.
- Digits are accumulated manually and converted to integer hundredths; totals use integer addition.
- `0.1`, `0.2`, `99.99`, `100`, and `100.01` produce the expected displays without binary-float artifacts or rounding.
- Leading zeros are handled consistently with the backend decimal contract.
- A single value is capped at 10,000 hundredths. No explicit collection-size limit exists, but exceeding JavaScript's safe-integer total would require an infeasible number of browser rows; no practical overflow was identified in this Slice.
- Exact `100.00` is described only as mechanical completeness, not approval or recommendation.

## Async and race review

The initial top-level GETs are genuinely parallel. Workspace reloads abort their predecessor and use a monotonic sequence check, and history-detail requests abort their predecessor. React Strict Mode's effect replay does not trigger mutations.

The remaining blocking issues are that dependent history failure is coupled to the core workspace (M-1), editor dirty state is invisible to publish and reload (M-2/M-3), and the workspace audit request and mutation-triggered audit request use independent controller domains without a shared generation guard (M-4). Load-more/history refresh requests also lack AbortSignal or generation checks (L-1). Mutation and pagination handlers do not have unmount guards; React ignores state updates after unmount, but the tests cover only initial GET cleanup (NB-1).

## Accessibility review

- Buttons declare `type="button"` or use the intended submit type.
- Textareas and allocation inputs use labels; errors/status/loading use `role="alert"` or `role="status"`.
- Publication/discard confirmation and allocation reordering are keyboard operable.
- Required/optional and completeness states include text, so color is not the only signal.
- Responsive CSS collapses grids and row layouts on narrow screens.
- Repeated row controls expose identical button names (`Move up`, `Move down`, `Remove`); the surrounding unlabeled `div` does not give each button a row-specific accessible name (L-6).
- No third-party state/form/UI dependency was added.

## Findings

### BLOCKER

None.

### HIGH

None.

### MEDIUM

#### M-1 — An auxiliary history failure hides an otherwise usable core Policy workspace

- File/location: `frontend/app/policy/policy-client.tsx:644-666`
- Evidence: Draft, Published and history requests share one `Promise.all`. Only audit has a local result wrapper. A history rejection enters the outer catch and sets global `loadError`, while the successful Draft/Published results are never committed.
- Impact: a transient version-history outage makes the current Draft or Published workflow inaccessible, contrary to the independent history loading/error requirement. Retry repeats the whole workspace load.
- Suggested fix: isolate history (and other non-core reads) with per-resource result handling or `Promise.allSettled`; commit the core Draft/Published snapshot and report history through `historyError`. Add a test in which history fails while Draft succeeds.

#### M-2 — Publish can silently publish the saved server Draft while editors contain newer unsaved input

- File/location: `frontend/app/policy/policy-client.tsx:104-137`, `215-263`, `378-457`, `857-865`
- Evidence: text and allocation local states live inside sibling components. `PublishReview` receives only the parent saved `draft` and has no dirty-state input. Its confirmation remains enabled after either editor is changed but not saved.
- Impact: the owner can enter changes, open review and publish the older server snapshot, reasonably believing the visible editing work is part of the publication. The generic statement that review uses a saved snapshot is not a dirty-specific warning and does not require saving first.
- Suggested fix: surface text/allocation dirty flags to the parent; block review/publish while either editor is dirty and explicitly require Save or intentional local reset. Add tests for unsaved text and allocation edits.

#### M-3 — Reload server data silently discards local edits across both editors

- File/location: `frontend/app/policy/policy-client.tsx:86-91`, `616-658`, `863-865`
- Evidence: conflict panels call `loadWorkspace` directly. A successful load increments `workspaceEpoch`, changing both editor keys and remounting them from the server snapshot. The parent does not know whether either editor is dirty and shows no discard warning/confirmation.
- Impact: resolving a 409 in one editor can silently erase unrelated unsaved work in the other editor. This is direct local data-loss risk.
- Suggested fix: coordinate dirty state at the workspace boundary and require explicit confirmation that reload will discard all local edits, or reload only the conflicted resource while preserving other local state. Add cross-editor conflict/reload tests.

#### M-4 — Old audit responses can overwrite a newer workspace audit snapshot

- File/location: `frontend/app/policy/policy-client.tsx:616-651`, `675-694`, `705-709`
- Evidence: `loadWorkspace` aborts only `loadController` and performs its audit GET with that controller. `refreshAudit` uses `auditController`; neither path invalidates or generation-checks the other. Both independently call `setAuditEvents`.
- Impact: a mutation-triggered audit request can finish after a later full reload and replace the newer timeline with an older response. The stale timeline then persists until another manual refresh, weakening the auditability guarantee.
- Suggested fix: use one audit request coordinator/generation token for every audit GET, abort any existing audit request when a workspace load begins, and commit results only when the audit generation is current. Add a deterministic deferred-response race test.

### LOW

#### L-1 — History pagination and publication/workspace refreshes have no shared stale-response guard

- File/location: `frontend/app/policy/policy-client.tsx:767-800`
- Evidence: `loadMoreHistory` and the post-publish history refresh pass no AbortSignal and use no request generation. A late page can merge into a newer reload and overwrite `nextHistoryCursor`.
- Impact: history/cursor display can become temporarily inconsistent after load-more overlaps reload or publish. Immutable server data is not changed.
- Suggested fix: add a history AbortController/generation and validate the requested cursor before applying a page.

#### L-2 — Allocation semantic no-op detection suppresses legitimate case-only display-name changes

- File/location: `frontend/lib/policy-api.ts:283-299`
- Evidence: `normalizedName` lowercases both saved and edited display names before equality comparison. The backend stores and compares the normalized display name separately from its casefolded uniqueness key, so `Cash` to `CASH` is a real display update on the server but a client-side no-op.
- Impact: the user cannot explicitly save capitalization-only corrections to their authored asset-class display text.
- Suggested fix: compare the backend-equivalent normalized display name without lowercasing; leave canonical duplicate enforcement to the backend. Add a case-only update test.

#### L-3 — Allocation name `maxLength` uses UTF-16 units instead of approved Unicode character counting

- File/location: `frontend/app/policy/policy-client.tsx:299-305`
- Evidence: allocation names use HTML `maxLength={200}`. Browser maxlength counts UTF-16 code units, while the approved API limit and the text editor's helper count Unicode code points. Astral characters such as emoji consume two UTF-16 units.
- Impact: valid names containing astral characters are prematurely limited (for example, 200 emoji cannot be entered although the backend character limit permits them).
- Suggested fix: remove native maxlength for this field and validate/display `Array.from(value).length`, matching the Policy text approach and backend contract.

#### L-4 — HTTP 500 and network failures are not visibly distinguishable

- File/location: `frontend/lib/policy-api.ts:108-126`; `frontend/app/policy/policy-client.tsx:63-67`
- Evidence: non-listed HTTP statuses and non-`PolicyApiError` network exceptions both render `The Policy request could not be completed.`
- Impact: recovery guidance cannot distinguish a reachable server failure from loss of connectivity, despite the review requirement for distinct neutral handling.
- Suggested fix: retain safe, non-payload messages with a separate network-unavailable message and an explicit generic server-error message; test both empty/non-JSON 500 and rejected fetch.

#### L-5 — Published-with-Draft is not a distinct direct view

- File/location: `frontend/app/policy/policy-client.tsx:857-910`
- Evidence: when a Draft exists, the Draft branch renders and the loaded `published` snapshot is not rendered. The current Published Version is directly shown only when `draft` is null; with a Draft, the user must locate it through history detail.
- Impact: the required Published-with-new-Draft state is not clearly distinguishable and comparison/provenance context is harder to access, though immutable history remains available.
- Suggested fix: render a compact immutable current-Published section whenever both Draft and Published exist, without adding edit/copy-historical actions.

#### L-6 — Repeated allocation row controls lack row-specific accessible names

- File/location: `frontend/app/policy/policy-client.tsx:315-323`
- Evidence: every row exposes buttons named only `Move up`, `Move down`, and `Remove`. The `aria-label` is on a plain parent `div` and does not make each button's accessible name unique.
- Impact: keyboard operation works, but screen-reader users cannot easily identify which row each repeated action affects.
- Suggested fix: add row name/index to each button's `aria-label`, and optionally make the action container an explicitly labeled group.

### NON-BLOCKING

#### NB-1 — Test coverage does not exercise the state/race and Unicode boundaries above

- File/location: `frontend/app/policy/page.test.tsx`; `frontend/lib/policy-api.test.ts`
- Evidence: tests cover initial abort only, not mutation/history unmount; no deferred history/audit cross-request race; no dirty-editor publish/reload; no auxiliary-history failure; no case-only allocation update; no emoji boundary. The fetch fixture also adds `expected_revision` into its PATCH response and rebuilds from a fixed `draft`, which is not an exact FastAPI response model for sequential saves.
- Impact: the 37 green tests do not fail for the blocking behaviors identified in M-1 through M-4.
- Suggested fix: add behavior-level deferred-promise tests and make the fixture return exact server snapshots. Keep jsdom limitations disclosed.

#### NB-2 — Full Docker and data-backed browser validation remains unavailable locally

- Evidence: Docker CLI and local `TEST_DATABASE_URL` are unavailable. GitHub CI did validate Compose and run all 74 real PostgreSQL tests, but no real browser was run against the full local stack.
- Impact: cross-browser layout/focus and end-to-end browser/API/PostgreSQL behavior remain unverified.
- Suggested follow-up: retain the existing Docker/browser backlog and run it in a Docker-enabled environment after code findings are resolved.

## Test credibility and coverage gaps

The suite uses Testing Library interactions and awaited `findBy`/`waitFor` checks rather than testing private component implementation. It covers missing/empty states, create conflict, text save/no-op/409 retention, allocation add/remove/reorder/PUT/422 retention, publish confirmation/400/409/success, current-Published copy, history pagination/detail, audit order/failure/retry, discard, safety text and initial abort. API tests cover major mutation paths, status retention, no-body create and decimal arithmetic. Tests pass both individually and with shuffled order, and global fetch is restored after every test.

Coverage gaps are material for dirty-state publication/reload, auxiliary GET isolation, cross-controller stale audit results, stale history pages, 500/network distinction, Unicode allocation limits and case-only display updates. The tests use structurally representative fixtures but no runtime schema validation, and jsdom cannot substitute for the unverified full browser path.

## Product and scope exclusion confirmation

- No backend, migration, dependency, Compose, CI or environment file changed.
- No recommendation, default allocation, suitability, eligibility, score, ranking, Guardian threshold/alert, AI generation, Broker/market/holding/account, trade or rebalance execution was introduced.
- No authentication or production/public-deployment claim was introduced.
- The local-only, non-production, no-authentication and exact approved non-advisory copy are visible at Policy entry; the approved notice is repeated immediately before publication.
- README, Master Plan, Changelog, Architecture and PRD consistently keep Sprint 002 In Progress, Slice 2C in Review and Slice 3 unauthorized.
- Existing backlog items, including explicit JSON `null`, Docker/browser validation, `NEXT_PUBLIC_API_URL`, dependency split, AuditEvent pagination, persistence coverage and Alembic `path_separator`, remain present.

## Exact commands and results

- `git status --short --branch`, branch/SHA/remote rev-parse, and `gh pr view 9 ...`: expected branch and SHAs; tracked/staged clean; PR OPEN/Draft/MERGEABLE.
- `git diff --stat origin/main...origin/sprint/002-policy-frontend`: 12 files, 2,160 insertions, 28 deletions.
- `git diff --check origin/main...origin/sprint/002-policy-frontend`: passed.
- `npm ci`: 436 packages installed, 437 audited, 0 vulnerabilities.
- `npm run lint`: passed with zero warnings/errors.
- `npm run type-check`: passed with zero TypeScript errors.
- `npm test`: 4 files passed, 37 tests passed.
- `npm test -- app/policy/page.test.tsx`: 1 file passed, 19 tests passed.
- `npm test -- lib/policy-api.test.ts`: 1 file passed, 8 tests passed.
- `npm test -- --sequence.shuffle --sequence.seed=902`: 4 files passed, 37 tests passed with seed 902.
- `npm run build`: Next.js 16.2.10 production build passed; `/policy` generated successfully.
- `npm audit --omit=dev`: 0 vulnerabilities.
- `.venv/bin/pip check`: no broken requirements.
- `.venv/bin/ruff check apps tests`: all checks passed.
- `.venv/bin/python -m compileall -q apps/api`: passed.
- `.venv/bin/python -m pytest -q -m 'not postgres'`: 43 passed, 74 deselected.
- YAML parsing for `compose.yaml` and `.github/workflows/ci.yml`: passed.
- Static localhost binding inspection: web/API/PostgreSQL/Redis all bound to `127.0.0.1` defaults.
- Local Docker check: Docker CLI unavailable; Compose runtime not locally verified.
- `gh run list`, `gh pr checks 9` and job-log inspection: all six push/pull_request jobs SUCCESS; each backend job ran 74 real PostgreSQL tests with zero skips.

The local environment emitted an existing `NODE_TLS_REJECT_UNAUTHORIZED=0` warning during npm/Next.js commands. No repository configuration was changed to suppress it.

## Unverified items

- Full Docker runtime and full-stack browser workflow.
- Local real PostgreSQL run; this was instead verified by both required GitHub backend jobs.
- Real-browser focus, layout and assistive-technology behavior beyond static/jsdom review.

## Final conclusion

**REQUEST CHANGES**

Counts: BLOCKER 0, HIGH 0, MEDIUM 4, LOW 6, NON-BLOCKING 2.

The PR remains within the authorized product scope and its contracts, decimal arithmetic and safety copy are generally strong. M-1 through M-4 are merge-blocking because they can hide the core editor, publish an older snapshot than the owner's visible work, silently discard local edits, or regress the displayed audit history through stale async results. Per the review rule, the presence of MEDIUM findings requires REQUEST CHANGES.
