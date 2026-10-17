#!/bin/sh
# Starts the API. The database is brought up to date first only where RUN_MIGRATIONS_ON_START
# allows it: staging sets it to "true" (migrations run when a new container starts). Production
# sets it to "false" and runs `alembic upgrade head` once as the host's pre-deploy step, so the
# old version keeps serving until the new schema is in place and several instances never race.
# Unset means: migrate everywhere except production (the safe side for a forgotten variable).
set -e

case "${RUN_MIGRATIONS_ON_START:-}" in
  true | 1 | yes) migrate=1 ;;
  false | 0 | no) migrate=0 ;;
  *)
    if [ "${API_ENVIRONMENT:-}" = "production" ]; then migrate=0; else migrate=1; fi
    ;;
esac

if [ "$migrate" = "1" ]; then
  alembic upgrade head
fi

# The port comes from $PORT (hosting platforms). WEB_CONCURRENCY sets the worker processes (default
# 2). Limits that count per process (rate limits) apply per worker.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-proxy-headers --workers "${WEB_CONCURRENCY:-2}"
