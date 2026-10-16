"""The AI team's structure: who reports to whom and which team an agent belongs to.

The chief is always at the top. An agent without an explicit `reports_to_key` reports to the chief,
so a business that never edits the structure behaves as before. The structure is not decoration:
the chief hands a question to a team's lead before the other members (see `handoff_target`), and
the system prompt tells each agent who it leads and who it answers to."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.agents import Agent

CHIEF = "chief"


@dataclass(frozen=True)
class AgentTeam:
    id: UUID
    name: str
    color: str
    lead_key: str | None


class StructureError(ValueError):
    """The submitted structure breaks a rule; the message is a stable code."""


def load_teams(db: Session) -> list[AgentTeam]:
    rows = db.execute(
        text("SELECT id, name, color, lead_key FROM app.ai_agent_teams ORDER BY created_at, id")
    )
    return [AgentTeam(r.id, r.name, r.color, r.lead_key) for r in rows]


def effective_parent(agent: Agent) -> str | None:
    """The agent an agent reports to: its choice, else the chief; none for the chief itself."""
    if agent.key == CHIEF:
        return None
    return agent.reports_to_key or CHIEF


def check_structure(
    keys: set[str],
    parents: dict[str, str | None],
    team_ids: set[UUID],
    member_teams: dict[str, UUID | None],
    leads: dict[UUID, str | None],
) -> None:
    """Raises StructureError for an unknown agent or team, a chief that reports to someone, an
    agent that reports to itself, a cycle or a team lead outside its own team."""
    if CHIEF not in keys:
        raise StructureError("chief_missing")
    for key, parent in parents.items():
        if key not in keys:
            raise StructureError("unknown_agent")
        if parent is None:
            continue
        if key == CHIEF:
            raise StructureError("chief_on_top")
        if parent not in keys or parent == key:
            raise StructureError("unknown_parent")
    for key in keys - {CHIEF}:
        seen = {key}
        at = parents.get(key) or CHIEF
        while at != CHIEF:
            if at in seen:
                raise StructureError("cycle")
            seen.add(at)
            at = parents.get(at) or CHIEF
    for team in member_teams.values():
        if team is not None and team not in team_ids:
            raise StructureError("unknown_team")
    for team, lead in leads.items():
        if lead is not None and member_teams.get(lead) != team:
            raise StructureError("lead_not_in_team")


def handoff_target(
    team: list[Agent], teams: list[AgentTeam], wanted: str, allowed: frozenset[str]
) -> str:
    """The agent a hand-over should go to: the lead of the wanted agent's team when that lead can
    be handed to, else the wanted agent."""
    by_key = {a.key: a for a in team}
    agent = by_key.get(wanted)
    if agent is None or agent.team_id is None:
        return wanted
    lead = next((t.lead_key for t in teams if t.id == agent.team_id), None)
    return lead if lead and lead != wanted and lead in allowed else wanted


def prompt_part(agent: Agent, team: list[Agent], teams: list[AgentTeam]) -> str:
    """What the agent knows about the structure, as a block for its system prompt (empty when the
    business never shaped it)."""
    by_key = {a.key: a for a in team}
    lines: list[str] = []
    parent = effective_parent(agent)
    if parent and parent in by_key and any(a.reports_to_key for a in team):
        lines.append(f"You report to {by_key[parent].name}.")
    reports = [a.name for a in team if effective_parent(a) == agent.key and a.key != agent.key]
    if reports and any(a.reports_to_key for a in team):
        lines.append("Your direct reports: " + ", ".join(reports) + ".")
    for t in teams:
        members = [a for a in team if a.team_id == t.id]
        if agent.team_id == t.id or agent.key == t.lead_key or agent.key == CHIEF:
            lead = by_key.get(t.lead_key or "")
            lines.append(
                f'Team "{t.name}": '
                + ", ".join(a.name for a in members)
                + (f". Lead: {lead.name}" if lead else "")
                + "."
            )
    if agent.key == CHIEF and teams:
        lines.append(
            "When a question belongs to a team, hand it to that team's lead first; the lead "
            "involves the others."
        )
    return "\n".join(lines)
