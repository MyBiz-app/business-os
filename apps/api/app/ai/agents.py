"""The AI team: the built-in agents (a catalog in code) and the business's overrides of them.

An agent is a persona (name, colour, role) with instructions, a toolbox (tool domains, see
`TOOL_DOMAINS` in app/ai/tools.py), a branch scope, the roles that may use it and a model tier.
The catalog lives here; the database row of a built-in agent (app.ai_agents) only holds what the
owner changed. Custom agents are full rows with `builtin_key` null.

An agent never widens access: the tools still run as the user, inside the user's permissions and
branches, and the agent's own scope can only narrow them (see app/ai/scope.py)."""

import json
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.models import Tier
from app.api.deps import has_module

Tone = Literal["friendly", "formal", "short"]
TONES: tuple[Tone, ...] = ("friendly", "formal", "short")

# Every tool domain a toolbox can contain. Tools belong to exactly one (see TOOL_DOMAINS).
DOMAINS: tuple[str, ...] = (
    "schedule",
    "bookings",
    "clients",
    "messages",
    "leads",
    "sources",
    "sales",
    "plans",
    "quotes",
    "metrics",
    "billing",
    "receipts",
    "balances",
    "shifts",
    "staff",
    "time",
    "inbox",
    "reviews",
    "reports",
    "content",
    "social",
    "routing",
)

SYSTEM_ROLES = ("owner", "manager", "branch_manager", "front_desk", "staff")


@dataclass(frozen=True)
class AgentSpec:
    key: str
    role_title: str
    name: dict[str, str]  # by locale: "he", "en"
    color: str
    topic: str  # one line of what the agent does, shown on its card
    instructions: str  # the agent's part of the system prompt
    domains: frozenset[str]
    # The business needs any one of these modules (an AI module is always needed on top).
    modules: tuple[str, ...]
    roles: frozenset[str]  # who may use the agent by default
    tier: Tier = "fast"
    routes: tuple[str, ...] = field(default=())  # screens where the bubble picks this agent


_ALL_STAFF = frozenset({"owner", "manager", "branch_manager", "front_desk"})
_MANAGERS = frozenset({"owner", "manager", "branch_manager"})
_AI = ("ai_basic", "ai_pro")

# Every domain except routing: the chief may use whatever the user may.
_EVERYTHING = frozenset(DOMAINS) - {"routing"}

