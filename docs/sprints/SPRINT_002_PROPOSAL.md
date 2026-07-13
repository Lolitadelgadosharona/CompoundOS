# Sprint 002 Proposal: Household Discipline Foundation

## Status

**Selected for Implementation Planning — Implementation Not Started**

This document records approved product-planning decisions. It does not authorize
Sprint 002 implementation. Implementation still requires explicit final approval
after the planning pull request is reviewed and merged.

## Product Owner Decision

- **Selected proposal:** A — Household Investment Policy + Decision Journal
- **Product owner decision date:** 2026-07-13
- **Planning status:** Selected for implementation planning
- **Implementation status:** Not Started
- **Approval gate:** Implementation requires explicit final approval after this
  planning pull request merges

## Approved MVP Loop

Single household profile → investment policy draft → target asset allocation
percentages → explicitly confirm and publish a policy version → create a decision
journal entry → reference the policy version in effect when the decision was
recorded → review history that cannot be silently rewritten.

## Approved Product Boundaries

### Household Scope

- Support exactly one household owned by the project owner.
- The database may contain at most one active `HouseholdProfile`.
- A second household-creation request returns an explicit conflict response, such
  as HTTP 409.
- A caller cannot bypass the constraint by supplying a different `household_id`.
- This is a local single-household product constraint, not authentication or tenant
  isolation.
- Do not implement household members, invitations, roles, permissions,
  collaboration, multiple households, or multi-tenancy.
- Use the fixed audit actor identifier `local-owner`.
- `local-owner` identifies local single-user development mode; it is not an
  authenticated identity.

### Minimum Household Profile

- `household_name`
- `base_currency`
- `investment_horizon`
- `liquidity_needs`
- `risk_statement`
- `notes`

`base_currency` expresses policy context only. Sprint 002 performs no currency
conversion or monetary calculation and stores no household-member personal
identity information.

### Investment Policy Categories

- `objectives`
- `time_horizon`
- `liquidity`
- `target_asset_allocation`
- `diversification`
- `contribution_policy`
- `rebalancing_policy`
- `prohibited_assets`
- `leverage_policy`
- `decision_process`
- `notes`

All policy content is entered by the user. CompoundOS does not generate investment
rules, recommended values, or policy conclusions.

### Target Asset Allocation

- Store only user-entered asset-class names and target percentages.
- Target percentages must total 100%.
- Do not recommend percentages or provide a preset “best” allocation.
- Do not store or compare actual holdings.
- Do not calculate drift or generate rebalancing suggestions.

### Policy Lifecycle

- Investment Policy states are `Draft`, `Published`, and `Superseded`.
- A Draft is editable in place. Draft edits create `AuditEvent` records, but the
  system need not snapshot every keystroke or autosave.
- Publish creates an immutable Published `InvestmentPolicyVersion`.
- A Published version cannot be modified in place or physically deleted.
- Changing Published content requires creating a new Draft from that version.
- Publishing the new Draft may mark the prior Published version Superseded.
- Superseded changes status only and never changes historical version content.
- The system never judges whether policy content is reasonable, compliant, or
  suitable for the user.

### Decision Journal Minimum Fields

- `title`
- `decision_date`
- `decision_type`
- `summary`
- `supporting_reasons`
- `opposing_reasons`
- `assumptions`
- `uncertainties`
- `policy_version_reference`
- `final_decision`
- `review_date`
- `status`
- `created_at`
- `updated_at`

Decision Journal Entry states are `Draft`, `Confirmed`, and `Archived`. All content
is manually entered. A Draft is editable. Confirm creates a Confirmed revision that
cannot be silently rewritten and must reference a Published policy version.
Confirmed revisions may be Archived but not physically deleted. Corrections append
a Correction revision containing `corrected_entry_id`, `correction_reason`,
`created_at`, and `actor`; they never overwrite the original Confirmed content.
`updated_at` applies only to Draft content or status metadata and never implies
in-place modification of Confirmed content.

The system does not generate advice, scores, approvals, suitability conclusions,
AI output, Guardian output, broker actions, trades, or transactions.

### Risk, Guardian, and AI Boundaries

