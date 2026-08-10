# Sprint 012 Slice D — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 012 Slice A: DONE (59d137e)
> Sprint 012 Slice B: DONE (b5444ac)
> Sprint 012 Slice C: DONE (1d73f84)
> Sprint 012 Slice D: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION
>
> 4 decisions required before implementation.

---

## OD-12-D-1: Permission Gate Enforcement Level

### Question
At what layer should the PermissionGate be enforced?

### Options

| Option | Description |
|---|---|
| A: Service layer only | PermissionGate.check() called at the start of every AI service method. Code-review enforced. |
| B: Middleware + service | FastAPI middleware classifies request origin (Owner vs AI); service layer validates action permissions. Defense in depth. |
| C: Database-level | CHECK constraints on action tables enforce AI cannot write to Owner-only tables. Most robust, most complex. |

### Recommendation
**Option B — Middleware + service.** The global auth middleware already
sets `request.state.role`. The service layer validates via
PermissionGate. Two layers: middleware blocks external, service blocks
internal bypass. Database-level for NEVER actions already exists
(triggers).

### Owner Decision
- [ ] APPROVE — Option A (Service layer only)
- [ ] APPROVE — Option B (Middleware + service — recommended)
- [ ] APPROVE — Option C (Database-level)
- [ ] OTHER: _______________

---

## OD-12-D-2: Prompt Version Enforcement Strictness

### Question
How strict should prompt version enforcement be?

### Options

| Option | Description |
|---|---|
| A: Soft enforcement | Log warning if no active prompt; proceed with default. |
| B: Hard enforcement | Refuse LLM call if no active prompt for perspective. Run status = failed. |
| C: Fallback to latest deprecated | If no active, use most recently deprecated prompt with warning. |

### Recommendation
**Option B — Hard enforcement.** Running AI analysis with unapproved
prompts undermines governance. If a prompt is deprecated and no active
replacement exists, the system should fail loudly, not silently degrade.

### Owner Decision
- [ ] APPROVE — Option A (Soft enforcement)
- [ ] APPROVE — Option B (Hard enforcement — recommended)
- [ ] APPROVE — Option C (Fallback to deprecated)
- [ ] OTHER: _______________

---

## OD-12-D-3: Cost Governance Implementation

### Question
How should LLM cost governance be implemented?

### Options

| Option | Description |
|---|---|
| A: Log only | Record cost in llm_execution_log. No alerts. Owner reviews manually. |
| B: Per-run budget alert | If a single run exceeds configured threshold (e.g. $0.50), create notification_event. |
| C: Tiered budgets | Per-run + daily + monthly budgets with escalating alerts. |

### Recommendation
**Option A — Log only for Slice D.** Cost data is already captured in
`llm_execution_log.cost_estimate`. Alerts add complexity without
immediate value for a single-Owner system making ~1 research run
per day. Budget alerts can be added in a future sprint.

### Owner Decision
- [ ] APPROVE — Option A (Log only — recommended)
- [ ] APPROVE — Option B (Per-run budget alert)
- [ ] APPROVE — Option C (Tiered budgets)
- [ ] OTHER: _______________

---

## OD-12-D-4: Audit Log Integration for AI Events

### Question
Should AI governance events be written to the existing audit_log table?

### Options

| Option | Description |
|---|---|
| A: llm_execution_log only | AI events remain in llm_execution_log. No additional audit_log entries. |
| B: Dual-write key events | Write AI-specific events (run_started, run_completed, permission_denied) to both llm_execution_log and audit_log. |
| C: Full dual-write | Every AI execution event written to both tables. |

### Recommendation
**Option A — llm_execution_log only for Slice D.** The `llm_execution_log`
already provides detailed audit trail. `audit_log` integration adds
redundancy without new insight. The two tables serve different purposes:
`llm_execution_log` for AI-specific metrics, `audit_log` for security
events. Don't conflate them.

### Owner Decision
- [ ] APPROVE — Option A (llm_execution_log only — recommended)
- [ ] APPROVE — Option B (Dual-write key events)
- [ ] APPROVE — Option C (Full dual-write)
- [ ] OTHER: _______________

---

## AI Authority Confirmation

All decisions preserve the non-negotiable principles from OD-12-5:

| # | Action | Classification |
|---|---|---|
| 1-8 | Research execution | AUTO |
| 9-12 | Investment decisions | OWNER ONLY |
| 13-15 | Trading/broker/policy modification | NEVER |

---

## Decision Summary

| ID | Topic | Recommendation |
|---|---|---|
| OD-12-D-1 | Permission gate enforcement level | Middleware + service (defense in depth) (B) |
| OD-12-D-2 | Prompt version enforcement | Hard enforcement — fail if no active prompt (B) |
| OD-12-D-3 | Cost governance | Log only (A) |
| OD-12-D-4 | Audit log integration | llm_execution_log only (A) |
