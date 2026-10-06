#!/bin/sh
# CompoundOS production entrypoint — M7-002 Slice A.
#
# 1. Apply database migrations only with explicit COMPOUNDOS_RUN_MIGRATIONS=1.
# 2. Fail closed: if the migration fails, exit non-zero so the app never
#    starts with a mismatched schema (mutation_gate would otherwise 503).
# 3. Start the API after any explicitly requested migration succeeds.
#    exec preserves PID 1 for signal delivery.

set -eu

# Production migration is an explicit Owner-controlled step, never implicit on restart.
if [ "${COMPOUNDOS_RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "Running database migrations (alembic upgrade head)..."
    if ! alembic upgrade head; then
        echo "ERROR: database migration failed — aborting startup" >&2
        exit 1
    fi
fi

echo "Starting API; schema mutation gate remains enforced..."
exec uvicorn apps.api.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