- `risk_statement` is user-authored free text only.
- Do not define Guardian thresholds, run risk detection, or trigger notifications.
- Do not implement AI generation, summaries, scoring, discussions, agents, or AI
  Investment Committee behavior.
- Preserve policy versions and journal records only as auditable context for
  separately approved future work.

### Asset and Monetary Data Boundary

- Do not store actual holdings, securities quantities, accounts, balances,
  investment amounts, cost basis, current prices, returns, or transactions.
- Target allocation percentages are policy statements, not portfolio data.
- Do not connect market data or brokers.

### Persistence Direction

- Use PostgreSQL as formal Sprint 002 persistence; product data cannot use
  process-local memory as formal persistence.
- Implementation requires migrations that can upgrade an empty database.
- Multi-record business writes and their `AuditEvent` records commit in the same
  database transaction and roll back together on failure.
- CI requires a PostgreSQL service container or equivalent isolated PostgreSQL.
- Repository/integration tests run against real PostgreSQL. SQLite or mocks may
  support unit tests but cannot replace PostgreSQL integration tests.
- Redis carries no Sprint 002 product logic.
- This planning task creates no schema or migration; persistence design still
  requires implementation authorization and architecture review.

### Local-Only Security Boundary

- Sprint 002 has no authentication.
- Operation is limited to local development.
- Public internet deployment is prohibited until authentication and security
  review are separately approved.
- Future README and product UI must display this limitation clearly.
- Do not claim production-grade privacy or compliance readiness.
- Host ports for web, API, PostgreSQL, and Redis default to `127.0.0.1` only, for
  example `127.0.0.1:3000:3000`, `127.0.0.1:8000:8000`,
  `127.0.0.1:5432:5432`, and `127.0.0.1:6379:6379`.
- Containers may listen on `0.0.0.0` internally when required. Localhost host-port
  binding is not a substitute for authentication or production security.

### Approved Local-MVP Non-Advisory Copy

The following provisional copy must be visible on first entry to the core flow,
before publishing a policy, and before confirming a decision journal entry:

> CompoundOS records information you enter. It does not evaluate whether an
> investment policy or decision is suitable, appropriate, or likely to succeed.
> Policy links and validations are for recordkeeping only and do not constitute
> investment, tax, or legal advice.

This is temporary local-MVP copy, is not represented as lawyer-reviewed, and must
receive legal and compliance review before any remote, production, or commercial
use. Sprint 002 does not implement complex consent management.

### Approved Local-MVP Retention Boundary

- Sprint 002 provides no data export and no general-purpose hard-delete API.
- Published policy versions, Confirmed journal revisions, and `AuditEvent` records
  cannot be physically deleted.
- Drafts may be discarded before publication or confirmation.
- A documented development-only database reset command may clear all local data.
- Database reset is not a product deletion feature.
- Backup, long-term retention, user export, compliance deletion, and encryption-key
  management are deferred to future approved sprints and become blockers before
  any non-local or production use.

### Docker Boundary

- Full Docker runtime verification remains a non-blocking Backlog item.
- If the Sprint 002 execution environment provides Docker, Definition of Done
  requires runtime verification.
- If Docker remains unavailable, completion reporting must disclose that fact
  accurately and must not fabricate validation.

## 1. Problem Statement

CompoundOS has a validated technical foundation but no approved user workflow.
Households need a disciplined way to capture their context, state their own
investment policy, and preserve the reasoning behind decisions. Without that
foundation, later portfolio monitoring, Guardian, or committee workflows would
lack an approved source of constraints and an auditable decision history.

The system must support structured recordkeeping without interpreting the records
as personalized investment advice, predicting markets, executing trades, or
silently inventing policy.

## 2. Sprint Objective

Propose a small, demonstrable discipline workflow that can eventually let a user
record household context, owner-approved policy statements, and decision-journal
entries with traceable rationale. The Sprint 002 implementation objective remains
unapproved until the project owner selects a candidate, resolves blocking
questions, and approves detailed scope.

## 3. Candidate Comparison

### Option A: Household Investment Policy + Decision Journal

- **User value:** Establishes why the household invests, what constraints it has,
  and how decisions are documented before outcomes are known.
- **Four-principle fit:** Strongest fit. It centers capital protection,
  compounding horizon, discipline, and explainable records without prediction.
