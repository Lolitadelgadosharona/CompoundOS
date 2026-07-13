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

- Draft policies are editable.
- A Published version cannot be modified in place.
- Changing a Published policy requires a new version.
- Historical versions are retained and cannot be silently overwritten.
- A Published version cannot be physically deleted.
- A version may be marked Superseded while remaining available in history.

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

All journal content is manually entered. A decision record references the selected
Published policy version that was effective when the record was created. Confirmed
records cannot be silently modified; corrections use an appended correction record
or a new version. Confirmed records may be archived but not physically deleted.

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

- Plan to use PostgreSQL during Sprint 002 implementation.
- Do not use in-memory storage as formal persistence.
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
4. The user reviews and explicitly confirms a version of the household investment
   policy.
5. The user creates a decision-journal entry describing an idea or decision,
   rationale, counterarguments, assumptions, uncertainties, and decision status.
6. The user links the entry to one or more approved policy statements without the
   system judging compliance or quality.
7. The user reviews the saved entry and its policy-version references.
8. Later edits create traceable revisions rather than silently rewriting history.

## 6. Proposed Scope

- Exactly one household workspace for the project owner in local development.
- Structured capture of owner-provided household planning context.
- Draft and confirmed policy records with explicit version identifiers.
- Decision-journal creation and read views.
- Structured fields for rationale, counterarguments, assumptions, uncertainties,
  and status.
- Links from journal entries to confirmed policy statements or sections.
- Append-only audit events for create, confirm, revise, and archive actions.
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
- Policy editor organized by approved conceptual categories, with draft/confirm
  states and visible version metadata.
- Decision-journal form and detail view.
- Policy-link selector that only references confirmed user-authored policy content.
- Revision/audit timeline showing actor label, action, and timestamp.
- Persistent non-advisory messaging and clear distinction between user input and
  system metadata.
- Accessible validation messages for missing required recordkeeping fields.

No visual design, component library, route structure, or state-management choice
is approved by this proposal.

## 9. Proposed Backend Scope

- API contracts for household profile, policy drafts/versions, journal entries,
  policy links, and audit-event reads.
- Input validation for required recordkeeping fields and allowed lifecycle states.
- Explicit policy confirmation and revision operations.
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
- **InvestmentPolicyVersion:** Immutable snapshot of a draft or confirmed policy.
- **PolicyStatement:** Versioned, user-authored policy section or statement.
- **DecisionJournalEntry:** Decision record with lifecycle state and timestamps.
- **DecisionArgument:** Supporting or opposing reason supplied by the user.
- **DecisionAssumption:** User-stated assumption and optional uncertainty note.
- **PolicyReference:** Link from a journal entry to a specific policy version and
  statement.
- **AuditEvent:** Append-only record of a meaningful state change.

## 11. API Endpoint Proposals (Contracts Only)

Names are illustrative and not approved routes:

- `POST /api/households` — create a household profile from owner-provided fields.
- `GET /api/households/{household_id}` — retrieve the profile.
- `PATCH /api/households/{household_id}` — revise allowed profile fields and emit
  an audit event.
- `POST /api/households/{household_id}/policies` — create a policy draft.
- `GET /api/policies/{policy_id}` — retrieve current policy metadata.
- `POST /api/policies/{policy_id}/versions` — save a new immutable draft version.
- `POST /api/policies/{policy_id}/versions/{version_id}/confirm` — explicitly
  confirm a version; no evaluation is performed.
- `GET /api/policies/{policy_id}/versions` — list version metadata.
- `POST /api/households/{household_id}/journal-entries` — create a journal entry.
- `GET /api/journal-entries/{entry_id}` — retrieve an entry and policy references.
- `PATCH /api/journal-entries/{entry_id}` — create an auditable revision according
  to the approved immutability model.
- `GET /api/households/{household_id}/audit-events` — retrieve audit history.

Contracts must use neutral errors and never return advice, eligibility, score,
approval, or trade instructions.

## 12. Auditability Requirements

- Every confirmed policy version has a stable identifier and confirmation time.
- Journal policy links target a specific immutable policy version.
- Create, confirm, revise, status-change, archive, and link-change actions are
  attributable and timestamped.
