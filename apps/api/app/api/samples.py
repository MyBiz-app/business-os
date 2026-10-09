"""A sample business to explore before creating a real one (decision T79): someone who signed
up and has no business yet gets one business of the industry they pick, filled with a month of
fictitious clients, classes or appointments, sales and leads by the demo generator.

The generator writes across the whole schema, so it runs on the API's own connection (not the
request's restricted role). That is why the endpoint is narrow: only for the signed-in person,
only while they have no business, only for an industry in the catalog."""

import random

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import SessionDep, UserDep
from app.api.routes import ensure_profile
from app.catalog.verticals import CATALOG, VERTICAL_PACKS
from app.core.db import EngineDep
from app.messaging.email import load_all_messages
from app.seed import BranchSpec, BusinessSpec, seed

router = APIRouter(prefix="/tenants", tags=["tenants"])

SAMPLE_CLIENTS = 80
SAMPLE_MONTHS = 1


class SampleCreate(BaseModel):
    vertical: str


class SampleCreated(BaseModel):
    tenant_id: str


def _with_services(key: str) -> str:
    """A category without its own starter services uses its first kind that has some."""
    if CATALOG[key].default_services:
        return key
    kinds = [k for k, p in VERTICAL_PACKS.items() if p.parent == key and p.default_services]
    return kinds[0] if kinds else key


def _industry_name(key: str, messages: dict) -> str:
    texts = messages.get("verticals", {})
    pack = CATALOG.get(key)
    while pack is not None:
        name = texts.get(pack.key, {}).get("name")
        if name:
            return name
        pack = CATALOG.get(pack.parent) if pack.parent else None
    return key


@router.post("/sample", status_code=status.HTTP_201_CREATED)
def create_sample(
    body: SampleCreate, user: UserDep, session: SessionDep, engine: EngineDep
) -> SampleCreated:
    if body.vertical not in VERTICAL_PACKS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_vertical"
        )
    ensure_profile(session, user.id, user.email)
    has_business = session.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM app.tenant_members WHERE user_id = app.current_user_id())"
        )
    ).scalar_one()
    if has_business:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="has_business")
    session.commit()  # the profile must exist for the generator's connection

    vertical = _with_services(body.vertical)
    messages = load_all_messages("he")  # the generator's people and notes are in Hebrew
    name = messages["samples"]["businessName"].replace(
        "{industry}", _industry_name(vertical, messages)
    )
    spec = BusinessSpec(
        name=name,
        vertical=vertical,
        color="#4f46e5",
        billing_name=name,
        branches=(BranchSpec(messages["samples"]["branch"], messages["samples"]["address"]),),
        clients=SAMPLE_CLIENTS,
        staff_per_branch=3,
    )
    with engine.begin() as connection:
        tenant_id = seed(connection, user.email, SAMPLE_MONTHS, random.Random(), spec)
    return SampleCreated(tenant_id=str(tenant_id))
