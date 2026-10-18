from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found, set_clause
from app.api.deps import TenantContext, ensure_branch_visible, require
from app.api.settings import MAX_LOGO_BYTES, read_image
from app.catalog.verticals import CATALOG, VerticalPack
from app.commerce.modules import MODULES
from app.core.permissions import Permission
from app.core.website import normalize_website
from app.geo.addresses import AddressFields
from app.geo.branch import CLEARED, branch_address_columns
from app.schedule.branch_managers import appoint, step_down

router = APIRouter(tags=["locations"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]
SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

# A branch shows its own logo and color, else the network's (the business's own).
LOCATION_COLUMNS = """
    l.id, l.name, l.address, l.active, l.created_at, l.updated_at,
    l.kind, l.manager_user_id, t.vertical AS tenant_vertical,
    l.primary_color, l.website_url,
    l.city_code, l.street_code, l.house_number, l.address_details, l.street_unlisted,
    l.latitude, l.longitude,
    (SELECT c.name_he FROM app.geo_cities c WHERE c.code = l.city_code) AS city_name,
    (SELECT st.name_he FROM app.geo_streets st
      WHERE st.city_code = l.city_code AND st.code = l.street_code) AS street_name,
    coalesce(l.website_url, t.website_url) AS effective_website_url,
    CASE WHEN l.logo IS NULL THEN NULL
         ELSE '/public/locations/' || l.id || '/logo?v='
              || extract(epoch FROM l.logo_updated_at)::bigint END AS logo_url,
    coalesce(l.primary_color, t.primary_color) AS effective_primary_color,
    CASE WHEN l.logo IS NOT NULL
              THEN '/public/locations/' || l.id || '/logo?v='
                   || extract(epoch FROM l.logo_updated_at)::bigint
         WHEN t.logo IS NOT NULL
              THEN '/public/tenants/' || t.id || '/logo?v='
                   || extract(epoch FROM t.logo_updated_at)::bigint END AS effective_logo_url
"""
ROOM_COLUMNS = "id, location_id, name, capacity, active, bookable"


def _strip_required(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value.strip()


class LocationCreate(AddressFields):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    kind: str | None = Field(
        default=None,
        max_length=60,
        description="The branch's sub-category (a catalog key); null: as the business",
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)

    website_url: str | None = Field(
        default=None, max_length=300, description="The branch's own website; empty: the business's"
    )

    @field_validator("address", mode="before")
    @classmethod
    def blank_address(cls, value: object) -> object:
        return blank_to_none(value)

    @field_validator("website_url", mode="before")
    @classmethod
    def clean_website(cls, value: object) -> object:
        return normalize_website(value) if isinstance(value, str) else value


class LocationUpdate(AddressFields):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=300)
    active: bool | None = None
    kind: str | None = Field(
        default=None,
        max_length=60,
        description="The branch's sub-category (a catalog key); null: as the business",
    )
    primary_color: str | None = Field(
        default=None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="The branch's own accent color; null falls back to the network's",
    )
    latitude: float | None = Field(
        default=None, ge=-90, le=90, description="The pin, moved by hand (with longitude)"
    )
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def point_is_whole(self) -> "LocationUpdate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("a point needs both latitude and longitude")
        return self

    website_url: str | None = Field(
        default=None, max_length=300, description="The branch's own website; null: the business's"
    )

    @field_validator("address", mode="before")
    @classmethod
    def blank_address(cls, value: object) -> object:
        return blank_to_none(value)

    @field_validator("website_url", mode="before")
    @classmethod
    def clean_website(cls, value: object) -> object:
        return normalize_website(value) if isinstance(value, str) else value


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    bookable: bool | None = Field(
        default=None, description="Reserved by the hour (a court, a room)"
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return _strip_required(value)


class RoomUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    active: bool | None = None
    bookable: bool | None = None


class Room(BaseModel):
    id: UUID
    location_id: UUID
    name: str
    capacity: int | None
    active: bool
    bookable: bool


class Location(BaseModel):
    id: UUID
    name: str
    address: str | None
    city_code: int | None = Field(description="The branch's city, from the official list")
    street_code: int | None
    house_number: str | None
    address_details: str | None
    street_unlisted: str | None = Field(description="A street typed because it is not on the list")
    city_name: str | None
    street_name: str | None
    latitude: float | None = Field(description="The branch's point on the map, if known")
    longitude: float | None
    active: bool
    created_at: datetime
    updated_at: datetime
    rooms: list[Room]
    manager_user_id: UUID | None = Field(
        description="Who manages the branch (the owner until someone is appointed)"
    )
    kind: str | None = Field(description="The branch's own sub-category, if it set one")
    effective_kind: str = Field(description="The branch's kind, else the business's industry")
    schedule_view: str = Field(
        description="class_blocks | appointments | courts: how clients see this branch's schedule"
    )
    social: str = Field(description="on | off | default_off: friends and participant lists")
    primary_color: str | None = Field(description="The branch's own color, if it set one")
    website_url: str | None = Field(description="The branch's own website, if it set one")
    effective_website_url: str | None = Field(
        description="The branch's website, else the business's, else none"
    )
    logo_url: str | None = Field(description="The branch's own logo (public path), if it set one")
    effective_primary_color: str | None = Field(
        description="The branch's color, else the network's"
    )
    effective_logo_url: str | None = Field(
        description="The branch's logo, else the network's logo, else none (show initials)"
    )


def kind_pack(business_vertical: str, kind: str | None) -> VerticalPack:
    """What a branch inherits: its own kind's pack, else the business's."""
    return CATALOG[kind] if kind in CATALOG else CATALOG[business_vertical]


def ensure_branch_kind(session: Session, kind: str | None) -> None:
    """A branch kind must be the business's category or one of its sub-categories."""
    if kind is None:
        return
    vertical = session.execute(
        text("SELECT vertical FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    pack = CATALOG[vertical]
    category = CATALOG[pack.category]
    if kind not in {category.key, pack.key, *category.branch_kinds}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid_branch_kind"
        )


def _load_locations(session: Session, location_id: UUID | None = None) -> list[Location]:
    where, params = ("WHERE l.id = :id", {"id": location_id}) if location_id else ("", {})
    locations = session.execute(
        text(
            f"SELECT {LOCATION_COLUMNS} FROM app.locations l"
            f" JOIN app.tenants t ON t.id = l.tenant_id {where}"
            " ORDER BY l.active DESC, l.created_at, l.name"
        ),
        params,
    ).mappings()
    rooms_by_location: dict[UUID, list[Room]] = {}
    room_where = "WHERE location_id = :id" if location_id else ""
    for row in session.execute(
        text(f"SELECT {ROOM_COLUMNS} FROM app.rooms {room_where} ORDER BY active DESC, name"),
        params,
    ).mappings():
        rooms_by_location.setdefault(row["location_id"], []).append(Room.model_validate(dict(row)))
    result = []
    for row in locations:
        pack = kind_pack(row["tenant_vertical"], row["kind"])
        result.append(
            Location.model_validate(
                {
                    **row,
                    "rooms": rooms_by_location.get(row["id"], []),
                    "effective_kind": pack.key,
                    "schedule_view": pack.schedule_view,
                    "social": pack.social,
                }
            )
        )
    return result


def _one_location(session: Session, location_id: UUID) -> Location:
    found = _load_locations(session, location_id)
    if not found:
        raise not_found()
    return found[0]


@router.get("/locations")
def list_locations(context: ReadDep) -> list[Location]:
    """The business's branches; a member kept to some branches sees only theirs (#64)."""
    locations = _load_locations(context.session)
    if context.branches is None:
        return locations
    return [location for location in locations if location.id in context.branches]


@router.post("/locations", status_code=status.HTTP_201_CREATED)
def create_location(body: LocationCreate, context: WriteDep) -> Location:
    if context.branches is not None:  # new branches are for people who reach every branch
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    ensure_branch_kind(context.session, body.kind)
    location_id = _insert_location(context, body)
    return _one_location(context.session, location_id)


class NewBranchPreview(BaseModel):
    """What adding one more branch costs, shown before the form is filled in."""

    currency: str
    active_branches: int
    extra_branch_price: int = Field(description="Monthly, minor units, per branch beyond the first")
    monthly_extra_now: int = Field(description="Monthly cost of the extra branches today")
    monthly_extra_after: int = Field(
        description="Monthly cost of the extra branches with the new one"
    )
    chargeable: bool = Field(description="The new branch adds a monthly charge")


class BranchSetup(LocationCreate):
    copy_hours_from: UUID | None = Field(
        default=None, description="Start with another branch's opening hours"
    )
    staff_user_ids: list[UUID] = Field(
        default_factory=list, max_length=200, description="Team members who work here too"
    )
    accept_extra_charge: bool = Field(
        default=False, description="Required when the new branch adds a monthly charge"
    )


def _insert_location(context: TenantContext, body: LocationCreate) -> UUID:
    """The branch row. A structured address (city, street, house number) is checked against the
    official lists and its point looked up; a plain `address` text is still accepted."""
    values = {"name": body.name, "kind": body.kind, "website_url": body.website_url}
    if body.address_given():
        values |= branch_address_columns(context.session, body.model_dump(exclude_unset=True))
    else:
        values["address"] = body.address
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    return context.session.execute(
        text(
            f"INSERT INTO app.locations (tenant_id, {columns}) "
            f"VALUES (:tenant_id, {placeholders}) RETURNING id"
        ),
        {**values, "tenant_id": context.tenant_id},
    ).scalar_one()


def _new_branch_preview(session: Session) -> NewBranchPreview:
    currency, active = session.execute(
        text("""
            SELECT t.currency, (SELECT count(*) FROM app.locations WHERE active)
            FROM app.tenants t WHERE t.id = app.current_tenant_id()
        """)
    ).one()
    prices = MODULES["extra_location"].prices
    price = prices.get(currency, prices["USD"])
    now = max(active - 1, 0)
    # The first branch is included; any branch added to a business that has one is extra.
    return NewBranchPreview(
        currency=currency,
        active_branches=active,
        extra_branch_price=price,
        monthly_extra_now=now * price,
        monthly_extra_after=(now + 1) * price if active >= 1 else 0,
        chargeable=active >= 1,
    )


@router.get("/locations/new-branch")
def new_branch_preview(context: SettingsDep) -> NewBranchPreview:
    return _new_branch_preview(context.session)


@router.post("/locations/new-branch", status_code=status.HTTP_201_CREATED)
def add_branch(body: BranchSetup, context: SettingsDep) -> Location:
    """Adds a branch to a running business: its details, opening hours copied from another
    branch, and the team members who work there. When it adds a monthly charge the owner must
    have accepted it; nothing is billed here (the extra-branch module follows the branches)."""
    session = context.session
    ensure_branch_kind(session, body.kind)
    if not (body.city_code and (body.street_code or body.street_unlisted) and body.house_number):
        raise HTTPException(status_code=422, detail="address_incomplete")  # a branch needs one
    if _new_branch_preview(session).chargeable and not body.accept_extra_charge:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="charge_not_accepted")
    if (
        body.copy_hours_from is not None
        and not session.execute(
            text("SELECT EXISTS (SELECT 1 FROM app.locations WHERE id = :id)"),
            {"id": body.copy_hours_from},
        ).scalar_one()
    ):
        raise HTTPException(status_code=422, detail="unknown_branch")
    staff = sorted(set(body.staff_user_ids))
    known = session.execute(
        text("""
            SELECT count(*) FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = ANY(CAST(:ids AS uuid[]))
        """),
        {"ids": [str(i) for i in staff]},
    ).scalar_one()
    if known != len(staff):
        raise HTTPException(status_code=422, detail="unknown_member")
    location_id = _insert_location(context, body)
    if body.copy_hours_from is not None:
        session.execute(
            text("""
                INSERT INTO app.location_hours (tenant_id, location_id, weekday, opens, closes)
                SELECT tenant_id, :new, weekday, opens, closes
                FROM app.location_hours WHERE location_id = :source
            """),
            {"new": location_id, "source": body.copy_hours_from},
        )
    if staff:
        # A member with no branches works everywhere already, so only narrowed ones change.
        session.execute(
            text("""
                UPDATE app.tenant_members SET location_ids = location_ids || :new
                WHERE tenant_id = app.current_tenant_id() AND user_id = ANY(CAST(:ids AS uuid[]))
                  AND cardinality(location_ids) > 0
            """),
            {"new": [location_id], "ids": [str(i) for i in staff]},
        )
    return _one_location(session, location_id)


@router.get("/locations/{location_id}")
def get_location(location_id: UUID, context: ReadDep) -> Location:
    return _one_location(context.session, location_id)


@router.patch("/locations/{location_id}")
def update_location(location_id: UUID, body: LocationUpdate, context: WriteDep) -> Location:
    ensure_branch_visible(context, location_id)
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if not (key in {"name", "active"} and value is None)
    }
    ensure_branch_kind(context.session, changes.get("kind"))
    if body.address_given() or "latitude" in changes:
        current = (
            context.session.execute(
                text("""
                    SELECT address, city_code, street_code, house_number, address_details,
                           street_unlisted
                    FROM app.locations WHERE id = :id
                """),
                {"id": location_id},
            )
            .mappings()
            .first()
        )
        if current is None:
            raise not_found()
        if body.address_given():
            changes |= branch_address_columns(context.session, changes, dict(current))
        else:  # only the pin moved
            changes |= {"geocoded_at": None}
    elif "address" in changes:  # plain text replaces a structured address and its point
        changes |= {**CLEARED, "address": changes["address"]}
    if changes.get("active") is False:
        # A business always keeps at least one active branch.
        others = context.session.execute(
            text("SELECT count(*) FROM app.locations WHERE active AND id <> :id"),
            {"id": location_id},
        ).scalar_one()
        if others == 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="last_branch")
    if "primary_color" in changes and Permission.BUSINESS_SETTINGS not in context.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    assignments = set_clause(changes, {*LocationUpdate.model_fields, "geocoded_at"})
    updated = context.session.execute(
        text(f"UPDATE app.locations SET {assignments} WHERE id = :id RETURNING id"),
        {**changes, "id": location_id},
    ).first()
    if updated is None:
        raise not_found()
    return _one_location(context.session, location_id)


