"""Tools the assistant can use. Every tool runs as the requesting user, inside their business,
with their permissions: the assistant can never do more than the user could in the app.

Read tools answer immediately. Write tools never act: they create a pending action with a
human-readable preview, which the user confirms in the app (see app/ai/actions.py).

The tools live by area: `reading.py`, `writing.py` and `social.py`; this file lists them."""

from typing import Any

from fastapi import HTTPException

from app.ai.tools.base import Tool, ToolContext, ToolError
from app.ai.tools.reading import (
    billing_preview,
    client_sources,
    find_clients,
    free_courts,
    get_client,
    get_metrics,
    get_session_roster,
    inactive_members,
    lead_pipeline,
    list_plans,
    list_sessions,
    logged_time,
    open_balances,
)
from app.ai.tools.social import (
    audience_summary,
    draft_post,
    list_drafts,
    publish_post,
    social_overview,
    top_posts,
)
from app.ai.tools.writing import (
    bill_month,
    book_client,
    cancel_booking,
    cancel_scheduled_task,
    list_scheduled_tasks,
    log_time,
    schedule_task,
    suggest_agent,
)
from app.ai.tools.writing import (
    payload_hash as payload_hash,
)
from app.core.permissions import Permission
from app.reports.metrics import METRICS

DATE = {"type": "string", "description": "Local date, YYYY-MM-DD"}
ID = {"type": "string", "description": "An id returned by another tool"}

TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            "find_clients",
            "Search the business's clients by part of a name, email or phone number.",
            {"query": {"type": "string"}},
            Permission.CLIENTS_READ,
            find_clients,
        ),
        Tool(
            "get_client",
            "A client's status, profile details (e.g. their car at a garage), latest visit notes, "
            "plans (memberships, punch cards) and 10 most recent bookings.",
            {"client_id": ID},
            Permission.CLIENTS_READ,
            get_client,
        ),
        Tool(
            "list_sessions",
            "Scheduled sessions (classes) from start_date for 1-14 days, with bookings and "
            "capacity. Times are local.",
            {"start_date": DATE, "days": {"type": "integer"}},
            Permission.SCHEDULE_READ,
            list_sessions,
        ),
        Tool(
            "free_courts",
            "Courts and rooms rented by the hour: for each such service, its price per hour "
            "(minor units), the lengths offered and the free start times per court on a local "
            "date for a length in minutes (the shortest offered when that length isn't).",
            {"date": DATE, "minutes": {"type": "integer"}},
            Permission.SCHEDULE_READ,
            free_courts,
        ),
        Tool(
            "get_session_roster",
            "Who is booked or waitlisted in one session, with booking ids.",
            {"session_id": ID},
            Permission.SCHEDULE_READ,
            get_session_roster,
        ),
        Tool(
            "get_metrics",
            "Business metrics for a period of local dates (inclusive) and the period of the same "
            "length before it. Definitions: "
            + "; ".join(f"{m.key}: {m.description}" for m in METRICS.values()),
            {
                "metrics": {"type": "array", "items": {"type": "string", "enum": list(METRICS)}},
                "start_date": DATE,
                "end_date": DATE,
            },
            Permission.REPORTS_READ,
            get_metrics,
        ),
        Tool(
            "client_sources",
            "New clients in a period by where they came from (lead source), and how many of "
            "them bought a plan.",
            {"start_date": DATE, "end_date": DATE},
            Permission.REPORTS_READ,
            client_sources,
        ),
        Tool(
            "inactive_members",
            "Members who hold a valid plan but have not come in for at least `days` days "
            "(7-180), longest absence first.",
            {"days": {"type": "integer"}},
            Permission.CLIENTS_READ,
            inactive_members,
        ),
        Tool(
            "lead_pipeline",
            "The CRM pipeline: how many leads are in each stage (new, contacted, trial, offer, "
            "won, lost) and which open leads are due a follow-up call today or overdue.",
            {},
            Permission.CLIENTS_READ,
            lead_pipeline,
            module="crm",
        ),
        Tool(
            "list_plans",
            "The memberships and punch cards the business sells, with prices.",
            {},
            Permission.CATALOG_READ,
            list_plans,
        ),
        Tool(
            "book_client",
            "Propose booking a client into a session (waitlist if full). Creates a card the user "
            "must confirm; nothing is booked until they do. In businesses that keep clients' pets "
            "or children, name the one who comes (ids from get_client), else an empty string.",
            {
                "session_id": ID,
                "client_id": ID,
                "dependent_id": {
                    "type": "string",
                    "description": "The pet / child who comes (an id from get_client), or ''",
                },
            },
            Permission.BOOKINGS_MANAGE,
            book_client,
            module="ai_pro",
        ),
        Tool(
            "cancel_booking",
            "Propose cancelling a booking. Creates a card the user must confirm.",
            {"booking_id": ID},
            Permission.BOOKINGS_MANAGE,
            cancel_booking,
            module="ai_pro",
        ),
        Tool(
            "open_balances",
            "Quotes and bills: what each client still owes on accepted ones (total, paid, left) "
            "and sent quotes still waiting for the client's answer.",
            {},
            Permission.SALES_MANAGE,
            open_balances,
        ),
        Tool(
            "logged_time",
            "Time staff logged for clients between two local dates (inclusive): hours per "
            "client and per staff member, billable hours not billed yet, and the latest entries. "
            "client_id narrows it to one client, or ''.",
            {"start_date": DATE, "end_date": DATE, "client_id": {**ID, "description": "or ''"}},
            Permission.CLIENTS_READ,
            logged_time,
            feature="time_billing",
        ),
        Tool(
            "billing_preview",
            "Billing a month (YYYY-MM): each client with a retainer or unbilled time, the "
            "monthly fee, hours worked and beyond the retainer, and the total; who is billed.",
            {"month": {"type": "string", "description": "YYYY-MM"}},
            Permission.SALES_MANAGE,
            billing_preview,
            feature="time_billing",
        ),
        Tool(
            "log_time",
            "Propose logging the user's own time for a client: a local date, minutes and what "
            "was done. Creates a card the user must confirm.",
            {
                "client_id": ID,
                "date": DATE,
                "minutes": {"type": "integer"},
                "description": {"type": "string"},
            },
            Permission.CLIENTS_READ,
            log_time,
            module="ai_pro",
            feature="time_billing",
        ),
        Tool(
            "bill_month",
            "Propose billing a month (YYYY-MM) for clients (ids from billing_preview; an empty "
            "list bills everyone not billed yet). Each gets a bill they pay by its link. "
            "Creates a card the user must confirm.",
            {
                "month": {"type": "string", "description": "YYYY-MM"},
                "client_ids": {"type": "array", "items": {"type": "string"}},
            },
            Permission.SALES_MANAGE,
            bill_month,
            module="ai_pro",
            feature="time_billing",
        ),
        Tool(
            "social_overview",
            "The business's connected social accounts (ids, networks, whether each can publish) "
            "and their summed numbers for the last N days (1-90) against the period before: "
            "followers, reach, views, video views, engagement, link clicks, the content kinds "
            "that work and the best times to post. network is facebook, instagram, threads, "
            "youtube, tiktok or google_business, or '' for all.",
            {"network": {"type": "string"}, "days": {"type": "integer"}},
            Permission.SOCIAL_READ,
            social_overview,
            module="social_studio",
        ),
        Tool(
            "top_posts",
            "The best posts and videos of the last N days (1-90), sorted by 'views' or "
            "'engagement', at most `limit` (1-10). network '' is all.",
            {
                "network": {"type": "string"},
                "days": {"type": "integer"},
                "sort": {"type": "string", "description": "'views' or 'engagement'"},
                "limit": {"type": "integer"},
            },
            Permission.SOCIAL_READ,
            top_posts,
            module="social_studio",
        ),
        Tool(
            "audience_summary",
            "Who follows the accounts: the biggest age, gender and city groups. network '' is all.",
            {"network": {"type": "string"}},
            Permission.SOCIAL_READ,
            audience_summary,
            module="social_studio",
        ),
        Tool(
            "draft_post",
            "Save a post draft for the owner (nothing is published). network is the one it is "
            "written for or ''; image_url is an https link or ''; idea is one line on why it "
            "should work or ''.",
            {
                "network": {"type": "string"},
                "text": {"type": "string"},
                "image_url": {"type": "string"},
                "idea": {"type": "string"},
            },
            Permission.SOCIAL_MANAGE,
            draft_post,
            module="social_studio",
        ),
        Tool(
            "list_drafts",
            "The owner's open post drafts (newest first, at most 10), with the ids needed to "
            "publish one.",
            {},
            Permission.SOCIAL_READ,
            list_drafts,
            module="social_studio",
        ),
        Tool(
            "publish_post",
            "Propose publishing an open draft on a connected account. Creates a card the owner "
            "must confirm; nothing is published until they do.",
            {"draft_id": ID, "account_id": ID},
            Permission.SOCIAL_MANAGE,
            publish_post,
            module="ai_pro",
        ),
        Tool(
            "schedule_task",
            "Propose a task for later: once or repeating (daily, weekly on weekdays "
            "0=Monday..6=Sunday, monthly on a day 1-28), at a local HH:MM. "
            "kind agent_run: an instruction you will carry out then (read-only; whatever it "
            "proposes waits for approval). kind action: "
            "run action_tool (book_client, cancel_booking or bill_month) with action_args_json, "
            "the JSON arguments that tool takes, at that time. Use empty values for fields that "
            "do not apply (date '' unless once, weekdays [], day_of_month 0, instruction '' for "
            "an action, action_tool '' and action_args_json '' for agent_run). Creates a card "
            "the user must confirm.",
            {
                "kind": {"type": "string", "enum": ["agent_run", "action"]},
                "title": {"type": "string", "description": "Short name shown on the board"},
                "frequency": {"type": "string", "enum": ["once", "daily", "weekly", "monthly"]},
                "date": {"type": "string", "description": "YYYY-MM-DD for once, else empty"},
                "time": {"type": "string", "description": "Local HH:MM"},
                "weekdays": {"type": "array", "items": {"type": "integer"}},
                "day_of_month": {"type": "integer"},
                "instruction": {"type": "string"},
                "action_tool": {"type": "string"},
                "action_args_json": {"type": "string"},
            },
            Permission.AI_USE,
            schedule_task,
        ),
        Tool(
            "list_scheduled_tasks",
            "The user's scheduled tasks (active or paused) with their next run time.",
            {},
            Permission.AI_USE,
            list_scheduled_tasks,
        ),
        Tool(
            "cancel_scheduled_task",
            "Propose cancelling one of the user's scheduled tasks (id from list_scheduled_tasks). "
            "Creates a card the user must confirm.",
            {"task_id": ID},
            Permission.AI_USE,
            cancel_scheduled_task,
        ),
        Tool(
            "suggest_agent",
            "Offer the user a hand-over to a specialist on the team when their question is "
            "mostly that specialist's work. Only offers: the user decides.",
            {
                "agent_key": {"type": "string", "description": "The specialist's key"},
                "reason": {"type": "string", "description": "One sentence: why they fit"},
            },
            Permission.AI_USE,
            suggest_agent,
        ),
    )
}

