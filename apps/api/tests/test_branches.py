from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, add_member, local_today
from tests.test_bookings import new_client
from tests.test_plans import sell


def modules(client: TestClient, headers: dict) -> dict[str, int]:
    return client.get("/tenants/current/modules", headers=headers).json()["modules"]


def test_a_business_starts_with_its_branches_and_pays_for_the_extra_ones(
    client: TestClient, auth: AuthHeaders
) -> None:
    owner = uuid4()
    body = {**STUDIO, "locale": "he", "modules": {"client_app": 1, "extra_location": 2}}
    tenant = client.post("/tenants", json=body, headers=auth(owner)).json()
    headers = auth(owner, tenant["id"])

    branches = client.get("/locations", headers=headers).json()
    assert [b["name"] for b in branches] == ["סניף ראשי", "סניף 2", "סניף 3"]
    assert modules(client, headers)["extra_location"] == 2

    # The extra-branch charge follows the active branches.
    client.post("/locations", json={"name": "Haifa"}, headers=headers)
    assert modules(client, headers)["extra_location"] == 3
    for branch in branches[1:]:
        client.patch(f"/locations/{branch['id']}", json={"active": False}, headers=headers)
    assert modules(client, headers)["extra_location"] == 1
    # Choosing modules does not change it; branches do.
    client.put("/tenants/current/modules", json={"modules": {"crm": 1}}, headers=headers)
    assert modules(client, headers).get("extra_location") == 1


def test_the_last_active_branch_stays_active(client: TestClient, studio: dict) -> None:
    only = studio["location"]["id"]
    response = client.patch(f"/locations/{only}", json={"active": False}, headers=studio["headers"])
    assert response.status_code == 409 and response.json()["detail"] == "last_branch"


