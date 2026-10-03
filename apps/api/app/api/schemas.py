from typing import Literal
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator

from app.verticals import VERTICAL_PACKS

Locale = Literal["he", "en"]
Role = Literal["owner", "manager", "staff", "front_desk"]


class Membership(BaseModel):
    tenant_id: UUID
    tenant_name: str
    role: Role


class Me(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    locale: Locale | None
    memberships: list[Membership]


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    vertical: str
    locale: Locale
    time_zone: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("vertical")
    @classmethod
    def known_vertical(cls, value: str) -> str:
        if value not in VERTICAL_PACKS:
            raise ValueError("unknown vertical")
        return value

    @field_validator("time_zone")
    @classmethod
    def known_time_zone(cls, value: str) -> str:
        if value not in available_timezones():
            raise ValueError("unknown time zone")
        return value


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    locale: Locale | None = None
    time_zone: str | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name must not be blank")
        return value.strip() if value else value

    @field_validator("time_zone")
    @classmethod
    def known_time_zone(cls, value: str | None) -> str | None:
        if value is not None and value not in available_timezones():
            raise ValueError("unknown time zone")
        return value


class Tenant(BaseModel):
    id: UUID
    name: str
    vertical: str
    locale: Locale
    time_zone: str
    currency: str
    primary_color: str | None
    logo_url: str | None = Field(description="Public path of the logo on this API, if any")
    role: Role
