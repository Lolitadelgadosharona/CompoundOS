#!/usr/bin/env bash
# backup.sh — CompoundOS PostgreSQL backup
# Usage: ./scripts/backup.sh
# Schedule: 0 2 * * * /app/scripts/backup.sh (daily at 2 AM)

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/compoundos_${TIMESTAMP}.sql.gz"
DB_URL="${DATABASE_URL:-postgresql+psycopg://compoundos:local@db:5432/compoundos}"

# Extract connection params from SQLAlchemy URL
# Format: postgresql+psycopg://user:pass@host:port/dbname
DB_USER=$(echo "$DB_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DB_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DB_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_PORT="${DB_PORT:-5432}"
DB_NAME=$(echo "$DB_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup of $DB_NAME..."

PGPASSWORD="$DB_PASS" pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner --no-acl \
    | gzip > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$(date)] Backup complete: $BACKUP_FILE ($SIZE)"

# Keep last 30 days of backups
find "$BACKUP_DIR" -name "compoundos_*.sql.gz" -mtime +30 -delete

echo "[$(date)] Cleaned up old backups."
