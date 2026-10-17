import datetime as dt
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator, model_validator

from app.catalog.verticals import VERTICAL_PACKS

LegalEntityType = Literal[
    "company", "licensed_dealer", "exempt_dealer", "nonprofit", "partnership", "other"
]

Locale = Literal["he", "en"]
Role = Literal["owner", "manager", "branch_manager", "staff", "front_desk"]


class Membership(BaseModel):
    tenant_id: UUID
    tenant_name: str
    role: Role


class SupportAccess(BaseModel):
    tenant_id: UUID
    tenant_name: str
    expires_at: datetime


Palette = Literal["mybiz", "ocean", "forest", "custom"]


class PaletteColors(BaseModel):
    """The three colors a person picks for "my own colors" (`#rrggbb`). The app derives every
    other color from them, so any combination is safe to store."""

    background: str = Field(pattern=r"^#[0-9a-f]{6}$")
    text: str = Field(pattern=r"^#[0-9a-f]{6}$")
    accent: str = Field(pattern=r"^#[0-9a-f]{6}$")


class Me(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    locale: Locale | None
    platform_admin: bool = Field(description="On the MyBiz team (sees the console)")
    phone: str | None = None
    birth_date: date | None = None
    address_line: str | None = None
    city: str | None = None
    postal_code: str | None = None
    email_roster: bool = Field(
        default=True, description="Email the person when their roster is published"
    )
    marketing_consent: bool = Field(
        default=False, description="Agreed to marketing messages (service messages are sent anyway)"
    )
    palette: Palette | None = Field(
        default=None, description="The person's color palette (none: the MyBiz default)"
    )
    palette_colors: PaletteColors | None = Field(
        default=None,
        description="The colors picked for the `custom` palette, kept when a preset is chosen",
    )
    avatar_url: str | None = Field(
        default=None, description="Path of the person's own picture on this API, if any"
    )
    status_text: str | None = Field(
        default=None, description="A short free-text status shown on the profile (up to 80)"
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
    booking_horizon_days: int | None = Field(default=None, ge=1, le=60)
    weekly_release_weekday: int | None = Field(default=None, ge=0, le=6)
    weekly_release_time: dt.time | None = None
    booking_requires_plan: bool | None = None
    requires_health_declaration: bool | None = None
    online_sales: bool | None = None
    require_mfa_for_staff: bool | None = None
    resource_payment: Literal["app", "venue"] | None = None
    schedule_default_view: Literal["day", "week", "month"] | None = None
    schedule_default_branches: list[UUID] | None = Field(
        default=None,
        max_length=3,
        description="Branches the schedule opens with; empty means the menu's branch",
    )
    shifts_default_view: Literal["people", "branches"] | None = None
    shifts_default_range: Literal["day", "week", "month", "custom"] | None = None
    shifts_default_branches: list[UUID] | None = Field(
        default=None,
        max_length=3,
        description="Branches the shifts board opens with; empty means all of them",
    )
    network_scope: Literal["network", "branch"] | None = None
    client_id_number: Literal["off", "optional", "required"] | None = None
    shifts_publish_auto: bool | None = None
    shifts_publish_cadence: Literal["daily", "weekly", "monthly"] | None = None
    shifts_publish_weekday: int | None = Field(default=None, ge=0, le=6)
    shifts_publish_day: int | None = Field(default=None, ge=1, le=28)
    shifts_publish_time: dt.time | None = None
    legal_entity_type: LegalEntityType | None = None
    business_number: str | None = Field(
        default=None, max_length=20, description="Registration number (ח.פ., עוסק מורשה...)"
    )
    address_line: str | None = Field(default=None, max_length=200)
    address_city: str | None = Field(default=None, max_length=100)
    employer_file_number: str | None = Field(
        default=None, pattern=r"^[0-9A-Za-z/-]{2,20}$", description="Deductions file (תיק ניכויים)"
    )
    business_license_number: str | None = Field(default=None, max_length=40)
    business_license_expires_on: dt.date | None = None

    @model_validator(mode="after")
    def release_is_complete(self) -> "TenantUpdate":
        # The weekly release is a weekday and a time together; both null switches it off.
        if (self.weekly_release_weekday is None) != (self.weekly_release_time is None):
            raise ValueError("the weekly release needs both a weekday and a time (or neither)")
        return self

    @field_validator("address_line", "address_city", "business_license_number", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("business_number", "employer_file_number", mode="before")
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
    address_line: str | None = Field(default=None, description="Settings managers only")
    address_city: str | None = Field(default=None, description="Settings managers only")
    employer_file_number: str | None = Field(default=None, description="Settings managers only")
    business_license_number: str | None = Field(default=None, description="Settings managers only")
    business_license_expires_on: dt.date | None = Field(
        default=None, description="Settings managers only"
    )
    cancellation_window_minutes: int
    booking_horizon_days: int = Field(
        default=7, description="Without a weekly release: how many days ahead classes open"
    )
    weekly_release_weekday: int | None = Field(
        default=None, description="Weekly release: 0 = Monday, 6 = Sunday; none: rolling horizon"
    )
    weekly_release_time: dt.time | None = Field(
        default=None, description="Weekly release: local time the next week opens"
    )
    booking_requires_plan: bool = Field(description="Clients need a valid plan to book in the app")
    requires_health_declaration: bool = Field(
        description="Clients need a valid health declaration to book in the app"
    )
    online_sales: bool = Field(description="Clients can buy plans in the app")
    require_mfa_for_staff: bool = Field(
        default=False, description="Every team member must sign in with an authenticator code"
    )
    network_scope: Literal["network", "branch"] = Field(
        default="network",
        description="network: clients shared by all branches; branch: each branch keeps its own",
    )
    client_id_number: Literal["off", "optional", "required"] = Field(
        default="off", description="Whether the business asks its clients for an ID number"
    )
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
    shifts_default_view: Literal["people", "branches"] = Field(
        default="people", description="How the shifts board opens: a row per person or per branch"
    )
    shifts_default_range: Literal["day", "week", "month", "custom"] | None = Field(
        default=None, description="The range the shifts board opens with; none: the planning rhythm"
    )
    shifts_default_branches: list[UUID] = Field(
        default_factory=list,
        description="Branches the shifts board opens with; empty: all of them",
    )
    shifts_publish_auto: bool = Field(
        default=True, description="Publish the shifts roster on schedule"
    )
    shifts_publish_cadence: Literal["daily", "weekly", "monthly"] = "weekly"
    shifts_publish_weekday: int = Field(default=6, description="Weekly: 0 = Monday, 6 = Sunday")
    shifts_publish_day: int = Field(default=1, description="Monthly: day of the month, 1-28")
    shifts_publish_time: dt.time = Field(
        default=dt.time(8), description="Local time the roster goes out"
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
