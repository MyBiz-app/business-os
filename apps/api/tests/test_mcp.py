"""AI connectors (R37a): OAuth sign-in, the MCP endpoint, read-only tools, usage and limits."""

import base64
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.tools import MCP_READ_TOOLS, TOOL_DOMAINS, TOOLS
from app.ai.untrusted import unwrap
from app.core import config
from app.core.brand import NAME
from app.mcp.access import AccessDenied, authenticate, count_call, tenant_context
from app.mcp.tokens import hash_token
from tests.conftest import STUDIO, AuthHeaders, add_member

REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def register(client: TestClient, redirect: str = REDIRECT, name: str = "Claude") -> dict:
    response = client.post(
        "/mcp-oauth/register", json={"client_name": name, "redirect_uris": [redirect]}
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve(
    client: TestClient, headers: dict, app: dict, challenge: str, redirect: str = REDIRECT
) -> str:
    """The person approves in the web app; returns the one-time code."""
    response = client.post(
        "/mcp-oauth/approve",
        json={
            "client_id": app["client_id"],
            "redirect_uri": redirect,
            "code_challenge": challenge,
            "state": "xyz",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    query = parse_qs(urlparse(response.json()["redirect_to"]).query)
    assert query["state"] == ["xyz"]
    return query["code"][0]


def exchange(client: TestClient, app: dict, code: str, verifier: str, redirect: str = REDIRECT):
    return client.post(
        "/mcp-oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": app["client_id"],
            "code": code,
            "redirect_uri": redirect,
            "code_verifier": verifier,
        },
    )


def connect(client: TestClient, headers: dict, name: str = "Claude") -> dict:
    """The whole sign-in; returns the app and its tokens."""
    app = register(client, name=name)
    verifier, challenge = pkce()
    tokens = exchange(client, app, approve(client, headers, app, challenge), verifier)
    assert tokens.status_code == 200, tokens.text
    return {**app, **tokens.json()}


def rpc(client: TestClient, token: str, method: str, params: dict | None = None, id: int = 1):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}},
        headers={"Authorization": f"Bearer {token}"},
    )


def call(client: TestClient, token: str, tool: str, args: dict | None = None) -> dict:
    response = rpc(client, token, "tools/call", {"name": tool, "arguments": args or {}})
    assert response.status_code == 200, response.text
    return response.json()["result"]


def tool_names(client: TestClient, token: str) -> set[str]:
    return {t["name"] for t in rpc(client, token, "tools/list").json()["result"]["tools"]}


def add_client(client: TestClient, headers: dict, name: str) -> str:
    created = client.post("/clients", json={"first_name": name}, headers=headers)
    assert created.status_code == 201
    return created.json()["id"]


def test_discovery_points_apps_to_the_sign_in(client: TestClient) -> None:
    resource = client.get("/.well-known/oauth-protected-resource").json()
    server = client.get("/.well-known/oauth-authorization-server").json()

    assert resource["resource"].endswith("/mcp")
    assert resource["authorization_servers"] == [server["issuer"]]
    assert server["code_challenge_methods_supported"] == ["S256"]
    assert server["token_endpoint"].endswith("/mcp-oauth/token")
    assert client.get("/.well-known/oauth-protected-resource/mcp").json() == resource


def test_an_app_without_a_token_is_sent_to_sign_in(client: TestClient) -> None:
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})

    assert response.status_code == 401
    assert "resource_metadata" in response.headers["WWW-Authenticate"]
    bad = rpc(client, "mbat_nonsense", "ping")
    assert bad.status_code == 401


