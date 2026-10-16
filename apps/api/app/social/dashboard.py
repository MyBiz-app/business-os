"""The numbers behind the content studio dashboard, summed from our own daily history.

Every function takes the request's session, so row level security keeps it to one business."""

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

SUMMED = ("reach", "impressions", "video_views", "engagements", "profile_views", "link_clicks")
HEATMAP_DAYS = 90


@dataclass(frozen=True)
class Selection:
    """Which accounts the dashboard looks at: all, some accounts or some networks."""

    accounts: tuple[UUID, ...] | None = None
    networks: tuple[str, ...] | None = None

    def params(self) -> dict[str, object]:
        return {
            "accounts": [str(a) for a in self.accounts] if self.accounts else None,
            "networks": list(self.networks) if self.networks else None,
        }


ORDERS = {"views": "pm.views", "engagement": "(pm.likes + pm.comments + pm.shares + pm.saves)"}
SUMS = ", ".join(f"coalesce(sum(m.{c}), 0)::int AS {c}" for c in SUMMED)


def _sql(template: str, **parts: str) -> TextClause:
    """A query from a template and constant fragments (the account filter, column lists, an
    ORDER BY picked from ORDERS). Values never go in here: they are bound as :params."""
    for name, fragment in {"filter": ACCOUNT_FILTER, "sums": SUMS, **parts}.items():
        template = template.replace(f"@{name}@", fragment)
    return text(template)


# Added to a query that selects from `app.social_accounts a`.
ACCOUNT_FILTER = """
    (CAST(:accounts AS uuid[]) IS NULL OR a.id = ANY(CAST(:accounts AS uuid[])))
    AND (CAST(:networks AS text[]) IS NULL OR a.network = ANY(CAST(:networks AS text[])))
"""


def _totals(db: Session, selection: Selection, start: date, end: date) -> dict[str, int]:
    row = (
        db.execute(
            _sql("""
                SELECT @sums@
                FROM app.social_metrics_daily m
                JOIN app.social_accounts a ON a.id = m.account_id
                WHERE m.day BETWEEN :start AND :end AND @filter@
            """),
            {"start": start, "end": end, **selection.params()},
        )
        .mappings()
        .one()
    )
    return dict(row)


def _followers_at(db: Session, selection: Selection, day: date) -> int:
    """The followers of the selected accounts on a day (the latest known on or before it)."""
    return db.execute(
        _sql("""
            SELECT coalesce(sum(latest.followers), 0)::int FROM app.social_accounts a
            JOIN LATERAL (
                SELECT m.followers FROM app.social_metrics_daily m
                WHERE m.account_id = a.id AND m.day <= :day AND m.followers > 0
                ORDER BY m.day DESC LIMIT 1
            ) latest ON true
            WHERE @filter@
        """),
        {"day": day, **selection.params()},
    ).scalar_one()


def _rate_bp(totals: dict[str, int]) -> int:
    return round(10000 * totals["engagements"] / totals["reach"]) if totals["reach"] else 0


