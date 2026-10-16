"""What the content agent (Sophie) reads and does in the content studio.

Everything takes the request's session, so row level security keeps it to one business. A
conversation kept to some branches only sees the accounts of those branches (a business-wide
account holds numbers of every branch, so it is not shown then)."""

from collections.abc import Collection
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.providers.secrets import decrypt
from app.social import dashboard as stats
from app.social.providers import AccountInfo, NeedsReauth, NetworkError, social_provider

MAX_DAYS = 90
MAX_DRAFTS = 10
BEST_TIMES = 5


def visible_accounts(
    db: Session, branches: Collection[UUID] | None, network: str = ""
) -> list[dict[str, Any]]:
    """The connected accounts in view, optionally of one network. `branches` None means the
    whole business."""
    rows = db.execute(
        text("""
            SELECT id, network, name, provider, status, is_demo, location_id, last_synced_at
            FROM app.social_accounts
            WHERE (:network = '' OR network = :network)
              AND (CAST(:branches AS uuid[]) IS NULL
                   OR location_id = ANY(CAST(:branches AS uuid[])))
            ORDER BY network, name
        """),
        {
            "network": network,
            "branches": [str(b) for b in branches] if branches is not None else None,
        },
    ).mappings()
    return [dict(r) for r in rows]


def can_publish(account: dict[str, Any]) -> bool:
    provider = social_provider(account["provider"])
    return (
        provider is not None
        and hasattr(provider, "publish")
        and not account["is_demo"]
        and account["status"] == "connected"
    )


def _selection(accounts: list[dict[str, Any]]) -> stats.Selection:
    return stats.Selection(accounts=tuple(a["id"] for a in accounts))


def period(days: int, today: date) -> tuple[date, date]:
    days = max(1, min(days, MAX_DAYS))
    return today - timedelta(days=days - 1), today


def overview(
    db: Session, accounts: list[dict[str, Any]], days: int, today: date, time_zone: str
) -> dict[str, Any]:
    """Summed numbers for the period and the one before, the best content kinds and the best
    times to post. No account, no numbers."""
    listing = [
        {
            "account_id": str(a["id"]),
            "network": a["network"],
            "name": a["name"],
            "needs_reconnecting": a["status"] != "connected",
            "demo": a["is_demo"],
            "can_publish": can_publish(a),
        }
        for a in accounts
    ]
    if not accounts:
        return {"accounts": [], "note": "no social account is connected (or in view) yet"}
    start, end = period(days, today)
    data = stats.dashboard(db, _selection(accounts), start, end, True, time_zone)
    best = sorted(data["heatmap"], key=lambda c: c["value"], reverse=True)[:BEST_TIMES]
    return {
        "accounts": listing,
        "period": f"{start} to {end}",
        "kpis": data["kpis"],
        "engagement_rate_note": "engagement_rate_bp is in basis points (100 = 1%)",
        "engagement_by_kind": data["engagement_by_kind"],
        "best_times": [
            {"weekday": c["weekday"], "hour": c["hour"], "avg_engagements": c["value"]}
            for c in best
        ],
        "weekday_note": "weekday 0 = Sunday; hours are local",
        "google_business": data["google_business"],
    }


def best_posts(
    db: Session, accounts: list[dict[str, Any]], days: int, today: date, sort: str, limit: int
) -> list[dict[str, Any]]:
    if not accounts:
        return []
    start, end = period(days, today)
    rows = stats.top_posts(db, _selection(accounts), start, end, sort, max(1, min(limit, 10)))
    return [
        {
            "network": r["network"],
            "kind": r["kind"],
            "published": r["published_at"].date().isoformat(),
            "caption": r["caption"],
            "views": r["views"],
            "engagements": r["engagements"],
            "link": r["permalink"],
        }
        for r in rows
    ]


def audience_summary(db: Session, accounts: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """The three biggest groups of each audience dimension (age, gender, city, ...)."""
    if not accounts:
        return {}
    found: dict[str, list[dict[str, Any]]] = {}
    for row in stats.audience(db, _selection(accounts)):
        group = found.setdefault(row["dimension"], [])
        if len(group) < 3:
            group.append({"label": row["label"], "percent": round(row["share_bp"] / 100, 1)})
    return found


def save_draft(
    db: Session,
    user_id: UUID,
    agent_key: str,
    network: str | None,
    body: str,
    image_url: str | None,
    idea: str | None,
) -> UUID:
    return db.execute(
        text("""
            INSERT INTO app.social_drafts
                (tenant_id, network, body, image_url, idea, created_by, agent_key)
            VALUES (app.current_tenant_id(), :network, :body, :image_url, :idea, :user, :agent)
            RETURNING id
        """),
        {
            "network": network,
            "body": body,
            "image_url": image_url,
            "idea": idea,
            "user": user_id,
            "agent": agent_key,
        },
    ).scalar_one()


def open_drafts(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT id, network, body, image_url, idea, created_at
            FROM app.social_drafts WHERE status = 'draft'
            ORDER BY created_at DESC LIMIT :limit
        """),
        {"limit": MAX_DRAFTS},
    ).mappings()
    return [dict(r) for r in rows]


def get_draft(db: Session, draft_id: UUID) -> dict[str, Any] | None:
    row = (
        db.execute(
            text("""
                SELECT id, network, body, image_url, status
                FROM app.social_drafts WHERE id = :id
            """),
            {"id": draft_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def publish_draft(db: Session, account_id: UUID, draft_id: UUID) -> dict[str, Any]:
    """Publishes an open draft on a connected account, then files the live link on the draft.
    Raises HTTPException with a reason the app translates."""
    draft = get_draft(db, draft_id)
    if draft is None or draft["status"] != "draft":
        raise HTTPException(status_code=409, detail="draft_not_open")
    row = (
        db.execute(
            text("""
                SELECT provider, network, external_id, name, secrets, status, is_demo
                FROM app.social_accounts WHERE id = :id
            """),
            {"id": account_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    provider = social_provider(row["provider"])
    publish = getattr(provider, "publish", None)
    if row["is_demo"] or publish is None:
        raise HTTPException(status_code=409, detail="publishing_not_supported")
    if row["status"] != "connected":
        raise HTTPException(status_code=409, detail="needs_reauth")
    info = AccountInfo(
        row["network"], row["external_id"], row["name"], secrets=decrypt(row["secrets"])
    )
    try:
        done = publish(info, draft["body"], draft["image_url"])
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except NeedsReauth as error:
        raise HTTPException(status_code=409, detail="needs_reauth") from error
    except NetworkError as error:
        raise HTTPException(status_code=502, detail="network_error") from error
    db.execute(
        text("""
            UPDATE app.social_drafts
            SET status = 'published', published_at = now(), external_id = :external_id,
                permalink = :permalink, network = :network
            WHERE id = :id
        """),
        {
            "id": draft_id,
            "external_id": done.external_id,
            "permalink": done.permalink,
            "network": row["network"],
        },
    )
    return {"draft_id": str(draft_id), "external_id": done.external_id, "permalink": done.permalink}
