# Sprint 010 Slice D — Technical Design
# Authentication, Authorization, Audit & Escalation

> **STATUS: DESIGN PHASE — NOT AUTHORIZED FOR IMPLEMENTATION**
>
> Sprint 010 Slice A (Committee Bridge): DONE — 972bf24 (PR #82)
> Sprint 010 Slice B (Guardian Intelligence): DONE — 414e38f (PR #83)
> Sprint 010 Slice C (Dashboard + Learning): DONE — 558dbac (PR #84)
> Sprint 010 Slice D (Security + Notifications): DESIGN ONLY
>
> This is the final slice of Sprint 010 — the security foundation
> and notification escalation architecture.

---

## 1. Objective

Establish the identity, access, and audit layer for CompoundOS, and design
the notification escalation data model.

**This is NOT:**
- Full enterprise IAM (single-owner family office)
- External auth provider integration (OAuth2, SSO)
- Email/SMS delivery implementation
- Broker credential management

**This IS:**
- Owner API key authentication via X-API-Key header
- Endpoint classification (READ / OWNER_MUTATION / SYSTEM_INTERNAL / PUBLIC)
- Immutable audit log for all security events
- Escalation rules schema (design only)

---

## 2. Existing Foundation

### 2.1 Current State

| System | Sprint | Auth Status |
|---|---|---|
| All routers | 002–010 | No authentication — any request accepted |
| Health endpoint | 007 | PUBLIC |
| Worker endpoints | 005 | No auth (localhost only) |
| Notification infrastructure | 007/008 | No auth on preferences |

### 2.2 What Slice D Adds

| Component | Type | Purpose |
|---|---|---|
| `owner_api_keys` table | New | Hashed API key storage |
| Auth middleware | New | FastAPI Depends for X-API-Key validation |
| Endpoint classification | Documentation + decorators | READ / OWNER_MUTATION / SYSTEM_INTERNAL / PUBLIC |
| `audit_log` table | New | Immutable security event records |
| `notification_escalation_rules` | New | Escalation config (schema only) |
| `notification_events` | Extended CHECK | New escalation-related fields |

---

## 3. Authentication Design

### 3.1 API Key Architecture

```
┌──────────────────────────────────────────────────┐
│              Request Authentication Flow          │
├──────────────────────────────────────────────────┤
│  Client → X-API-Key header → Middleware           │
│    ↓                                               │
│  1. Extract key from header                       │
│  2. Hash with SHA-256                             │
│  3. Look up hash in owner_api_keys                │
│  4. If match → set request.state.role = 'owner'   │
│  5. If no match → 401 Unauthorized                │
│  No match + OWNER_MUTATION → 401                  │
│  Match + READ → 200 (optional auth)               │
└──────────────────────────────────────────────────┘
```

### 3.2 Key Storage

| Column | Type | Purpose |
|---|---|---|
| `id` | UUID | Primary key |
| `key_hash` | TEXT (UNIQUE) | SHA-256 hash of the API key |
| `label` | TEXT | Human-readable label (e.g. "Owner CLI 2026") |
| `created_at` | TIMESTAMPTZ | When key was created |
| `last_used_at` | TIMESTAMPTZ, nullable | Last successful auth |
| `revoked_at` | TIMESTAMPTZ, nullable | When revoked (NULL = active) |
| `created_by` | TEXT | Who created this key |
| `revoked_by` | TEXT, nullable | Who revoked it |

**Hashing**: SHA-256 with per-key UUID salt stored in a separate column.

### 3.3 Key Rotation

1. Owner generates new key: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Owner sets `COMPOUNDOS_API_KEY` in environment or config
3. Owner calls `POST /api/auth/keys` to register the new key
4. System hashes and stores the key
5. Owner revokes old key via `DELETE /api/auth/keys/{id}`
6. Old key hash remains (audit trail) but `revoked_at` is set

### 3.4 Middleware

```python
# apps/api/middleware/auth.py
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

async def require_owner_auth(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Middleware: require valid X-API-Key for OWNER_MUTATION endpoints."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(401, "X-API-Key header required")
    key_hash = _hash_key(api_key)
    valid = _validate_key(session, key_hash)
    if not valid:
        _log_audit(session, "authentication.failure", ...)
        raise HTTPException(401, "Invalid API key")
    _log_audit(session, "authentication.success", ...)
    request.state.role = "owner"
```

### 3.5 Development Bypass

For local development, the middleware accepts a configurable bypass:

```python
if os.getenv("COMPOUNDOS_DEV_MODE") == "1":
    request.state.role = "owner"
    return  # Skip auth in development
```

This preserves the existing developer experience while adding production auth.

---

## 4. Authorization Layer

### 4.1 Endpoint Classification

| Classification | HTTP Methods | Examples | Auth Required |
|---|---|---|---|
| `PUBLIC` | GET | /health, /api/health | None |
| `READ` | GET | /api/dashboard, /api/positions, /api/guardian/events | None in V1 |
| `OWNER_MUTATION` | POST, PATCH, DELETE | /api/import/*, /api/investment-ideas/*, /api/decisions/* | X-API-Key |
| `SYSTEM_INTERNAL` | POST | /api/worker/*, /api/guardian/evaluate (worker) | Shared secret |

### 4.2 Role Matrix

| Action | Owner | System | AI (future) |
|---|---|---|---|
| Read portfolio | ✓ | ✓ | ✓ |
| Import data | ✓ | ✗ | ✗ |
| Create investment ideas | ✓ | ✗ | ✓ (READ only in V1) |
| Approve decisions | ✓ | ✗ | ✗ |
| Modify policy | ✓ | ✗ | ✗ |
| Execute Guardian evaluation | ✓ | ✓ | ✗ |
| View dashboard | ✓ | ✗ | ✓ (future) |
| Manage API keys | ✓ | ✗ | ✗ |
| Acknowledge risks | ✓ | ✗ | ✗ |
| Complete reviews | ✓ | ✗ | ✗ |

### 4.3 Classification Declaration

Endpoints declare their classification via dependency injection:

```python
@router.post("/api/import/positions", dependencies=[Depends(require_owner_auth)])
def import_positions(...): ...

@router.get("/api/dashboard")
def get_dashboard(...): ...  # READ — no auth required
```

---

## 5. Audit Logging

### 5.1 Schema

```
audit_log
├── id (UUID PK)
├── event_type (TEXT) — 'authentication.success','authentication.failure',
│                       'authorization.denied','owner.mutation',
│                       'system.action'
├── actor_id (TEXT, nullable) — API key hash or 'system'
├── actor_role (TEXT, nullable) — 'owner','system','ai'
├── action (TEXT) — HTTP method + path, e.g. 'POST /api/import/positions'
├── resource (TEXT, nullable) — affected entity ID
├── outcome (TEXT) — 'success','failure','denied'
├── detail (TEXT, nullable) — human-readable context
├── ip_address (TEXT, nullable)
├── occurred_at (TIMESTAMPTZ) — when the event happened
├── created_at (TIMESTAMPTZ) — when the record was written
```

### 5.2 Immutability

```sql
-- Trigger prevents ANY modification to audit records
CREATE OR REPLACE FUNCTION fn_audit_log_immutability()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log records are immutable'
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_log_immutability
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION fn_audit_log_immutability();
```

### 5.3 Event Taxonomy

| Event Type | Trigger | Actor | Severity |
|---|---|---|---|
| `authentication.success` | Valid X-API-Key matched | Owner | info |
| `authentication.failure` | Invalid X-API-Key | Unknown (key hash) | warning |
| `authorization.denied` | Role insufficient for action | Owner | warning |
| `owner.mutation` | Successful POST/PATCH/DELETE | Owner | info |
| `system.action` | Worker execution, Guardian run | System | info |

### 5.4 What Gets Logged

| Action | Logged | Not Logged |
|---|---|---|
| Failed auth (wrong key) | ✓ | Key value (only hash) |
| Successful auth | ✓ | Key value (only hash) |
| Authorization denied | ✓ | |
| Successful mutation | ✓ | |
| Read operations | ✗ (not logged to reduce noise) | |
| Health checks | ✗ | |

---

## 6. Notification Escalation Foundation

### 6.1 Schema (Design Only)

```
notification_escalation_rules
├── id (UUID PK)
├── source (TEXT) — 'guardian','committee','decision_review'
├── event_severity (TEXT) — 'critical','warning','info'
├── escalate_after_hours (INTEGER) — hours before escalation
├── escalation_level (INTEGER) — 1=email, 2=sms, 3=phone
├── enabled (BOOLEAN) — default TRUE
├── created_at (TIMESTAMPTZ)
```

**CHECK constraint**: event_severity IN ('critical','warning','info')

### 6.2 Escalation Paths (Design Only — No Implementation)

| Source | Severity | Level 1 (in-app) | Level 2 (email) | Level 3 (SMS) |
|---|---|---|---|---|
| Guardian `critical` | critical | Immediate | After 1h | After 24h |
| Guardian `warning` | warning | Immediate | Not escalated | Not escalated |
| Committee outcome | info | Immediate | Not escalated | Not escalated |
| Decision review due | info | Daily reminder | Not escalated | Not escalated |

**No delivery channel implementation in Sprint 010.** The table and rules
are defined; email/SMS integration is deferred.

### 6.3 Notification Events Extension

Extend `notification_events` CHECK constraint:

```
notification_events.source IN (
    'guardian','committee','automation','backup','health',
    'investment_idea',       -- from Slice C
    'decision_review',       -- from Slice D
    'escalation'            -- from Slice D
)
```

---

## 7. Database Impact

### 7.1 Migration: 0025_auth_and_audit

| Change | Table | Detail |
|---|---|---|
| CREATE | `owner_api_keys` | Hashed API key storage |
| CREATE | `audit_log` | Immutable security event records |
| CREATE | `notification_escalation_rules` | Escalation config (schema only) |
| Extend CHECK | `notification_events` | Add 'decision_review','escalation' sources |

**Additive only. Fully reversible.**

### 7.2 Triggers

| Trigger | Table | Purpose |
|---|---|---|
| `trg_audit_log_immutability` | `audit_log` | Prevents UPDATE/DELETE of audit records |

---

## 8. API Design

### 8.1 New Endpoints

| Method | Path | Classification | Description |
|---|---|---|---|
| POST | /api/auth/keys | OWNER_MUTATION | Register a new API key |
| GET | /api/auth/keys | OWNER_MUTATION | List active API keys |
| DELETE | /api/auth/keys/{id} | OWNER_MUTATION | Revoke an API key |
| GET | /api/audit | SYSTEM_INTERNAL | Query audit log (worker only) |

### 8.2 Existing Endpoints Classification

All existing endpoints are documented with their classification via comments
or decorator metadata. This is documentation — not middleware enforcement
on all endpoints yet. The middleware is applied to OWNER_MUTATION endpoints
in this slice; READ endpoints remain open.

---

## 9. Implementation Plan

### 9.1 File List

| File | Purpose |
|---|---|
| `migrations/versions/0025_auth_and_audit.py` | Migration |
| `apps/api/models.py` | + OwnerApiKey, AuditLog, NotificationEscalationRule |
| `apps/api/middleware/__init__.py` | Package |
| `apps/api/middleware/auth.py` | Auth middleware |
| `apps/api/database.py` | + key hashing utilities |
| `apps/api/routers/auth.py` | Key management endpoints |
| `tests/test_auth_audit.py` | Integration tests |
| `tests/api/test_households.py` | + audit_log, owner_api_keys, notification_escalation_rules |

### 9.2 Implementation Order

1. Migration 0025
2. Models: OwnerApiKey, AuditLog, NotificationEscalationRule
3. Auth middleware (require_owner_auth dependency)
4. Key hashing utilities
5. Auth router (key CRUD)
6. Classify existing OWNER_MUTATION endpoints
7. Tests
8. HEAD_REVISION sweep
9. Approved tables update

---

## 10. Test Strategy

### 10.1 Migration Tests (4 tests)

| Test | What it proves |
|---|---|
| owner_api_keys table exists | Migration applied |
| audit_log table exists | Migration applied |
| audit_log immutability trigger | UPDATE/DELETE rejected |
| notification_escalation_rules CHECK | Invalid event_severity rejected |

### 10.2 Authentication Tests (5 tests)

| Test | What it proves |
|---|---|
| Valid key → 200 on OWNER_MUTATION | Auth works |
| Invalid key → 401 on OWNER_MUTATION | Auth rejects bad keys |
| Missing key → 401 on OWNER_MUTATION | Auth requires key |
| READ endpoint works without key | READ is open |
| Key creation and revocation | Key lifecycle |

### 10.3 Authorization Tests (3 tests)

| Test | What it proves |
|---|---|
| Owner can access OWNER_MUTATION | Role check |
| Unauthenticated cannot access OWNER_MUTATION | Boundary enforced |
| Dev mode bypass works | Development convenience |

### 10.4 Audit Tests (3 tests)

| Test | What it proves |
|---|---|
| Authentication success logged | Event recorded |
| Authentication failure logged | Event recorded |
| Audit records are immutable | UPDATE/DELETE rejected |

### 10.5 Notification Escalation Tests (2 tests)

| Test | What it proves |
|---|---|
| Escalation rule can be created | Schema valid |
| Invalid severity rejected | CHECK constraint |

### 10.6 Total: ~17 tests

---

## 11. Security Constraints (Confirmed)

| Constraint | Status |
|---|---|
| No credentials in code | Environment variable only |
| No broker integration | Not authorized |
| No trading | Not authorized |
| No external auth provider | Local API key only |
| No credential storage in DB | Keys are hashed — plaintext never stored |

---

## 12. Owner Decisions (Pending)

| ID | Decision | Options | Recommendation |
|---|---|---|---|
| OD-10-D-1 | Dev mode bypass level | A: Full bypass / B: Confirm-only / C: No bypass | A: Full bypass for local dev |
| OD-10-D-2 | READ endpoints require auth? | A: No auth on READ / B: Optional auth on READ | A: No auth on READ |
| OD-10-D-3 | Audit log retention | A: Indefinite / B: 90 days / C: Configurable | A: Indefinite for family office |
| OD-10-D-4 | Key rotation: auto-expiry? | A: No auto-expiry / B: 90-day rotation | A: No auto-expiry in V1 |
| OD-10-D-5 | Escalation: implement now? | A: Schema only / B: Email only / C: None | A: Schema only (per OD-10-5) |

---

## 13. Estimated Scope

| Component | Lines | Tests |
|---|---|---|
| Migration | ~100 | 4 |
| Models | ~100 | 0 |
| Auth middleware | ~60 | 3 |
| Auth router | ~80 | 5 |
| Existing endpoint classification | ~50 (docs) | 0 |
| Audit logging calls | ~30 (in middleware + mutation endpoints) | 3 |
| Notification extension | ~40 | 2 |
| HEAD_REVISION sweep | ~15 files | 0 |
| Approved tables | +3 entries | 0 |
| **Total** | **~475 lines** | **~17 tests** |

---

## 14. Absolute Exclusions

- No email/SMS delivery implementation
- No OAuth2, JWT, or session-based auth
- No external identity provider (Okta, Auth0, Google)
- No broker credentials
- No trading or execution
- No multi-user support (single-owner V1)
- No RBAC beyond Owner/System/AI roles
