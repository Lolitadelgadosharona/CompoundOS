# Sprint 005 — Technical Design Gate

## Executive Summary

Three candidates evaluated. **Orchestration Foundation (B)** is recommended as the next logical infrastructure layer — Guardian is the first real consumer that needs scheduled evaluation, but Orchestration itself is a general-purpose infrastructure service that unlocks all future automated workflows.

## 1. Candidate Analysis

### Candidate A: Notification Escalation Foundation

**Concept**: Guardian Event → local inbox notification → acknowledgment/resolution lifecycle. Owner is notified of exceeded thresholds and must explicitly acknowledge/ resolve each event.

**Immediate user value**: Medium. After a manual evaluation (Sprint 004), the user sees results inline. Notification adds persistent tracking of which events have been acknowledged versus pending — useful when evaluation runs grow in number.

**Dependencies satisfied/missing**: No new external dependencies. Relies only on Guardian Events already created in Sprint 004. The backend/API is self-contained.

**Real feedback loop**: Acknowledgment closes the loop but doesn't prevent future exceedances. Value is primarily organizational, not mechanical.

**Data model complexity**: Low. ~3 new tables: `notifications` (derived from GuardianEvent), `acknowledgments`, `escalation_rules`. Simple CRUD.

**Backend/frontend complexity**: Low. ~8 endpoints: list/poll notifications, acknowledge, view detail, escalation rules CRUD. Frontend: inbox panel, notification detail, acknowledge button.

**Concurrency/idempotency risk**: Low. Single-user local context means no distributed notification delivery race conditions.

**Financial/safety risk**: Low. Notifications don't execute any action. Risk is only that severity labels could be misinterpreted as investment advice — mitigated by neutral language.

**Privacy/security risk**: Low. Local-only inbox. No external delivery unless explicitly configured later.

**Local-only feasibility**: High. Best approached as a pure local inbox in Sprint 005. Email/SMS/push deferred to future sprints.

**Testability**: High. Simple lifecycle tests with no external dependencies.

**Operating cost**: Zero in local-only mode. Future external delivery would add provider costs.

**Estimated slice count**: 1 slice (R2 — backend + frontend combined for this scope).

**Future roadmap unlocks**: Enables future AuditTrail notification, Portfolio drift alerts, scheduled evaluation result notifications. Building block for broader awareness.

**Reasons to defer**: Without scheduled evaluation, the user must manually run `POST /evaluate` then manually check for notifications — the notification layer adds passive tracking but doesn't reduce manual work. The fundamental bottleneck is the manual evaluation trigger.

### Candidate B: Data Orchestration Foundation

**Concept**: General-purpose job/run/attempt/schedule infrastructure. Supports idempotent, lease-based, crash-recoverable job execution. Guardian scheduled evaluation is the first consumer — but the orchestration layer is designed to support any future job (Data import, report generation, Portfolio re-evaluation, Decision Journal reminders).

**Immediate user value**: High. Solves the "manual-only evaluation" bottleneck. Owner can opt into scheduled Guardian evaluation without building a bespoke scheduler inside Guardian. The infrastructure is reusable.

**Dependencies satisfied/missing**: No external services required. Needs injectable clock and lease-based concurrency. Current PostgreSQL (already present) is sufficient for locking.

**Real feedback loop**: Scheduled evaluation → baseline established → subsequent evaluations detect drift. Without scheduling, each evaluation is a one-shot manual action. With scheduling, the system becomes a genuine monitoring foundation.

**Data model complexity**: Medium. ~5 tables: `schedules` (cron-like), `job_definitions`, `runs`, `attempts`, `leases`. Complex but well-understood patterns.

**Backend/frontend complexity**: High. Backend: schedule CRUD, lease acquisition/release, attempt tracking, retry with exponential backoff, graceful shutdown, crash recovery. Frontend: schedule management UI, run history, attempt detail.

**Concurrency/idempotency risk**: Medium. Must handle overlapping runs, stale leases, crashed workers. PostgreSQL advisory locks and idempotency keys mitigate most risks.

**Financial/safety risk**: Low-Medium. Orchestration itself doesn't evaluate — but scheduled Guardian evaluation could trigger more frequently than intended. Must default to opt-in with explicit Owner approval.

**Privacy/security risk**: Low. All processing is local. No credentials for external services.

**Local-only feasibility**: High. Worker runs as local process. No cloud infrastructure needed.

**Testability**: Medium. Lease-based tests require careful concurrent test setup. Threading.Barrier pattern from Sprin t 004 is directly applicable.

