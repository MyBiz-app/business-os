"""The official city and street lists, kept as a compressed snapshot inside the code.

Source: data.gov.il (Population and Immigration Authority), free open data, resources
`8f714b6f-c35c-4b40-a0e7-547b675eee0e` (localities) and `bf185c7f-1a4e-4662-88c5-fa118a244bda`
(streets with synonyms). `scripts/build_geo_snapshot.py` rebuilds the file once a year; a
migration (and `load_snapshot`) loads it into the shared, read-only tables `geo_cities` and
`geo_streets`."""

import gzip
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "data" / "il_geo.json.gz"

_QUOTES = re.compile("[\"'`\u05f3\u05f4\u2018\u2019\u201c\u201d]")  # quotes, geresh, gershayim
_JOINERS = re.compile("[-\u05be\u2010-\u2015_]")  # hyphens and maqaf
_SPACES = re.compile(r"\s+")


def normalize_search(value: str) -> str:
    """The form names are searched in: no quotes or geresh (ג'ת = גת), hyphens as spaces,
    single spaces, lower case. Applied to the stored names and to what people type."""
    value = _JOINERS.sub(" ", _QUOTES.sub("", value))
    return _SPACES.sub(" ", value).strip().lower()


@dataclass(frozen=True)
class CityRow:
    code: int
    name_he: str
    name_en: str | None
    region_code: int | None
    region_name: str | None

    @property
    def search_text(self) -> str:
        return normalize_search(" ".join(p for p in (self.name_he, self.name_en) if p))


@dataclass(frozen=True)
class StreetRow:
    city_code: int
    code: int
    name_he: str
    aliases: list[str]

    @property
    def search_text(self) -> str:
        return normalize_search(" ".join([self.name_he, *self.aliases]))


def read_snapshot(path: Path = SNAPSHOT) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def cities(data: dict) -> Iterator[CityRow]:
    for code, name_he, name_en, region_code, region_name in data["cities"]:
        yield CityRow(code, name_he, name_en or None, region_code, region_name)


def streets(data: dict) -> Iterator[StreetRow]:
    for city_code, rows in data["streets"].items():
        for code, name_he, aliases in rows:
            yield StreetRow(int(city_code), code, name_he, list(aliases))
