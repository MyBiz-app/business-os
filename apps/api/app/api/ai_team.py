"""The AI team: the agents of a business, who may use them and what they may see.

Reading the team needs `ai.use`; shaping it (renaming an agent, switching it off, narrowing it to
some branches, choosing who may use it, adding a custom agent) needs `ai.manage`. An agent never
gets more than its user has: this only decides who may talk to which agent and how far it sees."""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import budget
from app.ai.agents import (
    CATALOG,
    DOMAINS,
    SYSTEM_ROLES,
    Agent,
    State,
    find_agent,
    member_role_keys,
    state_of,
)
from app.ai.agents import load_team as load_agents
from app.api.common import check_columns, not_found
from app.api.deps import TenantContext, UserDep, ensure_branch_allowed, require
from app.core.permissions import Permission

router = APIRouter(prefix="/ai", tags=["ai"])

UseDep = Annotated[TenantContext, Depends(require(Permission.AI_USE))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.AI_MANAGE))]

MAX_CUSTOM_AGENTS = 20
COLOR = r"^#[0-9A-Fa-f]{6}$"
ModelTier = Literal["fast", "standard", "strong"]
Tone = Literal["friendly", "formal", "short"]
Scope = Literal["all", "locations"]  # "groups" arrives with branch groups


class AgentCard(BaseModel):
    key: str
    id: UUID | None
    builtin: bool
    name: str
    role_title: str
    color: str
    topic: str
    tone: Tone
    enabled: bool
    avatar_preset: str | None
    avatar_key: str | None
    # active: usable now; locked: a module is missing (see upsell_module); disabled: switched
    # off by the owner; forbidden: this user's role may not use it.
    state: State
    upsell_module: str | None = None
    credits_used_month: float = 0
    routes: list[str] = []
    # Only for those who may manage the team (ai.manage):
    instructions: str | None = None
    tool_domains: list[str] | None = None
    allowed_roles: list[str] | None = None
    location_scope: Scope | None = None
    location_ids: list[UUID] | None = None
    model_tier: ModelTier | None = None


class Team(BaseModel):
    agents: list[AgentCard]
    credits_used: float
    credits_included: int
    can_manage: bool


