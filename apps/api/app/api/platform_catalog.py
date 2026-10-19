"""The catalog and price list, read-only, in the MyBiz console (K5).

One page for the questions "what do we sell, for how much, and which industries are open?". It
only reads what the code already holds (app/commerce/modules.py and the industry catalog); the
prices stay in code. For industries that are not open yet it also counts the site requests that
named them (the "tell me when it opens" button), for team members who may read the inbox."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.platform import PlatformPermission, StaffDep
from app.catalog.verticals import CATALOG
from app.commerce.modules import (
    AI_CREDITS_INCLUDED,
    AI_USERS_INCLUDED,
    CORE_TIERS,
    MODULES,
    PRESETS,
)

router = APIRouter(prefix="/platform", tags=["platform"])


class CatalogModuleRow(BaseModel):
    key: str
    prices: dict[str, int] = Field(description="Monthly (or one-time), minor units, by currency")
    available: bool
    per_unit: bool
    billing: Literal["monthly", "once"]
    group: str | None
    requires_any: list[str]
    requires_all: list[str]
    ai_credits_included: int
    ai_users_included: int


class CatalogTierRow(BaseModel):
    up_to_clients: int | None
    prices: dict[str, int]


class CatalogIndustryRow(BaseModel):
    key: str
    parent: str | None
    status: Literal["live", "beta", "planned"]
    requests: int | None = Field(
        description="Site requests naming it (latest 300); null without the inbox permission"
    )


class PlatformCatalog(BaseModel):
    core: list[CatalogTierRow]
    modules: list[CatalogModuleRow]
    presets: dict[str, list[str]]
    industries: list[CatalogIndustryRow]


@router.get("/catalog")
def platform_catalog(db: StaffDep) -> PlatformCatalog:
    """Every industry, module and price in one read-only view."""
    can_see_requests = db.execute(
        text("SELECT app.platform_can(:p)"), {"p": PlatformPermission.INBOX_MANAGE.value}
    ).scalar_one()
    wanted: dict[str, int] = {}
    if can_see_requests:
        rows = db.execute(text("SELECT vertical FROM app.platform_contact_requests()")).all()
        for (vertical,) in rows:
            if vertical:
                wanted[vertical] = wanted.get(vertical, 0) + 1
    return PlatformCatalog(
        core=[CatalogTierRow(up_to_clients=limit, prices=prices) for limit, prices in CORE_TIERS],
        modules=[
            CatalogModuleRow(
                key=module.key,
                prices=module.prices,
                available=module.available,
                per_unit=module.per_unit,
                billing=module.billing,
                group=module.group,
                requires_any=list(module.requires_any),
                requires_all=list(module.requires_all),
                ai_credits_included=AI_CREDITS_INCLUDED.get(module.key, 0),
                ai_users_included=AI_USERS_INCLUDED.get(module.key, 0),
            )
            for module in MODULES.values()
        ],
        presets={key: list(modules) for key, modules in PRESETS.items()},
        industries=[
            CatalogIndustryRow(
                key=pack.key,
                parent=pack.parent,
                status=pack.status,  # type: ignore[arg-type]
                requests=(wanted.get(pack.key, 0) if can_see_requests else None),
            )
            for pack in CATALOG.values()
        ],
    )
