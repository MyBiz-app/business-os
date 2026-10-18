"""The sign-in for AI apps: a small OAuth 2.1 server for MCP.

* Discovery: `/.well-known/oauth-protected-resource` and `/.well-known/oauth-authorization-server`.
* Registration (RFC 7591): an app registers its name and redirect addresses and gets a client id.
  There are no client secrets: every app is a public client and PKCE (S256) is required.
* Authorization: the app sends the person to `/mcp-oauth/authorize`, which hands them to the MyBiz
  web app. There they sign in as usual, see who is asking and for which business, and approve
  (`POST /mcp-oauth/approve`). MyBiz answers with the address to go back to, carrying a one-time
  code that lives five minutes.
* Token: the code (with the PKCE verifier) becomes a short-lived access token and a refresh token;
  a refresh token is used once and replaced.

A person sees and cuts their own connections with `/mcp-connections`. Nothing here stores a token:
only hashes (see `tokens.py` and migration 0133)."""

import datetime as dt
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, TenantDep
from app.core import audit
from app.core.brand import NAME
from app.core.config import get_settings
from app.core.db import EngineDep
from app.mcp.access import anonymous_session
from app.mcp.tokens import (
    ACCESS_PREFIX,
    CODE_PREFIX,
    REFRESH_PREFIX,
    hash_token,
    new_client_id,
    new_token,
)

router = APIRouter(tags=["mcp"])
hidden = APIRouter(tags=["mcp"], include_in_schema=False)

CODE_MINUTES = 5
SCOPE = "mcp:read"
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
MAX_CONNECTIONS_PER_PERSON = 20


def _api() -> str:
    return get_settings().api_url.rstrip("/")


def valid_redirect(uri: str) -> bool:
    """https anywhere, or http on this machine (desktop apps listen on a local port)."""
    try:
        parsed = urlparse(uri)
    except ValueError:
        return False
    if parsed.fragment or not parsed.hostname or len(uri) > 500:
        return False
    return parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in LOOPBACK)


def _oauth_error(error: str, description: str = "", status_code: int = 400) -> JSONResponse:
    body = {"error": error, **({"error_description": description} if description else {})}
    return JSONResponse(body, status_code=status_code, headers={"Cache-Control": "no-store"})


# --- Discovery -----------------------------------------------------------------------------


@hidden.get("/.well-known/oauth-protected-resource")
@hidden.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource() -> dict[str, Any]:
    return {
        "resource": f"{_api()}/mcp",
        "authorization_servers": [_api()],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
        "resource_name": NAME,
    }


@hidden.get("/.well-known/oauth-authorization-server")
def authorization_server() -> dict[str, Any]:
    return {
        "issuer": _api(),
        "authorization_endpoint": f"{_api()}/mcp-oauth/authorize",
        "token_endpoint": f"{_api()}/mcp-oauth/token",
        "registration_endpoint": f"{_api()}/mcp-oauth/register",
        "scopes_supported": [SCOPE],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }


# --- Registration --------------------------------------------------------------------------


class ClientRegistration(BaseModel):
    client_name: str = Field(default="", max_length=100)
    redirect_uris: list[str] = Field(default_factory=list)
    token_endpoint_auth_method: str = "none"  # noqa: S105 - an OAuth method name
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code", "refresh_token"])
    response_types: list[str] = Field(default_factory=lambda: ["code"])


@hidden.post("/mcp-oauth/register", status_code=status.HTTP_201_CREATED)
def register_client(body: ClientRegistration, engine: EngineDep) -> JSONResponse:
    uris = list(dict.fromkeys(body.redirect_uris))
    if not 1 <= len(uris) <= 5 or not all(valid_redirect(uri) for uri in uris):
        return _oauth_error("invalid_redirect_uri", "Give 1-5 https (or local http) addresses.")
    if body.token_endpoint_auth_method != "none":  # noqa: S105 - an OAuth method name
        return _oauth_error("invalid_client_metadata", "Only public clients (method none).")
    name = body.client_name.strip() or "AI app"
    client_id = new_client_id()
    with anonymous_session(engine) as session:
        session.execute(
            text("""
                INSERT INTO app.mcp_clients (id, client_name, redirect_uris)
                VALUES (:id, :name, :uris)
            """),
            {"id": client_id, "name": name, "uris": uris},
        )
    return JSONResponse(
        {
            "client_id": client_id,
            "client_name": name,
            "redirect_uris": uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": SCOPE,
        },
        status_code=201,
        headers={"Cache-Control": "no-store"},
    )