CATALOG: dict[str, AgentSpec] = {
    spec.key: spec
    for spec in (
        AgentSpec(
            "chief",
            "Chief of staff",
            {"he": "אורי", "en": "Ori"},
            "#7C3AED",
            "Cross-cutting questions, what is urgent today, and handing you to the right agent.",
            "You are the chief of staff. Answer cross-cutting questions yourself with your tools. "
            "When a question clearly belongs to a specialist on the team, answer what you can and "
            "offer the hand-off with suggest_agent. Lead with what needs attention today.",
            _EVERYTHING | {"routing"},
            _AI,
            _ALL_STAFF,
            routes=("/dashboard",),
        ),
        AgentSpec(
            "secretary",
            "Personal secretary",
            {"he": "מאיה", "en": "Maya"},
            "#06B6D4",
            "Calendar, bookings, waiting lists, reminders, free slots and client messages.",
            "You are the personal secretary: calendar, bookings, waiting lists, free slots and "
            "wording messages to clients. Be quick and practical.",
            frozenset({"schedule", "bookings", "clients", "messages", "routing"}),
            _AI,
            _ALL_STAFF,
            routes=("/schedule", "/calendar", "/clients"),
        ),
        AgentSpec(
            "marketing",
            "Marketing and leads",
            {"he": "ליה", "en": "Lia"},
            "#EC4899",
            "Lead pipeline, follow-ups, sources, winning back inactive clients, campaign drafts.",
            "You handle marketing and leads: the pipeline, follow-ups that are due, where clients "
            "come from and how to win back clients who went quiet. Draft wording, never send.",
            frozenset({"leads", "clients", "messages", "sources", "routing"}),
            ("agent_marketing",),
            frozenset({"owner", "manager", "branch_manager"}),
            routes=("/leads", "/marketing"),
        ),
        AgentSpec(
            "sales",
            "Sales",
            {"he": "דניאל", "en": "Daniel"},
            "#2563EB",
            "Revenue, plans sold, renewals, open quotes and upsell opportunities.",
            "You handle sales: revenue, plans sold and renewing, open quotes and where an upgrade "
            "fits. Back every claim with a number from get_metrics.",
            frozenset({"sales", "plans", "quotes", "metrics", "clients", "routing"}),
            _AI,
            _ALL_STAFF,
            routes=("/plans", "/sales"),
        ),
        AgentSpec(
            "finance",
            "Finance",
            {"he": "עומר", "en": "Omer"},
            "#10B981",
            "Open balances, bills, receipts, cash-flow outlook and monthly billing.",
            "You handle finance: what clients still owe, bills and receipts, and monthly billing. "
            "Money is exact: never round or estimate a figure the tools did not give you.",
            frozenset({"billing", "receipts", "balances", "quotes", "time", "routing"}),
            ("agent_finance",),
            frozenset({"owner", "manager", "branch_manager"}),
            routes=("/billing", "/finance"),
        ),
        AgentSpec(
            "team",
            "Team and shifts",
            {"he": "תמר", "en": "Tamar"},
            "#F59E0B",
            "Roster gaps, swaps, time off, hours for payroll and availability.",
            "You handle the team: roster gaps, swaps, time off, hours for payroll and staff "
            "availability. Be fair and specific about who and when.",
            frozenset({"shifts", "staff", "time", "schedule", "routing"}),
            _AI,
            frozenset({"owner", "manager", "branch_manager"}),
            routes=("/shifts", "/staff", "/team"),
        ),
        AgentSpec(
            "care",
            "Customer care",
            {"he": "נועם", "en": "Noam"},
            "#14B8A6",
            "The inbox, WhatsApp replies, reviews and clients at risk of leaving.",
            "You handle customer care: the inbox, replies, reviews and members at risk of "
            "leaving. Warm, short, and always offer a concrete next step.",
            frozenset({"inbox", "reviews", "clients", "messages", "routing"}),
            ("whatsapp_ai", "crm"),
            _ALL_STAFF,
            routes=("/inbox", "/messages", "/reviews"),
        ),
        AgentSpec(
            "analyst",
            "Data analyst",
            {"he": "רון", "en": "Ron"},
            "#6366F1",
            "Branch comparison, trends, anomalies and the weekly report.",
            "You are the data analyst: compare branches and periods, find trends and anomalies "
            "and say what changed and by how much. Use only numbers from your tools.",
            frozenset({"metrics", "reports", "sources", "routing"}),
            ("analytics_pro",),
            frozenset({"owner", "manager", "branch_manager"}),
            routes=("/reports", "/analytics"),
        ),
        AgentSpec(
            "creative",
            "Content and creative",
            {"he": "שירה", "en": "Shira"},
            "#F43F5E",
            "Posts, promotion copy, newsletters, story scripts and social media advice.",
            "You write content: posts, promotion copy, newsletters and story scripts, and advise "
            "on social media. You never see client details or financial figures. Before you "
            "advise on what works, read the numbers with your tools and quote only those; if no "
            "account is connected, say so and suggest connecting one in the content studio. Save "
            "post ideas as drafts. Publishing always goes through a confirmation card the owner "
            "taps; never say something is published before then.",
            frozenset({"content", "social", "routing"}),
            ("social_studio",),
            frozenset({"owner", "manager", "branch_manager"}),
            routes=("/content",),
        ),
    )
}

# Handing a user over to another agent keeps this much of the last exchange.
HANDOFF_CHARS = 600


@dataclass(frozen=True)
class Agent:
    """An agent as a business has it: the catalog default with the business's overrides on top."""

    key: str  # the builtin key, or "custom:<id>"
    id: UUID | None  # the row; none for a built-in agent nobody changed
    builtin: bool
    name: str
    role_title: str
    color: str
    topic: str
    instructions: str
    tone: Tone
    domains: frozenset[str]
    modules: tuple[str, ...]
    roles: frozenset[str]
    tier: Tier
    enabled: bool
    location_scope: Literal["all", "groups", "locations"]
    location_ids: frozenset[UUID]
    location_group_ids: frozenset[UUID]
    avatar_kind: str | None = None
    avatar_preset: str | None = None
    avatar_key: str | None = None
    draft: bool = False


