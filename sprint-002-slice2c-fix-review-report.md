# CompoundOS Sprint 002 Slice 2C — Incremental Fix Review

## Review identity

- Pull request: #9 — `Sprint 002 Slice 2C: Policy Frontend Workflow`
- PR URL: https://github.com/Lolitadelgadosharona/CompoundOS/pull/9
- Original reviewed HEAD: `917e64b83bf35363555a388f555a9feff8e36d40`
- Current HEAD (fix commit): `c732569a2a22fd9846c6fa064993d4ea0514754b`
- Fix commit message: `fix: address Sprint 002 Slice 2C review findings`
- Original review conclusion: REQUEST CHANGES (M-1 through M-4, L-1 through L-6)
- Incremental review scope: read-only re-review of fix commit only
- Slice 3: Not Authorized / Not Started

## PR and CI status

| Property | Value |
|---|---|
| State | OPEN |
| Draft | true |
| Mergeable | MERGEABLE |
| Head branch | `sprint/002-policy-frontend` |
| Head SHA | `c732569a2a22fd9846c6fa064993d4ea0514754b` |

### CI runs targeting fix commit `c732569`

| Event | Run ID | Job | Result |
|---|---:|---|---|
| push | 29406093504 | backend | SUCCESS |
| push | 29406093504 | frontend | SUCCESS |
| push | 29406093504 | infrastructure | SUCCESS |
| pull_request | 29406097286 | backend | SUCCESS |
| pull_request | 29406097286 | frontend | SUCCESS |
| pull_request | 29406097286 | infrastructure | SUCCESS |

All six CI jobs targeting the fix commit passed. CI success is noted but does not substitute for the async state-machine review below.

## Incremental diff summary

```
 docs/ARCHITECTURE.md                  |  19 +-
 docs/CHANGELOG.md                     |  13 ++
 docs/MASTER_PLAN.md                   |  10 +
 docs/PRD.md                           |   9 +
 frontend/app/policy/page.test.tsx     | 371 +++++++++++++++++++++++++++++++++-
 frontend/app/policy/policy-client.tsx | 293 ++++++++++++++++++---------
 frontend/lib/policy-api.test.ts       |  35 ++++
 frontend/lib/policy-api.ts            |  34 +++-
 8 files changed, 674 insertions(+), 110 deletions(-)
```

No backend, migration, dependency, lockfile, Compose, CI, or environment file was modified.

## Resolution matrix — MEDIUM findings

### M-1 — Auxiliary resource isolation

**Verdict: RESOLVED**

The fix restructures `loadWorkspace` into three distinct phases:

1. **Core identity**: `Promise.all([hasCurrentHousehold, getCurrentPolicy])` — the only requests whose failure sets `loadError`.
2. **Core workspace**: `Promise.all([getCurrentDraft, getCurrentPublished])` — awaited in the same block, sharing the core controller.
3. **Auxiliary resources**: `void refreshHistory()` and `void refreshAudit()` — fire-and-forget, each with its own AbortController and monotonic generation.

History failure sets only `historyError` (via `refreshHistory` catch block, line 713). Audit failure sets only `auditError` (via `refreshAudit` catch block, line 686). Neither path can set `loadError` or affect the core Draft/Published snapshot.

When the household is missing or the Policy is absent, both auxiliary controllers are explicitly aborted and their generations incremented (lines 738-741), preventing any pending auxiliary response from committing.

**Tests**: "keeps the core Draft usable when initial history loading fails" (page.test.tsx line 373), "keeps Published visible and retries only history after history failure" (line 395), "keeps the Draft usable when audit fails and retries only audit" (line 406), "shows a core error when the Draft request fails" (line 419).

History retry calls only `getVersionHistory` (GET, line 705). Audit retry calls only `getPolicyAuditEvents` (GET, line 681). Neither retry replays a mutation or re-executes a core GET.

`refreshHistory` and `refreshAudit` both suppress AbortError via `!isAbort(caught)` before setting error state. History recovery does not reset Draft local state because the editors use `key={`text-${draft.id}-${workspaceEpoch}`}` — only a successful `loadWorkspace` bumps `workspaceEpoch` (line 769).

### M-2 — Dirty state and publish blocking

**Verdict: RESOLVED**

