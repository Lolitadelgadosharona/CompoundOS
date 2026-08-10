# Sprint 010 Slice D — Owner Decisions

> **STATUS: OWNER DECISIONS RESOLVED — READY FOR IMPLEMENTATION**
>
> Sprint 010 Slice D Design: COMPLETE
> All 5 decisions recorded. Implementation proceeds.

---

## OD-10-D-1: Development Mode Bypass

### Question
When `ENVIRONMENT` is set to `development` or `test`, should the auth
middleware skip validation?

### Owner Decision
- [x] **APPROVED — Environment-based bypass**
  - **Development/Test**: Full bypass — auth middleware skipped
  - **Production**: Authentication always required
  - Implementation: check `ENVIRONMENT` env var, not `COMPOUNDOS_DEV_MODE`
  - Rationale: Production must never run without auth. Bypass is explicitly
    scoped to non-production environments.

---

## OD-10-D-2: READ Endpoint Authentication

### Question
Should READ-only endpoints (dashboard, positions, guardian status) require
the X-API-Key header?

### Owner Decision
- [x] **APPROVED — Require auth for all financial READ endpoints**
  - Financial data endpoints require X-API-Key: /api/dashboard, /api/positions,
    /api/guardian/*, /api/decisions/*, /api/investment-ideas/*
  - Only `/health` and `/api/health` remain PUBLIC (no auth required)
  - Rationale: Dashboard and portfolio data are sensitive financial information.
    Health endpoints are infrastructure-level and remain open.

---

## OD-10-D-3: Audit Log Retention

### Question
How long should audit log records be retained?

### Owner Decision
- [x] **APPROVED — Indefinite retention**
  - All audit_log records kept permanently
  - No pruning, no expiry
  - Rationale: Audit logs are immutable historical records. They provide
    the definitive account of all system activity. Volume is low enough
    (~7 MB/year at 100 events/day) that indefinite retention is feasible.

---

## OD-10-D-4: API Key Auto-Expiry

### Question
Should API keys automatically expire after a set period?

### Owner Decision
- [x] **APPROVED — No automatic expiry**
  - Keys valid until explicitly revoked
  - Must support: revoke, rotate, audit usage
  - Key creation → API key returned once (Owner stores securely)
  - Key revocation → `revoked_at` timestamp, key hash preserved for audit
  - Key rotation → create new key, revoke old key
  - Audit: all key usage logged to audit_log
  - Rationale: Manual control with full audit trail. Auto-expiry adds
    operational complexity without proportional security benefit at V1.

---

## OD-10-D-5: Escalation Implementation Scope

### Question
Should any escalation delivery channels be implemented in Sprint 010?

### Owner Decision
- [x] **APPROVED — Schema foundation only**
  - `notification_escalation_rules` table defined (schema only)
  - No email/SMS/external notification delivery implementation
  - Escalation paths documented in design but not implemented
  - Rationale: Maintains Sprint 010 scope boundaries. Escalation channels
    require external service credentials which are not authorized yet.

---

## Decision Summary

| ID | Topic | Recommendation | Owner Decision |
|---|---|---|---|
| OD-10-D-1 | Dev mode bypass | Full bypass (A) | Environment-based: dev/test bypass, production requires auth |
| OD-10-D-2 | READ endpoint auth | No auth on READ (A) | Required for all financial READ; health only PUBLIC |
| OD-10-D-3 | Audit log retention | Indefinite (A) | Indefinite — immutable records |
| OD-10-D-4 | Key auto-expiry | No auto-expiry (A) | No expiry; must support revoke, rotate, audit |
| OD-10-D-5 | Escalation scope | Schema only (A) | Schema foundation only; no email/SMS

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