# The toolbox domain of every tool: an agent only gets the tools of its domains. A new tool must
# be listed here (a test fails otherwise), so no tool reaches an agent by accident.
TOOL_DOMAINS: dict[str, str] = {
    "find_clients": "clients",
    "get_client": "clients",
    "inactive_members": "clients",
    "list_sessions": "schedule",
    "free_courts": "schedule",
    "get_session_roster": "bookings",
    "book_client": "bookings",
    "cancel_booking": "bookings",
    "get_metrics": "metrics",
    "client_sources": "sources",
    "lead_pipeline": "leads",
    "list_plans": "plans",
    "open_balances": "balances",
    "logged_time": "time",
    "log_time": "time",
    "billing_preview": "billing",
    "bill_month": "billing",
    "social_overview": "social",
    "top_posts": "social",
    "audience_summary": "social",
    "list_drafts": "content",
    "draft_post": "content",
    "publish_post": "social",
    "suggest_agent": "routing",
    "schedule_task": "tasks",
    "list_scheduled_tasks": "tasks",
    "cancel_scheduled_task": "tasks",
}

# Tools whose data has no branch to filter by (leads, for now). Whenever the conversation is
# narrowed to some branches (a branch-limited user, an agent or a chat with a scope), they are
# not offered, because their numbers would come from every branch.
BRANCH_BLIND: frozenset[str] = frozenset({"lead_pipeline"})