@router.post("/locations/{location_id}/rooms", status_code=status.HTTP_201_CREATED)
def create_room(location_id: UUID, body: RoomCreate, context: WriteDep) -> Room:
    ensure_branch_visible(context, location_id)
    # The location must be visible to this tenant (RLS); otherwise it does not exist for us.
    row = (
        context.session.execute(
            text(f"""
                INSERT INTO app.rooms (tenant_id, location_id, name, capacity, bookable)
                SELECT l.tenant_id, l.id, :name, :capacity, coalesce(:bookable, false)
                FROM app.locations l WHERE l.id = :id
                RETURNING {ROOM_COLUMNS}
            """),
            {**body.model_dump(), "id": location_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Room.model_validate(dict(row))


@router.patch("/rooms/{room_id}")
def update_room(room_id: UUID, body: RoomUpdate, context: WriteDep) -> Room:
    changes = {
        key: value
        for key, value in body.model_dump(exclude_unset=True).items()
        if not (key in {"name", "active", "bookable"} and value is None)
    }
    if context.branches is not None:
        ensure_branch_visible(
            context,
            context.session.execute(
                text("SELECT location_id FROM app.rooms WHERE id = :id"), {"id": room_id}
            ).scalar(),
        )
    assignments = set_clause(changes, RoomUpdate.model_fields)
    sql = f"UPDATE app.rooms SET {assignments} WHERE id = :id RETURNING {ROOM_COLUMNS}"
    row = (
        context.session.execute(
            text(sql),
            {**changes, "id": room_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return Room.model_validate(dict(row))


@router.put("/locations/{location_id}/logo")
def upload_location_logo(location_id: UUID, file: UploadFile, context: SettingsDep) -> Location:
    data, content_type = read_image(file, MAX_LOGO_BYTES, context)
    updated = context.session.execute(
        text("""
            UPDATE app.locations
            SET logo = :logo, logo_content_type = :content_type, logo_updated_at = now(),
                updated_at = now()
            WHERE id = :id RETURNING id
        """),
        {"logo": data, "content_type": content_type, "id": location_id},
    ).first()
    if updated is None:
        raise not_found()
    return _one_location(context.session, location_id)


@router.delete("/locations/{location_id}/logo")
def delete_location_logo(location_id: UUID, context: SettingsDep) -> Location:
    updated = context.session.execute(
        text("""
            UPDATE app.locations
            SET logo = NULL, logo_content_type = NULL, logo_updated_at = NULL, updated_at = now()
            WHERE id = :id RETURNING id
        """),
        {"id": location_id},
    ).first()
    if updated is None:
        raise not_found()
    return _one_location(context.session, location_id)


class BranchManager(BaseModel):
    user_id: UUID = Field(description="The team member who will manage the branch")


@router.put("/locations/{location_id}/manager")
def appoint_branch_manager(
    location_id: UUID, body: BranchManager, context: SettingsDep
) -> Location:
    """Appoints a team member as the branch's manager. Staff become branch managers: manager
    rights at the branches they manage only. The previous manager steps down."""
    ensure_branch_visible(context, location_id)
    _one_location(context.session, location_id)
    try:
        appoint(context.session, location_id, body.user_id)
    except LookupError:
        raise HTTPException(status_code=422, detail="invalid_reference") from None
    return _one_location(context.session, location_id)


@router.delete("/locations/{location_id}/manager")
def remove_branch_manager(location_id: UUID, context: SettingsDep) -> Location:
    """The branch has no appointed manager (its owner still reaches it)."""
    ensure_branch_visible(context, location_id)
    _one_location(context.session, location_id)
    step_down(context.session, location_id)
    return _one_location(context.session, location_id)
