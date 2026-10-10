from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator

from app.catalog.verticals import VERTICAL_PACKS

LegalEntityType = Literal[
    "company", "licensed_dealer", "exempt_dealer", "nonprofit", "partnership", "other"
]

Locale = Literal["he", "en"]
Role = Literal["owner", "manager", "staff", "front_desk"]


class Membership(BaseModel):
    tenant_id: UUID
    tenant_name: str
    role: Role


class SupportAccess(BaseModel):
    tenant_id: UUID
    tenant_name: str
    expires_at: datetime


class Me(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    locale: Locale | None
    platform_admin: bool = Field(description="On the MyBiz team (sees the console)")
    phone: str | None = None
    palette: Literal["mybiz", "ocean", "forest"] | None = Field(
        default=None, description="The person's color palette (none: the MyBiz default)"
    )
    avatar_url: str | None = Field(
        default=None, description="Path of the person's own picture on this API, if any"
    )
    memberships: list[Membership]
    support_access: list[SupportAccess] = Field(
        description="Businesses that let MyBiz support in (the MyBiz team only)"
    )


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    vertical: str
    locale: Locale
    time_zone: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    modules: dict[str, int] | None = Field(
        default=None, description="Modules to enable; defaults to the vertical pack's preset"
    )

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
    cancellation_window_minutes: int | None = Field(default=None, ge=0, le=10080)
    booking_requires_plan: bool | None = None
    requires_health_declaration: bool | None = None
    online_sales: bool | None = None
    resource_payment: Literal["app", "venue"] | None = None
    schedule_default_view: Literal["day", "week", "month"] | None = None
    schedule_default_branches: list[UUID] | None = Field(
        default=None,
        max_length=3,
        description="Branches the schedule opens with; an empty list means the branch picked in the menu",
    )
    legal_entity_type: LegalEntityType | None = None
    business_number: str | None = Field(
        default=None, max_length=20, description="Registration number (ח.פ., עוסק מורשה...)"
    )

    @field_validator("business_number", mode="before")
    @classmethod
    def normalize_number(cls, value: object) -> object:
        # People type it with spaces or dashes; an empty field clears it.
        if isinstance(value, str):
            value = value.replace(" ", "").strip()
            return value or None
        return value

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
    cover_url: str | None = Field(
        default=None, description="Path of the workspace cover image on this API (members only)"
    )
    legal_entity_type: LegalEntityType | None = Field(
        default=None, description="Shown only to people who manage the business's settings"
    )
    business_number: str | None = Field(
        default=None, description="Shown only to people who manage the business's settings"
    )
    cancellation_window_minutes: int
    booking_requires_plan: bool = Field(description="Clients need a valid plan to book in the app")
    requires_health_declaration: bool = Field(
        description="Clients need a valid health declaration to book in the app"
    )
    online_sales: bool = Field(description="Clients can buy plans in the app")
    resource_payment: Literal["app", "venue"] = Field(
        default="app",
        description="Reservations of courts and rooms: paid in the app or at the venue",
    )
    schedule_default_view: Literal["day", "week", "month"] = Field(
        default="week", description="The range the schedule opens with"
    )
    schedule_default_branches: list[UUID] = Field(
        default_factory=list,
        description="Branches the schedule opens with side by side; empty: the menu's branch",
    )
    join_code: str = Field(description="Code clients enter or scan to join this business")
    modules: list[str] = Field(description="Enabled modules (features depend on them)")
    permissions: list[str] = Field(description="The current user's effective permissions")
    custom_role_name: str | None
    role: Role | Literal["support", "platform"] = Field(
        description=(
            "'support': MyBiz support, read-only, while the owner's grant lasts. "
            "'platform': MyBiz staff working in the business for its owner (audited)."
        )
    )