The parent `PolicyClient` owns `textDirty` and `allocationsDirty` as independent `useState` booleans (lines 668-669), combined as `const dirty = textDirty || allocationsDirty` (line 671).

Each editor receives an `onDirtyChange` callback. `DraftTextEditor` computes dirty via `useMemo` over `POLICY_TEXT_FIELDS.some((field) => form[field].trim() !== draft[field])` (line 113-116). `AllocationEditor` uses `!allocationsEqual(draft.allocations, inputs)` (line 239), which applies NFKC + trim + whitespace collapse matching backend semantics.

Both editors report dirty through `useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange])` (lines 118, 241). The effect fires only on boolean transitions. `onDirtyChange` maps to the stable `setTextDirty`/`setAllocationsDirty` setters, so setting the same value is a React no-op — no render loop.

Text save calls `setTextDirty(false)` (line 148) without touching `allocationsDirty`. Allocation save calls `setAllocationsDirty(false)` (line 289) without touching `textDirty`. Verified by test "blocks publication until both text and allocation edits are saved" (line 305).

Modifying and reverting to original values restores clean: the `useMemo` recomputes on every render. Test "returns to clean when text and allocation order are restored" (line 453) verifies text clearing and allocation reorder-then-unreorder.

Publish is blocked at three levels: (1) "Review for publication" button `disabled={dirty}` (line 445), (2) early return in `publish()` (line 422), (3) "Publish immutable Version" button `disabled={dirty || !confirmed || submitting}` (line 476). A dirty-state notice is displayed (line 449): "Save or discard local text and allocation changes before publication."

409/422 error handlers in both `save()` functions never call `onDirtyChange(false)`. No auto-save or auto-discard exists.

`handlePublished` (line 893) clears both dirty flags after successful publish.

### M-3 — Reload confirmation and local data protection

**Verdict: RESOLVED**

`requestWorkspaceReload` (lines 778-781) is the single reload entry point:

```typescript
const requestWorkspaceReload = useCallback(() => {
    if (dirty) setReloadConfirmation(true);
    else void loadWorkspace();
}, [dirty, loadWorkspace]);
```

When dirty, a confirmation panel appears (lines 924-933) stating "Reloading replaces unsaved text and allocation edits" and "Both Policy text and Draft allocation local changes will be lost." Two buttons: "Discard local changes and reload" and "Keep editing."

"Keep editing" dismisses the panel without any GET: `onClick={() => setReloadConfirmation(false)}` (line 931). Test "protects both editors from a reload and preserves them when the reload fails" (line 487) confirms `fetchMock.mock.calls.length` is unchanged after Keep editing.

"Discard local changes and reload" calls `loadWorkspace()`. If the reload fails, `workspaceEpoch` is not incremented (line 769 is in the success path only), so editor component keys remain stable and their internal `form`/`rows` state retains local values. The test verifies both text and allocation inputs survive a failed reload (lines 496-498).

On successful reload, `setTextDirty(false)`, `setAllocationsDirty(false)`, and `setWorkspaceEpoch((current) => current + 1)` are all called (lines 767-769). The epoch bump remounts editors with fresh server data.

All workspace reload paths use `requestWorkspaceReload`:
- Workspace status "Reload workspace" button (line 965)
- DraftTextEditor `onReload` prop (line 968)
- AllocationEditor `onReload` prop (line 969)
- PublishReview `onReload` prop (line 970)
- Load error "Try again" (line 919)
- Mutation error ConflictPanel (line 923)

The post-discard path calls `loadWorkspace()` directly (line 849), which is correct: the discard flow already has explicit user confirmation (lines 975-987).

The two confirmation types are distinct: the reload confirmation says "Discard local changes and reload" (local edits), while the discard confirmation says "Discard this Draft" (server Draft). They use separate state variables (`reloadConfirmation` vs `discardConfirmation`) and cannot be confused.

Double-click protection: after the first click opens the confirmation panel, the "Reload workspace" button is no longer visible. The confirmation buttons dismiss the panel on click.

### M-4 — Audit request coordination

**Verdict: RESOLVED**

All audit GETs share one `auditController` ref (line 642) and one `auditGeneration` ref (line 645). `refreshAudit` (lines 673-694):

```typescript
auditController.current?.abort();
const controller = new AbortController();
auditController.current = controller;
const generation = ++auditGeneration.current;
```

