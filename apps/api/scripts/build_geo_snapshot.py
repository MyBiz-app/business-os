"""Rebuilds app/geo/data/il_geo.json.gz from data.gov.il (free, no key). Run once a year:

    uv run python scripts/build_geo_snapshot.py
    uv run python -m app.geo.loader        # loads it into the database it points at

Review the diff of the counts it prints before committing the new file."""

import gzip
import json
from collections import defaultdict
from pathlib import Path

import httpx2

API = "https://data.gov.il/api/3/action/datastore_search"
CITIES = "8f714b6f-c35c-4b40-a0e7-547b675eee0e"
STREETS = "bf185c7f-1a4e-4662-88c5-fa118a244bda"
HEADERS = {"User-Agent": "datagov-external-client"}  # the portal's edge rejects unknown agents
TARGET = Path(__file__).resolve().parents[1] / "app" / "geo" / "data" / "il_geo.json.gz"


def fetch(client: httpx2.Client, resource: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        response = client.get(
            API, params={"resource_id": resource, "limit": 32000, "offset": len(rows)}
        )
        response.raise_for_status()
        page = response.json()["result"]["records"]
        if not page:
            return rows
        rows.extend(page)


def main() -> None:
    with httpx2.Client(headers=HEADERS, timeout=120) as client:
        city_rows = fetch(client, CITIES)
        street_rows = fetch(client, STREETS)
    cities = [
        [
            int(r["city_code"]),
            r["city_name_he"].strip(),
            (r["city_name_en"] or "").strip() or None,
            r["region_code"],
            (r["region_name"] or "").strip() or None,
        ]
        for r in city_rows
    ]
    known = {c[0] for c in cities}
    official: dict[int, dict[int, str]] = defaultdict(dict)
    synonyms: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for r in street_rows:
        city, code, name = int(r["city_code"]), int(r["official_code"]), r["street_name"].strip()
        if city not in known or not name:
            continue
        if str(r["street_name_status"]).strip().startswith("official"):
            official[city][code] = name
        else:
            synonyms[city][code].append(name)
    streets = {
        str(city): [
            [code, name, sorted(set(synonyms[city][code]) - {name})]
            for code, name in sorted(by_code.items())
        ]
        for city, by_code in sorted(official.items())
    }
    data = {
        "source": {
            "cities": f"data.gov.il resource {CITIES}",
            "streets": f"data.gov.il resource {STREETS}",
        },
        "cities": cities,
        "streets": streets,
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    TARGET.write_bytes(gzip.compress(payload, 9))
    print(f"cities {len(cities)}, streets {sum(len(v) for v in streets.values())} -> {TARGET}")


if __name__ == "__main__":
    main()
