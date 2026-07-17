# Sprint 004 Technical Design: Guardian Monitoring Foundation

- Date: 2026-07-17
- Status: Approved Technical Design — Implementation Not Authorized
- Owner Decisions: All 13 Resolved by Project Owner on 2026-07-17
- Baseline: main @ 759a556
- Branch: planning/sprint-004-technical-design

## 1. Candidate Analysis

### Candidate A: Guardian Monitoring Foundation (RECOMMENDED)

Guardian is a passive, rule-based monitoring system that evaluates Policy
allocations and Portfolio holdings against Owner-defined thresholds. It
detects conditions, records them as neutral Events, and leaves all action
to the human Owner.

**User value**: High. With three completed data domains (Policy, Portfolio,
Decisions), the system can now tell the Owner *what changed* without the
Owner having to manually cross-reference spreadsheets. Guardian makes the
existing data actionable.

**Dependencies satisfied**: Yes. Guardian requires Policy (target allocations)
and Portfolio (actual holdings) — both are Done. No external services needed.

**Data model complexity**: Medium. Guardian introduces two new entities
(GuardianCheck + GuardianEvent) reusing the proven Identity+Draft convention
from Policy and Portfolio. Rules are user-authored, not system-generated.

**Financial/safety risk**: Low. Guardian is passive detection, not active
intervention. No trading. No advice. Every Event has a fixed severity label
and a non-interpreted threshold. The system never auto-acts.

**Testability**: High. Every rule is a pure function of Policy Version snapshot
+ Portfolio Snapshot. No market data. No external APIs. No time-based flakiness.

**Real feedback loop**: Yes. Owner configures thresholds → Guardian evaluates →
Owner sees Events → Owner adjusts Policy or Portfolio → Guardian re-evaluates.
This is the first closed-loop feedback mechanism in CompoundOS.

**Unlocks future Sprints**: Guardian Events feed into notification escalation
(Sprint 005), AI Committee evidence (Sprint 006), and eventually alert routing.

**Estimated slices**: 3 (A: DB + rules, B: API + evaluation engine, C: UI).

**External services**: None. Fully local-only.

**Local-only**: Yes. No data leaves the machine.

---

### Candidate B: Data Persistence and Orchestration Foundation

Data Orchestration provides a job/run/attempt infrastructure for recurring
data collection tasks — the groundwork for market data feeds, scheduled
Guardian runs, and periodic reporting.

**User value**: Medium. Orchestration is infrastructure, not a user-facing
feature. The Owner sees no new page or workflow in this sprint. Value accrues
only when future sprints build on it.

**Dependencies satisfied**: Partially. The job runner needs PostgreSQL and
a worker process (Autopilot provides the worker pattern). But the *consumers*
of orchestration (market data, scheduled Guardian, reports) do not exist yet.

**Data model complexity**: High. Job definitions, runs, attempts, leases,
idempotency keys, retry/backoff policies, payload storage, secret boundaries,
and scheduling — all before any consumer exists to use them.

**Financial/safety risk**: Medium. A misconfigured job runner could hammer
external APIs, leak credentials, or silently fail on retry exhaustion.

**Testability**: Medium. Idempotency and lease recovery require careful
concurrency tests that are hard to write without a real multi-process
environment.

**Real feedback loop**: No. Until a consumer exists, orchestration produces
no user-visible outcome.

**Unlocks future Sprints**: Yes — but pre-building infrastructure without a
consumer risks over-engineering. Guardian and AI Committee can start with
synchronous evaluation (no scheduler needed).

**External services**: Potentially. Data source credentials, API keys.

**Local-only**: Yes, but the job runner pattern introduces background
processes that complicate the simple local-MVP launch model.

---

### Candidate C: AI Investment Committee Foundation

AI Committee provides structured evidence collection, prompt/model/version
recording, and human-approval-gated analysis workflows. It never generates
trade instructions or auto-changes Policy.

**User value**: Low in current state. Without Guardian (to surface what
*changed*) and Data Orchestration (to feed market context), the AI Committee
has no structured evidence to analyze. It would be a prompt-response system
operating on stale data.

**Dependencies satisfied**: No. AI Committee needs Guardian Events (for
"What changed?") and ideally market data or at least Portfolio trends.
Neither exists. The Committee can read Policy and Portfolio directly, but
without Guardian's detection layer, it has no reason to run.

