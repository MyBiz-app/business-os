"""Promo codes the business offers for plans bought in the client app (migration 0035).
Seeing them needs `catalog.read`; creating, pausing and deleting them `catalog.write`."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.permissions import Permission

router = APIRouter(prefix="/promo-codes", tags=["plans"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CATALOG_WRITE))]


class PromoCodeCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{3,20}$")
    percent_off: int | None = Field(default=None, ge=1, le=100)
    amount_off: int | None = Field(default=None, gt=0, description="Minor units")
    plan_id: UUID | None = Field(default=None, description="Only this plan; empty = every plan")
    starts_on: date | None = None
    ends_on: date | None = None
    max_uses: int | None = Field(default=None, gt=0)

    @field_validator("code")
    @classmethod
    def upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def one_discount(self) -> "PromoCodeCreate":
        if (self.percent_off is None) == (self.amount_off is None):
            raise ValueError("give exactly one of percent_off, amount_off")
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("ends_on must not be before starts_on")
        return self


class PromoCodeUpdate(BaseModel):
    active: bool


class PromoCode(BaseModel):
    id: UUID
    code: str
    percent_off: int | None
    amount_off: int | None
    plan_id: UUID | None
    plan_name: str | None
    starts_on: date | None
    ends_on: date | None
    max_uses: int | None
    uses: int = Field(description="Paid checkouts with this code")
    discount_given: int = Field(description="Total discount on those checkouts, minor units")
    active: bool
    created_at: datetime


SELECT = """
    SELECT c.id, c.code, c.percent_off, c.amount_off, c.plan_id, p.name AS plan_name,
           c.starts_on, c.ends_on, c.max_uses, c.active, c.created_at,
           count(k.id) AS uses, coalesce(sum(k.discount), 0) AS discount_given
    FROM app.promo_codes c
    LEFT JOIN app.plans p ON p.id = c.plan_id
    LEFT JOIN app.checkouts k ON k.promo_code_id = c.id AND k.status = 'paid'
"""
GROUP = " GROUP BY c.id, p.name"


@router.get("")
def list_promo_codes(context: ReadDep) -> list[PromoCode]:
    rows = context.session.execute(
        text(f"{SELECT} {GROUP} ORDER BY c.active DESC, c.created_at DESC")
    ).mappings()
    return [PromoCode.model_validate(dict(r)) for r in rows]


def _load(context: TenantContext, code_id: UUID) -> PromoCode:
    row = (
        context.session.execute(text(f"{SELECT} WHERE c.id = :id {GROUP}"), {"id": code_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return PromoCode.model_validate(dict(row))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_promo_code(body: PromoCodeCreate, context: WriteDep) -> PromoCode:
    try:
        with context.session.begin_nested():
            code_id = context.session.execute(
                text("""
                    INSERT INTO app.promo_codes
                        (tenant_id, code, percent_off, amount_off, plan_id, starts_on, ends_on,
                         max_uses)
                    VALUES (:t, :code, :percent_off, :amount_off, :plan_id, :starts_on, :ends_on,
                            :max_uses)
                    RETURNING id
                """),
                {"t": context.tenant_id, **body.model_dump()},
            ).scalar_one()
    except IntegrityError as error:
        detail = "code_taken" if "promo_codes_tenant_id_code_key" in str(error.orig) else None
        if detail is None:
            raise HTTPException(status_code=422, detail="unknown_plan") from error
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from error
    return _load(context, code_id)


@router.patch("/{code_id}")
def update_promo_code(code_id: UUID, body: PromoCodeUpdate, context: WriteDep) -> PromoCode:
    updated = context.session.execute(
        text("UPDATE app.promo_codes SET active = :active WHERE id = :id RETURNING id"),
        {"active": body.active, "id": code_id},
    ).scalar()
    if updated is None:
        raise not_found()
    return _load(context, code_id)


@router.delete("/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo_code(code_id: UUID, context: WriteDep) -> None:
    """Deletes a code nobody used; a used code is paused instead (its history stays)."""
    code = _load(context, code_id)
    if code.uses:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="code_used")
    context.session.execute(text("DELETE FROM app.promo_codes WHERE id = :id"), {"id": code_id})