New request aborts old (line 674). Old success cannot overwrite new: `if (generation === auditGeneration.current && !controller.signal.aborted)` (line 682). Old failure cannot overwrite new: same guard at line 686. Abort does not show error: `!isAbort(caught)` at line 686.

Workspace load, mutation refresh, and manual retry all call `refreshAudit()`: workspace load (line 759), `acceptDraft` (line 797), `handlePublished` (line 895), retry button (line 1032).

Loading flag is cleared only by the current generation: `if (generation === auditGeneration.current && !controller.signal.aborted) setAuditLoading(false)` (line 692). An old request's finally block cannot clear a newer request's loading state.

Unmount aborts all three controllers in the cleanup effect (lines 786-790).

**Tests**: "lets only the newest audit refresh update the timeline" (line 501) resolves the second request first, then resolves the first, and confirms "policy.stale" never appears. "aborts an old audit request and ignores its later rejection" (line 522) confirms abort signal is set and stale rejection doesn't show an error.

Mutation success and audit failure are separate: `acceptDraft` sets the draft and saved message before calling `refreshAudit(true)`. If audit fails, the `afterMutation` flag produces the message "The Policy mutation succeeded, but the audit timeline could not be refreshed."

## Resolution matrix — LOW findings

### L-1 — History coordination and pagination

**Verdict: RESOLVED**

All history operations share `historyGeneration` ref (line 646) and `historyController` ref (line 643). `refreshHistory` (lines 696-720), `loadMoreHistory` (lines 856-884), and the clear-on-no-household path (line 740: `++historyGeneration.current`) all use the same generation counter.

`refreshHistory` aborts the shared `historyController` (line 697) and increments generation (line 700). A pending `loadMoreHistory` request fails its triple guard at line 868: `generation === historyGeneration.current && historyCursorRef.current === requestedCursor && !controller.signal.aborted`.

Load more validates both generation AND requested cursor before applying results. The `historyCursorRef` (line 648) is a ref, not React state, so it always reflects the latest value synchronously.

Deduplication uses stable version identity: `const byId = new Map(current.map((item) => [item.id, item]))` (line 870) — uses `item.id` (UUID), not `version_number`.

Double-click on Load more is prevented by `historyLoadingRef.current` (line 858): a synchronous ref check that blocks re-entry before React re-renders. Test "invalidates a pending Load more when workspace history refreshes" (line 570) confirms stale Load More data is discarded.

Detail requests in `VersionHistory` use their own `detailController` (line 526) but the component is keyed with `key={`history-${workspaceEpoch}`}` (line 1022), so a workspace reload remounts it and aborts the old detail controller via the cleanup effect.

### L-2 — Allocation no-op semantics

**Verdict: RESOLVED**

`normalizeAllocationDisplayName` (policy-api.ts lines 304-306):

```typescript
export function normalizeAllocationDisplayName(value: string): string {
  return value.normalize("NFKC").trim().replace(/\s+/gu, " ");
}
```

No case folding. Case is preserved. The old `normalizedName` function that applied `.toLocaleLowerCase()` is replaced.

`allocationsEqual` (lines 315-320) compares normalized display names without case folding. `Cash` to `CASH` produces different normalized strings ("Cash" vs "CASH"), so `allocationsEqual` returns false and the edit is dirty. Test "allows exactly 200 emoji and treats a case-only display edit as a save" (page.test.tsx line 630) confirms a PUT is sent for a case-only change.

`" Cash "` to `"Cash"` is a no-op: both normalize to "Cash". Unit test "treats display case as meaningful while normalizing Unicode whitespace and percentages" (policy-api.test.ts line 157) confirms `"  Cash\u00a0 Reserve  "` matches `"Cash Reserve"`.

Duplicate detection remains the backend's responsibility (422 response). The client surfaces the 422 error through the existing error handling path. Test at page.test.tsx line 353 confirms 422 retention.

No locale-sensitive lowercasing is used. `\s+` matches Unicode whitespace including `\u00a0` (non-breaking space), consistent with backend behavior.

### L-3 — Unicode character limit

**Verdict: RESOLVED**

The HTML `maxLength={200}` attribute is removed from the allocation name input (line 328). Test at page.test.tsx line 603 confirms `name.maxLength === -1`.

