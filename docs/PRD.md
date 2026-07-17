# Product Requirements Document

## Status

Approved behavior includes the Slice 1 Household workflow, the Slice 2B local-only
Investment Policy backend API, the Slice 2C local-only Policy frontend, the
Slice 3B Decision Journal backend API, and the Slice C Portfolio frontend.
Sprint 002 is Done; Sprint 003 (Slices A, B, C) is Done; Sprint 004 (Slices A, B, C) is Done.
Sprint 005 is Not Authorized.

## Summary

Slice 1 provides a local, single-user HouseholdProfile record with PostgreSQL
persistence and an append-only AuditEvent timeline. It records user-entered
context without interpreting it or providing investment advice.

Slice 2B records user-authored Investment Policy Draft text and target allocation
percentages, publishes immutable Version snapshots, and exposes version and audit
reads. It provides no frontend and never evaluates the recorded information.

Slice 2C provides the `/policy` user interface for those approved contracts. It
supports explicit user-authored Draft saves, mechanical publication review,
immutable Version reads, and a Policy-filtered audit timeline without interpreting
the content or providing investment advice.

## Slice 2B Backend Requirements

- The sole Household owns at most one stable Policy and one editable Draft.
- Draft text updates and whole-allocation replacement require an expected revision,
  reject no-ops, and commit one redacted AuditEvent atomically.
- Allocation percentages are decimal strings with at most two places; Draft totals
  may be incomplete, while publication mechanically requires exactly `100.00`.
- Publication requires non-whitespace `objectives`, `time_horizon`, and
  `decision_process`, without judging their meaning or quality.
- Publication creates immutable Version snapshots and consumes the Draft in one
  Policy-then-Draft locked transaction.
- Reads expose current metadata, Draft, current Published Version, cursor-based
  newest-first history, immutable Version detail, and a limited Policy audit window.
- Responses never expose normalized names, sealing internals, or sensitive Audit metadata.

## Slice 2B Explicit Non-Goals

- Policy frontend or frontend API client
- Advice, recommendations, evaluation, suitability, eligibility, scores, rankings,
  compliance conclusions, rebalancing calculations, or trades
- Decision Journal, Guardian, AI, Broker, market, holdings, accounts, authentication,
  multiple households/users, export, or hard-delete workflows

## Slice 2C Frontend Requirements

- Initial Household and Policy reads are parallel, abortable, and protected from
  stale-response replacement.
- A missing Household links to `/household` and cannot create a Policy. An empty
  Policy state can create the sole blank Draft without sending explicit JSON `null`.
- The Draft editor exposes the ten approved user-input fields with explicit saves,
  Unicode character limits, changed-field-only PATCH requests, expected revisions,
  neutral conflict/validation feedback, and no suggested text or autosave.
- The allocation editor supports local add, remove, and accessible reordering, then
  explicitly replaces the complete ordered collection. It supplies no default asset
  classes or target percentages.
- Allocation display-name no-op comparison preserves case after NFKC, trim, and
  whitespace normalization. Names use a 200 Unicode code-point technical limit,
  and every row action has a row-specific accessible name.
- Allocation inputs remain decimal strings. The displayed total uses integer
  hundredths and reports only mechanical equality with `100.00`; it never scores or
  evaluates the allocation.
- Publication shows a read-only saved Draft snapshot, required-field presence,
  exact total, and current revision. It requires explicit confirmation and sends
  `confirmation: true`; the server remains authoritative.
- Publication review is unavailable while either editor contains semantic local
  changes. Reloading a dirty workspace requires an explicit choice to discard both
  editors' local changes or keep editing; a failed reload retains local state.
- Published and historical Versions are immutable and read-only. New Drafts may be
  blank or copied only from the current Published Version; historical restore/copy,
  Published editing, and product deletion are absent.
- The audit timeline preserves the server-returned sequence order and discloses the
  latest-window/no-cursor boundary. Audit refresh errors are independent from
  successful mutations, and retry performs only the audit GET.
- Draft discard requires explicit confirmation and an expected revision; it never
  deletes the Policy or immutable Versions.
- The page visibly states its local-only, non-production, no-authentication, and
  non-advisory boundary.

## Slice 2C Acceptance Criteria

- Loading, missing Household, empty Policy, Draft, publish review, current
  Published, history, audit, and discard states are accessible at `/policy`.
- Duplicate mutation submissions are prevented; mutations are not automatically
  retried, and 409 conflicts offer an explicit server reload without overwriting
  local input.
- Text and allocation no-ops issue no mutation. Successful saves adopt the complete
  server snapshot and revision; failures retain local edits.