**Data model complexity**: High. Evidence provenance, prompt versioning,
model identity, hallucination boundaries, human approval workflow,
recommendation-vs-decision separation — all on a foundation where the
triggering data does not exist.

**Financial/safety risk**: High. An AI model that generates plausible-looking
analysis without structured input data could mislead the Owner. The safety
boundary ("never trade, never change Policy") is clear, but the *reliability*
of analysis without Guardian or market data is poor.

**Testability**: Low. LLM output is non-deterministic. Testing "hallucination
boundaries" and "sensitive information boundaries" requires adversarial
evaluation infrastructure not yet built.

**Real feedback loop**: No. Without Guardian events as input, the Committee
has nothing to react to.

**Unlocks future Sprints**: Yes, but requires Guardian + Data Orchestration
first. Attempting AI Committee before these is building the roof before
the walls.

**External services**: Yes. Requires LLM API access (provider, credentials,
cost). Violates the pure local-only boundary.

---

### Candidate D: Notification Escalation (considered, not recommended)

Notification Escalation delivers Guardian Events or other system outputs
to external channels (email, messaging platforms). 

**Rejection rationale**: CompoundOS is currently local-only. Notification
requires outbound connectivity, platform credentials, and multi-channel
routing — infrastructure that belongs in a post-MVP hardening sprint,
not in Sprint 004. Guardian Events must exist first (they can be viewed
in the UI). Premature notification infrastructure duplicates the Hermes
cron delivery pattern without adding unique Sprint 004 value.

---

### Recommendation Summary

| Dimension | Guardian (A) | Orchestration (B) | AI Committee (C) |
|-----------|-------------|-------------------|------------------|
| User value | High | Medium (deferred) | Low (no inputs) |
| Dependencies | ✅ All met | ⚠️ No consumers | ❌ Guardian missing |
| Data complexity | Medium | High | High |
| Safety risk | Low | Medium | High |
| Testability | High | Medium | Low |
| Feedback loop | ✅ Yes | ❌ No | ❌ No |
| Unlocks future | ✅ Guardian→AI, Notify | ✅ Scheduler infra | ⚠️ Needs A+B first |
| External services | None | Potential | ✅ Requires LLM API |
| Local-only | ✅ Pure | ⚠️ Background process | ❌ API dependency |
| Slice count | 3 | 3-4 | 3-4 |

**Recommended: Candidate A — Guardian Monitoring Foundation.**

Reasons:
1. All dependencies are satisfied (Policy + Portfolio exist).
2. Creates the first real feedback loop: Owner sets rules → system detects → Owner acts.
3. No external services, no credentials, no API costs.
4. Pure local-only — every Guardian evaluation runs in-process.
5. Unlocks AI Committee (Sprint 006+) and Notification (Sprint 005+).
6. Incremental data model — two new tables on top of proven Identity+Draft pattern.
7. Low safety risk — passive detection, no action, no advice.

Rejected:
- B (Orchestration): Pre-building infrastructure without a consumer. Add after Guardian.
- C (AI Committee): Missing dependencies (Guardian), external API dependency, high risk.
- D (Notification): Premature for local-only MVP. Depends on Guardian Events existing first.

---

## 2. Problem Statement

The Owner currently has Policy (target allocations), Portfolio (actual holdings),
and Decision Journal (recorded rationale). But there is no automated way to
answer the question: "Is my actual portfolio aligned with my stated policy?"

Guardian fills this gap by evaluating Policy Version snapshots against Portfolio
Snapshots using Owner-defined rules and recording the results as neutral,
non-advisory Guardian Events.

---

## 3. Goals

- Detect when Portfolio holdings drift from Policy target allocations by more
  than an Owner-defined threshold.
- Detect when a holding category exceeds an Owner-defined exposure limit.
- Detect when a Portfolio Snapshot is older than an Owner-defined staleness
  threshold (no recent valuation).
- Record every detection as an immutable GuardianEvent with the specific Policy
  Version and Portfolio Snapshot that triggered it.
- Never recommend action, never auto-trade, never interpret the significance
  of a detection beyond mechanical threshold comparison.

---

## 4. Non-Goals (Explicit)

