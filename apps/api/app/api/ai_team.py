"""The AI team: the agents of a business, who may use them and what they may see.

Reading the team needs `ai.use`; shaping it (renaming an agent, switching it off, narrowing it to
some branches, choosing who may use it, adding a custom agent) needs `ai.manage`. An agent never
gets more than its user has: this only decides who may talk to which agent and how far it sees."""

import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import budget, structure
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
from app.api.deps import TenantContext, UserDep, ensure_branch_allowed, has_module, require
from app.api.settings import IMAGE_RESPONSES, image_response, read_image
from app.core.permissions import Permission

router = APIRouter(prefix="/ai", tags=["ai"])

UseDep = Annotated[TenantContext, Depends(require(Permission.AI_USE))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.AI_MANAGE))]

# Custom agents a business may have: 3 with AI Basic, 10 with AI Pro.
CUSTOM_AGENTS_BASIC = 3
CUSTOM_AGENTS_PRO = 10
MAX_AVATAR_BYTES = 2 * 1024 * 1024
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
    # Where an uploaded picture is served from (versioned, so browsers may keep it).
    avatar_url: str | None = None
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
    # The structure: who the agent reports to (the chief unless set), its team and its manual
    # place on the map in percent of the stage.
    reports_to: str | None = None
    team_id: UUID | None = None
    map_x: float | None = None
    map_y: float | None = None


class TeamGroup(BaseModel):
    id: UUID
    name: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#6B7280", pattern=COLOR)
    lead_key: str | None = None


class Team(BaseModel):
    agents: list[AgentCard]
    teams: list[TeamGroup] = []
    credits_used: float
    credits_included: int
    payg_enabled: bool = False
    can_manage: bool
    custom_count: int = 0
    custom_limit: int = CUSTOM_AGENTS_BASIC


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
    draft: Literal[False] | None = None  # the wizard's last step: the draft joins the team

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
    draft: bool = False  # kept out of the team while the wizard tries it

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
        avatar_url=(
            f"/ai/agents/{agent.key}/avatar?v={agent.avatar_key}"
            if agent.avatar_kind == "upload" and agent.avatar_key
            else None
        ),
        state=state,
        upsell_module=upsell,
        credits_used_month=round(used.get(agent.key, 0), 2),
        routes=list(spec.routes) if spec else [],
        reports_to=structure.effective_parent(agent),
        team_id=agent.team_id,
        map_x=agent.map_x,
        map_y=agent.map_y,
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
    everyone = load_agents(db, tenant_locale(db))
    agents = [_card(db, a, role_keys, used, manage) for a in everyone if not a.draft]
    return Team(
        agents=agents,
        teams=[TeamGroup(**vars(t)) for t in structure.load_teams(db)],
        credits_used=round(budget.credits_used(db, _month_start(db)), 2),
        credits_included=budget.credits_included(db),
        payg_enabled=budget.spend_settings(db).payg_enabled,
        can_manage=manage,
        custom_count=sum(1 for a in everyone if not a.builtin),
        custom_limit=_custom_limit(db),
    )


@router.get("/team")
def ai_team(context: UseDep, user: UserDep) -> Team:
    return _team(context, user.id)


class Placement(BaseModel):
    key: str
    reports_to: str | None = None
    team_id: UUID | None = None
    map_x: float | None = Field(default=None, ge=0, le=100)
    map_y: float | None = Field(default=None, ge=0, le=100)


class StructureUpdate(BaseModel):
    """The whole structure at once: every team and where each agent stands. Agents left out keep
    what they have."""

    teams: list[TeamGroup] = Field(max_length=20)
    agents: list[Placement]


