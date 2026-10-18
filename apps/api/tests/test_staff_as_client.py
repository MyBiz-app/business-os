"""R36: team members who are also clients of their own business."""

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_client_app import join


def sign_up_as_member(client: TestClient, auth: AuthHeaders, user, studio: dict):
    return client.post(
        "/client/businesses/self",
        json={"tenant_id": str(studio["tenant_id"])},
        headers=auth(user),
    )


def test_coach_signs_up_as_client_without_code(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    coach = studio["coach"]

    first = sign_up_as_member(client, auth, coach, studio)
    again = sign_up_as_member(client, auth, coach, studio)

    assert first.status_code == 201, first.text
    assert first.json()["client_id"] == again.json()["client_id"]
    assert [b["id"] for b in client.get("/client/businesses", headers=auth(coach)).json()] == [
        str(studio["tenant_id"])
    ]
    card = client.get(f"/clients/{first.json()['client_id']}", headers=studio["headers"]).json()
    assert card["is_staff"] is True


def test_someone_outside_the_team_cannot_use_the_shortcut(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    stranger = uuid4()

    response = sign_up_as_member(client, auth, stranger, studio)

    assert response.status_code == 404
    assert client.get("/client/businesses", headers=auth(stranger)).json() == []


def test_owner_adds_themselves_in_the_crm(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    first = client.post("/clients/me", headers=studio["headers"])
    again = client.post("/clients/me", headers=studio["headers"])

    assert first.status_code == 201, first.text
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["is_staff"] is True
    # The same card is what the owner sees in the client app.
    businesses = client.get("/client/businesses", headers=auth(studio["owner"])).json()
    assert businesses[0]["client_id"] == first.json()["id"]


def test_staff_card_merges_with_an_existing_one_by_email(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    coach = studio["coach"]
    existing = client.post(
        "/clients",
        json={"first_name": "Coach", "email": f"{coach}@example.com"},
        headers=studio["headers"],
    ).json()

    joined = sign_up_as_member(client, auth, coach, studio).json()

    assert joined["client_id"] == existing["id"]
    assert client.get("/clients", headers=studio["headers"]).json()["total"] == 1


def test_client_list_filter_and_reports_can_leave_staff_out(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    sign_up_as_member(client, auth, studio["coach"], studio)
    code = client.get("/tenants/current", headers=studio["headers"]).json()["join_code"]
    join(client, auth, uuid4(), code)
    headers = studio["headers"]

    everyone = client.get("/clients", headers=headers).json()
    only = client.get("/clients", params={"staff": "only"}, headers=headers).json()
    without = client.get("/clients", params={"staff": "exclude"}, headers=headers).json()

    assert everyone["total"] == 2
    assert [c["is_staff"] for c in only["items"]] == [True]
    assert [c["is_staff"] for c in without["items"]] == [False]

    today = local_today().isoformat()

    def new_clients(**extra: str) -> float:
        rows = client.get(
            "/metrics",
            params={"start": today, "end": today, "keys": "new_clients", **extra},
            headers=headers,
        ).json()
        return rows[0]["value"]

    assert new_clients() == 2
    assert new_clients(exclude_staff="true") == 1


def test_each_area_gives_only_that_areas_permissions(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    coach = studio["coach"]
    sign_up_as_member(client, auth, coach, studio)
    as_staff = auth(coach, studio["tenant_id"])

    # As a client: only their own business view, no team data.
    assert client.get("/client/businesses", headers=auth(coach)).status_code == 200
    # A plain client (not on the team) cannot reach the team area of the same business.
    plain = uuid4()
    code = client.get("/tenants/current", headers=studio["headers"]).json()["join_code"]
    join(client, auth, plain, code)
    assert client.get("/clients", headers=auth(plain, studio["tenant_id"])).status_code in (
        401,
        403,
        404,
    )
    # As staff the coach keeps the staff role's rights and nothing more (no billing, say).
    me = client.get("/me", headers=as_staff).json()
    roles = {m["tenant_id"]: m["role"] for m in me["memberships"]}
    assert roles[str(studio["tenant_id"])] == "staff"
