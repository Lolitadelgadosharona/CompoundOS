# Sprint 012 Slice B — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 012 Slice A: DONE
> Sprint 012 Slice B: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 5 decisions required before implementation.

---

## OD-12-B-1: Worker Execution Model

### Question
Should the research worker run in-process or as a separate process?

### Options

| Option | Description |
|---|---|
| A: In-process (FastAPI background task) | `BackgroundTasks.add_task()` runs in same process. Simplest. No queue infrastructure. |
| B: Separate process (subprocess/worker pool) | Research runs in separate process via `multiprocessing` or worker pool. Survives API restarts. |
| C: External queue (Redis/RabbitMQ) | Full async queue. Most robust. Highest complexity. |

### Recommendation
**Option A — In-process.** For a single-Owner system with ~1 research run
per day, background tasks are sufficient. Can migrate to Option B or C
when concurrent research needs arise.

### Owner Decision
- [ ] APPROVE — Option A (In-process background task)
- [ ] APPROVE — Option B (Separate process)
- [ ] APPROVE — Option C (External queue)
- [ ] OTHER: _______________

---

## OD-12-B-2: Parallel Perspective Limit

### Question
How many perspectives can run concurrently?

### Options

| Option | Description |
|---|---|
| A: All 6 concurrent | `ThreadPoolExecutor(max_workers=6)`. Fastest. |
| B: 3 concurrent | `max_workers=3`. Balances speed with resource usage. |
| C: Sequential | One at a time. Slowest but simplest. |

### Recommendation
**Option A — All 6 concurrent.** Each perspective call is I/O bound
(waiting for LLM API). ThreadPoolExecutor handles I/O-bound parallelism
efficiently. 6 × 30s sequential = 3 min vs 30s parallel.

### Owner Decision
- [ ] APPROVE — Option A (All 6 concurrent)
- [ ] APPROVE — Option B (3 concurrent)
- [ ] APPROVE — Option C (Sequential)
- [ ] OTHER: _______________

---

## OD-12-B-3: Research Run Timeout

### Question
What is the maximum duration for a research run?

### Options

| Option | Timeout | Rationale |
|---|---|---|
| A: 5 minutes | Tight; may fail with slow LLM | |
| B: 10 minutes | Balanced; allows 6 × 60s + memo | |
| C: 20 minutes | Conservative | |

### Recommendation
**Option B — 10 minutes.** Evidence (30s) + 6 perspectives (60s each
parallel) + memo (30s) = ~2 min typical. 10 min gives 5× margin for
slow API responses without blocking indefinitely.

### Owner Decision
- [ ] APPROVE — Option A (5 minutes)
- [ ] APPROVE — Option B (10 minutes)
- [ ] APPROVE — Option C (20 minutes)
- [ ] OTHER: _______________

---

## OD-12-B-4: Partial Result Policy

### Question
When some perspectives fail, what happens?

### Options

| Option | Description |
|---|---|
| A: Full memo generation | Run synthesis with partial perspectives; flag missing |
| B: No memo, partial results | Preserve successful analyses; skip memo; Owner sees partial |
| C: Discard all | No partial results; all or nothing |

### Recommendation
**Option B — No memo, partial results.** Preserving successful
perspectives lets the Owner see what analysis the AI produced before
failure. Re-running gets a new run_number; the old run is an
immutable partial record.

### Owner Decision
- [ ] APPROVE — Option A (Full memo with partial)
- [ ] APPROVE — Option B (No memo, partial results)
- [ ] APPROVE — Option C (Discard all)
- [ ] OTHER: _______________

---

## OD-12-B-5: Failed Research Notification

### Question
How should the Owner be notified of research completion or failure?

### Options

| Option | Description |
|---|---|
| A: Poll only | Owner polls GET /api/research/{id}/progress |
| B: Notification event | Worker creates notification_event on completion/failure |
| C: Dashboard integration | Research status visible in /api/dashboard activity feed |

### Recommendation
**Option A — Poll only (for now).** Notification infrastructure exists
(Sprint 007/008) but adds complexity. For V1 with manual research
triggering, polling is sufficient. Can add notification in a future
sprint.

### Owner Decision
- [ ] APPROVE — Option A (Poll only)
- [ ] APPROVE — Option B (Notification event)
- [ ] APPROVE — Option C (Dashboard integration)
- [ ] OTHER: _______________

---

## AI Authority Confirmation

All decisions preserve:

| Principle | Enforcement |
|---|---|
| AI advisory only | AI analyzes, Owner decides |
| No automatic investment | Decision creation requires Owner POST |
| No trading | No trade code paths |
| No policy modification | Policy mutation blocked by triggers |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-B-1 | Worker model | In-process background task (A) |
| OD-12-B-2 | Parallel limit | All 6 concurrent (A) |
| OD-12-B-3 | Run timeout | 10 minutes (B) |
| OD-12-B-4 | Partial results | No memo, preserve partial (B) |
| OD-12-B-5 | Completion notification | Poll only (A) |
