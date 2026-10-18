"""A branch's address as saved: the checked structured address, its text and its map point."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.geo.addresses import ADDRESS_KEYS, resolve_address
from app.geo.geocoder import get_geocoder

log = logging.getLogger(__name__)
CLEARED = {
    **dict.fromkeys(ADDRESS_KEYS),
    "address": None,
    "latitude": None,
    "longitude": None,
    "geocoded_at": None,
}


def _point(resolved_street: str | None, house: str | None, city: str) -> tuple[float, float] | None:
    try:
        found = get_geocoder().find(street=resolved_street, house_number=house, city=city)
    except Exception:  # the map service must never stop a branch from being saved
        log.exception("geocoder crashed")
        return None
    return (found.latitude, found.longitude) if found else None


def branch_address_columns(
    session: Session, fields: dict[str, Any], current: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The columns to write when the request carries a structured address (city, street, house
    number, details) and/or a hand-placed point. The address is checked as a whole (every
    part, merged with what the branch already has), its text is composed, and the point is looked
    up once, only when the address changed."""
    current = current or {}
    merged = {key: current.get(key) for key in ADDRESS_KEYS}
    merged.update({key: fields[key] for key in ADDRESS_KEYS if key in fields})
    if not any(merged.values()):
        return dict(CLEARED)
    resolved = resolve_address(session, merged, required=True)
    columns: dict[str, Any] = {**resolved.columns, "address": resolved.text}
    placed = fields.get("latitude") is not None and fields.get("longitude") is not None
    changed = resolved.text != current.get("address") or any(
        merged[key] != current.get(key) for key in ADDRESS_KEYS
    )
    if placed:
        columns |= {"latitude": fields["latitude"], "longitude": fields["longitude"]}
        columns["geocoded_at"] = None  # set by hand, not looked up
    elif changed:
        point = _point(resolved.street, merged["house_number"], resolved.city or "")
        columns |= {
            "latitude": point[0] if point else None,
            "longitude": point[1] if point else None,
            "geocoded_at": datetime.now(UTC) if point else None,
        }
    return columns