- No automatic trading, rebalancing, or order placement.
- No investment advice, recommendation, suitability, or scoring.
- No market data integration or external price feeds.
- No broker synchronization.
- No AI-generated rules or thresholds.
- No multi-household or multi-portfolio monitoring.
- No notification delivery (email, SMS, push) — events are viewable in the
  local UI only.
- No scheduled/cron-based evaluation in Sprint 004 — evaluation is
  manual (Owner triggers) or on-demand (after Portfolio Confirm).
- No authentication or public deployment.
- No hard-delete or retirement lifecycle for Confirmed Checks — once
  confirmed, a Check identity persists indefinitely, matching the
  Policy Version and Portfolio Snapshot immutability patterns. The
  Owner can stop using a Check without deleting it.

---

## 5. Domain Terminology

| Term | Definition |
|------|-----------|
| Guardian Check | A named, Owner-defined rule configuration (e.g., "Equity drift > 5pp") |
| Guardian Event | An immutable record of a single threshold breach. Contains the Check ID, the Policy Version and Portfolio Snapshot evaluated, and the computed metric. Events record ONLY when a threshold is exceeded. The `exceeded` boolean is always TRUE for events. |
| Guardian Evaluation Run | An immutable record of a single evaluation pass (manual trigger). Records whether evaluation executed, how many Checks were evaluated, how many Events were created, and why any Checks were skipped. This is the "evaluation happened" fact — distinct from Events which are the "threshold breached" facts. |
| Threshold | A numeric boundary in percentage points (drift, category_exposure) or days (staleness). Always Owner-configured, never system-generated. |
| Severity | A fixed label on each Check: `info`, `warning`, `critical`. Purely organizational — no automatic escalation. Owner explicitly selects severity in the Check Draft. |
| Staleness | A Check that fires when `valuation_date` of the latest Portfolio Snapshot is older than N calendar days from an explicit `as_of` evaluation date injected by the evaluation engine. |
| Drift | The absolute percentage-point difference between a Policy allocation's target percentage and the corresponding Portfolio holding category's actual percentage of total portfolio value. Computed as `abs(actual_pct - target_pct)`. |
| Category Exposure | A single Portfolio holding category exceeding X% of total Portfolio value. Renamed from "concentration" per OD-S4-004 to avoid confusion with single-security concentration. |
| Confirmed | The immutable lifecycle state of a Guardian Check after the Owner confirms its Draft. Analogous to Policy "Published" and Portfolio "Active." |

---

## 6. Data Model — Three Approaches Compared

### Approach A: Single mutable check + event table (Rejected)

One `guardian_checks` table with mutable rows, one `guardian_events` table.
Simple but not auditable — you cannot prove what rule produced what event
if the rule was changed after the event.

### Approach B: Immutable event log only (Rejected)

Every evaluation writes a GuardianEvent with the rule definition embedded
inline. The rule is repeated in every event. Simple, auditable, but no
way to name or manage rules — "what rules do I have?" requires scanning
every event.

### Approach C: Stable Check Identity + Draft + Immutable Event (RECOMMENDED)

Reuses the proven Policy/Portfolio/Decision pattern:

- `guardian_checks` — stable identity for each rule (Owner-named)
- `guardian_check_drafts` — mutable working state for rule editing
- `guardian_check_confirmed` — immutable confirmed rule version (after publish)
- `guardian_evaluation_runs` — immutable record of each evaluation pass (when, status, counts)
- `guardian_events` — immutable record of each threshold breach (one event per
  exceeded check per evaluation pass)

A Guardian Check has a lifecycle: Draft → Confirmed. Confirmed Checks are
immutable (like Policy Versions and Portfolio Snapshots). When the Owner
wants to change a threshold, they edit the Draft and re-Confirm — creating
a new immutable version. Guardian Events reference the specific Confirmed
Check version + the Policy Version + the Portfolio Snapshot that were
evaluated. This provides full provenance: "Event E was produced by Check C
version V, evaluating Policy P version Vp against Portfolio Snapshot S."

### Tables

