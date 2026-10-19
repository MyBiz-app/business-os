"""AI in the MyBiz console (round 5, A9): the AI cost board, the model and emergency-stop
settings, pausing AI for one business, and the console assistant (MyBiz's own AI team).

Every route needs the console permission it would need without AI (usage.read to look,
billing.manage to change); the database functions enforce the same rules."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import console, console_agents
from app.ai import models as ai_models
from app.ai.gateway import LLMProvider, ProviderBusy, ProviderUnavailable
from app.api.assistant import ProviderDep, _check_user_rate, _model_calls
from app.api.common import not_found
from app.api.deps import UserDep
from app.api.platform import BillingDep, StaffDep, UsageDep, run_rule
from app.commerce.modules import MODULES
from app.core.config import get_settings

router = APIRouter(prefix="/platform/ai", tags=["platform"])

# A console conversation stops at this much model cost (AI credits are US cents).
CONVERSATION_CREDIT_CAP = 500
AI_MODULES = ("ai_basic", "ai_pro", "agent_finance", "agent_marketing", "whatsapp_ai")


class BusinessAICost(BaseModel):
    tenant_id: UUID
    name: str
    currency: str
    credits: float = Field(description="AI credits (US cents of model cost) in the window")
    previous_credits: float = Field(description="Credits in the window before, for the trend")
    revenue_monthly_minor: int = Field(description="Monthly price of its AI modules, minor units")
    margin_usd_minor: int | None = Field(
        description="Revenue minus cost in US cents, scaled to a month; only for USD businesses"
    )
    paused: bool


class CurrencyRevenue(BaseModel):
    currency: str
    revenue_monthly_minor: int


class AICostBoard(BaseModel):
    days: int
    total_credits: float
    previous_total_credits: float
    revenue: list[CurrencyRevenue]
    businesses: list[BusinessAICost]


def _ai_revenue(modules: list[str], currency: str) -> int:
    return sum(
        MODULES[key].prices.get(currency, MODULES[key].prices["USD"])
        for key in AI_MODULES
        if key in modules and key in MODULES
    )


@router.get("/costs")
def ai_costs(db: UsageDep, days: Annotated[int, Query(ge=1, le=90)] = 30) -> AICostBoard:
    """AI cost per business against what its AI modules earn (the margin), biggest users first."""
    rows = db.execute(text("SELECT * FROM app.platform_ai_costs(:d)"), {"d": days}).mappings()
    items: list[BusinessAICost] = []
    revenue: dict[str, int] = {}
    for r in rows:
        earned = _ai_revenue(list(r["modules"]), r["currency"])
        credits = float(r["credits"])
        month_cost = round(credits * 30 / days)
        items.append(
            BusinessAICost(
                tenant_id=r["tenant_id"],
                name=r["name"],
                currency=r["currency"],
                credits=credits,
                previous_credits=float(r["previous_credits"]),
                revenue_monthly_minor=earned,
                margin_usd_minor=earned - month_cost if r["currency"] == "USD" else None,
                paused=r["paused"],
            )
        )
        if earned:
            revenue[r["currency"]] = revenue.get(r["currency"], 0) + earned
    return AICostBoard(
        days=days,
        total_credits=sum(i.credits for i in items),
        previous_total_credits=sum(i.previous_credits for i in items),
        revenue=[CurrencyRevenue(currency=c, revenue_monthly_minor=v) for c, v in revenue.items()],
        businesses=items,
    )


class ConnectorUse(BaseModel):
    tenant_id: UUID
    name: str
    connections: int = Field(description="AI apps connected now")
    apps: list[str]
    calls: int = Field(description="Calls in the window")
    last_call: dt.datetime | None
    proposed: int = Field(description="Changes the apps proposed in the window")
    executed: int
    rejected: int
    waiting: int = Field(description="Proposals waiting for approval now")


class ConnectorBoard(BaseModel):
    days: int
    daily_limit: int = Field(description="Calls per business per rolling 24 hours")
    businesses: list[ConnectorUse]


@router.get("/connectors")
def ai_connectors(db: UsageDep, days: Annotated[int, Query(ge=1, le=90)] = 30) -> ConnectorBoard:
    """Who uses the AI connectors (Claude, ChatGPT): per business, the apps, the calls and what
    became of the changes they proposed."""
    rows = db.execute(text("SELECT * FROM app.platform_mcp_usage(:d)"), {"d": days}).mappings()
    return ConnectorBoard(
        days=days,
        daily_limit=get_settings().mcp_daily_calls_per_business,
        businesses=[ConnectorUse.model_validate(dict(r)) for r in rows],
    )


class ModelChoice(BaseModel):
    id: str
    tier: ai_models.Tier
    vendor: str
    enabled: bool


class AIPause(BaseModel):
    tenant_id: UUID
    name: str
    reason: str
    paused_by: str
    paused_at: dt.datetime


class AISettings(BaseModel):
    kill_all: bool
    model_fast: str | None
    model_standard: str | None
    model_strong: str | None
    defaults: dict[str, str] = Field(description="The model each tier uses when none is chosen")
    choices: list[ModelChoice]
    pauses: list[AIPause]
    updated_by: str | None
    updated_at: dt.datetime | None


class AISettingsChange(BaseModel):
    kill_all: bool
    model_fast: str | None = None
    model_standard: str | None = None
    model_strong: str | None = None


def _settings(db: Session) -> AISettings:
    row = db.execute(text("SELECT * FROM app.platform_ai_settings_get()")).mappings().one()
    pauses = db.execute(text("SELECT * FROM app.platform_ai_pauses()")).mappings()
    ai_models.set_overrides(row["model_fast"], row["model_standard"], row["model_strong"])
    saved = dict(ai_models.OVERRIDES)
    ai_models.OVERRIDES.clear()  # show the deployment's own defaults, not the chosen ones
    defaults = {tier: ai_models.model_for_tier(tier) for tier in ai_models.TIERS}
    ai_models.OVERRIDES.update(saved)
    return AISettings(
        kill_all=row["kill_all"],
        model_fast=row["model_fast"],
        model_standard=row["model_standard"],
        model_strong=row["model_strong"],
        defaults=defaults,
        choices=[
            ModelChoice(
                id=m.id,
                tier=m.tier,
                vendor=m.vendor,
                enabled=m.vendor in ai_models.enabled_vendors(),
            )
            for m in ai_models.MODELS.values()
            if m.vendor != "demo"
        ],
        pauses=[AIPause.model_validate(dict(p)) for p in pauses],
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    )


@router.get("/settings")
def ai_settings(db: UsageDep) -> AISettings:
    return _settings(db)


@router.put("/settings")
def change_ai_settings(body: AISettingsChange, db: BillingDep) -> AISettings:
    """Chooses the model for each tier (empty: the default) and flips the emergency stop that
    halts AI for every business at once. Both are written to the console audit log."""
    for tier, model in (
        ("fast", body.model_fast),
        ("standard", body.model_standard),
        ("strong", body.model_strong),
    ):
        if model is None:
            continue
        info = ai_models.MODELS.get(model)
        if info is None or info.vendor not in ai_models.enabled_vendors() or info.vendor == "demo":
            raise HTTPException(status_code=422, detail="model_not_available")
        if info.tier != tier:
            raise HTTPException(status_code=422, detail="model_wrong_tier")
    run_rule(
        db,
        "SELECT app.platform_ai_settings_set(:kill, :fast, :standard, :strong)",
        {
            "kill": body.kill_all,
            "fast": body.model_fast,
            "standard": body.model_standard,
            "strong": body.model_strong,
        },
    )
    return _settings(db)


class PauseChange(BaseModel):
    paused: bool
    reason: str | None = Field(default=None, max_length=500)


@router.post("/businesses/{tenant_id}/pause")
def pause_business_ai(tenant_id: UUID, body: PauseChange, db: BillingDep) -> AISettings:
    """Stops (or resumes) AI for one business, with the reason in both audit logs."""
    run_rule(
        db,
        "SELECT app.platform_ai_pause(:t, :paused, :reason)",
        {"t": tenant_id, "paused": body.paused, "reason": body.reason},
    )
    return _settings(db)


# --- The agents map -------------------------------------------------------------------------


class ConsoleAgentCard(BaseModel):
    key: console_agents.AgentKey
    color: str
    chief: bool
    ready: bool = Field(description="False until a later slice gives the agent its tools")
    enabled: bool
    name_he: str | None = Field(description="The team's own name for the agent, if set")
    name_en: str | None
    portrait_url: str | None
    x: float | None = Field(description="Place on the map in percent, null: automatic")
    y: float | None
    instructions: str | None = Field(
        description="Extra instructions; only shown to a member who can change them"
    )


class ConsoleAgentChange(BaseModel):
    enabled: bool
    name_he: str | None = Field(default=None, max_length=60)
    name_en: str | None = Field(default=None, max_length=60)
    instructions: str | None = Field(default=None, max_length=console_agents.MAX_INSTRUCTIONS)
    x: float | None = Field(default=None, ge=0, le=100)
    y: float | None = Field(default=None, ge=0, le=100)
    portrait_url: str | None = Field(default=None, max_length=500, pattern=r"^https://\S+$")


def _agent_cards(db: Session) -> list[ConsoleAgentCard]:
    permissions = console.permissions_of(db)
    changes = console_agents.overrides(db)
    editor = "billing.manage" in permissions
    cards = []
    for agent in console_agents.CATALOG.values():
        if not console_agents.can_use(agent, permissions):
            continue
        change = changes.get(agent.key, console_agents.Override())
        cards.append(
            ConsoleAgentCard(
                key=agent.key,  # type: ignore[arg-type]
                color=agent.color,
                chief=agent.key == console_agents.CHIEF,
                ready=agent.ready,
                enabled=change.enabled,
                name_he=change.name_he,
                name_en=change.name_en,
                portrait_url=change.portrait_url,
                x=change.x,
                y=change.y,
                instructions=change.instructions if editor else None,
            )
        )
    return cards


@router.get("/agents")
def console_agents_map(db: StaffDep) -> list[ConsoleAgentCard]:
    """The console's AI agents this team member may ask, for the map: the chief and the
    specialists, each with the team's changes (name, portrait, place, switched off)."""
    return _agent_cards(db)


