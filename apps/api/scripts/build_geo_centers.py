"""Rebuilds app/geo/data/il_city_centers.json: a map point for each city in the official list.

The government list has no coordinates, so the points come from GeoNames (free, CC BY 4.0,
https://download.geonames.org/export/dump/IL.zip): a city is matched by its Hebrew or English
name. A city GeoNames does not know gets the middle of the cities of its region, marked
`region` so nobody mistakes it for the real centre. Run once a year, after the city snapshot:

    uv run python scripts/build_geo_centers.py
    uv run python -m app.geo.loader        # loads the points into the database it points at

Review the printed counts before committing the new file."""

import difflib
import io
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

import httpx2

from app.geo.snapshot import normalize_search, read_snapshot

GEONAMES = "https://download.geonames.org/export/dump/IL.zip"
TARGET = Path(__file__).resolve().parents[1] / "app" / "geo" / "data" / "il_city_centers.json"
HEBREW = re.compile("[֐-׿]")
BRACKETS = re.compile(r"\s*\([^)]*\)")
FUZZY_CUTOFF = 0.88


def latin_key(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value)
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", plain.lower().replace("-", " ")).strip()


def load_places() -> tuple[dict[str, tuple], dict[str, tuple]]:
    """Name -> (population, latitude, longitude) of the biggest populated place of that name."""
    with httpx2.Client(timeout=120) as client:
        archive = client.get(GEONAMES).raise_for_status().content
    he: dict[str, tuple] = {}
    en: dict[str, tuple] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        lines = io.TextIOWrapper(bundle.open("IL.txt"), encoding="utf-8")
        for line in lines:
            fields = line.split("\t")
            if fields[6] != "P":
                continue
            place = (int(fields[14] or 0), float(fields[4]), float(fields[5]))
            for name in [fields[1], fields[2], *fields[3].split(",")]:
                table, key = (
                    (he, normalize_search(name)) if HEBREW.search(name) else (en, latin_key(name))
                )
                if key and (key not in table or place[0] > table[key][0]):
                    table[key] = place
    return he, en


def main() -> None:
    he, en = load_places()
    cities = read_snapshot()["cities"]
    found: dict[int, list] = {}
    for code, name_he, name_en, _region_code, _region in cities:
        keys_he = [normalize_search(name_he), normalize_search(BRACKETS.sub("", name_he))]
        place = next((he[k] for k in keys_he if k in he), None)
        if place is None and name_en:
            keys_en = [latin_key(name_en), latin_key(BRACKETS.sub("", name_en))]
            place = next((en[k] for k in keys_en if k in en), None)
            if place is None:
                close = difflib.get_close_matches(keys_en[1], list(en), n=1, cutoff=FUZZY_CUTOFF)
                place = en[close[0]] if close else None
        if place is not None:
            found[code] = [round(place[1], 5), round(place[2], 5), "geonames"]
    by_region: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for code, _he, _en, region_code, _region in cities:
        if code in found and region_code is not None:
            by_region[region_code].append((found[code][0], found[code][1]))
    missing = 0
    for code, _he, _en, region_code, _region in cities:
        if code in found:
            continue
        points = by_region.get(region_code) if region_code is not None else None
        if not points:
            missing += 1
            continue
        found[code] = [
            round(sum(p[0] for p in points) / len(points), 5),
            round(sum(p[1] for p in points) / len(points), 5),
            "region",
        ]
    TARGET.write_text(
        json.dumps({str(code): found[code] for code in sorted(found)}, separators=(",", ":")),
        encoding="utf-8",
    )
    exact = sum(1 for row in found.values() if row[2] == "geonames")
    print(
        f"cities {len(cities)}: {exact} from GeoNames, {len(found) - exact} region middle,"
        f" {missing} none"
    )


if __name__ == "__main__":
    main()
