"""The official Israeli cities and streets, for the address picker (R34). Reference data, the
same for every business; any signed-in person may search it."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import AnonymousSessionDep, SessionDep, UserDep
from app.geo.addresses import search_cities, search_streets

router = APIRouter(prefix="/geo", tags=["geo"])
public_router = APIRouter(prefix="/public/geo", tags=["geo"])


class City(BaseModel):
    code: int
    name_he: str
    name_en: str | None
    region_name: str | None


class Street(BaseModel):
    code: int
    name_he: str
    aliases: list[str]


class CoverageCity(BaseModel):
    name_he: str
    name_en: str | None
    latitude: float
    longitude: float
    businesses: int


class Coverage(BaseModel):
    cities: list[CoverageCity] = Field(description="Only cities with at least five businesses")
    businesses: int = Field(description="Businesses in those cities")


QueryParam = Annotated[str, Query(max_length=60, description="Letters from the name; empty: all")]
LimitParam = Annotated[int, Query(ge=1, le=50)]


@router.get("/cities")
def list_cities(
    _user: UserDep, session: SessionDep, q: QueryParam = "", limit: LimitParam = 20
) -> list[City]:
    """Cities and towns whose name contains the letters, names starting with them first."""
    return [City(**row) for row in search_cities(session, q, limit)]


@router.get("/cities/{city_code}/streets")
def list_streets(
    city_code: int, _user: UserDep, session: SessionDep, q: QueryParam = "", limit: LimitParam = 20
) -> list[Street]:
    """Streets of one city whose name (or an alternative spelling) contains the letters."""
    return [Street(**row) for row in search_streets(session, city_code, q, limit)]


@public_router.get("/cities")
def list_cities_public(
    session: AnonymousSessionDep, q: QueryParam = "", limit: LimitParam = 12
) -> list[City]:
    """The same city list for a form anyone can open (a business's inquiry form)."""
    return [City(**row) for row in search_cities(session, q, limit)]


@public_router.get("/coverage")
def coverage(session: AnonymousSessionDep) -> Coverage:
    """Where MyBiz businesses are, for the landing page: city names and counts only. A city
    with fewer than five businesses is not listed (the database enforces it); no one is named."""
    rows = session.execute(text("SELECT * FROM app.public_coverage()")).mappings()
    cities = [
        CoverageCity(
            name_he=r["city_name"],
            name_en=r["city_name_en"],
            latitude=r["latitude"],
            longitude=r["longitude"],
            businesses=r["businesses"],
        )
        for r in rows
    ]
    return Coverage(cities=cities, businesses=sum(c.businesses for c in cities))
