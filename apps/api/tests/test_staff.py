from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, TokenFactory, add_member
from tests.test_tenants import STUDIO


@pytest.fixture
def studio(client: TestClient, auth: AuthHeaders) -> dict[str, UUID]:
    owner = uuid4()
    tenant_id = UUID(client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"])
    return {"owner": owner, "tenant_id": tenant_id}


def headers_for(make_token: TokenFactory, user_id: UUID, email: str, tenant_id: UUID | None = None):
    result = {"Authorization": f"Bearer {make_token(user_id, email)}"}
    if tenant_id:
        result["X-Tenant-Id"] = str(tenant_id)
    return result


def invite(client: TestClient, auth: AuthHeaders, studio: dict[str, UUID], email: str, role: str):
    return client.post(
        "/staff/invitations",
        json={"email": email, "role": role},
        headers=auth(studio["owner"], studio["tenant_id"]),
    )


def test_invite_and_accept(
    client: TestClient, auth: AuthHeaders, make_token: TokenFactory, studio: dict[str, UUID]
) -> None:
    created = invite(client, auth, studio, "Coach@Example.com", "staff")
    assert created.status_code == 201
    token = created.json()["token"]

    coach = uuid4()
    coach_headers = headers_for(make_token, coach, "coach@example.com")
    preview = client.get(f"/invitations/{token}", headers=coach_headers)
    accepted = client.post("/invitations/accept", json={"token": token}, headers=coach_headers)
    again = client.post("/invitations/accept", json={"token": token}, headers=coach_headers)

    assert preview.json() == {
        "tenant_name": "Studio Flow",
        "role": "staff",
        "email": "coach@example.com",
        "status": "pending",
    }
    assert accepted.json() == {"tenant_id": str(studio["tenant_id"])}
    assert again.status_code == 410
    team = client.get("/staff", headers=auth(studio["owner"], studio["tenant_id"])).json()
    assert {m["email"]: m["role"] for m in team["members"]} == {
        f"{studio['owner']}@example.com": "owner",
        "coach@example.com": "staff",
    }
    assert team["invitations"] == []


def test_accept_requires_matching_email(
    client: TestClient, auth: AuthHeaders, make_token: TokenFactory, studio: dict[str, UUID]
) -> None:
    token = invite(client, auth, studio, "coach@example.com", "staff").json()["token"]
    stranger = headers_for(make_token, uuid4(), "someone-else@example.com")

    response = client.post("/invitations/accept", json={"token": token}, headers=stranger)

    assert response.status_code == 403
    assert (
        client.post("/invitations/accept", json={"token": "made-up"}, headers=stranger).status_code
        == 404
    )


def test_expired_invitation(
    client: TestClient,
    auth: AuthHeaders,
    make_token: TokenFactory,
    engine: Engine,
    studio: dict[str, UUID],
) -> None:
    token = invite(client, auth, studio, "late@example.com", "staff").json()["token"]
    with engine.begin() as admin:
        admin.execute(text("UPDATE app.invitations SET expires_at = now() - interval '1 day'"))
    late = headers_for(make_token, uuid4(), "late@example.com")

    assert client.get(f"/invitations/{token}", headers=late).json()["status"] == "expired"
    assert (
        client.post("/invitations/accept", json={"token": token}, headers=late).status_code == 410
    )


def test_token_is_stored_only_as_hash(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    token = invite(client, auth, studio, "a@example.com", "staff").json()["token"]
    with engine.begin() as admin:
        stored = admin.execute(text("SELECT token_hash FROM app.invitations")).scalar_one()

    assert token not in stored
    assert len(stored) == 64


def test_change_role_and_remove_member(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, "staff")
    owner = auth(studio["owner"], studio["tenant_id"])

    promoted = client.patch(f"/staff/{member}", json={"role": "front_desk"}, headers=owner)
    removed = client.delete(f"/staff/{member}", headers=owner)

    assert promoted.json()["role"] == "front_desk"
    assert removed.status_code == 204
    assert client.get("/clients", headers=auth(member, studio["tenant_id"])).status_code == 403


def test_last_owner_is_protected(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    owner = auth(studio["owner"], studio["tenant_id"])

    demote = client.patch(f"/staff/{studio['owner']}", json={"role": "manager"}, headers=owner)
    remove_self = client.delete(f"/staff/{studio['owner']}", headers=owner)

    assert demote.status_code == 409
    assert demote.json()["detail"] == "last_owner"
    assert remove_self.status_code == 409


def test_managers_cannot_touch_owners(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    headers = auth(manager, studio["tenant_id"])

    invite_owner = client.post(
        "/staff/invitations", json={"email": "x@example.com", "role": "owner"}, headers=headers
    )
    demote_owner = client.patch(
        f"/staff/{studio['owner']}", json={"role": "staff"}, headers=headers
    )
    self_promote = client.patch(f"/staff/{manager}", json={"role": "owner"}, headers=headers)
    invite_staff = client.post(
        "/staff/invitations", json={"email": "y@example.com", "role": "staff"}, headers=headers
    )

    assert invite_owner.status_code == 403
    assert demote_owner.status_code == 403
    assert self_promote.status_code == 403
    assert invite_staff.status_code == 201


def test_staff_and_front_desk_cannot_see_team(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    for role in ("staff", "front_desk"):
        member = uuid4()
        add_member(engine, studio["tenant_id"], member, role)
        assert client.get("/staff", headers=auth(member, studio["tenant_id"])).status_code == 403


def test_cannot_invite_existing_member(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    response = invite(client, auth, studio, f"{studio['owner']}@example.com", "staff")

    assert response.status_code == 409


def test_revoke_invitation(
    client: TestClient, auth: AuthHeaders, make_token: TokenFactory, studio: dict[str, UUID]
) -> None:
    created = invite(client, auth, studio, "gone@example.com", "staff").json()
    owner = auth(studio["owner"], studio["tenant_id"])

    revoked = client.delete(f"/staff/invitations/{created['id']}", headers=owner)
    gone = headers_for(make_token, uuid4(), "gone@example.com")

    assert revoked.status_code == 204
    accept = client.post("/invitations/accept", json={"token": created["token"]}, headers=gone)
    assert accept.status_code == 404


def test_team_is_isolated_between_businesses(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    other_owner = uuid4()
    other_tenant = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]
    invitation = invite(client, auth, studio, "a@example.com", "staff").json()
    theirs = auth(other_owner, other_tenant)

    team = client.get("/staff", headers=theirs).json()

    assert [m["user_id"] for m in team["members"]] == [str(other_owner)]
    assert team["invitations"] == []
    assert (
        client.delete(f"/staff/invitations/{invitation['id']}", headers=theirs).status_code == 404
    )
    assert (
        client.patch(
            f"/staff/{studio['owner']}", json={"role": "staff"}, headers=theirs
        ).status_code
        == 404
    )
