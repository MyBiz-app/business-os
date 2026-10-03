"""Tenant isolation: one business must never see or change another business's data.

Checked twice: through the API, and directly in Postgres with row-level security, so that
a bug in API code alone cannot leak data."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.core.db import open_session
from tests.conftest import AuthHeaders
from tests.test_tenants import STUDIO


@pytest.fixture
def two_tenants(client: TestClient, auth: AuthHeaders) -> dict[str, UUID]:
    alice, bob = uuid4(), uuid4()
    tenant_a = client.post("/tenants", json={**STUDIO, "name": "A"}, headers=auth(alice)).json()
    tenant_b = client.post("/tenants", json={**STUDIO, "name": "B"}, headers=auth(bob)).json()
    return {
        "alice": alice,
        "bob": bob,
        "tenant_a": UUID(tenant_a["id"]),
        "tenant_b": UUID(tenant_b["id"]),
    }


def test_api_denies_access_to_another_tenant(
    client: TestClient, auth: AuthHeaders, two_tenants: dict[str, UUID]
) -> None:
    response = client.get(
        "/tenants/current", headers=auth(two_tenants["bob"], two_tenants["tenant_a"])
    )

    assert response.status_code == 403


def test_api_denies_unknown_tenant(client: TestClient, auth: AuthHeaders) -> None:
    response = client.get("/tenants/current", headers=auth(uuid4(), uuid4()))

    assert response.status_code == 403


def test_me_lists_only_own_tenants(
    client: TestClient, auth: AuthHeaders, two_tenants: dict[str, UUID]
) -> None:
    memberships = client.get("/me", headers=auth(two_tenants["bob"])).json()["memberships"]

    assert [m["tenant_name"] for m in memberships] == ["B"]


def test_database_hides_other_tenants_even_with_forged_context(
    engine: Engine, two_tenants: dict[str, UUID]
) -> None:
    # Bob's session claims tenant A, as a buggy or malicious API call might.
    with open_session(engine, two_tenants["bob"], two_tenants["tenant_a"]) as session:
        assert session.execute(text("SELECT app.current_tenant_id()")).scalar() is None
        tenant_names = session.execute(text("SELECT name FROM app.tenants")).scalars().all()
        member_tenants = (
            session.execute(text("SELECT tenant_id FROM app.tenant_members")).scalars().all()
        )
        renamed = session.execute(
            text("UPDATE app.tenants SET name = 'hacked' WHERE id = :id"),
            {"id": two_tenants["tenant_a"]},
        )

        assert tenant_names == ["B"]
        assert member_tenants == [two_tenants["tenant_b"]]
        assert renamed.rowcount == 0


def test_database_rejects_joining_another_tenant(
    engine: Engine, two_tenants: dict[str, UUID]
) -> None:
    with (
        open_session(engine, two_tenants["bob"], two_tenants["tenant_a"]) as session,
        pytest.raises(DBAPIError, match="row-level security"),
    ):
        session.execute(
            text(
                "INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'owner')"
            ),
            {"t": two_tenants["tenant_a"], "u": two_tenants["bob"]},
        )


def test_database_shows_nothing_without_a_user(
    engine: Engine, two_tenants: dict[str, UUID]
) -> None:
    with open_session(engine, None) as session:
        assert session.execute(text("SELECT count(*) FROM app.tenants")).scalar() == 0
        assert session.execute(text("SELECT count(*) FROM app.users")).scalar() == 0


def test_restricted_role_survives_commit(engine: Engine) -> None:
    with open_session(engine, uuid4()) as session:
        assert session.execute(text("SELECT current_user")).scalar() == "app_api"
        session.commit()
        assert session.execute(text("SELECT current_user")).scalar() == "app_api"
