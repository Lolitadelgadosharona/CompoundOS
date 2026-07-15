# Product Requirements Document

## Status

Approved behavior includes the Slice 1 Household workflow and the Slice 2B
local-only Investment Policy backend API. Slice 2A is Done. Slice 2B is in Review;
Slice 2C and Slice 3 are not authorized.

## Summary

Slice 1 provides a local, single-user HouseholdProfile record with PostgreSQL
persistence and an append-only AuditEvent timeline. It records user-entered
context without interpreting it or providing investment advice.

Slice 2B records user-authored Investment Policy Draft text and target allocation
percentages, publishes immutable Version snapshots, and exposes version and audit
reads. It provides no frontend and never evaluates the recorded information.

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
