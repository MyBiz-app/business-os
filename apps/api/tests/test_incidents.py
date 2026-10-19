from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, make_staff

BANNER = {
    "kind": "incident",
    "content": {
        "he": {"title": "תקלה בהתחברות", "body": "אנחנו מטפלים בזה"},
        "en": {"title": "Sign-in problem", "body": "We are on it"},
    },
    "status_url": "https://status.mybiz.test",
}


def test_a_banner_is_public_until_the_team_resolves_it(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    team = uuid4()
    make_staff(engine, team, "owner")
    assert client.get("/public/incidents").json() == []

    opened = client.post("/platform/incidents", json=BANNER, headers=auth(team))
    assert opened.status_code == 201, opened.text
    incident_id = opened.json()["id"]

    shown = client.get("/public/incidents").json()
    assert [row["id"] for row in shown] == [incident_id]
    assert shown[0]["content"]["en"]["title"] == "Sign-in problem"
    assert shown[0]["status_url"] == "https://status.mybiz.test"
    assert "created_by" not in shown[0]

    resolved = client.post(f"/platform/incidents/{incident_id}/resolve", headers=auth(team))
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None
    assert client.get("/public/incidents").json() == []
    # Resolving twice is a 404, and the history keeps the banner.
    again = client.post(f"/platform/incidents/{incident_id}/resolve", headers=auth(team))
    assert again.status_code == 404
    [kept] = client.get("/platform/incidents", headers=auth(team)).json()
    assert kept["id"] == incident_id


def test_only_the_incident_permission_opens_a_banner(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    allowed, plain = uuid4(), uuid4()
    make_staff(engine, allowed, "employee", ("incidents.manage",))
    make_staff(engine, plain, "employee", ("inbox.manage", "broadcasts.manage"))
    assert client.post("/platform/incidents", json=BANNER, headers=auth(allowed)).status_code == 201
    assert client.post("/platform/incidents", json=BANNER, headers=auth(plain)).status_code == 403
    assert client.get("/platform/incidents", headers=auth(plain)).status_code == 403
    # A business owner is not on the team.
    assert (
        client.post("/platform/incidents", json=BANNER, headers=studio["headers"]).status_code
        == 403
    )


def test_a_banner_needs_a_title_and_a_real_address(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    team = uuid4()
    make_staff(engine, team, "owner")
    blank = {**BANNER, "content": {"he": {"title": " ", "body": "x"}}}
    assert client.post("/platform/incidents", json=blank, headers=auth(team)).status_code == 422
    bad = {**BANNER, "status_url": "javascript:alert(1)"}
    assert client.post("/platform/incidents", json=bad, headers=auth(team)).status_code == 422
