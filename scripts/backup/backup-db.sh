#!/usr/bin/env bash
# Daily encrypted database dump to the second (independent) storage: Cloudflare R2.
#
# Needs: pg_dump, age, aws (the AWS CLI talks to R2's S3 API).
# Environment (names only; values are secrets and never go in the repository):
#   BACKUP_DATABASE_URL   session-pooler connection string of the database to dump
#   BACKUP_AGE_RECIPIENT  age PUBLIC key (age1...); the private key stays with the owner only
#   R2_ENDPOINT           https://<account-id>.r2.cloudflarestorage.com
#   R2_BUCKET             bucket name
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY   R2 API token (object read and write)
# Optional: BACKUP_PREFIX (default "db"), BACKUP_RETENTION_DAYS (default 30).
set -euo pipefail

: "${BACKUP_DATABASE_URL:?}" "${BACKUP_AGE_RECIPIENT:?}" "${R2_ENDPOINT:?}" "${R2_BUCKET:?}"
prefix="${BACKUP_PREFIX:-db}"
retention="${BACKUP_RETENTION_DAYS:-30}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
key="${prefix}/mybiz-${stamp}.dump.age"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Dump straight into the encryption: an unencrypted dump never touches the disk.
pg_dump --format=custom --no-owner --no-privileges "$BACKUP_DATABASE_URL" \
  | age -r "$BACKUP_AGE_RECIPIENT" -o "$work/dump.age"

size="$(stat -c %s "$work/dump.age")"
if [ "$size" -lt 1024 ]; then
  echo "Backup is suspiciously small ($size bytes); not uploading." >&2
  exit 1
fi

aws s3 cp --endpoint-url "$R2_ENDPOINT" "$work/dump.age" "s3://${R2_BUCKET}/${key}" --only-show-errors
echo "Uploaded ${key} (${size} bytes)"

# Retention: delete dumps older than N days (the object name carries its date).
cutoff="$(date -u -d "-${retention} days" +%Y%m%d)"
aws s3 ls --endpoint-url "$R2_ENDPOINT" "s3://${R2_BUCKET}/${prefix}/" | awk '{print $4}' | while read -r name; do
  day="$(printf '%s' "$name" | sed -n 's/^mybiz-\([0-9]\{8\}\)T.*\.dump\.age$/\1/p')"
  if [ -n "$day" ] && [ "$day" -lt "$cutoff" ]; then
    aws s3 rm --endpoint-url "$R2_ENDPOINT" "s3://${R2_BUCKET}/${prefix}/${name}" --only-show-errors
    echo "Deleted old backup ${name}"
  fi
done