@pytest.mark.parametrize(
    "redirect",
    ["http://evil.example/cb", "ftp://x.example/cb", "javascript:alert(1)", "https://x.example/#f"],
)
def test_only_safe_redirect_addresses_register(client: TestClient, redirect: str) -> None:
    response = client.post(
        "/mcp-oauth/register", json={"client_name": "X", "redirect_uris": [redirect]}
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


def test_a_desktop_app_may_return_to_this_machine(client: TestClient) -> None:
    assert register(client, "http://127.0.0.1:33418/callback")["client_id"].startswith("mbc_")


def test_authorize_hands_the_person_to_the_web_app(client: TestClient) -> None:
    app = register(client)
    _, challenge = pkce()
    params = {
        "client_id": app["client_id"],
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "s1",
    }

    response = client.get("/mcp-oauth/authorize", params=params, follow_redirects=False)

    assert response.status_code == 302
    target = urlparse(response.headers["location"])
    assert target.path == "/connect/mcp"
    assert parse_qs(target.query)["client_id"] == [app["client_id"]]
    wrong = client.get(
        "/mcp-oauth/authorize",
        params={**params, "redirect_uri": "https://evil.example/cb"},
        follow_redirects=False,
    )
    assert wrong.status_code == 400
    plain = client.get(
        "/mcp-oauth/authorize",
        params={**params, "code_challenge_method": "plain"},
        follow_redirects=False,
    )
    assert plain.status_code == 400


def test_the_approval_screen_names_the_app_and_where_it_returns(
    client: TestClient, studio: dict
) -> None:
    app = register(client, name="Claude")
    url = f"/mcp-oauth/clients/{app['client_id']}"

    info = client.get(url, params={"redirect_uri": REDIRECT}, headers=studio["headers"])

    assert info.json() == {"client_name": "Claude", "redirect_host": "claude.ai"}
    other = client.get(
        url, params={"redirect_uri": "https://evil.example/"}, headers=studio["headers"]
    )
    assert other.status_code == 404
    assert client.get(url, params={"redirect_uri": REDIRECT}).status_code == 401


def test_sign_in_gives_tokens_the_endpoint_accepts(client: TestClient, studio: dict) -> None:
    tokens = connect(client, studio["headers"])

    assert tokens["token_type"] == "Bearer"
    initialized = rpc(
        client, tokens["access_token"], "initialize", {"protocolVersion": "2025-06-18"}
    )
    assert initialized.json()["result"]["serverInfo"]["name"] == NAME
    assert initialized.json()["result"]["protocolVersion"] == "2025-06-18"
    assert rpc(client, tokens["access_token"], "ping").json()["result"] == {}
    notified = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert notified.status_code == 202


def test_a_code_works_once_and_only_with_its_secret(client: TestClient, studio: dict) -> None:
    app = register(client)
    verifier, challenge = pkce()
    code = approve(client, studio["headers"], app, challenge)

    wrong = exchange(client, app, code, secrets.token_urlsafe(48))
    assert wrong.status_code == 400
    assert wrong.json()["error"] == "invalid_grant"
    # A failed try does not burn the code, but a right one uses it up.
    assert exchange(client, app, code, verifier).status_code == 200
    again = exchange(client, app, code, verifier)
    assert again.status_code == 400

    other_code = approve(client, studio["headers"], app, challenge)
    other_app = register(client)
    stolen = exchange(client, other_app, other_code, verifier)
    assert stolen.status_code == 400
    elsewhere = exchange(client, app, other_code, verifier, redirect="https://evil.example/cb")
    assert elsewhere.status_code == 400


def test_an_expired_code_is_refused(client: TestClient, studio: dict, engine: Engine) -> None:
    app = register(client)
    verifier, challenge = pkce()
    code = approve(client, studio["headers"], app, challenge)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.mcp_connections SET code_expires_at = now() - '1s'::interval")
        )

    assert exchange(client, app, code, verifier).status_code == 400


def test_tokens_are_stored_only_as_hashes(client: TestClient, studio: dict, engine: Engine) -> None:
    tokens = connect(client, studio["headers"])

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT access_hash, refresh_hash, code_hash FROM app.mcp_connections")
        ).one()
    assert row.access_hash == hash_token(tokens["access_token"])
    assert tokens["access_token"] not in row
    assert tokens["refresh_token"] not in row
    assert row.code_hash is None


def test_a_refresh_token_is_used_once(client: TestClient, studio: dict) -> None:
    tokens = connect(client, studio["headers"])
    refresh = {
        "grant_type": "refresh_token",
        "client_id": tokens["client_id"],
        "refresh_token": tokens["refresh_token"],
    }

    renewed = client.post("/mcp-oauth/token", data=refresh)

    assert renewed.status_code == 200
    new_access = renewed.json()["access_token"]
    assert rpc(client, new_access, "ping").status_code == 200
    # The old access token is replaced, and the old refresh token is spent.
    assert rpc(client, tokens["access_token"], "ping").status_code == 401
    assert client.post("/mcp-oauth/token", data=refresh).status_code == 400


def test_the_person_sees_and_cuts_their_connections(client: TestClient, studio: dict) -> None:
    tokens = connect(client, studio["headers"], name="Claude")
    connect(client, studio["headers"], name="ChatGPT")

    listed = client.get("/mcp-connections", headers=studio["headers"]).json()
    assert {c["client_name"] for c in listed} == {"Claude", "ChatGPT"}
    mine = next(c for c in listed if c["client_name"] == "Claude")
    gone = client.delete(f"/mcp-connections/{mine['id']}", headers=studio["headers"])

    assert gone.status_code == 204
    assert rpc(client, tokens["access_token"], "ping").status_code == 401
    assert (
        client.post(
            "/mcp-oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": tokens["client_id"],
                "refresh_token": tokens["refresh_token"],
            },
        ).status_code
        == 400
    )
    assert len(client.get("/mcp-connections", headers=studio["headers"]).json()) == 1
    assert (
        client.delete(f"/mcp-connections/{mine['id']}", headers=studio["headers"]).status_code
        == 404
    )


