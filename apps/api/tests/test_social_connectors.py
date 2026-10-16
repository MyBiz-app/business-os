"""Content studio connectors: YouTube, Google Business Profile and TikTok (OAuth, sync, errors).

The networks are replaced by canned answers; nothing here calls the internet."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.config import get_settings
from app.social import google, tiktok
from app.social.oauth import make_state
from app.social.providers import ReauthNeeded
from app.social.sync import sync_account
from tests.test_social import with_studio

TODAY = datetime.now(UTC).date()


@pytest.fixture
def keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name, value in {
        "API_GOOGLE_OAUTH_CLIENT_ID": "google-client",
        "API_GOOGLE_OAUTH_CLIENT_SECRET": "google-secret",
        "API_TIKTOK_CLIENT_KEY": "tiktok-key",
        "API_TIKTOK_CLIENT_SECRET": "tiktok-secret",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def fake_google(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    def answer(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(url)
        if url == google.TOKEN_URL:
            if kwargs["data"]["grant_type"] == "refresh_token":
                return {"access_token": "fresh-access"}
            return {"access_token": "a1", "refresh_token": "r1", "scope": "yt"}
        if url.endswith("/channels"):
            part = kwargs["params"]["part"]
            if part == "snippet":
                return {"items": [{"id": "UC1", "snippet": {"title": "Studio channel"}}]}
            if part == "statistics":
                return {"items": [{"statistics": {"subscriberCount": "120"}}]}
            return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        if url.endswith("/playlistItems"):
            return {"items": [{"contentDetails": {"videoId": "v1"}}]}
        if url.endswith("/videos"):
            return {
                "items": [
                    {
                        "id": "v1",
                        "snippet": {"title": "Tour", "publishedAt": f"{TODAY}T08:00:00Z"},
                        "statistics": {"viewCount": "50", "likeCount": "5", "commentCount": "1"},
                    }
                ]
            }
        if url == google.YT_ANALYTICS:
            if kwargs["params"]["dimensions"] == "day":
                return {"rows": [[TODAY.isoformat(), 40, 4, 1, 0, 3, 1]]}
            return {"rows": []}
        raise AssertionError(url)

    monkeypatch.setattr(google, "request", answer)


def test_without_keys_the_networks_stay_soon(client: TestClient, studio: dict) -> None:
    headers = with_studio(client, studio)
    networks = {
        n["network"]: n["status"]
        for n in client.get("/social/providers", headers=headers).json()["networks"]
    }
    for network in (
        "youtube",
        "tiktok",
        "google_business",
        "x",
        "linkedin",
        "pinterest",
        "snapchat",
    ):
        assert networks[network] == "soon"
        response = client.post(f"/social/connect/{network}", headers=headers)
        assert response.status_code == 409 and response.json()["detail"] == "coming_soon"


def test_with_keys_google_and_tiktok_can_be_connected_but_the_closed_ones_cannot(
    client: TestClient, studio: dict, keys: None
) -> None:
    headers = with_studio(client, studio)
    networks = {
        n["network"]: n["status"]
        for n in client.get("/social/providers", headers=headers).json()["networks"]
    }
    assert networks["youtube"] == networks["google_business"] == networks["tiktok"] == "available"
    assert networks["x"] == networks["linkedin"] == networks["pinterest"] == "soon"
    assert client.post("/social/connect/x", headers=headers).status_code == 409

    url = client.post("/social/connect/youtube", headers=headers).json()["authorize_url"]
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["google-client"] and query["access_type"] == ["offline"]
    assert query["redirect_uri"] == [f"{get_settings().api_url}/social/callback/google"]
    assert "yt-analytics.readonly" in query["scope"][0]

    url = client.post("/social/connect/tiktok", headers=headers).json()["authorize_url"]
    assert parse_qs(urlparse(url).query)["client_key"] == ["tiktok-key"]


def test_youtube_connects_stores_tokens_encrypted_and_fills_the_dashboard(
    client: TestClient, studio: dict, engine: Engine, keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = with_studio(client, studio)
    calls: list[str] = []
    fake_google(monkeypatch, calls)
    state = parse_qs(
        urlparse(
            client.post("/social/connect/youtube", headers=headers).json()["authorize_url"]
        ).query
    )["state"][0]

    done = client.get(f"/social/callback/google?code=abc&state={state}", follow_redirects=False)
    assert done.status_code == 302
    assert "social_connected=1" in done.headers["location"]

    accounts = client.get("/social/accounts", headers=headers).json()
    assert [(a["network"], a["name"], a["status"]) for a in accounts] == [
        ("youtube", "Studio channel", "connected")
    ]
    assert accounts[0]["last_synced_at"] is not None
    with engine.connect() as connection:
        blob = connection.execute(text("SELECT secrets FROM app.social_accounts")).scalar_one()
    assert b"r1" not in bytes(blob) and b"a1" not in bytes(blob)

    data = client.get("/social/dashboard", headers=headers).json()
    assert data["kpis"]["followers"]["value"] == 120
    assert data["kpis"]["video_views"]["value"] == 40
    top = client.get("/social/posts/top", headers=headers).json()
    assert [p["caption"] for p in top] == ["Tour"] and top[0]["views"] == 50
    assert top[0]["permalink"].endswith("watch?v=v1")


def test_a_forged_or_wrong_callback_saves_nothing(
    client: TestClient, studio: dict, keys: None
) -> None:
    headers = with_studio(client, studio)
    forged = client.get("/social/callback/google?code=abc&state=nope", follow_redirects=False)
    assert "social_error=invalid_state" in forged.headers["location"]
    state = make_state(
        studio["tenant_id"], studio["owner"], "tiktok"
    )  # a TikTok state on Google's address
    wrong = client.get(f"/social/callback/google?code=abc&state={state}", follow_redirects=False)
    assert "social_error=invalid_state" in wrong.headers["location"]
    denied = client.get(
        f"/social/callback/tiktok?error=access_denied&state={state}", follow_redirects=False
    )
    assert "social_error=denied" in denied.headers["location"]
    assert client.get("/social/accounts", headers=headers).json() == []


def test_a_revoked_google_access_marks_the_account_for_reconnecting(
    client: TestClient, studio: dict, engine: Engine, keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = with_studio(client, studio)
    fake_google(monkeypatch, [])
    state = make_state(studio["tenant_id"], studio["owner"], "youtube")
    client.get(f"/social/callback/google?code=abc&state={state}", follow_redirects=False)

    def revoked(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        raise ReauthNeeded("refresh_token_rejected")

    monkeypatch.setattr(google, "request", revoked)
    account_id = client.get("/social/accounts", headers=headers).json()[0]["id"]
    with engine.begin() as connection:  # the daily job's path
        sync_account(connection, studio["tenant_id"], UUID(account_id))
    assert client.get("/social/accounts", headers=headers).json()[0]["status"] == "needs_reauth"


def test_tiktok_connects_and_reads_videos(
    client: TestClient, studio: dict, keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = with_studio(client, studio)
    stamp = int(datetime.now(UTC).timestamp())

    def answer(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        if url.endswith("/oauth/token/"):
            return {
                "access_token": "t1",
                "refresh_token": "rt1",
                "open_id": "OPEN1",
                "scope": "user.info.basic",
            }
        if url.endswith("/user/info/"):
            return {
                "data": {"user": {"display_name": "Studio TT", "follower_count": 900}},
                "error": {"code": "ok"},
            }
        if url.endswith("/video/list/"):
            return {
                "data": {
                    "videos": [
                        {
                            "id": 7,
                            "title": "Class clip",
                            "create_time": stamp,
                            "view_count": 300,
                            "like_count": 30,
                            "comment_count": 3,
                            "share_count": 2,
                            "share_url": "https://tiktok.com/v/7",
                        }
                    ],
                    "has_more": False,
                },
                "error": {"code": "ok"},
            }
        raise AssertionError(url)

    monkeypatch.setattr(tiktok, "request", answer)
    state = make_state(studio["tenant_id"], studio["owner"], "tiktok")
    done = client.get(f"/social/callback/tiktok?code=abc&state={state}", follow_redirects=False)
    assert "social_connected=1" in done.headers["location"]
    data = client.get("/social/dashboard", headers=headers).json()
    assert data["kpis"]["followers"]["value"] == 900
    assert data["kpis"]["video_views"]["value"] == 300
    assert data["kpis"]["engagements"]["value"] == 35
