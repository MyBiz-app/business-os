"""Business settings and branding."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import text

from app.api.common import not_found, set_clause
from app.api.deps import AnonymousSessionDep, TenantContext, require
from app.api.routes import load_current_tenant
from app.api.schemas import Tenant, TenantUpdate
from app.core.permissions import Permission

router = APIRouter(tags=["settings"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

LOGO_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_LOGO_BYTES = 512 * 1024
# Magic numbers: trust the file's content, not the type the browser claims.
SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),
}


def _detect_type(data: bytes) -> str | None:
    for content_type, prefixes in SIGNATURES.items():
        if any(data.startswith(prefix) for prefix in prefixes):
            if content_type == "image/webp" and data[8:12] != b"WEBP":
                continue
            return content_type
    return None


@router.patch("/tenants/current")
def update_tenant(body: TenantUpdate, context: SettingsDep) -> Tenant:
    # An explicit null clears the brand color; other fields cannot be cleared.
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None or key == "primary_color"
    }
    context.session.execute(
        text(f"UPDATE app.tenants SET {set_clause(changes)} WHERE id = app.current_tenant_id()"),
        changes,
    )
    return load_current_tenant(context.session)


@router.put("/tenants/current/logo")
async def upload_logo(file: UploadFile, context: SettingsDep) -> Tenant:
    data = await file.read(MAX_LOGO_BYTES + 1)
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="logo_too_large")
    content_type = _detect_type(data)
    if content_type not in LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_image"
        )
    context.session.execute(
        text("""
            UPDATE app.tenants
            SET logo = :logo, logo_content_type = :content_type, logo_updated_at = now(),
                updated_at = now()
            WHERE id = app.current_tenant_id()
        """),
        {"logo": data, "content_type": content_type},
    )
    return load_current_tenant(context.session)


@router.delete("/tenants/current/logo")
def delete_logo(context: SettingsDep) -> Tenant:
    context.session.execute(
        text("""
            UPDATE app.tenants
            SET logo = NULL, logo_content_type = NULL, logo_updated_at = NULL, updated_at = now()
            WHERE id = app.current_tenant_id()
        """)
    )
    return load_current_tenant(context.session)


public_router = APIRouter(prefix="/public", tags=["public"])


@public_router.get(
    "/tenants/{tenant_id}/logo",
    response_class=Response,
    responses={200: {"content": {"image/png": {}, "image/jpeg": {}, "image/webp": {}}}},
)
def get_logo(tenant_id: UUID, session: AnonymousSessionDep) -> Response:
    row = (
        session.execute(text("SELECT * FROM app.tenant_logo(:id)"), {"id": tenant_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    # URLs carry ?v=<updated_at>, so a logo URL never changes content and can be cached long.
    expires = datetime.now(UTC) + timedelta(days=365)
    return Response(
        content=bytes(row["logo"]),
        media_type=row["content_type"],
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Expires": expires.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "X-Content-Type-Options": "nosniff",
        },
    )
