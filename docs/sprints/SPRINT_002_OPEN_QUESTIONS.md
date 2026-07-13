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

### Resolved for the Local MVP on 2026-07-13

- Provisional non-advisory copy and its three display checkpoints.
- Temporary no-export/no-general-hard-delete boundary, immutable-record retention,
  Draft discard behavior, and development-only full database reset.

### Open but Non-Blocking for the Local MVP

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
- **Recommended default:** Enforce at most one active HouseholdProfile in the
  database/transaction layer; any second create returns HTTP 409 and cannot be
  bypassed with a different supplied ID.
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

- **Status:** Resolved for local MVP; legal review deferred before any non-local or
  production use.

- **Question:** Approve the notices, consent, and terminology that distinguish
  user recordkeeping from investment advice or suitability review.
- **Why answer is needed:** Policy and decision interfaces could otherwise appear
  to endorse a strategy or decision.
- **Recommended default:** Display the approved provisional copy on core-flow entry,
  before policy publication, and before journal confirmation: “CompoundOS records
  information you enter. It does not evaluate whether an investment policy or
  decision is suitable, appropriate, or likely to succeed. Policy links and
  validations are for recordkeeping only and do not constitute investment, tax,
  or legal advice.” Do not claim lawyer review or implement complex consent.
- **Other options:** Legal-review-provided language, per-action attestation, or no
  notice.
- **Impact:** Insufficient language is a release blocker; repeated attestations may
  increase UX friction.
- **Blocks implementation:** No — resolved for the local MVP.

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
  shared deployment. Web, API, PostgreSQL, and Redis host ports default to
  `127.0.0.1`; containers may listen on `0.0.0.0` internally. This is not a
  substitute for authentication or production security.
- **Other options:** Add authentication through separate approval, anonymized demo
  data only, or defer implementation.
- **Impact:** Remote use makes authentication/authorization and security review
  prerequisites, expanding scope materially.
- **Blocks implementation:** No — resolved by product-owner decision.

### PS2. What are the retention, export, and deletion expectations?

- **Status:** Resolved for local MVP; production retention/export/deletion policy
  deferred.

- **Question:** Define how long records live and whether users need export or
  deletion in the first approved workflow.
- **Why answer is needed:** These requirements shape audit architecture and data
  model boundaries.
- **Recommended default:** No export or general hard-delete API; Published policy
  versions, Confirmed journal revisions, and AuditEvents cannot be physically
  deleted; Drafts may be discarded; a documented development-only database reset
  may clear all local data but is not a product deletion feature.
- **Other options:** Immediate export/delete, indefinite retention, configurable
  policy, or ephemeral demo data.
- **Impact:** Export/delete adds contracts and security tests; indefinite retention
  increases privacy exposure; ephemeral data reduces demonstration realism.
- **Blocks implementation:** No — resolved for the local MVP.

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
  migrations upgrade an empty database; business records and AuditEvents commit or
  roll back together; CI and repository integration tests use real isolated
  PostgreSQL. SQLite/mocks may support unit tests but cannot replace integration
  tests. Redis carries no product logic.
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
- **Recommended default:** Require the approved journey, lifecycle/immutability,
  single-household, allocation-100%, real-PostgreSQL, transaction rollback,
  localhost binding, disclaimer-display, prohibited-scope, standard CI, and
  independent-review gates. Run full Docker runtime validation when available;
  otherwise disclose accurately that it was not completed.
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
