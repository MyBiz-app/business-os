from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules import PRESETS
from app.verticals import CATALOG, VERTICAL_PACKS
from tests.conftest import AuthHeaders


def test_sub_categories_inherit_from_their_category() -> None:
    pilates, fitness = CATALOG["pilates"], CATALOG["fitness"]
    assert (pilates.parent, pilates.category, pilates.terms) == ("fitness", "fitness", "fitness")
    assert pilates.health_form == "fitness" and pilates.requires_health_declaration
    assert pilates.client_fields == fitness.client_fields
    assert pilates.default_plans == fitness.default_plans
    assert pilates.default_services != fitness.default_services  # its own classes

    garage, automotive = CATALOG["garage"], CATALOG["automotive"]
    assert garage.category == "automotive" and garage.terms == "automotive"
    assert garage.default_services == automotive.default_services

    # extra fields are added to the inherited ones; client_fields replaces them
    assert [f.key for f in CATALOG["physiotherapy"].client_fields][-1] == "injury"
    assert [f.key for f in CATALOG["nails"].client_fields] == ["allergies", "preferences"]


def test_prices_cover_every_currency() -> None:
    service = CATALOG["barbershop"].default_services[0]
    assert set(service.prices) == {"ILS", "USD", "EUR"}
    assert service.prices["ILS"] == 8000 and 0 < service.prices["EUR"] < service.prices["USD"]


def test_planned_categories_are_listed_but_closed() -> None:
    assert "pets" in CATALOG and "pets" not in VERTICAL_PACKS
    assert {"fitness", "beauty", "clinic", "classes", "automotive"} <= set(VERTICAL_PACKS)
    for pack in VERTICAL_PACKS.values():
        assert pack.default_preset in PRESETS, pack.key
        assert pack.terms, pack.key


@pytest.mark.parametrize("key", sorted(VERTICAL_PACKS))
def test_every_open_industry_starts_a_business(
    client: TestClient, auth: AuthHeaders, key: str
) -> None:
    owner = uuid4()
    business = {"name": f"Test {key}", "vertical": key, "locale": "he",
                "time_zone": "Asia/Jerusalem", "currency": "ILS"}  # fmt: skip
    created = client.post("/tenants", json=business, headers=auth(owner))
    assert created.status_code == 201, created.text
    headers = auth(owner, created.json()["id"])
    pack = VERTICAL_PACKS[key]

    services = client.get("/services", headers=headers).json()
    assert sorted(s["name"] for s in services) == sorted(
        s.names["he"] for s in pack.default_services
    )
    fields = client.get("/clients/fields", headers=headers).json()
    assert [f["key"] for f in fields] == [f.key for f in pack.client_fields]


def test_planned_and_unknown_industries_cannot_sign_up(
    client: TestClient, auth: AuthHeaders
) -> None:
    for key in ("pets", "spaceship"):
        business = {"name": "Nope", "vertical": key, "locale": "en",
                    "time_zone": "Asia/Jerusalem", "currency": "ILS"}  # fmt: skip
        assert client.post("/tenants", json=business, headers=auth(uuid4())).status_code == 422


def test_contact_form_accepts_any_catalog_industry(client: TestClient) -> None:
    lead = {"name": "Dana", "email": "dana@example.com", "locale": "en"}
    for key in ("pets", "barbershop", "other"):
        assert client.post("/public/contact", json={**lead, "vertical": key}).status_code == 202
    bad = client.post("/public/contact", json={**lead, "vertical": "spaceship"})
    assert bad.status_code == 422


def test_a_new_club_has_courts_ready_to_book(client: TestClient, auth: AuthHeaders) -> None:
    """Sports & facilities: the starter courts are for rent with opening hours, serve the
    services by the hour, and have free times from the first minute."""
    owner = uuid4()
    business = {"name": "Padel Point", "vertical": "padel_tennis", "locale": "en",
                "time_zone": "Asia/Jerusalem", "currency": "ILS"}  # fmt: skip
    tenant_id = client.post("/tenants", json=business, headers=auth(owner)).json()["id"]
    headers = auth(owner, tenant_id)

    services = {s["name"]: s for s in client.get("/resources", headers=headers).json()}
    padel = services["Padel court"]
    assert (padel["min_minutes"], padel["max_minutes"], padel["step_minutes"]) == (60, 120, 30)
    assert padel["price_per_hour"] == 16000
    assert [r["name"] for r in padel["rooms"]] == ["Court 1", "Court 2", "Court 3"]
    day = (date.today() + timedelta(days=3)).isoformat()
    slots = client.get(
        "/resources/slots",
        params={"service_id": padel["id"], "date": day, "minutes": 90},
        headers=headers,
    ).json()
    assert len({s["room_id"] for s in slots}) == 3 and slots[0]["price_amount"] == 24000