def dashboard(
    db: Session, selection: Selection, start: date, end: date, compare: bool, time_zone: str
) -> dict[str, object]:
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length - 1)
    now = _totals(db, selection, start, end)
    before = _totals(db, selection, prev_start, prev_end) if compare else None
    kpis: dict[str, dict[str, int | None]] = {
        "followers": {
            "value": _followers_at(db, selection, end),
            "previous": _followers_at(db, selection, prev_end),
        }
    }
    for key in SUMMED:
        kpis[key] = {"value": now[key], "previous": before[key] if before else None}
    kpis["engagement_rate_bp"] = {
        "value": _rate_bp(now),
        "previous": _rate_bp(before) if before else None,
    }

    followers = db.execute(
        _sql("""
            SELECT a.network, m.day, sum(m.followers)::int AS followers
            FROM app.social_metrics_daily m JOIN app.social_accounts a ON a.id = m.account_id
            WHERE m.day BETWEEN :start AND :end AND @filter@ AND m.followers > 0
              AND a.network <> 'google_business'
            GROUP BY a.network, m.day ORDER BY a.network, m.day
        """),
        {"start": start, "end": end, **selection.params()},
    ).mappings()
    series: dict[str, list[dict[str, object]]] = {}
    for row in followers:
        series.setdefault(row["network"], []).append(
            {"day": row["day"], "followers": row["followers"]}
        )

    weekly = db.execute(
        _sql("""
            SELECT date_trunc('week', m.day)::date AS week_start, sum(m.video_views)::int AS views
            FROM app.social_metrics_daily m JOIN app.social_accounts a ON a.id = m.account_id
            WHERE m.day BETWEEN :start AND :end AND @filter@
            GROUP BY 1 ORDER BY 1
        """),
        {"start": start, "end": end, **selection.params()},
    ).mappings()

    kinds = db.execute(
        _sql("""
            SELECT p.kind, sum(pm.likes + pm.comments + pm.shares + pm.saves)::int AS engagements
            FROM app.social_posts p
            JOIN app.social_post_metrics pm ON pm.post_id = p.id
            JOIN app.social_accounts a ON a.id = p.account_id
            WHERE p.published_at >= :start AND p.published_at < CAST(:end AS date) + 1
              AND @filter@
            GROUP BY p.kind ORDER BY 2 DESC
        """),
        {"start": start, "end": end, **selection.params()},
    ).mappings()

    cells = db.execute(
        _sql("""
            SELECT extract(dow FROM p.published_at AT TIME ZONE :tz)::int AS weekday,
                   extract(hour FROM p.published_at AT TIME ZONE :tz)::int AS hour,
                   round(avg(pm.likes + pm.comments + pm.shares + pm.saves))::int AS value
            FROM app.social_posts p
            JOIN app.social_post_metrics pm ON pm.post_id = p.id
            JOIN app.social_accounts a ON a.id = p.account_id
            WHERE p.published_at >= CAST(:end AS date) - :days AND @filter@
            GROUP BY 1, 2 ORDER BY 1, 2
        """),
        {"end": end, "days": HEATMAP_DAYS, "tz": time_zone, **selection.params()},
    ).mappings()

    google = (
        db.execute(
            _sql("""
                SELECT coalesce(sum(m.searches), 0)::int AS searches,
                       coalesce(sum(m.profile_views), 0)::int AS profile_views,
                       coalesce(sum(m.calls), 0)::int AS calls,
                       coalesce(sum(m.directions), 0)::int AS directions,
                       coalesce(sum(m.reviews_new), 0)::int AS reviews_new,
                       round(avg(m.rating), 2) AS rating
                FROM app.social_metrics_daily m JOIN app.social_accounts a ON a.id = m.account_id
                WHERE m.day BETWEEN :start AND :end AND a.network = 'google_business'
                  AND @filter@
                HAVING count(*) > 0
            """),
            {"start": start, "end": end, **selection.params()},
        )
        .mappings()
        .first()
    )
    return {
        "period_from": start,
        "period_to": end,
        "previous_from": prev_start if compare else None,
        "previous_to": prev_end if compare else None,
        "kpis": kpis,
        "followers_series": [{"network": n, "points": pts} for n, pts in series.items()],
        "video_views_weekly": [dict(r) for r in weekly],
        "engagement_by_kind": [dict(r) for r in kinds],
        "heatmap": [dict(r) for r in cells],
        "google_business": dict(google) if google else None,
    }


def top_posts(
    db: Session, selection: Selection, start: date, end: date, sort: str, limit: int
) -> list[dict[str, object]]:
    rows = db.execute(
        _sql(
            """
            SELECT p.id, a.network, a.name AS account_name, p.kind, p.published_at,
                   p.thumbnail_url, p.permalink, p.caption, pm.views,
                   (pm.likes + pm.comments + pm.shares + pm.saves) AS engagements,
                   pm.avg_watch_sec
            FROM app.social_posts p
            JOIN app.social_post_metrics pm ON pm.post_id = p.id
            JOIN app.social_accounts a ON a.id = p.account_id
            WHERE p.published_at >= :start AND p.published_at < CAST(:end AS date) + 1
              AND @filter@
            ORDER BY @order@ DESC, p.published_at DESC LIMIT :limit
        """,
            order=ORDERS[sort],
        ),
        {"start": start, "end": end, "limit": limit, **selection.params()},
    ).mappings()
    return [dict(r) for r in rows]


def audience(db: Session, selection: Selection) -> list[dict[str, object]]:
    """The audience of the selected accounts: each account's latest snapshot, weighted by its
    followers, so a big account counts more than a small one."""
    rows = db.execute(
        _sql("""
            WITH latest AS (
                SELECT a.id, max(s.captured_on) AS captured_on
                FROM app.social_accounts a JOIN app.social_audience s ON s.account_id = a.id
                WHERE @filter@ GROUP BY a.id
            ), weight AS (
                SELECT l.id, l.captured_on, greatest(coalesce((
                    SELECT m.followers FROM app.social_metrics_daily m
                    WHERE m.account_id = l.id ORDER BY m.day DESC LIMIT 1), 0), 1) AS w
                FROM latest l
            )
            SELECT s.dimension, s.label,
                   round(sum(s.share_bp::numeric * w.w) / sum(w.w))::int AS share_bp
            FROM weight w JOIN app.social_audience s
                ON s.account_id = w.id AND s.captured_on = w.captured_on
            GROUP BY s.dimension, s.label ORDER BY s.dimension, share_bp DESC
        """),
        selection.params(),
    ).mappings()
    return [dict(r) for r in rows]