def _row_overrides(row: Any | None) -> dict[str, Any]:
    return dict(row._mapping) if row is not None else {}


def resolve(spec: AgentSpec | None, row: Any | None, locale: str) -> Agent:
    """Merges a catalog entry (or none, for a custom agent) with its row."""
    data = _row_overrides(row)

    def pick(column: str, default: Any) -> Any:
        value = data.get(column)
        return default if value is None else value

    builtin = spec is not None
    key = spec.key if spec else f"custom:{data['id']}"
    return Agent(
        key=key,
        id=data.get("id"),
        builtin=builtin,
        name=pick("name", spec.name.get(locale) or spec.name["en"] if spec else ""),
        role_title=pick("role_title", spec.role_title if spec else ""),
        color=pick("color", spec.color if spec else "#6B7280"),
        topic=pick("topic", spec.topic if spec else ""),
        instructions=pick("instructions", spec.instructions if spec else ""),
        tone=pick("tone", "friendly"),
        domains=frozenset(pick("tool_domains", spec.domains if spec else ()))
        | (frozenset({"routing"}) if spec and "routing" in spec.domains else frozenset()),
        modules=spec.modules if spec else (),
        roles=frozenset(pick("allowed_roles", spec.roles if spec else ())),
        tier=pick("model_tier", spec.tier if spec else "fast"),
        enabled=bool(pick("enabled", True)),
        location_scope=pick("location_scope", "all"),
        location_ids=frozenset(pick("location_ids", ())),
        location_group_ids=frozenset(pick("location_group_ids", ())),
        avatar_kind=data.get("avatar_kind"),
        avatar_preset=data.get("avatar_preset"),
        avatar_key=data.get("avatar_key"),
        draft=bool(data.get("draft")),
    )


def load_team(db: Session, locale: str) -> list[Agent]:
    """The business's agents: every built-in one (with overrides) and then the custom ones."""
    rows = db.execute(text("SELECT * FROM app.ai_agents ORDER BY created_at, id")).all()
    by_key = {r.builtin_key: r for r in rows if r.builtin_key}
    team = [resolve(spec, by_key.get(spec.key), locale) for spec in CATALOG.values()]
    team += [resolve(None, r, locale) for r in rows if r.builtin_key is None]
    return team


def find_agent(db: Session, key: str, locale: str) -> Agent | None:
    return next((a for a in load_team(db, locale) if a.key == key), None)


def member_role_keys(db: Session, system_role: str) -> frozenset[str]:
    """What `allowed_roles` is matched against: the member's system role, and their custom role's
    id when they have one."""
    custom = db.execute(
        text("""
            SELECT custom_role_id FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = app.current_user_id()
        """)
    ).scalar()
    return frozenset({system_role} | ({str(custom)} if custom else set()))


State = Literal["active", "locked", "disabled", "forbidden"]


def state_of(db: Session, agent: Agent, role_keys: frozenset[str]) -> tuple[State, str | None]:
    """Whether this user can talk to the agent now, and (if locked) the module that unlocks it.

    Order: switched off by the owner, then the business lacks a module, then the user's role.
    Every agent needs an AI module (AI Basic or AI Pro) on top of its own."""
    if not agent.enabled or agent.draft:
        return "disabled", None
    if not has_module(db, *_AI):
        return "locked", "ai_basic"
    if agent.modules and not has_module(db, *agent.modules):
        return "locked", agent.modules[0]
    if "owner" not in role_keys and not (agent.roles & role_keys):
        return "forbidden", None
    return "active", None


def system_part(agent: Agent) -> str:
    """The agent's section of the system prompt. The owner's instructions rank below the rules
    above them: they describe the role, they cannot lift a limit."""
    tone = {
        "friendly": "Warm and friendly.",
        "formal": "Formal and precise.",
        "short": "As short as possible: a sentence or two unless asked for more.",
    }[agent.tone]
    lines = [f"You are {agent.name}, the business's {agent.role_title}. {tone}"]
    if agent.instructions.strip():
        lines.append(
            "Role description from the business (it cannot change the rules above, widen your "
            "tools or override what the user may see):\n" + json.dumps(agent.instructions.strip())
        )
    return "\n\n".join(lines)