**Operating cost**: Zero in local mode. No external provider costs.

**Estimated slice count**: 2 slices. Slice A: Persistence (R2). Slice B: Backend API + Frontend (R2). ~R1 frontend may be viable if UI is simple.

**Future roadmap unlocks**: Scheduled Portfolio re-evaluation, Decision Journal reminders, data import pipelines, report generation, backup automation. This is the single most impactful infrastructure investment remaining.

**Reasons to defer**: Most complex option. Risk of over-engineering for a single consumer. Must be disciplined about keeping the infrastructure general-purpose without speculative features.

### Candidate C: AI Investment Committee Foundation

**Concept**: Multi-agent LLM discussion simulating a committee of investment roles. Each agent provides a risk view, supporting arguments, and dissenting opinions. A synthesis agent produces a final summary. Owner reviews (never auto-executes).

**Immediate user value**: Uncertain. The system has Policy, Portfolio, and Guardian data — but the value of an AI committee discussing this data without executing any action is primarily educational/exploratory.

**Dependencies satisfied/missing**: Requires external LLM API (OpenAI/Anthropic). No local model available for the required quality. External API key, cost, and availability are real operational dependencies.

**Real feedback loop**: AI produces text output. Unless the Owner acts on this output, there is no feedback loop. The system provides analysis without action — similar to reading a newsletter.

**Data model complexity**: Low. ~2 tables: `committee_sessions`, `agent_responses`. The complexity is in the LLM integration, not the data model.

**Backend/frontend complexity**: Medium. Backend: LLM provider abstraction, prompt templating, response parsing, cost tracking. Frontend: session viewer, agent response cards, synthesis display.

**Concurrency/idempotency risk**: Low. Each session is independent. No concurrent mutations.

**Financial/safety risk**: High. LLM outputs could be interpreted as investment advice despite neutral language. Hallucination risk is real. Cost cannot be predicted — each session consumes unknown tokens.

**Privacy/security risk**: High. Portfolio holdings, Policy allocations, and Guardian thresholds would be sent to external LLM providers. Sensitive financial data leaves the local machine. Prompt injection risk via user-authored Policy/Decision text.

**Local-only feasibility**: Low. No high-quality local models exist that can run on consumer hardware for this use case. External provider is a hard dependency.

**Testability**: Medium. LLM outputs are non-deterministic. Mocking is possible but tests would validate structure not content.

**Operating cost**: Variable. Token-based pricing. 4-6 agent responses per session × response length could cost $0.10-$1.00+ per session.

**Estimated slice count**: 2 slices. Slice A: Backend LLM integration (R2). Slice B: Frontend committee UI (R1).

**Future roadmap unlocks**: Enables AI-assisted Policy drafting, Portfolio review, Decision Journal analysis.

**Reasons to defer**: No automated Guardian evaluation yet — the AI would have no new information to discuss between manual evaluations. External LLM dependency violates local-only principles. Hallucination and advice-interpretation risks are not yet mitigated. This is a Milestone 3 feature — it needs Orchestration (B) and mature data sources first.

### Candidate D: Audit & Analytics Foundation

**Concept**: Extracted from backlog. Cross-domain audit querying, aggregated views, basic analytics on Guardian Events, Portfolio snapshots, Policy versions. Provides the Owner with a dashboard of what has happened across all domains.

**Immediate user value**: Medium. Useful for review but doesn't change system behavior.

**Dependencies**: Low. Uses existing data. New read-only endpoints.

**Complexity**: Low. ~3 read-only endpoints, analytics queries, simple frontend dashboard.

**Reasons to defer**: More of a Milestone 3 feature. Needs richer data (scheduled evaluations, more snapshots) to be truly valuable. Doesn't unlock any new workflows.

## 2. Recommendation

**Candidate B: Data Orchestration Foundation** is recommended as Sprint 005.

### Evidence-based rationale

1. **Removes the #1 bottleneck**: Guardian's manual-only evaluation is the most frequently noted limitation. Orchestration directly addresses this.

2. **Maximizes existing investment**: Sprint 004 built the Guardian foundation. Orchestration makes it operational at scale.

3. **General-purpose infrastructure**: Unlike Notification (which is domain-specific) or AI Committee (which is niche), Orchestration benefits every future sprint.

4. **Clear opt-in boundary**: Scheduled evaluation is explicitly opt-in per check — satisfies the Owner Decision requirement that automatic behavior requires approval.

5. **No external dependencies**: PostgreSQL-based locking and local worker process preserve the local-only principle.

