# CompoundOS Sprint 002 Planning PR #4 Read-Only Review

## 1. PR #4 Metadata

```json
{"baseRefName":"main","headRefName":"planning/sprint-002","headRefOid":"3ab5885107b4984093dc8f9a8d153c4a3b9ce260","isDraft":true,"number":4,"state":"OPEN","statusCheckRollup":[{"__typename":"CheckRun","completedAt":"2026-07-13T03:00:18Z","conclusion":"SUCCESS","detailsUrl":"https://github.com/Lolitadelgadosharona/CompoundOS/actions/runs/29220679186/job/86725009378","name":"infrastructure","startedAt":"2026-07-13T03:00:11Z","status":"COMPLETED","workflowName":"CI"},{"__typename":"CheckRun","completedAt":"2026-07-13T02:59:44Z","conclusion":"SUCCESS","detailsUrl":"https://github.com/Lolitadelgadosharona/CompoundOS/actions/runs/29220658047/job/86724949040","name":"infrastructure","startedAt":"2026-07-13T02:59:37Z","status":"COMPLETED","workflowName":"CI"},{"__typename":"CheckRun","completedAt":"2026-07-13T03:00:22Z","conclusion":"SUCCESS","detailsUrl":"https://github.com/Lolitadelgadosharona/CompoundOS/actions/runs/29220679186/job/86725009391","name":"backend","startedAt":"2026-07-13T03:00:11Z","status":"COMPLETED","workflowName":"CI"},{"__typename":"CheckRun","completedAt":"2026-07-13T02:59:48Z","conclusion":"SUCCESS","detailsUrl":"https://github.com/Lolitadelgadosharona/CompoundOS/actions/runs/29220658047/job/86724949024","name":"backend","startedAt":"2026-07-13T02:59:36Z","status":"COMPLETED","workflowName":"CI"},{"__typename":"CheckRun","completedAt":"2026-07-13T03:00:51Z","conclusion":"SUCCESS","detailsUrl":"https://github.com/Lolitadelgadosharona/CompoundOS/actions/runs/29220679186/job/86725009371","name":"frontend","startedAt":"2026-07-13T03:00:12Z","status":"COMPLETED","workflowName":"CI"},{"__typename":"CheckRun","completedAt":"2026-07-13T03:00:08Z","conclusion":"SUCCESS","detailsUrl":"https://github.com/Lolitadelgadosharona/CompoundOS/actions/runs/29220658047/job/86724949051","name":"frontend","startedAt":"2026-07-13T02:59:37Z","status":"COMPLETED","workflowName":"CI"}],"title":"Planning: Sprint 002 Policy and Decision Journal","url":"https://github.com/Lolitadelgadosharona/CompoundOS/pull/4"}
```

## 2. `git diff --stat main...HEAD`

```text
 docs/MASTER_PLAN.md                       |  17 +
 docs/sprints/SPRINT_002_OPEN_QUESTIONS.md | 394 +++++++++++++++++++++
 docs/sprints/SPRINT_002_PROPOSAL.md       | 550 ++++++++++++++++++++++++++++++
 3 files changed, 961 insertions(+)
```

## 3. `git diff --name-status main...HEAD`

```text
M	docs/MASTER_PLAN.md
A	docs/sprints/SPRINT_002_OPEN_QUESTIONS.md
A	docs/sprints/SPRINT_002_PROPOSAL.md
```

## 4. `docs/sprints/SPRINT_002_PROPOSAL.md`

~~~markdown
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
~~~

## 5. `docs/sprints/SPRINT_002_OPEN_QUESTIONS.md`

~~~markdown
# Sprint 002 Open Questions

## Status

Planning decisions and remaining questions only. Sprint 002 implementation is
**Not Started** and still requires explicit approval after the planning pull request
merges.

## Resolution Summary

### Resolved on 2026-07-13

- Selected Option A: Household Investment Policy + Decision Journal.
- Approved one household owned by the project owner; no members, collaboration,
  roles, permissions, multiple households, or multi-tenancy.
- Approved local-development-only operation with no authentication and no public
  deployment.
- Approved the minimum household fields and fixed audit actor `local-owner`.
- Approved user-entered policy categories, target asset-class percentages totaling
  100%, Published version immutability, and Superseded history.
- Approved the decision-journal fields, Published policy-version references,
  appended corrections, archive behavior, and no physical deletion of confirmed
  records.
- Approved PostgreSQL as formal persistence direction; Redis has no product logic.
- Confirmed no actual holdings, accounts, monetary data, market data, AI, Guardian,
  broker integration, recommendations, suitability conclusions, or trading.
- Confirmed Docker runtime validation remains non-blocking with accurate disclosure
  when Docker is unavailable.

### Open but Non-Blocking for the Local MVP

- Final non-advisory disclaimer and consent copy.
- Long-term retention, export, broader deletion, backup, and encryption policy.
- Detailed PostgreSQL schema, migrations, transactions, and repository boundaries.
- Final visual design and exact acceptance-test wording.
- Jurisdiction-specific requirements for any future non-local deployment.

### Deferred to Future Sprints

- Household member collaboration, invitations, roles, permissions, multi-household,
  and multi-tenant support.
- Authentication, authorization, private remote environments, and public deployment.
- Actual holdings, securities quantities, accounts, balances, monetary amounts,
  costs, prices, returns, market data, and transactions.
- Guardian rules, thresholds, monitoring, alerts, and notifications.
- AI agents, AI generation, summarization, scoring, and AI Investment Committee
  behavior.
- Broker integrations, recommendations, eligibility engines, and trading.

## Product

### P1. Which candidate should define Sprint 002?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Choose A: Household Investment Policy + Decision Journal, B:
  Portfolio Snapshot + Manual Holdings, C: Investment Idea Intake + Rule-Based
  Eligibility Check, or defer all three.
- **Why answer is needed:** The options require different data, safety boundaries,
  and architecture; combining them would exceed a focused sprint.
- **Recommended default:** Option A only.
- **Other options:** Option B, Option C, a narrower subset of A, or no Sprint 002.
- **Impact:** A establishes policy/audit context; B prioritizes valuation and
  portfolio modeling; C requires approved rule semantics and carries greater
  advice risk.
- **Blocks implementation:** No — resolved by product-owner decision.

### P2. Who is the first intended user?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Is the first user a single household owner recording their own
  information, a family-office professional, or another role?
- **Why answer is needed:** Language, consent, ownership, workflow, and compliance
  assumptions depend on the user.
- **Recommended default:** One household owner in a controlled local/demo setting.
- **Other options:** Family-office operator, adviser, multiple household members.
- **Impact:** Professional or multi-member use adds permissions, fiduciary,
  collaboration, and recordkeeping concerns that may make this sprint infeasible.
- **Blocks implementation:** No — resolved by product-owner decision.

## Household Profile

### H1. What is the minimum household profile?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Which fields are necessary beyond a display name?
- **Why answer is needed:** Household data is sensitive, and unnecessary fields
  increase privacy and compliance exposure.
- **Recommended default:** Use the approved fields `household_name`, `base_currency`,
  `investment_horizon`, `liquidity_needs`, `risk_statement`, and `notes`; exclude
  member identity information and monetary calculations.
- **Other options:** Structured members, demographics, jurisdictions, dependents,
  or legal entities.
- **Impact:** More structured personal data increases security, consent, and
  authentication requirements.
- **Blocks implementation:** No — resolved by product-owner decision.

### H2. Is Sprint 002 single-household only?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Should the system support exactly one household record in the
  approved deployment context or multiple isolated households?
- **Why answer is needed:** Multi-tenancy changes identifiers, isolation,
  authorization, testing, and deletion behavior.
- **Recommended default:** One household for the first demonstrable workflow.
- **Other options:** Multiple households without users, or full tenant isolation.
- **Impact:** Multiple households likely requires authentication/authorization,
  which is currently excluded and needs separate architectural approval.
- **Blocks implementation:** No — resolved by product-owner decision.

## Investment Policy

### IP1. Which policy categories may be captured?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Approve the neutral categories allowed in the policy editor.
- **Why answer is needed:** Categories can become implicit investment rules if the
  system invents or prescribes them.
