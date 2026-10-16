"""Content studio: connected social accounts and their analytics (migration 0093).

Needs the `social_studio` module. `social.read` opens the dashboard, `social.manage` connects and
disconnects accounts. Only summarized, public numbers of the business's own accounts are kept."""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from app.api.common import not_found
from app.api.deps import TenantContext, has_module, require
from app.core.permissions import Permission
from app.social import dashboard as stats
from app.social.demo import DEMO
from app.social.providers import NETWORK_KEYS, NETWORKS, network_status
from app.social.sync import add_account, sync_account

router = APIRouter(prefix="/social", tags=["social"])

SYNC_COOLDOWN = timedelta(hours=1)
MAX_RANGE_DAYS = 400


def _studio(permission: Permission):
    def check(context: Annotated[TenantContext, Depends(require(permission))]) -> TenantContext:
        if not has_module(context.session, "social_studio"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="module_disabled")
        return context

    return check


ReadDep = Annotated[TenantContext, Depends(_studio(Permission.SOCIAL_READ))]
ManageDep = Annotated[TenantContext, Depends(_studio(Permission.SOCIAL_MANAGE))]


class NetworkOption(BaseModel):
    network: str
    provider: str
    status: Literal["available", "soon"]
    gives: list[str]
    connected: int


class SocialProviders(BaseModel):
    networks: list[NetworkOption]
    demo_available: bool


class SocialAccount(BaseModel):
    id: UUID
    network: str
    name: str
    provider: str
    status: Literal["connected", "needs_reauth"]
    is_demo: bool
    location_id: UUID | None
    last_synced_at: datetime | None


class Kpi(BaseModel):
    value: int
    previous: int | None


class FollowerPoint(BaseModel):
    day: date
    followers: int


class FollowerSeries(BaseModel):
    network: str
    points: list[FollowerPoint]


class WeeklyViews(BaseModel):
    week_start: date
    views: int


class KindEngagement(BaseModel):
    kind: str
    engagements: int


class HeatCell(BaseModel):
    weekday: int  # 0 = Sunday
    hour: int
    value: int


class GoogleBusiness(BaseModel):
    searches: int
    profile_views: int
    calls: int
    directions: int
    reviews_new: int
    rating: float | None


class SocialDashboard(BaseModel):
    period_from: date
    period_to: date
    previous_from: date | None
    previous_to: date | None
    kpis: dict[str, Kpi]
    followers_series: list[FollowerSeries]
    video_views_weekly: list[WeeklyViews]
    engagement_by_kind: list[KindEngagement]
    heatmap: list[HeatCell]
    google_business: GoogleBusiness | None


class TopPost(BaseModel):
    id: UUID
    network: str
    account_name: str
    kind: str
    published_at: datetime
    thumbnail_url: str | None
    permalink: str | None
    caption: str | None
    views: int
    engagements: int
    avg_watch_sec: int | None


class AudienceShare(BaseModel):
    dimension: Literal["age", "gender", "city", "country"]
    label: str
    share_bp: int


class ConnectResult(BaseModel):
    accounts: list[SocialAccount]
    authorize_url: str | None = None


def _selection(accounts: list[UUID] | None, networks: list[str] | None) -> stats.Selection:
    if networks and any(n not in NETWORK_KEYS for n in networks):
        raise HTTPException(status_code=422, detail="unknown_network")
    return stats.Selection(
        accounts=tuple(accounts) if accounts else None,
        networks=tuple(networks) if networks else None,
    )


def _period(context: TenantContext, start: date | None, end: date | None) -> tuple[date, date]:
    end = end or datetime.now(UTC).date()
    start = start or end - timedelta(days=29)
    if start > end or (end - start).days >= MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail="invalid_period")
    return start, end


ACCOUNT_SELECT = """
    SELECT id, network, name, provider, status, is_demo, location_id, last_synced_at
    FROM app.social_accounts
"""