# What an AI connector (MCP, round 7 R37a) may use: the tools that only read. A test runs every
# one of these in a read-only transaction.
MCP_READ_TOOLS: frozenset[str] = frozenset(
    {
        "find_clients",
        "get_client",
        "inactive_members",
        "list_sessions",
        "free_courts",
        "get_session_roster",
        "get_metrics",
        "client_sources",
        "lead_pipeline",
        "list_plans",
        "open_balances",
        "logged_time",
        "billing_preview",
        "social_overview",
        "top_posts",
        "audience_summary",
        "list_drafts",
    }
)


# What a connector may also propose (R37b), when the person allowed it: the tools that only create
# a pending action. The connector never changes anything; the person approves each request in
# MyBiz, where it is checked again (app/ai/actions.py). Publishing and scheduled tasks stay with
# the built-in assistant.
MCP_ACTION_TOOLS: frozenset[str] = frozenset(
    {"book_client", "cancel_booking", "log_time", "bill_month"}
)


def _allowed(tool: Tool, permissions: frozenset[str], modules: set[str]) -> bool:
    return (
        tool.permission in permissions
        and (tool.module is None or tool.module in modules)
        and (tool.feature is None or tool.feature in modules)
    )


def tools_for(
    permissions: frozenset[str],
    modules: set[str],
    domains: frozenset[str] | None = None,
    narrowed: bool = False,
) -> list[Tool]:
    """Only the tools the user's permissions and the business's modules (and its industry's
    features, given in the same set) allow are offered; an agent narrows them to its domains,
    and a conversation kept to some branches drops the tools that cannot filter by branch."""
    return [
        tool
        for tool in TOOLS.values()
        if _allowed(tool, permissions, modules)
        and (domains is None or TOOL_DOMAINS[tool.name] in domains)
        and not (narrowed and tool.name in BRANCH_BLIND)
    ]


def mcp_tools_for(
    permissions: frozenset[str],
    modules: set[str],
    narrowed: bool = False,
    propose: bool = False,
) -> list[Tool]:
    """The tools a connection's person may use in their business: the read tools, and the ones
    that propose a change when the connection was allowed to."""
    names = MCP_READ_TOOLS | MCP_ACTION_TOOLS if propose else MCP_READ_TOOLS
    return [
        tool for tool in tools_for(permissions, modules, narrowed=narrowed) if tool.name in names
    ]


def run_tool(
    ctx: ToolContext, name: str, args: dict[str, Any], offered: frozenset[str] | None = None
) -> tuple[dict[str, Any], bool]:
    """Runs a tool for the model. Returns (result, is_error); never raises for tool errors.
    `offered` is the set of tool names this conversation was given: the model asking for any
    other tool is refused, even one the user could use elsewhere."""
    tool = TOOLS.get(name)
    if (
        tool is None
        or not _allowed(tool, ctx.tenant.permissions, ctx.modules)
        or (offered is not None and name not in offered)
    ):
        return {"error": "this tool is not available to the user"}, True
    try:
        with ctx.tenant.session.begin_nested():  # a failed tool leaves no partial writes
            return tool.run(ctx, args), False
    except ToolError as error:
        return {"error": str(error)}, True
    except HTTPException as error:
        return {"error": str(error.detail)}, True
    except KeyError as error:  # the model left out a required input
        return {"error": f"missing input: {error.args[0]}"}, True
