"""Shared types and helpers for the assistant's tools. Every tool runs as the requesting user,
inside their business, with their permissions: the assistant can never do more than the user
could in the app.

Read tools answer immediately. Write tools never act: they create a pending action with a
human-readable preview, which the user confirms in the app (see app/ai/actions.py)."""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.api.deps import TenantContext
from app.core.permissions import Permission

PENDING_ACTION_TTL = dt.timedelta(minutes=15)
MAX_ROWS = 25
MAX_ROSTER = 200


@dataclass(frozen=True)
class ToolContext:
    tenant: TenantContext
    user_id: UUID
    conversation_id: UUID
    time_zone: str
    modules: set[str]
    # The agent talking (its key is filed on the actions it proposes) and the agents the user
    # may be handed over to.
    agent_key: str = "chief"
    handoff_keys: frozenset[str] = frozenset()
    # Where a hand-over to a key really goes (a team's lead stands in for its members).
    handoff_via: dict[str, str] = field(default_factory=dict)
    # How long a card this conversation proposes stays open (a scheduled run nobody watches
    # leaves its cards for days).
    pending_ttl: dt.timedelta = PENDING_ACTION_TTL


class ToolError(Exception):
    """A problem the model should see and can react to (bad id, not allowed, ...)."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict[str, Any]
    permission: Permission
    run: Callable[[ToolContext, dict[str, Any]], dict[str, Any]]
    module: str | None = None  # extra module the tool needs (actions need AI Pro)
    feature: str | None = None  # an industry feature it needs (e.g. time_billing)

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": self.properties,
                "required": list(self.properties),
                "additionalProperties": False,
            },
        }


def _local(instant: dt.datetime, time_zone: str) -> str:
    return instant.astimezone(ZoneInfo(time_zone)).strftime("%Y-%m-%d %H:%M")


def _uuid(value: str, what: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as error:
        raise ToolError(f"{what} is not a valid id") from error


def _date(value: str, what: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise ToolError(f"{what} must be a date like 2026-10-03") from error