class AgentChange(BaseModel):
    """Fields left out stay as they are; for a built-in agent `null` goes back to the default."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    role_title: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=COLOR)
    topic: str | None = Field(default=None, max_length=200)
    instructions: str | None = Field(default=None, max_length=4000)
    tone: Tone | None = None
    tool_domains: list[str] | None = None
    enabled: bool | None = None
    location_scope: Scope | None = None
    location_ids: list[UUID] | None = None
    allowed_roles: list[str] | None = None
    model_tier: ModelTier | None = None
    avatar_preset: str | None = Field(default=None, max_length=40)

    @field_validator("name", "role_title", "topic", "instructions", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class CustomAgent(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    role_title: str = Field(default="", max_length=80)
    color: str = Field(default="#6B7280", pattern=COLOR)
    topic: str = Field(default="", max_length=200)
    instructions: str = Field(default="", max_length=4000)
    tone: Tone = "friendly"
    tool_domains: list[str] = Field(min_length=1)
    allowed_roles: list[str] = ["owner", "manager"]
    location_scope: Scope = "all"
    location_ids: list[UUID] = []
    model_tier: ModelTier = "fast"
    avatar_preset: str | None = Field(default=None, max_length=40)

    @field_validator("name", "role_title", "topic", "instructions", mode="before")
    @classmethod
    def trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def tenant_locale(db: Session) -> str:
    return (
        db.execute(
            text("SELECT locale FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar()
        or "en"
    )


def _month_start(db: Session) -> dt.date:
    time_zone = db.execute(
        text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
    ).scalar_one()
    return dt.datetime.now(ZoneInfo(time_zone)).date().replace(day=1)


def _used_by_agent(db: Session) -> dict[str, float]:
    rows = db.execute(
        text("""
            SELECT coalesce(u.details ->> 'agent_key', 'chief') AS agent_key,
                   sum(u.quantity) AS used
            FROM app.usage_events u JOIN app.tenants t ON t.id = u.tenant_id
            WHERE u.meter = 'ai_credits'
              AND u.occurred_at >= (CAST(:start AS date)::timestamp AT TIME ZONE t.time_zone)
            GROUP BY 1
        """),
        {"start": _month_start(db)},
    )
    return {r.agent_key: float(r.used) for r in rows}


def _card(
    db: Session,
    agent: Agent,
    role_keys: frozenset[str],
    used: dict[str, float],
    manage: bool,
) -> AgentCard:
    state, upsell = state_of(db, agent, role_keys)
    spec = CATALOG.get(agent.key)
    card = AgentCard(
        key=agent.key,
        id=agent.id,
        builtin=agent.builtin,
        name=agent.name,
        role_title=agent.role_title,
        color=agent.color,
        topic=agent.topic,
        tone=agent.tone,
        enabled=agent.enabled,
        avatar_preset=agent.avatar_preset,
        avatar_key=agent.avatar_key,
        state=state,
        upsell_module=upsell,
        credits_used_month=round(used.get(agent.key, 0), 2),
        routes=list(spec.routes) if spec else [],
    )
    if manage:
        card.instructions = agent.instructions
        card.tool_domains = sorted(agent.domains - {"routing"})
        card.allowed_roles = sorted(agent.roles)
        card.location_scope = "locations" if agent.location_scope != "all" else "all"
        card.location_ids = sorted(agent.location_ids)
        card.model_tier = agent.tier
    return card


def _team(context: TenantContext, user_id: UUID) -> Team:
    db = context.session
    manage = Permission.AI_MANAGE in context.permissions
    role_keys = member_role_keys(db, context.role)
    used = _used_by_agent(db)
    # Agents the user may not use are still listed (the map shows them locked), but not
    # for a role that has none of them: that is the card's "forbidden" state.
    agents = [_card(db, a, role_keys, used, manage) for a in load_agents(db, tenant_locale(db))]
    return Team(
        agents=agents,
        credits_used=round(budget.credits_used(db, _month_start(db)), 2),
        credits_included=budget.credits_included(db),
        can_manage=manage,
    )


@router.get("/team")
def ai_team(context: UseDep, user: UserDep) -> Team:
    return _team(context, user.id)


def _agent_id(db: Session, key: str) -> UUID | None:
    """The row id behind an agent reference, if it has one."""
    if key in CATALOG:
        return db.execute(
            text("SELECT id FROM app.ai_agents WHERE builtin_key = :key"), {"key": key}
        ).scalar()
    raw = key.removeprefix("custom:")
    try:
        found = UUID(raw)
    except ValueError:
        raise not_found() from None
    return (
        db.execute(
            text("SELECT id FROM app.ai_agents WHERE id = :id AND builtin_key IS NULL"),
            {"id": found},
        ).scalar()
        or None
    )


def _checked(db: Session, context: TenantContext, change: dict[str, Any], custom: bool) -> None:
    """Validates a change to an agent's roles, domains and branches against the business."""
    if "tool_domains" in change and change["tool_domains"] is not None:
        unknown = set(change["tool_domains"]) - (set(DOMAINS) - {"routing"})
        if unknown or (custom and not change["tool_domains"]):
            raise _bad("unknown_tool_domain")
    if change.get("allowed_roles") is not None:
        custom_roles = {
            str(r) for r in db.execute(text("SELECT id FROM app.tenant_roles")).scalars()
        }
        if set(change["allowed_roles"]) - set(SYSTEM_ROLES) - custom_roles:
            raise _bad("unknown_role")
    if change.get("location_scope") == "locations" or (change.get("location_ids")):
        ids = list(dict.fromkeys(change.get("location_ids") or []))
        known = set(
            db.execute(
                text("SELECT id FROM app.locations WHERE id = ANY(:ids)"), {"ids": ids}
            ).scalars()
        )
        if not ids or set(ids) - known:
            raise _bad("unknown_branch")
        for location_id in ids:
            ensure_branch_allowed(context, location_id)


