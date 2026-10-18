"""What AI apps asked for: the requests that wait for the person's approval, and the address to
give an app. A request is a pending action filed by an AI app (agent key `mcp`); approving or
rejecting it uses the same endpoints as the assistant's cards (`/ai/pending-actions/...`), which
check everything again before anything changes."""

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import TenantDep
from app.core.brand import NAME
from app.core.config import get_settings

router = APIRouter(tags=["mcp"])

HISTORY_DAYS = 30
MAX_REQUESTS = 50


class ConnectorInfo(BaseModel):
    name: str = Field(description="What to call the connector in the AI app")
    url: str = Field(description="The address to paste into the AI app")


@router.get("/mcp-info", operation_id="mcp_info")
def info(_tenant: TenantDep) -> ConnectorInfo:
    return ConnectorInfo(name=NAME, url=f"{get_settings().api_url.rstrip('/')}/mcp")


class McpRequest(BaseModel):
    id: UUID
    tool_name: str
    preview: dict[str, Any]
    client_name: str | None = Field(description="The AI app that asked")
    status: Literal["pending", "rejected", "expired", "executed", "failed"]
    created_at: dt.datetime
    expires_at: dt.datetime
    result: dict[str, Any] | None


@router.get("/mcp-requests", operation_id="list_mcp_requests")
def list_requests(tenant: TenantDep) -> list[McpRequest]:
    """The changes AI apps proposed to the signed-in person: the ones waiting first, then what
    happened to the recent ones. Only the person the app acted for sees and decides them."""
    rows = (
        tenant.session.execute(
            text("""
                SELECT id, tool_name, preview, preview #>> '{source,client}' AS client_name,
                       CASE WHEN status = 'pending' AND expires_at <= now()
                            THEN 'expired' ELSE status END AS status,
                       created_at, expires_at, result
                FROM app.pending_actions
                WHERE tenant_id = app.current_tenant_id() AND agent_key = 'mcp'
                  AND requested_by = app.current_user_id()
                  AND created_at > now() - make_interval(days => :days)
                ORDER BY (status = 'pending' AND expires_at > now()) DESC, created_at DESC
                LIMIT :limit
            """),
            {"days": HISTORY_DAYS, "limit": MAX_REQUESTS},
        )
        .mappings()
        .all()
    )
    return [McpRequest.model_validate(dict(r)) for r in rows]
