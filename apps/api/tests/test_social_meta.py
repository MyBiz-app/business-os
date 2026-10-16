"""Meta connector: OAuth connect, account choice, sync, publish. The network is a fake Graph."""

import json
import re
from urllib.parse import parse_qs, urlparse

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import get_settings
from app.social import meta
from tests.conftest import AuthHeaders  # noqa: F401
from tests.test_social import with_studio

PAGE = {
    "id": "p1",
    "name": "Studio Flow Page",
    "access_token": "PAGE-TOKEN",
    "picture": {"data": {"url": "https://img/p1.png"}},
    "instagram_business_account": {"id": "ig1", "username": "studioflow"},
}


def fake_graph(request: httpx2.Request) -> httpx2.Response:
    path = request.url.path
    q = dict(request.url.params)
    if request.method == "POST":
        q = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
    if path.endswith("/oauth/access_token") and "code" in q:
        return httpx2.Response(200, json={"access_token": "SHORT"})
    if path.endswith("/oauth/access_token"):
        return httpx2.Response(200, json={"access_token": "LONG"})
    if path.endswith("/me/accounts"):
        assert q["access_token"] == "LONG"
        return httpx2.Response(200, json={"data": [PAGE]})
    if path.endswith("/insights"):
        if q.get("metric") == "page_video_views":  # a metric Meta removed
            return httpx2.Response(400, json={"error": {"code": 100, "message": "bad metric"}})
        values = [{"value": 7, "end_time": "2026-10-15T07:00:00+0000"}]
        return httpx2.Response(200, json={"data": [{"name": q.get("metric"), "values": values}]})
    if path.endswith("/published_posts"):
        return httpx2.Response(
            200,
            json={
                "data": [
                    {
                        "id": "p1_9",
                        "message": "Hello",
                        "created_time": "2026-10-14T10:00:00+0000",
                        "likes": {"summary": {"total_count": 4}},
                    }
                ]
            },
        )
    if path.endswith("/media"):
        return httpx2.Response(200, json={"data": []})
    if path.endswith("/feed"):
        assert q["message"] == "Hi there"
        return httpx2.Response(200, json={"id": "p1_10"})
    if path.endswith("/p1_10"):
        return httpx2.Response(200, json={"permalink_url": "https://fb.com/p1_10"})
    if path.endswith("/p1"):
        return httpx2.Response(200, json={"followers_count": 120})
    if path.endswith("/ig1"):
        return httpx2.Response(200, json={"followers_count": 80})
    return httpx2.Response(404, json={"error": {"code": 100, "message": path}})


@pytest.fixture
def meta_on(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "meta_app_id", "APPID")
    monkeypatch.setattr(settings, "meta_app_secret", SecretStr("APPSECRET"))
    monkeypatch.setattr(
        meta.META.graph, "client", httpx2.Client(transport=httpx2.MockTransport(fake_graph))
    )


def test_without_keys_meta_stays_soon_and_connect_is_refused(
    client: TestClient, studio: dict
) -> None:
    headers = with_studio(client, studio)
    networks = {
        n["network"]: n for n in client.get("/social/providers", headers=headers).json()["networks"]
    }
    assert networks["facebook"]["status"] == "soon" and networks["threads"]["status"] == "soon"
    assert client.post("/social/connect/meta", headers=headers).status_code == 409


def test_connect_choose_accounts_and_publish(
    client: TestClient, studio: dict, meta_on: None
) -> None:
    headers = with_studio(client, studio)
    networks = {
        n["network"]: n for n in client.get("/social/providers", headers=headers).json()["networks"]
    }
    assert (
        networks["facebook"]["status"] == "available"
        and networks["instagram"]["status"] == "available"
    )
    assert networks["threads"]["status"] == "soon"

    started = client.post("/social/connect/meta", headers=headers).json()
    url = urlparse(started["authorize_url"])
    query = parse_qs(url.query)
    assert url.netloc == "www.facebook.com" and query["client_id"] == ["APPID"]
    assert query["redirect_uri"][0].endswith("/social/callback/meta")
    state = query["state"][0]

    bad = client.get(
        "/social/callback/meta", params={"code": "c", "state": "junk"}, follow_redirects=False
    )
    assert bad.headers["location"].endswith("/content?connect_error=state")
    denied = client.get("/social/callback/meta", params={"state": state}, follow_redirects=False)
    assert denied.headers["location"].endswith("/content?connect_error=denied")

    back = client.get(
        "/social/callback/meta", params={"code": "c", "state": state}, follow_redirects=False
    )
    assert back.status_code == 303
    pending_id = re.search(r"connect=([0-9a-f-]{36})$", back.headers["location"]).group(1)

    pending = client.get(f"/social/pending/{pending_id}", headers=headers).json()
    assert {c["network"] for c in pending["candidates"]} == {"facebook", "instagram"}
    assert "PAGE-TOKEN" not in json.dumps(pending)

    chosen = client.post(
        f"/social/pending/{pending_id}/select", json={"external_ids": ["p1"]}, headers=headers
    )
    assert chosen.status_code == 200, chosen.text
    accounts = chosen.json()
    assert [a["network"] for a in accounts] == ["facebook"] and accounts[0]["last_synced_at"]
    assert client.get(f"/social/pending/{pending_id}", headers=headers).status_code == 404

    kpis = client.get("/social/dashboard", headers=headers).json()["kpis"]
    assert kpis["followers"]["value"] == 120
    top = client.get("/social/posts/top", headers=headers).json()
    assert top and top[0]["caption"] == "Hello"

    published = client.post(
        f"/social/accounts/{accounts[0]['id']}/publish", json={"text": "Hi there"}, headers=headers
    )
    assert published.status_code == 201 and published.json()["permalink"] == "https://fb.com/p1_10"


def test_an_expired_token_asks_to_connect_again(
    client: TestClient, studio: dict, meta_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = with_studio(client, studio)
    state = parse_qs(
        urlparse(client.post("/social/connect/meta", headers=headers).json()["authorize_url"]).query
    )["state"][0]
    pending_id = re.search(
        r"connect=([0-9a-f-]{36})$",
        client.get(
            "/social/callback/meta", params={"code": "c", "state": state}, follow_redirects=False
        ).headers["location"],
    ).group(1)
    account = client.post(
        f"/social/pending/{pending_id}/select", json={"external_ids": ["ig1"]}, headers=headers
    ).json()[0]

    def expired(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": {"code": 190, "message": "expired"}})

    monkeypatch.setattr(
        meta.META.graph, "client", httpx2.Client(transport=httpx2.MockTransport(expired))
    )
    refused = client.post(
        f"/social/accounts/{account['id']}/publish",
        json={"text": "x", "image_url": "https://i/x.png"},
        headers=headers,
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "needs_reauth"
    listed = client.get("/social/accounts", headers=headers).json()
    assert listed[0]["status"] == "needs_reauth"
    assert (
        client.post(
            f"/social/accounts/{account['id']}/publish", json={"text": "x"}, headers=headers
        ).status_code
        == 409
    )
