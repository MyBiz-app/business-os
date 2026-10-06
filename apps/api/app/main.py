from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api import (
    appointments,
    assistant,
    attention,
    billing,
    bookings,
    businesses,
    checkouts,
    client_app,
    client_import,
    client_notes,
    clients,
    leads,
    locations,
    marketing,
    messaging,
    modules,
    notifications,
    plans,
    platform,
    privacy,
    promo_codes,
    receipts,
    reports,
    reviews,
    schedule,
    services,
    staff,
    support,
    welcome,
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
    app.include_router(businesses.router)
    app.include_router(client_import.router)
    app.include_router(clients.router)
    app.include_router(client_notes.router)
    app.include_router(privacy.router)
    app.include_router(leads.router)
    app.include_router(messaging.router)
    app.include_router(leads.public_router)
    app.include_router(services.router)
    app.include_router(locations.router)
    app.include_router(staff.router)
    app.include_router(schedule.router)
    app.include_router(bookings.router)
    app.include_router(appointments.router)
    app.include_router(appointments.client_router)
    app.include_router(plans.router)
    app.include_router(promo_codes.router)
    app.include_router(reports.router)
    app.include_router(reviews.router)
    app.include_router(reviews.client_router)
    app.include_router(assistant.router)
    app.include_router(modules.router)
    app.include_router(billing.router)
    app.include_router(welcome.router)
    app.include_router(welcome.setup_router)
    app.include_router(modules.public_router)
    app.include_router(marketing.router)
    app.include_router(platform.router)
    app.include_router(support.router)
    app.include_router(support.complaints_router)
    app.include_router(client_app.public_router)
    app.include_router(client_app.router)
    app.include_router(checkouts.router)
    app.include_router(receipts.router)
    app.include_router(receipts.client_router)
    app.include_router(attention.router)
    app.include_router(notifications.router)
    app.include_router(health_declarations.router)
    app.include_router(health_declarations.client_router)
    app.include_router(business_settings.router)
    app.include_router(business_settings.public_router)

    return app


app = create_app()