```
guardian_checks
  id UUID PK
  household_id UUID FK → household_profiles
  name VARCHAR(200) NOT NULL UNIQUE
  check_type VARCHAR(50) CHECK(drift|category_exposure|staleness)
  status VARCHAR(20) CHECK(draft|confirmed)
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ

guardian_check_drafts
  check_id UUID PK+FK → guardian_checks (ON DELETE CASCADE)
  threshold_value NUMERIC(5,2) NOT NULL CHECK(> 0 AND <= 100)
  target_category VARCHAR(200) — for drift, which Policy category to compare
  target_holding_category VARCHAR(200) — for drift/category_exposure, which Portfolio category to compare
  staleness_days INTEGER — for staleness checks, max age in days
  severity VARCHAR(20) CHECK(info|warning|critical) DEFAULT 'info'
  notes TEXT
  expected_revision INTEGER DEFAULT 1
  updated_at TIMESTAMPTZ

guardian_check_confirmed
  id UUID PK
  check_id UUID FK → guardian_checks (RESTRICT)
  version_number INTEGER NOT NULL
  check_type VARCHAR(50)
  threshold_value NUMERIC(5,2)
  target_category VARCHAR(200)
  target_holding_category VARCHAR(200)
  staleness_days INTEGER
  severity VARCHAR(20)
  notes TEXT
  confirmed_at TIMESTAMPTZ
  — UNIQUE(check_id, version_number)
  — BEFORE INSERT/UPDATE/DELETE trigger prohibits all modification

guardian_evaluation_runs
  id UUID PK
  household_id UUID FK → household_profiles
  status VARCHAR(50) CHECK(completed|skipped_no_published_policy|skipped_no_portfolio_snapshot)
  checks_evaluated INTEGER CHECK(>= 0)
  events_created INTEGER CHECK(>= 0)
  skip_reason TEXT — human-readable when status starts with 'skipped_'
  as_of_date DATE NOT NULL — explicit evaluation date injected by engine
  started_at TIMESTAMPTZ
  completed_at TIMESTAMPTZ
  — BEFORE INSERT/UPDATE/DELETE trigger prohibits all modification

guardian_events
  id UUID PK
  evaluation_run_id UUID FK → guardian_evaluation_runs (RESTRICT)
  household_id UUID FK → household_profiles
  check_id UUID FK → guardian_checks (RESTRICT)
  check_version_id UUID FK → guardian_check_confirmed (RESTRICT)
  policy_version_id UUID FK → policy_versions (RESTRICT)
  portfolio_snapshot_id UUID FK → portfolio_snapshots (RESTRICT)
  detected_at TIMESTAMPTZ
  drift_pp NUMERIC(5,2) — for drift checks, the computed percentage-point difference
  exposure_pct NUMERIC(5,2) — for category_exposure checks
  staleness_days_actual INTEGER — for staleness checks, the actual age in calendar days
  exceeded BOOLEAN NOT NULL DEFAULT TRUE — always TRUE for events (only exceeded thresholds are recorded)
  — BEFORE INSERT/UPDATE/DELETE trigger prohibits all modification
  — UNIQUE fingerprint on (check_version_id, policy_version_id, portfolio_snapshot_id, as_of_date)
    for staleness; (check_version_id, policy_version_id, portfolio_snapshot_id) for drift/exposure
```

---

## 7. Lifecycle

### Guardian Check Lifecycle

```
  [No Check] → Create Draft → [Draft exists, status=draft]
                                   ↓
                           Edit Draft (revision++)
                                   ↓
                           Confirm → [Confirmed, version=N]
                                   ↓
                           Edit → new Draft → Confirm → [version=N+1]
```

Matches the Policy Version pattern: Confirm consumes Draft, creates immutable
Confirmed version, increments version_number. Previous Confirmed versions are
preserved for audit.

### Evaluation Lifecycle

Evaluation is explicitly manual (OD-S4-001: Option B). It is NEVER
triggered automatically by Portfolio Confirm or any other mutation.

```
  Owner triggers "Evaluate" (all or single Check)
    → Insert guardian_evaluation_runs (status=started, as_of_date=NOW())
    → If no Published Policy Version: set status=skipped_no_published_policy, commit, return
    → If no Portfolio Snapshot: set status=skipped_no_portfolio_snapshot, commit, return
    → For each Confirmed Check:
        → Load current Policy Published Version
        → Load latest Portfolio Snapshot
        → Compute rule-specific metric
        → Compare against threshold
        → If exceeded: INSERT GuardianEvent (exceeded=TRUE)
        → If within bounds: no event recorded
    → Update evaluation_run (status=completed, checks_evaluated=N, events_created=M)
    → Write AuditEvent
    → Commit
```

