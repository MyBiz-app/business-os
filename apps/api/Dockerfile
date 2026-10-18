# Production image for the API. Build from apps/api:  docker build -t business-os-api .
FROM python:3.13-slim AS base

# WeasyPrint (PDF documents) needs Pango and HarfBuzz; the fonts it uses ship with the code.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

# setuptools ships with the base image and lags behind its security fixes; upgrade it here.
RUN pip install --no-cache-dir --upgrade uv==0.11.15 "setuptools>=83"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so code changes don't invalidate the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --system --uid 1001 api
USER api

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# The entrypoint runs the migrations (only where RUN_MIGRATIONS_ON_START allows it, see the script)
# and then starts the API; the port comes from $PORT. Migrations are additive, so the previous
# version keeps working while it drains.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"
CMD ["sh", "/app/docker-entrypoint.sh"]
