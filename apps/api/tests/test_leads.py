from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import STUDIO, AuthHeaders
from tests.test_client_app import join_code


def with_crm(client: TestClient, studio: dict) -> None:
    response = client.put(
        "/tenants/current/modules", json={"modules": {"crm": 1}}, headers=studio["headers"]
    )
    assert response.status_code == 200, response.text


def test_leads_need_the_crm_module(client: TestClient, studio: dict) -> None:
    off = client.get("/leads", headers=studio["headers"])
    assert off.status_code == 403 and off.json()["detail"] == "module_disabled"
    with_crm(client, studio)
    assert client.get("/leads", headers=studio["headers"]).status_code == 200


def test_pipeline_from_new_lead_to_client(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    created = client.post(
        "/leads",
        json={
            "first_name": "Noa",
            "last_name": "Bar",
            "email": "Noa@Example.com",
            "phone": "050-1111111",
            "interest": "Mornings",
            "source": "instagram",
            "owner_user_id": str(studio["owner"]),
            "follow_up_on": "2020-01-01",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    lead = created.json()
    assert lead["stage"] == "new" and lead["email"] == "noa@example.com"
    assert [a["kind"] for a in lead["activities"]] == ["created"]

    moved = client.post(f"/leads/{lead['id']}/stage", json={"stage": "trial"}, headers=headers)
    noted = client.post(
        f"/leads/{lead['id']}/activities",
        json={"kind": "call", "note": "Booked a trial class"},
        headers=headers,
    )
    assert moved.json()["stage"] == "trial"
    assert [a["kind"] for a in noted.json()["activities"]] == ["call", "stage", "created"]

    # "Won" means converting: the lead becomes a client.
    win = client.post(f"/leads/{lead['id']}/stage", json={"stage": "won"}, headers=headers)
    assert win.status_code == 409 and win.json()["detail"] == "convert_to_win"
    converted = client.post(f"/leads/{lead['id']}/convert", headers=headers).json()
    assert converted["stage"] == "won" and converted["client_id"]
    new_client = client.get(f"/clients/{converted['client_id']}", headers=headers).json()
    assert (new_client["first_name"], new_client["email"], new_client["source"]) == (
        "Noa", "noa@example.com", "instagram"
    )  # fmt: skip

    board = client.get("/leads", headers=headers).json()
    assert {c["stage"]: c["count"] for c in board["counts"]}["won"] == 1
    assert board["won_last_30_days"] == 1 and board["conversion_rate"] == 1.0
    assert board["follow_ups_due"] == 0  # closed leads don't need a follow-up


def test_converting_links_an_existing_client(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    existing = client.post(
        "/clients", json={"first_name": "Dana", "email": "dana@example.com"}, headers=headers
    ).json()
    lead = client.post(
        "/leads", json={"first_name": "Dana", "email": "DANA@example.com"}, headers=headers
    ).json()
    converted = client.post(f"/leads/{lead['id']}/convert", headers=headers).json()
    assert converted["client_id"] == existing["id"]


def test_lost_leads_keep_the_reason(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    lead = client.post("/leads", json={"first_name": "Avi"}, headers=headers).json()
    lost = client.post(
        f"/leads/{lead['id']}/stage",
        json={"stage": "lost", "lost_reason": "Too far away"},
        headers=headers,
    ).json()
    assert lost["lost_reason"] == "Too far away"
    board = client.get("/leads", headers=headers).json()
    assert board["conversion_rate"] == 0.0
    assert client.get("/leads", params={"closed_days": 0}, headers=headers).json()["items"] == []


def test_staff_without_clients_write_can_only_look(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    with_crm(client, studio)
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/leads", headers=coach).status_code == 200
    assert client.post("/leads", json={"first_name": "X"}, headers=coach).status_code == 403


def test_owner_must_be_a_member(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    response = client.post(
        "/leads",
        json={"first_name": "X", "owner_user_id": "00000000-0000-0000-0000-000000000001"},
        headers=studio["headers"],
    )
    assert response.status_code == 422


def test_public_inquiry_form(client: TestClient, studio: dict) -> None:
    code = join_code(client, studio)
    inquiry = {"first_name": "Maya", "phone": "052-2222222", "interest": "Pilates for beginners"}

    closed = client.post(f"/public/businesses/{code}/inquiries", json=inquiry)
    assert closed.status_code == 404  # no CRM module, no form
    assert client.get(f"/public/businesses/{code}").json()["inquiries"] is False

    with_crm(client, studio)
    assert client.get(f"/public/businesses/{code}").json()["inquiries"] is True
    for _ in range(3):
        assert client.post(f"/public/businesses/{code}/inquiries", json=inquiry).status_code == 202
    limited = client.post(f"/public/businesses/{code}/inquiries", json=inquiry)
    assert limited.status_code == 429
    bot = client.post(f"/public/businesses/{code}/inquiries", json={**inquiry, "website": "x"})
    assert bot.status_code == 202
    nothing = client.post(f"/public/businesses/{code}/inquiries", json={"first_name": "Q"})
    assert nothing.status_code == 422

    board = client.get("/leads", headers=studio["headers"]).json()
    assert [(i["first_name"], i["source"], i["stage"]) for i in board["items"]] == [
        ("Maya", "form", "new")
    ] * 3


def test_leads_are_isolated_between_businesses(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    with_crm(client, studio)
    lead = client.post("/leads", json={"first_name": "Secret"}, headers=studio["headers"]).json()
    other_owner = uuid4()
    other = client.post(
        "/tenants",
        json={
            "name": "Other",
            "vertical": "fitness",
            "locale": "en",
            "time_zone": "Asia/Jerusalem",
            "currency": "ILS",
        },
        headers=auth(other_owner),
    ).json()
    headers = auth(other_owner, other["id"])
    client.put("/tenants/current/modules", json={"modules": {"crm": 1}}, headers=headers)
    assert client.get(f"/leads/{lead['id']}", headers=headers).status_code == 404
    assert client.get("/leads", headers=headers).json()["items"] == []


def test_lead_owners_are_the_team(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    owners = client.get("/leads/owners", headers=studio["headers"]).json()
    assert {o["user_id"] for o in owners} == {str(studio["owner"]), str(studio["coach"])}


def test_lead_owners_are_this_business_only(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    """The owner's memberships in their other businesses don't repeat them in the list."""
    with_crm(client, studio)
    other = client.post(
        "/tenants", json={**STUDIO, "name": "Second"}, headers=auth(studio["owner"])
    )
    assert other.status_code == 201, other.text
    owners = client.get("/leads/owners", headers=studio["headers"]).json()
    assert sorted(o["user_id"] for o in owners) == sorted(
        [str(studio["owner"]), str(studio["coach"])]
    )