The evaluation run + events share one transaction. The Household FOR UPDATE
lock serializes evaluation. Evaluation does NOT modify Policy, Portfolio, or
Check data — it only reads immutable snapshots and writes new evaluation
records and events.

### Auto-Evaluate Prohibition

Per OD-S4-001 Option B: Guardian evaluation is NOT triggered by Portfolio
Confirm or any other mutation. This prevents Guardian failures from blocking
Portfolio operations and avoids coupling the two domains. Automatic and
scheduled evaluation is deferred to the Orchestration sprint (Sprint 006).

---

## 8. Evaluation Rules

### Category Matching (Mandatory Clarification #2)

Policy allocation categories are matched to Portfolio holding categories
by trim + NFKC + casefold of the Policy's `asset_class_name` (already
NFKC-normalized at Policy creation) against the Portfolio's `asset_category`.
This is an exact string match — no fuzzy matching, no AI mapping, no silent
guessing. Unmatched categories are recorded in the EvaluationRun summary but
produce no Events.

### Drift Check (OD-S4-008: absolute percentage points)

For each Policy allocation category named in `target_category`, find the
corresponding Portfolio holding category named in `target_holding_category`.
Both are matched via trim + NFKC + casefold (see above).

```
target_pct = allocation.target_percentage (Decimal, e.g., 20.00)
actual_pct = (sum of total_value for holdings in category) / (sum of total_value for ALL holdings) × 100
absolute_drift_pp = abs(actual_pct - target_pct)
exceeded = absolute_drift_pp > threshold_value
```

If total portfolio value is zero: skip drift checks (record zero_total_value in
EvaluationRun). No division by zero, no synthetic events.

If the Policy category has no matching Portfolio holdings: actual_pct = 0,
absolute_drift_pp = target_pct. If target is 20% and actual is 0%, drift = 20
percentage points. Event created if 20 > threshold.

Equal-to-threshold (drift == threshold) is NOT exceeded. The boundary `>`
is strict. Both threshold and drift use NUMERIC(5,2) with ROUND_HALF_EVEN.

### Category Exposure Check (formerly "Concentration", OD-S4-004: Option B)

```
actual_pct = (sum of total_value for holdings in target_holding_category)
           / (sum of total_value for ALL holdings) × 100
exceeded = actual_pct > threshold_value
```

If total portfolio value is zero: skip.

### Staleness Check (OD-S4-005: Mandatory Clarification #4)

```
age_calendar_days = as_of_date - latest_snapshot.valuation_date
exceeded = age_calendar_days > staleness_days
```

The `as_of_date` is injected by the evaluation engine at the start of each
evaluation run. It is NEVER read from the system clock at check evaluation
time — this ensures deterministic replay. Calendar days: two DATE values
subtracted; no hour/minute/second granularity. Boundary: `>` (strict);
exactly N days old is NOT exceeded.

If no confirmed Portfolio Snapshot exists: skip, record
status=skipped_no_portfolio_snapshot in EvaluationRun. No events created.

### Per-Check-Type Field Validation (Mandatory Clarification)

The following fields are required based on `check_type`:

| check_type | Required fields | Optional fields |
|-----------|----------------|-----------------|
| drift | threshold_value (NUMERIC(5,2)), target_category, target_holding_category | severity, notes |
| category_exposure | threshold_value (NUMERIC(5,2)), target_holding_category | severity, notes |
| staleness | staleness_days (INTEGER > 0) | severity, notes |

A Draft that omits required fields for its type is rejected at the API
boundary (422). Fields not relevant to the type are stored as NULL.
Category names are validated to be non-empty, ≤200 Unicode code points,
and must satisfy the trim + NFKC + casefold normalization used for matching.

---

## 9. Currency and Precision

All drift, category exposure, and staleness values use NUMERIC(5,2) (matching Policy
allocation precision). Total portfolio value uses NUMERIC(20,2). All
computation uses Python Decimal with ROUND_HALF_EVEN. API boundary uses
decimal strings.

---

## 10. Concurrency and Lock Order

Evaluation runs in a single transaction per evaluation pass:

