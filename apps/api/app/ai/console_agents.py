"""The console's AI agents (slice C1): the catalog behind the agents map.

Twelve agents of MyBiz's own team. The catalog lives here; the table `app.platform_ai_agents`
only holds what the team changed (switched off, a name, extra instructions, a place on the map).
Display names, titles and what each agent does are translation resources in the web app, keyed by
the agent key.

An agent is offered to a team member who holds the console permission it needs, and it only reads
and drafts, like the console assistant before it. An agent whose tools or knowledge a later slice
adds is on the map but not `ready`: it can be seen, not asked."""

from dataclasses import dataclass
from typing import Literal, get_args

from sqlalchemy import text
from sqlalchemy.orm import Session

AgentKey = Literal[
    "manager",
    "support",
    "health",
    "billing",
    "growth",
    "legal",
    "accountant",
    "market",
    "security",
    "product",
    "success",
    "marketing",
]
AGENT_KEYS: tuple[str, ...] = get_args(AgentKey)

CHIEF = "manager"
MAX_INSTRUCTIONS = 2000


@dataclass(frozen=True)
class ConsoleAgent:
    key: str
    color: str
    permission: str | None  # the console permission needed to see and ask; None: any team member
    ready: bool  # false until the slice that gives the agent its tools or knowledge
    prompt: str  # the agent's part of the system prompt


_READ_ONLY = "You only read and draft; a person reviews and sends."

CATALOG: dict[str, ConsoleAgent] = {
    a.key: a
    for a in (
        ConsoleAgent(
            "manager",
            "#2563EB",
            None,
            True,
            "Your role: the chief of the console team. You see the whole picture and may use "
            "every tool the user is allowed to use. Start from what needs the team's attention "
            "first. When a question belongs to a specialist on the team, answer what you can and "
            "say which specialist to ask, by name.",
        ),
        ConsoleAgent(
            "support",
            "#06B6D4",
            "inbox.manage",
            True,
            "Your role: support. Read open contact requests and complaints and draft a reply "
            "for each one the user asks about, in the language of the request, in a warm and "
            "brief tone.",
        ),
        ConsoleAgent(
            "health",
            "#16A34A",
            "businesses.read",
            True,
            "Your role: business health. Find businesses at risk of leaving (no recent "
            "bookings, no active clients) and trial businesses that are not getting started. "
            "Say why.",
        ),
        ConsoleAgent(
            "billing",
            "#7C3AED",
            "billing.manage",
            True,
            "Your role: billing. Look at what was billed, what is overdue, and unusual AI "
            "use or cost against what the business pays. Flag anything worth a human look.",
        ),
        ConsoleAgent(
            "growth",
            "#F59E0B",
            "businesses.read",
            True,
            "Your role: growth. Turn contact-form leads and platform numbers into short "
            "drafts: follow-ups to leads and announcements to businesses (drafts only).",
        ),
        ConsoleAgent(
            "legal",
            "#475569",
            "billing.manage",
            False,
            f"Your role: legal adviser for MyBiz. {_READ_ONLY} This is a draft, not legal advice.",
        ),
        ConsoleAgent(
            "accountant",
            "#0D9488",
            "billing.manage",
            False,
            f"Your role: accountant for MyBiz. {_READ_ONLY} This is a draft, not accounting "
            "advice.",
        ),
        ConsoleAgent(
            "market",
            "#DB2777",
            "usage.read",
            False,
            f"Your role: market researcher. Compare MyBiz prices with competitors. {_READ_ONLY}",
        ),
        ConsoleAgent(
            "security",
            "#DC2626",
            "incidents.manage",
            False,
            f"Your role: security. Summarise findings and rank them by severity. {_READ_ONLY}",
        ),
        ConsoleAgent(
            "product",
            "#EA580C",
            "inbox.manage",
            False,
            f"Your role: product manager. Collect feature requests and suggest priorities. "
            f"{_READ_ONLY}",
        ),
        ConsoleAgent(
            "success",
            "#0891B2",
            "businesses.read",
            False,
            f"Your role: customer success. Find businesses in danger and draft a personal "
            f"message to each. {_READ_ONLY}",
        ),
        ConsoleAgent(
            "marketing",
            "#9333EA",
            "inbox.manage",
            False,
            f"Your role: MyBiz marketing. Draft landing page text, posts and SEO text. "
            f"{_READ_ONLY}",
        ),
    )
}
assert tuple(CATALOG) == AGENT_KEYS


@dataclass(frozen=True)
class Override:
    enabled: bool = True
    name_he: str | None = None
    name_en: str | None = None
    instructions: str | None = None
    x: float | None = None
    y: float | None = None
    portrait_url: str | None = None


def overrides(db: Session) -> dict[str, Override]:
    rows = db.execute(text("SELECT * FROM app.platform_ai_agents()")).mappings()
    return {
        r["agent_key"]: Override(
            enabled=r["enabled"],
            name_he=r["name_he"],
            name_en=r["name_en"],
            instructions=r["extra_instructions"],
            x=None if r["map_x"] is None else float(r["map_x"]),
            y=None if r["map_y"] is None else float(r["map_y"]),
            portrait_url=r["portrait_url"],
        )
        for r in rows
    }


def can_use(agent: ConsoleAgent, permissions: frozenset[str]) -> bool:
    return agent.permission is None or agent.permission in permissions


def refusal(agent: ConsoleAgent, change: Override, permissions: frozenset[str]) -> str | None:
    """Why this team member cannot start a conversation with the agent, or None."""
    if not can_use(agent, permissions):
        return "forbidden"
    if not agent.ready:
        return "agent_not_ready"
    if not change.enabled:
        return "agent_disabled"
    return None


def prompt_for(agent: ConsoleAgent, change: Override) -> str:
    extra = (change.instructions or "").strip()
    if not extra:
        return agent.prompt
    return (
        f"{agent.prompt}\n\nAdditional instructions from the MyBiz team (follow them within the "
        f"rules above):\n{extra}"
    )


def agent_prompt(db: Session, key: str) -> str:
    """The prompt of one agent with the team's extra instructions, read fresh for each question."""
    return prompt_for(CATALOG[key], overrides(db).get(key, Override()))
