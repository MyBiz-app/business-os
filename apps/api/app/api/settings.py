"""Business settings and branding."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import text

from app.api.common import not_found, set_clause
from app.api.deps import AnonymousSessionDep, TenantContext, TenantDep, require
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


def israeli_number_valid(number: str) -> bool:
    """The check digit shared by Israeli ID numbers (עוסק מורשה / פטור use the owner's ID) and
    registered bodies (ח.פ., עמותה, שותפות): up to 9 digits, weights 1,2,1,2..., digit sums."""
    if not number.isdigit() or len(number) > 9:
        return False
    total = 0
    for index, digit in enumerate(number.zfill(9)):
        value = int(digit) * (1 + index % 2)
        total += value - 9 if value > 9 else value
    return total % 10 == 0 and int(number) > 0


@router.patch("/tenants/current")
def update_tenant(body: TenantUpdate, context: SettingsDep) -> Tenant:
    # An explicit null clears the brand color and the business identifier; other fields
    # cannot be cleared.
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None or key in ("primary_color", "legal_entity_type", "business_number")
    }
    if changes.get("business_number"):
        currency = (
            changes.get("currency")
            or context.session.execute(
                text("SELECT currency FROM app.tenants WHERE id = app.current_tenant_id()")
            ).scalar_one()
        )
        number = changes["business_number"]
        # Israeli businesses get the check digit; other countries' formats are kept as typed.
        if currency == "ILS" and not israeli_number_valid(number.replace("-", "")):
            raise HTTPException(status_code=422, detail="invalid_business_number")
        if currency == "ILS":
            changes["business_number"] = number.replace("-", "")
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


MAX_COVER_BYTES = 1536 * 1024
IMAGE_RESPONSES = {200: {"content": {"image/png": {}, "image/jpeg": {}, "image/webp": {}}}}


async def read_image(file: UploadFile, limit: int) -> tuple[bytes, str]:
    """An uploaded picture: at most `limit` bytes and a PNG, JPEG or WebP by its content."""
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="image_too_large")
    content_type = _detect_type(data)
    if content_type not in LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_image"
        )
    return data, content_type


def image_response(data: bytes, content_type: str) -> Response:
    """A private picture: its URL carries a version, so browsers may keep it."""
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.put("/tenants/current/cover")
async def upload_cover(file: UploadFile, context: SettingsDep) -> Tenant:
    """The workspace's cover image (the dashboard header), seen by the business's team."""
    data, content_type = await read_image(file, MAX_COVER_BYTES)
    context.session.execute(
        text("""
            UPDATE app.tenants
            SET cover = :cover, cover_content_type = :content_type, cover_updated_at = now(),
                updated_at = now()
            WHERE id = app.current_tenant_id()
        """),
        {"cover": data, "content_type": content_type},
    )
    return load_current_tenant(context.session)


@router.delete("/tenants/current/cover")
def delete_cover(context: SettingsDep) -> Tenant:
    context.session.execute(
        text("""
            UPDATE app.tenants
            SET cover = NULL, cover_content_type = NULL, cover_updated_at = NULL,
                updated_at = now()
            WHERE id = app.current_tenant_id()
        """)
    )
    return load_current_tenant(context.session)


@router.get("/tenants/current/cover", response_class=Response, responses=IMAGE_RESPONSES)
def get_cover(context: TenantDep) -> Response:
    row = context.session.execute(
        text("""
            SELECT cover, cover_content_type FROM app.tenants
            WHERE id = app.current_tenant_id() AND cover IS NOT NULL
        """)
    ).first()
    if row is None:
        raise not_found()
    return image_response(row.cover, row.cover_content_type)


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
