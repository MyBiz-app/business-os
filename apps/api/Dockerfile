# Production image for the API. Build from apps/api:  docker build -t business-os-api .
FROM python:3.13-slim AS base

RUN pip install --no-cache-dir uv==0.8.17

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so code changes don't invalidate the cached layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --system --uid 1001 api
USER api

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Hosting platforms pass the port in $PORT. Migrations run as a separate release step:
#   alembic upgrade head
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
