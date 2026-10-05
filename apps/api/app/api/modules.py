"""The configurator: module catalog, recommendations, live quotes and enabling modules."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, TenantDep, UserDep, require
from app.modules import (
    CORE_TIERS,
    MODULES,
    PRESETS,
    ModuleKey,
    PresetKey,
    Questionnaire,
    quote,
    recommend,
    validate,
)
from app.permissions import Permission

router = APIRouter(tags=["modules"])
public_router = APIRouter(tags=["public"])

SettingsDep = Annotated[TenantContext, Depends(require(Permission.BUSINESS_SETTINGS))]
Currency = Annotated[str, Query(pattern=r"^[A-Z]{3}$")]


class CatalogModule(BaseModel):
    key: ModuleKey
    price: int = Field(description="Monthly, minor units (per unit when per_unit)")
    available: bool
    per_unit: bool
    requires_any: list[ModuleKey]
    requires_all: list[ModuleKey]


class CoreTier(BaseModel):
    up_to_clients: int | None
    price: int


class Catalog(BaseModel):
    currency: str
    core: list[CoreTier]
    modules: list[CatalogModule]
    presets: dict[PresetKey, list[ModuleKey]]


class QuestionnaireIn(BaseModel):
    active_clients: int = Field(ge=0, le=100000)
    staff: int = Field(ge=1, le=1000)
    locations: int = Field(ge=1, le=50)
    wants_client_app: bool
    wants_ai_actions: bool


class Recommendation(BaseModel):
    preset: PresetKey
    modules: dict[ModuleKey, int]


class Selection(BaseModel):
    modules: dict[ModuleKey, int]


class QuoteOut(BaseModel):
    currency: str
    core: int
    core_tier: int | None
    lines: dict[ModuleKey, int]
    total: int


class TenantModules(BaseModel):
    modules: dict[ModuleKey, int]
    active_clients: int
    quote: QuoteOut


@router.get("/modules/catalog")
def catalog(_user: UserDep, currency: Currency = "ILS") -> Catalog:
    return build_catalog(currency)


@public_router.get("/public/pricing")
def public_pricing(currency: Currency = "ILS") -> Catalog:
    """The price list for the marketing site (no sign-in)."""
    return build_catalog(currency)


def build_catalog(currency: str) -> Catalog:
    return Catalog(
        currency=currency,
        core=[
            CoreTier(up_to_clients=limit, price=prices.get(currency, prices["USD"]))
            for limit, prices in CORE_TIERS
        ],
        modules=[
            CatalogModule(
                key=m.key,
                price=m.prices.get(currency, m.prices["USD"]),
                available=m.available,
                per_unit=m.per_unit,
                requires_any=list(m.requires_any),
                requires_all=list(m.requires_all),
            )
            for m in MODULES.values()
        ],
        presets={key: list(modules) for key, modules in PRESETS.items()},  # type: ignore[misc]
    )


@router.post("/modules/recommend")
def recommend_modules(body: QuestionnaireIn, _user: UserDep) -> Recommendation:
    preset = recommend(Questionnaire(**body.model_dump()))
    modules = {key: 1 for key in PRESETS[preset]}
    if body.locations > 1:
        modules["extra_location"] = body.locations - 1
    return Recommendation(preset=preset, modules=modules)  # type: ignore[arg-type]


def check_selection(selection: dict[str, int]) -> None:
    error = validate(selection)
    if error:
        raise HTTPException(status_code=422, detail=error)


def _quote_out(selection: dict[str, int], active_clients: int, currency: str) -> QuoteOut:
    result = quote(selection, active_clients, currency)
    return QuoteOut(
        currency=result.currency,
        core=result.core,
        core_tier=result.core_tier,
        lines=result.lines,  # type: ignore[arg-type]
        total=result.total,
    )


@router.post("/modules/quote")
def quote_modules(
    body: Selection,
    _user: UserDep,
    currency: Currency = "ILS",
    active_clients: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> QuoteOut:
    check_selection(body.modules)
    return _quote_out(body.modules, active_clients, currency)


def enabled_modules(db: Session) -> dict[str, int]:
    return dict(
        db.execute(
            text("""
                SELECT module_key, quantity FROM app.tenant_modules
                WHERE tenant_id = app.current_tenant_id()
            """)
        ).all()
    )


def set_modules(db: Session | Connection, tenant_id: object, selection: dict[str, int]) -> None:
    db.execute(text("DELETE FROM app.tenant_modules WHERE tenant_id = :t"), {"t": tenant_id})
    for key, quantity in selection.items():
        db.execute(
            text("""
                INSERT INTO app.tenant_modules (tenant_id, module_key, quantity)
                VALUES (:t, :key, :quantity)
            """),
            {"t": tenant_id, "key": key, "quantity": quantity},
        )


def _tenant_modules(db: Session) -> TenantModules:
    modules = enabled_modules(db)
    row = db.execute(
        text("""
            SELECT t.currency, (
                SELECT count(DISTINCT e.client_id) FROM app.entitlements e
                WHERE e.status = 'active'
                  AND (now() AT TIME ZONE t.time_zone)::date BETWEEN e.starts_on AND e.ends_on
            ) AS active_clients
            FROM app.tenants t WHERE t.id = app.current_tenant_id()
        """)
    ).one()
    return TenantModules(
        modules=modules,  # type: ignore[arg-type]
        active_clients=row.active_clients,
        quote=_quote_out(modules, row.active_clients, row.currency),
    )


@router.get("/tenants/current/modules")
def get_tenant_modules(context: TenantDep) -> TenantModules:
    return _tenant_modules(context.session)


@router.put("/tenants/current/modules")
def put_tenant_modules(body: Selection, context: SettingsDep) -> TenantModules:
    """Replaces the business's modules (billing is simulated in the prototype)."""
    check_selection(body.modules)
    set_modules(context.session, context.tenant_id, body.modules)
    return _tenant_modules(context.session)


@router.post("/tenants/current/modules/{key}")
def add_tenant_module(key: ModuleKey, context: SettingsDep) -> TenantModules:
    """Adds one module to the plan (the "add to plan" button on a locked module). Choosing an AI
    tier replaces the other one; adding a module the plan already has changes nothing."""
    db = context.session
    selection = enabled_modules(db)
    if key not in selection:
        if key in ("ai_basic", "ai_pro"):
            selection.pop("ai_pro" if key == "ai_basic" else "ai_basic", None)
        selection[key] = 1
        check_selection(selection)
        set_modules(db, context.tenant_id, selection)
    return _tenant_modules(db)