6. **Proven patterns**: Lease-based job execution is a well-understood pattern with clear failure modes and recovery paths. The implementation can be tested deterministically with injectable clock and threading.Barrier.

### Why not Notification first

Notification without scheduling is a tracking layer without automation. The user must still manually evaluate, then manually check notifications. The incremental value is organizational rather than operational. Notification should follow Orchestration so that notifications are triggered by scheduled evaluations — closing the loop end-to-end.

### Why not AI Committee

The AI Committee requires external LLM providers, violates local-only principles, introduces cost unpredictability, and has hallucination/safety risks. It also has no automated data source — the AI would analyze static data. This is a Milestone 3 feature.

## 3. Goals and Non-Goals

### Goals

- General-purpose job scheduling infrastructure
- Guardian scheduled evaluation as first consumer
- Opt-in per-check scheduling with explicit Owner approval
- Idempotent, lease-based execution
- Crash recovery and graceful shutdown
- Run/attempt history with audit trail
- Injectable clock for deterministic testing

### Non-Goals

- External notification delivery (future Sprint)
- Guardian automatic severity upgrades
- Automatic trading or rebalancing
- Distributed worker pools
- Priority queues or fair scheduling
- External data ingestion pipelines
- AI or LLM integration
- Scheduled anything other than Guardian evaluation in Sprint 005

## 4. Domain Terminology

| Term | Definition |
|------|------------|
| Schedule | A recurring time specification (cron-like) attached to a job definition |
| Job Definition | What to run, with what parameters (e.g., "evaluate Guardian Check X") |
| Run | One execution instance of a Job Definition, triggered by a Schedule or manual invocation |
| Attempt | One attempt within a Run — retries create new Attempts |
| Lease | A time-bound ownership claim on a Run, preventing duplicate execution |
| Idempotency Key | Deterministic key per Run that ensures at-most-once execution |
| Worker | The local process that polls for pending Runs and executes them |
| Backoff | Exponential delay between retry attempts |
| Graceful Shutdown | On SIGTERM: finish current attempt, release leases, mark in-flight runs as aborted |

## 5. Data Model Approaches

### Approach 1: Single-table Runs

Simplicity-maximizing. One `runs` table with status, attempt count, result. No separate schedules or job definitions — schedule is stored as metadata on the run row.

- Pros: Simple, fast to implement, fewer FK relationships
- Cons: Schedule management is ad-hoc, no reuse across jobs, hard to query "what runs are scheduled"

### Approach 2: Three-tier (Schedule → Job Definition → Run → Attempt)

Industry-standard. Schedules 1:N Job Definitions. Job Definitions 1:N Runs. Runs 1:N Attempts.

- Pros: Clean separation of concerns, reusable job definitions, clear audit trail per attempt, supports different schedules for the same job type
- Cons: More tables, more FK complexity, more ORM mapping

### Approach 3: Queue-based (no Schedules)

Runs are enqueued by an external trigger (API call, cron daemon). The worker polls a queue. No schedule persistence — scheduling is external.

- Pros: Decouples scheduling from the application, simpler app-level data model
- Cons: Requires an external scheduler (system cron, Kubernetes CronJob), harder to introspect "what's scheduled" from within the app

### Recommended: Approach 2 (Three-tier)

Justification: Approach 1 doesn't scale to multiple job types. Approach 3 externalizes scheduling knowledge, making it harder to display and manage schedules from the UI. Approach 2 is the right balance of structure and flexibility for a local-first system.

## 6. Recommended Schema

```sql
-- What should run
CREATE TABLE job_definitions (
    id UUID PRIMARY KEY,
    household_id UUID NOT NULL REFERENCES household_profiles(id),
    job_type TEXT NOT NULL,  -- 'guardian_evaluate_all', 'guardian_evaluate_one'
    job_params JSONB NOT NULL DEFAULT '{}',  -- {check_id: "..."}
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- When it should run
CREATE TABLE schedules (
    id UUID PRIMARY KEY,
    job_definition_id UUID NOT NULL REFERENCES job_definitions(id),
    execution_time TIME NOT NULL,  -- Local wall-clock time, e.g. '09:00'
    timezone TEXT NOT NULL,  -- IANA timezone, e.g. 'America/New_York'
    next_run_at TIMESTAMPTZ NOT NULL,  -- UTC, computed from execution_time + timezone
    enabled BOOLEAN NOT NULL DEFAULT FALSE,  -- MUST be explicitly enabled
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One execution
CREATE TABLE runs (
    id UUID PRIMARY KEY,
    job_definition_id UUID NOT NULL REFERENCES job_definitions(id),
    schedule_id UUID REFERENCES schedules(id),  -- NULL for manual runs
    idempotency_key TEXT NOT NULL,  -- deterministic: hash(job_type, job_params, scheduled_time_bucket)
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, aborted
    triggered_by TEXT NOT NULL,  -- 'schedule', 'manual'
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE(idempotency_key)
);

-- One attempt within a run
CREATE TABLE attempts (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES runs(id),
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, succeeded, failed, aborted
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE(run_id, attempt_number)
);

-- Worker lease with fencing token for concurrency control

CREATE TABLE leases (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL UNIQUE REFERENCES runs(id),
    worker_id TEXT NOT NULL,
    fencing_token UUID NOT NULL,  -- prevents stale worker from completing reclaimed run\n    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n    expires_at TIMESTAMPTZ NOT NULL,  -- TTL: 60s\n    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- refreshed every 15s\n    released_at TIMESTAMPTZ
);
```

