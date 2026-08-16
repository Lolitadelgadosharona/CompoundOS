#!/bin/sh
# CompoundOS production entrypoint — M7-002 Slice A.
#
# 1. Apply database migrations (alembic upgrade head).
# 2. Fail closed: if the migration fails, exit non-zero so the app never
#    starts with a mismatched schema (mutation_gate would otherwise 503).
# 3. exec uvicorn only after a successful migration (exec preserves PID 1
#    so signals reach uvicorn).

set -eu

echo "Running database migrations (alembic upgrade head)..."
if ! alembic upgrade head; then
    echo "ERROR: database migration failed — aborting startup" >&2
    exit 1
fi

echo "Migrations complete. Starting API..."
exec uvicorn apps.api.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
