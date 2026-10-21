"""Structured addresses: search the official lists, check a chosen address, compose its text.

An address is a city and a street from the lists, a house number and free details (apartment,
floor, entrance). A street missing from the list can be typed instead (`street_unlisted`): it is
kept as typed and stays visible for review. The text is also saved in the older free-text column,
so everything that still reads that column (reports, messages, documents) keeps working."""

import re
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import blank_to_none
from app.geo.snapshot import normalize_search

ADDRESS_KEYS = ("city_code", "street_code", "house_number", "address_details", "street_unlisted")
MAX_RESULTS = 50


class AddressFields(BaseModel):
    """The fields every form with an address shares."""

    city_code: int | None = Field(default=None, description="A city from /geo/cities")
    street_code: int | None = Field(
        default=None, description="A street of that city, from /geo/cities/{code}/streets"
    )
    house_number: str | None = Field(default=None, max_length=20)
    address_details: str | None = Field(
        default=None, max_length=100, description="Apartment, floor, entrance"
    )
    street_unlisted: str | None = Field(
        default=None, max_length=120, description="A street that is not on the list, as typed"
    )

    @field_validator("house_number", "address_details", "street_unlisted", mode="before")
    @classmethod
    def blank_address_part(cls, value: object) -> object:
        return blank_to_none(value)

    def address_given(self) -> bool:
        """Any address field is part of the request (even to clear it)."""
        return any(key in self.model_fields_set for key in ADDRESS_KEYS)


def _like(query: str) -> str:
    cleaned = normalize_search(query)
    return "%" + cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search_cities(session: Session, query: str, limit: int) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in session.execute(
            text("""
                SELECT code, name_he, name_en, region_name
                FROM app.geo_cities
                WHERE search_text LIKE :pattern
                ORDER BY (search_text LIKE :prefix) DESC, name_he
                LIMIT :limit
            """),
            {
                "pattern": _like(query),
                "prefix": _like(query).removeprefix("%"),
                "limit": min(limit, MAX_RESULTS),
            },
        ).mappings()
    ]


def search_streets(
    session: Session, city_code: int, query: str, limit: int
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in session.execute(
            text("""
                SELECT code, name_he, aliases
                FROM app.geo_streets
                WHERE city_code = :city AND search_text LIKE :pattern
                ORDER BY (search_text LIKE :prefix) DESC, name_he
                LIMIT :limit
            """),
            {
                "city": city_code,
                "pattern": _like(query),
                "prefix": _like(query).removeprefix("%"),
                "limit": min(limit, MAX_RESULTS),
            },
        ).mappings()
    ]


_BRACKETS = re.compile(r"\s*\([^)]*\)")


class CityMatcher:
    """Finds the official city for a name typed in a file (an import): the exact name in Hebrew
    or English, the name without a bracketed note or after the first " - " ("תל אביב" for
    "תל אביב - יפו"), else the only city containing the letters. Unclear is not guessed."""

    def __init__(self, session: Session) -> None:
        self._exact: dict[str, int | None] = {}
        self._search: list[tuple[str, int]] = []
        for code, name_he, name_en, search_text in session.execute(
            text("SELECT code, name_he, name_en, search_text FROM app.geo_cities")
        ):
            keys = {normalize_search(name_he), normalize_search(_BRACKETS.sub("", name_he))}
            keys.add(normalize_search(name_he.split(" - ")[0]))
            if name_en:
                keys.add(normalize_search(name_en))
            for key in keys - {""}:
                # Two cities with the same key: neither is chosen.
                self._exact[key] = code if self._exact.get(key, code) == code else None
            self._search.append((search_text, code))

    def find(self, name: str | None) -> int | None:
        key = normalize_search(name or "")
        if not key:
            return None
        if key in self._exact:
            return self._exact[key]
        if len(key) < 3:
            return None
        hits = {code for search_text, code in self._search if key in search_text}
        return hits.pop() if len(hits) == 1 else None


class Resolved(BaseModel):
    """A checked address: the columns to save and the names it was resolved from."""

    columns: dict[str, Any]
    text: str | None
    city: str | None
    street: str | None


def _refuse(code: str) -> HTTPException:
    return HTTPException(status_code=422, detail=code)


def resolve_address(session: Session, fields: dict[str, Any], *, required: bool) -> Resolved:
    """Checks the address in `fields` against the lists. `required`: a city, a street (listed or
    typed) and a house number must all be there. Raises 422 with a code the screens translate:
    address_incomplete, unknown_city, unknown_street."""
    given = {key: fields.get(key) for key in ADDRESS_KEYS}
    if given["street_code"] is not None:
        given["street_unlisted"] = None  # a listed street wins over typed text
    city_name = street_name = None
    if given["city_code"] is not None:
        city_name = session.execute(
            text("SELECT name_he FROM app.geo_cities WHERE code = :code"),
            {"code": given["city_code"]},
        ).scalar_one_or_none()
        if city_name is None:
            raise _refuse("unknown_city")
    elif given["street_code"] is not None or given["street_unlisted"]:
        raise _refuse("address_incomplete")
    if given["street_code"] is not None:
        street_name = session.execute(
            text("SELECT name_he FROM app.geo_streets WHERE city_code = :city AND code = :code"),
            {"city": given["city_code"], "code": given["street_code"]},
        ).scalar_one_or_none()
        if street_name is None:
            raise _refuse("unknown_street")
    else:
        street_name = given["street_unlisted"]
    if required and not (city_name and street_name and given["house_number"]):
        raise _refuse("address_incomplete")
    if given["house_number"] and not street_name:
        raise _refuse("address_incomplete")
    line = " ".join(p for p in (street_name, given["house_number"]) if p)
    composed = ", ".join(p for p in (line, city_name) if p)
    if composed and given["address_details"]:
        composed += f" ({given['address_details']})"
    return Resolved(columns=given, text=composed or None, city=city_name, street=street_name)
