"""The planned-branch numbers (clients by city) and the console's map of businesses (W2-4)."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, add_member, make_staff

TEL_AVIV, KIRYAT_SHMONA = 5000, 2800


def city_point(engine: Engine, code: int) -> tuple[float | None, float | None]:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT latitude, longitude FROM app.geo_cities WHERE code = :c"), {"c": code}
        ).one()
    return row.latitude, row.longitude


def add_clients(
    engine: Engine, tenant_id, city_code: int | None, count: int, status: str = "active"
) -> list[str]:
    """`count` clients whose saved address is in the city (no address when `city_code` is None)."""
    ids = []
    with engine.begin() as connection:
        for i in range(count):
            client_id = connection.execute(
                text("""
                    INSERT INTO app.clients (tenant_id, first_name, status)
                    VALUES (:t, :n, :s) RETURNING id
                """),
                {"t": tenant_id, "n": f"C{uuid4().hex[:6]}{i}", "s": status},
            ).scalar_one()
            ids.append(str(client_id))
            if city_code is not None:
                connection.execute(
                    text("""
                        INSERT INTO app.client_addresses
                            (tenant_id, client_id, street, city, city_code)
                        VALUES (:t, :c, 'x', 'x', :city)
                    """),
                    {"t": tenant_id, "c": client_id, "city": city_code},
                )
    return ids


def make_business(client: TestClient, auth: AuthHeaders, name: str, vertical: str) -> str:
    body = {**STUDIO, "name": name, "vertical": vertical}
    return client.post("/tenants", json=body, headers=auth(uuid4())).json()["id"]


def staff(engine: Engine, auth: AuthHeaders, *permissions: str) -> dict:
    user = uuid4()
    make_staff(engine, user, "employee", tuple(permissions))
    return auth(user)


def test_clients_by_city_show_everyone_including_a_single_far_client(
    client: TestClient, engine: Engine, studio: dict
) -> None:
    tenant = studio["tenant_id"]
    add_clients(engine, tenant, TEL_AVIV, 3)
    add_clients(engine, tenant, KIRYAT_SHMONA, 1)  # one client: still on the map
    add_clients(engine, tenant, None, 2)
    add_clients(engine, tenant, TEL_AVIV, 4, status="lead")  # not clients yet

    body = client.get("/metrics/client-cities", headers=studio["headers"]).json()

    assert body["clients_total"] == 6
    assert body["clients_without_city"] == 2
    assert [(c["city_code"], c["clients"]) for c in body["cities"]] == [
        (TEL_AVIV, 3),
        (KIRYAT_SHMONA, 1),
    ]
    assert (body["cities"][0]["latitude"], body["cities"][0]["longitude"]) == city_point(
        engine, TEL_AVIV
    )
    assert "first_name" not in str(body)  # numbers only, no people


def test_clients_by_city_count_each_client_in_the_city_of_their_latest_address(
    client: TestClient, engine: Engine, studio: dict
) -> None:
    (moved,) = add_clients(engine, studio["tenant_id"], TEL_AVIV, 1)
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.client_addresses (tenant_id, client_id, street, city, city_code)
                VALUES (:t, :c, 'y', 'y', :city)
            """),
            {"t": studio["tenant_id"], "c": moved, "city": KIRYAT_SHMONA},
        )

    cities = client.get("/metrics/client-cities", headers=studio["headers"]).json()["cities"]

    assert [(c["city_code"], c["clients"]) for c in cities] == [(KIRYAT_SHMONA, 1)]


def test_clients_by_city_are_for_reports_readers_who_work_in_every_branch(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    add_clients(engine, studio["tenant_id"], TEL_AVIV, 1)
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/metrics/client-cities", headers=coach).status_code == 403

    # A branch manager has the reports right but sees only their own branch, not the whole business.
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "branch_manager")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenant_members SET location_ids = :ids WHERE user_id = :u"),
            {"ids": [studio["location"]["id"]], "u": manager},
        )
    answer = client.get("/metrics/client-cities", headers=auth(manager, studio["tenant_id"]))
    assert answer.status_code == 403 and answer.json()["detail"] == "all_branches_only"


def test_a_clients_own_city_counts_before_their_street_addresses(
    client: TestClient, engine: Engine, studio: dict
) -> None:
    (moved, _plain) = add_clients(engine, studio["tenant_id"], TEL_AVIV, 2)
    with engine.begin() as connection:  # the city on the client's record wins
        connection.execute(
            text("UPDATE app.clients SET city_code = :c WHERE id = :id"),
            {"c": KIRYAT_SHMONA, "id": moved},
        )
    (only_city,) = add_clients(engine, studio["tenant_id"], None, 1)
    with engine.begin() as connection:  # a client with a city and no street address at all
        connection.execute(
            text("UPDATE app.clients SET city_code = :c WHERE id = :id"),
            {"c": TEL_AVIV, "id": only_city},
        )

    cities = client.get("/metrics/client-cities", headers=studio["headers"]).json()
    counts = {c["city_code"]: c["clients"] for c in cities["cities"]}

    assert counts == {TEL_AVIV: 2, KIRYAT_SHMONA: 1}
    assert cities["clients_without_city"] == 0


