# Sprint 005 — Open Questions

**All Owner Decisions resolved as of 2026-07-17.**

| ID | Question | Options | Owner Decision | Resolution | Blocks |
|----|----------|---------|---------------|------------|--------|
| OD-S5-001 | Sprint 005 candidate selection | A: Notification Escalation, B: Data Orchestration, C: AI Investment Committee | **B** | Orchestration unlocks Guardian scheduled evaluation. General-purpose infrastructure. All slices Not Authorized for implementation. | Entire sprint |
| OD-S5-002 | Local-only worker or external scheduler? | A: Local worker process, B: External cron, C: Both | **A** | Local worker process preserves local-only principle. No external cron dependency. | Worker architecture |
| OD-S5-003 | Scheduled evaluation: opt-in or opt-out? | A: Per-check opt-in, B: Global opt-in | **A** | Per-check opt-in. Default off. Owner must explicitly enable each schedule. | Schedule UI |
| OD-S5-004 | Schedule frequency? | A: Daily-only, B: Minimum 5min, C: No minimum | **A** | Daily-only. Explicit local execution time + IANA timezone. UTC next_run_at. No cron expressions. No sub-daily scheduling. DST missing/repeated-time handled. | Schedule design |
| OD-S5-005 | Run history retention? | A: Indefinite, B: Keep last N, C: Keep X days | **A** | Indefinite paginated history. Local-only storage has no cost pressure. | Run persistence |
| OD-S5-006 | Worker process lifecycle? | A: App lifespan, B: Standalone process, C: Fire-and-forget | **B** | Standalone process. Runs independently of FastAPI web server. Terminates on graceful shutdown signal. | Process architecture |
| OD-S5-007 | Failed run notification? | A: In-app inbox, B: No notification, C: OS notification | **B** | No notification infrastructure. Owner checks run history. No notification/AI/external services in Sprint 005. | Run history UI |
| OD-S5-008 | Manual + scheduled overlap? | A: Overlap prevention via PostgreSQL, B: Unrestricted independent | **A** | Manual evaluation preserved. Each schedule has at most one queued/running run. GuardianEvent uses existing fingerprint dedup. Overlap prevented by PostgreSQL state check. | Run concurrency |
| OD-S5-009 | Multiple schedules per job? | A: One schedule per job, B: Multiple, C: Independent | **A** | One schedule per job definition. Different frequencies require separate job definitions. | Schedule schema |
| OD-S5-010 | Evaluate scope? | A: Both (all + one), B: All only, C: One only | **A** | Both supported. Guardian is the only Sprint 005 consumer. Code allowlisted job types only. No arbitrary shell/dynamic import/pickle. | Job definition params |
| OD-S5-011 | Shutdown timeout? | A: 30 seconds, B: 60 seconds, C: Configurable | **A** | 30 seconds. Graceful shutdown: finish current attempt, release lease with fencing token, mark in-flight runs aborted. | Shutdown behavior |
| OD-S5-012 | Lease parameters? | A: Fixed: TTL 60s, heartbeat 15s, max execution 5min, B: 2× expected duration | **A** | Lease TTL: 60s. Heartbeat: 15s. Max execution: 5min. DB clock for all timing. Fencing token prevents stale worker from completing reclaimed run. | Lease acquisition |
| OD-S5-013 | UI placement? | A: /automation page, B: /orchestration page, C: Settings panel | **A** | `/automation` — plain language, not infrastructure jargon. | Frontend routing |
| OD-S5-014 | Survive restart? | A: PostgreSQL-persisted, B: In-memory | **A** | All schedules, runs, attempts persisted in PostgreSQL. | Persistence design |
| OD-S5-015 | Worker health reporting? | A: DB-backed heartbeat via FastAPI read-only endpoint, B: Worker HTTP server | **A** | Worker writes heartbeat to DB. FastAPI exposes read-only `GET /api/automation/worker/status`. Worker does NOT start its own HTTP server. | Worker monitoring |

## Additional Approved Semantics

- Retry only transient failures. Max 3 attempts: immediate / 30s / 120s.
- Failed run manual retry creates new run (not attempt).
- Misfire coalesce latest occurrence only — if a daily schedule is missed, only the most recent missed occurrence fires.
- No notification, AI, or external services in Sprint 005.
