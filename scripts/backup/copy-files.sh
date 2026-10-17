#!/usr/bin/env bash
# Daily copy of the Supabase Storage bucket (documents, logos, payslips) to the second storage.
# Files are copied, never deleted from the destination by this script; the destination lifecycle
# rule (docs/deploy/restore-runbook.md) removes versions older than the retention window.
#
# Needs: aws. Environment (names only):
#   FILES_S3_ENDPOINT      Supabase Storage S3 endpoint, https://<ref>.storage.supabase.co/storage/v1/s3
#   FILES_S3_ACCESS_KEY_ID, FILES_S3_SECRET_ACCESS_KEY   Supabase Storage S3 keys
#   FILES_BUCKET           source bucket (default "files")
#   R2_ENDPOINT, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY   destination
# Optional: FILES_PREFIX (default "files").
set -euo pipefail

: "${FILES_S3_ENDPOINT:?}" "${FILES_S3_ACCESS_KEY_ID:?}" "${FILES_S3_SECRET_ACCESS_KEY:?}"
: "${R2_ENDPOINT:?}" "${R2_BUCKET:?}" "${R2_ACCESS_KEY_ID:?}" "${R2_SECRET_ACCESS_KEY:?}"
bucket="${FILES_BUCKET:-files}"
prefix="${FILES_PREFIX:-files}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

AWS_ACCESS_KEY_ID="$FILES_S3_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$FILES_S3_SECRET_ACCESS_KEY" \
  AWS_DEFAULT_REGION="${FILES_S3_REGION:-eu-central-1}" \
  aws s3 sync --endpoint-url "$FILES_S3_ENDPOINT" "s3://${bucket}" "$work/files" --only-show-errors

count="$(find "$work/files" -type f 2>/dev/null | wc -l)"
echo "Downloaded ${count} files from ${bucket}"

AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
  AWS_DEFAULT_REGION=auto \
  aws s3 sync --endpoint-url "$R2_ENDPOINT" "$work/files" "s3://${R2_BUCKET}/${prefix}/" --only-show-errors
echo "Synced ${count} files to ${R2_BUCKET}/${prefix}/"
