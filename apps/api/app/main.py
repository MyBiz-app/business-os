from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api import (
    assistant,
    bookings,
    client_app,
    client_import,
    clients,
    locations,
    modules,
    plans,
    platform,
    privacy,
    reports,
    schedule,
    services,
    staff,
)
from app.api import health as health_declarations
from app.api import settings as business_settings
from app.api.routes import router
from app.core.config import get_settings


class HealthResponse(BaseModel):
    status: str
    environment: str


def create_app() -> FastAPI:
    settings = get_settings()
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
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        expose_headers=["Cache-Control"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
    )

    @app.get("/health", tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=settings.environment)

    app.include_router(router)
    app.include_router(client_import.router)
    app.include_router(clients.router)
    app.include_router(privacy.router)
    app.include_router(services.router)
    app.include_router(locations.router)
    app.include_router(staff.router)
    app.include_router(schedule.router)
    app.include_router(bookings.router)
    app.include_router(plans.router)
    app.include_router(reports.router)
    app.include_router(assistant.router)
    app.include_router(modules.router)
    app.include_router(platform.router)
    app.include_router(client_app.public_router)
    app.include_router(client_app.router)
    app.include_router(health_declarations.router)
    app.include_router(health_declarations.client_router)
    app.include_router(business_settings.router)
    app.include_router(business_settings.public_router)

    return app


app = create_app()
