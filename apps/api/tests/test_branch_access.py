"""Branch-scoped access (#64): a member kept to some branches reaches only those, by id as well
as in lists, and can't file anything under another branch. Owners and managers see them all."""

from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.catalog.verticals import CATALOG
from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_quotes import new_quote, quote_body
from tests.test_receipts import sell
from tests.test_workspace import at


@pytest.fixture
def branches(client: TestClient, studio: dict) -> dict:
    """Two branches, each with a session, a booking and a client; plus the owner's headers."""
    owner = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=owner).json()["id"]
    day = (local_today() + timedelta(days=3)).isoformat()
    found: dict = {"north": north, "south": south, "day": day, "owner": owner}
    for name, branch in (("north", north), ("south", south)):
        created = client.post(
            "/sessions",
            json={
                "service_id": studio["service"]["id"],
                "date": day,
                "start_time": "09:00",
                "location_id": branch,
            },
            headers=owner,
        )
        assert created.status_code == 201, created.text
        found[f"{name}_session"] = created.json()["session_ids"][0]
        found[f"{name}_client"] = client.post(
            "/clients", json={"first_name": name, "home_location_id": branch}, headers=owner
        ).json()["id"]
        booked = client.post(
            f"/sessions/{found[f'{name}_session']}/bookings",
            json={"client_id": found[f"{name}_client"]},
            headers=owner,
        )
        assert booked.status_code == 201, booked.text
        found[f"{name}_booking"] = booked.json()["id"]
    return found


def member_at_north(
    client: TestClient,
    auth: AuthHeaders,
    engine: Engine,
    studio: dict,
    branches: dict,
    role: str = "front_desk",
) -> dict[str, str]:
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, role)
    kept = client.put(
        f"/staff/{member}/branches",
        json={"location_ids": [branches["north"]]},
        headers=branches["owner"],
    )
    assert kept.status_code == 200, kept.text
    return auth(member, studio["tenant_id"])


def test_a_member_kept_to_a_branch_cannot_reach_another_by_id(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, branches: dict
) -> None:
    mine = member_at_north(client, auth, engine, studio, branches)
    south_session, south_client = branches["south_session"], branches["south_client"]

    # Their own branch works end to end.
    assert client.get(f"/sessions/{branches['north_session']}", headers=mine).status_code == 200
    assert client.get(f"/clients/{branches['north_client']}", headers=mine).status_code == 200
    assert (
        client.get(f"/sessions/{branches['north_session']}/bookings", headers=mine).status_code
        == 200
    )
    changed = client.patch(
        f"/bookings/{branches['north_booking']}", json={"status": "checked_in"}, headers=mine
    )
    assert changed.status_code == 200, changed.text

    # Another branch's rows are "not found", whether read or changed.
    attempts = {
        "get session": client.get(f"/sessions/{south_session}", headers=mine),
        "edit session": client.patch(
            f"/sessions/{south_session}", json={"notes": "mine now"}, headers=mine
        ),
        "roster": client.get(f"/sessions/{south_session}/bookings", headers=mine),
        "book": client.post(
            f"/sessions/{south_session}/bookings",
            json={"client_id": branches["north_client"]},
            headers=mine,
        ),
        "cancel booking": client.patch(
            f"/bookings/{branches['south_booking']}", json={"status": "cancelled"}, headers=mine
        ),
        "get client": client.get(f"/clients/{south_client}", headers=mine),
        "edit client": client.patch(
            f"/clients/{south_client}", json={"first_name": "Taken"}, headers=mine
        ),
    }
    for name, response in attempts.items():
        assert response.status_code == 404, f"{name}: {response.status_code} {response.text}"
    # Nothing changed behind the refusals.
    after = client.get(f"/sessions/{south_session}", headers=branches["owner"]).json()
    assert after["notes"] is None and after["booked"] == 1
    assert (
        client.get(f"/clients/{south_client}", headers=branches["owner"]).json()["first_name"]
        == "south"
    )
    # The client's history shows only what happened at their branches.
    assert client.get(f"/clients/{south_client}/bookings", headers=mine).json() == []
    assert client.get(f"/clients/{south_client}/bookings", headers=branches["owner"]).json()


