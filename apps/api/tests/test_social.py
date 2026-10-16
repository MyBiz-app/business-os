"""Content studio: connecting accounts (demo data), the dashboard, tenant isolation, permissions."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.social.demo import DEMO, DEMO_NETWORKS
from tests.conftest import STUDIO, AuthHeaders, add_member


def with_studio(client: TestClient, studio: dict) -> dict:
    response = client.put(
        "/tenants/current/modules",
        json={"modules": {"social_studio": 1}},
        headers=studio["headers"],
    )
    assert response.status_code == 200, response.text
    return studio["headers"]


def test_the_studio_needs_its_module(client: TestClient, studio: dict) -> None:
    response = client.get("/social/providers", headers=studio["headers"])
    assert response.status_code == 403 and response.json()["detail"] == "module_disabled"


def test_providers_list_every_network_and_mark_the_unfinished_ones_soon(
    client: TestClient, studio: dict
) -> None:
    headers = with_studio(client, studio)
    body = client.get("/social/providers", headers=headers).json()
    networks = {n["network"]: n for n in body["networks"]}
    assert {"facebook", "instagram", "tiktok", "youtube", "google_business", "x"} <= set(networks)
    assert all(n["status"] == "soon" for n in networks.values())  # connectors arrive later
    assert body["demo_available"] is True


def test_demo_connection_fills_the_dashboard(client: TestClient, studio: dict) -> None:
    headers = with_studio(client, studio)
    connected = client.post("/social/connect/demo", headers=headers)
    assert connected.status_code == 201
    accounts = connected.json()["accounts"]
    assert {a["network"] for a in accounts} == set(DEMO_NETWORKS)
    assert all(a["is_demo"] and a["last_synced_at"] for a in accounts)

    data = client.get("/social/dashboard?compare=true", headers=headers).json()
    kpis = data["kpis"]
    assert kpis["followers"]["value"] > 0 and kpis["followers"]["previous"] > 0
    assert kpis["reach"]["value"] > 0 and kpis["reach"]["previous"] is not None
    assert {s["network"] for s in data["followers_series"]} == set(DEMO_NETWORKS) - {
        "google_business"
    }
    assert data["video_views_weekly"] and data["heatmap"]
    assert data["google_business"]["rating"] >= 4.5

    top = client.get("/social/posts/top?limit=3", headers=headers).json()
    assert len(top) == 3 and top[0]["views"] >= top[1]["views"] >= top[2]["views"]
    audience = client.get("/social/audience", headers=headers).json()
    for dimension in ("age", "gender", "city"):
        assert sum(a["share_bp"] for a in audience if a["dimension"] == dimension) in range(
            9990, 10011
        )


def test_filtering_by_network_narrows_the_numbers(client: TestClient, studio: dict) -> None:
    headers = with_studio(client, studio)
    client.post("/social/connect/demo", headers=headers)
    everything = client.get("/social/dashboard", headers=headers).json()
    one = client.get("/social/dashboard?networks=tiktok", headers=headers).json()
    assert 0 < one["kpis"]["followers"]["value"] < everything["kpis"]["followers"]["value"]
    assert [s["network"] for s in one["followers_series"]] == ["tiktok"]
    assert one["google_business"] is None
    unknown = client.get("/social/dashboard?networks=myspace", headers=headers)
    assert unknown.status_code == 422


def test_period_is_validated(client: TestClient, studio: dict) -> None:
    headers = with_studio(client, studio)
    response = client.get("/social/dashboard?from=2026-02-01&to=2026-01-01", headers=headers)
    assert response.status_code == 422 and response.json()["detail"] == "invalid_period"


def test_refresh_is_limited_to_once_an_hour(client: TestClient, studio: dict) -> None:
    headers = with_studio(client, studio)
    client.post("/social/connect/demo", headers=headers)
    response = client.post("/social/sync", headers=headers)
    assert response.status_code == 429 and response.json()["detail"] == "sync_too_soon"


def test_real_connectors_are_not_there_yet(client: TestClient, studio: dict) -> None:
    headers = with_studio(client, studio)
    response = client.post("/social/connect/meta", headers=headers)
    assert response.status_code == 409 and response.json()["detail"] == "coming_soon"


def test_disconnecting_removes_the_account_and_its_numbers(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = with_studio(client, studio)
    accounts = client.post("/social/connect/demo", headers=headers).json()["accounts"]
    gone = accounts[0]["id"]
    assert client.delete(f"/social/accounts/{gone}", headers=headers).status_code == 204
    assert client.delete(f"/social/accounts/{gone}", headers=headers).status_code == 404
    with engine.connect() as connection:
        left = connection.execute(
            text("SELECT count(*) FROM app.social_metrics_daily WHERE account_id = :a"),
            {"a": gone},
        ).scalar_one()
    assert left == 0


def test_a_business_never_sees_another_businesss_accounts(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    headers = with_studio(client, studio)
    client.post("/social/connect/demo", headers=headers)

    owner = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(owner)).json()
    other_headers = auth(owner, other["id"])
    client.put(
        "/tenants/current/modules", json={"modules": {"social_studio": 1}}, headers=other_headers
    )
    assert client.get("/social/accounts", headers=other_headers).json() == []
    assert (
        client.get("/social/dashboard", headers=other_headers).json()["kpis"]["reach"]["value"] == 0
    )


def test_staff_do_not_open_the_studio(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = with_studio(client, studio)
    assert (
        client.get(
            "/social/accounts", headers=auth(studio["coach"], studio["tenant_id"])
        ).status_code
        == 403
    )
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    manager_headers = auth(manager, studio["tenant_id"])
    assert client.get("/social/accounts", headers=manager_headers).status_code == 200
    assert client.post("/social/connect/demo", headers=manager_headers).status_code == 201
    assert headers


def test_demo_numbers_are_stable_and_start_where_asked() -> None:
    info = DEMO.accounts()[0]
    first = DEMO.fetch_account_metrics(info, date(2026, 5, 1), date(2026, 5, 10))
    again = DEMO.fetch_account_metrics(info, date(2026, 5, 1), date(2026, 5, 10))
    assert first == again and len(first) == 10 and first[0].day == date(2026, 5, 1)
    since = datetime.now(UTC) - timedelta(days=30)
    assert all(p.published_at >= since - timedelta(days=1) for p in DEMO.fetch_posts(info, since))