Accounts = Annotated[list[UUID] | None, Query(description="Only these accounts")]
Networks = Annotated[list[str] | None, Query(description="Only these networks")]


@router.get("/providers")
def list_social_providers(context: ReadDep) -> SocialProviders:
    """Every network the studio knows, and whether it can be connected yet or is "soon"."""
    counts = dict(
        context.session.execute(
            text("SELECT network, count(*) FROM app.social_accounts GROUP BY network")
        ).all()
    )
    return SocialProviders(
        networks=[
            NetworkOption(
                network=n.key,
                provider=n.provider,
                status=network_status(n),
                gives=list(n.gives),
                connected=counts.get(n.key, 0),
            )
            for n in NETWORKS
        ],
        demo_available=True,
    )


@router.get("/accounts")
def list_social_accounts(context: ReadDep) -> list[SocialAccount]:
    rows = context.session.execute(text(f"{ACCOUNT_SELECT} ORDER BY network, name")).mappings()
    return [SocialAccount.model_validate(dict(r)) for r in rows]


@router.post("/connect/{provider}", status_code=status.HTTP_201_CREATED)
def connect_social(provider: str, context: ManageDep) -> ConnectResult:
    """Starts a connection. `demo` connects sample accounts with believable numbers; other
    providers return the address where the owner agrees to share their numbers."""
    if provider == DEMO.name:
        for info in DEMO.accounts():
            account_id = add_account(
                context.session,
                context.tenant_id,
                DEMO.name,
                info,
                is_demo=True,
                connected_by=context.session.execute(text("SELECT app.current_user_id()")).scalar(),
            )
            sync_account(context.session, context.tenant_id, account_id)
        return ConnectResult(accounts=list_social_accounts(context))
    # The real connectors (Meta, YouTube, TikTok, Google) arrive with their own OAuth callback.
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="coming_soon")


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_social(account_id: UUID, context: ManageDep) -> None:
    """Removes the account and every number we kept for it. (The owner can also revoke access
    on the network itself.)"""
    deleted = context.session.execute(
        text("DELETE FROM app.social_accounts WHERE id = :id"), {"id": account_id}
    )
    if deleted.rowcount == 0:
        raise not_found()


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_social_now(context: ManageDep) -> list[SocialAccount]:
    """ "Refresh now": reads the latest numbers, at most once an hour."""
    recent = context.session.execute(
        text("SELECT max(last_synced_at) FROM app.social_accounts")
    ).scalar_one()
    if recent is not None and datetime.now(UTC) - recent < SYNC_COOLDOWN:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="sync_too_soon")
    ids = context.session.execute(text("SELECT id FROM app.social_accounts")).scalars().all()
    for account_id in ids:
        sync_account(context.session, context.tenant_id, account_id)
    return list_social_accounts(context)


@router.get("/dashboard")
def get_social_dashboard(
    context: ReadDep,
    accounts: Accounts = None,
    networks: Networks = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    compare: bool = False,
) -> SocialDashboard:
    start, end = _period(context, date_from, date_to)
    tz = context.session.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    data = stats.dashboard(context.session, _selection(accounts, networks), start, end, compare, tz)
    return SocialDashboard.model_validate(data)


@router.get("/posts/top")
def get_social_top_posts(
    context: ReadDep,
    accounts: Accounts = None,
    networks: Networks = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    sort: Literal["views", "engagement"] = "views",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[TopPost]:
    start, end = _period(context, date_from, date_to)
    rows = stats.top_posts(context.session, _selection(accounts, networks), start, end, sort, limit)
    return [TopPost.model_validate(r) for r in rows]


@router.get("/audience")
def get_social_audience(
    context: ReadDep, accounts: Accounts = None, networks: Networks = None
) -> list[AudienceShare]:
    rows = stats.audience(context.session, _selection(accounts, networks))
    return [AudienceShare.model_validate(r) for r in rows]
