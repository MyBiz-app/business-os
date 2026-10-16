"""Branch managers (round 5, G2): manager rights at their own branches only. The server refuses
anything outside their branches or above their level, whatever the screen offers."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.permissions import ROLE_PERMISSIONS, Permission
from tests.conftest import AuthHeaders, TokenFactory, add_member


@pytest.fixture
def network(client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict) -> dict:
    """Two branches (North, South), staff at each, and a branch manager appointed at North."""
    owner = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=owner).json()["id"]
    found: dict = {"owner": owner, "north": north, "south": south, "tenant": studio["tenant_id"]}
    for name, branch in (("north_staff", north), ("south_staff", south)):
        user = uuid4()
        add_member(engine, studio["tenant_id"], user, "staff")
        client.put(f"/staff/{user}/branches", json={"location_ids": [branch]}, headers=owner)
        found[name] = user
    boss = uuid4()
    add_member(engine, studio["tenant_id"], boss, "staff")
    appointed = client.put(
        f"/locations/{north}/manager", json={"user_id": str(boss)}, headers=owner
    )
    assert appointed.status_code == 200, appointed.text
    found["boss"] = boss
    found["boss_headers"] = auth(boss, studio["tenant_id"])
    found["other_manager"] = uuid4()
    add_member(engine, studio["tenant_id"], found["other_manager"], "manager")
    return found


def test_branch_manager_is_not_a_full_manager() -> None:
    perms = ROLE_PERMISSIONS["branch_manager"]
    assert Permission.STAFF_MANAGE in perms
    for withheld in (
        Permission.BUSINESS_SETTINGS,
        Permission.AI_MANAGE,
        Permission.CATALOG_WRITE,
        Permission.CATALOG_DELETE,
        Permission.CLIENTS_PRIVACY,
    ):
        assert withheld not in perms


def test_new_branches_are_managed_by_the_owner(client: TestClient, studio: dict) -> None:
    branches = client.get("/locations", headers=studio["headers"]).json()
    assert {b["manager_user_id"] for b in branches} == {str(studio["owner"])}


def test_appointing_makes_a_staff_member_a_branch_manager_there(
    client: TestClient, network: dict
) -> None:
    owner = network["owner"]
    team = {m["user_id"]: m for m in client.get("/staff", headers=owner).json()["members"]}
    boss = team[str(network["boss"])]
    assert boss["role"] == "branch_manager"
    assert boss["location_ids"] == [network["north"]]
    north = client.get(f"/locations/{network['north']}", headers=owner).json()
    assert north["manager_user_id"] == str(network["boss"])
    # People at the branch now report to its manager (a suggestion the owner can change).
    assert team[str(network["north_staff"])]["reports_to"] == str(network["boss"])
    owner_id = next(u for u, m in team.items() if m["role"] == "owner")
    assert team[str(network["south_staff"])]["reports_to"] == owner_id  # South: still the owner's


def test_a_branch_manager_sees_only_their_branches(client: TestClient, network: dict) -> None:
    mine = network["boss_headers"]
    branches = client.get("/locations", headers=mine).json()
    assert [b["id"] for b in branches] == [network["north"]]
    ids = {m["user_id"] for m in client.get("/staff", headers=mine).json()["members"]}
    assert str(network["north_staff"]) in ids and str(network["boss"]) in ids
    assert str(network["south_staff"]) not in ids


def test_a_branch_manager_manages_staff_in_their_branch(client: TestClient, network: dict) -> None:
    mine = network["boss_headers"]
    user = network["north_staff"]
    assert (
        client.patch(f"/staff/{user}", json={"role": "front_desk"}, headers=mine).status_code == 200
    )
    title = client.patch(f"/staff/{user}/organization", json={"job_title": "Coach"}, headers=mine)
    assert title.status_code == 200, title.text
    assert client.delete(f"/staff/{user}", headers=mine).status_code == 204


def test_a_branch_manager_cannot_touch_another_branch(client: TestClient, network: dict) -> None:
    mine = network["boss_headers"]
    user = network["south_staff"]
    attempts = [
        client.patch(f"/staff/{user}", json={"role": "front_desk"}, headers=mine),
        client.put(
            f"/staff/{user}/branches", json={"location_ids": [network["north"]]}, headers=mine
        ),
        client.put(
            f"/staff/{user}/home-branch", json={"location_id": network["north"]}, headers=mine
        ),
        client.patch(f"/staff/{user}/organization", json={"job_title": "x"}, headers=mine),
        client.delete(f"/staff/{user}", headers=mine),
    ]
    assert [a.status_code for a in attempts] == [404] * 5
    # Nor can they file someone under a branch that is not theirs.
    own = network["north_staff"]
    moved = client.put(
        f"/staff/{own}/branches", json={"location_ids": [network["south"]]}, headers=mine
    )
    assert moved.status_code == 422
    # An empty list would mean "all branches": refused.
    assert (
        client.put(f"/staff/{own}/branches", json={"location_ids": []}, headers=mine).status_code
        == 422
    )


def test_a_branch_manager_cannot_reach_above_their_level(client: TestClient, network: dict) -> None:
    mine = network["boss_headers"]
    owner_id = next(
        m["user_id"]
        for m in client.get("/staff", headers=network["owner"]).json()["members"]
        if m["role"] == "owner"
    )
    peer = network["south_staff"]  # a branch manager of the other branch
    client.put(
        f"/locations/{network['south']}/manager",
        json={"user_id": str(peer)},
        headers=network["owner"],
    )
    # Not owners, managers or other branch managers: they are not in reach, or not their level.
    for target in (owner_id, str(network["other_manager"]), str(peer)):
        for call in (
            client.patch(f"/staff/{target}", json={"role": "staff"}, headers=mine),
            client.delete(f"/staff/{target}", headers=mine),
        ):
            assert call.status_code in (403, 404), call.text
    user = network["north_staff"]
    for role in ("owner", "manager", "branch_manager"):
        denied = client.patch(f"/staff/{user}", json={"role": role}, headers=mine)
        assert denied.status_code == 403, role
        invited = client.post(
            "/staff/invitations", json={"email": f"{role}@example.com", "role": role}, headers=mine
        )
        assert invited.status_code == 403, role


def test_a_branch_manager_cannot_give_more_than_they_have(
    client: TestClient, network: dict
) -> None:
    mine = network["boss_headers"]
    over = client.post(
        "/roles", json={"name": "Everything", "permissions": ["business.settings"]}, headers=mine
    )
    assert over.status_code == 403
    # Custom roles are business-wide: even a harmless one is not theirs to create.
    harmless = client.post(
        "/roles", json={"name": "Reader", "permissions": ["clients.read"]}, headers=mine
    )
    assert harmless.status_code == 403
    made = client.post(
        "/roles",
        json={"name": "Everything", "permissions": ["business.settings"]},
        headers=network["owner"],
    )
    assert made.status_code == 201
    grant = client.patch(
        f"/staff/{network['north_staff']}", json={"custom_role_id": made.json()["id"]}, headers=mine
    )
    assert grant.status_code == 403
    assert grant.json()["detail"] == "exceeds_own_permissions"


def test_a_branch_manager_cannot_use_business_wide_settings(
    client: TestClient, network: dict
) -> None:
    mine = network["boss_headers"]
    assert (
        client.patch("/tenants/current", json={"name": "Mine now"}, headers=mine).status_code == 403
    )
    assert client.post("/locations", json={"name": "Third"}, headers=mine).status_code == 403
    assert (
        client.put(
            f"/locations/{network['north']}/manager",
            json={"user_id": str(network["boss"])},
            headers=mine,
        ).status_code
        == 403
    )


def test_invitations_from_a_branch_manager_stay_in_their_branches(
    client: TestClient, network: dict
) -> None:
    mine = network["boss_headers"]
    invited = client.post(
        "/staff/invitations", json={"email": "new@example.com", "role": "staff"}, headers=mine
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["location_ids"] == [network["north"]]
    elsewhere = client.post(
        "/staff/invitations",
        json={"email": "far@example.com", "role": "staff", "location_ids": [network["south"]]},
        headers=mine,
    )
    assert elsewhere.status_code == 422
    # The owner's invitation to another branch is not visible to them, nor revocable.
    theirs = client.post(
        "/staff/invitations",
        json={"email": "south@example.com", "role": "staff", "location_ids": [network["south"]]},
        headers=network["owner"],
    ).json()
    listed = client.get("/staff", headers=mine).json()["invitations"]
    assert [i["email"] for i in listed] == ["new@example.com"]
    assert client.delete(f"/staff/invitations/{theirs['id']}", headers=mine).status_code == 404


def test_an_accepted_invitation_keeps_the_new_member_in_their_branch(
    client: TestClient, make_token: TokenFactory, network: dict
) -> None:
    mine = network["boss_headers"]
    token = client.post(
        "/staff/invitations", json={"email": "joiner@example.com", "role": "staff"}, headers=mine
    ).json()["token"]
    joiner = uuid4()
    accepted = client.post(
        "/invitations/accept",
        json={"token": token},
        headers={"Authorization": f"Bearer {make_token(joiner, 'joiner@example.com')}"},
    )
    assert accepted.status_code == 200, accepted.text
    members = {
        m["user_id"]: m for m in client.get("/staff", headers=network["owner"]).json()["members"]
    }
    assert members[str(joiner)]["location_ids"] == [network["north"]]


def test_a_branch_manager_without_branches_reaches_nothing(
    client: TestClient, auth: AuthHeaders, engine: Engine, network: dict
) -> None:
    stray = uuid4()
    add_member(engine, network["tenant"], stray, "branch_manager")
    mine = auth(stray, network["tenant"])
    assert client.get("/clients", headers=mine).status_code == 403
    # The API never produces this state: a branch manager always has a branch.
    owner = network["owner"]
    refused = client.put(f"/staff/{stray}/branches", json={"location_ids": []}, headers=owner)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "branch_manager_needs_branch"
    refused = client.patch(
        f"/staff/{network['south_staff']}", json={"role": "branch_manager"}, headers=owner
    )
    assert refused.status_code == 200  # already kept to South


def test_replacing_a_manager_steps_the_old_one_down(client: TestClient, network: dict) -> None:
    owner = network["owner"]
    successor = network["north_staff"]
    appointed = client.put(
        f"/locations/{network['north']}/manager", json={"user_id": str(successor)}, headers=owner
    )
    assert appointed.status_code == 200
    members = {m["user_id"]: m for m in client.get("/staff", headers=owner).json()["members"]}
    assert members[str(successor)]["role"] == "branch_manager"
    old = members[str(network["boss"])]
    assert old["role"] == "staff"  # kept at their branch, not widened to every branch
    assert old["location_ids"] == [network["north"]]


def test_removing_the_manager_and_removing_the_member(client: TestClient, network: dict) -> None:
    owner = network["owner"]
    cleared = client.delete(f"/locations/{network['north']}/manager", headers=owner)
    assert cleared.status_code == 200 and cleared.json()["manager_user_id"] is None
    appointed = client.put(
        f"/locations/{network['south']}/manager",
        json={"user_id": str(network["south_staff"])},
        headers=owner,
    )
    assert appointed.status_code == 200
    assert client.delete(f"/staff/{network['south_staff']}", headers=owner).status_code == 204
    south = client.get(f"/locations/{network['south']}", headers=owner).json()
    assert south["manager_user_id"] is None


def test_appointing_a_stranger_is_refused(client: TestClient, network: dict) -> None:
    refused = client.put(
        f"/locations/{network['north']}/manager",
        json={"user_id": str(uuid4())},
        headers=network["owner"],
    )
    assert refused.status_code == 422


def test_branch_manager_cannot_be_given_to_a_member_without_branches(
    client: TestClient, engine: Engine, network: dict
) -> None:
    free = uuid4()
    add_member(engine, network["tenant"], free, "staff")  # works everywhere
    refused = client.patch(
        f"/staff/{free}", json={"role": "branch_manager"}, headers=network["owner"]
    )
    assert refused.status_code == 422
    with engine.begin() as connection:
        stored = connection.execute(
            text("SELECT role FROM app.tenant_members WHERE user_id = :u"), {"u": free}
        ).scalar_one()
    assert stored == "staff"
    assert isinstance(network["tenant"], UUID)