def test_a_member_kept_to_a_branch_cannot_file_things_under_another(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, branches: dict
) -> None:
    mine = member_at_north(client, auth, engine, studio, branches)
    south = branches["south"]
    session = {
        "service_id": studio["service"]["id"],
        "date": branches["day"],
        "start_time": "11:00",
    }
    refused = {
        "new session": client.post(
            "/sessions", json={**session, "location_id": south}, headers=mine
        ),
        "new weekly series": client.post(
            "/sessions",
            json={
                **session,
                "location_id": south,
                "repeat": {"weekdays": [0, 1, 2, 3, 4, 5, 6], "ends_on": branches["day"]},
            },
            headers=mine,
        ),
        "move a session": client.patch(
            f"/sessions/{branches['north_session']}", json={"location_id": south}, headers=mine
        ),
        "new client": client.post(
            "/clients", json={"first_name": "Q", "home_location_id": south}, headers=mine
        ),
        "move a client": client.patch(
            f"/clients/{branches['north_client']}", json={"home_location_id": south}, headers=mine
        ),
    }
    for name, response in refused.items():
        assert response.status_code == 422, f"{name}: {response.status_code} {response.text}"
        assert response.json()["detail"] == "unknown_branch"
    # Their own branch is fine.
    ok = client.post(
        "/sessions",
        json={**session, "location_id": branches["north"]},
        headers=mine,
    )
    assert ok.status_code == 201, ok.text


def test_series_and_copy_week_stay_inside_the_members_branches(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, branches: dict
) -> None:
    owner = branches["owner"]
    south_series = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": branches["day"],
            "start_time": "15:00",
            "location_id": branches["south"],
            "repeat": {
                "weekdays": [0, 1, 2, 3, 4, 5, 6],
                "ends_on": (local_today() + timedelta(days=30)).isoformat(),
            },
        },
        headers=owner,
    )
    assert south_series.status_code == 201, south_series.text
    series_id = south_series.json()["series_id"]
    mine = member_at_north(client, auth, engine, studio, branches)

    ended = client.post(
        f"/series/{series_id}/end", json={"last_date": branches["day"]}, headers=mine
    )
    assert ended.status_code == 404
    changed = client.patch(
        f"/series/{series_id}",
        json={
            "from_date": branches["day"],
            "start_time": "16:00",
            "duration_minutes": 60,
            "capacity": 5,
            "location_id": branches["north"],
        },
        headers=mine,
    )
    assert changed.status_code == 404

    # Copying a week only copies what the member can see: the south session stays put.
    source = local_today() + timedelta(days=3)
    copied = client.post(
        "/sessions/copy-week",
        json={"from_date": source.isoformat(), "to_date": (source + timedelta(days=7)).isoformat()},
        headers=mine,
    )
    assert copied.status_code == 200, copied.text
    assert copied.json()["created"] == 1  # the north session only
    next_week = client.get(
        "/sessions",
        params={"start": (source + timedelta(days=7)).isoformat(), "days": 1},
        headers=owner,
    ).json()
    one_offs = [s for s in next_week if s["series_id"] is None]
    assert [s["location_id"] for s in one_offs] == [branches["north"]]