@router.put("/agents/{key}")
def change_console_agent(
    key: console_agents.AgentKey, body: ConsoleAgentChange, db: BillingDep
) -> list[ConsoleAgentCard]:
    """Switches an agent on or off, renames it, sets its portrait and place, and writes the extra
    instructions it always gets. Written to the console audit log."""
    run_rule(
        db,
        "SELECT app.platform_ai_agent_set(:key, :enabled, :name_he, :name_en, :instructions,"
        " CAST(:x AS numeric), CAST(:y AS numeric), :portrait)",
        {
            "key": key,
            "enabled": body.enabled if key != console_agents.CHIEF else True,
            "name_he": body.name_he,
            "name_en": body.name_en,
            "instructions": body.instructions,
            "x": body.x,
            "y": body.y,
            "portrait": body.portrait_url,
        },
    )
    return _agent_cards(db)


# --- The console assistant ------------------------------------------------------------------


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str


class Chat(BaseModel):
    id: UUID
    role: console_agents.AgentKey
    title: str | None
    turns: list[Turn]
    credits: float
    updated_at: dt.datetime


class ChatSummary(BaseModel):
    id: UUID
    role: str
    title: str | None
    updated_at: dt.datetime


class ChatStart(BaseModel):
    role: console_agents.AgentKey = "manager"


