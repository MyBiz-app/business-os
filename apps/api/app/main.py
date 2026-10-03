from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
    )

    @app.get("/health", tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", environment=settings.environment)

    app.include_router(router)

    return app


app = create_app()