- **End-to-end loop:** Household profile → owner-authored policy → journal entry →
  link to policy → review an immutable history of revisions.
- **Data needed:** Household profile, goals, horizons, liquidity statements, risk
  boundary statements, policy versions, decision entries, arguments, assumptions,
  uncertainties, policy links, and audit events.
- **Safety/compliance risk:** Medium. Policy language could be mistaken for advice
  unless clearly owner-entered and neutrally displayed. Sensitive household data
  raises privacy obligations.
- **Technical complexity:** Medium. Requires coherent versioning and auditability,
  but no market data or calculation engine.
- **Future foundation value:** High for Guardian and AI Investment Committee
  because they will eventually need explicit, approved policy context. Moderate
  for broker integration because policies and journals are independent of broker
  data.
- **Scope-expansion risks:** Policy scoring, recommendations, household member
  permissions, document ingestion, rich collaboration, workflow approvals, or
  automated compliance conclusions.
- **Explicit exclusions:** Advice, suitability determinations, policy templates
  presented as authoritative, automated rule evaluation, alerts, AI analysis,
  trades, broker connections, authentication, and portfolio calculations.
- **Suggested priority:** 1.

### Option B: Portfolio Snapshot + Manual Holdings

- **User value:** Gives the household a consolidated, manually maintained view of
  holdings and cash without waiting for broker integrations.
- **Four-principle fit:** Moderate. Visibility can support discipline and capital
  protection, but a snapshot alone does not encode why decisions were made.
- **End-to-end loop:** Create portfolio → enter holdings manually → view totals and
  allocation snapshot → update as-of date.
- **Data needed:** Accounts, manual holdings, quantities, user-entered prices or
  values, currencies, asset labels, cash, valuation date, and provenance.
- **Safety/compliance risk:** Medium to high. Stale prices, incorrect totals, asset
  classification, and prominent allocation views may be perceived as advice or
  monitoring even when they are only user-entered records.
- **Technical complexity:** Medium to high. Currency, valuation, decimal precision,
  duplicate assets, stale data, and reconciliation rules create complexity.
- **Future foundation value:** High for future read-only broker integration and
  Guardian; moderate for the AI Investment Committee. It lacks policy context.
- **Scope-expansion risks:** Live pricing, performance calculations, allocation
  targets, rebalancing, tax lots, benchmarks, alerts, and broker sync.
- **Explicit exclusions:** Market-data feeds, performance analytics, rebalancing,
  recommendations, trade execution, tax calculations, alerts, and broker APIs.
- **Suggested priority:** 2, after policy and provenance decisions are approved.

### Option C: Investment Idea Intake + Rule-Based Eligibility Check

- **User value:** Structures an idea before action and could show whether required
  owner-authored information is missing.
- **Four-principle fit:** Potentially strong for discipline and explainability, but
  a pass/fail result can easily appear to be an investment recommendation.
- **End-to-end loop:** Submit idea → select applicable owner-approved rules → record
  evidence → receive a procedural completeness result → retain history.
- **Data needed:** Ideas, instruments or opportunity descriptions, thesis,
  assumptions, evidence, rule versions, rule applicability, owner attestations,
  and evaluation records.
- **Safety/compliance risk:** Highest. “Eligibility” can be interpreted as
  suitability, approval, or advice. Unapproved rules or thresholds would be
  especially risky.
- **Technical complexity:** High. Requires a rule representation, versioning,
  deterministic evaluation semantics, exception handling, and careful language.
- **Future foundation value:** High for the AI Investment Committee and Guardian;
  lower for broker integration. It depends on an approved policy/rule foundation
  that does not yet exist.
- **Scope-expansion risks:** Recommendation scores, automated approval, market-data
  enrichment, AI research, alerts, committee voting, and trade handoff.
- **Explicit exclusions:** Advice, suitability claims, ranking, scoring,
  autonomous approval, AI agents, alerts, market prediction, and execution.
- **Suggested priority:** 3; defer until owner-approved policies and rule semantics
  exist.

## 4. Recommended Option and Rationale

**Selected direction: Option A — Household Investment Policy + Decision Journal.**

**Implementation approval state: Not Started; not yet authorized.**

