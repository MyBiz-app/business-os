"""MyBiz Sites (round 7, R24): the business orders a landing page that MyBiz builds.

The owner answers the 8 step brief (saved as a draft after each step), submits it, and follows
the order: briefing, received, building, in review (the business approves or asks for changes),
live. MyBiz works the order from the console board (`/platform/website-orders`). Nothing is
charged before payments (#46): the order records the prices it was offered."""

import json
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import AnonymousSessionDep, TenantContext, require
from app.api.modules import set_modules
from app.catalog.verticals import VERTICAL_PACKS
from app.commerce.modules import PRESETS
from app.core import events
from app.core.audit import record
from app.core.permissions import Permission
from app.files import system_folder_id
from app.websites.brief import Brief, missing_for_submit
from app.websites.pricing import Product, price_for

router = APIRouter(prefix="/website", tags=["website"])
public_router = APIRouter(prefix="/public", tags=["public"])

OwnerDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]

Stage = Literal["briefing", "received", "building", "review", "live"]
# The brief can change until MyBiz starts building.
EDITABLE: tuple[str, ...] = ("briefing", "received")


class Price(BaseModel):
    product: Product
    currency: str
    setup: int = Field(description="One-time, minor units")
    monthly: int = Field(description="Minor units")


class OrderOut(BaseModel):
    id: UUID
    stage: Stage
    product: Product
    brief: Brief
    site_url: str | None
    customer_message: str | None = Field(description="The platform team's note to the business")
    change_request: str | None = Field(description="What the business asked to change")
    setup_price: int | None
    monthly_price: int | None
    currency: str
    submitted_at: datetime | None
    approved_at: datetime | None
    live_at: datetime | None
    updated_at: datetime


class OrderState(BaseModel):
    order: OrderOut | None
    price: Price
    with_system: bool = Field(description="The business also uses the system")
    missing: list[str] = Field(description="Answers the brief still needs before it can be sent")
    files_folder_id: UUID = Field(description="Where the wizard's images are uploaded")
    prefill: Brief = Field(
        description="What MyBiz already knows about the business, to start the brief with"
    )


class BriefSave(BaseModel):
    brief: Brief


class Response(BaseModel):
    action: Literal["approve", "changes"]
    message: str | None = Field(default=None, max_length=2000)


class Visit(BaseModel):
    key: str = Field(min_length=8, max_length=64, pattern=r"^[0-9a-f]+$")
    source: Literal["direct", "search", "social", "other"] = "other"