- Historical confirmed policy content cannot be silently overwritten.
- Journal history behavior—immutable entries versus explicit revisions—must be
  owner-approved before implementation.
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

- A user can create and retrieve one household profile using only approved fields.
- A user can create, review, and explicitly confirm a policy version.
- A user can create and retrieve a journal entry with rationale,
  counterarguments, assumptions, and uncertainties.
- A journal entry can reference a specific confirmed policy version and statement.
- Revisions preserve the approved historical/audit representation.
- The UI clearly labels user-authored data and displays non-advisory language.
- APIs never return recommendations, scores, eligibility, alerts, or trade actions.
- Automated tests cover validation, version linkage, audit events, API contracts,
  and the demonstrable frontend journey.
- Existing Sprint 001 health, lint, type-check, tests, build, and CI remain green.
- Security, compliance, retention, and authentication deployment boundaries are
  documented.

## 17. Test Strategy

- **Domain tests:** lifecycle transitions, version immutability, policy references,
  required fields, and audit-event creation.
- **API tests:** contract shapes, invalid identifiers, validation errors,
  concurrency behavior once approved, and absence of advisory outputs.
- **Frontend tests:** form validation, draft/confirm flow, journal capture, policy
  linking, audit timeline, and disclaimer presence.
- **End-to-end test:** create profile → confirm policy → record journal entry → link
  policy → inspect history.
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
- **Sensitive household data without authentication:** Restrict approved deployment
  scope or make authentication a prerequisite in a separately approved decision.
- **Audit history conflicts with deletion rights:** Resolve retention/correction
  semantics before implementation.
- **Scope expands into a rule engine:** Treat policy links as references only and
  prohibit automated evaluation.
- **Prescriptive templates invent rules:** Start with approved neutral categories
  and freeform owner statements, subject to owner review.
- **Over-modeling early:** Approve the smallest end-to-end entities and defer
  portfolio, market, member, and collaboration models.
- **Ambiguous household ownership:** Decide single-household and actor assumptions
  before coding.

## 20. Dependencies

- Final implementation approval after the planning pull request merges.
- Resolution of any architecture or compliance question promoted to a blocker
  before implementation approval.
- Compliance review of language, retention, and intended deployment boundary.
- Architecture decisions for persistence, audit behavior, identifiers, and
  authentication/deployment boundary.
- Approved UX copy for non-advisory notices and confirmations.
- Docker runtime verification remains a non-blocking Sprint 001 backlog item; run
  it when Docker is available, otherwise disclose that it was not completed.

No new software dependency is approved by this planning document.

## 21. Definition of Done

Proposed definition, not approved:

- Project owner has approved one option, scope, non-goals, and all blocking
  decisions.
- Approved end-to-end workflow meets its acceptance criteria.
- Audit and explainability requirements are implemented and tested.
- No advice, trading, broker, AI agent, Guardian, authentication, or unapproved
  rule behavior has been introduced.
- Privacy/security and deployment limitations are documented and enforced.
- Tests, lint, type-check, build, and CI pass.
- Required product, architecture, ADR, API, privacy, and changelog documentation is
  current.
- Independent review confirms implementation matches the approved Sprint 002
  scope.

## 22. Estimated Implementation Sequence

This sequence is an estimate only and does not authorize work:

1. Resolve blocking product, compliance, privacy, audit, and architecture questions.
2. Approve a narrow PRD amendment, API contracts, entity concepts, and ADRs.
3. Establish domain validation and audit behavior with tests.
4. Add the minimal approved persistence layer and migrations.
5. Implement household profile and policy version APIs.
6. Implement journal and policy-reference APIs.
7. Implement the minimal frontend workflow.
8. Add end-to-end, privacy, regression, and failure-path tests.
9. Update documentation and complete independent review.

## 23. Decisions Requiring Project-Owner Approval

- Detailed implementation architecture and final acceptance-test wording.
- Non-advisory disclaimer and consent language.
- PostgreSQL schema, migration, transaction, and repository design.
- Retention, export, deletion, backup, and encryption expectations.
- Any decision to expand beyond local-only, no-auth operation.

## 24. Planning Outcome

Option A has been selected for implementation planning with the approved boundaries
in this document. Sprint 002 remains Not Started until this planning pull request
merges and the project owner separately authorizes implementation.
