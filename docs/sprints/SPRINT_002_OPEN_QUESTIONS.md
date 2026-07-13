# Sprint 002 Open Questions

## Status

Planning questions only. Sprint 002 is **Not Started** and implementation is not
approved. Recommended defaults below are proposals, not product decisions.

## Product

### P1. Which candidate should define Sprint 002?

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
- **Blocks implementation:** Yes.

### P2. Who is the first intended user?

- **Question:** Is the first user a single household owner recording their own
  information, a family-office professional, or another role?
- **Why answer is needed:** Language, consent, ownership, workflow, and compliance
  assumptions depend on the user.
- **Recommended default:** One household owner in a controlled local/demo setting.
- **Other options:** Family-office operator, adviser, multiple household members.
- **Impact:** Professional or multi-member use adds permissions, fiduciary,
  collaboration, and recordkeeping concerns that may make this sprint infeasible.
- **Blocks implementation:** Yes.

## Household Profile

### H1. What is the minimum household profile?

- **Question:** Which fields are necessary beyond a display name?
- **Why answer is needed:** Household data is sensitive, and unnecessary fields
  increase privacy and compliance exposure.
- **Recommended default:** Display name plus optional freeform planning context;
  exclude legal names, addresses, tax identifiers, birth dates, and contact data.
- **Other options:** Structured members, demographics, jurisdictions, dependents,
  or legal entities.
- **Impact:** More structured personal data increases security, consent, and
  authentication requirements.
- **Blocks implementation:** Yes.

### H2. Is Sprint 002 single-household only?

- **Question:** Should the system support exactly one household record in the
  approved deployment context or multiple isolated households?
- **Why answer is needed:** Multi-tenancy changes identifiers, isolation,
  authorization, testing, and deletion behavior.
- **Recommended default:** One household for the first demonstrable workflow.
- **Other options:** Multiple households without users, or full tenant isolation.
- **Impact:** Multiple households likely requires authentication/authorization,
  which is currently excluded and needs separate architectural approval.
- **Blocks implementation:** Yes.

## Investment Policy

### IP1. Which policy categories may be captured?

- **Question:** Approve the neutral categories allowed in the policy editor.
- **Why answer is needed:** Categories can become implicit investment rules if the
  system invents or prescribes them.
- **Recommended default:** Goals, time horizons, liquidity needs, risk boundary
  statements, and freeform owner notes only.
- **Other options:** Asset allocation, prohibited assets, concentration limits,
  tax constraints, rebalancing, or return targets.
- **Impact:** Numeric limits or asset rules require formal rule governance and may
  enable evaluation behavior outside the recommended sprint.
- **Blocks implementation:** Yes.

### IP2. What makes a policy version “confirmed”?

- **Question:** Is explicit user confirmation sufficient, and can a confirmed
  version later be edited?
- **Why answer is needed:** Auditability requires clear draft, confirmation, and
  revision semantics.
- **Recommended default:** Explicit confirmation creates an immutable version;
  changes require a new draft/version.
- **Other options:** Editable confirmed records, approval by another actor, or no
  confirmation lifecycle.
- **Impact:** Editable history weakens auditability; multi-actor approval requires
  identity and permissions.
- **Blocks implementation:** Yes.

## Portfolio Data

### PD1. Is any portfolio or holdings data allowed in Sprint 002?

- **Question:** May a journal mention an asset or amount, or must all portfolio
  structures be deferred?
- **Why answer is needed:** Structured instruments, values, and positions can pull
  Option A into portfolio, pricing, and suitability scope.
- **Recommended default:** No portfolio/holding entities; allow only a user-entered
  decision title and narrative, with no valuation or market-data behavior.
- **Other options:** Optional instrument label, user-entered amount, or full manual
  holdings.
- **Impact:** Structured identifiers or amounts add validation, privacy, precision,
  and potentially advice/compliance requirements.
- **Blocks implementation:** Yes.

## Decision Journal

### DJ1. Which journal fields are required?

- **Question:** Approve the minimum content necessary for a meaningful decision
  record.
- **Why answer is needed:** Too few fields undermine discipline; prescriptive fields
  could imply a system-endorsed investment method.
- **Recommended default:** Title, decision/status label, rationale,
  counterarguments, assumptions, uncertainties, and policy references.
- **Other options:** Evidence links, expected outcome, price, amount, review date,
  confidence score, or attachments.
- **Impact:** Scores and expected outcomes risk recommendation semantics; attachments
  and links expand privacy and content-security scope.
