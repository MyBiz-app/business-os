"""Receipts for payments (see migration 0025). Staff see a client's receipts; clients see
their own in the app. While payments are simulated, receipts are samples and say so."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, require
from app.permissions import Permission

router = APIRouter(tags=["receipts"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]


class Receipt(BaseModel):
    id: UUID
    number: int
    issued_at: datetime
    business_name: str
    client_id: UUID
    client_name: str
    client_email: str | None
    description: str
    amount: int = Field(description="Minor units")
    currency: str
    method: Literal["card", "cash", "transfer", "other"]
    simulated: bool = Field(description="A sample from a test payment, not a tax document")


SELECT = """
    SELECT id, number, issued_at, business_name, client_id, client_name, client_email,
           description, amount, currency, method, simulated
    FROM app.receipts
"""


def _one(db: Session, receipt_id: UUID) -> Receipt:
    row = db.execute(text(f"{SELECT} WHERE id = :id"), {"id": receipt_id}).mappings().first()
    if row is None:
        raise not_found()
    return Receipt.model_validate(dict(row))


@router.get("/receipts")
def list_receipts(
    context: ReadDep,
    client_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[Receipt]:
    """Newest first; for one client when `client_id` is given."""
    rows = context.session.execute(
        text(f"""
            {SELECT}
            WHERE CAST(:client_id AS uuid) IS NULL OR client_id = CAST(:client_id AS uuid)
            ORDER BY number DESC LIMIT :limit
        """),
        {"client_id": client_id, "limit": limit},
    ).mappings()
    return [Receipt.model_validate(dict(row)) for row in rows]


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: UUID, context: ReadDep) -> Receipt:
    return _one(context.session, receipt_id)


@client_router.get("/receipts")
def my_receipts(context: ClientDep) -> list[Receipt]:
    rows = context.session.execute(
        text(f"{SELECT} WHERE client_id = :id ORDER BY number DESC LIMIT 100"),
        {"id": context.client_id},
    ).mappings()
    return [Receipt.model_validate(dict(row)) for row in rows]


@client_router.get("/receipts/{receipt_id}")
def my_receipt(receipt_id: UUID, context: ClientDep) -> Receipt:
    receipt = _one(context.session, receipt_id)
    if receipt.client_id != context.client_id:
        raise not_found()
    return receipt
