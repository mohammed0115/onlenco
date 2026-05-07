#!/usr/bin/env bash
# Backup the Onlenco Postgres DB and media files to a target directory.
#
# Usage:
#   BACKUP_DIR=/var/backups/onlenco scripts/backup.sh
#
# Required env: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST
# Optional env: BACKUP_DIR (default ./backups), MEDIA_DIR (default ./media),
#               BACKUP_RETENTION_DAYS (default 14)
#
# Run via cron, e.g.:  0 3 * * *  /opt/onlenco/scripts/backup.sh

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
MEDIA_DIR="${MEDIA_DIR:-./media}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TS="$(date -u +%Y-%m-%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

DB_FILE="$BACKUP_DIR/db_${TS}.sql.gz"
echo "→ pg_dump → $DB_FILE"
PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
    -h "${POSTGRES_HOST:-127.0.0.1}" \
    -U "${POSTGRES_USER:-onlenco}" \
    -d "${POSTGRES_DB:-onlenco}" \
    --no-owner --no-privileges \
  | gzip > "$DB_FILE"

if [ -d "$MEDIA_DIR" ]; then
    MEDIA_FILE="$BACKUP_DIR/media_${TS}.tar.gz"
    echo "→ tar media → $MEDIA_FILE"
    tar -czf "$MEDIA_FILE" -C "$(dirname "$MEDIA_DIR")" "$(basename "$MEDIA_DIR")"
fi

echo "→ pruning backups older than ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -maxdepth 1 -type f -mtime +"$RETENTION_DAYS" -delete

echo "OK: backup complete in $BACKUP_DIR"
