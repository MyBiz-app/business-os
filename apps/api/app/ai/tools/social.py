"""Social studio tools (read and propose)."""

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.tools.base import (
    ToolContext,
    ToolError,
    _uuid,
)
from app.ai.tools.writing import _propose
from app.social import studio
from app.social.providers import NETWORK_KEYS


def _network(args: dict[str, Any]) -> str:
    value = str(args["network"]).strip()
    if value and value not in NETWORK_KEYS:
        raise ToolError(f"unknown network; use one of: {', '.join(NETWORK_KEYS)} or '' for all")
    return value


def _studio_accounts(ctx: ToolContext, args: dict[str, Any]) -> list[dict[str, Any]]:
    return studio.visible_accounts(ctx.tenant.session, ctx.tenant.branches, _network(args))


def _today(ctx: ToolContext) -> dt.date:
    return dt.datetime.now(ZoneInfo(ctx.time_zone)).date()


def social_overview(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return studio.overview(
        ctx.tenant.session,
        _studio_accounts(ctx, args),
        int(args["days"]),
        _today(ctx),
        ctx.time_zone,
    )


def top_posts(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sort = str(args["sort"])
    if sort not in ("views", "engagement"):
        raise ToolError("sort must be 'views' or 'engagement'")
    posts = studio.best_posts(
        ctx.tenant.session,
        _studio_accounts(ctx, args),
        int(args["days"]),
        _today(ctx),
        sort,
        int(args["limit"]),
    )
    return {"posts": posts}


def audience_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "audience": studio.audience_summary(ctx.tenant.session, _studio_accounts(ctx, args)),
        "note": "percent of the audience; only where the network shares it",
    }


def draft_post(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    body = str(args["text"]).strip()
    if not 1 <= len(body) <= 2200:
        raise ToolError("the post text must be 1 to 2200 characters")
    image_url = str(args["image_url"]).strip()
    if image_url and not image_url.startswith("https://"):
        raise ToolError("image_url must be an https link, or ''")
    idea = str(args["idea"]).strip()[:300]
    draft_id = studio.save_draft(
        ctx.tenant.session,
        ctx.user_id,
        ctx.agent_key,
        _network(args) or None,
        body,
        image_url or None,
        idea or None,
    )
    return {
        "draft_id": str(draft_id),
        "saved": True,
        "instruction": "The draft is saved, not published. Tell the owner it waits in their "
        "content drafts and offer to publish it (that needs their confirmation).",
    }


def list_drafts(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    return {
        "drafts": [
            {
                "draft_id": str(d["id"]),
                "network": d["network"],
                "text": d["body"][:500],
                "has_image": bool(d["image_url"]),
                "idea": d["idea"],
            }
            for d in studio.open_drafts(ctx.tenant.session)
        ]
    }


def publish_post(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    draft_id, account_id = (
        _uuid(args["draft_id"], "draft_id"),
        _uuid(args["account_id"], "account_id"),
    )
    draft = studio.get_draft(ctx.tenant.session, draft_id)
    if draft is None or draft["status"] != "draft":
        raise ToolError("that draft is not open (not found, published or discarded)")
    account = next(
        (
            a
            for a in studio.visible_accounts(ctx.tenant.session, ctx.tenant.branches)
            if a["id"] == account_id
        ),
        None,
    )
    if account is None:
        raise ToolError("no such connected account (ids come from social_overview)")
    if draft["network"] and draft["network"] != account["network"]:
        raise ToolError("the draft was written for another network")
    if not studio.can_publish(account):
        raise ToolError("this account cannot publish: demo data, not reconnected, or no support")
    preview = {
        "kind": "publish_post",
        "network": account["network"],
        "account": account["name"],
        "text": draft["body"][:300],
        "image_url": draft["image_url"],
    }
    payload = {"draft_id": str(draft_id), "account_id": str(account_id)}
    return _propose(ctx, "publish_post", payload, preview)
