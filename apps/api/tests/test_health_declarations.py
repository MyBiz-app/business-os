from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_bookings import new_session
from tests.test_client_app import give_plan, join, join_code, sign_health


def joined_with_plan(client: TestClient, auth: AuthHeaders, studio: dict) -> tuple[dict, dict]:
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    give_plan(client, studio, joined["client_id"])
    return joined, auth(user, studio["tenant_id"])


def book(client: TestClient, headers: dict, session_id: str):
    return client.post(f"/client/sessions/{session_id}/bookings", headers=headers)


def test_fitness_business_requires_a_declaration(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    tenant = client.get("/tenants/current", headers=studio["headers"]).json()
    assert tenant["requires_health_declaration"] is True
    _, headers = joined_with_plan(client, auth, studio)

    mine = client.get("/client/health-declaration", params={"locale": "en"}, headers=headers)

    assert mine.status_code == 200
    body = mine.json()
    assert body["required"] is True and body["state"] == "missing" and body["current"] is None
    assert body["form"]["key"] == "fitness-v1"
    assert len(body["form"]["questions"]) == 7
    assert body["form"]["statement"].startswith("I declare")
    response = book(client, headers, new_session(client, studio))
    assert response.status_code == 409
    assert response.json()["detail"] == "health_declaration_required"


def test_all_no_is_valid_for_a_year_and_lets_the_client_book(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, headers = joined_with_plan(client, auth, studio)

    signed = sign_health(client, headers)

    assert signed["state"] == "ok"
    current = signed["current"]
    assert current["status"] == "valid" and current["all_clear"] is True
    assert current["valid_until"] == (local_today() + timedelta(days=365)).isoformat()
    assert current["answers"][0]["question"].startswith("האם")  # stored as shown (Hebrew)
    assert book(client, headers, new_session(client, studio)).status_code == 201


def test_a_yes_waits_for_the_studio_to_approve(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    joined, headers = joined_with_plan(client, auth, studio)
    session_id = new_session(client, studio)

    signed = sign_health(client, headers, yes=("bone_joint",))

    assert signed["state"] == "needs_review"
    blocked = book(client, headers, session_id)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "health_declaration_review"

    # Staff can still book the client; the roster shows the state.
    staff_booking = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": joined["client_id"]},
        headers=studio["headers"],
    )
    assert staff_booking.status_code == 201
    assert staff_booking.json()["health_state"] == "needs_review"

    history = client.get(
        f"/clients/{joined['client_id']}/health-declarations", headers=studio["headers"]
    ).json()
    assert history["state"] == "needs_review"
    declaration_id = history["declarations"][0]["id"]
    approved = client.post(
        f"/health-declarations/{declaration_id}/review",
        json={"approve": True, "note": "Physio letter on file"},
        headers=studio["headers"],
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    again = client.post(
        f"/health-declarations/{declaration_id}/review",
        json={"approve": False},
        headers=studio["headers"],
    )
    assert again.status_code == 409
    roster = client.get(f"/sessions/{session_id}/bookings", headers=studio["headers"]).json()
    assert roster[0]["health_state"] == "ok"


def test_rejected_declaration_blocks_until_a_new_one(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, headers = joined_with_plan(client, auth, studio)
    signed = sign_health(client, headers, yes=("heart",))
    client.post(
        f"/health-declarations/{signed['current']['id']}/review",
        json={"approve": False},
        headers=studio["headers"],
    )
    session_id = new_session(client, studio)

    assert book(client, headers, session_id).json()["detail"] == "health_declaration_review"
    assert sign_health(client, headers)["state"] == "ok"  # the latest declaration counts
    assert book(client, headers, session_id).status_code == 201


def test_expired_declaration_needs_renewal(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    _, headers = joined_with_plan(client, auth, studio)
    sign_health(client, headers)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.health_declarations SET valid_until = :d"),
            {"d": local_today() - timedelta(days=1)},
        )

    assert client.get("/client/health-declaration", headers=headers).json()["state"] == "expired"
    response = book(client, headers, new_session(client, studio))
    assert response.json()["detail"] == "health_declaration_required"


def test_answers_must_cover_the_form(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    _, headers = joined_with_plan(client, auth, studio)

    partial = client.post(
        "/client/health-declaration",
        json={"locale": "he", "answers": {"heart": False}, "signed_name": "Dana", "accept": True},
        headers=headers,
    )
    not_accepted = client.post(
        "/client/health-declaration",
        json={"locale": "he", "answers": {}, "signed_name": "Dana", "accept": False},
        headers=headers,
    )

    assert partial.status_code == 422
    assert not_accepted.status_code == 422


def test_business_can_turn_the_requirement_off(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, headers = joined_with_plan(client, auth, studio)
    updated = client.patch(
        "/tenants/current",
        json={"requires_health_declaration": False},
        headers=studio["headers"],
    )
    assert updated.json()["requires_health_declaration"] is False

    assert book(client, headers, new_session(client, studio)).status_code == 201


def test_clients_see_only_their_own_declarations(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, alice = joined_with_plan(client, auth, studio)
    bob_joined, bob = joined_with_plan(client, auth, studio)
    sign_health(client, alice, yes=("heart",))

    assert client.get("/client/health-declaration", headers=bob).json()["current"] is None
    # Clients are not staff: the staff endpoints refuse them.
    staff_view = client.get(f"/clients/{bob_joined['client_id']}/health-declarations", headers=bob)
    assert staff_view.status_code == 403


def test_review_needs_clients_write(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    joined, headers = joined_with_plan(client, auth, studio)
    signed = sign_health(client, headers, yes=("heart",))
    coach = auth(studio["coach"], studio["tenant_id"])
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")

    as_coach = client.post(
        f"/health-declarations/{signed['current']['id']}/review",
        json={"approve": True},
        headers=coach,
    )
    as_desk = client.get(
        f"/clients/{joined['client_id']}/health-declarations",
        headers=auth(desk, studio["tenant_id"]),
    )

    assert as_coach.status_code == 403
    assert as_desk.status_code == 200
