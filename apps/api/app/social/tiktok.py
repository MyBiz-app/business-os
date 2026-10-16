"""TikTok connector (Login Kit v2 + Display API).

Reads the business's own profile and videos: followers, likes, and every video's views, likes,
comments and shares. TikTok keeps no daily history for us, so the followers count is stored for
the day we read it (the history builds up by itself) and a video's numbers count on the day it
was published. Needs API_TIKTOK_CLIENT_KEY / API_TIKTOK_CLIENT_SECRET."""

from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode

from app.core.config import get_settings
from app.social.oauth import ProviderUnavailable, request
from app.social.providers import (
    AccountInfo,
    AudienceSlice,
    DayMetrics,
    PostData,
    ReauthNeeded,
    register_social,
)

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,user.info.stats,video.list"
MAX_PAGES = 5  # 20 videos a page


def _credentials() -> tuple[str, str] | None:
    settings = get_settings()
    if not settings.tiktok_client_key or settings.tiktok_client_secret is None:
        return None
    return settings.tiktok_client_key, settings.tiktok_client_secret.get_secret_value()


def _checked(data: dict[str, Any]) -> dict[str, Any]:
    """TikTok reports many failures inside a normal answer, as `error.code`."""
    code = (data.get("error") or {}).get("code", "ok")
    if code == "ok":
        return data
    if code in ("access_token_invalid", "access_token_expired", "invalid_grant"):
        raise ReauthNeeded(code)
    raise ProviderUnavailable(code)


class TikTokProvider:
    name = "tiktok"
    callback = "tiktok"

    def configured(self) -> bool:
        return _credentials() is not None

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        credentials = _credentials()
        if credentials is None:
            raise ProviderUnavailable("tiktok_not_configured")
        return (
            AUTH_URL
            + "?"
            + urlencode(
                {
                    "client_key": credentials[0],
                    "scope": SCOPES,
                    "response_type": "code",
                    "redirect_uri": redirect_uri,
                    "state": state,
                }
            )
        )

    def _token(self, form: dict[str, str]) -> dict[str, Any]:
        credentials = _credentials()
        if credentials is None:
            raise ProviderUnavailable("tiktok_not_configured")
        try:
            data = request(
                "POST",
                f"{API}/oauth/token/",
                data={"client_key": credentials[0], "client_secret": credentials[1], **form},
            )
        except ProviderUnavailable as error:
            if form.get("grant_type") == "refresh_token" and "HTTP 4" in str(error):
                raise ReauthNeeded("refresh_token_rejected") from error
            raise
        if "access_token" not in data:
            _checked({"error": {"code": data.get("error", "no_token")}})
        return data

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]:
        token = self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
        )
        secrets = {
            "access_token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "open_id": token["open_id"],
        }
        user = self._user(secrets, "open_id,display_name,avatar_url")
        return [
            AccountInfo(
                network="tiktok",
                external_id=token["open_id"],
                name=(user.get("display_name") or "TikTok")[:200],
                avatar_url=user.get("avatar_url"),
                scopes=tuple(token.get("scope", SCOPES).split(",")),
                secrets=secrets,
            )
        ]

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]:
        """Access tokens last a day; TikTok may hand back a new refresh token, which replaces
        the old one."""
        token = self._token(
            {"grant_type": "refresh_token", "refresh_token": secrets["refresh_token"]}
        )
        return {
            **secrets,
            "access_token": token["access_token"],
            "refresh_token": token.get("refresh_token", secrets["refresh_token"]),
        }

    def _user(self, secrets: dict[str, str], fields: str) -> dict[str, Any]:
        data = _checked(
            request(
                "GET", f"{API}/user/info/", token=secrets["access_token"], params={"fields": fields}
            )
        )
        return data["data"]["user"]

    def _videos(self, secrets: dict[str, str]) -> list[dict[str, Any]]:
        videos: list[dict[str, Any]] = []
        cursor: int | None = None
        fields = (
            "id,title,cover_image_url,create_time,share_url,"
            "view_count,like_count,comment_count,share_count"
        )
        for _ in range(MAX_PAGES):
            body: dict[str, Any] = {"max_count": 20}
            if cursor is not None:
                body["cursor"] = cursor
            data = _checked(
                request(
                    "POST",
                    f"{API}/video/list/",
                    token=secrets["access_token"],
                    params={"fields": fields},
                    json=body,
                )
            )["data"]
            videos += data.get("videos", [])
            if not data.get("has_more"):
                break
            cursor = data.get("cursor")
        return videos

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        user = self._user(account.secrets, "follower_count")
        by_day: dict[date, dict[str, int]] = {}
        for video in self._videos(account.secrets):
            day = datetime.fromtimestamp(video["create_time"], UTC).date()
            if not since <= day <= until:
                continue
            bucket = by_day.setdefault(day, {"views": 0, "engagements": 0})
            bucket["views"] += video.get("view_count", 0)
            bucket["engagements"] += sum(
                video.get(k, 0) for k in ("like_count", "comment_count", "share_count")
            )
        today = datetime.now(UTC).date()
        by_day.setdefault(today, {"views": 0, "engagements": 0})
        return [
            DayMetrics(
                day=day,
                followers=int(user.get("follower_count", 0)) if day == today else 0,
                impressions=values["views"],
                video_views=values["views"],
                engagements=values["engagements"],
            )
            for day, values in sorted(by_day.items())
        ]

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        return [
            PostData(
                external_id=str(v["id"]),
                kind="video",
                published_at=datetime.fromtimestamp(v["create_time"], UTC),
                caption=v.get("title"),
                thumbnail_url=v.get("cover_image_url"),
                permalink=v.get("share_url"),
                views=v.get("view_count", 0),
                likes=v.get("like_count", 0),
                comments=v.get("comment_count", 0),
                shares=v.get("share_count", 0),
            )
            for v in self._videos(account.secrets)
            if datetime.fromtimestamp(v["create_time"], UTC) >= since
        ]

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        return []  # the Display API gives no audience breakdown


register_social(TikTokProvider())