1. Lock Household FOR UPDATE (serializes evaluation)
2. Insert guardian_evaluation_runs (status=started, as_of_date=DATE(NOW()))
3. If no Published Policy Version: set status=skipped_no_published_policy, commit, return
4. If no Portfolio Snapshot: set status=skipped_no_portfolio_snapshot, commit, return
5. Read current Published Policy Version (no lock — immutable)
6. Read latest Portfolio Snapshot (no lock — immutable)
7. For each Confirmed Check:
   a. Match categories (trim + NFKC + casefold)
   b. Compute metric with ROUND_HALF_EVEN
   c. If exceeded: INSERT GuardianEvent (with evaluation_run_id)
   d. If within bounds: skip (no event)
8. Update evaluation_run (status=completed, checks_evaluated, events_created)
9. Insert AuditEvent
10. Commit

Lock order: Household FOR UPDATE → reads only (Policy, Portfolio, Checks are
immutable; no write locks needed). Evaluation NEVER acquires locks on Policy,
Portfolio, or Check rows. It does NOT call external services — pure local
computation.

Concurrent evaluation: Household FOR UPDATE serializes. A second request
blocks. If wait exceeds 30s, return 409 "Evaluation already in progress."

---

## 11. API Design

All endpoints under `/api/guardian`. Decimal strings for all numeric values.

| Method | Path | Purpose |
|--------|------|---------|
| POST | /api/guardian/checks | Create a new Guardian Check (status=draft) |
| GET | /api/guardian/checks | List all Checks with current status |
| GET | /api/guardian/checks/{id} | Get Check detail with current Draft and latest Confirmed |
| PATCH | /api/guardian/checks/{id}/draft | Update Draft metadata (threshold, category, severity) |
| POST | /api/guardian/checks/{id}/draft/confirm | Confirm Draft → immutable Confirmed version |
| POST | /api/guardian/checks/{id}/draft/discard | Discard Draft (identity deletion if never confirmed) |
| POST | /api/guardian/evaluate | Run evaluation of all Confirmed Checks. Returns evaluation_run + events. |
| POST | /api/guardian/checks/{id}/evaluate | Run evaluation of a single Confirmed Check. Reuses same evaluation service. |
| GET | /api/guardian/evaluations | Cursor-paginated evaluation run history |
| GET | /api/guardian/evaluations/{id} | Single evaluation run with summary and events |
| GET | /api/guardian/events | Cursor-paginated event history (before_sequence_number, limit, filter by check_id) |
| GET | /api/guardian/events/{id} | Single event detail |
| GET | /api/guardian/audit | Cursor-paginated Guardian audit |

---

## 12. UI States

Based on the Policy/Portfolio/Decision frontend patterns:

1. Loading
2. No Household → link to /household
3. No Guardian Checks → "Configure your first monitoring rule"
4. Check List — all checks with status, type, severity, last evaluation
5. Check Editor — Draft with threshold, category, severity, notes
6. Confirm Review — read-only review of Draft before Confirm
7. Confirmed View — read-only Confirmed check version
8. Event List — cursor-paginated, newest first, filterable by check
9. Event Detail — rule evaluated, versions referenced, result
10. Evaluate Button — manual trigger with loading state
11. Evaluation In Progress — progress indicator
12. Evaluation Complete — summary (N within bounds, M exceeded)
13. Audit Timeline — Guardian-filtered audit events
14. 409 Conflict — ConflictPanel with reload
15. 404 / Network Error — neutral error with retry
16. Dirty State — unsaved changes block Confirm
17. Local-Only Notice
18. Non-Advisory Notice — "Guardian detects mechanical threshold crossings. It does not advise."

---

## 13. Local-Only Security Boundary

Guardian evaluation is purely local. No data leaves the machine:
- Policy allocations are local.
- Portfolio holdings are local.
- Thresholds are Owner-defined.
- Evaluation happens in-process.
- Events are stored in local PostgreSQL.

No external API calls, no market data, no LLM, no notification delivery.

---

## 14. Neutral / Non-Advisory Language

All Guardian UI text uses neutral, mechanical language:
- "Threshold exceeded" — not "Alert" or "Warning"
- "Drift detected" — not "Rebalance needed"
- "Concentration above threshold" — not "Overweight" or "Reduce"
- "Snapshot is X days old" — not "Stale" or "Outdated"

The system never uses language that implies a recommended action.

---

## 15. Test Matrix

