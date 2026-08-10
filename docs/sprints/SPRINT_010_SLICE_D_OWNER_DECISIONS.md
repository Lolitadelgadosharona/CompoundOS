# Sprint 010 Slice D — Owner Decisions

> **STATUS: PENDING OWNER DECISIONS**
>
> Sprint 010 Slice D Design: COMPLETE
> 5 decisions require Owner review before implementation begins.

---

## OD-10-D-1: Development Mode Bypass

### Question
When `COMPOUNDOS_DEV_MODE=1`, should the auth middleware skip validation?

### Context
Currently all endpoints are open. Adding auth middleware will break local
development unless there's a bypass. The question is what level of bypass
is appropriate.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Full bypass | Auth middleware completely skipped | Seamless dev experience; no setup | Production misconfiguration risk |
| B: Confirm-only | Bypass validates but always succeeds; logs "dev-bypass" to audit | Security code path exercised; production-like | Extra log noise |
| C: No bypass | Auth always enforced; developer must set API key in env | Security path always active; no gap | Dev friction; every new clone needs key setup |

### Recommendation
**Option A — Full bypass.** The existing dev experience is already completely
open. Adding auth friction to local development provides no security benefit
(no real data, no network exposure). Production deployment will NEVER set
`COMPOUNDOS_DEV_MODE=1`.

### Owner Decision
- [ ] APPROVE — Option A (Full bypass)
- [ ] APPROVE — Option B (Confirm-only bypass)
- [ ] APPROVE — Option C (No bypass)
- [ ] OTHER:

---

## OD-10-D-2: READ Endpoint Authentication

### Question
Should READ-only endpoints (dashboard, positions, guardian status) require
the X-API-Key header?

### Context
The dashboard and other read endpoints aggregate private financial data.
Currently they're completely open. Requiring auth on READ would protect
this data but adds header requirements to every request.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: No auth on READ | READ endpoints remain open | Simple; no frontend changes | Private data accessible without auth |
| B: Optional auth | READ accepts optional X-API-Key; if present, enriches with owner context | Graceful; frontend can add key when ready | Slightly more complex middleware |
| C: Required auth | All endpoints require X-API-Key | Maximum security | Breaks existing frontend; all API consumers need key |

### Recommendation
**Option A — No auth on READ in V1.** The dashboard is currently behind
localhost. Future network exposure (SEC-001 gate) will require auth on all
endpoints. For Sprint 010, keep READ open and focus auth on mutation endpoints.

### Owner Decision
- [ ] APPROVE — Option A (No auth on READ)
- [ ] APPROVE — Option B (Optional auth on READ)
- [ ] APPROVE — Option C (Required auth on READ)
- [ ] OTHER:

---

## OD-10-D-3: Audit Log Retention

### Question
How long should audit log records be retained?

### Context
Audit logs record every authentication attempt and authorization decision.
Over time this table will grow. The retention policy determines whether old
records are pruned or kept indefinitely.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Indefinite | Keep all audit records forever | Complete history; compliance-friendly | Table grows unbounded |
| B: 90 days | Prune records older than 90 days | Predictable storage; manageable | Loses history |
| C: Configurable | Retention period set via env variable | Flexible; can tighten/relax per environment | Slightly more complex |

### Recommendation
**Option A — Indefinite.** For a single-owner family office, audit volume
is very low (tens of events per day). An audit_log row is ~200 bytes.
At 100 events/day, that's 7 MB/year. Indefinite retention is feasible and
provides complete accountability.

### Owner Decision
- [ ] APPROVE — Option A (Indefinite)
- [ ] APPROVE — Option B (90 days)
- [ ] APPROVE — Option C (Configurable)
- [ ] OTHER:

---

## OD-10-D-4: API Key Auto-Expiry

### Question
Should API keys automatically expire after a set period?

### Context
Key rotation is a security best practice. Auto-expiry forces rotation.
Manual management gives the Owner control over when to rotate.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: No auto-expiry | Keys valid until explicitly revoked | Simple; Owner controls timing | Stale keys persist |
| B: 90-day rotation | Keys expire 90 days after creation | Best practice alignment | Owner must rotate quarterly |
| C: Per-key expiry | Each key has configurable expires_at | Flexible; short-lived + long-lived keys coexist | More complex key creation UI |

### Recommendation
**Option A — No auto-expiry in V1.** For a single-owner system with local
deployment, key rotation is good practice but not critical. The Owner can
manually revoke and rotate keys at any time. Auto-expiry adds operational
complexity without proportional security benefit at this stage.

### Owner Decision
- [ ] APPROVE — Option A (No auto-expiry)
- [ ] APPROVE — Option B (90-day rotation)
- [ ] APPROVE — Option C (Per-key expiry)
- [ ] OTHER:

---

## OD-10-D-5: Escalation Implementation Scope

### Question
Should any escalation delivery channels be implemented in Sprint 010?

### Context
Per OD-10-5 (Sprint 010 high-level: "Design only"), escalation channels
are deferred. Slice D defines the escalation_rules schema. The question is
whether to implement any delivery now.

### Options

| Option | Description | Pros | Cons |
|---|---|---|---|
| A: Schema only | Define escalation_rules table; no delivery code | Matches OD-10-5; keeps Sprint 010 bounded | No actionable escalation |
| B: Email only | Implement SMTP delivery for level-1 escalation | Immediate practical value | Requires email config (SMTP server, credentials) |
| C: None | Don't even define the schema yet | Minimal migration | Postpones architecture decision |

### Recommendation
**Option A — Schema only.** Per the earlier Owner decision OD-10-5. The
schema is defined, the architecture is designed, and implementation is
deferred to when the system has real network exposure. This keeps Sprint
010 focused on API-layer features.

### Owner Decision
- [ ] APPROVE — Option A (Schema only)
- [ ] APPROVE — Option B (Email only)
- [ ] APPROVE — Option C (None — defer schema too)
- [ ] OTHER:

---

## Decision Summary

| ID | Topic | Recommendation | Owner Decision |
|---|---|---|---|
| OD-10-D-1 | Dev mode bypass | Full bypass (A) | |
| OD-10-D-2 | READ endpoint auth | No auth on READ (A) | |
| OD-10-D-3 | Audit log retention | Indefinite (A) | |
| OD-10-D-4 | Key auto-expiry | No auto-expiry (A) | |
| OD-10-D-5 | Escalation scope | Schema only (A) | |

---

## Post-Decision Process

1. Owner marks each decision above.
2. Agent updates this document with final decisions.
3. Agent updates MASTER_PLAN.
4. Implementation begins (Sprint 010 Slice D — final slice).

---

## AI Authority Reminder

None of these decisions expand AI authority:
- AI cannot manage API keys (Owner only)
- AI cannot modify audit logs (immutable)
- AI cannot configure escalation rules (Owner only)
- Authentication is a system boundary, not an AI function