def test_the_current_branch_must_be_one_of_the_business(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    other_owner = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()
    their_branch = client.get("/locations", headers=auth(other_owner, other["id"])).json()[0]

    for branch in (their_branch["id"], str(uuid4())):
        headers = {**studio["headers"], "X-Location-Id": branch}
        response = client.get("/clients", headers=headers)
        assert response.status_code == 422 and response.json()["detail"] == "unknown_branch"


def test_clients_sales_and_numbers_follow_the_current_branch(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    in_north = {**headers, "X-Location-Id": north}
    in_south = {**headers, "X-Location-Id": south}

    # New clients are filed under the current branch; with none chosen, they have no home branch.
    dana = new_client(client, in_north, "Dana")
    yossi = new_client(client, in_south, "Yossi")
    anyone = new_client(client, headers, "Avi")
    assert client.get(f"/clients/{dana}", headers=headers).json()["home_location_id"] == north
    assert client.get(f"/clients/{anyone}", headers=headers).json()["home_location_id"] is None

    names = lambda h: {c["first_name"] for c in client.get("/clients", headers=h).json()["items"]}  # noqa: E731
    assert names(headers) == {"Dana", "Yossi", "Avi"}
    assert names(in_north) == {"Dana", "Avi"}  # no home branch: shown in every branch

    # A sale is filed under the current branch, else the client's home branch.
    plan = client.get("/plans", headers=headers).json()[0]
    sell(client, in_north, dana, plan["id"])
    sell(client, headers, yossi, plan["id"])  # Yossi's home branch: South

    today = local_today()
    params = {"start": today - timedelta(days=1), "end": today, "keys": ["revenue", "plans_sold"]}

    def numbers(h: dict) -> dict[str, float]:
        return {
            m["key"]: m["value"] for m in client.get("/metrics", params=params, headers=h).json()
        }

    everywhere, north_only, south_only = numbers(headers), numbers(in_north), numbers(in_south)
    assert everywhere["plans_sold"] == 2
    assert north_only["plans_sold"] == south_only["plans_sold"] == 1
    assert north_only["revenue"] + south_only["revenue"] == everywhere["revenue"]

    sales = client.get("/sales", params={"start": today, "end": today}, headers=in_south).json()
    assert [r["client_name"] for r in sales["receipts"]] == ["Yossi"]


def test_sessions_follow_the_current_branch(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    day = local_today() + timedelta(days=1)
    for branch in (north, south, None):
        client.post(
            "/sessions",
            json={
                "service_id": studio["service"]["id"],
                "date": day.isoformat(),
                "start_time": "09:00",
                "location_id": branch,
            },
            headers=headers,
        )

    def branches(h: dict) -> list[str | None]:
        found = client.get("/sessions", params={"start": day, "days": 1}, headers=h).json()
        return sorted((s["location_id"] or "") for s in found)

    assert len(branches(headers)) == 3
    # Without a branch it shows everywhere.
    assert branches({**headers, "X-Location-Id": south}) == sorted(["", south])

    # A new session with no place is filed under the current branch.
    client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": day.isoformat(),
            "start_time": "11:00",
        },
        headers={**headers, "X-Location-Id": south},
    )
    assert branches({**headers, "X-Location-Id": south}).count(south) == 2


def test_team_members_work_at_branches(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    headers = studio["headers"]
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    coach = str(studio["coach"])

    updated = client.put(
        f"/staff/{coach}/branches", json={"location_ids": [south]}, headers=headers
    )
    assert updated.status_code == 200 and updated.json()["location_ids"] == [south]
    members = {m["user_id"]: m for m in client.get("/staff", headers=headers).json()["members"]}
    assert members[coach]["location_ids"] == [south]
    assert members[str(studio["owner"])]["location_ids"] == []  # all branches

    bad = client.put(
        f"/staff/{coach}/branches", json={"location_ids": [str(uuid4())]}, headers=headers
    )
    assert bad.status_code == 422
    # Staff cannot assign branches.
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "staff")
    denied = client.put(
        f"/staff/{coach}/branches",
        json={"location_ids": []},
        headers=auth(desk, studio["tenant_id"]),
    )
    assert denied.status_code == 403


def test_migration_files_existing_rows_of_single_branch_businesses(engine: Engine) -> None:
    """The trigger files a new row under the only active branch when nothing else says where."""
    with engine.begin() as conn:
        tenant = conn.execute(
            text("""
                INSERT INTO app.tenants (name, vertical, locale, time_zone, currency)
                VALUES ('Solo', 'fitness', 'en', 'Asia/Jerusalem', 'ILS') RETURNING id
            """)
        ).scalar_one()
        branch = conn.execute(
            text("INSERT INTO app.locations (tenant_id, name) VALUES (:t, 'Only') RETURNING id"),
            {"t": tenant},
        ).scalar_one()
        home = conn.execute(
            text("""
                INSERT INTO app.clients (tenant_id, first_name) VALUES (:t, 'Noa')
                RETURNING home_location_id
            """),
            {"t": tenant},
        ).scalar_one()
    assert home == branch


def test_my_businesses_shows_each_business_with_its_branches(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner = uuid4()
    pizza = client.post(
        "/tenants",
        json={**STUDIO, "name": "Pizza", "modules": {"extra_location": 3}},
        headers=auth(owner),
    ).json()
    barber = client.post(
        "/tenants", json={**STUDIO, "name": "Barber", "vertical": "barbershop"}, headers=auth(owner)
    ).json()
    # In a third business they are only staff: no money figures there.
    other_owner = uuid4()
    gym = client.post("/tenants", json={**STUDIO, "name": "Gym"}, headers=auth(other_owner)).json()
    add_member(engine, gym["id"], owner, "staff")

    found = client.get("/me/businesses", headers=auth(owner)).json()
    by_name = {b["name"]: b for b in found}
    assert list(by_name) == ["Pizza", "Barber", "Gym"]
    assert len(by_name["Pizza"]["branches"]) == 4 and len(by_name["Barber"]["branches"]) == 1
    assert by_name["Barber"]["vertical"] == "barbershop" and by_name["Pizza"]["role"] == "owner"
    assert by_name["Pizza"]["revenue_month"] == 0 and by_name["Pizza"]["active_clients"] == 0
    assert by_name["Gym"]["role"] == "staff" and by_name["Gym"]["revenue_month"] is None
    assert {b["tenant_id"] for b in found} == {pizza["id"], barber["id"], gym["id"]}


def test_a_member_kept_to_branches_sees_only_theirs(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    east = client.post("/locations", json={"name": "East"}, headers=headers).json()["id"]
    day = local_today() + timedelta(days=1)
    for branch in (north, south, east):
        client.post(
            "/sessions",
            json={
                "service_id": studio["service"]["id"],
                "date": day.isoformat(),
                "start_time": "09:00",
                "location_id": branch,
            },
            headers=headers,
        )
    coach = str(studio["coach"])
    client.put(f"/staff/{coach}/branches", json={"location_ids": [south, east]}, headers=headers)
    mine = auth(studio["coach"], studio["tenant_id"])

    def seen(h: dict) -> list[str]:
        found = client.get("/sessions", params={"start": day, "days": 1}, headers=h)
        assert found.status_code == 200, found.text
        return sorted(s["location_id"] for s in found.json())

    both = sorted([south, east])
    assert sorted(b["id"] for b in client.get("/locations", headers=mine).json()) == both
    assert seen(mine) == both  # "all branches" is all of theirs
    assert seen({**mine, "X-Location-Id": east}) == [east]
    assert seen({**mine, "X-Location-Id": north}) == both  # never another branch
    assert len(seen(headers)) == 3  # the owner sees every branch

    # Kept to a single branch, they always work in it.
    client.put(f"/staff/{coach}/branches", json={"location_ids": [east]}, headers=headers)
    assert seen(mine) == [east]


def test_adding_a_branch_states_the_charge_and_sets_it_up(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    headers = studio["headers"]
    main = studio["location"]["id"]
    client.put(
        f"/locations/{main}/hours",
        json={"intervals": [{"weekday": 0, "opens": "09:00", "closes": "17:00"}]},
        headers=headers,
    )
    colleague = uuid4()
    add_member(engine, studio["tenant_id"], colleague, "staff")
    client.put(f"/staff/{colleague}/branches", json={"location_ids": [main]}, headers=headers)

    preview = client.get("/locations/new-branch", headers=headers).json()
    assert preview["chargeable"] and preview["monthly_extra_now"] == 0
    assert preview["monthly_extra_after"] == preview["extra_branch_price"] > 0

    body = {"name": "Ashdod", "copy_hours_from": main, "staff_user_ids": [str(colleague)]}
    refused = client.post("/locations/new-branch", json=body, headers=headers)
    assert refused.status_code == 409 and refused.json()["detail"] == "charge_not_accepted"
    assert len(client.get("/locations", headers=headers).json()) == 1

    created = client.post(
        "/locations/new-branch", json={**body, "accept_extra_charge": True}, headers=headers
    )
    assert created.status_code == 201
    new_id = created.json()["id"]
    assert modules(client, headers)["extra_location"] == 1
    hours = client.get(f"/locations/{new_id}/hours", headers=headers).json()["intervals"]
    assert [(h["weekday"], h["opens"][:5]) for h in hours] == [(0, "09:00")]
    member = next(
        m
        for m in client.get("/staff", headers=headers).json()["members"]
        if m["user_id"] == str(colleague)
    )
    assert set(member["location_ids"]) == {main, new_id}

    # Staff without the settings permission cannot add one.
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "staff")
    desk_headers = auth(desk, studio["tenant_id"])
    assert client.get("/locations/new-branch", headers=desk_headers).status_code == 403