Validation uses `unicodeLength` (policy-client.tsx line 83-85): `Array.from(value).length` — counts Unicode code points, not UTF-16 code units. The allocation save guard (lines 264-270) rejects names exceeding 200 code points.

200 emoji accepted: test at line 630 types `"repeat 200 emoji"` and confirms a PUT is sent. 201 emoji rejected: test at line 597 types `"repeat 201 emoji"` and confirms the error "200 characters or fewer" with no PUT sent.

No silent truncation exists. On validation failure, `setError(...)` is called but `setRows` is not — the over-length input remains visible for user correction. The boundary test at line 609 confirms `199 ASCII + 1 emoji = 200 code points` is accepted, while `201 ASCII` is rejected.

Counting semantics match the Policy text fields and backend: all use `Array.from(value).length` for code-point counting. The review note that `Array.from` counts code points rather than grapheme clusters is acknowledged; the contract is Unicode characters/code points, not graphemes.

### L-4 — Error classification

**Verdict: RESOLVED**

`PolicyNetworkError` (policy-api.ts lines 108-113): a distinct error class for connection failures with message "The Policy service connection is unavailable."

`fetchResponse` (lines 134-141): wraps all `fetch()` calls. If fetch rejects with a non-abort error, it throws `PolicyNetworkError`. If fetch rejects with an AbortError, it re-throws without wrapping.

`neutralErrorMessage` (lines 115-128): status >= 500 returns "The Policy service returned an unexpected server error." The response body is never read — the message is a pure function of the HTTP status code.

Unit tests at policy-api.test.ts lines 95-110 verify that null body, non-JSON body, and body containing "secret-marker" all produce the same neutral message for HTTP 500 and 503.

Unit test at policy-api.test.ts lines 112-117 confirms `TypeError` (network failure) produces `PolicyNetworkError` while `DOMException("Aborted", "AbortError")` is re-thrown as-is.

Component test at page.test.tsx line 516 verifies both error classes render distinct messages, the save button recovers, and neither leaks sensitive data into the UI.

No sensitive data enters the UI: `request()` throws `PolicyApiError` based on status code only (line 145); response bodies for non-ok responses are never parsed.

### L-5 — Published-with-Draft

**Verdict: RESOLVED**

`CurrentPublishedSummary` (lines 626-637) renders when both Draft and Published exist:

```jsx
{published ? <CurrentPublishedSummary draft={draft} published={published} /> : null}
```

This is inside the `{workspaceReady && policy && draft ? (<>` block (line 960), so it appears alongside the Draft editors.

The component shows: version number ("Current Published Version · Version {N}"), publication time, "Published versions cannot be edited", and provenance.

Provenance logic: `draft.source_version_id === published.id ? "This Draft started from current Published." : "This Draft started blank."` (line 635).

Test "shows current Published provenance beside an editable Draft" (line 663) confirms the heading, provenance text, and absence of edit/delete/restore buttons. Test "labels blank Draft provenance without mixing it into Published content" (line 672) confirms "This Draft started blank" when `source_version_id` is null.

No `sealed_at` or `normalized_asset_class_name` is displayed. No edit, delete, restore, or historical copy action exists in the component. The Published section does not trigger any additional GET — it reuses the `published` state already loaded by `getCurrentPublished`.

History failure does not affect this section: `CurrentPublishedSummary` depends on `published` state, not `historyError`.

### L-6 — Accessible names

**Verdict: RESOLVED**

Each allocation row action button now has a unique `aria-label` incorporating the row's display name:

```jsx
aria-label={`Move ${row.asset_class_name.trim() || `allocation row ${index + 1}`} up`}
aria-label={`Move ${row.asset_class_name.trim() || `allocation row ${index + 1}`} down`}
aria-label={`Remove ${row.asset_class_name.trim() || `allocation row ${index + 1}`}`}
```

(lines 341-349)

When the name is empty, it falls back to `allocation row ${index + 1}`. Test at page.test.tsx line 688 confirms: after adding a new unnamed row, the fallback name is used.

Labels update when the name is edited: test at line 689-690 types "Owner category" and finds the button by the new name.

Labels track the row after reorder: test at line 339 confirms "Move Third user class up" after adding and naming a third row.