@router.put("/structure")
def update_structure(body: StructureUpdate, context: ManageDep, user: UserDep) -> Team:
    """Saves who reports to whom, the teams and the map positions. The chief stays on top, there
    are no cycles, and an agent the business cannot use (locked) cannot be connected."""
    db = context.session
    everyone = load_agents(db, tenant_locale(db))
    by_key = {a.key: a for a in everyone}
    role_keys = member_role_keys(db, context.role)
    places = {p.key: p for p in body.agents}
    if len(places) != len(body.agents) or {t.id for t in body.teams}.__len__() != len(body.teams):
        raise _bad("duplicate")
    for key, place in places.items():
        agent = by_key.get(key)
        if agent is None or agent.draft:
            raise _bad("unknown_agent")
        wired = place.reports_to is not None or place.team_id is not None
        if wired and key != structure.CHIEF and state_of(db, agent, role_keys)[0] == "locked":
            raise _bad("locked_agent")
        parent = by_key.get(place.reports_to or "")
        if parent is not None and state_of(db, parent, role_keys)[0] == "locked":
            raise _bad("locked_agent")
    parents = {
        a.key: (places[a.key].reports_to if a.key in places else a.reports_to_key)
        for a in everyone
        if not a.draft
    }
    kept = {t.id for t in body.teams}
    members = {
        a.key: (places[a.key].team_id if a.key in places else a.team_id)
        for a in everyone
        if not a.draft
    }
    # Agents left out of the request lose a team the request removes (the database frees them).
    members = {
        k: (v if v is None or v in kept or k in places else None) for k, v in members.items()
    }
    try:
        structure.check_structure(
            set(parents),
            parents,
            {t.id for t in body.teams},
            members,
            {t.id: t.lead_key for t in body.teams},
        )
    except structure.StructureError as error:
        raise _bad(str(error)) from None

    keep = [t.id for t in body.teams]
    db.execute(text("DELETE FROM app.ai_agent_teams WHERE NOT (id = ANY(:keep))"), {"keep": keep})
    for t in body.teams:
        db.execute(
            text("""
                INSERT INTO app.ai_agent_teams (id, tenant_id, name, color, lead_key)
                VALUES (:id, app.current_tenant_id(), :name, :color, :lead)
                ON CONFLICT (tenant_id, id) DO UPDATE
                SET name = EXCLUDED.name, color = EXCLUDED.color, lead_key = EXCLUDED.lead_key
            """),
            {"id": t.id, "name": t.name, "color": t.color, "lead": t.lead_key},
        )
    for key, place in places.items():
        values = {
            "reports_to_key": place.reports_to if key != structure.CHIEF else None,
            "team_id": place.team_id,
            "map_x": place.map_x,
            "map_y": place.map_y,
        }
        agent = by_key[key]
        if agent.id is None:  # a built-in agent nobody changed yet: its row appears now
            _write(db, {"tenant_id": context.tenant_id, "builtin_key": key, **values})
        else:
            db.execute(
                text(
                    "UPDATE app.ai_agents SET reports_to_key = :reports_to_key, "
                    "team_id = :team_id, map_x = :map_x, map_y = :map_y, updated_at = now() "
                    "WHERE id = :id"
                ),
                {**values, "id": agent.id},
            )
    return _team(context, user.id)


def _custom_limit(db: Session) -> int:
    return CUSTOM_AGENTS_PRO if has_module(db, "ai_pro") else CUSTOM_AGENTS_BASIC


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
    "team_id": "uuid",
}
NOT_NULL = {"enabled", "location_scope", "location_ids"}