The product owner selected Option A because it provides the strongest foundation
for CompoundOS's discipline and
explainability principles while avoiding market data, portfolio calculations, and
rule-engine semantics. It creates policy provenance needed by Options B and C and
by future Guardian or committee work. The approved product boundaries are recorded
above; implementation still depends on final approval after this planning pull
request merges.

## 5. Proposed User Journey

1. The user sees a clear notice that CompoundOS is recording user-provided policy
   and decisions, not providing investment advice.
2. The user creates a household profile with a display name and optional planning
   context approved for this sprint.
3. The user records long-term goals, time horizons, liquidity needs, and risk
   boundary statements in their own words.
4. The user reviews a Draft and explicitly publishes an immutable Published policy
   version.
5. The user creates a decision-journal entry describing an idea or decision,
   rationale, counterarguments, assumptions, uncertainties, and decision status.
6. The user links the journal Draft to the Published policy version in effect
   without the system judging compliance or quality.
7. The user confirms the journal entry, creating an immutable Confirmed revision.
8. The user reviews policy versions, journal corrections, and audit history that
   cannot be silently rewritten.

## 6. Proposed Scope

- Exactly one household workspace for the project owner in local development.
- Structured capture of owner-provided household planning context.
- Draft policies and immutable Published policy versions with explicit identifiers.
- Decision-journal creation and read views.
- Structured fields for rationale, counterarguments, assumptions, uncertainties,
  and status.
- Links from Confirmed journal revisions to Published policy versions.
- Audit events for create, edit draft, publish policy, confirm journal, correct,
  archive, and supersede actions.
- Neutral, non-advisory labels and disclaimers.
- Minimal end-to-end UI and API contracts necessary to demonstrate the workflow.

## 7. Explicit Non-Goals

- Investment recommendations, suitability determinations, or personalized advice.
- Automatic trading, order preparation, or execution.
- Broker or market-data integrations.
- Manual holdings, portfolio valuation, performance, or rebalancing.
- AI agents, AI Investment Committee behavior, AI-generated analysis, or voting.
- Guardian monitoring, alerts, thresholds, or escalation.
- Rule engines, automated eligibility, scores, rankings, or pass/fail conclusions.
- Authentication, authorization, invitations, household members, collaboration,
  multiple households, and multi-tenancy.
- Prescriptive investment policy templates or invented investment rules.
- Database schema or migrations during planning.
- Actual holdings, securities quantities, accounts, balances, investment amounts,
  costs, prices, returns, or transactions.
- Notifications, document uploads, OCR, imports, or exports.

## 8. Proposed Frontend Scope

- Household profile form and read-only summary.
- Policy editor organized by approved conceptual categories, with Draft, Published,
  and Superseded states and visible version metadata.
- Decision-journal form and detail view.
- Policy-link selector that only references Published user-authored policy versions.
- Revision/audit timeline showing actor label, action, and timestamp.
- Approved local-MVP non-advisory copy on flow entry, before policy publication,
  and before journal confirmation.
- Accessible validation messages for missing required recordkeeping fields.

No visual design, component library, route structure, or state-management choice
is approved by this proposal.

## 9. Proposed Backend Scope

- API contracts for household profile, policy drafts/versions, journal entries,
  policy links, and audit-event reads.
- Enforce at most one active household transactionally; return a clear conflict
  response such as HTTP 409 for any second creation attempt, regardless of a
  caller-supplied `household_id`.
- Input validation for required recordkeeping fields and allowed lifecycle states.
- Explicit policy publish/supersede operations and journal confirm/correct/archive
  operations.
- Server-generated identifiers, timestamps, version references, and audit events.
- Neutral retrieval only; no recommendation, scoring, rules evaluation, or alerts.

Persistence technology, service/module boundaries, and transaction behavior remain
implementation decisions requiring architecture review.

## 10. Proposed Data Entities (Conceptual Only)

These are domain concepts, not database schemas:

- **HouseholdProfile:** The approved minimum fields for the one local household.
- **HouseholdGoal:** User-authored objective, horizon, priority label, and notes.
- **LiquidityNeed:** User-authored description and timing context without monetary
  calculations.
