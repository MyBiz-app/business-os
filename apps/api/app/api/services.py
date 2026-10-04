from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from app.api.common import blank_to_none, not_found, set_clause
from app.api.deps import TenantContext, require
from app.permissions import Permission

router = APIRouter(prefix="/services", tags=["services"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]

COLUMNS = (
    "id, name, description, duration_minutes, capacity, booking_mode, price_amount, "
    "price_currency, color, active, created_at, updated_at"
)
COLOR_PATTERN = r"^#[0-9a-fA-F]{6}$"
# class: scheduled sessions people join; appointment: one-to-one at a free time with a staff member.
BookingMode = Literal["class", "appointment"]


class ServiceFields(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern=COLOR_PATTERN)

    @field_validator("description", "color", mode="before")
    @classmethod
    def blank_is_missing(cls, value: object) -> object:
        return blank_to_none(value)


class ServiceCreate(ServiceFields):
    name: str = Field(min_length=1, max_length=120)
    duration_minutes: int = Field(ge=5, le=1440)
    capacity: int = Field(default=1, ge=1, le=1000)
    booking_mode: BookingMode = "class"
    price_amount: int = Field(default=0, ge=0, description="Price in minor units (agorot, cents)")
    price_currency: str | None = Field(
        default=None, pattern=r"^[A-Z]{3}$", description="Defaults to the business currency"
    )
    active: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class ServiceUpdate(ServiceFields):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    booking_mode: BookingMode | None = None
    price_amount: int | None = Field(default=None, ge=0)
    active: bool | None = None


class Service(BaseModel):
    id: UUID
    name: str
    description: str | None
    duration_minutes: int
    capacity: int
    booking_mode: BookingMode
    price_amount: int
    price_currency: str
    color: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


@router.get("")
def list_services(
    context: ReadDep, active: Annotated[bool | None, Query()] = None
) -> list[Service]:
    where, params = (
        ("WHERE active = :active", {"active": active}) if active is not None else ("", {})
    )
    rows = context.session.execute(
        text(f"SELECT {COLUMNS} FROM app.services {where} ORDER BY active DESC, name"), params
    ).mappings()
    return [Service.model_validate(dict(row)) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceCreate, context: WriteDep) -> Service:
    row = (
        context.session.execute(
            text(f"""
                INSERT INTO app.services
                    (tenant_id, name, description, duration_minutes, capacity, booking_mode,
                     price_amount, price_currency, color, active)
                SELECT :tenant_id, :name, :description, :duration_minutes,
                       CASE WHEN :booking_mode = 'appointment' THEN 1 ELSE :capacity END,
                       :booking_mode, :price_amount, coalesce(:price_currency, t.currency),
                       :color, :active
                FROM app.tenants t WHERE t.id = :tenant_id
                RETURNING {COLUMNS}
            """),
            {**body.model_dump(), "tenant_id": context.tenant_id},
        )
        .mappings()
        .one()
    )
    return Service.model_validate(dict(row))


@router.get("/{service_id}")
def get_service(service_id: UUID, context: ReadDep) -> Service:
    row = (
        context.session.execute(
            text(f"SELECT {COLUMNS} FROM app.services WHERE id = :id"), {"id": service_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Service.model_validate(dict(row))


@router.patch("/{service_id}")
def update_service(service_id: UUID, body: ServiceUpdate, context: WriteDep) -> Service:
    # Required columns cannot be cleared; an explicit null for them means "no change".
    required = {"name", "duration_minutes", "capacity", "booking_mode", "price_amount", "active"}
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if not (key in required and value is None)
    }
    row = (
        context.session.execute(
            text(
                f"UPDATE app.services SET {set_clause(changes)} WHERE id = :id RETURNING {COLUMNS}"
            ),
            {**changes, "id": service_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Service.model_validate(dict(row))
