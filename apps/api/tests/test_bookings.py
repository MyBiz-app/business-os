from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member
from tests.test_tenants import STUDIO


def new_session(client: TestClient, studio: dict, capacity: int = 2, on: date | None = None) -> str:
    on = on or date.today() + timedelta(days=30)
    created = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": on.isoformat(),
            "start_time": "18:00",
            "capacity": capacity,
        },
        headers=studio["headers"],
    )
    assert created.status_code == 201
    return created.json()["session_ids"][0]


def new_client(client: TestClient, headers: dict, name: str) -> str:
    created = client.post("/clients", json={"first_name": name}, headers=headers)
    assert created.status_code == 201
    return created.json()["id"]


def book(client: TestClient, headers: dict, session_id: str, client_id: str):
    return client.post(
        f"/sessions/{session_id}/bookings", json={"client_id": client_id}, headers=headers
    )


def set_status(client: TestClient, headers: dict, booking_id: str, status: str):
    return client.patch(f"/bookings/{booking_id}", json={"status": status}, headers=headers)


def counts(client: TestClient, headers: dict, session_id: str) -> tuple[int, int]:
    session = client.get(f"/sessions/{session_id}", headers=headers).json()
    return session["booked"], session["waitlisted"]


def test_books_until_full_then_waitlists_in_order(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio, capacity=2)
    names = ["Dana", "Noa", "Yael", "Maya"]
    bookings = [book(client, headers, session_id, new_client(client, headers, n)) for n in names]

    assert [b.status_code for b in bookings] == [201] * 4
    assert [b.json()["status"] for b in bookings] == [
        "booked",
        "booked",
        "waitlisted",
        "waitlisted",
    ]
    assert [b.json()["waitlist_position"] for b in bookings] == [None, None, 1, 2]
    assert counts(client, headers, session_id) == (2, 2)

    roster = client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    assert [b["client_name"] for b in roster] == names


def test_cancel_promotes_first_waitlisted(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio, capacity=1)
    first = book(client, headers, session_id, new_client(client, headers, "Dana")).json()
    second = book(client, headers, session_id, new_client(client, headers, "Noa")).json()
    third = book(client, headers, session_id, new_client(client, headers, "Yael")).json()

    cancelled = set_status(client, headers, first["id"], "cancelled")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["late_cancel"] is False  # 30 days ahead, outside the 2h window
    roster = {
        b["id"]: b for b in client.get(f"/sessions/{session_id}/bookings", headers=headers).json()
    }
    assert roster[second["id"]]["status"] == "booked"
    assert roster[third["id"]]["status"] == "waitlisted"
    assert roster[third["id"]]["waitlist_position"] == 1


def test_capacity_increase_promotes(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio, capacity=1)
    book(client, headers, session_id, new_client(client, headers, "Dana"))
    book(client, headers, session_id, new_client(client, headers, "Noa"))

    client.patch(f"/sessions/{session_id}", json={"capacity": 3}, headers=headers)

    assert counts(client, headers, session_id) == (2, 0)


def test_late_cancel_inside_window_and_no_promotion_for_past_sessions(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio, capacity=1)
    first = book(client, headers, session_id, new_client(client, headers, "Dana")).json()
    waiting = book(client, headers, session_id, new_client(client, headers, "Noa")).json()
    with engine.begin() as connection:  # the session started 10 minutes ago
        connection.execute(
            text("""
                UPDATE app.sessions SET starts_at = now() - interval '10 minutes',
                                        ends_at = now() + interval '45 minutes'
                WHERE id = :id
            """),
            {"id": session_id},
        )

    cancelled = set_status(client, headers, first["id"], "cancelled").json()

    assert cancelled["late_cancel"] is True
    assert counts(client, headers, session_id) == (0, 1)
    assert waiting["status"] == "waitlisted"


def test_check_in_no_show_and_undo(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio)
    booking = book(client, headers, session_id, new_client(client, headers, "Dana")).json()

    checked_in = set_status(client, headers, booking["id"], "checked_in").json()
    assert checked_in["status"] == "checked_in"
    assert checked_in["checked_in_at"] is not None

    undone = set_status(client, headers, booking["id"], "booked").json()
    assert undone["checked_in_at"] is None
    assert set_status(client, headers, booking["id"], "no_show").json()["status"] == "no_show"
    assert counts(client, headers, session_id) == (1, 0)  # a no-show still holds the spot


def test_rejects_duplicates_bad_transitions_and_cancelled_sessions(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio, capacity=1)
    dana = new_client(client, headers, "Dana")
    noa = new_client(client, headers, "Noa")
    booking = book(client, headers, session_id, dana).json()

    assert book(client, headers, session_id, dana).json()["detail"] == "already_booked"
    waiting = book(client, headers, session_id, noa).json()
    assert set_status(client, headers, waiting["id"], "checked_in").status_code == 409
    set_status(client, headers, booking["id"], "cancelled")
    assert set_status(client, headers, booking["id"], "booked").status_code == 409
    # A cancelled booking does not block booking again.
    assert book(client, headers, session_id, dana).json()["status"] == "waitlisted"

    client.patch(f"/sessions/{session_id}", json={"status": "cancelled"}, headers=headers)
    late = book(client, headers, session_id, new_client(client, headers, "Yael"))
    assert late.status_code == 409
    assert late.json()["detail"] == "session_cancelled"


def test_client_history(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    soon = new_session(client, studio, on=date.today() + timedelta(days=3))
    later = new_session(client, studio, on=date.today() + timedelta(days=10))
    book(client, headers, soon, dana)
    book(client, headers, later, dana)

    history = client.get(f"/clients/{dana}/bookings", headers=headers).json()

    assert [b["session_id"] for b in history] == [later, soon]
    assert history[0]["service_name"] == "Pilates"


def test_staff_can_check_in_but_not_create_sessions(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio)
    dana = new_client(client, headers, "Dana")
    coach_headers = auth(studio["coach"], studio["tenant_id"])

    booking = book(client, coach_headers, session_id, dana)
    assert booking.status_code == 201
    assert set_status(client, coach_headers, booking.json()["id"], "checked_in").status_code == 200


def test_bookings_are_tenant_isolated(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    session_id = new_session(client, studio)
    booking = book(client, headers, session_id, new_client(client, headers, "Dana")).json()

    other_owner = uuid4()
    other = UUID(client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"])
    other_headers = auth(other_owner, other)
    stranger = new_client(client, other_headers, "Stranger")

    assert client.get(f"/sessions/{session_id}/bookings", headers=other_headers).json() == []
    assert set_status(client, other_headers, booking["id"], "cancelled").status_code == 404
    assert book(client, other_headers, session_id, stranger).status_code == 404
    # A foreign client cannot be booked into this business's session.
    assert book(client, headers, session_id, stranger).status_code == 422


@pytest.mark.parametrize("role", ["front_desk", "manager"])
def test_desk_roles_can_book(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, role: str
) -> None:
    user = uuid4()
    add_member(engine, studio["tenant_id"], user, role)
    session_id = new_session(client, studio)
    dana = new_client(client, studio["headers"], "Dana")

    assert book(client, auth(user, studio["tenant_id"]), session_id, dana).status_code == 201