- Exact decimal-string examples such as `0.10 + 0.20`, `99.99`, `100.00`, and
  `100.01` display without binary floating-point artifacts or silent rounding.
- Publication requires the three approved fields, exactly `100.00`, and explicit
  confirmation while remaining subject to server validation.
- Version history paginates newest first without duplicate entries, remains
  immutable, and offers no restore or historical-copy action.
- Core Draft/Published state remains usable when history or audit fails. History
  and audit retries are isolated GETs, and stale auxiliary responses cannot replace
  the result of a newer reload, refresh, publication, or cursor request.
- Policy audit failures never recast a completed Policy mutation as failed, and
  the retry cannot replay that mutation.
- UI and API-client tests cover the approved flows, error classes, request payloads,
  cleanup, non-advisory copy, and prohibited action boundaries.

## Slice 2C Explicit Non-Goals

- Advice, recommendations, suitability, eligibility, scoring, rankings, asset-class
  defaults, rebalancing or drift calculations, and automated decisions
- Decision Journal, Guardian thresholds or alerts, AI, Broker or market integration,
  actual holdings, accounts, monetary amounts, authentication, or public deployment
- Backend contract or behavior changes, database changes, new dependencies, product
  deletion, historical restore/copy, Published editing, or Slice 3

## User Stories

- As the local owner, I can create the sole HouseholdProfile.
- As the local owner, I can refresh and retrieve the persisted profile.
- As the local owner, I can update approved profile fields.
- As the local owner, I can inspect a read-only, stably ordered audit timeline.
- As the local owner, I receive a 409 if any later create is attempted.

## Approved Fields and Technical Limits

- `household_name`: required, trimmed, 1–200 characters
- `base_currency`: required, exactly three uppercase ASCII letters
- `investment_horizon`: optional free text, at most 2,000 characters
- `liquidity_needs`: optional free text, at most 4,000 characters
- `risk_statement`: optional free text, at most 4,000 characters
- `notes`: optional free text, at most 8,000 characters

These are input-safety limits, not investment rules. `base_currency` is stored as
context only; no conversion occurs. `risk_statement` is never interpreted. The
same limits are enforced in the API contract and by named PostgreSQL constraints
using character length rather than byte length.

## Lifecycle and Audit Boundary

- The database permits at most one HouseholdProfile in total.
- The first create succeeds; every later create returns HTTP 409.
- Clients cannot supply identifiers, actors, or timestamps.
- Slice 1 has no household active, inactive, archived, deleted, or replacement
  state and no product delete endpoint.
- Create and actual update append an AuditEvent in the same transaction.
- Empty and no-op PATCH requests return HTTP 400 and do not create AuditEvents.
- Audit metadata lists changed field names only; it does not copy sensitive text.

## Local-Only Requirements

- No authentication or authorization is implemented.
- The application is limited to local, single-user development.
- Web, API, PostgreSQL, and Redis host ports bind to `127.0.0.1` by default.
- Public internet exposure is prohibited.
- The approved non-advisory notice appears on first entry to the household flow.

## Acceptance Criteria

- Create returns 201, persists through refresh, and emits an atomic AuditEvent.
- Current GET returns the profile or a clear 404.
- Approved PATCH fields persist and emit an atomic AuditEvent.
- Undeclared fields and client-controlled server fields are rejected without
  echoing sensitive values.
- Database constraints prevent a second profile, including concurrent attempts.
- Audit events are read-only, stably ordered, attributed to `local-owner`, and
  contain no full sensitive field values.
- Alembic upgrades an empty PostgreSQL database to head, and integration tests use
  real PostgreSQL.
- Household UI covers loading, empty, create, summary, edit, 409, error, and audit
  states with the required local-only and non-advisory notices.
- A successful create/update remains visibly successful if the following audit
  refresh fails; the existing timeline remains available and a retry performs only
  the audit GET without replaying the mutation.
- CI explicitly requires the PostgreSQL-marked suite and fails rather than skips
  when its real database URL is unavailable.
- Existing health, lint, type-check, test, build, audit, Compose, and CI checks pass.

## Explicit Non-Goals for Slice 1

- Investment Policy, target asset allocation, policy lifecycle, Decision Journal,
  or DecisionCorrection
- AI, AI Investment Committee, Guardian logic, thresholds, alerts, or notifications
- Broker integrations, market data, recommendations, suitability, eligibility,
  scores, rankings, or trading
- Authentication, authorization, household members, multiple households, or tenancy
- Accounts, holdings, amounts, balances, quantities, prices, costs, returns, or trades
- Export, product hard delete, Redis product logic, public deployment, or Slice 2