def test_one_person_cannot_see_or_cut_anothers_connection(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    connect(client, studio["headers"])
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    headers = auth(manager, studio["tenant_id"])
    mine = connect(client, headers, name="Manager's app")

    assert [c["client_name"] for c in client.get("/mcp-connections", headers=headers).json()] == [
        "Manager's app"
    ]
    owner_connection = client.get("/mcp-connections", headers=studio["headers"]).json()[0]
    assert (
        client.delete(f"/mcp-connections/{owner_connection['id']}", headers=headers).status_code
        == 404
    )
    assert rpc(client, mine["access_token"], "ping").status_code == 200


def test_only_a_member_can_approve(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    app = register(client)
    _, challenge = pkce()

    response = client.post(
        "/mcp-oauth/approve",
        json={"client_id": app["client_id"], "redirect_uri": REDIRECT, "code_challenge": challenge},
        headers=auth(uuid4(), studio["tenant_id"]),
    )

    assert response.status_code == 403


def test_the_tools_offered_are_the_read_tools_the_person_may_use(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner = connect(client, studio["headers"])
    coach_headers = auth(studio["coach"], studio["tenant_id"])
    coach = connect(client, coach_headers)

    owner_tools = tool_names(client, owner["access_token"])
    coach_tools = tool_names(client, coach["access_token"])

    assert {"find_clients", "get_client", "get_metrics", "list_sessions"} <= owner_tools
    assert owner_tools <= MCP_READ_TOOLS
    # Writes stay with the built-in assistant.
    assert not owner_tools & {"book_client", "cancel_booking", "bill_month", "schedule_task"}
    # An instructor has no business numbers, as in the app.
    assert "get_metrics" not in coach_tools
    assert "find_clients" in coach_tools
    definition = rpc(client, owner["access_token"], "tools/list").json()["result"]["tools"][0]
    assert definition["annotations"]["readOnlyHint"] is True
    assert definition["inputSchema"]["type"] == "object"


def test_every_connector_tool_is_a_known_read_tool() -> None:
    assert set(TOOLS) >= MCP_READ_TOOLS
    assert set(TOOL_DOMAINS) >= MCP_READ_TOOLS
    # Tools that propose a change need AI Pro or the task board; none of them is offered.
    assert [n for n in MCP_READ_TOOLS if TOOLS[n].module == "ai_pro"] == []
    assert not MCP_READ_TOOLS & {"suggest_agent", "schedule_task", "cancel_scheduled_task"}


def test_a_tool_answers_as_the_person_inside_their_business(
    client: TestClient, studio: dict
) -> None:
    add_client(client, studio["headers"], "Dana Cohen")
    tokens = connect(client, studio["headers"])

    result = call(client, tokens["access_token"], "find_clients", {"query": "dana"})

    assert result["isError"] is False
    text_ = result["content"][0]["text"]
    assert text_.startswith("<untrusted")  # client-written text is marked as data
    assert json.loads(unwrap(text_))["clients"][0]["name"] == "Dana Cohen"


def test_a_business_cannot_read_another(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    add_client(client, studio["headers"], "Dana Cohen")
    rival = uuid4()
    rival_tenant = UUID(client.post("/tenants", json=STUDIO, headers=auth(rival)).json()["id"])
    tokens = connect(client, auth(rival, rival_tenant))

    result = call(client, tokens["access_token"], "find_clients", {"query": "dana"})

    assert json.loads(unwrap(result["content"][0]["text"]))["clients"] == []


def test_a_tool_the_person_may_not_use_is_refused(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    coach = connect(client, auth(studio["coach"], studio["tenant_id"]))

    refused = call(client, coach["access_token"], "get_metrics", {})
    write = call(client, connect(client, studio["headers"])["access_token"], "book_client", {})

    assert refused["isError"] is True
    assert write["isError"] is True
    assert "not available" in write["content"][0]["text"]
    unknown = rpc(client, coach["access_token"], "resources/list")
    assert unknown.json()["error"]["code"] == -32601


def test_bad_input_is_an_error_the_app_can_read(client: TestClient, studio: dict) -> None:
    tokens = connect(client, studio["headers"])

    result = call(client, tokens["access_token"], "get_client", {"client_id": "not-an-id"})

    assert result["isError"] is True
    assert "not a valid id" in result["content"][0]["text"]


def test_every_call_is_counted_as_usage(client: TestClient, studio: dict, engine: Engine) -> None:
    tokens = connect(client, studio["headers"], name="ChatGPT")
    call(client, tokens["access_token"], "list_plans")
    call(client, tokens["access_token"], "find_clients", {"query": "x"})
    rpc(client, tokens["access_token"], "tools/list")  # listing is free

    with engine.connect() as connection:
        events = connection.execute(
            text("SELECT details FROM app.usage_events WHERE meter = 'mcp_calls' ORDER BY id")
        ).all()
        calls, used = connection.execute(
            text("SELECT calls, last_used_at IS NOT NULL FROM app.mcp_connections")
        ).one()
    assert [e.details["tool"] for e in events] == ["list_plans", "find_clients"]
    assert events[0].details["client"] == "ChatGPT"
    assert (calls, used) == (2, True)
    listed = client.get("/mcp-connections", headers=studio["headers"]).json()[0]
    assert listed["calls"] == 2


def test_a_business_has_a_daily_call_limit(
    client: TestClient, studio: dict, monkeypatch: pytest.MonkeyPatch, engine: Engine
) -> None:
    tokens = connect(client, studio["headers"])
    monkeypatch.setenv("API_MCP_DAILY_CALLS_PER_BUSINESS", "2")
    config.get_settings.cache_clear()
    try:
        assert call(client, tokens["access_token"], "list_plans")["isError"] is False
        assert call(client, tokens["access_token"], "list_plans")["isError"] is False
        over = call(client, tokens["access_token"], "list_plans")
    finally:
        config.get_settings.cache_clear()

    assert over["isError"] is True
    assert "daily limit" in over["content"][0]["text"]
    with engine.connect() as connection:
        counted = connection.execute(
            text("SELECT count(*) FROM app.usage_events WHERE meter = 'mcp_calls'")
        ).scalar_one()
    assert counted == 2


def test_a_member_who_leaves_loses_the_connection(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    coach = connect(client, auth(studio["coach"], studio["tenant_id"]))
    assert call(client, coach["access_token"], "list_plans")["isError"] is False

    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM app.tenant_members WHERE user_id = :u"), {"u": studio["coach"]}
        )

    response = rpc(client, coach["access_token"], "tools/list")
    assert response.status_code == 403


def test_a_branch_limited_member_sees_only_their_branch(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    second = client.post("/locations", json={"name": "North"}, headers=headers).json()
    here = add_client(client, headers, "Main Client")
    there = add_client(client, headers, "North Client")
    with engine.begin() as connection:
        for name, branch in (
            ("Main Client", studio["location"]["id"]),
            ("North Client", second["id"]),
        ):
            connection.execute(
                text("UPDATE app.clients SET home_location_id = :b WHERE first_name = :n"),
                {"b": branch, "n": name},
            )
        connection.execute(
            text("UPDATE app.tenant_members SET location_ids = :ids WHERE user_id = :u"),
            {"ids": [studio["location"]["id"]], "u": studio["coach"]},
        )
    tokens = connect(client, auth(studio["coach"], studio["tenant_id"]))

    found = call(client, tokens["access_token"], "find_clients", {"query": "client"})

    names = [c["name"] for c in json.loads(unwrap(found["content"][0]["text"]))["clients"]]
    assert names == ["Main Client"]
    assert here and there
    # Tools that cannot filter by branch are not offered to a branch-limited person.
    assert "lead_pipeline" not in tool_names(client, tokens["access_token"])


def test_connector_tools_run_in_a_read_only_transaction(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    tokens = connect(client, studio["headers"])
    connection = authenticate(engine, tokens["access_token"])
    assert connection is not None

    with tenant_context(engine, connection) as tenant, pytest.raises(Exception, match="read-only"):
        tenant.session.execute(text("UPDATE app.tenants SET name = 'hacked'"))
    assert authenticate(engine, "mbat_unknown") is None
    assert count_call(engine, connection, "list_plans") is True


def test_a_closed_business_stops_answering(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    tokens = connect(client, studio["headers"])
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.tenants SET closed_at = now()"))

    assert rpc(client, tokens["access_token"], "tools/list").status_code == 403
    connection = authenticate(engine, tokens["access_token"])
    assert connection is not None
    with pytest.raises(AccessDenied), tenant_context(engine, connection):
        pass
