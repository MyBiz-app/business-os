from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, add_member
from tests.test_client_app import join, join_code


def test_new_business_gets_the_pack_preset(client: TestClient, studio: dict) -> None:
    tenant = client.get("/tenants/current", headers=studio["headers"]).json()
    assert tenant["modules"] == ["ai_basic", "client_app"]

    modules = client.get("/tenants/current/modules", headers=studio["headers"]).json()
    assert modules["quote"]["core"] == 9900  # up to 100 active clients, ILS
    assert modules["quote"]["total"] == 9900 + 4900 + 4900


def test_business_created_with_chosen_modules(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()
    created = client.post("/tenants", json={**STUDIO, "modules": {}}, headers=auth(owner)).json()
    assert created["modules"] == []
    bad = client.post("/tenants", json={**STUDIO, "modules": {"crm": 1}}, headers=auth(uuid4()))
    assert bad.status_code == 422
    assert bad.json()["detail"] == "module_not_available"


def test_recommend_and_quote(client: TestClient, auth: AuthHeaders) -> None:
    headers = auth(uuid4())
    answers = {
        "active_clients": 250,
        "staff": 4,
        "locations": 2,
        "wants_client_app": True,
        "wants_ai_actions": False,
    }

    recommendation = client.post("/modules/recommend", json=answers, headers=headers).json()

    assert recommendation == {
        "preset": "growing",
        "modules": {"client_app": 1, "ai_basic": 1, "extra_location": 1},
    }
    quote = client.post(
        "/modules/quote",
        params={"currency": "ILS", "active_clients": 250},
        json={"modules": recommendation["modules"]},
        headers=headers,
    ).json()
    assert quote["core"] == 14900 and quote["total"] == 14900 + 4900 + 4900 + 2900
    both = client.post(
        "/modules/quote", json={"modules": {"ai_basic": 1, "ai_pro": 1}}, headers=headers
    )
    assert both.json()["detail"] == "choose_one_ai_tier"
    catalog = client.get("/modules/catalog", params={"currency": "USD"}, headers=headers).json()
    assert {m["key"] for m in catalog["modules"] if not m["available"]} >= {"crm", "whatsapp"}


def test_changing_modules_needs_settings_permission(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    body = {"modules": {"ai_pro": 1}}

    assert (
        client.put(
            "/tenants/current/modules", json=body, headers=auth(desk, studio["tenant_id"])
        ).status_code
        == 403
    )
    changed = client.put("/tenants/current/modules", json=body, headers=studio["headers"])
    assert changed.json()["modules"] == {"ai_pro": 1}


def test_features_follow_modules(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    headers = studio["headers"]
    member = uuid4()
    join(client, auth, member, join_code(client, studio))
    member_headers = auth(member, studio["tenant_id"])
    assert client.get("/client/plans", headers=member_headers).status_code == 200

    client.put("/tenants/current/modules", json={"modules": {}}, headers=headers)

    assert client.get("/client/plans", headers=member_headers).json()["detail"] == (
        "module_disabled"
    )
    newcomer = client.post(
        "/client/businesses", json={"code": join_code(client, studio)}, headers=auth(uuid4())
    )
    assert newcomer.status_code == 403
    assert client.post("/ai/conversations", headers=headers).json()["detail"] == ("module_disabled")


def test_platform_console_is_for_platform_admins(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner_headers = auth(studio["owner"])
    assert client.get("/platform/businesses", headers=owner_headers).status_code == 403
    assert client.get("/me", headers=owner_headers).json()["platform_admin"] is False

    admin = uuid4()
    client.get("/me", headers=auth(admin))  # creates the profile
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.platform_admins (user_id) VALUES (:id)"), {"id": admin}
        )
        connection.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity)
                VALUES (:t, 'ai_credits', 12.5)
            """),
            {"t": studio["tenant_id"]},
        )

    admin_headers = auth(admin)
    assert client.get("/me", headers=admin_headers).json()["platform_admin"] is True
    [business] = client.get("/platform/businesses", headers=admin_headers).json()
    assert business["name"] == STUDIO["name"]
    assert business["members"] == 2  # owner + coach
    assert business["ai_credits_30d"] == 12.5
    assert business["owner_email"] == f"{studio['owner']}@example.com"
    usage = client.get(
        "/platform/usage", params={"tenant_id": studio["tenant_id"]}, headers=admin_headers
    ).json()
    assert usage[0]["meter"] == "ai_credits" and usage[0]["quantity"] == 12.5
    # Being a platform admin does not make you a member of the business.
    assert client.get("/clients", headers=auth(admin, studio["tenant_id"])).status_code == 403
