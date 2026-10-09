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


def test_staff_can_work_inside_a_business_and_the_owner_sees_it(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    helper, helper_email = staff_member(engine, "employee", ("businesses.act",))
    inside = auth(helper, studio["tenant_id"])

    tenant = client.get("/tenants/current", headers=inside).json()
    assert tenant["role"] == "platform"
    assert "clients.write" in tenant["permissions"]  # can actually fix things
    assert "clients.privacy" not in tenant["permissions"]  # never privacy requests

    fixed = client.post("/clients", json={"first_name": "Dana"}, headers=inside)
    assert fixed.status_code == 201
    assert [c["first_name"] for c in client.get("/clients", headers=inside).json()["items"]] == [
        "Dana"
    ]

    # The business's owner sees the visit, and MyBiz's own audit log has the change.
    visits = client.get("/support-access", headers=studio["headers"]).json()["visits"]
    assert visits and visits[0]["actor_email"] == helper_email
    owner, _ = staff_member(engine, "owner")
    entries = client.get("/platform/audit", headers=auth(owner)).json()
    changes = [e for e in entries if e["action"] == "platform.change"]
    assert changes and changes[0]["tenant_id"] == str(studio["tenant_id"])
    assert changes[0]["details"]["path"] == "/clients"


def test_staff_without_that_permission_stay_outside(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    watcher, _ = staff_member(engine, "employee", ("businesses.read",))
    assert client.get("/clients", headers=auth(watcher, studio["tenant_id"])).status_code == 403


def test_the_inbox_moves_requests_along(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    staff, staff_email = staff_member(engine, "employee", ("inbox.manage",))
    headers = auth(staff)
    client.post(
        "/public/contact",
        json={"name": "Dana", "email": "dana@example.com", "message": "Hi", "locale": "he"},
    )
    complaint = client.post(
        "/support-requests",
        json={"message": "The schedule shows the wrong hour"},
        headers=studio["headers"],
    )
    assert complaint.status_code == 201

    inbox = client.get("/platform/contact-requests", headers=headers).json()
    assert {r["status"] for r in inbox} == {"new"} and len(inbox) == 2
    mine = next(r for r in inbox if r["from_business"])
    assert mine["business"] == "Studio Flow" and mine["tenant_id"] == str(studio["tenant_id"])

    taken = client.patch(
        f"/platform/contact-requests/{mine['id']}",
        json={"status": "in_progress", "assignee": "me", "notes": "Called them back"},
        headers=headers,
    ).json()
    updated = next(r for r in taken if r["id"] == mine["id"])
    assert updated["status"] == "in_progress" and updated["assignee"] == staff_email
    assert updated["notes"] == "Called them back"

    done = client.patch(
        f"/platform/contact-requests/{mine['id']}", json={"status": "done"}, headers=headers
    ).json()
    assert done[-1]["id"] == mine["id"]  # finished ones sink to the bottom

    other, _ = staff_member(engine, "employee", ("usage.read",))
    assert client.get("/platform/contact-requests", headers=auth(other)).status_code == 403


def test_support_tiers_order_the_inbox_and_setup_opens_a_task(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    staff, _ = staff_member(engine, "owner", ("inbox.manage", "billing.manage"))
    headers = auth(staff)
    tenant_id = str(studio["tenant_id"])
    client.post(
        "/public/contact",
        json={"name": "Dana", "email": "dana@example.com", "message": "Hi", "locale": "he"},
    )
    client.post(
        "/support-requests", json={"message": "Help with the schedule"}, headers=studio["headers"]
    )
    inbox = client.get("/platform/contact-requests", headers=headers).json()
    assert [r["tier"] for r in inbox] == ["standard", "standard"]

    # VIP support and setup done for them: the business's request moves up, and a task opens.
    modules = {"support_vip": 1, "setup_full": 1}
    for _ in range(2):  # saving the modules again doesn't open a second task
        client.put(
            f"/platform/businesses/{tenant_id}/modules", json={"modules": modules}, headers=headers
        )
    inbox = client.get("/platform/contact-requests", headers=headers).json()
    assert {(r["kind"], r["tier"]) for r in inbox[:2]} == {
        ("setup_full", "vip"),
        ("request", "vip"),
    }
    assert inbox[2]["tier"] == "standard" and not inbox[2]["from_business"]
    task = next(r for r in inbox if r["kind"] == "setup_full")
    assert task["tenant_id"] == tenant_id and task["business"] == "Studio Flow"
    assert sum(r["kind"] == "setup_full" for r in inbox) == 1


def test_staff_act_on_a_business_from_the_console(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    from tests.test_billing import end_trial, run_billing

    staff, staff_email = staff_member(engine, "employee", ("billing.manage", "businesses.read"))
    headers = auth(staff)
    tenant_id = str(studio["tenant_id"])

    before = client.get("/billing", headers=studio["headers"]).json()["trial_ends_at"]
    extended = client.post(
        f"/platform/businesses/{tenant_id}/trial", json={"days": 14}, headers=headers
    ).json()
    assert extended["trial_ends_at"] > before

    changed = client.put(
        f"/platform/businesses/{tenant_id}/modules",
        json={"modules": {"crm": 1, "whatsapp": 1}},
        headers=headers,
    ).json()
    assert changed["modules"] == ["crm", "whatsapp"]
    assert client.get("/tenants/current", headers=studio["headers"]).json()["modules"] == [
        "crm",
        "whatsapp",
    ]

    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)
    invoice = client.get("/billing", headers=studio["headers"]).json()["invoices"][0]
    voided = client.post(
        f"/platform/invoices/{invoice['id']}/void",
        json={"reason": "Goodwill after a problem"},
        headers=headers,
    )
    assert voided.status_code == 200
    billing = client.get("/billing", headers=studio["headers"]).json()
    assert billing["balance_due"] == 0
    assert (
        client.post(
            f"/platform/invoices/{invoice['id']}/void", json={"reason": "Again"}, headers=headers
        ).json()["detail"]
        == "already_void"
    )

    # Both logs: MyBiz's console audit and the business's own (its owner reads it).
    owner, _ = staff_member(engine, "owner")
    actions = [a["action"] for a in client.get("/platform/audit", headers=auth(owner)).json()]
    assert {
        "business.trial_extended",
        "business.modules_changed",
        "business.invoice_voided",
    } <= set(actions)
    visits = client.get("/support-access", headers=studio["headers"]).json()["visits"]
    assert any(v["actor_email"] == staff_email for v in visits)

    nobody, _ = staff_member(engine, "employee", ("businesses.read",))
    assert (
        client.post(
            f"/platform/businesses/{tenant_id}/trial", json={"days": 1}, headers=auth(nobody)
        ).status_code
        == 403
    )