| Category | Slice | Tests |
|----------|-------|-------|
| Schema/API | B | Pydantic validation, decimal strings, severity enum, check_type enum |
| PostgreSQL | A | Real database: constraints, triggers, immutability, foreign keys |
| Migration | A | upgrade head, downgrade, re-upgrade, offline SQL |
| Drift computation | B | Absolute pp difference, equal-to-threshold NOT exceeded, zero total value |
| Category exposure | B | Single category, multiple holdings, zero total value |
| Staleness | B | as_of_date injection, calendar days, strict >, future date rejection |
| Evaluation runs | B | Completed, skipped_no_published_policy, skipped_no_portfolio_snapshot |
| Concurrency | B | Evaluate vs Confirm race, double evaluate (409) |
| Immutability | A | Confirmed check immutable, event immutable |
| Audit | B | Check create/confirm/discard, evaluation run |
| Frontend states | C | All 18 UI states (Vitest) |
| Accessibility | C | aria-labels, keyboard navigation |
| Decimal precision | B | ROUND_HALF_EVEN, percentage boundaries |
| Local-only | B | CORS origin, no external calls |

---

## 16. Migration

New Alembic revision `0007_guardian_foundation` (or next available).
Creates five tables (guardian_checks, guardian_check_drafts,
guardian_check_confirmed, guardian_evaluation_runs, guardian_events)
with named constraints, indices, immutability triggers, and the
deterministic input fingerprint UNIQUE constraints on events.
Additive only — no modification to existing 0001-0006.

---

## 17. Observability

Each evaluation run writes one AuditEvent for the evaluation run itself
(action: guardian.evaluation.completed or guardian.evaluation.skipped),
with metadata: evaluation_run_id, status, checks_evaluated, events_created,
skip_reason (if applicable). Guardian Check lifecycle events (created,
draft updated, confirmed, discarded) each write one AuditEvent following
the Policy/Decision pattern.

Audit metadata contains: evaluation_run_id, check_version_number,
policy_version_number, portfolio_snapshot_version, exceeded.
No financial values (quantities, prices, total_values) in audit metadata.


---

## 18. Slice Decomposition

### Sprint 004 Slice A: Guardian Persistence Foundation (R2)
- Alembic revision 0007: guardian_checks, guardian_check_drafts,
  guardian_check_confirmed, guardian_events
- Named CHECK, UNIQUE, FK constraints
- Immutability triggers on confirmed and events
- SQLAlchemy ORM models
- Real PostgreSQL tests only (drift computation tested with raw SQL)
- No service, repository, API, router, or frontend

### Sprint 004 Slice B: Guardian Backend Workflow and API (R2)
- Pydantic schemas with decimal-string contracts
- Repository queries with FOR UPDATE
- Service transaction boundaries (lock order: Household → Check)
- All /api/guardian endpoints
- Evaluation engine (drift, category_exposure, staleness computation)
- Concurrency tests
- Guardian-filtered AuditEvent reads
- No frontend

### Sprint 004 Slice C: Guardian Frontend (R1)
- /guardian page with all 18 UI states
- Typed Guardian API client
- Check editor, Confirm, Event list, Evaluate button
- Non-advisory copy, local-only notice
- Vitest tests

---

## 19. Backlog Interaction

Guardian implements the backlog item "Add Guardian monitoring workflows."
It does NOT implement: "Introduce data persistence and orchestration"
(needed for scheduled evaluation), "Add AI Investment Committee workflows"
(needs Guardian + Orchestration first), or "Add notification escalation
capabilities" (needs Guardian Events + outbound infrastructure).

After Guardian, the natural sequence is:
- Sprint 005: Notification Escalation (deliver Guardian Events to channels)
- Sprint 006: Data Orchestration (scheduled evaluation, market data prep)
- Sprint 007: AI Investment Committee (structured evidence + Guardian events)

---

## 20. Implementation Authorization Boundary

This document authorizes the Technical Design Gate ONLY. Implementation of
Sprint 004 is NOT authorized. Each slice (A: DB, B: API, C: Frontend)
requires separate explicit Owner authorization.

---

## Owner Decision Status

All 13 Owner Decisions (OD-S4-001 through OD-S4-013) are **Resolved**
by Project Owner on 2026-07-17. See `docs/sprints/SPRINT_004_OPEN_QUESTIONS.md`
for the full decision table with selected options, rejected alternatives,
and additional constraints.

**This design is approved.** Sprint 004 implementation is NOT authorized.
Each slice (A: DB, B: API, C: Frontend) requires separate authorization.
