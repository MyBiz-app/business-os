"""Google connectors: YouTube (Data + Analytics APIs) and Google Business Profile.

One Google OAuth client serves both; each connection asks only for its own scope. Reads the
business's own channel / locations: subscribers, views, watch time, videos, reviews, searches,
calls and directions. Needs API_GOOGLE_OAUTH_CLIENT_ID / API_GOOGLE_OAUTH_CLIENT_SECRET."""

from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar
from urllib.parse import urlencode

from app.core.config import get_settings
from app.social.net import request
from app.social.providers import (
    AccountInfo,
    AudienceSlice,
    DayMetrics,
    NeedsReauth,
    NetworkError,
    PostData,
    register_social,
)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_DATA = "https://www.googleapis.com/youtube/v3"
YT_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
GBP_ACCOUNTS = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
GBP_INFO = "https://mybusinessbusinessinformation.googleapis.com/v1"
GBP_PERFORMANCE = "https://businessprofileperformance.googleapis.com/v1"
GBP_REVIEWS = "https://mybusiness.googleapis.com/v4"
MAX_ACCOUNTS = 50  # the owner picks which ones to connect
MAX_VIDEO_PAGES = 2


def _credentials() -> tuple[str, str] | None:
    settings = get_settings()
    if not settings.google_oauth_client_id or settings.google_oauth_client_secret is None:
        return None
    return settings.google_oauth_client_id, settings.google_oauth_client_secret.get_secret_value()


class GoogleProvider:
    """Shared OAuth for the Google networks. `scopes` is what each connection asks for."""

    name: str
    network: str
    scopes: tuple[str, ...]

    def configured(self) -> bool:
        return _credentials() is not None

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        credentials = _credentials()
        if credentials is None:
            raise NetworkError("google_not_configured")
        return (
            AUTH_URL
            + "?"
            + urlencode(
                {
                    "client_id": credentials[0],
                    "redirect_uri": redirect_uri,
                    "response_type": "code",
                    "scope": " ".join(self.scopes),
                    "access_type": "offline",
                    "prompt": "consent",  # a refresh token only comes with consent
                    "state": state,
                }
            )
        )

    def _token(self, form: dict[str, str]) -> dict[str, Any]:
        credentials = _credentials()
        if credentials is None:
            raise NetworkError("google_not_configured")
        try:
            return request(
                "POST",
                TOKEN_URL,
                data={"client_id": credentials[0], "client_secret": credentials[1], **form},
            )
        except NetworkError as error:
            if form.get("grant_type") == "refresh_token" and "HTTP 400" in str(error):
                raise NeedsReauth("refresh_token_rejected") from error  # invalid_grant
            raise

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]:
        token = self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri}
        )
        if not token.get("refresh_token"):
            raise NetworkError("no_refresh_token")
        secrets = {
            "refresh_token": token["refresh_token"],
            "access_token": token["access_token"],
            "expires_at": _expires(token),
        }
        return self._accounts(secrets, scopes=tuple(token.get("scope", "").split()))

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]:
        """A fresh access token (valid ~1 hour); the refresh token itself does not change."""
        token = self._token(
            {"grant_type": "refresh_token", "refresh_token": secrets["refresh_token"]}
        )
        return {**secrets, "access_token": token["access_token"], "expires_at": _expires(token)}

    def _accounts(self, secrets: dict[str, str], scopes: tuple[str, ...]) -> list[AccountInfo]:
        raise NotImplementedError

    def _get(self, secrets: dict[str, str], url: str, **params: Any) -> dict[str, Any]:
        return request("GET", url, token=secrets["access_token"], params=params)


def _expires(token: dict[str, Any]) -> str:
    """When the access token stops working. The sync renews tokens that expire within days
    (app/social/sync.py), so these short-lived ones are renewed on every run."""
    return (datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600)))).isoformat()


def _day(value: date) -> str:
    return value.isoformat()