**Immutable triggers**: `runs` and `attempts` are append-only after status reaches terminal state (completed, failed, aborted). `schedules` can be updated. `job_definitions` can be soft-disabled.

## 7. Lifecycle / State Machines

### Run Lifecycle

```
pending → running → completed
                  → failed → pending (retry) or failed (terminal)
running → aborted (graceful shutdown)
```

### Attempt Lifecycle

```
pending → running → succeeded
                  → failed
                  → aborted
```

### Schedule Lifecycle

```
disabled → enabled → disabled (toggle, never deleted)
```

### Guardian Evaluation Integration

When a Run with `job_type = 'guardian_evaluate_all'` executes:
1. Worker acquires lease on run
2. Worker calls `POST /api/guardian/evaluate` (same as manual)
3. Evaluation creates EvaluationRun + Events + Audit (existing Sprint 004 behavior)
4. Worker records Attempt as succeeded
5. Worker releases lease, marks Run as completed

## 8. Idempotency / Deduplication

**Idempotency key formula**: SHA256(job_type || canonical_job_params || scheduled_date).

Daily-only scheduling means the time bucket is the calendar date (not a minute window). Mis fire coalescence: if a daily schedule is missed (worker was down), only the most recent missed occurrence fires — not all missed days.

**Overlap prevention**: Each schedule has at most one queued/running run. Before creating a new scheduled run, check: `SELECT 1 FROM runs WHERE schedule_id = :sid AND status IN ('pending', 'running')`. If any exist, skip. Manual evaluation is preserved as an independent operation. GuardianEvent uses existing fingerprint dedup (Sprint 004).

## 9. Transaction Boundaries and Lock Order

```
1. SELECT ... FOR UPDATE on runs row (acquire lease)
2. INSERT or no-op on idempotency check
3. INSERT attempt (attempt_number = 1)
4. Execute job (call Guardian evaluate API)
5. UPDATE attempt status → succeeded
6. UPDATE run status → completed
7. RELEASE lease
8. COMMIT
```

Lock order: `runs` → `attempts` → `leases` (consistent across all operations).

## 10. Failure / Retry / Recovery

### Retry Policy
- Retry only transient failures (connection errors, timeouts)
- Terminal failures (validation errors, not found) → mark failed, no retry
- Max 3 attempts per run: immediate / 30s / 120s
- Failed run manual retry creates NEW run (not new attempt on old run)
- Attempt number tracked in `attempts`

### Lease
- Lease TTL: 60s
- Heartbeat: every 15s the worker refreshes `heartbeat_at`
- Max execution: 5 minutes (hard timeout)
- DB clock for all timing — no client-side clock dependency
- Fencing token: each lease acquisition generates a new UUID token. Worker must present the token to complete or heartbeat. If lease expires and another worker acquires it (new token), the stale worker's completion is rejected (token mismatch).

### Crash Recovery
On startup, worker releases any leases from previous instance whose `heartbeat_at` is older than TTL margin. Runs in `running` status with expired leases are marked `aborted` and re-queued as new runs.

## 11. API Contracts

### Schedule Management

