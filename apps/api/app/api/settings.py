"""Business settings and branding."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found, set_clause
from app.api.deps import AnonymousSessionDep, TenantContext, TenantDep, require
from app.api.routes import load_current_tenant
from app.api.schemas import Tenant, TenantUpdate
from app.catalog.terms import clean_terms_override
from app.core.audit import record
from app.core.identity import check_digit_valid
from app.core.legal_readiness import Readiness, evaluate
from app.core.permissions import Permission
from app.files import check_space
from app.files.scan import ensure_clean
from app.geo.addresses import resolve_address

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
    registered bodies (ח.פ., עמותה, שותפות)."""
    return check_digit_valid(number)


def _legal_address(session: Session, changes: dict) -> dict:
    """The legal address chosen from the official lists (all optional): the structured columns,
    and the older text columns that documents and the readiness card read kept in step."""
    current = (
        session.execute(
            text(
                "SELECT city_code, street_code, house_number, address_details, street_unlisted"
                " FROM app.tenants WHERE id = app.current_tenant_id()"
            )
        )
        .mappings()
        .one()
    )
    resolved = resolve_address(session, {**current, **changes}, required=False)
    line = " ".join(p for p in (resolved.street, resolved.columns["house_number"]) if p)
    if line and resolved.columns["address_details"]:
        line = f"{line} ({resolved.columns['address_details']})"
    return {**resolved.columns, "address_line": line or None, "address_city": resolved.city}


@router.patch("/tenants/current")
def update_tenant(body: TenantUpdate, context: SettingsDep) -> Tenant:
    # An explicit null clears the brand color and the business identifier; other fields
    # cannot be cleared.
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if value is not None
        or key
        in (
            "primary_color",
            "legal_entity_type",
            "business_number",
            "address_line",
            "address_city",
            "city_code",
            "street_code",
            "house_number",
            "address_details",
            "street_unlisted",
            "website_url",
            "employer_file_number",
            "business_license_number",
            "business_license_expires_on",
            "shifts_default_range",
            "weekly_release_weekday",
            "weekly_release_time",
        )
    }
    if "terms_override" in changes:
        try:
            cleaned = clean_terms_override(changes["terms_override"])
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        changes["terms_override"] = json.dumps(cleaned, ensure_ascii=False)
    if body.address_given():
        changes |= _legal_address(context.session, changes)
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
    for key in ("schedule_default_branches", "shifts_default_branches"):
        branches = changes.get(key)
        if not branches:
            continue
        known = context.session.execute(
            text("SELECT count(*) FROM app.locations WHERE id = ANY(:ids)"), {"ids": branches}
        ).scalar_one()
        if known != len(set(branches)):
            raise HTTPException(status_code=422, detail="unknown_branch")
    assignments = set_clause(changes, TenantUpdate.model_fields, casts={"terms_override": "jsonb"})
    context.session.execute(
        text(f"UPDATE app.tenants SET {assignments} WHERE id = app.current_tenant_id()"),
        changes,
    )
    if "cancellation_window_minutes" in changes:
        # The one window set the old way: a saved cancellation policy follows it for every kind.
        context.session.execute(
            text("""
                UPDATE app.cancellation_policies
                SET group_minutes = :minutes, personal_minutes = :minutes,
                    resource_minutes = :minutes, updated_at = now()
                WHERE scope = 'business'
            """),
            {"minutes": changes["cancellation_window_minutes"]},
        )
    # The names of what changed, never the values (an address, a business number).
    record(
        context.session,
        "tenant.updated",
        entity_type="tenant",
        entity_id=context.tenant_id,
        fields=sorted(changes),
    )
    if "require_mfa_for_staff" in changes:
        record(
            context.session,
            "mfa.team_requirement_set",
            entity_type="tenant",
            entity_id=context.tenant_id,
            required=changes["require_mfa_for_staff"],
        )
    return load_current_tenant(context.session)


@router.get("/tenants/current/readiness")
def get_readiness(context: SettingsDep) -> Readiness:
    """The legal-readiness card: what is filled in, what each missing piece would unlock."""
    row = (
        context.session.execute(
            text("""
                SELECT currency, legal_entity_type, business_number, address_line, address_city,
                       employer_file_number, business_license_number,
                       business_license_expires_on,
                       (now() AT TIME ZONE time_zone)::date AS today
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    return evaluate(
        currency=row["currency"],
        entity_type=row["legal_entity_type"],
        business_number=row["business_number"],
        address_line=row["address_line"],
        address_city=row["address_city"],
        employer_file=row["employer_file_number"],
        license_number=row["business_license_number"],
        license_expires_on=row["business_license_expires_on"],
        today=row["today"],
    )


@router.put("/tenants/current/logo")
def upload_logo(file: UploadFile, context: SettingsDep) -> Tenant:
    data = file.file.read(MAX_LOGO_BYTES + 1)
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="logo_too_large")
    content_type = _detect_type(data)
    if content_type not in LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_image"
        )
    ensure_clean(data)
    check_space(context.session, context.tenant_id, len(data))
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


def read_image(
    file: UploadFile, limit: int, context: TenantContext | None = None
) -> tuple[bytes, str]:
    """An uploaded picture: at most `limit` bytes and a PNG, JPEG or WebP by its content. With a
    business `context`, the picture must also fit the business's storage allowance."""
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="image_too_large")
    content_type = _detect_type(data)
    if content_type not in LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_image"
        )
    ensure_clean(data)
    if context is not None:
        check_space(context.session, context.tenant_id, len(data))
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
def upload_cover(file: UploadFile, context: SettingsDep) -> Tenant:
    """The workspace's cover image (the dashboard header), seen by the business's team."""
    data, content_type = read_image(file, MAX_COVER_BYTES, context)
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


def _public_logo(row: Mapping[str, Any] | None) -> Response:
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


@public_router.get("/tenants/{tenant_id}/logo", response_class=Response, responses=IMAGE_RESPONSES)
def get_logo(tenant_id: UUID, session: AnonymousSessionDep) -> Response:
    return _public_logo(
        session.execute(text("SELECT * FROM app.tenant_logo(:id)"), {"id": tenant_id})
        .mappings()
        .first()
    )


@public_router.get(
    "/locations/{location_id}/logo", response_class=Response, responses=IMAGE_RESPONSES
)
def get_location_logo(location_id: UUID, session: AnonymousSessionDep) -> Response:
    return _public_logo(
        session.execute(text("SELECT * FROM app.location_logo(:id)"), {"id": location_id})
        .mappings()
        .first()
    )