# Column -> the SQL cast its value needs.
CASTS = {
    "tool_domains": "text[]",
    "allowed_roles": "text[]",
    "location_ids": "uuid[]",
    "location_group_ids": "uuid[]",
}
NOT_NULL = {"enabled", "location_scope", "location_ids"}


AGENT_COLUMNS = frozenset(
    {
        "tenant_id", "builtin_key", "name", "role_title", "color", "topic", "instructions", "tone",
        "tool_domains", "enabled", "location_scope", "location_ids", "allowed_roles",
        "model_tier", "avatar_kind", "avatar_preset",
    }
)  # fmt: skip


def _assign(name: str) -> str:
    return f"CAST(:{name} AS {CASTS[name]})" if name in CASTS else f":{name}"


def _write(db: Session, values: dict[str, Any]) -> None:
    """Saves a built-in agent's overrides: inserts its row or updates the given columns."""
    check_columns(values, AGENT_COLUMNS)
    keys = ("tenant_id", "builtin_key")
    updates = ", ".join(f"{n} = EXCLUDED.{n}" for n in values if n not in keys)
    db.execute(
        text(
            "INSERT INTO app.ai_agents ("
            + ", ".join(values)
            + ") VALUES ("
            + ", ".join(_assign(n) for n in values)
            + ") ON CONFLICT (tenant_id, builtin_key) DO UPDATE SET "
            + updates
            + (", " if updates else "")
            + "updated_at = now()"
        ),
        values,
    )


@router.patch("/agents/{agent_key}")
def update_agent(agent_key: str, body: AgentChange, context: ManageDep, user: UserDep) -> AgentCard:
    db = context.session
    locale = tenant_locale(db)
    agent = find_agent(db, agent_key if agent_key in CATALOG else _custom_key(agent_key), locale)
    if agent is None:
        raise not_found()
    change = body.model_dump(exclude_unset=True)
    for column in NOT_NULL & change.keys():
        if change[column] is None:
            raise _bad(f"{column}_required")
    if not agent.builtin and any(
        change.get(c, "x") is None for c in ("name", "tool_domains", "allowed_roles")
    ):
        raise _bad("custom_agent_needs_value")
    _checked(db, context, change, custom=not agent.builtin)
    if change.get("location_scope") == "all":
        change["location_ids"] = []
    if "avatar_preset" in change:
        change["avatar_kind"] = "preset" if change["avatar_preset"] else None
    if not change:
        return _card(db, agent, member_role_keys(db, context.role), _used_by_agent(db), True)

    values = {**change, "tenant_id": context.tenant_id}
    if agent.builtin:
        values["builtin_key"] = agent.key
        _write(db, values)
    else:
        check_columns(change, AGENT_COLUMNS)
        sets = ", ".join(f"{n} = {_assign(n)}" for n in change)
        db.execute(
            text("UPDATE app.ai_agents SET " + sets + ", updated_at = now() WHERE id = :id"),
            {**change, "id": agent.id},
        )
    updated = find_agent(db, agent.key, locale)
    assert updated is not None
    return _card(db, updated, member_role_keys(db, context.role), _used_by_agent(db), True)


