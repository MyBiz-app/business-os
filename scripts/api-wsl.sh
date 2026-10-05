#!/usr/bin/env bash
# Runs the API from WSL (Ubuntu) on a Windows machine where Smart App Control blocks the
# unsigned Python binaries (uvicorn.exe, SQLAlchemy's and pydantic's compiled modules).
# The web app and the Expo apps keep running in PowerShell; Docker Desktop and the local
# Supabase are shared, and http://localhost:8000 works from Windows as usual.
#
#   bash /mnt/c/dev/business-os/scripts/api-wsl.sh            # migrate, then run the API
#   bash /mnt/c/dev/business-os/scripts/api-wsl.sh migrate    # only apply migrations
#   bash /mnt/c/dev/business-os/scripts/api-wsl.sh seed you@example.com   # demo data
set -euo pipefail

cd "$(dirname "$0")/../apps/api"

if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  echo "==> Installing uv (Python manager) for Linux"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# Linux packages live outside the Windows checkout, so the Windows .venv is left alone.
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/business-os-api"

echo "==> Python dependencies"
uv sync --quiet

echo "==> Database migrations"
uv run alembic upgrade head

case "${1:-run}" in
  migrate) ;;
  seed) uv run python -m app.seed --owner-email "${2:?usage: api-wsl.sh seed you@example.com}" ;;
  run)
    echo "==> API on http://localhost:8000 (Ctrl+C to stop)"
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ;;
  *) echo "usage: api-wsl.sh [run|migrate|seed EMAIL]" >&2; exit 2 ;;
esac