First/last disabled states are correct: `disabled={index === 0}` for Move up, `disabled={index === rows.length - 1}` for Move down (lines 341-342). Test at line 686 confirms first row's Move up is disabled, line 691 confirms last row's Move down is disabled.

The action container uses `role="group"` with `aria-label` describing the row (line 340).

Tests use `screen.getByRole("button", { name: ... })` throughout — accessing by accessible name, not DOM attributes.

## New findings

None. No new BLOCKER, HIGH, MEDIUM, LOW, or NON-BLOCKING issues were identified during this incremental review.

## Async coordinator review

Three independent coordinator domains are correctly isolated:

| Domain | Controller | Generation | Scope |
|---|---|---|---|
| Core workspace | `loadController` | `loadSequence` | Household + Policy + Draft + Published |
| History | `historyController` | `historyGeneration` | Version list, Load more, detail |
| Audit | `auditController` | `auditGeneration` | Audit event timeline |

Each coordinator follows the same pattern: abort previous, create new controller, increment generation, check generation + aborted signal before committing results, check generation + aborted signal in finally before clearing loading.

The cleanup effect (lines 785-790) aborts all three controllers on unmount. The no-household/no-policy path (lines 737-752) aborts and invalidates history and audit coordinators explicitly.

No cross-domain generation contamination was found. The `loadWorkspace` callback lists `[refreshAudit, refreshHistory]` as dependencies (line 776), which are stable `useCallback` references with empty dependency arrays — correct.

## Dirty-state transition review

| Transition | Implementation | Correct |
|---|---|---|
| Initial clean | `setTextDirty(false); setAllocationsDirty(false)` in `loadWorkspace` success | Yes |
| Type in text field | `useMemo` recomputes, `onDirtyChange(true)` via effect | Yes |
| Save text | `onDirtyChange(false)` in save try block, text dirty cleared only | Yes |
| Save allocation | `onDirtyChange(false)` in save try block, allocation dirty cleared only | Yes |
| Revert to server value | `useMemo` recomputes, `onDirtyChange(false)` via effect | Yes |
| Reorder then un-reorder | `allocationsEqual` recomputes, dirty returns to false | Yes |
| 409/422 on save | Error set, dirty NOT cleared | Yes |
| Publish success | `handlePublished` clears both dirty flags | Yes |
| Reload success | `loadWorkspace` clears both dirty, bumps epoch | Yes |
| Reload failure | Dirty preserved (epoch not bumped) | Yes |
| Unmount | Editor cleanup effect does not reset parent dirty | Yes |

The `onDirtyChange` effect pattern cannot produce render loops because: (1) `dirty` only changes when the comparison result changes, (2) `onDirtyChange` is a stable state setter, (3) setting the same boolean value is a React no-op.

## Test credibility review

### Test count and structure

The suite grew from 37 to 62 tests across 4 files. The 25 new tests directly target the behaviors identified in M-1 through M-4 and L-1 through L-6.

| File | Tests | New |
|---|---:|---:|
| page.test.tsx (component) | 39 | 20 |
| policy-api.test.ts (API client) | 13 | 5 |
| household page + health | 10 | 0 |

### New deferred-promise tests

A `deferred<T>()` helper (page.test.tsx lines 103-112) provides explicit control over promise resolution order. Tests using it:

- "lets only the newest audit refresh update the timeline" — resolves second first, then first; confirms stale data is rejected
- "aborts an old audit request and ignores its later rejection" — confirms abort signal and no error display
- "lets only the newest history refresh update the collection" — same deferred pattern for history
- "invalidates a pending Load more when workspace history refreshes" — stale cursor data rejected

These tests use deterministic resolution order, no sleep, and properly resolve all promises.

### Mock API response fidelity

The `serverFetch` fixture was improved: PATCH responses now merge from the current `state.draft` (not a fixed template), and sequential saves build on the previous snapshot. This more accurately reflects the FastAPI response model where each PATCH returns the updated Draft.

### Coverage of original gaps

| Original gap | Now covered |
|---|---|
| Auxiliary history failure | Yes |
| Dirty-state publish blocking | Yes |
| Reload discards local edits | Yes |
| Stale audit response race | Yes |
| Stale history pagination | Yes |
| Case-only allocation update | Yes |
| Emoji boundary | Yes |
| Network vs server error | Yes |
| Published-with-Draft view | Yes |
| Accessible row names | Yes |