```
POST   /api/automation/schedules          Create schedule + job definition
GET    /api/automation/schedules          List schedules
GET    /api/automation/schedules/{id}     Get schedule detail
PATCH  /api/automation/schedules/{id}     Update/disable schedule
DELETE /api/automation/schedules/{id}     Delete schedule (cascades to job definition)

GET    /api/automation/runs               List runs (paginated, filterable by job_type)
GET    /api/automation/runs/{id}          Run detail with attempts
POST   /api/automation/runs               Manually trigger a run

### Worker-internal (not exposed as API)

Worker writes heartbeat to `leases.heartbeat_at` every 15s.
FastAPI exposes read-only: `GET /api/automation/worker/status`.
Worker does NOT start its own HTTP server.

## 12. UI Routes and States

### Page: /automation

**18 UI States** (matching Sprint 004 pattern):

1. Loading
2. No household
3. No schedules
4. Schedule list
5. Create schedule
6. Edit schedule
7. Schedule detail
8. Run list (paginated)
9. Run detail with attempts
10. Attempt detail
11. Manual trigger button
12. Trigger in progress
13. Trigger completed
14. Trigger failed
15. Disable confirmation
16. Delete confirmation
17. Local-Only notice
18. Non-Advisory notice

## 13. Security / Local-Only Boundary

- All schedules are local PostgreSQL rows
- Worker runs as local process (no external scheduler)
- No credentials stored for external services
- Worker-internal endpoints authenticated via shared secret (local file)
- No data leaves the machine

## 14. Audit / Redaction

Audit events for:
- Schedule created/modified/deleted
- Run triggered (manual or schedule)
- Run completed/failed/aborted
- Attempt succeeded/failed

Metadata includes: `job_type`, `schedule_id`, `run_id`, `attempt_number`, `triggered_by`. No financial data. No check threshold values. No evaluation results (those are in Guardian audit).

## 15. Neutral Language

- "Scheduled evaluation completed" (not "Alert processed")
- "Run failed — will retry" (not "Critical failure")
- "Schedule enabled" (not "Monitoring activated")
- No advisory language in any UI text

## 16. Test Matrix

| Category | Tests |
|----------|-------|
| Schema | upgrade/downgrade, constraints, partial indexes |
| Lease | acquire, release, expiry, concurrent acquisition |
| Idempotency | duplicate run prevention, same-bucket dedup |
| Retry | exponential backoff timing, max attempts, terminal vs transient |
| Crash recovery | stale lease cleanup, run re-queue |
| Graceful shutdown | in-flight completion, run abort, lease release |
| Guardian integration | scheduled evaluation creates GuardianEvents |
| API | schedule CRUD, run list/detail, manual trigger |
| Frontend | 18 UI states |
| Concurrency | two workers can't acquire same lease |
| Clock | injectable clock for deterministic timing tests |

## 17. Migration Strategy

- 0008_orchestration_foundation.py: job_definitions, schedules, runs, attempts, leases tables
- Named constraints and immutable triggers on runs/attempts
- No data migration needed (new tables only)

## 18. Slice Decomposition

- **Slice A: Orchestration Persistence (R2)** — Migration 0008, ORM models, PostgreSQL tests, lease/idempotency constraints
- **Slice B: Orchestration API + Guardian Integration (R2)** — Worker process, schedule/run API, Guardian scheduled evaluation consumer, audit
- **Slice C: Orchestration Frontend (R1)** — /automation page, schedule management, run history, 18 UI states

## 19. Rollout / Rollback

- Migration 0008 is additive (new tables only) — safe to apply and rollback
- Worker process is opt-in — failing to start the worker has no impact on existing Guardian manual evaluation
- Schedules default to `enabled = FALSE` — no scheduled runs execute without explicit Owner opt-in

## 20. Backlog Interaction

- Enables future: Notification Escalation (Sprint 006 candidate), Data Import, Portfolio re-evaluation
- Does not change: AI Committee prerequisites (still needs external LLM)

## 21. Implementation Authorization Boundary

Sprint 005 authorization is for **Technical Design Gate only**. No implementation is authorized. All slices (A/B/C) remain Not Authorized / Not Started. The Owner must approve the Technical Design and resolve Open Questions before any slice is authorized.

## 22. Risks and Unresolved Questions

1. Single-worker assumption: What happens when the user runs two instances? Lease-based locking handles this, but the user experience may be confusing (one worker claims the lease, the other idles).
2. Clock skew: The worker's clock may differ from the database clock. Mitigated by using `NOW()` for lease expiry (server time) and injectable clock for scheduling.
3. DST transitions: When clocks fall back (e.g., 01:30 repeated), the schedule fires once at the first occurrence only. When clocks spring forward (e.g., 02:30 skipped), the schedule fires at the next valid time after the gap. These are standard IANA timezone behaviors.
4. Guardian evaluation performance: A scheduled run could trigger evaluation of all checks. This is the same as manual evaluate-all — no new performance risk.