def test_a_planner_kept_to_a_branch_plans_only_there(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, branches: dict
) -> None:
    """Rosters, stations, shift templates, opening hours and coverage (#166, #167) follow the
    branch rule too: another branch's shift, station or template is not found, and publishing
    never reaches its drafts."""
    owner, north, south = branches["owner"], branches["north"], branches["south"]
    coach = str(studio["coach"])
    role = client.post(
        "/roles",
        json={
            "name": "Planner",
            "permissions": [
                "schedule.read",
                "staff.read",
                "staff.manage",
                "catalog.read",
                "catalog.write",
            ],
        },
        headers=owner,
    ).json()["id"]
    planner = uuid4()
    add_member(engine, studio["tenant_id"], planner, "staff")
    client.patch(f"/staff/{planner}", json={"custom_role_id": role}, headers=owner)
    client.put(f"/staff/{planner}/branches", json={"location_ids": [north]}, headers=owner)
    mine = auth(planner, studio["tenant_id"])

    south_shift = client.post(
        "/shifts",
        json={"location_id": south, "user_id": coach, "starts_at": at(1, 9), "ends_at": at(1, 12)},
        headers=owner,
    ).json()["id"]
    south_station = client.post(
        "/stations", json={"location_id": south, "name": "Hall"}, headers=owner
    ).json()["id"]
    south_template = client.post(
        "/shift-templates",
        json={"location_id": south, "name": "Morning", "starts": "09:00", "ends": "12:00"},
        headers=owner,
    )
    assert south_template.status_code == 201, south_template.text

    # Planning into their own branch works; into the other one is refused.
    mine_shift = client.post(
        "/shifts",
        json={"location_id": north, "user_id": coach, "starts_at": at(2, 9), "ends_at": at(2, 12)},
        headers=mine,
    )
    assert mine_shift.status_code == 201, mine_shift.text
    refused = {
        "plan a shift": client.post(
            "/shifts",
            json={
                "location_id": south,
                "user_id": coach,
                "starts_at": at(3, 9),
                "ends_at": at(3, 12),
            },
            headers=mine,
        ),
        "move a shift there": client.patch(
            f"/shifts/{mine_shift.json()['id']}", json={"location_id": south}, headers=mine
        ),
        "edit its shift": client.patch(f"/shifts/{south_shift}", json={"note": "x"}, headers=mine),
        "delete its shift": client.delete(f"/shifts/{south_shift}", headers=mine),
        "add a station": client.post(
            "/stations", json={"location_id": south, "name": "Hall 2"}, headers=mine
        ),
        "rename its station": client.patch(
            f"/stations/{south_station}", json={"name": "Mine"}, headers=mine
        ),
        "delete its station": client.delete(f"/stations/{south_station}", headers=mine),
        "delete its template": client.delete(
            f"/shift-templates/{south_template.json()['id']}", headers=mine
        ),
        "read its hours": client.get(f"/locations/{south}/hours", headers=mine),
        "set its hours": client.put(
            f"/locations/{south}/hours", json={"intervals": []}, headers=mine
        ),
        "read its coverage rules": client.get(f"/locations/{south}/coverage-rules", headers=mine),
    }
    for name, response in refused.items():
        assert response.status_code in (404, 422), f"{name}: {response.status_code}"
    # The refusals changed nothing.
    assert client.get("/stations", headers=owner).json()[0]["name"] == "Hall"
    assert len(client.get("/shift-templates", headers=owner).json()) == 1
    assert (
        len(
            client.get(
                "/shifts", params={"start": local_today().isoformat(), "days": 14}, headers=owner
            ).json()
        )
        == 2
    )

    # They see only their branch's roster and stations, and publishing reaches only it.
    window = {"start": local_today().isoformat(), "days": 14}
    assert [
        s["location_id"] for s in client.get("/shifts", params=window, headers=mine).json()
    ] == [north]
    assert client.get("/stations", headers=mine).json() == []
    assert client.get("/shift-templates", headers=mine).json() == []
    published = client.post("/shifts/publish", json=window, headers=mine)
    assert published.json() == {"published": 1}
    still_draft = client.get("/shifts", params=window, headers=owner).json()
    assert sorted(s["published"] for s in still_draft) == [False, True]
    assert {s["location_id"] for s in still_draft if not s["published"]} == {south}
    # Naming the other branch explicitly publishes nothing either.
    assert client.post(
        "/shifts/publish", json={**window, "location_id": [south]}, headers=mine
    ).json() == {"published": 0}


def test_managers_and_owners_are_never_kept_to_branches(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, branches: dict
) -> None:
    # A manager listed against one branch still works across all of them.
    manager = member_at_north(client, auth, engine, studio, branches)
    assert client.get(f"/sessions/{branches['south_session']}", headers=manager).status_code == 200
    assert client.get(f"/clients/{branches['south_client']}", headers=manager).status_code == 200
    assert {b["id"] for b in client.get("/locations", headers=manager).json()} == {
        branches["north"],
        branches["south"],
    }
    moved = client.patch(
        f"/sessions/{branches['south_session']}",
        json={"location_id": branches["north"]},
        headers=manager,
    )
    assert moved.status_code == 200, moved.text
    assert UUID(moved.json()["location_id"]) == UUID(branches["north"])