class Question(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _chat(db: Session, chat_id: UUID) -> Chat:
    row = (
        db.execute(
            text("""
                SELECT id, role, title, messages, credits, updated_at
                FROM app.platform_ai_conversations WHERE id = :id
            """),
            {"id": chat_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()  # not yours, or not there: row-level security hides other people's
    return Chat(
        id=row["id"],
        role=row["role"],
        title=row["title"],
        turns=[Turn.model_validate(t) for t in console.turns_of(row["messages"])],
        credits=float(row["credits"]),
        updated_at=row["updated_at"],
    )


def _check_agent(db: Session, key: str) -> None:
    """The agent must be one this team member may ask, ready and switched on."""
    permissions = console.permissions_of(db)
    change = console_agents.overrides(db).get(key, console_agents.Override())
    why = console_agents.refusal(console_agents.CATALOG[key], change, permissions)
    if why == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=why)
    if why:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=why)


def _my_email(db: Session) -> str:
    return db.execute(text("SELECT email FROM app.platform_me()")).scalar_one()


@router.get("/assistant/conversations")
def console_list_chats(db: StaffDep) -> list[ChatSummary]:
    rows = db.execute(
        text("""
            SELECT id, role, title, updated_at FROM app.platform_ai_conversations
            ORDER BY updated_at DESC LIMIT 30
        """)
    ).mappings()
    return [ChatSummary.model_validate(dict(r)) for r in rows]


@router.post("/assistant/conversations", status_code=status.HTTP_201_CREATED)
def console_start_chat(db: StaffDep, body: ChatStart | None = None) -> Chat:
    body = body or ChatStart()
    _check_agent(db, body.role)
    chat_id = db.execute(
        text("""
            INSERT INTO app.platform_ai_conversations (staff_email, role)
            VALUES (:email, :role) RETURNING id
        """),
        {"email": _my_email(db), "role": body.role},
    ).scalar_one()
    return _chat(db, chat_id)


@router.get("/assistant/conversations/{chat_id}")
def console_get_chat(chat_id: UUID, db: StaffDep) -> Chat:
    return _chat(db, chat_id)


@router.post("/assistant/conversations/{chat_id}/messages")
def console_send_message(
    chat_id: UUID, body: Question, db: StaffDep, user: UserDep, provider: ProviderDep
) -> Chat:
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ai_not_configured"
        )
    chat = _chat(db, chat_id)
    _check_agent(db, chat.role)
    state = db.execute(text("SELECT * FROM app.ai_platform_state()")).one()
    ai_models.set_overrides(state.model_fast, state.model_standard, state.model_strong)
    if state.paused:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ai_paused")
    if chat.credits >= CONVERSATION_CREDIT_CAP:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="conversation_limit")
    _check_user_rate(user.id, provider)
    if not _model_calls.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="ai_busy")
    try:
        _ask(provider, db, chat_id, user.email, body.text)
    except ProviderBusy as error:
        raise HTTPException(status_code=429, detail="ai_busy") from error
    except ProviderUnavailable as error:
        raise HTTPException(status_code=502, detail="ai_unavailable") from error
    finally:
        _model_calls.release()
    return _chat(db, chat_id)


def _ask(provider: LLMProvider, db: Session, chat_id: UUID, email: str, question: str) -> None:
    console.ask(provider, db, chat_id, email, question)
