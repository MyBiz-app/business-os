from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import Engine, text

from app.api.registry import ROUTERS
from app.core.config import get_settings, missing_production_settings
from app.core.db import get_engine
from app.core.logging import configure_logging, request_logging
from app.core.monitoring import init_monitoring
from app.core.rate_limit import TenantQuota, build_store, limiter


class HealthResponse(BaseModel):
    status: str
    environment: str


class ReadyResponse(BaseModel):
    status: str
    database: str


def create_app() -> FastAPI:
    settings = get_settings()
    if missing := missing_production_settings(settings):
        raise RuntimeError(f"production needs these settings: {', '.join(missing)}")
    configure_logging()
    init_monitoring(settings)
    app = FastAPI(
        title="Business OS API",
        version="0.1.0",
        # Operation ids become method names in the generated client, so keep them short.
        generate_unique_id_function=lambda route: route.name,
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        # A JSON API is never framed, sniffed or a referrer source.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # The API only ever answers over HTTPS in staging and production (the host redirects plain HTTP).
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Answers carry one person's or one business's data: no browser or proxy keeps a copy.
        # Routes that choose their own policy (downloads, logos) keep it.
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    if settings.rate_limits_on:
        token = settings.internal_token.get_secret_value() if settings.internal_token else None
        store = build_store(
            settings.rate_limit_redis_url.get_secret_value()
            if settings.rate_limit_redis_url
            else None
        )
        app.state.tenant_quota = TenantQuota(store, settings.tenant_rate_limit_per_minute)
        app.middleware("http")(
            limiter(
                store,
                trust_forwarded=settings.trust_forwarded_for,
                internal_token=token,
            )
        )

    # Registered after the limiter (so 429s are logged) and before CORS (so a logged crash
    # still gets CORS headers); later registrations wrap earlier ones.
    app.middleware("http")(request_logging)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        expose_headers=["Cache-Control", "X-Request-ID", "X-Next-Cursor"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-ID"],
    )

    @app.get("/health", tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=settings.environment)

    @app.get("/health/ready", tags=["system"], responses={503: {"model": ReadyResponse}})
    def ready(engine: Annotated[Engine, Depends(get_engine)]) -> ReadyResponse:
        """Ready to serve: the database answers. Monitoring polls this; /health only says the
        process is up."""
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(  # type: ignore[return-value]
                ReadyResponse(status="unavailable", database="unreachable").model_dump(),
                status_code=503,
            )
        return ReadyResponse(status="ok", database="ok")

    for router in ROUTERS:
        app.include_router(router)

    return app


app = create_app()
