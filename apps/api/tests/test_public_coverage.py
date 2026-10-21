"""The landing page's "MyBiz across the country" numbers (W5-4): counts only, five at least."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders
from tests.test_business_map import (
    KIRYAT_SHMONA,
    TEL_AVIV,
    make_business,
    set_branch_city,
)

PATH = "/public/geo/coverage"


def test_coverage_needs_no_sign_in_and_shows_nothing_below_five(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    set_branch_city(engine, studio["tenant_id"], TEL_AVIV)
    for i in range(3):  # four businesses in Tel Aviv
        set_branch_city(engine, make_business(client, auth, f"B{i}", "fitness"), TEL_AVIV)

    assert client.get(PATH).json() == {"cities": [], "businesses": 0}


def test_coverage_lists_a_city_from_five_businesses_with_no_names_or_industries(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    set_branch_city(engine, studio["tenant_id"], TEL_AVIV)
    for i in range(4):
        set_branch_city(engine, make_business(client, auth, f"Secret{i}", "clinic"), TEL_AVIV)
    for i in range(2):  # a second city with only two: left out
        set_branch_city(engine, make_business(client, auth, f"Far{i}", "clinic"), KIRYAT_SHMONA)

    body = client.get(PATH).json()

    (city,) = body["cities"]
    assert city["businesses"] == 5 and body["businesses"] == 5
    assert set(city) == {"name_he", "name_en", "latitude", "longitude", "businesses"}
    assert "Secret" not in str(body) and "clinic" not in str(body)


def test_coverage_ignores_closed_businesses(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    tenants = [studio["tenant_id"]] + [
        make_business(client, auth, f"B{i}", "fitness") for i in range(4)
    ]
    for tenant in tenants:
        set_branch_city(engine, tenant, TEL_AVIV)
    assert client.get(PATH).json()["businesses"] == 5

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenants SET closed_at = now() WHERE id = :t"), {"t": tenants[1]}
        )
    assert client.get(PATH).json() == {"cities": [], "businesses": 0}