def _custom_key(key: str) -> str:
    return key if key.startswith("custom:") else f"custom:{key}"


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def create_agent(body: CustomAgent, context: ManageDep, user: UserDep) -> AgentCard:
    db = context.session
    data = body.model_dump()
    _checked(db, context, data, custom=True)
    if data["location_scope"] == "all":
        data["location_ids"] = []
    if (
        db.execute(
            text("SELECT count(*) FROM app.ai_agents WHERE builtin_key IS NULL")
        ).scalar_one()
        >= MAX_CUSTOM_AGENTS
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="agent_limit")
    avatar = data.pop("avatar_preset")
    agent_id = db.execute(
        text("""
            INSERT INTO app.ai_agents
                (tenant_id, name, role_title, color, topic, instructions, tone, tool_domains,
                 allowed_roles, location_scope, location_ids, model_tier, avatar_kind,
                 avatar_preset, created_by)
            VALUES (:tenant_id, :name, :role_title, :color, :topic, :instructions, :tone,
                    CAST(:tool_domains AS text[]), CAST(:allowed_roles AS text[]),
                    :location_scope, CAST(:location_ids AS uuid[]), :model_tier, :avatar_kind,
                    :avatar_preset, :user_id)
            RETURNING id
        """),
        {
            **data,
            "tenant_id": context.tenant_id,
            "avatar_kind": "preset" if avatar else None,
            "avatar_preset": avatar,
            "user_id": user.id,
        },
    ).scalar_one()
    agent = find_agent(db, f"custom:{agent_id}", tenant_locale(db))
    assert agent is not None
    return _card(db, agent, member_role_keys(db, context.role), {}, True)


@router.delete("/agents/{agent_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_key: str, context: ManageDep) -> None:
    """Removes a custom agent (its past conversations stay, with the agent gone). Built-in
    agents cannot be deleted, only switched off."""
    if agent_key in CATALOG:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="builtin_agent")
    agent_id = _agent_id(context.session, agent_key)
    if agent_id is None:
        raise not_found()
    context.session.execute(text("DELETE FROM app.ai_agents WHERE id = :id"), {"id": agent_id})


USAGE_DIMENSIONS = {
    "agent": "coalesce(u.details ->> 'agent_key', 'chief')",
    "user": "coalesce(u.details ->> 'user_id', 'unknown')",
    "day": "to_char((u.occurred_at AT TIME ZONE t.time_zone)::date, 'YYYY-MM-DD')",
}


class UsageRow(BaseModel):
    key: str
    credits: float


class Usage(BaseModel):
    month_start: dt.date
    credits_used: float
    credits_included: int
    by_agent: list[UsageRow]
    by_user: list[UsageRow]
    by_day: list[UsageRow]


@router.get("/usage")
def ai_usage(
    context: ManageDep,
    month: Annotated[dt.date | None, Query(description="Any day of the month; default now")] = None,
) -> Usage:
    """This month's AI credits by agent, by person and by day."""
    db = context.session
    start = (month or _month_start(db)).replace(day=1)
    end = (start + dt.timedelta(days=32)).replace(day=1)

    def grouped(dimension: str) -> list[UsageRow]:
        rows = db.execute(
            text(
                "SELECT "
                + USAGE_DIMENSIONS[dimension]
                + """ AS key, sum(u.quantity) AS credits
                FROM app.usage_events u JOIN app.tenants t ON t.id = u.tenant_id
                WHERE u.meter = 'ai_credits'
                  AND u.occurred_at >= (CAST(:start AS date)::timestamp AT TIME ZONE t.time_zone)
                  AND u.occurred_at < (CAST(:end AS date)::timestamp AT TIME ZONE t.time_zone)
                GROUP BY 1 ORDER BY 2 DESC, 1"""
            ),
            {"start": start, "end": end},
        )
        return [UsageRow(key=r.key, credits=round(float(r.credits), 2)) for r in rows]

    by_agent = grouped("agent")
    return Usage(
        month_start=start,
        credits_used=round(sum(r.credits for r in by_agent), 2),
        credits_included=budget.credits_included(db),
        by_agent=by_agent,
        by_user=grouped("user"),
        by_day=sorted(
            grouped("day"),
            key=lambda r: r.key,
        ),
    )
