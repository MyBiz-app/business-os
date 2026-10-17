#!/usr/bin/env bash
# Usage: render-rollback.sh [deploy-id]
# Rolls the Render API service back to a previous deploy (the newest one that was live before the
# current one, unless an id is given). Needs RENDER_API_KEY and RENDER_SERVICE_ID.
# The database is NOT rolled back: see docs/deploy/releases.md ("Rollback and the database").
set -euo pipefail
: "${RENDER_API_KEY:?RENDER_API_KEY is not set}"
: "${RENDER_SERVICE_ID:?RENDER_SERVICE_ID is not set}"
api="https://api.render.com/v1/services/$RENDER_SERVICE_ID"
auth=(-H "Authorization: Bearer $RENDER_API_KEY" -H "Accept: application/json")

deploy_id="${1:-}"
if [ -z "$deploy_id" ]; then
  deploy_id="$(curl --silent --fail --show-error "${auth[@]}" "$api/deploys?limit=20" \
    | jq -r '[.[].deploy | select(.status == "deactivated")][0].id // empty')"
fi
if [ -z "$deploy_id" ]; then
  echo "::error::No earlier live deploy found to roll back to."
  exit 1
fi
echo "Rolling the API back to deploy $deploy_id"
curl --silent --fail --show-error -X POST "${auth[@]}" -H "Content-Type: application/json" \
  -d "{\"deployId\": \"$deploy_id\"}" "$api/rollback" > /dev/null
echo "Rollback to $deploy_id started."
