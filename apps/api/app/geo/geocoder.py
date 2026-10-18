"""A branch address → a point on the map, through a free OpenStreetMap service (Nominatim).

One request per saved branch address (never per page load), as the service's usage policy asks.
A failure or an unknown address is never an error for the person saving: the branch just has no
point until the next save (or until someone places the pin by hand)."""

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx2

from app.core.config import get_settings

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"
TIMEOUT = 8.0


@dataclass(frozen=True)
class Point:
    latitude: float
    longitude: float


class Geocoder(Protocol):
    def find(self, *, street: str | None, house_number: str | None, city: str) -> Point | None: ...


class NoGeocoder:
    def find(self, *, street: str | None, house_number: str | None, city: str) -> Point | None:
        return None


class NominatimGeocoder:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def find(self, *, street: str | None, house_number: str | None, city: str) -> Point | None:
        params = {
            "format": "jsonv2",
            "limit": "1",
            "countrycodes": "il",
            "city": city,
            "accept-language": "he",
        }
        if street:
            params["street"] = f"{house_number} {street}" if house_number else street
        try:
            with httpx2.Client(timeout=TIMEOUT, headers={"User-Agent": self.user_agent}) as http:
                response = http.get(NOMINATIM, params=params)
            response.raise_for_status()
            hits = response.json()
        except (httpx2.HTTPError, ValueError) as error:
            log.warning("geocoding failed: %s", type(error).__name__)
            return None
        if not hits:
            return None
        try:
            return Point(float(hits[0]["lat"]), float(hits[0]["lon"]))
        except (KeyError, TypeError, ValueError):
            return None


def get_geocoder() -> Geocoder:
    settings = get_settings()
    if settings.geocoder == "nominatim":
        return NominatimGeocoder(settings.geocoder_user_agent)
    return NoGeocoder()