## Scope and documentation confirmation

- Backend, migration, dependency, lockfile, Compose, CI, and environment files: **not modified** (verified by `git diff --stat` on those paths — empty output)
- Only 4 source file groups modified: `policy-client.tsx`, `page.test.tsx`, `policy-api.ts`, `policy-api.test.ts`, plus 4 docs files
- No Slice 3 work
- No AI, Guardian, Broker, recommendation, scoring, or trading logic
- No autosave or mutation auto-retry
- MASTER_PLAN.md: correctly records "Slice 2C remains in Review and PR #9 remains Draft pending independent incremental review"
- CHANGELOG.md: correctly records "PR #9 remains Draft after its initial REQUEST CHANGES review"
- ARCHITECTURE.md: correctly describes the new isolation, dirty tracking, generation guards, and error classification
- PRD.md: correctly adds dirty-state publication gate, reload confirmation, and auxiliary resource independence
- No premature Slice 2C Done or APPROVE marking
- All existing Backlog items preserved

## Exact commands and results

| Command | Result |
|---|---|
| `git status` | Branch `sprint/002-policy-frontend`, tracked/staged clean, 22 untracked review files |
| `git rev-parse HEAD` | `c732569a2a22fd9846c6fa064993d4ea0514754b` |
| `gh pr view 9` | OPEN, Draft, MERGEABLE |
| `gh pr checks 9` | All 6 checks passed |
| `gh run list` | 4 most recent runs all completed successfully |
| `git diff --stat 917e64b...c732569` | 8 files, 674 insertions, 110 deletions |
| `git diff --check 917e64b...c732569` | Passed |
| `npm ci` | Clean install |
| `npm run lint` | All checks passed |
| `npm run type-check` | Zero TypeScript errors |
| `npm test` | 4 files, 62 tests passed |
| `vitest run app/policy/page.test.tsx` | 39 tests passed |
| `vitest run lib/policy-api.test.ts` | 13 tests passed |
| `vitest run --shuffle --seed=42` | 62 tests passed |
| `npm run build` | Next.js 16.2.10 production build passed |
| `npm audit --omit=dev` | 0 vulnerabilities |
| `pip check` | No broken requirements |
| `ruff check apps tests` | All checks passed |
| `compileall -q apps/api` | Passed |
| `pytest -q -m 'not postgres'` | 43 passed, 74 deselected |
| YAML parse `compose.yaml` | Passed |

## Unverified items

- Full Docker runtime and full-stack browser workflow (Docker CLI unavailable locally; retained as non-blocking Backlog)
- Real-browser focus, layout, and assistive-technology behavior beyond static/jsdom review
- Local real PostgreSQL run (instead verified by both required GitHub CI backend jobs targeting the fix commit, each running 74 real PostgreSQL tests with zero skips)

## Final conclusion

**APPROVE**

| Finding | Status |
|---|---|
| M-1 — Auxiliary resource isolation | RESOLVED |
| M-2 — Dirty state and publish blocking | RESOLVED |
| M-3 — Reload confirmation and local data protection | RESOLVED |
| M-4 — Audit request coordination | RESOLVED |
| L-1 — History coordination and pagination | RESOLVED |
| L-2 — Allocation no-op semantics | RESOLVED |
| L-3 — Unicode character limit | RESOLVED |
| L-4 — Error classification | RESOLVED |
| L-5 — Published-with-Draft | RESOLVED |
| L-6 — Accessible names | RESOLVED |

New findings: BLOCKER 0, HIGH 0, MEDIUM 0, LOW 0, NON-BLOCKING 0.

All four MEDIUM findings are fully resolved with appropriate async coordinator isolation, generation guards, dirty-state tracking, and explicit user confirmation. All six LOW findings are fully resolved with correct Unicode handling, error classification, accessible names, and provenance display. The test suite grew from 37 to 62 tests with deterministic deferred-promise race tests that would reliably fail on the old implementation. No regressions were introduced.

The PR remains within the authorized Slice 2C scope. No backend, migration, dependency, or infrastructure change was made. All documentation accurately reflects the current state without premature completion claims.

Slice 2C remains in Review. PR #9 remains Draft and may be marked ready for merge at the project owner's discretion. Slice 3 remains unauthorized and Not Started.