- **RiskBoundaryStatement:** Freeform owner statement, not a computed tolerance or
  system threshold.
- **InvestmentPolicy:** Stable identity for a household policy.
- **InvestmentPolicyDraft:** Editable working policy content derived initially or
  from a Published version.
- **InvestmentPolicyVersion:** Immutable Published policy content with Published or
  Superseded status.
- **PolicyStatement:** Versioned, user-authored policy section or statement.
- **DecisionJournalEntry:** Stable identity for a decision journal.
- **DecisionJournalRevision:** Draft, Confirmed, Archived, or Correction revision;
  a Correction includes `corrected_entry_id`, `correction_reason`, `created_at`,
  and `actor` without overwriting original Confirmed content.
- **DecisionArgument:** Supporting or opposing reason supplied by the user.
- **DecisionAssumption:** User-stated assumption and optional uncertainty note.
- **PolicyReference:** Link from a journal entry to a specific policy version and
  statement.
- **AuditEvent:** Append-only record of create, edit draft, publish policy, confirm
  journal, correct, archive, and supersede actions.

## 11. API Endpoint Proposals (Contracts Only)

Names are illustrative and not approved routes:

- `POST /api/households` — create the sole active household profile; return HTTP
  409 when one already exists, including attempts using a different supplied ID.
- `GET /api/households/{household_id}` — retrieve the profile.
- `PATCH /api/households/{household_id}` — revise allowed profile fields and emit
  an audit event.
- `POST /api/households/{household_id}/policies` — create a policy draft.
- `GET /api/policies/{policy_id}` — retrieve current policy metadata.
- `POST /api/policies/{policy_id}/drafts` — create a new editable Draft, optionally
  derived from a Published version.
- `PATCH /api/policies/{policy_id}/drafts/{draft_id}` — edit a Draft and emit an
  AuditEvent without requiring a full snapshot per keystroke/autosave.
- `POST /api/policies/{policy_id}/versions/{version_id}/publish` — publish an
  immutable version; no evaluation is performed.
- `GET /api/policies/{policy_id}/versions` — list version metadata.
- `POST /api/households/{household_id}/journal-entries` — create a journal entry.
- `GET /api/journal-entries/{entry_id}` — retrieve an entry and policy references.
- `PATCH /api/journal-entries/{entry_id}/draft` — edit only the journal Draft and
  emit an AuditEvent; never mutate Confirmed content.
- `POST /api/journal-entries/{entry_id}/confirm` — create a Confirmed revision that
  references a Published policy version.
- `POST /api/journal-entries/{entry_id}/corrections` — append a Correction revision
  without overwriting Confirmed content.
- `POST /api/journal-entries/{entry_id}/archive` — archive a Confirmed revision
  without physical deletion.
- `GET /api/households/{household_id}/audit-events` — retrieve audit history.

Contracts must use neutral errors and never return advice, eligibility, score,
approval, or trade instructions.

## 12. Auditability Requirements

- Every Published policy version has a stable identifier and publication time.
- Journal policy links target a specific immutable policy version.
- Create, edit draft, publish policy, confirm journal, correct, archive, supersede,
  and link-change actions are attributable and timestamped.
- Historical Published policy and Confirmed journal content cannot be silently
  overwritten.
- Draft edits create AuditEvents without requiring a full content snapshot for
  every keystroke or autosave.
- Business writes and AuditEvents commit or roll back in one PostgreSQL transaction.
- Audit events distinguish user-entered content from server-generated metadata.
- Time source, timezone display, retention, deletion, and correction semantics are
  documented and tested.

## 13. Explainability Requirements

- A journal entry displays the user's rationale, counterarguments, assumptions,
  uncertainties, and referenced policy text together.
- The UI explains that a policy link is a traceability relationship, not a system
  conclusion that the decision follows the policy.
- No hidden score, model inference, generated recommendation, or automatic rule
  interpretation is permitted.
- Lifecycle labels and validation messages use plain language.
- Any system-generated metadata is visibly distinguished from user-authored text.

## 14. Privacy and Security Considerations

- Household goals, liquidity needs, risk statements, and decision records are
  sensitive financial-planning data.
