"""The demo social provider: believable numbers for the dashboard before any network is connected.

Everything is generated from the account's id, so the numbers are stable between runs and look
different per network. Used by "show with demo data" and by tests; it never calls a network."""

import math
import random
import zlib
from datetime import UTC, date, datetime, timedelta

from app.social.providers import (
    AccountInfo,
    AudienceSlice,
    DayMetrics,
    PostData,
    register_social,
)

DEMO_NETWORKS = ("instagram", "facebook", "tiktok", "youtube", "google_business")
_SCALE = {  # roughly how big each network is for a small local business
    "instagram": 3200,
    "facebook": 2100,
    "tiktok": 5400,
    "youtube": 900,
    "google_business": 0,
}
_KINDS = {
    "instagram": ("reel", "post", "story"),
    "facebook": ("post", "video", "reel"),
    "tiktok": ("video",),
    "youtube": ("video",),
}
_CAPTIONS = (
    "Behind the scenes this week",
    "A new class is open for booking",
    "Meet the team",
    "Client story of the month",
    "Quick tip you can try today",
    "Our space, before opening",
    "Weekend special",
    "Three questions we always get",
)
_CITIES = ("Tel Aviv", "Jerusalem", "Haifa", "Ramat Gan", "Petah Tikva", "Beer Sheva")
_AGES = ("13-17", "18-24", "25-34", "35-44", "45-54", "55+")


def _rng(account: AccountInfo, salt: str = "") -> random.Random:
    return random.Random(zlib.crc32(f"{account.network}:{account.external_id}:{salt}".encode()))


class DemoProvider:
    name = "demo"

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError("the demo provider has nothing to authorize")

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]:
        raise NotImplementedError("the demo provider has nothing to authorize")

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]:
        return secrets

    def accounts(self) -> list[AccountInfo]:
        return [
            AccountInfo(network=n, external_id=f"demo-{n}", name=f"Demo {n.replace('_', ' ')}")
            for n in DEMO_NETWORKS
        ]

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        scale = _SCALE.get(account.network, 1000)
        days = (until - since).days + 1
        origin = date(2026, 1, 1)
        rows: list[DayMetrics] = []
        for offset in range(days):
            day = since + timedelta(days=offset)
            rng = _rng(account, day.isoformat())
            age = (day - origin).days
            weekly = 1 + 0.25 * math.sin(day.weekday() / 7 * 2 * math.pi)
            if account.network == "google_business":
                searches = int(rng.uniform(40, 90) * weekly)
                rows.append(
                    DayMetrics(
                        day=day,
                        profile_views=int(searches * rng.uniform(1.2, 1.8)),
                        searches=searches,
                        calls=int(rng.uniform(1, 9)),
                        directions=int(rng.uniform(2, 14)),
                        reviews_new=1 if rng.random() < 0.18 else 0,
                        rating=round(rng.uniform(4.5, 4.9), 2),
                    )
                )
                continue
            followers = int(scale + age * scale * 0.0016 + rng.uniform(-6, 6))
            reach = int(followers * rng.uniform(0.25, 0.6) * weekly)
            views = int(reach * rng.uniform(0.9, 1.6))
            video_views = int(views * 0.7) if account.network != "facebook" else int(views * 0.4)
            rows.append(
                DayMetrics(
                    day=day,
                    followers=followers,
                    reach=reach,
                    impressions=views,
                    video_views=video_views,
                    engagements=int(reach * rng.uniform(0.04, 0.11)),
                    profile_views=int(reach * rng.uniform(0.03, 0.08)),
                    link_clicks=int(reach * rng.uniform(0.004, 0.015)),
                )
            )
        return rows

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        kinds = _KINDS.get(account.network)
        if kinds is None:
            return []
        now = datetime.now(UTC)
        posts: list[PostData] = []
        day = since.date()
        scale = _SCALE.get(account.network, 1000)
        while day <= now.date():
            rng = _rng(account, f"post-{day.isoformat()}")
            if rng.random() < 0.42:
                hour = rng.choice((8, 9, 12, 13, 18, 19, 20, 21))
                views = int(scale * rng.uniform(0.2, 2.4))
                posts.append(
                    PostData(
                        external_id=f"{account.external_id}-{day.isoformat()}",
                        kind=rng.choice(kinds),
                        published_at=datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC),
                        caption=rng.choice(_CAPTIONS),
                        views=views,
                        likes=int(views * rng.uniform(0.03, 0.09)),
                        comments=int(views * rng.uniform(0.002, 0.012)),
                        shares=int(views * rng.uniform(0.001, 0.02)),
                        saves=int(views * rng.uniform(0.002, 0.03)),
                        avg_watch_sec=int(rng.uniform(4, 28)),
                    )
                )
            day += timedelta(days=1)
        return posts

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        if account.network == "google_business":
            return []
        rng = _rng(account, "audience")
        return [
            *_shares("age", _AGES, rng),
            *_shares("gender", ("female", "male", "other"), rng, tilt=(5, 4, 0.2)),
            *_shares("city", _CITIES, rng),
        ]


def _shares(
    dimension: str, labels: tuple[str, ...], rng: random.Random, tilt: tuple[float, ...] = ()
) -> list[AudienceSlice]:
    weights = [(tilt[i] if tilt else 1) * rng.uniform(0.4, 1.6) for i in range(len(labels))]
    total = sum(weights)
    shares = [int(10000 * w / total) for w in weights]
    shares[0] += 10000 - sum(shares)
    return [
        AudienceSlice(dimension, label, share) for label, share in zip(labels, shares, strict=True)
    ]


DEMO = DemoProvider()
register_social(DEMO)