- **Recommended default:** Use the approved user-authored categories: `objectives`,
  `time_horizon`, `liquidity`, `target_asset_allocation`, `diversification`,
  `contribution_policy`, `rebalancing_policy`, `prohibited_assets`,
  `leverage_policy`, `decision_process`, and `notes`.
- **Other options:** Asset allocation, prohibited assets, concentration limits,
  tax constraints, rebalancing, or return targets.
- **Impact:** Numeric limits or asset rules require formal rule governance and may
  enable evaluation behavior outside the recommended sprint.
- **Blocks implementation:** No — resolved by product-owner decision.

### IP2. What makes a policy version “Published”?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Is explicit user confirmation sufficient to create a Published
  version, and can that version later be edited?
- **Why answer is needed:** Auditability requires clear draft, confirmation, and
  revision semantics.
- **Recommended default:** Explicit confirmation creates an immutable Published
  version; changes require a new version, and the prior version may be marked
  Superseded but cannot be physically deleted.
- **Other options:** Editable confirmed records, approval by another actor, or no
  confirmation lifecycle.
- **Impact:** Editable history weakens auditability; multi-actor approval requires
  identity and permissions.
- **Blocks implementation:** No — resolved by product-owner decision.

## Portfolio Data

### PD1. Is any portfolio or holdings data allowed in Sprint 002?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** May a journal mention an asset or amount, or must all portfolio
  structures be deferred?
- **Why answer is needed:** Structured instruments, values, and positions can pull
  Option A into portfolio, pricing, and suitability scope.
- **Recommended default:** Permit only user-entered target asset-class percentages
  totaling 100%; exclude actual holdings, accounts, quantities, balances, amounts,
  prices, costs, returns, valuation, and market data.
- **Other options:** Optional instrument label, user-entered amount, or full manual
  holdings.
- **Impact:** Structured identifiers or amounts add validation, privacy, precision,
  and potentially advice/compliance requirements.
- **Blocks implementation:** No — resolved by product-owner decision.

## Decision Journal

### DJ1. Which journal fields are required?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Approve the minimum content necessary for a meaningful decision
  record.
- **Why answer is needed:** Too few fields undermine discipline; prescriptive fields
  could imply a system-endorsed investment method.
- **Recommended default:** Use the approved minimum fields: `title`,
  `decision_date`, `decision_type`, `summary`, `supporting_reasons`,
  `opposing_reasons`, `assumptions`, `uncertainties`,
  `policy_version_reference`, `final_decision`, `review_date`, `status`,
  `created_at`, and `updated_at`.
- **Other options:** Evidence links, expected outcome, price, amount, review date,
  confidence score, or attachments.
- **Impact:** Scores and expected outcomes risk recommendation semantics; attachments
  and links expand privacy and content-security scope.
- **Blocks implementation:** No — resolved by product-owner decision.

### DJ2. Can journal history be edited or deleted?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Define revision, correction, archive, and deletion behavior.
- **Why answer is needed:** Audit integrity may conflict with privacy and correction
  rights.
- **Recommended default:** Confirmed records cannot be silently edited or physically
  deleted; use appended correction records or new versions and allow archive.
- **Other options:** Fully editable entries, hard delete, or append-only with no
  correction.
- **Impact:** Each choice changes storage, audit, UX, privacy, and compliance design.
- **Blocks implementation:** No — resolved by product-owner decision.

## Risk and Guardian Boundaries

### RG1. How must policy “risk boundaries” be represented?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Are they freeform user statements only, or may they include numeric
  thresholds?
- **Why answer is needed:** Numeric thresholds could become Guardian alert logic or
  automated rule evaluation.
- **Recommended default:** Freeform owner-authored statements with no automated
  interpretation, threshold, alert, or compliance status.
- **Other options:** Structured numeric limits, categories, or severity levels.
- **Impact:** Structured limits require approved Guardian/rule architecture and are
  outside the recommended Sprint 002 boundary.
- **Blocks implementation:** No — resolved by product-owner decision.

## AI Investment Committee Boundaries

### AI1. May AI generate, summarize, or critique policy or journal content?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Confirm whether any AI behavior is allowed.
- **Why answer is needed:** AI-generated language could be mistaken for advice and
  would begin AI Investment Committee or agent scope.
- **Recommended default:** No AI generation, summarization, critique, scoring, or
  agents in Sprint 002.
- **Other options:** Draft assistance, summarization, structured extraction, or
  committee review.
- **Impact:** Any AI option requires separate safety, explainability, model,
  evaluation, privacy, and architecture approval.
- **Blocks implementation:** No — resolved by product-owner decision.

## Compliance

### C1. What non-advisory language is required?

- **Status:** Open — non-blocking for the approved local MVP boundary.

- **Question:** Approve the notices, consent, and terminology that distinguish
  user recordkeeping from investment advice or suitability review.
- **Why answer is needed:** Policy and decision interfaces could otherwise appear
  to endorse a strategy or decision.
- **Recommended default:** Prominent owner-authored-record notice and explicit
  statement that links and validation do not assess investment merit.
- **Other options:** Legal-review-provided language, per-action attestation, or no
  notice.
- **Impact:** Insufficient language is a release blocker; repeated attestations may
  increase UX friction.
- **Blocks implementation:** No — exact copy remains a non-blocking review item.

### C2. Which jurisdictions and retention duties apply?

- **Status:** Open — non-blocking for the approved local MVP boundary.

- **Question:** Identify intended initial jurisdiction and whether advisory,
  fiduciary, household-record, or financial-record retention rules apply.
- **Why answer is needed:** Retention, deletion, export, and terminology cannot be
  designed safely without intended-use context.
- **Recommended default:** Controlled non-production demonstration only until legal
  review identifies obligations.
- **Other options:** Named production jurisdiction, internal family-office use, or
  consumer launch.
- **Impact:** Production use may require authentication, consent, retention,
  disclosures, exports, and formal compliance controls beyond Sprint 002.
- **Blocks implementation:** No for the local MVP; future deployment remains deferred.

## Privacy and Security

### PS1. What deployment boundary is allowed without authentication?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** May Sprint 002 be implemented for local/demo use only, or must
  remote/multi-user access be supported?
- **Why answer is needed:** Sensitive household data cannot be safely exposed
  remotely without identity and access controls.
- **Recommended default:** Local, single-user demonstration only; no production or
  shared deployment.
- **Other options:** Add authentication through separate approval, anonymized demo
  data only, or defer implementation.
- **Impact:** Remote use makes authentication/authorization and security review
  prerequisites, expanding scope materially.
- **Blocks implementation:** No — resolved by product-owner decision.

### PS2. What are the retention, export, and deletion expectations?

- **Status:** Open — non-blocking for the approved local MVP boundary.

- **Question:** Define how long records live and whether users need export or
  deletion in the first approved workflow.
- **Why answer is needed:** These requirements shape audit architecture and data
  model boundaries.
- **Recommended default:** Define retention before implementation; keep export and
  deletion out of scope unless compliance makes them mandatory.
- **Other options:** Immediate export/delete, indefinite retention, configurable
  policy, or ephemeral demo data.
- **Impact:** Export/delete adds contracts and security tests; indefinite retention
  increases privacy exposure; ephemeral data reduces demonstration realism.
- **Blocks implementation:** No — open but non-blocking for the local MVP.

## UX

### UX1. What is the smallest acceptable demonstration?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Approve the exact screens and completion path.
- **Why answer is needed:** Without a fixed journey, policy editing and journal UI
  can expand into collaboration, analytics, or design-system work.
- **Recommended default:** Demonstrate the approved loop: single household profile,
  policy draft, target allocation percentages, Published policy version, decision
  journal, policy-version reference, and non-silent audit history.
- **Other options:** Wizard, dashboard, templates, search, list filters, responsive
  polish, or collaboration.
- **Impact:** Additional surfaces increase implementation and test scope without
  improving the core discipline loop.
- **Blocks implementation:** No — resolved by product-owner decision.

## Technical Architecture

### TA1. What persistence approach is approved?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Should an approved implementation use PostgreSQL immediately, an
  in-memory demo, or another repository abstraction?
- **Why answer is needed:** Audit/version semantics depend on transactions,
  constraints, and persistence behavior.
- **Recommended default:** PostgreSQL behind explicit repository boundaries;
  schema, migrations, and transactions require implementation approval and review.