def _with_system(db: Session) -> bool:
    """A "website only" business (sign-up track, R25a) pays the stand-alone price and cannot
    book through MyBiz until it adds the system."""
    return (
        db.execute(
            text("SELECT product_track FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar_one()
        == "full"
    )


def _price(db: Session, currency: str) -> Price:
    product: Product = "landing_with_system" if _with_system(db) else "landing_only"
    setup, monthly = price_for(product, currency)
    return Price(product=product, currency=currency, setup=setup, monthly=monthly)


def _currency(db: Session) -> str:
    return (
        db.execute(text("SELECT currency FROM app.tenants WHERE id = app.current_tenant_id()"))
        .scalar_one()
        .strip()
    )


COLUMNS = """id, stage, product, brief, site_url, customer_message, change_request, setup_price,
    monthly_price, currency, submitted_at, approved_at, live_at, updated_at"""


def _order(db: Session, *, lock: bool = False) -> dict | None:
    row = (
        db.execute(
            text(f"SELECT {COLUMNS} FROM app.website_orders" + (" FOR UPDATE" if lock else ""))
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _out(row: dict) -> OrderOut:
    return OrderOut.model_validate({**row, "currency": row["currency"].strip()})


def _prefill(db: Session, *, with_system: bool) -> Brief:
    """The brief with everything MyBiz already knows filled in (name, area, branding, services
    and booking from the system, the website address), so the wizard only asks what is missing."""
    business = (
        db.execute(
            text("""
                SELECT locale, primary_color, website_url, address_city,
                       (SELECT count(*) FROM app.services WHERE active) AS services,
                       (SELECT count(*) FROM app.locations WHERE active) AS branches
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    sections = ["hero"]
    if business["services"]:
        sections.append("services")
    if business["address_city"] or business["branches"]:
        sections.append("location")
    if with_system:
        sections.append("booking")
    sections.append("contact")
    brief = Brief(
        goals=["bookings", "leads"] if with_system else ["leads"],
        area=business["address_city"],
        sections=sections,  # type: ignore[arg-type]
        colors_from_brand=True,
        colors=[business["primary_color"]] if business["primary_color"] else [],
        languages=[business["locale"]],
    )
    host = urlparse(business["website_url"] or "").hostname
    if host:
        brief.domain = "have"
        brief.domain_name = host
    return brief


def _state(db: Session, tenant_id: UUID) -> OrderState:
    row = _order(db)
    brief = Brief.model_validate(row["brief"]) if row else Brief()
    with_system = _with_system(db)
    return OrderState(
        order=_out(row) if row else None,
        price=_price(db, _currency(db)),
        with_system=with_system,
        missing=missing_for_submit(brief, with_system=with_system),
        files_folder_id=system_folder_id(db, tenant_id, "website"),
        prefill=_prefill(db, with_system=with_system),
    )


@router.get("/order")
def get_order(context: OwnerDep) -> OrderState:
    """The business's website order (none yet), the price list and what the brief still lacks."""
    return _state(context.session, context.tenant_id)


@router.put("/order")
def save_brief(body: BriefSave, context: OwnerDep) -> OrderState:
    """Saves the brief as a draft; the first save opens the order. Locked once MyBiz builds."""
    db = context.session
    row = _order(db, lock=True)
    if row is not None and row["stage"] not in EDITABLE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="locked")
    brief = json.dumps(body.brief.model_dump(mode="json"))
    if row is None:
        price = _price(db, _currency(db))
        db.execute(
            text("""
                INSERT INTO app.website_orders (tenant_id, product, brief, currency, created_by)
                VALUES (app.current_tenant_id(), :product, CAST(:brief AS jsonb), :currency,
                        app.current_user_id())
            """),
            {"product": price.product, "brief": brief, "currency": price.currency},
        )
    else:
        db.execute(
            text("UPDATE app.website_orders SET brief = CAST(:brief AS jsonb), updated_at = now()"),
            {"brief": brief},
        )
    return _state(db, context.tenant_id)


def _snapshot(db: Session) -> dict:
    """What MyBiz knows about the business when the brief is sent, for the build prompt."""
    business = (
        db.execute(
            text("""
                SELECT name, vertical, locale, currency, primary_color, join_code, time_zone
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    branches = db.execute(
        text("SELECT name, address FROM app.locations WHERE active ORDER BY name LIMIT 30")
    ).mappings()
    services = db.execute(
        text("""
            SELECT name, price_amount, price_currency
            FROM app.services WHERE active ORDER BY name LIMIT 40
        """)
    ).mappings()
    return {
        "business": {**dict(business), "currency": business["currency"].strip()},
        "branches": [dict(row) for row in branches],
        "services": [
            {
                "name": row["name"],
                "price": f"{row['price_amount'] / 100:g}" if row["price_amount"] else None,
                "currency": row["price_currency"].strip(),
            }
            for row in services
        ],
    }


@router.post("/order/submit")
def submit_order(context: OwnerDep) -> OrderState:
    """Sends the brief to MyBiz (the order moves to "received")."""
    db = context.session
    row = _order(db, lock=True)
    if row is None:
        raise HTTPException(status_code=422, detail="brief_incomplete")
    if row["stage"] not in EDITABLE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="locked")
    with_system = _with_system(db)
    if missing_for_submit(Brief.model_validate(row["brief"]), with_system=with_system):
        raise HTTPException(status_code=422, detail="brief_incomplete")
    price = _price(db, _currency(db))
    db.execute(
        text("""
            UPDATE app.website_orders
            SET stage = 'received', product = :product, setup_price = :setup,
                monthly_price = :monthly, snapshot = CAST(:snapshot AS jsonb),
                submitted_at = coalesce(submitted_at, now()), updated_at = now()
        """),
        {
            "product": price.product,
            "setup": price.setup,
            "monthly": price.monthly,
            "snapshot": json.dumps(_snapshot(db)),
        },
    )
    return _state(db, context.tenant_id)


@router.post("/add-system")
def add_system(context: OwnerDep) -> OrderState:
    """A "website only" business adds the system: it gets the modules its kind of business
    starts with (no new sign-up) and from then on pays the with-system price."""
    db = context.session
    track = db.execute(
        text("SELECT product_track, vertical FROM app.tenants WHERE id = app.current_tenant_id()")
    ).one()
    if track.product_track != "website_only":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_has_system")
    preset = dict.fromkeys(PRESETS[VERTICAL_PACKS[track.vertical].default_preset], 1)
    set_modules(db, context.tenant_id, preset)
    db.execute(
        text("UPDATE app.tenants SET product_track = 'full' WHERE id = app.current_tenant_id()")
    )
    events.record(db, "system_added", track="website_only")
    record(
        db,
        "tenant.updated",
        entity_type="tenant",
        entity_id=context.tenant_id,
        fields=["product_track"],
    )
    return _state(db, context.tenant_id)


@router.post("/order/respond")
def respond(body: Response, context: OwnerDep) -> OrderState:
    """The business answers a site that waits for its review: approve it, or ask for changes
    (the order goes back to "building" with the request)."""
    db = context.session
    row = _order(db, lock=True)
    if row is None:
        raise not_found()
    if row["stage"] != "review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_in_review")
    if body.action == "changes":
        if not body.message or not body.message.strip():
            raise HTTPException(status_code=422, detail="message_required")
        db.execute(
            text("""
                UPDATE app.website_orders
                SET stage = 'building', change_request = :message, approved_at = NULL,
                    updated_at = now()
            """),
            {"message": body.message.strip()},
        )
    else:
        db.execute(text("UPDATE app.website_orders SET approved_at = now(), updated_at = now()"))
    return _state(db, context.tenant_id)


@public_router.post("/website-visits", status_code=status.HTTP_202_ACCEPTED)
def count_visit(body: Visit, db: AnonymousSessionDep) -> None:
    """The finished site reports a visit: a count per day and source, nothing personal."""
    db.execute(
        text("SELECT app.website_track_visit(:key, :source)"),
        {"key": body.key, "source": body.source},
    )