- Planning must define data minimization before choosing required fields.
- Logs and error messages must not expose full policy or journal text.
- Secrets remain outside source control and examples contain placeholders only.
- Transport, storage encryption, backup, retention, deletion, and export policies
  require explicit decisions before production use.
- Authentication is not part of this proposed sprint, creating a blocker for any
  deployment beyond a tightly controlled local/demo environment.

## 15. Compliance Questions

- Does storing user-authored policy and journal content create recordkeeping,
  retention, fiduciary, or advisory obligations in intended jurisdictions?
- What disclaimer and consent language is required to distinguish recordkeeping
  from advice?
- Can the product use terms such as “investment policy,” “risk boundary,” and
  “decision” without implying suitability review?
- Must users be able to export, correct, or delete records, and what audit history
  must remain after correction or deletion?
- Is a household profile allowed to include information about other people before
  roles, consent, and authentication are implemented?

## 16. Acceptance Criteria

Proposed criteria, subject to approval:

- A user can create and retrieve the sole active household profile using only
  approved fields.
- A second household creation attempt, including one with a different supplied
  `household_id`, returns an explicit conflict such as HTTP 409.
- A user can edit a policy Draft and publish an immutable Published version.
- Publishing a later Draft can mark the prior Published version Superseded without
  changing its historical content.
- User-entered target allocation percentages must total exactly 100%; the system
  provides no recommended allocation.
- A user can create and retrieve a journal entry with rationale,
  counterarguments, assumptions, and uncertainties.
- A Confirmed journal revision references a specific Published policy version.
- Corrections append the required correction metadata and preserve original
  Confirmed content; archive never physically deletes a Confirmed revision.
- AuditEvents cover create, edit draft, publish, confirm, correct, archive, and
  supersede operations.
- The approved provisional non-advisory copy appears on core-flow entry, before
  policy publication, and before journal confirmation.
- `docker compose config` shows web, API, PostgreSQL, and Redis host ports bound by
  default to `127.0.0.1`, with no default `0.0.0.0` host publication.
- Any future remote access requires a separate sprint and security approval.
- PostgreSQL migrations upgrade an empty database successfully.
- Repository/integration tests run against real isolated PostgreSQL.
- Multi-record business writes and AuditEvents commit atomically and roll back
  together on failure.
- APIs never return recommendations, scores, eligibility, alerts, or trade actions.
- Automated tests cover validation, version linkage, audit events, API contracts,
  and the demonstrable frontend journey.
- Existing Sprint 001 health, lint, type-check, tests, build, and CI remain green.
- Security, compliance, retention, and authentication deployment boundaries are
  documented.

## 17. Test Strategy

- **Domain tests:** Draft → Published → Superseded policy transitions; Draft →
  Confirmed → Archived journal transitions; correction immutability; target
  allocation totaling 100%; policy-version references; and AuditEvent creation.
- **API tests:** contract shapes, invalid identifiers, a second household returning
  HTTP 409 even with a different supplied ID, lifecycle conflicts, validation
  errors, and absence of advisory outputs.
- **PostgreSQL integration tests:** run repositories and migrations against real
  isolated PostgreSQL; verify empty-database migration and transactional rollback
  of both business records and AuditEvents. SQLite or mocks do not replace these.
- **Frontend tests:** form validation, policy publish flow, journal confirmation and
  correction flow, policy linking, audit timeline, and provisional disclaimer at
  all three required points.
- **Infrastructure tests:** statically inspect expanded Compose configuration for
  `127.0.0.1` host bindings and absence of default `0.0.0.0` publication.
- **End-to-end test:** create sole profile → publish policy → confirm journal entry
  referencing that Published version → append correction → inspect immutable history.
- **Security/privacy tests:** sensitive-field redaction in logs/errors and rejected
  overlong or malformed content.
- **Regression tests:** all Sprint 001 health and CI checks.

## 18. Documentation Updates Required During Implementation

- `docs/MASTER_PLAN.md` after explicit scope approval.
- `docs/PRD.md` with approved user stories and non-goals.
- `docs/ARCHITECTURE.md` with approved persistence and module boundaries.
- New ADRs for persistence, audit immutability, and deployment/authentication
  boundaries where decisions are significant.
- `docs/INVESTMENT_RULEBOOK.md` only if the owner approves policy semantics; no
  rules may be silently added.