- **Other options:** In-memory prototype, file-based persistence, or defer storage.
- **Impact:** In-memory is faster but cannot demonstrate durable audit history;
  PostgreSQL requires migrations, schema, transactions, and Docker/runtime work.
- **Blocks implementation:** No — resolved by product-owner decision.

### TA2. How are actors represented without authentication?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** What actor identifier appears in audit events before identity is
  implemented?
- **Why answer is needed:** Audit records require attribution, but fake user
  identity could mislead reviewers.
- **Recommended default:** A documented constant such as `local-owner`, visibly
  limited to local/demo use.
- **Other options:** Anonymous actor, user-entered label, or require authentication
  first.
- **Impact:** User-entered labels are not trustworthy; anonymous weakens audit;
  authentication is a major separately approved scope.
- **Blocks implementation:** No — resolved by product-owner decision.

## Definition of Done

### DOD1. Which gates are mandatory before Sprint 002 can be marked Done?

- **Status:** Resolved by product-owner decision on 2026-07-13.

- **Question:** Approve the acceptance criteria, documentation, independent review,
  security/compliance gates, and whether Docker runtime verification is required.
- **Why answer is needed:** A sprint cannot start safely without an agreed finish
  line and release boundary.
- **Recommended default:** All approved user journey and audit tests pass; existing
  CI remains green; privacy/compliance decisions are documented; independent
  review passes; run Docker runtime validation when Docker is available, otherwise
  disclose accurately that it was not completed.
- **Other options:** Require Docker runtime, require authentication, require legal
  review, or permit a local-only prototype with explicit limitations.
- **Impact:** Stronger gates increase confidence and schedule; weaker gates restrict
  deployment and must be clearly disclosed.
- **Blocks implementation:** No — resolved by product-owner decision.

## Decision and Follow-Up Summary

The product-scope questions below are resolved or explicitly non-blocking. Sprint
002 remains Not Started because implementation still requires a separate final
approval after this planning pull request merges:

1. P1 — candidate selection.
2. P2 — intended user.
3. H1/H2 — minimum household data and tenancy boundary.
4. IP1/IP2 — policy categories and confirmation/version semantics.
5. PD1 — portfolio/instrument data boundary.
6. DJ1/DJ2 — journal fields and history/deletion behavior.
7. RG1/AI1 — explicit Guardian and AI exclusions.
8. C1/C2 — non-advisory language, jurisdiction, and compliance context.
9. PS1/PS2 — deployment, authentication boundary, retention, export, and deletion.
10. UX1 — minimum demonstrable journey.
11. TA1/TA2 — persistence and audit actor architecture.
12. DOD1 — approved Definition of Done and quality gates.
~~~

## 6. `docs/MASTER_PLAN.md`

~~~markdown
# Master Plan

## Long-term Goal

Build CompoundOS as a trustworthy, explainable operating system for family office and wealth management workflows, beginning with a documented and testable foundation.

## Milestones

- Milestone 1: Foundation and governance scaffold
- Milestone 2: Core platform services and health monitoring
- Milestone 3: Decision support workflows and review interfaces

## Current Sprint

- Sprint 001: Project Foundation
- Status: Done
- Scope: final foundation verification, frontend health test, and Docker-based
  local development configuration
- Sprint 002: Not Started; implementation has not been authorized

## Planning

- Sprint 002 selected direction: Household Investment Policy + Decision Journal.
- Planning pull request is pending.
- Sprint 002 implementation is Not Started and requires explicit approval after
  the planning pull request merges.

## Backlog

- Complete Docker runtime verification in a Docker-enabled environment
- Decide whether to migrate `frontend/` to `apps/web/`
- Add backend domain modules
- Introduce data persistence and orchestration
- Add Guardian monitoring workflows
- Add AI Investment Committee workflows
- Add notification escalation capabilities

## In Progress

- None

## Review

- Sprint 001 independent code review passed
- Review conclusion: APPROVE WITH NON-BLOCKING FOLLOW-UP
- Pull request #3 approved for merge

## Done

- Sprint 001: Project Foundation
- Sprint 001.1: Repository Hardening
- Repository structure created
- Basic health endpoints implemented
- Initial documentation scaffold added
- Backend and frontend validation commands added
- Production frontend dependency audit completed with no known vulnerabilities
- CompoundOS repository isolated from unrelated parent-directory files
- npm, Node.js, TypeScript, and Next.js version decisions documented
- ADR 0001 accepted for the frontend framework and package manager
- Sprint 001 Git identity corrected using the approved repository-local identity
- Intended empty GitHub repository verified
- Pull request #1 squash-merged into `main` as
  `b3801c64fa09856d491317b0ebda45007c210ae0`
- GitHub Actions backend and frontend checks passed for push and pull request events
- Frontend health endpoint automated test added and included in CI
- Docker Compose and Dockerfiles added with static YAML, context, path, and command
  consistency validation

## Decision Log

- 2026-07-11: Use a minimal monorepo with FastAPI and Next.js placeholders for Sprint 001.
- 2026-07-11: Avoid implementing investment logic, trading, brokers, or autonomous agents in this sprint.
- 2026-07-11: Defer Docker Compose until it can be validated in a Docker-enabled environment.
- 2026-07-12: Isolate CompoundOS in a dedicated repository directory while preserving Sprint 001 history.
- 2026-07-12: Standardize on Node.js 22, npm 10, TypeScript, and Next.js 16.2.10.
- 2026-07-12: Retain `frontend/` alongside `apps/api/` for Sprint 001.1; evaluate `apps/web/` later.
- 2026-07-12: Complete Sprint 001.1 after local validation and GitHub Actions passed.
- 2026-07-12: Finalize Sprint 001 and Sprint 001.1 through pull request #1 using a
  squash merge (`b3801c64fa09856d491317b0ebda45007c210ae0`).
- 2026-07-12: Keep Sprint 002 Not Started; the next approved action is planning only.
- 2026-07-12: Reopen Sprint 001 in Review to add the approved Docker development
  configuration and frontend health test without beginning Sprint 002.
- 2026-07-12: Record Docker runtime verification as pending; do not claim container
  validation until Docker is available.
- 2026-07-12: Sprint 001 independent code review passed with the conclusion
  APPROVE WITH NON-BLOCKING FOLLOW-UP.
- 2026-07-12: Treat Docker runtime verification as a non-blocking follow-up and
  retain it in the Backlog.
- 2026-07-12: Approve pull request #3 for merge; Sprint 002 remains Not Started.
- 2026-07-13: Sprint 002 planning authorized.
- 2026-07-13: Planning does not authorize Sprint 002 implementation.
- 2026-07-13: Selected Sprint 002 candidate A, Household Investment Policy +
  Decision Journal.
- 2026-07-13: Approved the single-household, local-only, no-authentication boundary.
- 2026-07-13: Approved user-entered target allocation percentages while prohibiting
  actual holdings, accounts, and monetary data.
- 2026-07-13: Confirmed no AI, Guardian, broker integration, recommendations, or
  trading in Sprint 002.
- 2026-07-13: Planning approval does not yet authorize implementation.
~~~

## 7. Complete `git diff main...HEAD`

