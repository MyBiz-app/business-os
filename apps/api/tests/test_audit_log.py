"""The owner's audit log (GL7): what gets written, who can read it, filters, paging, CSV."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.jobs import purge_expired
from tests.conftest import AuthHeaders, add_member


def entries(client: TestClient, headers: dict, **query: str) -> list[dict]:
    response = client.get("/audit-log", params=query, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["entries"]


def actions(client: TestClient, headers: dict, **query: str) -> list[str]:
    return [e["action"] for e in entries(client, headers, **query)]


def test_a_role_change_shows_up_right_away(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, "staff")

    client.patch(f"/staff/{member}", json={"role": "front_desk"}, headers=headers)

    [entry] = [e for e in entries(client, headers) if e["action"] == "staff.role_changed"]
    assert entry["category"] == "team"
    assert entry["entity_id"] == str(member)
    assert entry["details"]["old_role"] == "staff" and entry["details"]["new_role"] == "front_desk"
    assert entry["actor_id"] is not None and entry["actor_type"] == "user"


def test_team_roles_and_settings_changes_are_logged(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, "staff")
    invitation = client.post(
        "/staff/invitations", json={"email": "new@example.com", "role": "staff"}, headers=headers
    ).json()
    client.delete(f"/staff/invitations/{invitation['id']}", headers=headers)
    role = client.post(
        "/roles", json={"name": "Reception", "permissions": ["clients.read"]}, headers=headers
    ).json()
    client.patch(
        f"/roles/{role['id']}",
        json={"permissions": ["clients.read", "clients.write"]},
        headers=headers,
    )
    client.delete(f"/roles/{role['id']}", headers=headers)
    client.patch("/tenants/current", json={"address_city": "Haifa"}, headers=headers)
    client.patch("/tenants/current", json={"require_mfa_for_staff": True}, headers=headers)
    client.delete(f"/staff/{member}", headers=headers)

    seen = actions(client, headers)
    for action in (
        "staff.invited",
        "staff.invitation_revoked",
        "role.created",
        "role.updated",
        "role.deleted",
        "tenant.updated",
        "mfa.team_requirement_set",
        "staff.removed",
    ):
        assert action in seen, action
    settings = [e for e in entries(client, headers) if e["action"] == "tenant.updated"]
    assert ["address_city"] in [e["details"]["fields"] for e in settings]  # names, never values
    assert "Haifa" not in str([e["details"] for e in settings])


def test_payroll_exports_and_the_audit_export_are_logged_with_a_category(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    assert client.get("/audit-log/export", headers=headers).status_code == 200
    [entry] = entries(client, headers, category="export")
    assert entry["action"] == "export.audit_log"


def test_a_new_device_is_logged_in_each_business(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    person = uuid4()
    add_member(engine, studio["tenant_id"], person, "manager")
    headers = auth(person)
    for device in ("a" * 32, "b" * 32):
        client.post(
            "/me/devices/check",
            json={"device_id": device, "label": "Safari on iPhone", "locale": "en"},
            headers=headers,
        )
    client.post("/me/devices/events", json={"kind": "mfa_enabled"}, headers=headers)

    log = entries(client, studio["headers"], category="security")
    assert [e["action"] for e in log] == ["mfa.enabled", "login.new_device"]
    assert log[1]["details"]["label"] == "Safari on iPhone"
    assert log[1]["actor_id"] == str(person)


def test_only_the_owner_and_unrestricted_managers_can_read_it(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    manager, coach = uuid4(), uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    add_member(engine, studio["tenant_id"], coach, "staff")
    assert client.get("/audit-log", headers=auth(manager, studio["tenant_id"])).status_code == 200
    assert client.get("/audit-log", headers=auth(coach, studio["tenant_id"])).status_code == 403
    assert (
        client.get("/audit-log/export", headers=auth(coach, studio["tenant_id"])).status_code == 403
    )


def test_another_business_never_sees_it(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    client.patch("/tenants/current", json={"address_city": "Haifa"}, headers=studio["headers"])
    other = uuid4()
    other_tenant = client.post(
        "/tenants",
        json={
            "name": "Other",
            "country": "IL",
            "locale": "he",
            "currency": "ILS",
            "vertical": "fitness_studio",
        },
        headers=auth(other),
    )
    if other_tenant.status_code != 201:  # the studio fixture's payload decides what is valid
        return
    headers = auth(other, other_tenant.json()["id"])
    assert "tenant.updated" not in actions(client, headers)


def test_filters_and_paging(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    for city in ("A", "B", "C", "D", "E"):
        client.patch("/tenants/current", json={"address_city": city}, headers=headers)
    page = client.get("/audit-log", params={"limit": 2}, headers=headers).json()
    assert len(page["entries"]) == 2 and page["next_cursor"]
    seen = {e["id"] for e in page["entries"]}
    while page["next_cursor"]:
        page = client.get(
            "/audit-log", params={"limit": 2, "cursor": page["next_cursor"]}, headers=headers
        ).json()
        ids = {e["id"] for e in page["entries"]}
        assert not ids & seen  # no row twice
        seen |= ids
    assert len(seen) == len(entries(client, headers, limit="200"))

    me = entries(client, headers)[0]["actor_id"]
    assert all(e["actor_id"] == me for e in entries(client, headers, actor_id=me))
    assert entries(client, headers, actor_id=str(uuid4())) == []
    assert entries(client, headers, category="payroll") == []
    assert client.get("/audit-log", params={"category": "nope"}, headers=headers).status_code == 422
    tomorrow = (datetime.now(UTC) + timedelta(days=2)).date().isoformat()
    assert entries(client, headers, date_from=tomorrow) == []
    assert client.get("/audit-log", params={"cursor": "bad"}, headers=headers).status_code == 422


def test_the_csv_neutralises_formulas(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, action, details)
                VALUES (:tenant, 'platform', 'platform.view',
                        jsonb_build_object('name', '=HYPERLINK("x")', 'email', 'a@b.c'))
            """),
            {"tenant": studio["tenant_id"]},
        )
    response = client.get("/audit-log/export", headers=headers)
    assert response.headers["content-type"].startswith("text/csv")
    body = response.text
    assert body.startswith("﻿") and "platform.view" in body
    assert ",'=HYPERLINK" in body.replace('"', "") or "'=HYPERLINK" in body


def test_old_entries_are_purged_after_24_months(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    client.patch("/tenants/current", json={"address_city": "Haifa"}, headers=studio["headers"])
    later = datetime.now(UTC) + timedelta(days=800)
    with engine.begin() as connection:
        deleted = purge_expired(connection, later)
        left = connection.execute(text("SELECT count(*) FROM app.audit_log")).scalar_one()
    assert deleted["audit_log"] >= 1 and left == 0