def test_clients_by_city_never_mix_businesses(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    other_tenant = make_business(client, auth, "Other", "fitness")
    add_clients(engine, other_tenant, TEL_AVIV, 5)
    add_clients(engine, studio["tenant_id"], KIRYAT_SHMONA, 1)

    cities = client.get("/metrics/client-cities", headers=studio["headers"]).json()["cities"]

    assert [(c["city_code"], c["clients"]) for c in cities] == [(KIRYAT_SHMONA, 1)]


def set_branch_city(engine: Engine, tenant_id, city_code: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.locations SET city_code = :c WHERE tenant_id = :t"),
            {"c": city_code, "t": tenant_id},
        )


def test_the_console_map_is_for_the_team_and_needs_businesses_read(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    path = "/platform/metrics/business-map"
    assert client.get(path, headers=studio["headers"]).status_code == 403
    assert client.get(path, headers=staff(engine, auth, "usage.read")).status_code == 403
    assert client.get(path, headers=staff(engine, auth, "businesses.read")).status_code == 200


def test_the_console_map_leaves_out_cities_with_fewer_than_five(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    reader = staff(engine, auth, "businesses.read")
    set_branch_city(engine, studio["tenant_id"], TEL_AVIV)
    for i in range(3):  # four businesses in Tel Aviv
        tenant = make_business(client, auth, f"B{i}", "fitness")
        set_branch_city(engine, tenant, TEL_AVIV)
    add_clients(engine, studio["tenant_id"], TEL_AVIV, 4)

    body = client.get("/platform/metrics/business-map", headers=reader).json()
    assert body["min_per_city"] == 5
    assert body["businesses"] == [] and body["clients"] == []

    fifth = make_business(client, auth, "B5", "fitness")
    set_branch_city(engine, fifth, TEL_AVIV)
    add_clients(engine, studio["tenant_id"], TEL_AVIV, 1)

    body = client.get("/platform/metrics/business-map", headers=reader).json()
    (city,) = body["businesses"]
    assert (city["city_code"], city["total"]) == (TEL_AVIV, 5)
    assert (city["latitude"], city["longitude"]) == city_point(engine, TEL_AVIV)
    assert city["industries"] == [{"vertical": "fitness", "total": 5}]
    (home,) = body["clients"]
    assert (home["city_code"], home["total"]) == (TEL_AVIV, 5)


def test_the_console_map_names_an_industry_only_when_there_are_five_of_it(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    reader = staff(engine, auth, "businesses.read")
    set_branch_city(engine, studio["tenant_id"], KIRYAT_SHMONA)  # the studio: fitness
    for i in range(4):  # four more fitness businesses and one clinic, all in the same city
        set_branch_city(engine, make_business(client, auth, f"F{i}", "fitness"), KIRYAT_SHMONA)
    set_branch_city(engine, make_business(client, auth, "Clinic", "clinic"), KIRYAT_SHMONA)

    (city,) = client.get("/platform/metrics/business-map", headers=reader).json()["businesses"]

    assert city["total"] == 6
    assert city["industries"] == [
        {"vertical": "fitness", "total": 5},
        {"vertical": None, "total": 1},  # one clinic is not named: it would be recognisable
    ]


def test_the_console_map_ignores_closed_businesses_and_cities_without_a_point(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    reader = staff(engine, auth, "businesses.read")
    unplaced = KIRYAT_SHMONA
    point = city_point(engine, unplaced)
    with engine.begin() as connection:  # a city whose point is not known
        connection.execute(
            text("UPDATE app.geo_cities SET latitude = NULL, longitude = NULL WHERE code = :c"),
            {"c": unplaced},
        )
    try:
        tenants = [studio["tenant_id"]] + [
            make_business(client, auth, f"B{i}", "fitness") for i in range(5)
        ]
        for tenant in tenants:
            set_branch_city(engine, tenant, unplaced)

        body = client.get("/platform/metrics/business-map", headers=reader).json()
        assert body["businesses"] == [] and body["without_point"] == 1

        # Closed businesses are not on the map: with two closed, four are left, below the minimum.
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app.tenants SET closed_at = now() WHERE id = ANY(:t)"),
                {"t": tenants[1:3]},
            )
        assert (
            client.get("/platform/metrics/business-map", headers=reader).json()["without_point"]
            == 0
        )
    finally:  # the city list is shared by every test
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app.geo_cities SET latitude = :a, longitude = :b WHERE code = :c"),
                {"a": point[0], "b": point[1], "c": unplaced},
            )
