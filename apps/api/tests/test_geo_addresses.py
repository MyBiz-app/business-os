"""Israeli cities and streets, structured addresses and branch coordinates (round 7, R34)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.geo.geocoder import Point
from app.geo.snapshot import normalize_search
from tests.conftest import AuthHeaders
from tests.test_bookings import new_client


class FakeGeocoder:
    def __init__(self, point: Point | None) -> None:
        self.point = point
        self.calls: list[dict] = []

    def find(self, **query) -> Point | None:
        self.calls.append(query)
        return self.point


@pytest.fixture
def geocoder(monkeypatch: pytest.MonkeyPatch) -> FakeGeocoder:
    fake = FakeGeocoder(Point(32.0853, 34.7818))
    monkeypatch.setattr("app.geo.branch.get_geocoder", lambda: fake)
    return fake


def city(client: TestClient, headers: dict, q: str) -> dict:
    found = client.get("/geo/cities", params={"q": q}, headers=headers).json()
    assert found, q
    return found[0]


def street(client: TestClient, headers: dict, city_code: int, q: str) -> dict:
    found = client.get(f"/geo/cities/{city_code}/streets", params={"q": q}, headers=headers).json()
    assert found, q
    return found[0]


def tel_aviv_address(client: TestClient, headers: dict, house: str = "12") -> dict:
    tel_aviv = city(client, headers, "תל אביב")
    dizengoff = street(client, headers, tel_aviv["code"], "דיזנגוף")
    return {"city_code": tel_aviv["code"], "street_code": dizengoff["code"], "house_number": house}


def test_the_lists_are_loaded_and_shared(engine: Engine) -> None:
    with engine.connect() as connection:
        cities, streets = connection.execute(
            text("""
                SELECT (SELECT count(*) FROM app.geo_cities),
                       (SELECT count(*) FROM app.geo_streets)
            """)
        ).one()
    assert cities > 1200
    assert streets > 60000


def test_names_are_searched_without_quotes_or_hyphens() -> None:
    assert normalize_search("ג'ת") == normalize_search("גת") == "גת"
    assert normalize_search("פרדס  חנה-כרכור") == "פרדס חנה כרכור"
    assert normalize_search('ת"א') == "תא"


def test_city_search(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    found = client.get("/geo/cities", params={"q": "תל אביב"}, headers=headers)
    assert found.status_code == 200
    assert found.json()[0]["name_he"].startswith("תל אביב")
    # Typing without the geresh or the hyphen still finds the town.
    assert "פרדס חנה-כרכור" in [
        c["name_he"]
        for c in client.get("/geo/cities", params={"q": "חנה כרכור"}, headers=headers).json()
    ]
    assert "ג'ת" in [
        c["name_he"] for c in client.get("/geo/cities", params={"q": "גת"}, headers=headers).json()
    ]
    # Names that start with the letters come before names that only contain them.
    gat = client.get("/geo/cities", params={"q": "גת"}, headers=headers).json()
    assert gat[0]["name_he"].startswith("גת") or gat[0]["name_he"].startswith("ג'ת")
    assert len(client.get("/geo/cities", params={"limit": 5}, headers=headers).json()) == 5
    assert client.get("/geo/cities", params={"q": "xxxzzz"}, headers=headers).json() == []


def test_street_search_covers_other_spellings(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    tel_aviv = city(client, headers, "תל אביב")["code"]
    official = street(client, headers, tel_aviv, "דיזנגוף")
    other_spelling = client.get(
        f"/geo/cities/{tel_aviv}/streets", params={"q": "דיזינגוף"}, headers=headers
    ).json()
    assert official["code"] in [s["code"] for s in other_spelling]
    # Street codes belong to one city: the same code in another city is another street.
    haifa = city(client, headers, "חיפה")["code"]
    assert official["code"] not in [
        s["code"]
        for s in client.get(
            f"/geo/cities/{haifa}/streets", params={"q": "דיזנגוף"}, headers=headers
        ).json()
    ]


def test_lists_need_a_signed_in_person(client: TestClient) -> None:
    assert client.get("/geo/cities").status_code in (401, 403)


def test_a_branch_keeps_a_checked_address_and_its_point(
    client: TestClient, studio: dict, geocoder: FakeGeocoder
) -> None:
    headers = studio["headers"]
    address = tel_aviv_address(client, headers) | {"address_details": "קומה 2"}
    created = client.post("/locations", json={"name": "Center", **address}, headers=headers)
    assert created.status_code == 201, created.text
    branch = created.json()
    assert branch["city_name"].startswith("תל אביב")
    assert branch["street_name"] == "דיזנגוף"
    assert branch["address"] == f"דיזנגוף 12, {branch['city_name']} (קומה 2)"
    assert (branch["latitude"], branch["longitude"]) == (32.0853, 34.7818)
    assert geocoder.calls == [
        {"street": "דיזנגוף", "house_number": "12", "city": branch["city_name"]}
    ]

    # Saving something else does not look the point up again.
    client.patch(f"/locations/{branch['id']}", json={"name": "Center 2"}, headers=headers)
    assert len(geocoder.calls) == 1
    # A different house number does.
    moved = client.patch(f"/locations/{branch['id']}", json={"house_number": "99"}, headers=headers)
    assert moved.json()["address"].startswith("דיזנגוף 99,")
    assert len(geocoder.calls) == 2


def test_an_address_must_be_a_real_city_and_street(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    good = tel_aviv_address(client, headers)

    def refused(body: dict) -> str:
        response = client.post("/locations", json={"name": "X", **body}, headers=headers)
        assert response.status_code == 422, response.text
        return response.json()["detail"]

    assert refused({**good, "city_code": 999999}) == "unknown_city"
    assert refused({**good, "street_code": 99999999}) == "unknown_street"
    assert (
        refused({"city_code": good["city_code"], "street_code": good["street_code"]})
        == "address_incomplete"
    )
    assert (
        refused({"street_code": good["street_code"], "house_number": "1"}) == "address_incomplete"
    )


def test_a_street_missing_from_the_list_can_be_typed(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    tel_aviv = city(client, headers, "תל אביב")
    created = client.post(
        "/locations",
        json={
            "name": "New",
            "city_code": tel_aviv["code"],
            "street_unlisted": "רחוב חדש",
            "house_number": "3",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    branch = created.json()
    assert (branch["street_code"], branch["street_unlisted"]) == (None, "רחוב חדש")
    assert branch["address"].startswith("רחוב חדש 3,")
    # Choosing a listed street later replaces the typed one.
    listed = tel_aviv_address(client, headers)
    again = client.patch(f"/locations/{branch['id']}", json=listed, headers=headers).json()
    assert (again["street_unlisted"], again["street_name"]) == (None, "דיזנגוף")


def test_the_map_service_never_blocks_saving(
    client: TestClient, studio: dict, geocoder: FakeGeocoder, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = studio["headers"]
    geocoder.point = None
    unknown = client.post(
        "/locations", json={"name": "A", **tel_aviv_address(client, headers)}, headers=headers
    )
    assert unknown.status_code == 201
    assert (unknown.json()["latitude"], unknown.json()["longitude"]) == (None, None)

    def crash(**_query) -> None:
        raise RuntimeError("down")

    geocoder.find = crash  # type: ignore[method-assign]
    crashed = client.post(
        "/locations", json={"name": "B", **tel_aviv_address(client, headers, "5")}, headers=headers
    )
    assert crashed.status_code == 201
    assert crashed.json()["latitude"] is None


def test_the_pin_can_be_placed_by_hand_and_plain_text_resets_it(
    client: TestClient, studio: dict, geocoder: FakeGeocoder
) -> None:
    headers = studio["headers"]
    branch = client.post(
        "/locations", json={"name": "Pin", **tel_aviv_address(client, headers)}, headers=headers
    ).json()
    url = f"/locations/{branch['id']}"
    pinned = client.patch(url, json={"latitude": 32.1, "longitude": 34.8}, headers=headers).json()
    assert (pinned["latitude"], pinned["longitude"]) == (32.1, 34.8)
    assert len(geocoder.calls) == 1  # the pin was not looked up again
    # A point needs both coordinates.
    assert client.patch(url, json={"latitude": 32.1}, headers=headers).status_code == 422
    # Plain text replaces the structured address and drops the (now wrong) point.
    text_only = client.patch(url, json={"address": "Somewhere else 1"}, headers=headers).json()
    assert text_only["address"] == "Somewhere else 1"
    assert (text_only["city_code"], text_only["street_code"], text_only["latitude"]) == (
        None,
        None,
        None,
    )
    # Clearing the structured address clears the rest.
    client.patch(url, json=tel_aviv_address(client, headers), headers=headers)
    cleared = client.patch(
        url, json={"city_code": None, "street_code": None, "house_number": None}, headers=headers
    ).json()
    assert (cleared["address"], cleared["city_code"], cleared["latitude"]) == (None, None, None)


def test_a_new_branch_needs_a_full_address(
    client: TestClient, studio: dict, geocoder: FakeGeocoder
) -> None:
    headers = studio["headers"]
    base = {"name": "Second", "accept_extra_charge": True}
    missing = client.post("/locations/new-branch", json=base, headers=headers)
    assert (missing.status_code, missing.json()["detail"]) == (422, "address_incomplete")
    ok = client.post(
        "/locations/new-branch", json=base | tel_aviv_address(client, headers), headers=headers
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["street_name"] == "דיזנגוף"


def test_a_person_keeps_their_home_address(client: TestClient, auth: AuthHeaders) -> None:
    user = uuid4()
    headers = auth(user)
    assert client.get("/me", headers=headers).json()["address_complete"] is False
    address = tel_aviv_address(client, headers, "7") | {"address_details": "דירה 3"}
    saved = client.patch("/me", json=address, headers=headers)
    assert saved.status_code == 200, saved.text
    me = saved.json()
    assert me["address_complete"] is True
    assert (me["address_line"], me["house_number"], me["address_details"]) == (
        "דיזנגוף 7",
        "7",
        "דירה 3",
    )
    assert me["city"].startswith("תל אביב")
    # Optional for people: a city alone is fine, and it can be cleared.
    city_only = client.patch(
        "/me",
        json={
            "city_code": address["city_code"],
            "street_code": None,
            "house_number": None,
            "address_details": None,
        },
        headers=headers,
    ).json()
    assert (city_only["address_complete"], city_only["address_line"]) == (False, None)
    gone = client.patch(
        "/me", json={"city_code": None, "street_code": None, "house_number": None}, headers=headers
    ).json()
    assert (gone["city"], gone["city_code"]) == (None, None)
    assert client.patch("/me", json={"city_code": 999999}, headers=headers).status_code == 422


def test_a_client_address_from_the_lists(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    chosen = tel_aviv_address(client, headers, "21") | {"address_details": "קומה 4", "label": "בית"}
    created = client.post(f"/clients/{dana}/addresses", json=chosen, headers=headers)
    assert created.status_code == 201, created.text
    saved = created.json()
    assert (saved["street"], saved["details"]) == ("דיזנגוף 21", "קומה 4")
    assert saved["city"].startswith("תל אביב")
    moved = client.patch(
        f"/addresses/{saved['id']}", json={"house_number": "30"}, headers=headers
    ).json()
    assert moved["street"] == "דיזנגוף 30"
    # The older way (free text) still works, and needs both parts.
    assert (
        client.post(
            f"/clients/{dana}/addresses",
            json={"street": "Ben Yehuda 5", "city": "Haifa"},
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/clients/{dana}/addresses", json={"street": "Only"}, headers=headers
        ).status_code
        == 422
    )