def _client(session: Any, client_id: str) -> Any:
    return session.execute(
        text("SELECT client_name, redirect_uris FROM app.mcp_clients WHERE id = :id"),
        {"id": client_id},
    ).first()


# --- Authorization -------------------------------------------------------------------------


@hidden.get("/mcp-oauth/authorize")
def authorize(
    engine: EngineDep,
    client_id: str,
    redirect_uri: str,
    code_challenge: Annotated[str, Query(min_length=43, max_length=128)],
    response_type: str = "code",
    code_challenge_method: str = "S256",
    state: Annotated[str, Query(max_length=500)] = "",
    scope: str = SCOPE,
) -> Response:
    """Hands the person to the web app's approval screen; nothing is decided here."""
    with anonymous_session(engine) as session:
        known = _client(session, client_id)
    if known is None or redirect_uri not in known.redirect_uris:
        return _oauth_error("invalid_request", "Unknown app or redirect address.")
    if response_type != "code" or code_challenge_method != "S256":
        return _oauth_error("invalid_request", "Use response_type=code and PKCE S256.")
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "state": state,
            "scope": scope,
        }
    )
    return RedirectResponse(f"{get_settings().web_url.rstrip('/')}/connect/mcp?{query}", 302)


class ClientInfo(BaseModel):
    client_name: str
    redirect_host: str = Field(description="Where the person is sent back to after approving")


@router.get("/mcp-oauth/clients/{client_id}", operation_id="mcp_client_info")
def client_info(client_id: str, redirect_uri: str, session: SessionDep) -> ClientInfo:
    """What the approval screen shows the signed-in person about the app asking (its self-chosen
    name: untrusted text, shown with the address it returns to)."""
    known = _client(session, client_id)
    if known is None or redirect_uri not in known.redirect_uris:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    return ClientInfo(client_name=known.client_name, redirect_host=urlparse(redirect_uri).netloc)


class Approval(BaseModel):
    client_id: str
    redirect_uri: str
    code_challenge: str = Field(min_length=43, max_length=128)
    state: str = Field(default="", max_length=500)


class ApprovalResult(BaseModel):
    redirect_to: str = Field(description="Send the browser here: back to the app, with the code")


@router.post("/mcp-oauth/approve", operation_id="mcp_approve")
def approve(body: Approval, tenant: TenantDep) -> ApprovalResult:
    """The signed-in person lets the app read the business they are working in."""
    db = tenant.session
    known = _client(db, body.client_id)
    if known is None or body.redirect_uri not in known.redirect_uris:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_app")
    mine = db.execute(
        text("""
            SELECT count(*) FROM app.mcp_connections
            WHERE tenant_id = app.current_tenant_id() AND user_id = app.current_user_id()
              AND revoked_at IS NULL
        """)
    ).scalar_one()
    if mine >= MAX_CONNECTIONS_PER_PERSON:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="too_many_connections")
    # Approvals nobody redeemed go away.
    db.execute(
        text("""
            DELETE FROM app.mcp_connections
            WHERE tenant_id = app.current_tenant_id() AND access_hash IS NULL
              AND code_expires_at < now()
        """)
    )
    code, code_hash = new_token(CODE_PREFIX)
    connection_id = db.execute(
        text("""
            INSERT INTO app.mcp_connections
                (tenant_id, user_id, mcp_client, client_name, redirect_uri, code_hash,
                 code_challenge, code_expires_at)
            VALUES (app.current_tenant_id(), app.current_user_id(), :client, :name, :redirect,
                    :code_hash, :challenge, now() + make_interval(mins => :minutes))
            RETURNING id
        """),
        {
            "client": body.client_id,
            "name": known.client_name,
            "redirect": body.redirect_uri,
            "code_hash": code_hash,
            "challenge": body.code_challenge,
            "minutes": CODE_MINUTES,
        },
    ).scalar_one()
    audit.record(
        db,
        "mcp.connect",
        entity_type="mcp_connection",
        entity_id=connection_id,
        client=known.client_name,
    )
    return ApprovalResult(redirect_to=_with_query(body.redirect_uri, code=code, state=body.state))


def _with_query(uri: str, **params: str) -> str:
    parsed = urlparse(uri)
    query = parse_qsl(parsed.query) + [(k, v) for k, v in params.items() if v]
    return urlunparse(parsed._replace(query=urlencode(query)))


