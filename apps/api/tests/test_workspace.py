"""The workspace upgrade's people and structure: profiles, business identity, organization,
opening hours, shifts and branch comparisons (docs/proposals/crm-upgrade-2026-10.md)."""

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, add_member, local_today

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def at(day_offset: int, hour: int, minute: int = 0) -> str:
    day = local_today() + timedelta(days=day_offset)
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo("Asia/Jerusalem"))
    return local.isoformat()


def test_a_person_manages_their_own_profile_and_picture(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    owner = auth(studio["owner"])
    me = client.patch("/me", json={"phone": "050-1234567", "palette": "ocean"}, headers=owner)
    assert me.status_code == 200
    assert (me.json()["phone"], me.json()["palette"], me.json()["avatar_url"]) == (
        "050-1234567",
        "ocean",
        None,
    )
    # Fields left out stay as they were.
    client.patch("/me", json={"full_name": "Noa"}, headers=owner)
    assert client.get("/me", headers=owner).json()["palette"] == "ocean"
    assert client.patch("/me", json={"palette": "pink"}, headers=owner).status_code == 422

    # Own colors: three picks, kept when a preset is chosen again.
    own = {"background": "#101820", "text": "#f0f0f0", "accent": "#22d3ee"}
    assert client.patch("/me", json={"palette": "custom"}, headers=owner).status_code == 422
    bad_color = {**own, "accent": "cyan"}
    assert (
        client.patch(
            "/me", json={"palette": "custom", "palette_colors": bad_color}, headers=owner
        ).status_code
        == 422
    )
    saved = client.patch("/me", json={"palette": "custom", "palette_colors": own}, headers=owner)
    assert (saved.json()["palette"], saved.json()["palette_colors"]) == ("custom", own)
    back = client.patch("/me", json={"palette": "forest"}, headers=owner).json()
    assert (back["palette"], back["palette_colors"]) == ("forest", own)

    bad = client.put(
        "/me/avatar", files={"file": ("a.png", b"GIF89a....", "image/png")}, headers=owner
    )
    assert bad.status_code == 415
    me = client.put("/me/avatar", files={"file": ("a.png", PNG, "image/png")}, headers=owner).json()
    assert me["avatar_url"].startswith("/me/avatar?v=")
    picture = client.get("/me/avatar", headers=owner)
    assert picture.content == PNG and picture.headers["content-type"] == "image/png"
    assert "private" in picture.headers["cache-control"]

    # The team sees it; another business does not.
    coach = auth(studio["coach"], studio["tenant_id"])
    team = client.get("/staff", headers=studio["headers"]).json()["members"]
    owner_row = next(m for m in team if m["user_id"] == str(studio["owner"]))
    assert owner_row["avatar_url"].startswith(f"/staff/{studio['owner']}/avatar")
    assert client.get(f"/staff/{studio['owner']}/avatar", headers=coach).content == PNG
    stranger = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(stranger)).json()
    their = auth(stranger, other["id"])
    assert client.get(f"/staff/{studio['owner']}/avatar", headers=their).status_code == 404

    assert client.delete("/me/avatar", headers=owner).json()["avatar_url"] is None
    assert client.get("/me/avatar", headers=owner).status_code == 404


