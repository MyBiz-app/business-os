"""Meta: Facebook Pages and Instagram (one Facebook login) and Threads (its own login).

Only summarized, public numbers of the business's own accounts are read. The Graph API removes
and renames insight metrics from time to time, so every metric is asked for on its own and one
that is gone is skipped instead of breaking the whole sync. Needs API_META_APP_ID and
API_META_APP_SECRET (Threads: API_META_THREADS_APP_ID and API_META_THREADS_APP_SECRET); without
them the networks stay "coming soon"."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx2

from app.core.config import get_settings
from app.social.providers import (
    AccountInfo,
    AudienceSlice,
    DayMetrics,
    NeedsReauth,
    NetworkError,
    PostData,
    Published,
    register_social,
)

FB_SCOPES = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "read_insights",
    "instagram_basic",
    "instagram_manage_insights",
    "instagram_content_publish",
)
THREADS_SCOPES = (
    "threads_basic",
    "threads_content_publish",
    "threads_manage_insights",
)
THREADS_API = "https://graph.threads.net"
MAX_POSTS = 25  # per account and sync: each post costs one extra call for its numbers
TOKEN_ERROR_CODES = {102, 190}  # invalid or expired session / token


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone(UTC)


class _Graph:
    """A thin Graph-style HTTP client: JSON in, JSON out, errors as our own exceptions."""

    def __init__(self, client: httpx2.Client | None = None) -> None:
        self.client = client

    def call(self, method: str, url: str, **params: Any) -> dict[str, Any]:
        client = self.client or httpx2.Client(timeout=30.0)
        try:
            if method == "GET":
                response = client.get(url, params=params)
            else:
                response = client.post(url, data=params)
        except httpx2.HTTPError as error:
            raise NetworkError("unreachable") from error
        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error") if isinstance(body, dict) else None
        if response.status_code >= 400 or error:
            error = error or {}
            if error.get("code") in TOKEN_ERROR_CODES or response.status_code == 401:
                raise NeedsReauth(str(error.get("message", "token refused")))
            raise NetworkError(f"HTTP {response.status_code}: {error.get('message', '')}"[:200])
        return body

    def get(self, url: str, **params: Any) -> dict[str, Any]:
        return self.call("GET", url, **params)

    def post(self, url: str, **params: Any) -> dict[str, Any]:
        return self.call("POST", url, **params)

    def get_or_none(self, url: str, **params: Any) -> dict[str, Any] | None:
        """For optional numbers: a metric the network no longer offers gives None."""
        try:
            return self.get(url, **params)
        except NetworkError:
            return None


def _total(body: dict[str, Any] | None) -> int:
    """A number out of an insights answer (`total_value`, or the latest `values` entry)."""
    for item in (body or {}).get("data", []):
        if "total_value" in item:
            return int(item["total_value"].get("value", 0))
        if item.get("values"):
            return int(item["values"][-1].get("value", 0) or 0)
    return 0


def _series(body: dict[str, Any] | None) -> dict[date, int]:
    out: dict[date, int] = {}
    for item in (body or {}).get("data", []):
        for v in item.get("values", []):
            if v.get("end_time") and isinstance(v.get("value"), int | float):
                out[_ts(v["end_time"]).date() - timedelta(days=1)] = int(v["value"])
    return out


def _range(since: date, until: date) -> dict[str, int]:
    def midnight(d: date) -> int:
        return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())

    return {"since": midnight(since), "until": midnight(until + timedelta(days=1))}


class MetaProvider:
    """Facebook Pages and the Instagram business accounts linked to them."""

    name = "meta"

    def __init__(self) -> None:
        self.graph = _Graph()

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.meta_app_id and s.meta_app_secret)

    @property
    def base(self) -> str:
        return f"https://graph.facebook.com/{get_settings().meta_graph_version}"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        s = get_settings()
        query = urlencode(
            {
                "client_id": s.meta_app_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": ",".join(FB_SCOPES),
                "response_type": "code",
            }
        )
        return f"https://www.facebook.com/{s.meta_graph_version}/dialog/oauth?{query}"

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]:
        s = get_settings()
        assert s.meta_app_secret is not None
        app = {"client_id": s.meta_app_id, "client_secret": s.meta_app_secret.get_secret_value()}
        short = self.graph.get(
            f"{self.base}/oauth/access_token", redirect_uri=redirect_uri, code=code, **app
        )
        long = self.graph.get(
            f"{self.base}/oauth/access_token",
            grant_type="fb_exchange_token",
            fb_exchange_token=short["access_token"],
            **app,
        )
        pages = self.graph.get(
            f"{self.base}/me/accounts",
            access_token=long["access_token"],
            limit=100,
            fields="id,name,access_token,picture{url},"
            "instagram_business_account{id,username,name,profile_picture_url}",
        )
        found: list[AccountInfo] = []
        for page in pages.get("data", []):
            token = {"access_token": page["access_token"]}  # page tokens do not expire
            found.append(
                AccountInfo(
                    "facebook",
                    page["id"],
                    page["name"],
                    (page.get("picture") or {}).get("data", {}).get("url"),
                    FB_SCOPES,
                    token,
                )
            )
            ig = page.get("instagram_business_account")
            if ig:
                found.append(
                    AccountInfo(
                        "instagram",
                        ig["id"],
                        ig.get("username") or ig.get("name") or ig["id"],
                        ig.get("profile_picture_url"),
                        FB_SCOPES,
                        token,
                    )
                )
        return found

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]:
        return secrets  # page tokens from a long-lived login do not expire

    # -- reading ------------------------------------------------------------------------------

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        token = account.secrets["access_token"]
        if account.network == "instagram":
            return self._instagram_metrics(account, token, since, until)
        return self._facebook_metrics(account, token, since, until)

    def _facebook_metrics(
        self, account: AccountInfo, token: str, since: date, until: date
    ) -> list[DayMetrics]:
        page = self.graph.get(
            f"{self.base}/{account.external_id}",
            access_token=token,
            fields="followers_count,fan_count",
        )
        followers = int(page.get("followers_count") or page.get("fan_count") or 0)
        wanted = {
            "reach": "page_total_media_view_unique",
            "impressions": "page_media_view",
            "engagements": "page_post_engagements",
            "video_views": "page_video_views",
            "profile_views": "page_views_total",
        }
        per_field: dict[str, dict[date, int]] = {}
        for field_name, metric in wanted.items():
            body = self.graph.get_or_none(
                f"{self.base}/{account.external_id}/insights",
                access_token=token,
                metric=metric,
                period="day",
                **_range(since, until),
            )
            per_field[field_name] = _series(body)
        days = sorted({d for series in per_field.values() for d in series} | {until})
        return [
            DayMetrics(
                day=d,
                followers=followers if d == until else 0,
                **{name: series.get(d, 0) for name, series in per_field.items()},
            )
            for d in days
            if since <= d <= until
        ]

    def _instagram_metrics(
        self, account: AccountInfo, token: str, since: date, until: date
    ) -> list[DayMetrics]:
        user = self.graph.get(
            f"{self.base}/{account.external_id}", access_token=token, fields="followers_count"
        )
        reach = _series(
            self.graph.get_or_none(
                f"{self.base}/{account.external_id}/insights",
                access_token=token,
                metric="reach",
                period="day",
                **_range(since, until),
            )
        )

        def today(metric: str) -> int:
            return _total(
                self.graph.get_or_none(
                    f"{self.base}/{account.external_id}/insights",
                    access_token=token,
                    metric=metric,
                    metric_type="total_value",
                    period="day",
                    **_range(until, until),
                )
            )

        days = sorted(set(reach) | {until})
        return [
            DayMetrics(
                day=d,
                followers=int(user.get("followers_count", 0)) if d == until else 0,
                reach=reach.get(d, 0),
                impressions=today("views") if d == until else 0,
                engagements=today("total_interactions") if d == until else 0,
                profile_views=today("profile_views") if d == until else 0,
                link_clicks=today("website_clicks") if d == until else 0,
            )
            for d in days
            if since <= d <= until
        ]

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        token = account.secrets["access_token"]
        if account.network == "instagram":
            return self._instagram_posts(account, token, since)
        data = self.graph.get(
            f"{self.base}/{account.external_id}/published_posts",
            access_token=token,
            limit=MAX_POSTS,
            since=int(since.timestamp()),
            fields="id,message,created_time,permalink_url,full_picture,status_type,"
            "shares,likes.summary(true).limit(0),comments.summary(true).limit(0)",
        )
        posts = []
        for item in data.get("data", []):
            views = _total(
                self.graph.get_or_none(
                    f"{self.base}/{item['id']}/insights",
                    access_token=token,
                    metric="post_media_view",
                )
            )
            posts.append(
                PostData(
                    external_id=item["id"],
                    kind="video" if "video" in item.get("status_type", "") else "post",
                    published_at=_ts(item["created_time"]),
                    caption=item.get("message"),
                    thumbnail_url=item.get("full_picture"),
                    permalink=item.get("permalink_url"),
                    views=views,
                    likes=item.get("likes", {}).get("summary", {}).get("total_count", 0),
                    comments=item.get("comments", {}).get("summary", {}).get("total_count", 0),
                    shares=item.get("shares", {}).get("count", 0),
                )
            )
        return posts

    def _instagram_posts(self, account: AccountInfo, token: str, since: datetime) -> list[PostData]:
        data = self.graph.get(
            f"{self.base}/{account.external_id}/media",
            access_token=token,
            limit=MAX_POSTS,
            since=int(since.timestamp()),
            fields="id,caption,media_type,media_product_type,timestamp,permalink,thumbnail_url,"
            "media_url,like_count,comments_count",
        )
        posts = []
        for item in data.get("data", []):
            kind = (
                "reel"
                if item.get("media_product_type") == "REELS"
                else "story"
                if item.get("media_product_type") == "STORY"
                else "video"
                if item.get("media_type") == "VIDEO"
                else "post"
            )
            numbers = {
                m["name"]: int((m.get("values") or [{}])[0].get("value", 0) or 0)
                for m in (
                    self.graph.get_or_none(
                        f"{self.base}/{item['id']}/insights",
                        access_token=token,
                        metric="views,saved,shares",
                    )
                    or {}
                ).get("data", [])
            }
            posts.append(
                PostData(
                    external_id=item["id"],
                    kind=kind,
                    published_at=_ts(item["timestamp"]),
                    caption=item.get("caption"),
                    thumbnail_url=item.get("thumbnail_url") or item.get("media_url"),
                    permalink=item.get("permalink"),
                    views=numbers.get("views", 0),
                    likes=int(item.get("like_count", 0)),
                    comments=int(item.get("comments_count", 0)),
                    shares=numbers.get("shares", 0),
                    saves=numbers.get("saved", 0),
                )
            )
        return posts

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        if account.network != "instagram":
            return []  # Facebook stopped giving page audience breakdowns
        token = account.secrets["access_token"]
        out: list[AudienceSlice] = []
        for dimension in ("age", "gender", "city", "country"):
            body = self.graph.get_or_none(
                f"{self.base}/{account.external_id}/insights",
                access_token=token,
                metric="follower_demographics",
                period="lifetime",
                metric_type="total_value",
                timeframe="this_month",
                breakdown=dimension,
            )
            rows: list[tuple[str, int]] = []
            for item in (body or {}).get("data", []):
                for breakdown in item.get("total_value", {}).get("breakdowns", []):
                    for r in breakdown.get("results", []):
                        rows.append((str(r["dimension_values"][0]), int(r["value"])))
            total = sum(v for _, v in rows)
            for label, value in sorted(rows, key=lambda r: -r[1])[:10] if total else []:
                out.append(AudienceSlice(dimension, label[:100], round(value * 10000 / total)))
        return out

    # -- publishing ---------------------------------------------------------------------------

    def publish(self, account: AccountInfo, text: str, image_url: str | None) -> Published:
        token = account.secrets["access_token"]
        if account.network == "instagram":
            if not image_url:
                raise ValueError("image_required")
            container = self.graph.post(
                f"{self.base}/{account.external_id}/media",
                access_token=token,
                image_url=image_url,
                caption=text,
            )
            made = self.graph.post(
                f"{self.base}/{account.external_id}/media_publish",
                access_token=token,
                creation_id=container["id"],
            )
            link = self.graph.get_or_none(
                f"{self.base}/{made['id']}", access_token=token, fields="permalink"
            )
            return Published(made["id"], (link or {}).get("permalink"))
        if image_url:
            made = self.graph.post(
                f"{self.base}/{account.external_id}/photos",
                access_token=token,
                url=image_url,
                caption=text,
            )
            post_id = made.get("post_id") or made["id"]
        else:
            made = self.graph.post(
                f"{self.base}/{account.external_id}/feed", access_token=token, message=text
            )
            post_id = made["id"]
        link = self.graph.get_or_none(
            f"{self.base}/{post_id}", access_token=token, fields="permalink_url"
        )
        return Published(post_id, (link or {}).get("permalink_url"))


class ThreadsProvider:
    """Threads, through its own API and its own login."""

    name = "threads"

    def __init__(self) -> None:
        self.graph = _Graph()

    def configured(self) -> bool:
        s = get_settings()
        return bool(s.meta_threads_app_id and s.meta_threads_app_secret)

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        query = urlencode(
            {
                "client_id": get_settings().meta_threads_app_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "scope": ",".join(THREADS_SCOPES),
                "response_type": "code",
            }
        )
        return f"https://threads.net/oauth/authorize?{query}"

    def _expiry(self, seconds: int | None) -> str:
        return (datetime.now(UTC) + timedelta(seconds=seconds or 60 * 86400)).isoformat()

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]:
        s = get_settings()
        assert s.meta_threads_app_secret is not None
        secret = s.meta_threads_app_secret.get_secret_value()
        short = self.graph.post(
            f"{THREADS_API}/oauth/access_token",
            client_id=s.meta_threads_app_id,
            client_secret=secret,
            grant_type="authorization_code",
            redirect_uri=redirect_uri,
            code=code,
        )
        long = self.graph.get(
            f"{THREADS_API}/access_token",
            grant_type="th_exchange_token",
            client_secret=secret,
            access_token=short["access_token"],
        )
        me = self.graph.get(
            f"{THREADS_API}/{get_settings().meta_graph_version}/me",
            access_token=long["access_token"],
            fields="id,username,threads_profile_picture_url",
        )
        return [
            AccountInfo(
                "threads",
                str(me["id"]),
                me.get("username") or str(me["id"]),
                me.get("threads_profile_picture_url"),
                THREADS_SCOPES,
                {
                    "access_token": long["access_token"],
                    "expires_at": self._expiry(long.get("expires_in")),
                },
            )
        ]

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]:
        body = self.graph.get(
            f"{THREADS_API}/refresh_access_token",
            grant_type="th_refresh_token",
            access_token=secrets["access_token"],
        )
        return {
            "access_token": body["access_token"],
            "expires_at": self._expiry(body.get("expires_in")),
        }

    def _url(self, path: str) -> str:
        return f"{THREADS_API}/{get_settings().meta_graph_version}/{path}"

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        token = account.secrets["access_token"]
        base = self._url(f"{account.external_id}/threads_insights")
        views = _series(
            self.graph.get_or_none(
                base, access_token=token, metric="views", period="day", **_range(since, until)
            )
        )

        def total(metric: str) -> int:
            return _total(
                self.graph.get_or_none(
                    base,
                    access_token=token,
                    metric=metric,
                    metric_type="total_value",
                    **_range(until, until),
                )
            )

        followers = _total(
            self.graph.get_or_none(base, access_token=token, metric="followers_count")
        )
        engagements = sum(total(m) for m in ("likes", "replies", "reposts", "quotes"))
        return [
            DayMetrics(
                day=d,
                followers=followers if d == until else 0,
                video_views=views.get(d, 0),
                impressions=views.get(d, 0),
                engagements=engagements if d == until else 0,
            )
            for d in sorted(set(views) | {until})
            if since <= d <= until
        ]

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        token = account.secrets["access_token"]
        data = self.graph.get(
            self._url(f"{account.external_id}/threads"),
            access_token=token,
            limit=MAX_POSTS,
            since=since.date().isoformat(),
            fields="id,text,timestamp,permalink,media_type,thumbnail_url,media_url",
        )
        posts = []
        for item in data.get("data", []):
            numbers = {
                m["name"]: int((m.get("values") or [{}])[0].get("value", 0) or 0)
                for m in (
                    self.graph.get_or_none(
                        self._url(f"{item['id']}/insights"),
                        access_token=token,
                        metric="views,likes,replies,reposts,quotes",
                    )
                    or {}
                ).get("data", [])
            }
            posts.append(
                PostData(
                    external_id=item["id"],
                    kind="video" if item.get("media_type") == "VIDEO" else "post",
                    published_at=_ts(item["timestamp"]),
                    caption=item.get("text"),
                    thumbnail_url=item.get("thumbnail_url") or item.get("media_url"),
                    permalink=item.get("permalink"),
                    views=numbers.get("views", 0),
                    likes=numbers.get("likes", 0),
                    comments=numbers.get("replies", 0),
                    shares=numbers.get("reposts", 0) + numbers.get("quotes", 0),
                )
            )
        return posts

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        return []

    def publish(self, account: AccountInfo, text: str, image_url: str | None) -> Published:
        token = account.secrets["access_token"]
        fields: dict[str, Any] = {"access_token": token, "text": text}
        if image_url:
            fields.update(media_type="IMAGE", image_url=image_url)
        else:
            fields["media_type"] = "TEXT"
        container = self.graph.post(self._url(f"{account.external_id}/threads"), **fields)
        made = self.graph.post(
            self._url(f"{account.external_id}/threads_publish"),
            access_token=token,
            creation_id=container["id"],
        )
        link = self.graph.get_or_none(self._url(made["id"]), access_token=token, fields="permalink")
        return Published(made["id"], (link or {}).get("permalink"))


META = MetaProvider()
THREADS = ThreadsProvider()
register_social(META)
register_social(THREADS)
