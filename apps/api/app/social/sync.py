"""Connecting accounts and syncing their numbers into our own tables.

Works with a request session (tenant set by RLS) and with the jobs' owner connection alike:
every statement names the tenant."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.providers.secrets import decrypt, encrypt
from app.social.providers import AccountInfo, ReauthNeeded, SocialProvider, social_provider

FIRST_SYNC_DAYS = 90
RESYNC_OVERLAP_DAYS = 3  # recent days are revised by the networks, so they are read again
Db = Session | Connection


def add_account(
    db: Db,
    tenant_id: UUID,
    provider: str,
    info: AccountInfo,
    *,
    is_demo: bool = False,
    location_id: UUID | None = None,
    connected_by: UUID | None = None,
) -> UUID:
    """Stores a connected account (or refreshes it when the same account connects again)."""
    return db.execute(
        text("""
            INSERT INTO app.social_accounts
                (tenant_id, location_id, provider, network, external_id, name, avatar_url,
                 is_demo, scopes, secrets, connected_by)
            VALUES (:t, :location, :provider, :network, :external, :name, :avatar,
                    :demo, :scopes, :secrets, :by)
            ON CONFLICT (tenant_id, network, external_id) DO UPDATE
                SET name = EXCLUDED.name, avatar_url = EXCLUDED.avatar_url,
                    scopes = EXCLUDED.scopes, secrets = EXCLUDED.secrets, status = 'connected'
            RETURNING id
        """),
        {
            "t": tenant_id,
            "location": location_id,
            "provider": provider,
            "network": info.network,
            "external": info.external_id,
            "name": info.name,
            "avatar": info.avatar_url,
            "demo": is_demo,
            "scopes": list(info.scopes),
            "secrets": encrypt(info.secrets) if info.secrets else None,
            "by": connected_by,
        },
    ).scalar_one()


def sync_account(db: Db, tenant_id: UUID, account_id: UUID, today: date | None = None) -> None:
    """Reads the account's latest numbers from its provider and stores them."""
    row = (
        db.execute(
            text("""
                SELECT provider, network, external_id, name, secrets
                FROM app.social_accounts WHERE id = :a AND tenant_id = :t
            """),
            {"a": account_id, "t": tenant_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return
    provider: SocialProvider | None = social_provider(row["provider"])
    if provider is None:
        return
    info = AccountInfo(
        network=row["network"],
        external_id=row["external_id"],
        name=row["name"],
        secrets=decrypt(row["secrets"]),
    )
    if info.secrets:  # real connections: a fresh access token first (and keep a rotated one)
        try:
            renewed = provider.refresh(info.secrets)
        except ReauthNeeded:
            db.execute(
                text("UPDATE app.social_accounts SET status = 'needs_reauth' WHERE id = :a"),
                {"a": account_id},
            )
            return
        if renewed != info.secrets:
            db.execute(
                text("UPDATE app.social_accounts SET secrets = :s WHERE id = :a"),
                {"s": encrypt(renewed), "a": account_id},
            )
        info = AccountInfo(**{**info.__dict__, "secrets": renewed})
    today = today or datetime.now(UTC).date()
    last = db.execute(
        text("SELECT max(day) FROM app.social_metrics_daily WHERE account_id = :a"),
        {"a": account_id},
    ).scalar_one()
    since = (
        last - timedelta(days=RESYNC_OVERLAP_DAYS)
        if last
        else today - timedelta(days=FIRST_SYNC_DAYS)
    )
    try:
        metrics = provider.fetch_account_metrics(info, since, today)
        posts = provider.fetch_posts(info, datetime.combine(since, datetime.min.time(), tzinfo=UTC))
        audience = provider.fetch_audience(info)
    except ReauthNeeded:
        db.execute(
            text("UPDATE app.social_accounts SET status = 'needs_reauth' WHERE id = :a"),
            {"a": account_id},
        )
        return
    for m in metrics:
        db.execute(
            text("""
                INSERT INTO app.social_metrics_daily
                    (tenant_id, account_id, day, followers, reach, impressions, video_views,
                     engagements, profile_views, link_clicks, calls, directions, searches,
                     reviews_new, rating)
                VALUES (:t, :a, :day, :followers, :reach, :impressions, :video_views,
                        :engagements, :profile_views, :link_clicks, :calls, :directions,
                        :searches, :reviews_new, :rating)
                ON CONFLICT (account_id, day) DO UPDATE SET
                    followers = CASE WHEN EXCLUDED.followers = 0 THEN social_metrics_daily.followers
                                     ELSE EXCLUDED.followers END, reach = EXCLUDED.reach,
                    impressions = EXCLUDED.impressions, video_views = EXCLUDED.video_views,
                    engagements = EXCLUDED.engagements, profile_views = EXCLUDED.profile_views,
                    link_clicks = EXCLUDED.link_clicks, calls = EXCLUDED.calls,
                    directions = EXCLUDED.directions, searches = EXCLUDED.searches,
                    reviews_new = EXCLUDED.reviews_new, rating = EXCLUDED.rating
            """),
            {"t": tenant_id, "a": account_id, **m.__dict__},
        )
    for p in posts:
        post_id = db.execute(
            text("""
                INSERT INTO app.social_posts
                    (tenant_id, account_id, external_id, kind, published_at, thumbnail_url,
                     permalink, caption)
                VALUES (:t, :a, :external, :kind, :published, :thumb, :link, :caption)
                ON CONFLICT (account_id, external_id) DO UPDATE
                    SET caption = EXCLUDED.caption, thumbnail_url = EXCLUDED.thumbnail_url,
                        permalink = EXCLUDED.permalink
                RETURNING id
            """),
            {
                "t": tenant_id,
                "a": account_id,
                "external": p.external_id,
                "kind": p.kind,
                "published": p.published_at,
                "thumb": p.thumbnail_url,
                "link": p.permalink,
                "caption": (p.caption or None) and p.caption[:300],
            },
        ).scalar_one()
        db.execute(
            text("""
                INSERT INTO app.social_post_metrics
                    (post_id, tenant_id, views, likes, comments, shares, saves, avg_watch_sec)
                VALUES (:post, :t, :views, :likes, :comments, :shares, :saves, :watch)
                ON CONFLICT (post_id) DO UPDATE SET
                    views = EXCLUDED.views, likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments, shares = EXCLUDED.shares,
                    saves = EXCLUDED.saves, avg_watch_sec = EXCLUDED.avg_watch_sec,
                    updated_at = now()
            """),
            {
                "post": post_id,
                "t": tenant_id,
                "views": p.views,
                "likes": p.likes,
                "comments": p.comments,
                "shares": p.shares,
                "saves": p.saves,
                "watch": p.avg_watch_sec,
            },
        )
    for s in audience:
        db.execute(
            text("""
                INSERT INTO app.social_audience
                    (tenant_id, account_id, captured_on, dimension, label, share_bp)
                VALUES (:t, :a, :day, :dimension, :label, :share)
                ON CONFLICT (account_id, captured_on, dimension, label)
                DO UPDATE SET share_bp = EXCLUDED.share_bp
            """),
            {
                "t": tenant_id,
                "a": account_id,
                "day": today,
                "dimension": s.dimension,
                "label": s.label,
                "share": s.share_bp,
            },
        )
    db.execute(
        text("UPDATE app.social_accounts SET last_synced_at = now() WHERE id = :a"),
        {"a": account_id},
    )
