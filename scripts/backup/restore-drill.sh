#!/usr/bin/env bash
# Restore drill: download the newest encrypted dump, decrypt it, restore it into an EMPTY scratch
# database, run smoke queries and print how long it took. Never point TARGET_DATABASE_URL at
# production. Fill the result into the drill table in docs/deploy/restore-runbook.md.
#
# Needs: age, aws, pg_restore, psql. Environment (names only):
#   TARGET_DATABASE_URL   scratch database (empty); the script refuses a non-empty one
#   AGE_IDENTITY_FILE     path to the age PRIVATE key file (kept by the owner only)
#   R2_ENDPOINT, R2_BUCKET, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# Optional: BACKUP_PREFIX (default "db"), LOCAL_DUMP (use this encrypted file instead of R2).
set -euo pipefail

: "${TARGET_DATABASE_URL:?}" "${AGE_IDENTITY_FILE:?}"
prefix="${BACKUP_PREFIX:-db}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
start="$(date +%s)"

existing="$(psql "$TARGET_DATABASE_URL" -Atc "select count(*) from information_schema.tables where table_schema = 'public'")"
if [ "$existing" != "0" ]; then
  echo "Target database is not empty ($existing tables in public). Use a fresh scratch database." >&2
  exit 1
fi

if [ -n "${LOCAL_DUMP:-}" ]; then
  cp "$LOCAL_DUMP" "$work/dump.age"
  name="$(basename "$LOCAL_DUMP")"
else
  : "${R2_ENDPOINT:?}" "${R2_BUCKET:?}"
  name="$(aws s3 ls --endpoint-url "$R2_ENDPOINT" "s3://${R2_BUCKET}/${prefix}/" | awk '{print $4}' | grep -E '\.dump\.age$' | sort | tail -n 1)"
  [ -n "$name" ] || { echo "No backup found in ${R2_BUCKET}/${prefix}/" >&2; exit 1; }
  aws s3 cp --endpoint-url "$R2_ENDPOINT" "s3://${R2_BUCKET}/${prefix}/${name}" "$work/dump.age" --only-show-errors
fi
echo "Backup used: ${name}"

age -d -i "$AGE_IDENTITY_FILE" -o "$work/dump" "$work/dump.age"
pg_restore --no-owner --no-privileges --exit-on-error -d "$TARGET_DATABASE_URL" "$work/dump"

# Smoke checks: tables exist and the migration head is present.
tables="$(psql "$TARGET_DATABASE_URL" -Atc "select count(*) from information_schema.tables where table_schema = 'public'")"
head="$(psql "$TARGET_DATABASE_URL" -Atc "select version_num from alembic_version" 2>/dev/null || echo "none")"
echo "Restored tables in public: ${tables}"
echo "Migration head in the backup: ${head}"
[ "$tables" -gt 0 ] || { echo "Smoke check failed: no tables restored" >&2; exit 1; }

end="$(date +%s)"
echo "Restore took $((end - start)) seconds (download, decrypt, restore, checks)."
