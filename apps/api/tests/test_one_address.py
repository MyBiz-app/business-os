"""One address component everywhere (W2-5): city centers, the legal address, leads, a client's
city, the public inquiry form, the import and the demo residents."""

import json
import random
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.seed import seed
from app.seed.residence import place_residents
from tests.conftest import AuthHeaders
from tests.test_client_app import join, join_code
from tests.test_geo_addresses import city, tel_aviv_address
from tests.test_leads import with_crm


def test_every_city_has_a_center_inside_the_country(engine: Engine) -> None:
    with engine.connect() as connection:
        total, placed, outside, sources = connection.execute(
            text("""
                SELECT count(*), count(latitude),
                       count(*) FILTER (WHERE latitude NOT BETWEEN 29.3 AND 33.6
                                           OR longitude NOT BETWEEN 34.1 AND 36),
                       count(DISTINCT center_source)
                FROM app.geo_cities
            """)
        ).one()
    assert total == placed > 1200
    assert outside == 0
    assert sources == 2  # a city's own point, or only the middle of its region


def test_legal_address_is_chosen_from_the_lists_and_keeps_the_text(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    address = tel_aviv_address(client, headers) | {"address_details": "קומה 3"}

    saved = client.patch("/tenants/current", json=address, headers=headers)

    assert saved.status_code == 200, saved.text
    tenant = saved.json()
    assert tenant["city_code"] == address["city_code"]
    assert tenant["street_name"] == "דיזנגוף"
    # The older text columns (documents, the readiness card) follow the structured address.
    assert tenant["address_line"] == "דיזנגוף 12 (קומה 3)"
    assert tenant["address_city"].startswith("תל אביב")

    cleared = client.patch(
        "/tenants/current",
        json={"city_code": None, "street_code": None, "house_number": None},
        headers=headers,
    ).json()
    assert cleared["city_code"] is None and cleared["address_line"] is None

    refused = client.patch("/tenants/current", json={"street_code": 5}, headers=headers)
    assert refused.status_code == 422  # a street needs its city
    old_way = client.patch(
        "/tenants/current", json={"address_line": "הרצל 1", "address_city": "חיפה"}, headers=headers
    ).json()
    assert old_way["address_line"] == "הרצל 1" and old_way["city_code"] is None


def test_a_lead_has_a_city_and_a_street_is_optional(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    haifa = city(client, headers, "חיפה")

    with_city = client.post(
        "/leads", json={"first_name": "Dana", "city_code": haifa["code"]}, headers=headers
    )
    assert with_city.status_code == 201, with_city.text
    assert with_city.json()["city_name"] == haifa["name_he"]
    assert with_city.json()["address"] == haifa["name_he"]
    assert with_city.json()["street_code"] is None

    without = client.post("/leads", json={"first_name": "Noa"}, headers=headers)
    assert without.status_code == 201 and without.json()["city_code"] is None  # soft

    address = tel_aviv_address(client, headers, house="7")
    lead = client.patch(f"/leads/{with_city.json()['id']}", json=address, headers=headers).json()
    assert lead["street_name"] == "דיזנגוף"
    assert lead["address"].startswith("דיזנגוף 7, תל אביב")

    unknown = client.post("/leads", json={"first_name": "X", "city_code": 999999}, headers=headers)
    assert unknown.status_code == 422 and unknown.json()["detail"] == "unknown_city"
    no_city = client.post("/leads", json={"first_name": "X", "street_code": 1}, headers=headers)
    assert no_city.status_code == 422

    won = client.post(f"/leads/{lead['id']}/convert", headers=headers).json()
    profile = client.get(f"/clients/{won['client_id']}", headers=headers).json()
    assert profile["city_code"] == address["city_code"]  # the client keeps the lead's city


def test_a_client_has_a_city(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    haifa = city(client, headers, "חיפה")
    created = client.post(
        "/clients", json={"first_name": "Dana", "city_code": haifa["code"]}, headers=headers
    )
    assert created.status_code == 201, created.text
    assert created.json()["city_name"] == haifa["name_he"]

    moved = client.patch(
        f"/clients/{created.json()['id']}", json={"city_code": None}, headers=headers
    )
    assert moved.json()["city_code"] is None
    bad = client.post("/clients", json={"first_name": "X", "city_code": 999999}, headers=headers)
    assert bad.status_code == 422 and bad.json()["detail"] == "unknown_city"


def test_client_names_their_city_when_joining_in_the_app(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    headers = auth(user, studio["tenant_id"])
    haifa = city(client, studio["headers"], "חיפה")

    saved = client.patch(
        "/client/profile", json={"first_name": "Dana", "city_code": haifa["code"]}, headers=headers
    )

    assert saved.status_code == 200, saved.text
    stored = client.get(f"/clients/{joined['client_id']}", headers=studio["headers"]).json()
    assert stored["city_code"] == haifa["code"]
    # Leaving the city out keeps it.
    client.patch("/client/profile", json={"first_name": "Dana"}, headers=headers)
    kept = client.get(f"/clients/{joined['client_id']}", headers=studio["headers"]).json()
    assert kept["city_code"] == haifa["code"]
    bad = client.patch(
        "/client/profile", json={"first_name": "Dana", "city_code": 999999}, headers=headers
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "unknown_city"


def test_the_public_inquiry_form_takes_a_city(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    code = join_code(client, studio)
    found = client.get("/public/geo/cities", params={"q": "חיפה"})  # no sign-in
    assert found.status_code == 200 and found.json()[0]["name_he"] == "חיפה"
    haifa = found.json()[0]["code"]

    sent = client.post(
        f"/public/businesses/{code}/inquiries",
        json={"first_name": "Maya", "phone": "052-2222222", "city_code": haifa},
    )
    assert sent.status_code == 202, sent.text
    lead = client.get("/leads", headers=studio["headers"]).json()["items"][0]
    assert lead["city_code"] == haifa and lead["address"] == "חיפה"

    bad = client.post(
        f"/public/businesses/{code}/inquiries",
        json={"first_name": "Maya", "phone": "052-3333333", "city_code": 999999},
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "unknown_city"


def test_import_finds_the_city_column_and_matches_names(client: TestClient, studio: dict) -> None:
    csv = (
        "שם פרטי,טלפון,עיר\n"
        "דנה,0501111111,תל אביב\n"  # the short name of "תל אביב - יפו"
        "יוסי,0502222222,חיפה\n"
        "נועה,0503333333,עיר שלא קיימת\n"
        "רון,0504444444,\n"
    ).encode()
    preview = client.post(
        "/clients/import", files={"file": ("c.csv", csv)}, headers=studio["headers"]
    ).json()

    assert preview["mapping"] == ["first_name", "phone", "city"]
    assert preview["ready"] == 4  # an unknown city never keeps a client out
    assert (preview["cities_matched"], preview["cities_unmatched"]) == (2, 1)
    assert [(i["line"], i["code"]) for i in preview["issues"]] == [(4, "unknown_city")]

    done = client.post(
        "/clients/import",
        files={"file": ("c.csv", csv)},
        data={"commit": "true", "mapping": json.dumps(preview["mapping"])},
        headers=studio["headers"],
    )
    assert done.json()["imported"] is True
    rows = client.get("/clients", headers=studio["headers"]).json()["items"]
    cities = {r["first_name"]: r["city_name"] for r in rows}
    assert cities["יוסי"] == "חיפה" and cities["דנה"].startswith("תל אביב")
    assert cities["נועה"] is None and cities["רון"] is None


def test_demo_people_get_cities_and_streets_once(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": f"{owner}@example.com"},
        )
        tenant = seed(connection, f"{owner}@example.com", 2, random.Random(5))
        before = connection.execute(
            text("SELECT count(*) FROM app.clients WHERE tenant_id = :t AND city_code IS NULL"),
            {"t": tenant},
        ).scalar_one()

        first = place_residents(connection, [tenant])
        again = place_residents(connection, [tenant])

        left = connection.execute(
            text("SELECT count(*) FROM app.clients WHERE tenant_id = :t AND city_code IS NULL"),
            {"t": tenant},
        ).scalar_one()
        streets = connection.execute(
            text("""
                SELECT count(*) FROM app.client_addresses
                WHERE tenant_id = :t AND street_code IS NOT NULL AND city_code IS NOT NULL
            """),
            {"t": tenant},
        ).scalar_one()
        cities = connection.execute(
            text("SELECT count(DISTINCT city_code) FROM app.clients WHERE tenant_id = :t"),
            {"t": tenant},
        ).scalar_one()

    assert before > 0 and first["clients"] == before and left == 0
    assert again == {"clients": 0, "addresses": 0, "leads": 0, "people": 0}  # nothing twice
    assert streets > 0 and cities > 1  # people live in more than one town
