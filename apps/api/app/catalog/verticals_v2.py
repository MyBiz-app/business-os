"""Catalog v2: domains, resource types and business types (spec: categories and service model).

The source is packages/verticals/catalog-v2/*.json; `pnpm verticals:export` copies it to
app/verticals_catalog_v2.json because the API's image is built from apps/api alone. It sits next to
the v1 catalog (app/catalog/verticals.py) and nothing reads it yet: the next slice (C2) fills
a business's activities and resources from it.
"""

import json
from pathlib import Path
from typing import Any

CATALOG_V2_PATH = Path(__file__).resolve().parent.parent / "verticals_catalog_v2.json"

# The eight service models and whether the booking engine already runs each one.
SERVICE_MODELS: dict[str, str] = {
    "appointment": "existing",
    "group_class": "existing",
    "large_group": "partial",
    "resource_rental": "existing",
    "resource_staff": "new",
    "open_entry": "partial",
    "on_site": "existing",
    "project": "existing",
}

Entry = dict[str, Any]


def load_catalog_v2(path: Path = CATALOG_V2_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


_RAW = load_catalog_v2()
DOMAINS: dict[str, Entry] = {d["key"]: d for d in _RAW["domains"]}
RESOURCE_TYPES: dict[str, Entry] = {r["key"]: r for r in _RAW["resource_types"]}
BUSINESS_TYPES: dict[str, Entry] = {t["key"]: t for t in _RAW["business_types"]}


def default_activities(key: str) -> list[Entry]:
    """What a new business of this type starts with: everything not optional or coming soon."""
    return [
        a
        for a in BUSINESS_TYPES[key]["activities"]
        if not a.get("optional") and not a.get("coming_soon")
    ]


def successors_of(legacy_key: str) -> list[Entry]:
    """The business types that take over a v1 key (a category or sub-category)."""
    taken = [t for t in BUSINESS_TYPES.values() if legacy_key in t.get("replaces", ())]
    if taken:
        return taken
    same = BUSINESS_TYPES.get(legacy_key)
    return [same] if same else []
