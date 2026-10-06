from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_leads import with_crm
from tests.test_reports import demo


def kinds(response) -> dict[str, dict]:
    assert response.status_code == 200, response.text
    return {entry["kind"]: entry for entry in response.json()}


def test_retention_lists_come_from_the_demo(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    studio = demo(engine, auth)

    lists = kinds(client.get("/attention", headers=studio["headers"]))

    assert {"inactive", "plan_ending"} <= lists.keys()
    for entry in (lists["inactive"], lists["plan_ending"]):
        assert len(entry["items"]) == min(5, entry["count"])  # at most five shown, all counted
    ends = [item["date"] for item in lists["plan_ending"]["items"]]
    assert all(end is not None and end >= local_today().isoformat() for end in ends)


def test_leads_due_today_or_overdue(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    yesterday = (local_today() - timedelta(days=1)).isoformat()
    tomorrow = (local_today() + timedelta(days=1)).isoformat()
    for name, follow_up, stage in (
        ("Due", yesterday, "new"),
        ("Later", tomorrow, "new"),
        ("Lost", yesterday, "lost"),
    ):
        created = client.post(
            "/leads", json={"first_name": name, "follow_up_on": follow_up}, headers=headers
        )
        assert created.status_code == 201, created.text
        if stage != "new":
            moved = client.post(
                f"/leads/{created.json()['id']}/stage", json={"stage": stage}, headers=headers
            )
            assert moved.status_code == 200, moved.text

    lists = kinds(client.get("/attention", headers=headers))

    assert lists["leads_due"]["count"] == 1
    assert [item["name"] for item in lists["leads_due"]["items"]] == ["Due"]


def test_each_list_needs_its_permission(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    studio = demo(engine, auth)
    coach = uuid4()
    add_member(engine, studio["tenant_id"], coach, "staff")

    lists = kinds(client.get("/attention", headers=auth(coach, studio["tenant_id"])))

    assert "inactive" not in lists and "plan_ending" not in lists