class YouTubeProvider(GoogleProvider):
    name = "youtube"
    network = "youtube"
    scopes = (
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly",
    )

    def _accounts(self, secrets: dict[str, str], scopes: tuple[str, ...]) -> list[AccountInfo]:
        data = self._get(secrets, f"{YT_DATA}/channels", part="snippet", mine="true")
        return [
            AccountInfo(
                network=self.network,
                external_id=item["id"],
                name=item["snippet"]["title"][:200],
                avatar_url=item["snippet"].get("thumbnails", {}).get("default", {}).get("url"),
                scopes=scopes,
                secrets=secrets,
            )
            for item in data.get("items", [])[:MAX_ACCOUNTS]
        ]

    def _report(self, account: AccountInfo, **params: str) -> list[list[Any]]:
        data = self._get(account.secrets, YT_ANALYTICS, ids="channel==MINE", **params)
        return data.get("rows", [])

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        channel = self._get(account.secrets, f"{YT_DATA}/channels", part="statistics", mine="true")
        subscribers = int(channel["items"][0]["statistics"].get("subscriberCount", 0))
        rows = self._report(
            account,
            startDate=_day(since),
            endDate=_day(until),
            dimensions="day",
            sort="-day",
            metrics="views,likes,comments,shares,subscribersGained,subscribersLost",
        )
        out: list[DayMetrics] = []
        followers = subscribers  # walked backwards from today's total with each day's net change
        for day, views, likes, comments, shares, gained, lost in rows:  # newest first
            out.append(
                DayMetrics(
                    day=date.fromisoformat(day),
                    followers=max(followers, 0),
                    impressions=int(views),
                    video_views=int(views),
                    engagements=int(likes) + int(comments) + int(shares),
                )
            )
            followers -= int(gained) - int(lost)
        return sorted(out, key=lambda m: m.day)

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        channel = self._get(
            account.secrets, f"{YT_DATA}/channels", part="contentDetails", mine="true"
        )
        uploads = channel["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ids: list[str] = []
        page: str | None = None
        for _ in range(MAX_VIDEO_PAGES):
            params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
            if page:
                params["pageToken"] = page
            data = self._get(account.secrets, f"{YT_DATA}/playlistItems", **params)
            ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])]
            page = data.get("nextPageToken")
            if not page:
                break
        posts: list[PostData] = []
        for start in range(0, len(ids), 50):
            data = self._get(
                account.secrets,
                f"{YT_DATA}/videos",
                part="snippet,statistics",
                id=",".join(ids[start : start + 50]),
            )
            for item in data.get("items", []):
                published = datetime.fromisoformat(item["snippet"]["publishedAt"])
                stats = item.get("statistics", {})
                posts.append(
                    PostData(
                        external_id=item["id"],
                        kind="video",
                        published_at=published,
                        caption=item["snippet"].get("title"),
                        thumbnail_url=item["snippet"]
                        .get("thumbnails", {})
                        .get("medium", {})
                        .get("url"),
                        permalink=f"https://www.youtube.com/watch?v={item['id']}",
                        views=int(stats.get("viewCount", 0)),
                        likes=int(stats.get("likeCount", 0)),
                        comments=int(stats.get("commentCount", 0)),
                    )
                )
        return posts

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        end = datetime.now(UTC).date()
        window = {"startDate": _day(end - timedelta(days=90)), "endDate": _day(end)}
        slices: list[AudienceSlice] = []
        try:
            demographics = self._report(
                account, dimensions="ageGroup,gender", metrics="viewerPercentage", **window
            )
            ages: dict[str, float] = {}
            genders: dict[str, float] = {}
            for age, gender, percent in demographics:
                ages[age.removeprefix("age")] = ages.get(age.removeprefix("age"), 0) + percent
                genders[gender] = genders.get(gender, 0) + percent
            slices += [AudienceSlice("age", k, round(v * 100)) for k, v in ages.items()]
            slices += [AudienceSlice("gender", k, round(v * 100)) for k, v in genders.items()]
            countries = self._report(
                account,
                dimensions="country",
                metrics="views",
                sort="-views",
                maxResults="5",
                **window,
            )
            total = sum(int(r[1]) for r in countries) or 1
            slices += [
                AudienceSlice("country", r[0], round(int(r[1]) / total * 10000)) for r in countries
            ]
        except NetworkError:
            pass  # channels with few viewers have no demographics; the rest of the sync stays
        return slices