def test_everything_filed_under_a_client_follows_the_clients_branch(
    client: TestClient,
    auth: AuthHeaders,
    engine: Engine,
    studio: dict,
    branches: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Notes, documents, health declarations, dependents, receipts and quotes (GL2)."""
    monkeypatch.setitem(CATALOG, "fitness", replace(CATALOG["fitness"], dependents="pet"))
    owner = branches["owner"]
    mine = member_at_north(client, auth, engine, studio, branches)
    north, south = branches["north_client"], branches["south_client"]

    # One of each under the other branch's client, made by the owner.
    note = client.post(f"/clients/{south}/notes", json={"body": "hi"}, headers=owner)
    assert note.status_code == 201, note.text
    document = client.post(
        f"/clients/{south}/documents",
        files={"file": ("a.txt", b"hello", "text/plain")},
        headers=owner,
    )
    assert document.status_code == 201, document.text
    dependent = client.post(f"/clients/{south}/dependents", json={"name": "Rex"}, headers=owner)
    assert dependent.status_code == 201, dependent.text
    sale = sell(client, studio, south)
    quote = new_quote(client, owner, south)
    with engine.begin() as connection:
        declaration = connection.execute(
            text("""
                INSERT INTO app.health_declarations
                    (tenant_id, client_id, form_key, locale, answers, statement, all_clear,
                     signed_name, valid_until, status)
                VALUES (:t, :c, 'par_q', 'en', '{}', 's', false, 'Sam South',
                        current_date + 30, 'needs_review')
                RETURNING id
            """),
            {"t": studio["tenant_id"], "c": south},
        ).scalar_one()

    hidden = [
        client.get(f"/clients/{south}/notes", headers=mine),
        client.post(f"/clients/{south}/notes", json={"body": "x"}, headers=mine),
        client.delete(f"/clients/{south}/notes/{note.json()['id']}", headers=mine),
        client.get(f"/clients/{south}/documents", headers=mine),
        client.post(
            f"/clients/{south}/documents",
            files={"file": ("b.txt", b"x", "text/plain")},
            headers=mine,
        ),
        client.get(f"/documents/{document.json()['id']}/file", headers=mine),
        client.patch(f"/documents/{document.json()['id']}", json={"shared": True}, headers=mine),
        client.delete(f"/documents/{document.json()['id']}", headers=mine),
        client.get(f"/clients/{south}/health-declarations", headers=mine),
        client.post(
            f"/health-declarations/{declaration}/review", json={"approve": True}, headers=mine
        ),
        client.get(f"/clients/{south}/dependents", headers=mine),
        client.post(f"/clients/{south}/dependents", json={"name": "Max"}, headers=mine),
        client.patch(f"/dependents/{dependent.json()['id']}", json={"name": "Z"}, headers=mine),
        client.get(f"/receipts/{sale['receipt_id']}", headers=mine),
        client.get("/receipts", params={"client_id": south}, headers=mine),
        client.get(f"/quotes/{quote['id']}", headers=mine),
        client.put(f"/quotes/{quote['id']}", json=quote_body(south), headers=mine),
        client.post(f"/quotes/{quote['id']}/send", headers=mine),
        client.post(f"/quotes/{quote['id']}/copy", headers=mine),
        client.get("/quotes", params={"client_id": south}, headers=mine),
        client.post("/quotes", json=quote_body(south), headers=mine),
    ]
    assert [r.status_code for r in hidden] == [404] * len(hidden), [r.text for r in hidden]

    # Unfiltered lists leave the other branch's rows out.
    assert client.get("/receipts", headers=mine).json() == []
    assert client.get("/quotes", headers=mine).json() == []
    # ... but the member's own branch works throughout.
    assert (
        client.post(f"/clients/{north}/notes", json={"body": "ok"}, headers=mine).status_code == 201
    )
    assert client.get(f"/clients/{north}/dependents", headers=mine).status_code == 200
    assert client.post("/quotes", json=quote_body(north), headers=mine).status_code == 201
    assert len(client.get("/quotes", headers=mine).json()) == 1

    # The owner still sees everything.
    assert client.get(f"/receipts/{sale['receipt_id']}", headers=owner).status_code == 200
    assert len(client.get("/quotes", headers=owner).json()) == 2


def test_client_sub_routes_added_for_gl2_follow_the_clients_branch(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, branches: dict
) -> None:
    """Consent trail, addresses, retainer and entitlements (export/erase are owner-only)."""
    mine = member_at_north(client, auth, engine, studio, branches)
    south = branches["south_client"]

    hidden = [
        client.get(f"/clients/{south}/consent-events", headers=mine),
        client.put(
            f"/clients/{south}/marketing-consent",
            json={"consent": True, "source": "desk_other"},
            headers=mine,
        ),
        client.get(f"/clients/{south}/addresses", headers=mine),
        client.get(f"/clients/{south}/retainer", headers=mine),
        client.get(f"/clients/{south}/entitlements", headers=mine),
    ]
    codes = [r.status_code for r in hidden]
    assert codes == [404] * len(hidden), [r.text for r in hidden]
    assert (
        client.get(f"/clients/{branches['north_client']}/consent-events", headers=mine).status_code
        == 200
    )
