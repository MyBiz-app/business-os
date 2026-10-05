from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, local_today
from tests.test_bookings import new_session, set_status
from tests.test_client_app import give_plan, join, join_code


def attended_visit(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine, days_ago: int = 2
) -> tuple[dict, str]:
    """A client-app member who attended a session `days_ago` days ago."""
    user = uuid4()
    member = join(client, auth, user, join_code(client, studio))
    give_plan(client, studio, member["client_id"])
    session_id = new_session(client, studio, on=local_today() + timedelta(days=3))
    booking = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": member["client_id"]},
        headers=studio["headers"],
    ).json()
    with engine.begin() as connection:  # move the session into the past
        connection.execute(
            text("""
                UPDATE app.sessions SET starts_at = starts_at - make_interval(days => :d),
                                        ends_at = ends_at - make_interval(days => :d)
                WHERE id = :id
            """),
            {"d": days_ago + 3, "id": session_id},
        )
    set_status(client, studio["headers"], booking["id"], "checked_in")
    return {"headers": auth(user, studio["tenant_id"]), **member}, booking["id"]


def test_client_rates_an_attended_visit(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    member, booking_id = attended_visit(client, studio, auth, engine)
    headers = member["headers"]

    [pending] = client.get("/client/reviews/pending", headers=headers).json()
    assert pending["booking_id"] == booking_id and pending["service_name"] == "Pilates"

    bad = client.post(f"/client/bookings/{booking_id}/review", json={"rating": 6}, headers=headers)
    assert bad.status_code == 422
    review = client.post(
        f"/client/bookings/{booking_id}/review",
        json={"rating": 5, "comment": "  Great class  "},
        headers=headers,
    )
    assert review.status_code == 201, review.text
    assert review.json()["comment"] == "Great class"
    again = client.post(
        f"/client/bookings/{booking_id}/review", json={"rating": 1}, headers=headers
    )
    assert again.status_code == 409 and again.json()["detail"] == "already_reviewed"
    assert client.get("/client/reviews/pending", headers=headers).json() == []
    [visit] = [
        b for b in client.get("/client/bookings", headers=headers).json() if b["id"] == booking_id
    ]
    assert visit["rating"] == 5

    summary = client.get("/reviews", headers=studio["headers"]).json()
    assert summary["average"] == 5.0 and summary["count"] == 1
    assert summary["distribution"] == [0, 0, 0, 0, 1]
    assert [s["name"] for s in summary["by_service"]] == ["Pilates"]
    assert summary["latest"][0]["comment"] == "Great class"


def test_only_recent_attended_own_visits(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    old_member, old_booking = attended_visit(client, studio, auth, engine, days_ago=30)
    stale = client.post(
        f"/client/bookings/{old_booking}/review", json={"rating": 4}, headers=old_member["headers"]
    )
    assert stale.status_code == 409 and stale.json()["detail"] == "not_reviewable"

    _member, booking_id = attended_visit(client, studio, auth, engine)
    stranger = client.post(
        f"/client/bookings/{booking_id}/review", json={"rating": 1}, headers=old_member["headers"]
    )
    assert stranger.status_code == 404


def test_erasing_keeps_the_rating_without_the_comment(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    member, booking_id = attended_visit(client, studio, auth, engine)
    client.post(
        f"/client/bookings/{booking_id}/review",
        json={"rating": 2, "comment": "Too crowded"},
        headers=member["headers"],
    )
    document = client.get(
        f"/clients/{member['client_id']}/export", headers=studio["headers"]
    ).json()
    assert document["reviews"][0]["comment"] == "Too crowded"
    client.post(
        f"/clients/{member['client_id']}/erase", json={"confirm": True}, headers=studio["headers"]
    )
    [item] = client.get("/reviews", headers=studio["headers"]).json()["latest"]
    assert item["rating"] == 2 and item["comment"] is None
