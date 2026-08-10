# Sprint 012 Slice B — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 012 Slice A: DONE
> Sprint 012 Slice B: DESIGN APPROVED — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 5 decisions required before implementation.

---

## Architecture Notes

### 1. Worker Abstraction

The research execution worker MUST NOT be permanently coupled to FastAPI
BackgroundTasks. Design a conceptual abstraction:

```
ResearchJobQueue          ← abstract interface
        │
        ▼
ResearchWorker            ← pluggable implementation
```

| V1 | V2 (future) |
|---|---|
| `LocalWorker` using `asyncio.create_task` or `BackgroundTasks` | `CeleryWorker` or `TemporalWorker` |
| In-process only. Does NOT survive API restart. | Distributed. Survives restarts. Scales horizontally. |

V1 implements `LocalWorker` behind the `WorkerQueue` interface. When
distributed execution is needed, swap the implementation without
changing the execution pipeline logic.

### 2. Perspective Execution Abstraction

Parallel perspective execution MUST NOT be permanently coupled to
`ThreadPoolExecutor`. Design a conceptual interface:

```
PerspectiveExecutor       ← abstract interface
        │
        ▼
┌───────────────────┐
│ LocalParallel      │   V1: ThreadPoolExecutor(max_workers=N)
│ DistributedWorker  │   V2: Celery task per perspective
└───────────────────┘
```

The execution pipeline calls `executor.execute_all(perspectives)` and
the implementation handles parallelism. This allows:
- V1: local thread pool
- V2: distributed workers per perspective
- Future: GPU-accelerated inference if local LLMs are used

### 3. Confidence Scoring Versioning

Confidence calculations MUST carry a model version for future evaluation:

```python
class ConfidenceResult:
    score: int              # 0-100
    level: str              # HIGH/MEDIUM/LOW
    model_version: int      # increments when scoring formula changes
    breakdown: dict[str, int]  # per-dimension scores
```

When the scoring formula is updated (e.g., weights change, new dimensions
added), the `model_version` increments. Old research runs retain their
original version for audit and comparison.

---

## OD-12-B-1: Worker Execution Model

### Question
What worker abstraction and V1 implementation should be used?

### Options

| Option | Abstraction | V1 Implementation | Future |
|---|---|---|---|
| A: Local async worker | `WorkerQueue` interface + `LocalWorker` (asyncio) | In-process, no queue infra | Swap to Celery/Temporal later |
| B: Queue abstraction + local | `WorkerQueue` interface with pluggable backends | In-process backed by simple queue | Same — already abstracted |
| C: Distributed queue (future-only) | External queue from day one (Redis/Celery) | Requires infrastructure setup | No migration needed |

### Recommendation
**Option A — Local async worker behind WorkerQueue interface.**
Simplest V1. The abstraction layer ensures migration to distributed
workers is a swap, not a rewrite.

### Owner Decision
- [ ] APPROVE — Option A (Local async worker)
- [ ] APPROVE — Option B (Queue abstraction + local)
- [ ] APPROVE — Option C (Distributed queue)
- [ ] OTHER: _______________

---

## OD-12-B-2: Perspective Parallelism Limit

### Question
How many perspectives can run concurrently?

### Options

| Option | Concurrency | Implementation |
|---|---|---|
| A: All 6 concurrent | max_workers=6 | Fastest (~30s total LLM time) |
| B: 3 concurrent | max_workers=3 | Balanced |
| C: Sequential | 1 at a time | Slowest (~3 min total) |

### Architecture Impact
The `PerspectiveExecutor` abstraction accepts `max_workers` as
configuration. Changing this is a config value, not a code change.

### Recommendation
**Option A — All 6 concurrent.** Perspectives are I/O bound (LLM API
calls). Thread parallelization handles this efficiently.

### Owner Decision
- [ ] APPROVE — Option A (All 6 concurrent)
- [ ] APPROVE — Option B (3 concurrent)
- [ ] APPROVE — Option C (Sequential)
- [ ] OTHER: _______________

---

## OD-12-B-3: Research Run Timeout

### Question
What is the maximum duration for a research run before timeout?

### Options

| Option | Timeout |
|---|---|
| A: 5 minutes | Tight; may fail with slow LLM responses |
| B: 10 minutes | Balanced; ~5× margin over typical 2 min run |
| C: 20 minutes | Conservative; handles worst-case API latency |

### Recommendation
**Option B — 10 minutes.** Typical run: evidence (30s) + 6 parallel
perspectives (60s) + memo (30s) = ~2 min. 10 min provides 5× margin.

### Owner Decision
- [ ] APPROVE — Option A (5 minutes)
- [ ] APPROVE — Option B (10 minutes)
- [ ] APPROVE — Option C (20 minutes)
- [ ] OTHER: _______________

---

## OD-12-B-4: Partial Result Handling

### Question
When some perspectives fail, what happens?

### Options

| Option | Description |
|---|---|
| A: Full memo with partial | Run synthesis LLM with partial perspectives; flag which are missing in committee section |
| B: No memo, preserve partial | Preserve successful perspectives; skip memo generation; Owner reviews partial analyses |
| C: Discard all | No partial results; all-or-nothing; re-run required |

### Recommendation
**Option B — No memo, preserve partial.** Memo quality degrades with
missing perspectives. Owner can review partial results and decide to
re-run or proceed.

### Owner Decision
- [ ] APPROVE — Option A (Full memo with partial)
- [ ] APPROVE — Option B (No memo, partial results)
- [ ] APPROVE — Option C (Discard all)
- [ ] OTHER: _______________

---

## OD-12-B-5: Failed Perspective Retry Strategy

### Question
How should individual LLM perspective failures be retried?

### Options

| Option | Retry | Backoff | Max | After Max |
|---|---|---|---|---|
| A: Aggressive | 3 retries | Exponential (1s, 4s, 16s) | 3 | Mark perspective failed |
| B: Conservative | 1 retry | Fixed 5s | 1 | Mark perspective failed |
| C: No retry | 0 | — | — | Mark perspective failed immediately |

### Recommendation
**Option A — Aggressive (3 retries with exponential backoff).**
Transient LLM failures (429 rate limit, 5xx server errors) typically
resolve within seconds. Exponential backoff avoids hammering the API.
After 3 failures, mark as failed and proceed per OD-12-B-4.

### Owner Decision
- [ ] APPROVE — Option A (3 retries, exponential backoff)
- [ ] APPROVE — Option B (1 retry, fixed delay)
- [ ] APPROVE — Option C (No retry)
- [ ] OTHER: _______________

---

## AI Authority Confirmation

All decisions preserve:

| Principle | Enforcement |
|---|---|
| AI advisory only | AI analyzes + recommends; Owner decides |
| No automatic investment approval | Decision creation requires Owner POST |
| No trading capability | No trade/order execution code paths |
| No policy modification | Policy mutation blocked by triggers |
| No credentials in code | API keys only in environment variables |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-B-1 | Worker execution model | Local async worker behind WorkerQueue abstraction (A) |
| OD-12-B-2 | Perspective parallelism | All 6 concurrent via PerspectiveExecutor (A) |
| OD-12-B-3 | Run timeout | 10 minutes (B) |
| OD-12-B-4 | Partial result handling | No memo, preserve partial analyses (B) |
| OD-12-B-5 | Failed perspective retry | 3 retries, exponential backoff (A) |