- **Blocks implementation:** Yes.

### DJ2. Can journal history be edited or deleted?

- **Question:** Define revision, correction, archive, and deletion behavior.
- **Why answer is needed:** Audit integrity may conflict with privacy and correction
  rights.
- **Recommended default:** Preserve immutable revisions; allow archive and explicit
  correction events; defer hard deletion pending compliance review.
- **Other options:** Fully editable entries, hard delete, or append-only with no
  correction.
- **Impact:** Each choice changes storage, audit, UX, privacy, and compliance design.
- **Blocks implementation:** Yes.

## Risk and Guardian Boundaries

### RG1. How must policy “risk boundaries” be represented?

- **Question:** Are they freeform user statements only, or may they include numeric
  thresholds?
- **Why answer is needed:** Numeric thresholds could become Guardian alert logic or
  automated rule evaluation.
- **Recommended default:** Freeform owner-authored statements with no automated
  interpretation, threshold, alert, or compliance status.
- **Other options:** Structured numeric limits, categories, or severity levels.
- **Impact:** Structured limits require approved Guardian/rule architecture and are
  outside the recommended Sprint 002 boundary.
- **Blocks implementation:** Yes.

## AI Investment Committee Boundaries

### AI1. May AI generate, summarize, or critique policy or journal content?

- **Question:** Confirm whether any AI behavior is allowed.
- **Why answer is needed:** AI-generated language could be mistaken for advice and
  would begin AI Investment Committee or agent scope.
- **Recommended default:** No AI generation, summarization, critique, scoring, or
  agents in Sprint 002.
- **Other options:** Draft assistance, summarization, structured extraction, or
  committee review.
- **Impact:** Any AI option requires separate safety, explainability, model,
  evaluation, privacy, and architecture approval.
- **Blocks implementation:** Yes.

## Compliance

### C1. What non-advisory language is required?

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
- **Blocks implementation:** Yes, pending owner/compliance approval.

### C2. Which jurisdictions and retention duties apply?

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
- **Blocks implementation:** Yes for production; no for documentation-only planning.

## Privacy and Security

### PS1. What deployment boundary is allowed without authentication?

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
- **Blocks implementation:** Yes.

### PS2. What are the retention, export, and deletion expectations?

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
- **Blocks implementation:** Yes.

## UX

### UX1. What is the smallest acceptable demonstration?

- **Question:** Approve the exact screens and completion path.
- **Why answer is needed:** Without a fixed journey, policy editing and journal UI
  can expand into collaboration, analytics, or design-system work.
- **Recommended default:** Profile summary, policy draft/confirm, journal create,
  journal detail with policy link, and audit timeline.
- **Other options:** Wizard, dashboard, templates, search, list filters, responsive
  polish, or collaboration.
- **Impact:** Additional surfaces increase implementation and test scope without
  improving the core discipline loop.
- **Blocks implementation:** Yes.

## Technical Architecture

### TA1. What persistence approach is approved?

- **Question:** Should an approved implementation use PostgreSQL immediately, an
  in-memory demo, or another repository abstraction?
- **Why answer is needed:** Audit/version semantics depend on transactions,
  constraints, and persistence behavior.
- **Recommended default:** PostgreSQL behind explicit repository boundaries, but
  only after an ADR and schema review are approved.
- **Other options:** In-memory prototype, file-based persistence, or defer storage.
- **Impact:** In-memory is faster but cannot demonstrate durable audit history;
  PostgreSQL requires migrations, schema, transactions, and Docker/runtime work.
- **Blocks implementation:** Yes.

### TA2. How are actors represented without authentication?

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
- **Blocks implementation:** Yes.

## Definition of Done

### DOD1. Which gates are mandatory before Sprint 002 can be marked Done?

- **Question:** Approve the acceptance criteria, documentation, independent review,
  security/compliance gates, and whether Docker runtime verification is required.
- **Why answer is needed:** A sprint cannot start safely without an agreed finish
  line and release boundary.
- **Recommended default:** All approved user journey and audit tests pass; existing
  CI remains green; privacy/compliance decisions are documented; independent
  review passes; Docker runtime is a gate only if the owner explicitly promotes
  the existing backlog item.
- **Other options:** Require Docker runtime, require authentication, require legal
  review, or permit a local-only prototype with explicit limitations.
- **Impact:** Stronger gates increase confidence and schedule; weaker gates restrict
  deployment and must be clearly disclosed.
- **Blocks implementation:** Yes.

## Blocking-Question Summary

The following must be answered before implementation authorization:

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
