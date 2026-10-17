#!/usr/bin/env bash
# Usage: wait-healthy.sh <url> [seconds]
# Succeeds when the address answers 2xx within the time limit (default 300 s), else fails.
set -u
url="${1:?usage: wait-healthy.sh <url> [seconds]}"
limit="${2:-300}"
end=$((SECONDS + limit))
while [ "$SECONDS" -lt "$end" ]; do
  if curl --silent --fail --max-time 15 --output /dev/null "$url"; then
    echo "Healthy: $url"
    exit 0
  fi
  sleep 10
done
echo "::error::$url did not become healthy within ${limit}s"
exit 1
