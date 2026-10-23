"""The client's "all mine" view (/client/overview): one person, several businesses.

The security promise: the view reads only the signed-in person's own rows, business by business,
and no business ever learns that its client uses another one."""

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.push import LogPushSender, push_to_user
from tests.conftest import STUDIO, AuthHeaders, local_today
from tests.test_bookings import book, new_session, set_status
from tests.test_client_app import give_plan, join, join_code, member, sign_health


def another_studio(
    client: TestClient, auth: AuthHeaders, name: str, service: str = "Spinning"
) -> dict:
    """A second business (fitness, like the first) with one class type."""
    owner = uuid4()
    created = client.post("/tenants", json={**STUDIO, "name": name}, headers=auth(owner))
    assert created.status_code == 201, created.text
    tenant_id = UUID(created.json()["id"])
    headers = auth(owner, tenant_id)
    made = client.post(
        "/services",
        json={"name": service, "duration_minutes": 45, "capacity": 10},
        headers=headers,
    ).json()
    client.patch("/tenants/current", json={"booking_horizon_days": 60}, headers=headers)
    return {"owner": owner, "tenant_id": tenant_id, "headers": headers, "service": made}


def client_book(client: TestClient, auth: AuthHeaders, user: UUID, studio: dict, session: str):
    response = client.post(
        f"/client/sessions/{session}/bookings",
        json={},
        headers=auth(user, studio["tenant_id"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def overview(client: TestClient, auth: AuthHeaders, user: UUID) -> dict:
    response = client.get("/client/overview", headers=auth(user))
    assert response.status_code == 200, response.text
    return response.json()


def test_overview_needs_a_signed_in_user(client: TestClient) -> None:
    assert client.get("/client/overview").status_code == 401


def test_someone_who_is_not_a_client_anywhere_sees_nothing(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    result = overview(client, auth, studio["owner"])  # the owner is staff, not a client

    assert result == {"businesses": [], "next": [], "cards": [], "waiting": [], "rebook": []}


def test_all_my_businesses_in_one_timeline(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    other = another_studio(client, auth, "Court Club")
    user = uuid4()
    member(client, auth, studio, user)
    member(client, auth, other, user)
    later = new_session(client, other, on=local_today() + timedelta(days=22))
    sooner = new_session(client, studio, on=local_today() + timedelta(days=21))
    client_book(client, auth, user, other, later)
    client_book(client, auth, user, studio, sooner)

    result = overview(client, auth, user)

    assert {b["business"]["name"] for b in result["businesses"]} == {STUDIO["name"], "Court Club"}
    assert [(v["business_id"], v["service_name"]) for v in result["next"]] == [
        (str(studio["tenant_id"]), "Pilates"),
        (str(other["tenant_id"]), "Spinning"),
    ]
    assert result["next"][0]["session_id"] == sooner
    by_business = {b["business"]["id"]: b for b in result["businesses"]}
    assert by_business[str(studio["tenant_id"])]["upcoming"] == 1
    assert by_business[str(other["tenant_id"])]["dormant"] is False
    assert {c["business_id"] for c in result["cards"]} == {
        str(studio["tenant_id"]),
        str(other["tenant_id"]),
    }


def test_a_business_that_is_closed_is_left_out(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    other = another_studio(client, auth, "Court Club")
    user = uuid4()
    join(client, auth, user, join_code(client, studio))
    join(client, auth, user, join_code(client, other))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenants SET closed_at = now() WHERE id = :id"),
            {"id": other["tenant_id"]},
        )

    result = overview(client, auth, user)

    assert [b["business"]["name"] for b in result["businesses"]] == [STUDIO["name"]]


def test_nothing_upcoming_and_no_card_marks_the_business_dormant(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    join(client, auth, user, join_code(client, studio))

    result = overview(client, auth, user)

    assert result["businesses"][0]["dormant"] is True
    assert result["next"] == []


def test_a_visit_done_before_can_be_booked_again(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    joined = member(client, auth, studio, user)
    past = new_session(client, studio, on=local_today() - timedelta(days=3))
    booking = book(client, studio["headers"], past, joined["client_id"]).json()
    assert set_status(client, studio["headers"], booking["id"], "checked_in").status_code == 200

    result = overview(client, auth, user)

    assert [(r["business_id"], r["service_name"]) for r in result["rebook"]] == [
        (str(studio["tenant_id"]), "Pilates")
    ]
    assert result["businesses"][0]["last_visit_at"] is not None


def test_only_my_own_rows_are_shown(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    """Two clients of the same business: each sees only their own booking, card and business."""
    other = another_studio(client, auth, "Court Club")
    me, neighbour = uuid4(), uuid4()
    member(client, auth, studio, me)
    member(client, auth, studio, neighbour)
    join(client, auth, me, join_code(client, other))
    session = new_session(client, studio)
    mine = client_book(client, auth, me, studio, session)
    theirs = client_book(client, auth, neighbour, studio, session)

    mine_view = overview(client, auth, me)
    theirs_view = overview(client, auth, neighbour)

    assert [v["booking_id"] for v in mine_view["next"]] == [mine["my_booking"]["id"]]
    assert [v["booking_id"] for v in theirs_view["next"]] == [theirs["my_booking"]["id"]]
    assert len(mine_view["cards"]) == 1 and len(theirs_view["cards"]) == 1
    assert mine_view["cards"][0]["entitlement_id"] != theirs_view["cards"][0]["entitlement_id"]
    # The neighbour joined one business only: nothing of mine shows through.
    assert [b["business"]["name"] for b in theirs_view["businesses"]] == [STUDIO["name"]]
    assert str(other["tenant_id"]) not in str(theirs_view)


def test_a_business_never_learns_its_client_uses_another(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    other = another_studio(client, auth, "Court Club")
    user = uuid4()
    joined = member(client, auth, studio, user)
    member(client, auth, other, user)
    other_session = new_session(client, other)
    client_book(client, auth, user, other, other_session)
    marker = str(other["tenant_id"])

    # Everything the first business's staff can read about this client mentions only that business.
    card = client.get(f"/clients/{joined['client_id']}", headers=studio["headers"])
    bookings = client.get(f"/clients/{joined['client_id']}/bookings", headers=studio["headers"])
    listing = client.get("/clients", headers=studio["headers"])
    entitlements = client.get(
        f"/clients/{joined['client_id']}/entitlements", headers=studio["headers"]
    )
    for response in (card, bookings, listing, entitlements):
        assert response.status_code == 200, response.text
        assert marker not in response.text
        assert "Court Club" not in response.text
    assert bookings.json() == []
    # And the other business's own view of its clients does not show the first business.
    theirs = client.get("/clients", headers=other["headers"])
    assert theirs.status_code == 200
    assert str(studio["tenant_id"]) not in theirs.text and STUDIO["name"] not in theirs.text


def test_staff_cannot_read_the_overview_of_a_client(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    """The route takes no client id: it can only ever describe the caller."""
    user = uuid4()
    member(client, auth, studio, user)
    new_session(client, studio)

    owner_view = overview(client, auth, studio["owner"])

    assert owner_view["businesses"] == []
    response = client.get("/client/overview", headers=studio["headers"])
    assert response.status_code == 200 and response.json()["businesses"] == []


def test_a_waiting_health_declaration_shows_with_its_business(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    user = uuid4()
    join(client, auth, user, join_code(client, studio))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenants SET requires_health_declaration = true WHERE id = :id"),
            {"id": studio["tenant_id"]},
        )

    result = overview(client, auth, user)

    assert [(w["business_id"], w["kind"]) for w in result["waiting"]] == [
        (str(studio["tenant_id"]), "health")
    ]
    assert result["businesses"][0]["waiting"] == 1


def test_a_push_names_the_business_so_the_app_opens_it(engine: Engine) -> None:
    user, tenant = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'p@example.com')"), {"id": user}
        )
        connection.execute(
            text(
                "INSERT INTO app.push_tokens (user_id, token, platform) VALUES (:u, 'tok', 'ios')"
            ),
            {"u": user},
        )
        push = LogPushSender()
        push_to_user(connection, push, user, "Hi", "Body", tenant)
        push_to_user(connection, push, user, "Hi", "Body")

    assert push.sent_data == [{"tenant_id": str(tenant)}, None]


def test_a_team_member_who_is_also_a_client_sees_only_their_own_rows(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    """Staff may read every booking of their business, the overview still shows only theirs."""
    owner, neighbour = studio["owner"], uuid4()
    own = client.post(
        "/client/businesses/self", json={"tenant_id": str(studio["tenant_id"])}, headers=auth(owner)
    )
    assert own.status_code == 201, own.text
    sign_health(client, auth(owner, studio["tenant_id"]))
    give_plan(client, studio, own.json()["client_id"])
    member(client, auth, studio, neighbour)
    session = new_session(client, studio)
    mine = client_book(client, auth, owner, studio, session)
    client_book(client, auth, neighbour, studio, session)

    result = overview(client, auth, owner)

    assert [v["booking_id"] for v in result["next"]] == [mine["my_booking"]["id"]]
    assert len(result["cards"]) == 1


def test_the_tenant_header_does_not_widen_or_narrow_the_view(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    other = another_studio(client, auth, "Court Club")
    user, stranger = uuid4(), uuid4()
    member(client, auth, studio, user)
    member(client, auth, other, stranger)

    plain = overview(client, auth, user)
    # A header naming a business the person does not belong to changes nothing and leaks nothing.
    named = client.get("/client/overview", headers=auth(user, other["tenant_id"]))

    assert named.status_code == 200
    assert named.json() == plain
    assert str(other["tenant_id"]) not in named.text
