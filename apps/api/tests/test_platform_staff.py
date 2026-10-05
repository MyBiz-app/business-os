from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, make_staff

PRIMARY = "adire7399@gmail.com"


def staff_member(engine: Engine, level: str = "owner", permissions: tuple[str, ...] = ()):
    user = uuid4()
    return user, make_staff(engine, user, level, permissions)


def emails(response) -> dict[str, str]:
    return {m["email"]: m["level"] for m in response.json()}


def test_the_primary_owner_exists_and_cannot_be_touched(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    owner, _ = staff_member(engine)
    headers = auth(owner)
    team = client.get("/platform/staff", headers=headers)
    assert emails(team)[PRIMARY] == "primary_owner"

    demote = client.put(f"/platform/staff/{PRIMARY}", json={"level": "employee"}, headers=headers)
    assert demote.status_code == 403 and demote.json()["detail"] == "primary_owner_protected"
    remove = client.delete(f"/platform/staff/{PRIMARY}", headers=headers)
    assert remove.status_code == 403
    # Not even straight SQL as the API's database role.
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL ROLE app_api"))
        try:
            connection.execute(
                text("DELETE FROM app.platform_staff WHERE email = :e"), {"e": PRIMARY}
            )
            deleted = True
        except Exception:
            deleted = False
    assert not deleted
    assert emails(client.get("/platform/staff", headers=headers))[PRIMARY] == "primary_owner"


def test_owners_build_the_team(client: TestClient, engine: Engine, auth: AuthHeaders) -> None:
    owner, owner_email = staff_member(engine)
    headers = auth(owner)
    me = client.get("/platform/me", headers=headers).json()
    assert me["level"] == "owner" and "staff.manage" in me["permissions"]

    partner = client.put(
        "/platform/staff/Partner@Example.com", json={"level": "owner"}, headers=headers
    )
    assert emails(partner)["partner@example.com"] == "owner"
    client.put(
        "/platform/staff/maya@example.com",
        json={"level": "manager", "permissions": ["staff.manage", "inbox.manage"]},
        headers=headers,
    )
    added = client.put(
        "/platform/staff/noa@example.com",
        json={"level": "employee", "permissions": ["inbox.manage"]},
        headers=headers,
    ).json()
    noa = next(m for m in added if m["email"] == "noa@example.com")
    assert noa["permissions"] == ["inbox.manage"] and noa["signed_up"] is False

    myself = client.put(
        f"/platform/staff/{owner_email}", json={"level": "employee"}, headers=headers
    )
    assert myself.status_code == 403 and myself.json()["detail"] == "not_yourself"
    bad = client.put(
        "/platform/staff/x@example.com",
        json={"level": "employee", "permissions": ["staff.manage"]},
        headers=headers,
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "employees_do_not_manage_staff"

    audit = client.get("/platform/audit", headers=headers).json()
    assert [a["action"] for a in audit[:3]] == ["staff.added"] * 3
    assert audit[0]["actor_email"] == owner_email


def test_managers_manage_employees_with_what_they_hold(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    manager, _ = staff_member(engine, "manager", ("staff.manage", "inbox.manage"))
    headers = auth(manager)
    ok = client.put(
        "/platform/staff/dan@example.com",
        json={"level": "employee", "permissions": ["inbox.manage"]},
        headers=headers,
    )
    assert ok.status_code == 200
    more = client.put(
        "/platform/staff/dan@example.com",
        json={"level": "employee", "permissions": ["businesses.act"]},
        headers=headers,
    )
    assert more.status_code == 403 and more.json()["detail"] == "cannot_grant_more_than_you_hold"
    promote = client.put(
        "/platform/staff/dan@example.com", json={"level": "manager"}, headers=headers
    )
    assert promote.status_code == 403
    _, other_owner = staff_member(engine)
    assert client.delete(f"/platform/staff/{other_owner}", headers=headers).status_code == 403
    assert client.delete("/platform/staff/dan@example.com", headers=headers).status_code == 200
    assert client.get("/platform/audit", headers=headers).status_code == 403  # owners only


def test_employees_see_only_what_they_were_given(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    employee, _ = staff_member(engine, "employee", ("inbox.manage",))
    headers = auth(employee)
    assert client.get("/me", headers=headers).json()["platform_admin"] is True
    assert client.get("/platform/contact-requests", headers=headers).status_code == 200
    assert client.get("/platform/businesses", headers=headers).status_code == 403
    assert client.get("/platform/billing", headers=headers).status_code == 403
    assert client.get("/platform/staff", headers=headers).status_code == 403

    # A disabled member loses the console.
    owner, _ = staff_member(engine)
    client.put(
        f"/platform/staff/{employee}@example.com",
        json={"level": "employee", "permissions": ["inbox.manage"], "disabled": True},
        headers=auth(owner),
    )
    assert client.get("/platform/me", headers=headers).status_code == 403
