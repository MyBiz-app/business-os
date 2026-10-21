"""Console access rules: who sees which page, in step with the menu (slice K1)."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, make_staff


def test_incident_banners_have_their_own_permission(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner, announcer, plain = uuid4(), uuid4(), uuid4()
    make_staff(engine, owner, "owner")
    make_staff(engine, announcer, "employee", ("broadcasts.manage",))
    make_staff(engine, plain, "employee", ("incidents.manage",))
    # Messaging businesses no longer opens a banner; the new permission does. Owners hold it.
    assert client.get("/platform/incidents", headers=auth(announcer)).status_code == 403
    assert client.get("/platform/incidents", headers=auth(plain)).status_code == 200
    me = client.get("/platform/me", headers=auth(owner)).json()
    assert "incidents.manage" in me["permissions"]
    assert client.get("/platform/broadcasts", headers=auth(plain)).status_code == 403


def test_one_business_by_id(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    reader, blind = uuid4(), uuid4()
    make_staff(engine, reader, "employee", ("businesses.read",))
    make_staff(engine, blind, "employee", ("inbox.manage",))
    tenant = str(studio["tenant_id"])
    one = client.get(f"/platform/businesses/{tenant}", headers=auth(reader))
    assert one.status_code == 200
    assert one.json()["id"] == tenant
    listed = client.get("/platform/businesses", headers=auth(reader)).json()
    assert one.json() == next(row for row in listed if row["id"] == tenant)
    assert client.get(f"/platform/businesses/{uuid4()}", headers=auth(reader)).status_code == 404
    assert client.get(f"/platform/businesses/{tenant}", headers=auth(blind)).status_code == 403
    outsider = client.get(f"/platform/businesses/{tenant}", headers=studio["headers"])
    assert outsider.status_code == 403


def test_owner_only_pages_stay_owner_only_in_the_api(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner, manager, employee = uuid4(), uuid4(), uuid4()
    make_staff(engine, owner, "owner")
    make_staff(engine, manager, "manager", ("staff.manage", "usage.read"))
    make_staff(engine, employee, "employee", ("businesses.read",))
    for path in ("/platform/integrations", "/platform/audit"):
        assert client.get(path, headers=auth(owner)).status_code == 200, path
        for member in (manager, employee):
            denied = client.get(path, headers=auth(member))
            assert denied.status_code == 403, path
            assert denied.json()["detail"] == "owners_only"


def test_the_support_template_gives_a_ready_made_set(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner = uuid4()
    make_staff(engine, owner, "owner")
    templates = client.get("/platform/staff-templates", headers=auth(owner)).json()
    support = next(t for t in templates if t["key"] == "support")
    assert set(support["permissions"]) == {
        "businesses.read",
        "inbox.manage",
        "incidents.manage",
    }
    saved = client.put(
        "/platform/staff/helper@example.com",
        json={"level": "employee", "template": "support", "permissions": ["usage.read"]},
        headers=auth(owner),
    )
    assert saved.status_code == 200, saved.text
    row = next(m for m in saved.json() if m["email"] == "helper@example.com")
    assert set(row["permissions"]) == {*support["permissions"], "usage.read"}