def test_the_business_number_is_validated_and_kept_from_the_team(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers = studio["headers"]
    wrong = client.patch("/tenants/current", json={"business_number": "123456789"}, headers=headers)
    assert wrong.status_code == 422 and wrong.json()["detail"] == "invalid_business_number"
    # 515555555 has a valid Israeli check digit; spaces and dashes are dropped.
    tenant = client.patch(
        "/tenants/current",
        json={"legal_entity_type": "company", "business_number": "51-555 5555"},
        headers=headers,
    ).json()
    assert (tenant["legal_entity_type"], tenant["business_number"]) == ("company", "515555555")
    coach = client.get("/tenants/current", headers=auth(studio["coach"], studio["tenant_id"]))
    assert coach.json()["business_number"] is None and coach.json()["legal_entity_type"] is None
    cleared = client.patch("/tenants/current", json={"business_number": ""}, headers=headers)
    assert cleared.json()["business_number"] is None


def test_the_workspace_cover_is_for_the_team(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers = studio["headers"]
    tenant = client.put(
        "/tenants/current/cover", files={"file": ("c.png", PNG, "image/png")}, headers=headers
    ).json()
    assert tenant["cover_url"].startswith("/tenants/current/cover?v=")
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/tenants/current/cover", headers=coach).content == PNG
    assert (
        client.put(
            "/tenants/current/cover", files={"file": ("c.png", PNG, "image/png")}, headers=coach
        ).status_code
        == 403
    )
    client.delete("/tenants/current/cover", headers=headers)
    assert client.get("/tenants/current/cover", headers=coach).status_code == 404


def test_reporting_lines_never_loop_and_grant_nothing(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    headers = studio["headers"]
    owner, coach = str(studio["owner"]), str(studio["coach"])
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "staff")

    def set_org(user: object, body: dict):
        return client.patch(f"/staff/{user}/organization", json=body, headers=headers)

    member = set_org(manager, {"job_title": "Branch manager", "reports_to": owner}).json()
    assert (member["job_title"], member["reports_to"]) == ("Branch manager", owner)
    set_org(coach, {"reports_to": str(manager), "job_title": "Coach"})

    # The owner cannot report to someone who (through others) reports to them.
    loop = set_org(owner, {"reports_to": coach})
    assert loop.status_code == 422 and loop.json()["detail"] == "reporting_cycle"
    assert set_org(owner, {"reports_to": owner}).status_code == 422
    assert set_org(owner, {"reports_to": str(uuid4())}).status_code == 422

    # Reporting to someone changes no permission, and only managers set it.
    as_manager = auth(manager, studio["tenant_id"])
    assert client.get("/staff", headers=as_manager).status_code == 403
    assert set_org(coach, {"job_title": "x"}).status_code == 200
    assert (
        client.patch(
            f"/staff/{coach}/organization", json={"job_title": "x"}, headers=as_manager
        ).status_code
        == 403
    )

    # A member who leaves leaves no dangling line.
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM app.tenant_members WHERE user_id = :u"), {"u": manager}
        )
    team = client.get("/staff", headers=headers).json()["members"]
    assert next(m for m in team if m["user_id"] == coach)["reports_to"] is None


def test_opening_hours_have_breaks_and_no_overlaps(client: TestClient, studio: dict) -> None:
    headers, branch = studio["headers"], studio["location"]["id"]
    week = {
        "intervals": [
            {"weekday": 0, "opens": "08:00", "closes": "13:00"},
            {"weekday": 0, "opens": "16:00", "closes": "20:00"},
            {"weekday": 4, "opens": "08:00", "closes": "14:00"},
        ]
    }
    saved = client.put(f"/locations/{branch}/hours", json=week, headers=headers)
    assert saved.status_code == 200 and len(saved.json()["intervals"]) == 3
    overlapping = {
        "intervals": [*week["intervals"], {"weekday": 0, "opens": "12:00", "closes": "17:00"}]
    }
    assert (
        client.put(f"/locations/{branch}/hours", json=overlapping, headers=headers).status_code
        == 422
    )
    assert client.get(f"/locations/{branch}/hours", headers=headers).json() == saved.json()


def test_shifts_refuse_double_booking_and_flag_time_off(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers, branch, coach = studio["headers"], studio["location"]["id"], str(studio["coach"])
    shift = {"user_id": coach, "location_id": branch, "starts_at": at(1, 9), "ends_at": at(1, 15)}
    created = client.post("/shifts", json={**shift, "position": "Reception"}, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert (body["position"], body["on_time_off"], body["outside_hours"]) == (
        "Reception",
        False,
        False,
    )

    clash = client.post(
        "/shifts", json={**shift, "starts_at": at(1, 14), "ends_at": at(1, 18)}, headers=headers
    )
    assert clash.status_code == 409 and clash.json()["detail"] == "shift_overlap"
    later = client.post(
        "/shifts", json={**shift, "starts_at": at(1, 15), "ends_at": at(1, 18)}, headers=headers
    )
    assert later.status_code == 201

    # Time off and opening hours are warnings on the shift, not refusals.
    day = (local_today() + timedelta(days=1)).isoformat()
    client.post(
        f"/staff/{coach}/time-off", json={"starts_on": day, "ends_on": day}, headers=headers
    )
    client.put(
        f"/locations/{branch}/hours",
        json={
            "intervals": [
                {
                    "weekday": (local_today() + timedelta(days=1)).weekday(),
                    "opens": "10:00",
                    "closes": "16:00",
                }
            ]
        },
        headers=headers,
    )
    listed = client.get(
        "/shifts", params={"start": local_today().isoformat()}, headers=headers
    ).json()
    assert [s["on_time_off"] for s in listed] == [True, True]
    assert [s["outside_hours"] for s in listed] == [True, True]

    # Moving a shift onto another of the same person is refused; deleting works.
    moved = client.patch(f"/shifts/{body['id']}", json={"ends_at": at(1, 16)}, headers=headers)
    assert moved.status_code == 409
    assert (
        client.patch(f"/shifts/{body['id']}", json={"note": "Opens"}, headers=headers).json()[
            "note"
        ]
        == "Opens"
    )

    # The team reads shifts; only managers plan them.
    coach_headers = auth(studio["coach"], studio["tenant_id"])
    assert (
        len(
            client.get(
                "/shifts", params={"start": local_today().isoformat()}, headers=coach_headers
            ).json()
        )
        == 2
    )
    assert client.post("/shifts", json=shift, headers=coach_headers).status_code == 403
    assert client.delete(f"/shifts/{body['id']}", headers=headers).status_code == 204


def test_a_week_of_shifts_is_copied_without_clashes(client: TestClient, studio: dict) -> None:
    headers, branch, coach = studio["headers"], studio["location"]["id"], str(studio["coach"])
    for day in (0, 1):
        client.post(
            "/shifts",
            json={
                "user_id": coach,
                "location_id": branch,
                "starts_at": at(day, 8),
                "ends_at": at(day, 12),
            },
            headers=headers,
        )
    # One already planned next week clashes with a copy.
    client.post(
        "/shifts",
        json={
            "user_id": coach,
            "location_id": branch,
            "starts_at": at(7, 10),
            "ends_at": at(7, 11),
        },
        headers=headers,
    )
    today = local_today()
    copied = client.post(
        "/shifts/copy-week",
        json={"from_week": today.isoformat(), "to_week": (today + timedelta(days=7)).isoformat()},
        headers=headers,
    ).json()
    # Shifts from the earlier days of this week are copied too; the clash is skipped.
    assert copied["skipped"] >= 1 and copied["created"] >= 0
    next_week = client.get(
        "/shifts",
        params={"start": (today + timedelta(days=7)).isoformat(), "days": 1},
        headers=headers,
    ).json()
    assert len(next_week) == 1  # the one planned by hand, not a clashing copy


def test_branch_comparison_and_calendars_stay_within_the_persons_branches(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    headers = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    start, end = local_today().isoformat(), local_today().isoformat()

    compared = client.get(
        "/metrics/branches",
        params={"start": start, "end": end, "keys": ["revenue", "new_clients"]},
        headers=headers,
    ).json()
    assert [b["name"] for b in compared] == ["Main", "South"]
    assert [m["key"] for m in compared[0]["metrics"]] == ["revenue", "new_clients"]

    # A manager kept to one branch compares only that one (managers see all; use a custom role).
    keeper = uuid4()
    add_member(engine, studio["tenant_id"], keeper, "staff")
    with engine.begin() as connection:
        role = connection.execute(
            text("""
                INSERT INTO app.tenant_roles (tenant_id, name, permissions)
                VALUES (:t, 'Branch lead', ARRAY['reports.read', 'schedule.read']) RETURNING id
            """),
            {"t": studio["tenant_id"]},
        ).scalar_one()
        connection.execute(
            text("""
                UPDATE app.tenant_members
                SET custom_role_id = :r, location_ids = ARRAY[CAST(:b AS uuid)]
                WHERE user_id = :u
            """),
            {"r": role, "b": south, "u": keeper},
        )
    theirs = client.get(
        "/metrics/branches",
        params={"start": start, "end": end},
        headers=auth(keeper, studio["tenant_id"]),
    ).json()
    assert [b["name"] for b in theirs] == ["South"]

    # The calendar filters by several branches at once.
    service = studio["service"]["id"]
    for branch in (north, south):
        client.post(
            "/sessions",
            json={
                "service_id": service,
                "location_id": branch,
                "date": (local_today() + timedelta(days=1)).isoformat(),
                "start_time": "10:00",
                "capacity": 5,
            },
            headers=headers,
        )
    week = {"start": local_today().isoformat()}
    assert len(client.get("/sessions", params=week, headers=headers).json()) == 2
    only_south = client.get(
        "/sessions", params={**week, "location_id": [south]}, headers=headers
    ).json()
    assert [s["location_id"] for s in only_south] == [south]
    both = client.get(
        "/sessions", params={**week, "location_id": [north, south]}, headers=headers
    ).json()
    assert len(both) == 2