- `docs/GUARDIAN.md` and `docs/AI_INVESTMENT_COMMITTEE.md` only to restate exclusion
  boundaries if needed, not to implement those systems.
- `README.md`, API contract documentation, privacy notes, test instructions, and
  `docs/CHANGELOG.md`.

## 19. Risks and Mitigations

- **Recordkeeping perceived as advice:** Use neutral language, user-authored labels,
  disclaimers, and compliance review; do not score or interpret policy.
- **Sensitive household data without authentication:** Enforce local-only host
  bindings and prohibit remote deployment; authentication requires a separate
  approved sprint.
- **Audit history conflicts with deletion rights:** Apply the approved local-MVP
  retention/reset boundary and require a production policy before non-local use.
- **Scope expands into a rule engine:** Treat policy links as references only and
  prohibit automated evaluation.
- **Prescriptive templates invent rules:** Start with approved neutral categories
  and freeform owner statements, subject to owner review.
- **Over-modeling early:** Approve the smallest end-to-end entities and defer
  portfolio, market, member, and collaboration models.
- **Single-household constraint bypass:** Enforce at most one active profile in the
  database/transaction layer and test alternate-ID creation conflicts.

## 20. Dependencies

- Final implementation approval after the planning pull request merges.
- Approved detailed PostgreSQL schema, migrations, transaction boundaries,
  repositories, and audit implementation plan.
- CI access to an isolated real PostgreSQL service for blocking integration tests.
- Implementation of the approved provisional non-advisory copy and local-only
  boundary; final legal review is deferred until non-local or production use.
- Docker runtime verification remains a non-blocking Sprint 001 backlog item; run
  it when Docker is available, otherwise disclose that it was not completed.

Final production legal copy, production retention, authentication, full application
Docker runtime, export, backup, and encryption-key management are not blockers for
local MVP development. They become blockers before remote, production, or
commercial use.

No new software dependency is approved by this planning document.

## 21. Definition of Done

Proposed local-MVP definition, subject to final implementation approval:

- The approved household → policy Draft → target allocation → Published version →
  Confirmed journal → immutable history loop is complete.
- Policy and journal lifecycle, immutability, correction, archive, and supersede
  tests pass.
- Single-active-household constraint and second-create HTTP 409 tests pass.
- Target allocation total-equals-100% validation tests pass without generating a
  recommended allocation.
- Real PostgreSQL migration, repository, and integration tests pass in CI.
- Business-write and AuditEvent transaction rollback tests pass.
- Expanded Compose host-port configuration defaults to `127.0.0.1` and has no
  default `0.0.0.0` host publication.
- The provisional non-advisory copy appears at all three approved checkpoints and
  its display tests pass.
- No recommendations, AI, Guardian, broker, trading, actual holdings, accounts, or
  monetary data are implemented.
- Lint, type-check, tests, build, and CI pass.
- Required product, architecture, ADR, API, privacy, and changelog documentation is
  current.
- Independent code review confirms implementation matches the approved Sprint 002
  scope.

## 22. Estimated Implementation Sequence

This sequence is an estimate only and does not authorize work:

1. Obtain explicit implementation approval after this planning PR merges.
2. Approve a narrow PRD amendment, PostgreSQL design, API contracts, entity
   concepts, transactions, migrations, and ADRs.
3. Establish domain validation and audit behavior with tests.
4. Add the minimal approved persistence layer and migrations.
5. Implement household profile and policy version APIs.
6. Implement journal and policy-reference APIs.
7. Implement the minimal frontend workflow.
8. Add end-to-end, privacy, regression, and failure-path tests.
9. Update documentation and complete independent review.

## 23. Decisions Requiring Project-Owner Approval

- Detailed implementation architecture and final acceptance-test wording.
- PostgreSQL schema, migration, transaction, and repository design.
- Final production disclaimer, retention, export, deletion, backup, and encryption
  requirements before any non-local use.
- Any decision to expand beyond local-only, no-auth operation.

## 24. Planning Outcome

Option A has been selected for implementation planning with the approved boundaries
in this document. Sprint 002 remains Not Started until this planning pull request
merges and the project owner separately authorizes implementation.
