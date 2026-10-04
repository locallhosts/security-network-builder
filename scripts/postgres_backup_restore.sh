#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_DB_URL:?Set SOURCE_DB_URL to the PostgreSQL source database URL}"
: "${RESTORE_DB_URL:?Set RESTORE_DB_URL to a disposable PostgreSQL restore target}"
BACKUP_FILE="${BACKUP_FILE:-/tmp/snb-history.dump}"

command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 1; }
command -v pg_restore >/dev/null || { echo "pg_restore is required" >&2; exit 1; }

echo "Creating PostgreSQL custom-format backup..."
pg_dump --format=custom --no-owner --no-acl --dbname="$SOURCE_DB_URL" --file="$BACKUP_FILE"

echo "Restoring backup into disposable target..."
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$RESTORE_DB_URL" "$BACKUP_FILE"

source_count="$(psql "$SOURCE_DB_URL" -Atc 'SELECT count(*) FROM runs')"
restore_count="$(psql "$RESTORE_DB_URL" -Atc 'SELECT count(*) FROM runs')"
source_latest="$(psql "$SOURCE_DB_URL" -Atc 'SELECT coalesce(max(id),0) FROM runs')"
restore_latest="$(psql "$RESTORE_DB_URL" -Atc 'SELECT coalesce(max(id),0) FROM runs')"

test "$source_count" = "$restore_count"
test "$source_latest" = "$restore_latest"

echo "Backup/restore verification passed: runs=$source_count latest_run=$source_latest"