class GoogleBusinessProvider(GoogleProvider):
    name = "google_business"
    network = "google_business"
    scopes = ("https://www.googleapis.com/auth/business.manage",)
    _METRICS: ClassVar[dict[str, str]] = {
        "BUSINESS_IMPRESSIONS_DESKTOP_MAPS": "profile_views",
        "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH": "searches",
        "BUSINESS_IMPRESSIONS_MOBILE_MAPS": "profile_views",
        "BUSINESS_IMPRESSIONS_MOBILE_SEARCH": "searches",
        "CALL_CLICKS": "calls",
        "BUSINESS_DIRECTION_REQUESTS": "directions",
        "WEBSITE_CLICKS": "link_clicks",
    }

    def _accounts(self, secrets: dict[str, str], scopes: tuple[str, ...]) -> list[AccountInfo]:
        found: list[AccountInfo] = []
        for account in self._get(secrets, GBP_ACCOUNTS).get("accounts", []):
            data = self._get(
                secrets,
                f"{GBP_INFO}/{account['name']}/locations",
                readMask="name,title",
                pageSize=100,
            )
            for location in data.get("locations", []):
                found.append(
                    AccountInfo(
                        network=self.network,
                        external_id=location["name"],  # locations/123
                        name=location.get("title", location["name"])[:200],
                        scopes=scopes,
                        secrets={**secrets, "account": account["name"]},  # accounts/456
                    )
                )
        return found[:MAX_ACCOUNTS]

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        query: list[tuple[str, Any]] = [("dailyMetrics", m) for m in self._METRICS] + [
            ("dailyRange.startDate.year", since.year),
            ("dailyRange.startDate.month", since.month),
            ("dailyRange.startDate.day", since.day),
            ("dailyRange.endDate.year", until.year),
            ("dailyRange.endDate.month", until.month),
            ("dailyRange.endDate.day", until.day),
        ]
        data = request(
            "GET",
            f"{GBP_PERFORMANCE}/{account.external_id}:fetchMultiDailyMetricsTimeSeries",
            token=account.secrets["access_token"],
            params=query,
        )
        days: dict[date, dict[str, int]] = {}
        for group in data.get("multiDailyMetricTimeSeries", []):
            for series in group.get("dailyMetricTimeSeries", []):
                column = self._METRICS.get(series.get("dailyMetric", ""))
                if column is None:
                    continue
                for point in series.get("timeSeries", {}).get("datedValues", []):
                    d = point["date"]
                    day = date(d["year"], d["month"], d["day"])
                    bucket = days.setdefault(day, {})
                    bucket[column] = bucket.get(column, 0) + int(point.get("value", 0))
        reviews = self._reviews(account)
        new_by_day: dict[date, int] = {}
        for review in reviews["items"]:
            created = datetime.fromisoformat(review["createTime"].replace("Z", "+00:00")).date()
            new_by_day[created] = new_by_day.get(created, 0) + 1
        out = [
            DayMetrics(day=day, reviews_new=new_by_day.get(day, 0), **values)
            for day, values in sorted(days.items())
        ]
        if out and reviews["rating"] is not None:  # only the latest day carries today's rating
            last = out[-1]
            out[-1] = DayMetrics(**{**last.__dict__, "rating": reviews["rating"]})
        return out

    def _reviews(self, account: AccountInfo) -> dict[str, Any]:
        """Reviews live only in the older v4 API; the first page (newest first) is enough."""
        data = request(
            "GET",
            f"{GBP_REVIEWS}/{account.secrets['account']}/{account.external_id}/reviews",
            token=account.secrets["access_token"],
            params={"pageSize": 50, "orderBy": "updateTime desc"},
        )
        rating = data.get("averageRating")
        return {
            "items": data.get("reviews", []),
            "rating": round(float(rating), 2) if rating else None,
        }

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        return []  # a Business Profile has reviews and searches, not posts to rank

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        return []


register_social(YouTubeProvider())
register_social(GoogleBusinessProvider())