```diff
diff --git a/docs/MASTER_PLAN.md b/docs/MASTER_PLAN.md
index 6a2f17c..b0ff1f6 100644
--- a/docs/MASTER_PLAN.md
+++ b/docs/MASTER_PLAN.md
@@ -18,6 +18,13 @@ Build CompoundOS as a trustworthy, explainable operating system for family offic
   local development configuration
 - Sprint 002: Not Started; implementation has not been authorized
 
+## Planning
+
+- Sprint 002 selected direction: Household Investment Policy + Decision Journal.
+- Planning pull request is pending.
+- Sprint 002 implementation is Not Started and requires explicit approval after
+  the planning pull request merges.
+
 ## Backlog
 
 - Complete Docker runtime verification in a Docker-enabled environment
@@ -80,3 +87,13 @@ Build CompoundOS as a trustworthy, explainable operating system for family offic
 - 2026-07-12: Treat Docker runtime verification as a non-blocking follow-up and
   retain it in the Backlog.
 - 2026-07-12: Approve pull request #3 for merge; Sprint 002 remains Not Started.
+- 2026-07-13: Sprint 002 planning authorized.
+- 2026-07-13: Planning does not authorize Sprint 002 implementation.
+- 2026-07-13: Selected Sprint 002 candidate A, Household Investment Policy +
+  Decision Journal.
+- 2026-07-13: Approved the single-household, local-only, no-authentication boundary.
+- 2026-07-13: Approved user-entered target allocation percentages while prohibiting
+  actual holdings, accounts, and monetary data.
+- 2026-07-13: Confirmed no AI, Guardian, broker integration, recommendations, or
+  trading in Sprint 002.
+- 2026-07-13: Planning approval does not yet authorize implementation.
diff --git a/docs/sprints/SPRINT_002_OPEN_QUESTIONS.md b/docs/sprints/SPRINT_002_OPEN_QUESTIONS.md
new file mode 100644
index 0000000..3b46fbe
--- /dev/null
+++ b/docs/sprints/SPRINT_002_OPEN_QUESTIONS.md
@@ -0,0 +1,394 @@
+# Sprint 002 Open Questions
+
+## Status
+
+Planning decisions and remaining questions only. Sprint 002 implementation is
+**Not Started** and still requires explicit approval after the planning pull request
+merges.
+
+## Resolution Summary
+
+### Resolved on 2026-07-13
+
+- Selected Option A: Household Investment Policy + Decision Journal.
+- Approved one household owned by the project owner; no members, collaboration,
+  roles, permissions, multiple households, or multi-tenancy.
+- Approved local-development-only operation with no authentication and no public
+  deployment.
+- Approved the minimum household fields and fixed audit actor `local-owner`.
+- Approved user-entered policy categories, target asset-class percentages totaling
+  100%, Published version immutability, and Superseded history.
+- Approved the decision-journal fields, Published policy-version references,
+  appended corrections, archive behavior, and no physical deletion of confirmed
+  records.
+- Approved PostgreSQL as formal persistence direction; Redis has no product logic.
+- Confirmed no actual holdings, accounts, monetary data, market data, AI, Guardian,
+  broker integration, recommendations, suitability conclusions, or trading.
+- Confirmed Docker runtime validation remains non-blocking with accurate disclosure
+  when Docker is unavailable.
+
+### Open but Non-Blocking for the Local MVP
+
+- Final non-advisory disclaimer and consent copy.
+- Long-term retention, export, broader deletion, backup, and encryption policy.
+- Detailed PostgreSQL schema, migrations, transactions, and repository boundaries.
+- Final visual design and exact acceptance-test wording.
+- Jurisdiction-specific requirements for any future non-local deployment.
+
+### Deferred to Future Sprints
+
+- Household member collaboration, invitations, roles, permissions, multi-household,
+  and multi-tenant support.
+- Authentication, authorization, private remote environments, and public deployment.
+- Actual holdings, securities quantities, accounts, balances, monetary amounts,
+  costs, prices, returns, market data, and transactions.
+- Guardian rules, thresholds, monitoring, alerts, and notifications.
+- AI agents, AI generation, summarization, scoring, and AI Investment Committee
+  behavior.
+- Broker integrations, recommendations, eligibility engines, and trading.
+
+## Product
+
+### P1. Which candidate should define Sprint 002?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Choose A: Household Investment Policy + Decision Journal, B:
+  Portfolio Snapshot + Manual Holdings, C: Investment Idea Intake + Rule-Based
+  Eligibility Check, or defer all three.
+- **Why answer is needed:** The options require different data, safety boundaries,
+  and architecture; combining them would exceed a focused sprint.
+- **Recommended default:** Option A only.
+- **Other options:** Option B, Option C, a narrower subset of A, or no Sprint 002.
+- **Impact:** A establishes policy/audit context; B prioritizes valuation and
+  portfolio modeling; C requires approved rule semantics and carries greater
+  advice risk.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+### P2. Who is the first intended user?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Is the first user a single household owner recording their own
+  information, a family-office professional, or another role?
+- **Why answer is needed:** Language, consent, ownership, workflow, and compliance
+  assumptions depend on the user.
+- **Recommended default:** One household owner in a controlled local/demo setting.
+- **Other options:** Family-office operator, adviser, multiple household members.
+- **Impact:** Professional or multi-member use adds permissions, fiduciary,
+  collaboration, and recordkeeping concerns that may make this sprint infeasible.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Household Profile
+
+### H1. What is the minimum household profile?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Which fields are necessary beyond a display name?
+- **Why answer is needed:** Household data is sensitive, and unnecessary fields
+  increase privacy and compliance exposure.
+- **Recommended default:** Use the approved fields `household_name`, `base_currency`,
+  `investment_horizon`, `liquidity_needs`, `risk_statement`, and `notes`; exclude
+  member identity information and monetary calculations.
+- **Other options:** Structured members, demographics, jurisdictions, dependents,
+  or legal entities.
+- **Impact:** More structured personal data increases security, consent, and
+  authentication requirements.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+### H2. Is Sprint 002 single-household only?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Should the system support exactly one household record in the
+  approved deployment context or multiple isolated households?
+- **Why answer is needed:** Multi-tenancy changes identifiers, isolation,
+  authorization, testing, and deletion behavior.
+- **Recommended default:** One household for the first demonstrable workflow.
+- **Other options:** Multiple households without users, or full tenant isolation.
+- **Impact:** Multiple households likely requires authentication/authorization,
+  which is currently excluded and needs separate architectural approval.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Investment Policy
+
+### IP1. Which policy categories may be captured?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Approve the neutral categories allowed in the policy editor.
+- **Why answer is needed:** Categories can become implicit investment rules if the
+  system invents or prescribes them.
+- **Recommended default:** Use the approved user-authored categories: `objectives`,
+  `time_horizon`, `liquidity`, `target_asset_allocation`, `diversification`,
+  `contribution_policy`, `rebalancing_policy`, `prohibited_assets`,
+  `leverage_policy`, `decision_process`, and `notes`.
+- **Other options:** Asset allocation, prohibited assets, concentration limits,
+  tax constraints, rebalancing, or return targets.
+- **Impact:** Numeric limits or asset rules require formal rule governance and may
+  enable evaluation behavior outside the recommended sprint.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+### IP2. What makes a policy version “Published”?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Is explicit user confirmation sufficient to create a Published
+  version, and can that version later be edited?
+- **Why answer is needed:** Auditability requires clear draft, confirmation, and
+  revision semantics.
+- **Recommended default:** Explicit confirmation creates an immutable Published
+  version; changes require a new version, and the prior version may be marked
+  Superseded but cannot be physically deleted.
+- **Other options:** Editable confirmed records, approval by another actor, or no
+  confirmation lifecycle.
+- **Impact:** Editable history weakens auditability; multi-actor approval requires
+  identity and permissions.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Portfolio Data
+
+### PD1. Is any portfolio or holdings data allowed in Sprint 002?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** May a journal mention an asset or amount, or must all portfolio
+  structures be deferred?
+- **Why answer is needed:** Structured instruments, values, and positions can pull
+  Option A into portfolio, pricing, and suitability scope.
+- **Recommended default:** Permit only user-entered target asset-class percentages
+  totaling 100%; exclude actual holdings, accounts, quantities, balances, amounts,
+  prices, costs, returns, valuation, and market data.
+- **Other options:** Optional instrument label, user-entered amount, or full manual
+  holdings.
+- **Impact:** Structured identifiers or amounts add validation, privacy, precision,
+  and potentially advice/compliance requirements.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Decision Journal
+
+### DJ1. Which journal fields are required?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Approve the minimum content necessary for a meaningful decision
+  record.
+- **Why answer is needed:** Too few fields undermine discipline; prescriptive fields
+  could imply a system-endorsed investment method.
+- **Recommended default:** Use the approved minimum fields: `title`,
+  `decision_date`, `decision_type`, `summary`, `supporting_reasons`,
+  `opposing_reasons`, `assumptions`, `uncertainties`,
+  `policy_version_reference`, `final_decision`, `review_date`, `status`,
+  `created_at`, and `updated_at`.
+- **Other options:** Evidence links, expected outcome, price, amount, review date,
+  confidence score, or attachments.
+- **Impact:** Scores and expected outcomes risk recommendation semantics; attachments
+  and links expand privacy and content-security scope.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+### DJ2. Can journal history be edited or deleted?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Define revision, correction, archive, and deletion behavior.
+- **Why answer is needed:** Audit integrity may conflict with privacy and correction
+  rights.
+- **Recommended default:** Confirmed records cannot be silently edited or physically
+  deleted; use appended correction records or new versions and allow archive.
+- **Other options:** Fully editable entries, hard delete, or append-only with no
+  correction.
+- **Impact:** Each choice changes storage, audit, UX, privacy, and compliance design.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Risk and Guardian Boundaries
+
+### RG1. How must policy “risk boundaries” be represented?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Are they freeform user statements only, or may they include numeric
+  thresholds?
+- **Why answer is needed:** Numeric thresholds could become Guardian alert logic or
+  automated rule evaluation.
+- **Recommended default:** Freeform owner-authored statements with no automated
+  interpretation, threshold, alert, or compliance status.
+- **Other options:** Structured numeric limits, categories, or severity levels.
+- **Impact:** Structured limits require approved Guardian/rule architecture and are
+  outside the recommended Sprint 002 boundary.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## AI Investment Committee Boundaries
+
+### AI1. May AI generate, summarize, or critique policy or journal content?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Confirm whether any AI behavior is allowed.
+- **Why answer is needed:** AI-generated language could be mistaken for advice and
+  would begin AI Investment Committee or agent scope.
+- **Recommended default:** No AI generation, summarization, critique, scoring, or
+  agents in Sprint 002.
+- **Other options:** Draft assistance, summarization, structured extraction, or
+  committee review.
+- **Impact:** Any AI option requires separate safety, explainability, model,
+  evaluation, privacy, and architecture approval.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Compliance
+
+### C1. What non-advisory language is required?
+
+- **Status:** Open — non-blocking for the approved local MVP boundary.
+
+- **Question:** Approve the notices, consent, and terminology that distinguish
+  user recordkeeping from investment advice or suitability review.
+- **Why answer is needed:** Policy and decision interfaces could otherwise appear
+  to endorse a strategy or decision.
+- **Recommended default:** Prominent owner-authored-record notice and explicit
+  statement that links and validation do not assess investment merit.
+- **Other options:** Legal-review-provided language, per-action attestation, or no
+  notice.
+- **Impact:** Insufficient language is a release blocker; repeated attestations may
+  increase UX friction.
+- **Blocks implementation:** No — exact copy remains a non-blocking review item.
+
+### C2. Which jurisdictions and retention duties apply?
+
+- **Status:** Open — non-blocking for the approved local MVP boundary.
+
+- **Question:** Identify intended initial jurisdiction and whether advisory,
+  fiduciary, household-record, or financial-record retention rules apply.
+- **Why answer is needed:** Retention, deletion, export, and terminology cannot be
+  designed safely without intended-use context.
+- **Recommended default:** Controlled non-production demonstration only until legal
+  review identifies obligations.
+- **Other options:** Named production jurisdiction, internal family-office use, or
+  consumer launch.
+- **Impact:** Production use may require authentication, consent, retention,
+  disclosures, exports, and formal compliance controls beyond Sprint 002.
+- **Blocks implementation:** No for the local MVP; future deployment remains deferred.
+
+## Privacy and Security
+
+### PS1. What deployment boundary is allowed without authentication?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** May Sprint 002 be implemented for local/demo use only, or must
+  remote/multi-user access be supported?
+- **Why answer is needed:** Sensitive household data cannot be safely exposed
+  remotely without identity and access controls.
+- **Recommended default:** Local, single-user demonstration only; no production or
+  shared deployment.
+- **Other options:** Add authentication through separate approval, anonymized demo
+  data only, or defer implementation.
+- **Impact:** Remote use makes authentication/authorization and security review
+  prerequisites, expanding scope materially.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+### PS2. What are the retention, export, and deletion expectations?
+
+- **Status:** Open — non-blocking for the approved local MVP boundary.
+
+- **Question:** Define how long records live and whether users need export or
+  deletion in the first approved workflow.
+- **Why answer is needed:** These requirements shape audit architecture and data
+  model boundaries.
+- **Recommended default:** Define retention before implementation; keep export and
+  deletion out of scope unless compliance makes them mandatory.
+- **Other options:** Immediate export/delete, indefinite retention, configurable
+  policy, or ephemeral demo data.
+- **Impact:** Export/delete adds contracts and security tests; indefinite retention
+  increases privacy exposure; ephemeral data reduces demonstration realism.
+- **Blocks implementation:** No — open but non-blocking for the local MVP.
+
+## UX
+
+### UX1. What is the smallest acceptable demonstration?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Approve the exact screens and completion path.
+- **Why answer is needed:** Without a fixed journey, policy editing and journal UI
+  can expand into collaboration, analytics, or design-system work.
+- **Recommended default:** Demonstrate the approved loop: single household profile,
+  policy draft, target allocation percentages, Published policy version, decision
+  journal, policy-version reference, and non-silent audit history.
+- **Other options:** Wizard, dashboard, templates, search, list filters, responsive
+  polish, or collaboration.
+- **Impact:** Additional surfaces increase implementation and test scope without
+  improving the core discipline loop.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Technical Architecture
+
+### TA1. What persistence approach is approved?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Should an approved implementation use PostgreSQL immediately, an
+  in-memory demo, or another repository abstraction?
+- **Why answer is needed:** Audit/version semantics depend on transactions,
+  constraints, and persistence behavior.
+- **Recommended default:** PostgreSQL behind explicit repository boundaries;
+  schema, migrations, and transactions require implementation approval and review.
+- **Other options:** In-memory prototype, file-based persistence, or defer storage.
+- **Impact:** In-memory is faster but cannot demonstrate durable audit history;
+  PostgreSQL requires migrations, schema, transactions, and Docker/runtime work.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+### TA2. How are actors represented without authentication?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** What actor identifier appears in audit events before identity is
+  implemented?
+- **Why answer is needed:** Audit records require attribution, but fake user
+  identity could mislead reviewers.
+- **Recommended default:** A documented constant such as `local-owner`, visibly
+  limited to local/demo use.
+- **Other options:** Anonymous actor, user-entered label, or require authentication
+  first.
+- **Impact:** User-entered labels are not trustworthy; anonymous weakens audit;
+  authentication is a major separately approved scope.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Definition of Done
+
+### DOD1. Which gates are mandatory before Sprint 002 can be marked Done?
+
+- **Status:** Resolved by product-owner decision on 2026-07-13.
+
+- **Question:** Approve the acceptance criteria, documentation, independent review,
+  security/compliance gates, and whether Docker runtime verification is required.
+- **Why answer is needed:** A sprint cannot start safely without an agreed finish
+  line and release boundary.
+- **Recommended default:** All approved user journey and audit tests pass; existing
+  CI remains green; privacy/compliance decisions are documented; independent
+  review passes; run Docker runtime validation when Docker is available, otherwise
+  disclose accurately that it was not completed.
+- **Other options:** Require Docker runtime, require authentication, require legal
+  review, or permit a local-only prototype with explicit limitations.
+- **Impact:** Stronger gates increase confidence and schedule; weaker gates restrict
+  deployment and must be clearly disclosed.
+- **Blocks implementation:** No — resolved by product-owner decision.
+
+## Decision and Follow-Up Summary
+
+The product-scope questions below are resolved or explicitly non-blocking. Sprint
+002 remains Not Started because implementation still requires a separate final
+approval after this planning pull request merges:
+
+1. P1 — candidate selection.
+2. P2 — intended user.
+3. H1/H2 — minimum household data and tenancy boundary.
+4. IP1/IP2 — policy categories and confirmation/version semantics.
+5. PD1 — portfolio/instrument data boundary.
+6. DJ1/DJ2 — journal fields and history/deletion behavior.
+7. RG1/AI1 — explicit Guardian and AI exclusions.
+8. C1/C2 — non-advisory language, jurisdiction, and compliance context.
+9. PS1/PS2 — deployment, authentication boundary, retention, export, and deletion.
+10. UX1 — minimum demonstrable journey.
+11. TA1/TA2 — persistence and audit actor architecture.
+12. DOD1 — approved Definition of Done and quality gates.
diff --git a/docs/sprints/SPRINT_002_PROPOSAL.md b/docs/sprints/SPRINT_002_PROPOSAL.md
new file mode 100644
index 0000000..7f1c275
--- /dev/null
+++ b/docs/sprints/SPRINT_002_PROPOSAL.md
@@ -0,0 +1,550 @@
+# Sprint 002 Proposal: Household Discipline Foundation
+
+## Status
+
+**Selected for Implementation Planning — Implementation Not Started**
+
+This document records approved product-planning decisions. It does not authorize
+Sprint 002 implementation. Implementation still requires explicit final approval
+after the planning pull request is reviewed and merged.
+
+## Product Owner Decision
+
+- **Selected proposal:** A — Household Investment Policy + Decision Journal
+- **Product owner decision date:** 2026-07-13
+- **Planning status:** Selected for implementation planning
+- **Implementation status:** Not Started
+- **Approval gate:** Implementation requires explicit final approval after this
+  planning pull request merges
+
+## Approved MVP Loop
+
+Single household profile → investment policy draft → target asset allocation
+percentages → explicitly confirm and publish a policy version → create a decision
+journal entry → reference the policy version in effect when the decision was
+recorded → review history that cannot be silently rewritten.
+
+## Approved Product Boundaries
+
+### Household Scope
+
+- Support exactly one household owned by the project owner.
+- Do not implement household members, invitations, roles, permissions,
+  collaboration, multiple households, or multi-tenancy.
+- Use the fixed audit actor identifier `local-owner`.
+- `local-owner` identifies local single-user development mode; it is not an
+  authenticated identity.
+
+### Minimum Household Profile
+
+- `household_name`
+- `base_currency`
+- `investment_horizon`
+- `liquidity_needs`
+- `risk_statement`
+- `notes`
+
+`base_currency` expresses policy context only. Sprint 002 performs no currency
+conversion or monetary calculation and stores no household-member personal
+identity information.
+
+### Investment Policy Categories
+
+- `objectives`
+- `time_horizon`
+- `liquidity`
+- `target_asset_allocation`
+- `diversification`
+- `contribution_policy`
+- `rebalancing_policy`
+- `prohibited_assets`
+- `leverage_policy`
+- `decision_process`
+- `notes`
+
+All policy content is entered by the user. CompoundOS does not generate investment
+rules, recommended values, or policy conclusions.
+
+### Target Asset Allocation
+
+- Store only user-entered asset-class names and target percentages.
+- Target percentages must total 100%.
+- Do not recommend percentages or provide a preset “best” allocation.
+- Do not store or compare actual holdings.
+- Do not calculate drift or generate rebalancing suggestions.
+
+### Policy Lifecycle
+
+- Draft policies are editable.
+- A Published version cannot be modified in place.
+- Changing a Published policy requires a new version.
+- Historical versions are retained and cannot be silently overwritten.
+- A Published version cannot be physically deleted.
+- A version may be marked Superseded while remaining available in history.
+
+### Decision Journal Minimum Fields
+
+- `title`
+- `decision_date`
+- `decision_type`
+- `summary`
+- `supporting_reasons`
+- `opposing_reasons`
+- `assumptions`
+- `uncertainties`
+- `policy_version_reference`
+- `final_decision`
+- `review_date`
+- `status`
+- `created_at`
+- `updated_at`
+
+All journal content is manually entered. A decision record references the selected
+Published policy version that was effective when the record was created. Confirmed
+records cannot be silently modified; corrections use an appended correction record
+or a new version. Confirmed records may be archived but not physically deleted.
+
+The system does not generate advice, scores, approvals, suitability conclusions,
+AI output, Guardian output, broker actions, trades, or transactions.
+
+### Risk, Guardian, and AI Boundaries
+
+- `risk_statement` is user-authored free text only.
+- Do not define Guardian thresholds, run risk detection, or trigger notifications.
+- Do not implement AI generation, summaries, scoring, discussions, agents, or AI
+  Investment Committee behavior.
+- Preserve policy versions and journal records only as auditable context for
+  separately approved future work.
+
+### Asset and Monetary Data Boundary
+
+- Do not store actual holdings, securities quantities, accounts, balances,
+  investment amounts, cost basis, current prices, returns, or transactions.
+- Target allocation percentages are policy statements, not portfolio data.
+- Do not connect market data or brokers.
+
+### Persistence Direction
+
+- Plan to use PostgreSQL during Sprint 002 implementation.
+- Do not use in-memory storage as formal persistence.
+- Redis carries no Sprint 002 product logic.
+- This planning task creates no schema or migration; persistence design still
+  requires implementation authorization and architecture review.
+
+### Local-Only Security Boundary
+
+- Sprint 002 has no authentication.
+- Operation is limited to local development.
+- Public internet deployment is prohibited until authentication and security
+  review are separately approved.
+- Future README and product UI must display this limitation clearly.
+- Do not claim production-grade privacy or compliance readiness.
+
+### Docker Boundary
+
+- Full Docker runtime verification remains a non-blocking Backlog item.
+- If the Sprint 002 execution environment provides Docker, Definition of Done
+  requires runtime verification.
+- If Docker remains unavailable, completion reporting must disclose that fact
+  accurately and must not fabricate validation.
+
+## 1. Problem Statement
+
+CompoundOS has a validated technical foundation but no approved user workflow.
+Households need a disciplined way to capture their context, state their own
+investment policy, and preserve the reasoning behind decisions. Without that
+foundation, later portfolio monitoring, Guardian, or committee workflows would
+lack an approved source of constraints and an auditable decision history.
+
+The system must support structured recordkeeping without interpreting the records
+as personalized investment advice, predicting markets, executing trades, or
+silently inventing policy.
+
+## 2. Sprint Objective
+
+Propose a small, demonstrable discipline workflow that can eventually let a user
+record household context, owner-approved policy statements, and decision-journal
+entries with traceable rationale. The Sprint 002 implementation objective remains
+unapproved until the project owner selects a candidate, resolves blocking
+questions, and approves detailed scope.
+
+## 3. Candidate Comparison
+
+### Option A: Household Investment Policy + Decision Journal
+
+- **User value:** Establishes why the household invests, what constraints it has,
+  and how decisions are documented before outcomes are known.
+- **Four-principle fit:** Strongest fit. It centers capital protection,
+  compounding horizon, discipline, and explainable records without prediction.
+- **End-to-end loop:** Household profile → owner-authored policy → journal entry →
+  link to policy → review an immutable history of revisions.
+- **Data needed:** Household profile, goals, horizons, liquidity statements, risk
+  boundary statements, policy versions, decision entries, arguments, assumptions,
+  uncertainties, policy links, and audit events.
+- **Safety/compliance risk:** Medium. Policy language could be mistaken for advice
+  unless clearly owner-entered and neutrally displayed. Sensitive household data
+  raises privacy obligations.
+- **Technical complexity:** Medium. Requires coherent versioning and auditability,
+  but no market data or calculation engine.
+- **Future foundation value:** High for Guardian and AI Investment Committee
+  because they will eventually need explicit, approved policy context. Moderate
+  for broker integration because policies and journals are independent of broker
+  data.
+- **Scope-expansion risks:** Policy scoring, recommendations, household member
+  permissions, document ingestion, rich collaboration, workflow approvals, or
+  automated compliance conclusions.
+- **Explicit exclusions:** Advice, suitability determinations, policy templates
+  presented as authoritative, automated rule evaluation, alerts, AI analysis,
+  trades, broker connections, authentication, and portfolio calculations.
+- **Suggested priority:** 1.
+
+### Option B: Portfolio Snapshot + Manual Holdings
+
+- **User value:** Gives the household a consolidated, manually maintained view of
+  holdings and cash without waiting for broker integrations.
+- **Four-principle fit:** Moderate. Visibility can support discipline and capital
+  protection, but a snapshot alone does not encode why decisions were made.
+- **End-to-end loop:** Create portfolio → enter holdings manually → view totals and
+  allocation snapshot → update as-of date.
+- **Data needed:** Accounts, manual holdings, quantities, user-entered prices or
+  values, currencies, asset labels, cash, valuation date, and provenance.
+- **Safety/compliance risk:** Medium to high. Stale prices, incorrect totals, asset
+  classification, and prominent allocation views may be perceived as advice or
+  monitoring even when they are only user-entered records.
+- **Technical complexity:** Medium to high. Currency, valuation, decimal precision,
+  duplicate assets, stale data, and reconciliation rules create complexity.
+- **Future foundation value:** High for future read-only broker integration and
+  Guardian; moderate for the AI Investment Committee. It lacks policy context.
+- **Scope-expansion risks:** Live pricing, performance calculations, allocation
+  targets, rebalancing, tax lots, benchmarks, alerts, and broker sync.
+- **Explicit exclusions:** Market-data feeds, performance analytics, rebalancing,
+  recommendations, trade execution, tax calculations, alerts, and broker APIs.
+- **Suggested priority:** 2, after policy and provenance decisions are approved.
+
+### Option C: Investment Idea Intake + Rule-Based Eligibility Check
+
+- **User value:** Structures an idea before action and could show whether required
+  owner-authored information is missing.
+- **Four-principle fit:** Potentially strong for discipline and explainability, but
+  a pass/fail result can easily appear to be an investment recommendation.
+- **End-to-end loop:** Submit idea → select applicable owner-approved rules → record
+  evidence → receive a procedural completeness result → retain history.
+- **Data needed:** Ideas, instruments or opportunity descriptions, thesis,
+  assumptions, evidence, rule versions, rule applicability, owner attestations,
+  and evaluation records.
+- **Safety/compliance risk:** Highest. “Eligibility” can be interpreted as
+  suitability, approval, or advice. Unapproved rules or thresholds would be
+  especially risky.
+- **Technical complexity:** High. Requires a rule representation, versioning,
+  deterministic evaluation semantics, exception handling, and careful language.
+- **Future foundation value:** High for the AI Investment Committee and Guardian;
+  lower for broker integration. It depends on an approved policy/rule foundation
+  that does not yet exist.
+- **Scope-expansion risks:** Recommendation scores, automated approval, market-data
+  enrichment, AI research, alerts, committee voting, and trade handoff.
+- **Explicit exclusions:** Advice, suitability claims, ranking, scoring,
+  autonomous approval, AI agents, alerts, market prediction, and execution.
+- **Suggested priority:** 3; defer until owner-approved policies and rule semantics
+  exist.
+
+## 4. Recommended Option and Rationale
+
+**Selected direction: Option A — Household Investment Policy + Decision Journal.**
+
+**Implementation approval state: Not Started; not yet authorized.**
+
+The product owner selected Option A because it provides the strongest foundation
+for CompoundOS's discipline and
+explainability principles while avoiding market data, portfolio calculations, and
+rule-engine semantics. It creates policy provenance needed by Options B and C and
+by future Guardian or committee work. The approved product boundaries are recorded
+above; implementation still depends on final approval after this planning pull
+request merges.
+
+## 5. Proposed User Journey
+
+1. The user sees a clear notice that CompoundOS is recording user-provided policy
+   and decisions, not providing investment advice.
+2. The user creates a household profile with a display name and optional planning
+   context approved for this sprint.
+3. The user records long-term goals, time horizons, liquidity needs, and risk
+   boundary statements in their own words.
+4. The user reviews and explicitly confirms a version of the household investment
+   policy.
+5. The user creates a decision-journal entry describing an idea or decision,
+   rationale, counterarguments, assumptions, uncertainties, and decision status.
+6. The user links the entry to one or more approved policy statements without the
+   system judging compliance or quality.
+7. The user reviews the saved entry and its policy-version references.
+8. Later edits create traceable revisions rather than silently rewriting history.
+
+## 6. Proposed Scope
+
+- Exactly one household workspace for the project owner in local development.
+- Structured capture of owner-provided household planning context.
+- Draft and confirmed policy records with explicit version identifiers.
+- Decision-journal creation and read views.
+- Structured fields for rationale, counterarguments, assumptions, uncertainties,
+  and status.
+- Links from journal entries to confirmed policy statements or sections.
+- Append-only audit events for create, confirm, revise, and archive actions.
+- Neutral, non-advisory labels and disclaimers.
+- Minimal end-to-end UI and API contracts necessary to demonstrate the workflow.
+
+## 7. Explicit Non-Goals
+
+- Investment recommendations, suitability determinations, or personalized advice.
+- Automatic trading, order preparation, or execution.
+- Broker or market-data integrations.
+- Manual holdings, portfolio valuation, performance, or rebalancing.
+- AI agents, AI Investment Committee behavior, AI-generated analysis, or voting.
+- Guardian monitoring, alerts, thresholds, or escalation.
+- Rule engines, automated eligibility, scores, rankings, or pass/fail conclusions.
+- Authentication, authorization, invitations, household members, collaboration,
+  multiple households, and multi-tenancy.
+- Prescriptive investment policy templates or invented investment rules.
+- Database schema or migrations during planning.
+- Actual holdings, securities quantities, accounts, balances, investment amounts,
+  costs, prices, returns, or transactions.
+- Notifications, document uploads, OCR, imports, or exports.
+
+## 8. Proposed Frontend Scope
+
+- Household profile form and read-only summary.
+- Policy editor organized by approved conceptual categories, with draft/confirm
+  states and visible version metadata.
+- Decision-journal form and detail view.
+- Policy-link selector that only references confirmed user-authored policy content.
+- Revision/audit timeline showing actor label, action, and timestamp.
+- Persistent non-advisory messaging and clear distinction between user input and
+  system metadata.
+- Accessible validation messages for missing required recordkeeping fields.
+
+No visual design, component library, route structure, or state-management choice
+is approved by this proposal.
+
+## 9. Proposed Backend Scope
+
+- API contracts for household profile, policy drafts/versions, journal entries,
+  policy links, and audit-event reads.
+- Input validation for required recordkeeping fields and allowed lifecycle states.
+- Explicit policy confirmation and revision operations.
+- Server-generated identifiers, timestamps, version references, and audit events.
+- Neutral retrieval only; no recommendation, scoring, rules evaluation, or alerts.
+
+Persistence technology, service/module boundaries, and transaction behavior remain
+implementation decisions requiring architecture review.
+
+## 10. Proposed Data Entities (Conceptual Only)
+
+These are domain concepts, not database schemas:
+
+- **HouseholdProfile:** The approved minimum fields for the one local household.
+- **HouseholdGoal:** User-authored objective, horizon, priority label, and notes.
+- **LiquidityNeed:** User-authored description and timing context without monetary
+  calculations.
+- **RiskBoundaryStatement:** Freeform owner statement, not a computed tolerance or
+  system threshold.
+- **InvestmentPolicy:** Stable identity for a household policy.
+- **InvestmentPolicyVersion:** Immutable snapshot of a draft or confirmed policy.
+- **PolicyStatement:** Versioned, user-authored policy section or statement.
+- **DecisionJournalEntry:** Decision record with lifecycle state and timestamps.
+- **DecisionArgument:** Supporting or opposing reason supplied by the user.
+- **DecisionAssumption:** User-stated assumption and optional uncertainty note.
+- **PolicyReference:** Link from a journal entry to a specific policy version and
+  statement.
+- **AuditEvent:** Append-only record of a meaningful state change.
+
+## 11. API Endpoint Proposals (Contracts Only)
+
+Names are illustrative and not approved routes:
+
+- `POST /api/households` — create a household profile from owner-provided fields.
+- `GET /api/households/{household_id}` — retrieve the profile.
+- `PATCH /api/households/{household_id}` — revise allowed profile fields and emit
+  an audit event.
+- `POST /api/households/{household_id}/policies` — create a policy draft.
+- `GET /api/policies/{policy_id}` — retrieve current policy metadata.
+- `POST /api/policies/{policy_id}/versions` — save a new immutable draft version.
+- `POST /api/policies/{policy_id}/versions/{version_id}/confirm` — explicitly
+  confirm a version; no evaluation is performed.
+- `GET /api/policies/{policy_id}/versions` — list version metadata.
+- `POST /api/households/{household_id}/journal-entries` — create a journal entry.
+- `GET /api/journal-entries/{entry_id}` — retrieve an entry and policy references.
+- `PATCH /api/journal-entries/{entry_id}` — create an auditable revision according
+  to the approved immutability model.
+- `GET /api/households/{household_id}/audit-events` — retrieve audit history.
+
+Contracts must use neutral errors and never return advice, eligibility, score,
+approval, or trade instructions.
+
+## 12. Auditability Requirements
+
+- Every confirmed policy version has a stable identifier and confirmation time.
+- Journal policy links target a specific immutable policy version.
+- Create, confirm, revise, status-change, archive, and link-change actions are
+  attributable and timestamped.
+- Historical confirmed policy content cannot be silently overwritten.
+- Journal history behavior—immutable entries versus explicit revisions—must be
+  owner-approved before implementation.
+- Audit events distinguish user-entered content from server-generated metadata.
+- Time source, timezone display, retention, deletion, and correction semantics are
+  documented and tested.
+
+## 13. Explainability Requirements
+
+- A journal entry displays the user's rationale, counterarguments, assumptions,
+  uncertainties, and referenced policy text together.
+- The UI explains that a policy link is a traceability relationship, not a system
+  conclusion that the decision follows the policy.
+- No hidden score, model inference, generated recommendation, or automatic rule
+  interpretation is permitted.
+- Lifecycle labels and validation messages use plain language.
+- Any system-generated metadata is visibly distinguished from user-authored text.
+
+## 14. Privacy and Security Considerations
+
+- Household goals, liquidity needs, risk statements, and decision records are
+  sensitive financial-planning data.
+- Planning must define data minimization before choosing required fields.
+- Logs and error messages must not expose full policy or journal text.
+- Secrets remain outside source control and examples contain placeholders only.
+- Transport, storage encryption, backup, retention, deletion, and export policies
+  require explicit decisions before production use.
+- Authentication is not part of this proposed sprint, creating a blocker for any
+  deployment beyond a tightly controlled local/demo environment.
+
+## 15. Compliance Questions
+
+- Does storing user-authored policy and journal content create recordkeeping,
+  retention, fiduciary, or advisory obligations in intended jurisdictions?
+- What disclaimer and consent language is required to distinguish recordkeeping
+  from advice?
+- Can the product use terms such as “investment policy,” “risk boundary,” and
+  “decision” without implying suitability review?
+- Must users be able to export, correct, or delete records, and what audit history
+  must remain after correction or deletion?
+- Is a household profile allowed to include information about other people before
+  roles, consent, and authentication are implemented?
+
+## 16. Acceptance Criteria
+
+Proposed criteria, subject to approval:
+
+- A user can create and retrieve one household profile using only approved fields.
+- A user can create, review, and explicitly confirm a policy version.
+- A user can create and retrieve a journal entry with rationale,
+  counterarguments, assumptions, and uncertainties.
+- A journal entry can reference a specific confirmed policy version and statement.
+- Revisions preserve the approved historical/audit representation.
+- The UI clearly labels user-authored data and displays non-advisory language.
+- APIs never return recommendations, scores, eligibility, alerts, or trade actions.
+- Automated tests cover validation, version linkage, audit events, API contracts,
+  and the demonstrable frontend journey.
+- Existing Sprint 001 health, lint, type-check, tests, build, and CI remain green.
+- Security, compliance, retention, and authentication deployment boundaries are
+  documented.
+
+## 17. Test Strategy
+
+- **Domain tests:** lifecycle transitions, version immutability, policy references,
+  required fields, and audit-event creation.
+- **API tests:** contract shapes, invalid identifiers, validation errors,
+  concurrency behavior once approved, and absence of advisory outputs.
+- **Frontend tests:** form validation, draft/confirm flow, journal capture, policy
+  linking, audit timeline, and disclaimer presence.
+- **End-to-end test:** create profile → confirm policy → record journal entry → link
+  policy → inspect history.
+- **Security/privacy tests:** sensitive-field redaction in logs/errors and rejected
+  overlong or malformed content.
+- **Regression tests:** all Sprint 001 health and CI checks.
+
+## 18. Documentation Updates Required During Implementation
+
+- `docs/MASTER_PLAN.md` after explicit scope approval.
+- `docs/PRD.md` with approved user stories and non-goals.
+- `docs/ARCHITECTURE.md` with approved persistence and module boundaries.
+- New ADRs for persistence, audit immutability, and deployment/authentication
+  boundaries where decisions are significant.
+- `docs/INVESTMENT_RULEBOOK.md` only if the owner approves policy semantics; no
+  rules may be silently added.
+- `docs/GUARDIAN.md` and `docs/AI_INVESTMENT_COMMITTEE.md` only to restate exclusion
+  boundaries if needed, not to implement those systems.
+- `README.md`, API contract documentation, privacy notes, test instructions, and
+  `docs/CHANGELOG.md`.
+
+## 19. Risks and Mitigations
+
+- **Recordkeeping perceived as advice:** Use neutral language, user-authored labels,
+  disclaimers, and compliance review; do not score or interpret policy.
+- **Sensitive household data without authentication:** Restrict approved deployment
+  scope or make authentication a prerequisite in a separately approved decision.
+- **Audit history conflicts with deletion rights:** Resolve retention/correction
+  semantics before implementation.
+- **Scope expands into a rule engine:** Treat policy links as references only and
+  prohibit automated evaluation.
+- **Prescriptive templates invent rules:** Start with approved neutral categories
+  and freeform owner statements, subject to owner review.
+- **Over-modeling early:** Approve the smallest end-to-end entities and defer
+  portfolio, market, member, and collaboration models.
+- **Ambiguous household ownership:** Decide single-household and actor assumptions
+  before coding.
+
+## 20. Dependencies
+
+- Final implementation approval after the planning pull request merges.
+- Resolution of any architecture or compliance question promoted to a blocker
+  before implementation approval.
+- Compliance review of language, retention, and intended deployment boundary.
+- Architecture decisions for persistence, audit behavior, identifiers, and
+  authentication/deployment boundary.
+- Approved UX copy for non-advisory notices and confirmations.
+- Docker runtime verification remains a non-blocking Sprint 001 backlog item; run
+  it when Docker is available, otherwise disclose that it was not completed.
+
+No new software dependency is approved by this planning document.
+
+## 21. Definition of Done
+
+Proposed definition, not approved:
+
+- Project owner has approved one option, scope, non-goals, and all blocking
+  decisions.
+- Approved end-to-end workflow meets its acceptance criteria.
+- Audit and explainability requirements are implemented and tested.
+- No advice, trading, broker, AI agent, Guardian, authentication, or unapproved
+  rule behavior has been introduced.
+- Privacy/security and deployment limitations are documented and enforced.
+- Tests, lint, type-check, build, and CI pass.
+- Required product, architecture, ADR, API, privacy, and changelog documentation is
+  current.
+- Independent review confirms implementation matches the approved Sprint 002
+  scope.
+
+## 22. Estimated Implementation Sequence
+
+This sequence is an estimate only and does not authorize work:
+
+1. Resolve blocking product, compliance, privacy, audit, and architecture questions.
+2. Approve a narrow PRD amendment, API contracts, entity concepts, and ADRs.
+3. Establish domain validation and audit behavior with tests.
+4. Add the minimal approved persistence layer and migrations.
+5. Implement household profile and policy version APIs.
+6. Implement journal and policy-reference APIs.
+7. Implement the minimal frontend workflow.
+8. Add end-to-end, privacy, regression, and failure-path tests.
+9. Update documentation and complete independent review.
+
+## 23. Decisions Requiring Project-Owner Approval
+
+- Detailed implementation architecture and final acceptance-test wording.
+- Non-advisory disclaimer and consent language.
+- PostgreSQL schema, migration, transaction, and repository design.
+- Retention, export, deletion, backup, and encryption expectations.
+- Any decision to expand beyond local-only, no-auth operation.
+
+## 24. Planning Outcome
+
+Option A has been selected for implementation planning with the approved boundaries
+in this document. Sprint 002 remains Not Started until this planning pull request
+merges and the project owner separately authorizes implementation.
```

## 8. Current Git Status

```text
## planning/sprint-002...origin/planning/sprint-002
?? sprint-001-critical-files.txt
?? sprint-001-review-report.md
?? sprint-001-review.diff
?? sprint-002-planning-review.md
```

## 9. Read-Only Review Declaration

This file is generated solely for read-only review. It is intentionally untracked
and has not been staged, committed, pushed, attached to the pull request, or merged.
No Sprint 002 implementation work was performed.

