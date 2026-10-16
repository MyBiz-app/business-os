"""Social providers: how a network is connected and how its numbers are read.

Each provider is one small class registered here. Adding a network is adding one file and one
`register_social` call (see docs/integrations.md). The networks a business can see are listed in
NETWORKS; a network whose provider is not registered yet shows as "coming soon".

Only summarized, public numbers of the business's own accounts are read: followers, reach, views,
engagement, its own posts and audience shares. Never private messages, never personal data of
followers."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

Kind = str  # post | reel | story | video


@dataclass(frozen=True)
class Network:
    key: str
    provider: str  # the provider that connects it (one provider may serve several networks)
    gives: tuple[str, ...]  # what the business gets, as i18n keys of the studio screens


NETWORKS: tuple[Network, ...] = (
    Network("facebook", "meta", ("followers", "reach", "videos", "engagement", "posts")),
    Network("instagram", "meta", ("followers", "reach", "videos", "engagement", "audience")),
    Network("threads", "meta", ("followers", "views", "engagement")),
    Network("youtube", "youtube", ("followers", "views", "watch_time", "videos")),
    Network("tiktok", "tiktok", ("followers", "views", "engagement", "videos")),
    Network("google_business", "google_business", ("reviews", "searches", "calls", "directions")),
    Network("x", "x", ("followers", "views", "engagement")),
    Network("linkedin", "linkedin", ("followers", "views", "engagement")),
    Network("pinterest", "pinterest", ("followers", "views", "engagement")),
    Network("snapchat", "snapchat", ("followers", "views")),
)
NETWORK_KEYS: tuple[str, ...] = tuple(n.key for n in NETWORKS)


@dataclass(frozen=True)
class AccountInfo:
    """One account a provider found after the business agreed to connect."""

    network: str
    external_id: str
    name: str
    avatar_url: str | None = None
    scopes: tuple[str, ...] = ()
    secrets: dict[str, str] = field(default_factory=dict)  # tokens, stored encrypted


@dataclass(frozen=True)
class DayMetrics:
    day: date
    followers: int = 0
    reach: int = 0
    impressions: int = 0
    video_views: int = 0
    engagements: int = 0
    profile_views: int = 0
    link_clicks: int = 0
    calls: int = 0
    directions: int = 0
    searches: int = 0
    reviews_new: int = 0
    rating: float | None = None


@dataclass(frozen=True)
class PostData:
    external_id: str
    kind: Kind
    published_at: datetime
    caption: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    avg_watch_sec: int | None = None


@dataclass(frozen=True)
class AudienceSlice:
    dimension: str  # age | gender | city | country
    label: str
    share_bp: int  # basis points: 10000 = 100%


class ReauthNeeded(Exception):
    """The network no longer accepts the saved access (revoked by the owner, or expired): the
    account is marked "needs reconnecting" instead of failing every sync."""


class SocialProvider(Protocol):
    """A connector may also define `callback` (the family in /social/callback/{family}) and
    `configured()` (False while the platform's developer keys are missing)."""

    name: str

    def authorize_url(self, state: str, redirect_uri: str) -> str: ...

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]: ...

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]: ...

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]: ...

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]: ...

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]: ...


_PROVIDERS: dict[str, SocialProvider] = {}


def register_social(provider: SocialProvider) -> None:
    if provider.name in _PROVIDERS:
        raise ValueError(f"social provider registered twice: {provider.name}")
    _PROVIDERS[provider.name] = provider


def social_provider(name: str) -> SocialProvider | None:
    return _PROVIDERS.get(name)


def network_ready(provider: SocialProvider) -> bool:
    """A provider can be connected once its platform keys are set (it may have none to set)."""
    return bool(getattr(provider, "configured", lambda: True)())


def network_status(network: Network) -> str:
    """ "available" once the network's provider is registered and configured, else "soon"."""
    provider = _PROVIDERS.get(network.provider)
    return "available" if provider is not None and network_ready(provider) else "soon"


def _load_providers() -> None:
    from app.social import demo, google, soon, tiktok  # noqa: F401  (each registers itself)


_load_providers()