AGENT_COLUMNS = frozenset(
    {
        "tenant_id", "builtin_key", "name", "role_title", "color", "topic", "instructions", "tone",
        "tool_domains", "enabled", "location_scope", "location_ids", "allowed_roles",
        "model_tier", "avatar_kind", "avatar_preset", "avatar_key", "draft", "reports_to_key",
        "team_id", "map_x", "map_y",
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
        change["avatar_key"] = None
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
    if "avatar_preset" in change and updated.id is not None:
        db.execute(
            text("DELETE FROM app.ai_agent_avatars WHERE agent_id = :id"), {"id": updated.id}
        )
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
    if db.execute(
        text("SELECT count(*) FROM app.ai_agents WHERE builtin_key IS NULL")
    ).scalar_one() >= _custom_limit(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="agent_limit")
    avatar = data.pop("avatar_preset")
    agent_id = db.execute(
        text("""
            INSERT INTO app.ai_agents
                (tenant_id, name, role_title, color, topic, instructions, tone, tool_domains,
                 allowed_roles, location_scope, location_ids, model_tier, avatar_kind,
                 avatar_preset, draft, created_by)
            VALUES (:tenant_id, :name, :role_title, :color, :topic, :instructions, :tone,
                    CAST(:tool_domains AS text[]), CAST(:allowed_roles AS text[]),
                    :location_scope, CAST(:location_ids AS uuid[]), :model_tier, :avatar_kind,
                    :avatar_preset, :draft, :user_id)
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
    db = context.session
    for statement in (
        "UPDATE app.ai_agents SET reports_to_key = NULL WHERE reports_to_key = :key",
        "UPDATE app.ai_agent_teams SET lead_key = NULL WHERE lead_key = :key",
    ):
        db.execute(text(statement), {"key": agent_key})
    db.execute(text("DELETE FROM app.ai_agents WHERE id = :id"), {"id": agent_id})


def _manageable(db: Session, key: str) -> Agent:
    agent = find_agent(db, key if key in CATALOG else _custom_key(key), tenant_locale(db))
    if agent is None:
        raise not_found()
    return agent


@router.put("/agents/{agent_key}/avatar")
def upload_agent_avatar(
    agent_key: str, file: UploadFile, context: ManageDep, user: UserDep
) -> AgentCard:
    """The agent's own picture (PNG, JPEG or WebP up to 2 MB) instead of a gallery face."""
    db = context.session
    data, content_type = read_image(file, MAX_AVATAR_BYTES)
    agent = _manageable(db, agent_key)
    version = str(int(dt.datetime.now(dt.UTC).timestamp() * 1000))
    if agent.builtin:
        _write(
            db,
            {
                "tenant_id": context.tenant_id,
                "builtin_key": agent.key,
                "avatar_kind": "upload",
                "avatar_preset": None,
                "avatar_key": version,
            },
        )
    else:
        db.execute(
            text("""
                UPDATE app.ai_agents
                SET avatar_kind = 'upload', avatar_preset = NULL, avatar_key = :v,
                    updated_at = now()
                WHERE id = :id
            """),
            {"v": version, "id": agent.id},
        )
    agent_id = _agent_id(db, agent.key)
    db.execute(
        text("""
            INSERT INTO app.ai_agent_avatars (tenant_id, agent_id, content, content_type)
            VALUES (:t, :id, :content, :type)
            ON CONFLICT (tenant_id, agent_id)
            DO UPDATE SET content = EXCLUDED.content, content_type = EXCLUDED.content_type,
                          updated_at = now()
        """),
        {"t": context.tenant_id, "id": agent_id, "content": data, "type": content_type},
    )
    updated = _manageable(db, agent.key)
    return _card(db, updated, member_role_keys(db, context.role), _used_by_agent(db), True)


@router.delete("/agents/{agent_key}/avatar")
def delete_agent_avatar(agent_key: str, context: ManageDep) -> AgentCard:
    """Drops the uploaded picture; the agent goes back to its gallery face or default."""
    db = context.session
    agent = _manageable(db, agent_key)
    if agent.id is not None:
        db.execute(text("DELETE FROM app.ai_agent_avatars WHERE agent_id = :id"), {"id": agent.id})
        db.execute(
            text("""
                UPDATE app.ai_agents
                SET avatar_kind = CASE WHEN avatar_preset IS NULL THEN NULL ELSE 'preset' END,
                    avatar_key = NULL, updated_at = now()
                WHERE id = :id AND avatar_kind = 'upload'
            """),
            {"id": agent.id},
        )
    updated = _manageable(db, agent.key)
    return _card(db, updated, member_role_keys(db, context.role), _used_by_agent(db), True)


@router.get("/agents/{agent_key}/avatar", response_class=Response, responses=IMAGE_RESPONSES)
def get_agent_avatar(agent_key: str, context: UseDep) -> Response:
    agent_id = _agent_id(context.session, agent_key)
    row = (
        context.session.execute(
            text("SELECT content, content_type FROM app.ai_agent_avatars WHERE agent_id = :id"),
            {"id": agent_id},
        ).first()
        if agent_id
        else None
    )
    if row is None:
        raise not_found()
    return image_response(bytes(row.content), row.content_type)


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


# --- spend: pay-as-you-go, limits and alerts ------------------------------------------------


class CreditLimit(BaseModel):
    kind: Literal["role", "user"]
    key: str = Field(min_length=1, max_length=64, description="A role key, or a user id")
    monthly_credits: int = Field(ge=0, le=1_000_000)


class AiSpend(BaseModel):
    month_start: dt.date
    currency: str
    credits_included: int
    credits_used: float
    payg_enabled: bool
    payg_cap_minor: int | None = Field(description="Most extra spend per month; null: no cap")
    price_per_100_minor: int = Field(description="Price of 100 extra credits, minor units")
    extra_credits: float = Field(description="Credits used above the included ones")
    extra_minor: int = Field(description="What that costs this month, minor units")
    credits_limit: int | None = Field(description="Where questions stop; null: no limit")
    alerts: list[int] = Field(description="Thresholds (%) passed this month")
    limits: list[CreditLimit]


def _spend(db: Session) -> AiSpend:
    start = _month_start(db)
    settings = budget.spend_settings(db)
    included, used = budget.credits_included(db), budget.credits_used(db, start)
    alerts = db.execute(
        text("SELECT threshold FROM app.ai_credit_alerts WHERE month_start = :m ORDER BY 1"),
        {"m": start},
    ).scalars()
    limits = db.execute(
        text(
            "SELECT subject_kind, subject_key, monthly_credits FROM app.ai_credit_limits "
            "ORDER BY 1, 2"
        )
    )
    return AiSpend(
        month_start=start,
        currency=settings.currency,
        credits_included=included,
        credits_used=round(used, 2),
        payg_enabled=settings.payg_enabled,
        payg_cap_minor=settings.payg_cap_minor,
        price_per_100_minor=settings.price_per_100,
        extra_credits=round(max(used - included, 0), 2),
        extra_minor=settings.extra_minor(used, included) if settings.payg_enabled else 0,
        credits_limit=budget.credits_limit(db),
        alerts=list(alerts),
        limits=[CreditLimit(kind=r[0], key=r[1], monthly_credits=r[2]) for r in limits],
    )


@router.get("/spend")
def ai_spend_status(context: ManageDep) -> AiSpend:
    """The month's AI spend: included credits, pay-as-you-go settings, extra cost, alerts and the
    limits per role and person."""
    return _spend(context.session)


class SpendUpdate(BaseModel):
    payg_enabled: bool
    payg_cap_minor: int | None = Field(default=None, ge=0, le=100_000_000)


@router.put("/spend")
def update_ai_spend(body: SpendUpdate, context: ManageDep) -> AiSpend:
    """Turns pay-as-you-go extra credits on or off and sets the monthly cap (no cap: no limit)."""
    db = context.session
    if body.payg_enabled and budget.credits_included(db) == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="ai_module_required")
    db.execute(
        text("""
            INSERT INTO app.tenant_ai_settings (tenant_id, payg_enabled, payg_cap_minor)
            VALUES (app.current_tenant_id(), :enabled, :cap)
            ON CONFLICT (tenant_id) DO UPDATE
               SET payg_enabled = :enabled, payg_cap_minor = :cap, updated_at = now()
        """),
        {"enabled": body.payg_enabled, "cap": body.payg_cap_minor},
    )
    return _spend(db)


class LimitsUpdate(BaseModel):
    limits: list[CreditLimit] = Field(max_length=200)


@router.put("/spend/limits")
def update_ai_limits(body: LimitsUpdate, context: ManageDep) -> AiSpend:
    """Replaces the monthly credit limits per role and per person (each person gets the limit,
    not the role as a whole)."""
    db = context.session
    seen = {(item.kind, item.key) for item in body.limits}
    if len(seen) != len(body.limits):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="duplicate_limit")
    for item in body.limits:
        if item.kind == "user":
            try:
                UUID(item.key)
            except ValueError as error:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_limit_subject"
                ) from error
    db.execute(text("DELETE FROM app.ai_credit_limits"))
    for item in body.limits:
        db.execute(
            text("""
                INSERT INTO app.ai_credit_limits
                    (tenant_id, subject_kind, subject_key, monthly_credits)
                VALUES (app.current_tenant_id(), :kind, :key, :credits)
            """),
            {"kind": item.kind, "key": item.key, "credits": item.monthly_credits},
        )
    return _spend(db)