# --- Tokens --------------------------------------------------------------------------------


def _token_response(access: str, refresh: str, minutes: int) -> JSONResponse:
    return JSONResponse(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": minutes * 60,
            "refresh_token": refresh,
            "scope": SCOPE,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@hidden.post("/mcp-oauth/token")
def token(
    engine: EngineDep,
    grant_type: Annotated[str, Form()],
    client_id: Annotated[str, Form()] = "",
    code: Annotated[str, Form()] = "",
    redirect_uri: Annotated[str, Form()] = "",
    code_verifier: Annotated[str, Form(max_length=128)] = "",
    refresh_token: Annotated[str, Form()] = "",
) -> JSONResponse:
    settings = get_settings()
    now = dt.datetime.now(dt.UTC)
    access_expires = now + dt.timedelta(minutes=settings.mcp_access_token_minutes)
    refresh_expires = now + dt.timedelta(days=settings.mcp_refresh_token_days)
    access, access_hash = new_token(ACCESS_PREFIX)
    refresh, refresh_hash = new_token(REFRESH_PREFIX)
    with anonymous_session(engine) as session:
        if grant_type == "authorization_code":
            if not (client_id and code and redirect_uri and code_verifier):
                return _oauth_error("invalid_request", "code, redirect_uri and code_verifier")
            granted = session.execute(
                text("""
                    SELECT app.mcp_exchange_code(:code, :client, :redirect, :verifier,
                                                 :access, :access_expires, :refresh,
                                                 :refresh_expires)
                """),
                {
                    "code": hash_token(code),
                    "client": client_id,
                    "redirect": redirect_uri,
                    "verifier": code_verifier,
                    "access": access_hash,
                    "access_expires": access_expires,
                    "refresh": refresh_hash,
                    "refresh_expires": refresh_expires,
                },
            ).scalar_one()
        elif grant_type == "refresh_token":
            if not (client_id and refresh_token):
                return _oauth_error("invalid_request", "client_id and refresh_token")
            granted = session.execute(
                text("""
                    SELECT app.mcp_refresh(:old, :client, :access, :access_expires, :refresh,
                                           :refresh_expires)
                """),
                {
                    "old": hash_token(refresh_token),
                    "client": client_id,
                    "access": access_hash,
                    "access_expires": access_expires,
                    "refresh": refresh_hash,
                    "refresh_expires": refresh_expires,
                },
            ).scalar_one()
        else:
            return _oauth_error("unsupported_grant_type")
    if granted is None:
        return _oauth_error("invalid_grant", "The code or token is wrong, used or expired.")
    return _token_response(access, refresh, settings.mcp_access_token_minutes)


# --- A person's own connections ------------------------------------------------------------


class McpConnection(BaseModel):
    id: UUID
    client_name: str
    created_at: dt.datetime
    last_used_at: dt.datetime | None
    calls: int


@router.get("/mcp-connections", operation_id="list_mcp_connections")
def list_connections(tenant: TenantDep) -> list[McpConnection]:
    """The AI apps the signed-in person connected to this business."""
    rows = tenant.session.execute(
        text("""
            SELECT id, client_name, created_at, last_used_at, calls
            FROM app.mcp_connections
            WHERE tenant_id = app.current_tenant_id() AND user_id = app.current_user_id()
              AND access_hash IS NOT NULL AND revoked_at IS NULL
            ORDER BY created_at DESC
        """)
    ).all()
    return [McpConnection.model_validate(r, from_attributes=True) for r in rows]


@router.delete(
    "/mcp-connections/{connection_id}",
    operation_id="revoke_mcp_connection",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_connection(connection_id: UUID, tenant: TenantDep) -> None:
    """Cuts an app off at once: its tokens stop working."""
    revoked = tenant.session.execute(
        text("""
            UPDATE app.mcp_connections
            SET revoked_at = now(), access_hash = NULL, refresh_hash = NULL, code_hash = NULL
            WHERE id = :id AND tenant_id = app.current_tenant_id()
              AND user_id = app.current_user_id() AND revoked_at IS NULL
            RETURNING client_name
        """),
        {"id": connection_id},
    ).first()
    if revoked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    audit.record(
        tenant.session,
        "mcp.revoke",
        entity_type="mcp_connection",
        entity_id=connection_id,
        client=revoked.client_name,
    )
