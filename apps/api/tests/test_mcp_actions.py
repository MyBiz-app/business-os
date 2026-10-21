"""AI connectors (R37b): an AI app may propose changes, and only the person approves them."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.tools import MCP_ACTION_TOOLS, MCP_READ_TOOLS, TOOL_DOMAINS, TOOLS
from app.ai.untrusted import unwrap
from tests.conftest import AuthHeaders, add_member
from tests.test_assistant import enable_ai_pro
from tests.test_bookings import new_client, new_session
from tests.test_mcp import REDIRECT, call, exchange, pkce, register, rpc, tool_names

PROPOSALS = {
    "book_client",
    "cancel_booking",
    "log_time",
    "bill_month",
    "send_message",
    "give_back_visit",
}


def connect(client: TestClient, headers: dict, propose: bool, name: str = "Claude") -> dict:
    """The whole sign-in, with or without letting the app propose changes."""
    app = register(client, name=name)
    verifier, challenge = pkce()
    approved = client.post(
        "/mcp-oauth/approve",
        json={
            "client_id": app["client_id"],
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "propose": propose,
        },
        headers=headers,
    )
    assert approved.status_code == 200, approved.text
    code = approved.json()["redirect_to"].split("code=")[1].split("&")[0]
    return {**app, **exchange(client, app, code, verifier).json()}


def waiting(client: TestClient, headers: dict) -> list[dict]:
    return [
        r for r in client.get("/mcp-requests", headers=headers).json() if r["status"] == "pending"
    ]


def test_action_tools_are_known_and_never_overlap_the_read_tools() -> None:
    assert set(MCP_ACTION_TOOLS) == PROPOSALS
    assert not MCP_ACTION_TOOLS & MCP_READ_TOOLS
    assert set(TOOLS) >= MCP_ACTION_TOOLS
    assert set(TOOL_DOMAINS) >= MCP_ACTION_TOOLS


def test_a_connection_only_proposes_when_the_person_allowed_it(
    client: TestClient, studio: dict
) -> None:
    enable_ai_pro(client, studio)
    read_only = connect(client, studio["headers"], propose=False)
    allowed = connect(client, studio["headers"], propose=True, name="ChatGPT")

    assert not tool_names(client, read_only["access_token"]) & PROPOSALS
    # log_time and bill_month also need an industry with time billing; a studio has none.
    assert {"book_client", "cancel_booking"} <= tool_names(client, allowed["access_token"])
    refused = call(client, read_only["access_token"], "log_time", {})
    assert refused["isError"] is True
    listed = {
        c["client_name"]: c["can_propose"]
        for c in client.get("/mcp-connections", headers=studio["headers"]).json()
    }
    assert listed == {"Claude": False, "ChatGPT": True}


def test_tools_that_change_things_are_marked_so(client: TestClient, studio: dict) -> None:
    enable_ai_pro(client, studio)
    tokens = connect(client, studio["headers"], propose=True)

    tools = rpc(client, tokens["access_token"], "tools/list").json()["result"]["tools"]

    hints = {t["name"]: t["annotations"]["readOnlyHint"] for t in tools}
    assert hints["find_clients"] is True
    assert hints["book_client"] is False and hints["cancel_booking"] is False


def test_a_proposal_waits_and_nothing_happens_until_the_person_approves(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    tokens = connect(client, headers, propose=True)

    result = call(
        client,
        tokens["access_token"],
        "book_client",
        {"session_id": session_id, "client_id": dana, "dependent_id": ""},
    )

    assert result["isError"] is False
    proposed = json.loads(unwrap(result["content"][0]["text"]))
    assert proposed["status"] == "waiting_for_user_confirmation"
    assert "Settings" in proposed["instruction"]
    assert client.get(f"/sessions/{session_id}/bookings", headers=headers).json() == []
    [request] = waiting(client, headers)
    assert request["client_name"] == "Claude"
    assert request["preview"]["client"] == "Dana"
    assert request["id"] == proposed["pending_action_id"]

    approved = client.post(f"/ai/pending-actions/{request['id']}/confirm", headers=headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "executed"
    assert len(client.get(f"/sessions/{session_id}/bookings", headers=headers).json()) == 1
    with engine.begin() as connection:
        details = connection.execute(
            text("""
                SELECT details FROM app.audit_log WHERE action = 'assistant.book_client'
                ORDER BY id DESC LIMIT 1
            """)
        ).scalar_one()
    assert details["source"]["client"] == "Claude"  # the log says which AI app asked
    assert waiting(client, headers) == []


def test_a_rejected_proposal_changes_nothing(client: TestClient, studio: dict) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    tokens = connect(client, headers, propose=True)
    call(
        client,
        tokens["access_token"],
        "book_client",
        {"session_id": session_id, "client_id": dana, "dependent_id": ""},
    )
    [request] = waiting(client, headers)

    rejected = client.post(f"/ai/pending-actions/{request['id']}/reject", headers=headers)

    assert rejected.json()["status"] == "rejected"
    assert client.get(f"/sessions/{session_id}/bookings", headers=headers).json() == []
    [entry] = client.get("/mcp-requests", headers=headers).json()
    assert entry["status"] == "rejected"


def test_only_the_person_the_app_acts_for_sees_and_decides_a_request(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    tokens = connect(client, headers, propose=True)
    call(
        client,
        tokens["access_token"],
        "book_client",
        {"session_id": session_id, "client_id": dana, "dependent_id": ""},
    )
    [request] = waiting(client, headers)
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    other = auth(manager, studio["tenant_id"])

    assert client.get("/mcp-requests", headers=other).json() == []
    decided = client.post(f"/ai/pending-actions/{request['id']}/confirm", headers=other)
    assert decided.status_code == 404


def test_a_proposal_is_checked_again_with_the_persons_permissions(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    enable_ai_pro(client, studio)
    coach_headers = auth(studio["coach"], studio["tenant_id"])
    tokens = connect(client, coach_headers, propose=True)

    # An instructor cannot bill clients in the app, so the connector does not offer it either.
    assert "bill_month" not in tool_names(client, tokens["access_token"])
    assert call(client, tokens["access_token"], "bill_month", {})["isError"] is True


def test_proposing_needs_the_business_to_have_ai_pro(client: TestClient, studio: dict) -> None:
    tokens = connect(client, studio["headers"], propose=True)

    assert not tool_names(client, tokens["access_token"]) & PROPOSALS


def test_too_many_waiting_requests_stop_new_ones(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    tokens = connect(client, headers, propose=True)
    for index in range(20):
        dana = new_client(client, headers, f"Client {index}")
        first = call(
            client,
            tokens["access_token"],
            "book_client",
            {"session_id": session_id, "client_id": dana, "dependent_id": ""},
        )
        assert first["isError"] is False

    extra = new_client(client, headers, "One too many")
    refused = call(
        client,
        tokens["access_token"],
        "book_client",
        {"session_id": session_id, "client_id": extra, "dependent_id": ""},
    )

    assert refused["isError"] is True
    assert "waiting for approval" in refused["content"][0]["text"]


def test_reads_still_cannot_write_on_a_connection_that_may_propose(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    from sqlalchemy import text as sql

    from app.mcp.access import authenticate, tenant_context

    enable_ai_pro(client, studio)
    tokens = connect(client, studio["headers"], propose=True)
    connection = authenticate(engine, tokens["access_token"])
    assert connection is not None and connection.may_propose

    with tenant_context(engine, connection) as tenant:  # the default stays read only
        try:
            tenant.session.execute(sql("UPDATE app.tenants SET name = 'hacked'"))
        except Exception as error:
            assert "read-only" in str(error)
        else:
            raise AssertionError("a read call could write")


def test_the_connector_address_is_given(client: TestClient, studio: dict) -> None:
    info = client.get("/mcp-info", headers=studio["headers"]).json()

    assert info["url"].endswith("/mcp")


def test_the_console_sees_who_uses_the_connectors(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    from tests.test_platform_ai import staff

    enable_ai_pro(client, studio)
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    tokens = connect(client, headers, propose=True)
    call(
        client,
        tokens["access_token"],
        "book_client",
        {"session_id": session_id, "client_id": dana, "dependent_id": ""},
    )

    assert client.get("/platform/ai/connectors", headers=headers).status_code == 403
    _, _, reader = staff(engine, auth, "usage.read")
    board = client.get("/platform/ai/connectors?days=30", headers=reader).json()

    mine = next(b for b in board["businesses"] if b["tenant_id"] == str(studio["tenant_id"]))
    assert mine["apps"] == ["Claude"] and mine["connections"] == 1
    assert mine["calls"] == 1 and mine["proposed"] == 1 and mine["waiting"] == 1
    assert board["daily_limit"] > 0


def test_a_message_to_a_client_waits_for_approval_then_is_queued(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    modules = {"client_app": 1, "ai_pro": 1, "whatsapp": 1}
    assert (
        client.put(
            "/tenants/current/modules", json={"modules": modules}, headers=headers
        ).status_code
        == 200
    )
    dana = client.post(
        "/clients", json={"first_name": "Dana", "phone": "050-1234567"}, headers=headers
    ).json()["id"]
    tokens = connect(client, headers, propose=True)

    proposed = call(
        client,
        tokens["access_token"],
        "send_message",
        {"client_id": dana, "body": "See you at 18:00"},
    )

    assert proposed["isError"] is False
    assert client.get("/messages", headers=headers).json() == []
    [request] = waiting(client, headers)
    assert request["preview"]["body"] == "See you at 18:00"
    approved = client.post(f"/ai/pending-actions/{request['id']}/confirm", headers=headers)
    assert approved.status_code == 200, approved.text
    [sent] = client.get("/messages", headers=headers).json()
    assert sent["body"] == "See you at 18:00" and sent["client_id"] == dana


def test_a_message_needs_a_phone_number(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    modules = {"client_app": 1, "ai_pro": 1, "whatsapp": 1}
    client.put("/tenants/current/modules", json={"modules": modules}, headers=headers)
    nobody = new_client(client, headers, "NoPhone")
    tokens = connect(client, headers, propose=True)

    refused = call(
        client, tokens["access_token"], "send_message", {"client_id": nobody, "body": "Hi"}
    )

    assert refused["isError"] is True
    assert waiting(client, headers) == []


def test_giving_a_visit_back_waits_for_approval(client: TestClient, studio: dict) -> None:
    from tests.test_cancellation_policy import booked_with_card, credits_left, week

    enable_ai_pro(client, studio)
    headers = studio["headers"]
    week(client, headers)
    client_id, booking = booked_with_card(client, studio)
    tokens = connect(client, headers, propose=True)
    args = {"booking_id": booking["id"], "reason": "family emergency"}

    too_early = call(client, tokens["access_token"], "give_back_visit", args)
    assert too_early["isError"] is True  # not cancelled late yet: nothing to give back

    client.patch(f"/bookings/{booking['id']}", json={"status": "cancelled"}, headers=headers)
    assert credits_left(client, headers, client_id) == 2
    proposed = call(client, tokens["access_token"], "give_back_visit", args)

    assert proposed["isError"] is False
    assert credits_left(client, headers, client_id) == 2  # nothing happens until approval
    [request] = waiting(client, headers)
    approved = client.post(f"/ai/pending-actions/{request['id']}/confirm", headers=headers)
    assert approved.status_code == 200, approved.text
    assert credits_left(client, headers, client_id) == 3
