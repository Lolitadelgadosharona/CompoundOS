#!/bin/sh
# CompoundOS VPS smoke check — read-only (M7-003 Slice C).
#
# Validates a deployment is healthy WITHOUT mutating data or printing
# secrets. Exit 0 = all checks passed, 1 = at least one check failed.
#
# Usage:
#   OWNER_KEY=<key> BASE_URL=http://127.0.0.1:8000 ./scripts/smoke_check.sh
#
# OWNER_KEY is optional — authenticated endpoints (readiness/health-full)
# will be checked with it when provided (never echoed).

set -u

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

pass=0
fail=0

ok() { echo "  ok   $1"; pass=$((pass + 1)); }
bad() { echo "  FAIL $1"; fail=$((fail + 1)); }

# GET with X-API-Key when OWNER_KEY is set (read-only, never prints key).
auth_curl() {
    if [ -n "${OWNER_KEY:-}" ]; then
        curl -fsS -H "X-API-Key: $OWNER_KEY" "$@"
    else
        curl -fsS "$@"
    fi
}

echo "CompoundOS smoke check — $BASE_URL"
echo ""

# 1. Docker service availability
if docker compose ps --format '{{.State}}' 2>/dev/null | grep -q running; then
    ok "docker services running"
else
    bad "docker services running (docker compose ps)"
fi

# 2. Public health endpoint
if curl -fsS "$BASE_URL/health" 2>/dev/null | grep -q '"status"'; then
    ok "health endpoint /health"
else
    bad "health endpoint /health"
fi

# 3. Readiness endpoint (read-only)
if auth_curl "$BASE_URL/api/setup/status" 2>/dev/null | grep -q '"overall"'; then
    ok "readiness /api/setup/status"
else
    bad "readiness /api/setup/status (set OWNER_KEY for production)"
fi

# 4. Migration readiness (schema_at_head == true)
if auth_curl "$BASE_URL/api/setup/status" 2>/dev/null | grep -q '"schema_at_head": true'; then
    ok "migration at head (schema_at_head=true)"
else
    bad "migration at head (schema_at_head=true)"
fi

echo ""
echo "Result: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
