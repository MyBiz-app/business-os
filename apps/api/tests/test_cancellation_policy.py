from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, add_member, local_today
from tests.test_bookings import book, new_client, new_session, set_status
from tests.test_client_app import member
from tests.test_plans import card, sell

SOON = 3  # days ahead: inside a one-week window, outside a zero one


def policy(client: TestClient, headers: dict, **changes: object) -> dict:
    body = {
        "group_minutes": 360,
        "personal_minutes": 1440,
        "resource_minutes": 1440,
        "late_outcome": "counts",
        "no_show_outcome": "counts",
        "no_show_limit": None,
        **changes,
    }
    saved = client.put("/cancellation-policy", json=body, headers=headers)
    assert saved.status_code == 200, saved.text
    return saved.json()


def week(client: TestClient, headers: dict) -> dict:
    """A one-week free window: cancelling anything less than a week ahead is late."""
    return policy(client, headers, group_minutes=10080, personal_minutes=10080)


def credits_left(client: TestClient, headers: dict, client_id: str) -> int:
    held = client.get(f"/clients/{client_id}/entitlements", headers=headers).json()
    return held[0]["credits_remaining"]


def booked_with_card(client: TestClient, studio: dict, credits: int = 3, capacity: int = 2):
    """A client with a punch card, booked into a session SOON days ahead: (client_id, booking)."""
    headers = studio["headers"]
    client_id = new_client(client, headers, "Dana")
    sell(client, headers, client_id, card(client, headers, credits)["id"])
    on = local_today() + timedelta(days=SOON)
    booking = book(client, headers, new_session(client, studio, capacity, on), client_id).json()
    assert booking["plan_name"] is not None
    return client_id, booking


def test_new_business_starts_with_its_category_policy(client: TestClient, studio: dict) -> None:
    overview = client.get("/cancellation-policy", headers=studio["headers"]).json()

    assert overview["business"] == {
        "group_minutes": 360,
        "personal_minutes": 1440,
        "resource_minutes": 1440,
        "late_outcome": "counts",
        "no_show_outcome": "counts",
        "no_show_limit": None,
        "configured": False,  # the suggestion applies, until the business confirms it
    }
    saved = policy(client, studio["headers"])
    assert saved["business"]["configured"] is True
    assert overview["suggested"]["group_minutes"] == 360
    assert "6" in overview["text"]["en"] and "6" in overview["text"]["he"]
    tenant = client.get("/tenants/current", headers=studio["headers"]).json()
    assert tenant["cancellation_window_minutes"] == 360  # the old single window follows


def test_policy_text_names_what_differs(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    same = policy(client, headers, group_minutes=1440, personal_minutes=1440)
    assert same["text"]["en"].startswith("You can cancel for free up to 1 day before the session.")

    mixed = policy(client, headers, late_outcome="recorded", no_show_limit=3)["text"]["en"]
    assert "a class for free up to 6 hours" in mixed
    assert "a court or room for free up to 1 day" in mixed
    assert "is noted but does not count" in mixed and "After 3 missed visits" in mixed


def test_policy_validation_and_permissions(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    fee = client.put(
        "/cancellation-policy",
        json={
            "group_minutes": 60,
            "personal_minutes": 60,
            "resource_minutes": 60,
            "late_outcome": "fee",
        },
        headers=headers,
    )
    assert fee.status_code == 422  # a fee waits for payments
    assert (
        client.put(
            "/cancellation-policy",
            json={"group_minutes": 99999, "personal_minutes": 1, "resource_minutes": 1},
            headers=headers,
        ).status_code
        == 422
    )

    reception = uuid4()
    add_member(engine, studio["tenant_id"], reception, "front_desk")
    denied = client.put(
        "/cancellation-policy",
        json={"group_minutes": 60, "personal_minutes": 60, "resource_minutes": 60},
        headers=auth(reception, studio["tenant_id"]),
    )
    assert denied.status_code == 403
    assert (
        client.get("/cancellation-policy", headers=auth(reception, studio["tenant_id"])).status_code
        == 200
    )


def test_late_cancel_counts_or_is_only_recorded(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    week(client, headers)
    client_id, booking = booked_with_card(client, studio)
    assert credits_left(client, headers, client_id) == 2

    late = set_status(client, headers, booking["id"], "cancelled").json()
    assert late["late_cancel"] is True
    assert credits_left(client, headers, client_id) == 2  # counts as a used visit

    policy(client, headers, group_minutes=10080, personal_minutes=10080, late_outcome="recorded")
    second = book(
        client,
        headers,
        new_session(client, studio, 2, local_today() + timedelta(days=SOON)),
        client_id,
    ).json()
    assert credits_left(client, headers, client_id) == 1
    noted = set_status(client, headers, second["id"], "cancelled").json()
    assert noted["late_cancel"] is True  # still recorded as late
    assert credits_left(client, headers, client_id) == 2  # but the visit is not used up


def test_most_specific_layer_wins(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    week(client, headers)
    service_id = studio["service"]["id"]
    client_id, booking = booked_with_card(client, studio)

    # The service says a day's notice is enough: three days ahead is no longer late.
    saved = client.put(
        f"/services/{service_id}/cancellation-policy",
        json={"free_minutes": 1440, "late_outcome": "counts", "no_show_outcome": "counts"},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["services"][0]["policy"]["free_minutes"] == 1440
    free = set_status(client, headers, booking["id"], "cancelled").json()
    assert free["late_cancel"] is False

    # The plan beats the service: this plan needs a week's notice.
    plan_id = client.get(f"/clients/{client_id}/entitlements", headers=headers).json()[0]["plan_id"]
    client.put(
        f"/plans/{plan_id}/cancellation-policy",
        json={"free_minutes": 10080, "late_outcome": "counts", "no_show_outcome": "counts"},
        headers=headers,
    )
    again = book(
        client,
        headers,
        new_session(client, studio, 2, local_today() + timedelta(days=SOON)),
        client_id,
    ).json()
    assert set_status(client, headers, again["id"], "cancelled").json()["late_cancel"] is True

    cleared = client.delete(f"/plans/{plan_id}/cancellation-policy", headers=headers)
    assert cleared.json()["plans"][0]["policy"] is None
    unknown = client.put(
        f"/plans/{uuid4()}/cancellation-policy",
        json={"free_minutes": 5},
        headers=headers,
    )
    assert unknown.status_code == 404


def test_no_show_outcome_and_undo(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    policy(client, headers, no_show_outcome="counts")
    client_id, booking = booked_with_card(client, studio)

    assert set_status(client, headers, booking["id"], "no_show").status_code == 200
    assert credits_left(client, headers, client_id) == 2  # counts

    policy(client, headers, no_show_outcome="recorded")
    set_status(client, headers, booking["id"], "booked")
    set_status(client, headers, booking["id"], "no_show")
    assert credits_left(client, headers, client_id) == 3  # only recorded

    set_status(client, headers, booking["id"], "booked")
    assert credits_left(client, headers, client_id) == 2


def test_waive_gives_the_visit_back(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    week(client, headers)
    client_id, booking = booked_with_card(client, studio)
    waive = f"/bookings/{booking['id']}/waive"

    assert client.post(waive, json={"reason": "x"}, headers=headers).status_code == 422
    assert client.post(waive, json={"reason": "valid reason"}, headers=headers).status_code == 409

    set_status(client, headers, booking["id"], "cancelled")
    assert credits_left(client, headers, client_id) == 2

    instructor = uuid4()
    add_member(engine, studio["tenant_id"], instructor, "staff")
    forbidden = client.post(
        waive, json={"reason": "family emergency"}, headers=auth(instructor, studio["tenant_id"])
    )
    assert forbidden.status_code == 403

    done = client.post(waive, json={"reason": "family emergency"}, headers=headers)
    assert done.status_code == 200
    assert credits_left(client, headers, client_id) == 3
    again = client.post(waive, json={"reason": "family emergency"}, headers=headers)
    assert again.status_code == 409

    waivers = client.get(f"/clients/{client_id}/waivers", headers=headers).json()
    assert waivers["this_year"] == 1
    assert waivers["items"][0]["reason"] == "family emergency"
    assert waivers["items"][0]["booking_id"] == booking["id"]
    with engine.begin() as connection:
        kinds = (
            connection.execute(
                text("SELECT kind FROM app.notifications WHERE client_id = :id"), {"id": client_id}
            )
            .scalars()
            .all()
        )
    assert "credit_returned" in kinds


def week_of_sessions(client: TestClient, studio: dict, count: int) -> list[str]:
    """Sessions on consecutive days of one Sunday-to-Saturday week, a few weeks ahead."""
    start = local_today() + timedelta(days=21)
    sunday = start + timedelta(days=(6 - start.weekday()) % 7)
    return [
        new_session(client, studio, 5, sunday + timedelta(days=offset)) for offset in range(count)
    ]


def test_membership_quota_per_week(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    plan = client.post(
        "/plans",
        json={
            "name": "Twice a week",
            "kind": "membership",
            "price_amount": 30000,
            "validity_days": 60,
            "period_quota": 2,
            "period_unit": "week",
        },
        headers=headers,
    )
    assert plan.status_code == 201, plan.text
    assert (plan.json()["period_quota"], plan.json()["period_unit"]) == (2, "week")
    client_id = new_client(client, headers, "Dana")
    sold = sell(client, headers, client_id, plan.json()["id"])
    assert (sold["period_quota"], sold["period_unit"]) == (2, "week")

    first, second, third = week_of_sessions(client, studio, 3)
    one = book(client, headers, first, client_id).json()
    two = book(client, headers, second, client_id).json()
    over = book(client, headers, third, client_id).json()
    assert one["plan_name"] and two["plan_name"]
    assert over["plan_name"] is None  # the week's two visits are used; this one is a walk-in

    # Cancelling in time frees a place in the week again.
    set_status(client, headers, one["id"], "cancelled")
    other = book(
        client,
        headers,
        new_session(client, studio, 5, local_today() + timedelta(days=40)),
        client_id,
    ).json()
    assert other["plan_name"] is not None  # a different week


def test_quota_rules_for_plans(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    base = {"name": "X", "price_amount": 1, "validity_days": 30}
    for extra in (
        {"kind": "membership", "period_quota": 2},  # the unit is missing
        {"kind": "punch_card", "credits": 5, "period_quota": 2, "period_unit": "week"},
        {"kind": "membership", "period_quota": 0, "period_unit": "week"},
    ):
        assert client.post("/plans", json={**base, **extra}, headers=headers).status_code == 422
    plain = client.post("/plans", json={**base, "kind": "membership"}, headers=headers).json()
    assert plain["period_quota"] is None

    limited = client.patch(
        f"/plans/{plain['id']}", json={"period_quota": 3, "period_unit": "month"}, headers=headers
    )
    assert limited.json()["period_quota"] == 3
    only_one = client.patch(f"/plans/{plain['id']}", json={"period_quota": 3}, headers=headers)
    assert only_one.status_code == 422
    unlimited = client.patch(
        f"/plans/{plain['id']}", json={"period_quota": None, "period_unit": None}, headers=headers
    )
    assert unlimited.json()["period_quota"] is None
    punch = card(client, headers)
    nope = client.patch(
        f"/plans/{punch['id']}", json={"period_quota": 3, "period_unit": "week"}, headers=headers
    )
    assert nope.status_code == 409


def test_period_start_for_weeks_and_months(engine: Engine) -> None:
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT app.period_start(DATE '2026-10-21', 'week', 0),   -- Wednesday, Sunday start
                       app.period_start(DATE '2026-10-18', 'week', 0),   -- a Sunday
                       app.period_start(DATE '2026-10-18', 'week', 1),   -- a Sunday, Monday start
                       app.period_start(DATE '2026-10-31', 'month', 0)
            """)
        ).one()
    assert rows == (date(2026, 10, 18), date(2026, 10, 18), date(2026, 10, 12), date(2026, 10, 1))


def test_client_sees_terms_before_cancelling(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    week(client, headers)
    user = uuid4()
    joined = member(client, auth, studio, user)
    mine = auth(user, studio["tenant_id"])
    booking = book(
        client,
        headers,
        new_session(client, studio, 2, local_today() + timedelta(days=SOON)),
        joined["client_id"],
    ).json()

    text_ = client.get("/client/cancellation-policy", headers=mine).json()["text"]
    assert "1 week" not in text_["en"] and "7 days" in text_["en"]

    preview = client.get(f"/client/bookings/{booking['id']}/cancel-preview", headers=mine).json()
    assert preview["late"] is True and preview["outcome"] == "counts"
    assert preview["plan_name"] is not None

    listed = client.get("/client/bookings", headers=mine).json()
    assert listed[0]["free_cancel_until"] == preview["free_until"]

    policy(client, headers, group_minutes=0, personal_minutes=0, late_outcome="recorded")
    free = client.get(f"/client/bookings/{booking['id']}/cancel-preview", headers=mine).json()
    assert free["late"] is False and free["outcome"] == "free"

    week(client, headers)
    policy(client, headers, group_minutes=10080, personal_minutes=10080, late_outcome="recorded")
    noted = client.get(f"/client/bookings/{booking['id']}/cancel-preview", headers=mine).json()
    assert noted["outcome"] == "recorded"


def test_clients_cannot_read_other_businesses_or_edit(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    member(client, auth, studio, user)
    mine = auth(user, studio["tenant_id"])
    assert client.get(f"/client/bookings/{uuid4()}/cancel-preview", headers=mine).status_code == 404
    edit = client.put(
        "/cancellation-policy",
        json={"group_minutes": 0, "personal_minutes": 0, "resource_minutes": 0},
        headers=mine,
    )
    assert edit.status_code in (401, 403)


def test_no_show_limit_pauses_app_booking(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    policy(client, headers, no_show_limit=1)
    user = uuid4()
    joined = member(client, auth, studio, user)
    mine = auth(user, studio["tenant_id"])
    missed = book(client, headers, new_session(client, studio, 2), joined["client_id"]).json()
    set_status(client, headers, missed["id"], "no_show")
    with engine.begin() as connection:  # it happened yesterday
        connection.execute(
            text("""
                UPDATE app.sessions SET starts_at = now() - interval '1 day',
                                        ends_at = now() - interval '23 hours'
                WHERE id = (SELECT session_id FROM app.bookings WHERE id = :id)
            """),
            {"id": missed["id"]},
        )

    target = new_session(client, studio, 2, local_today() + timedelta(days=5))
    blocked = client.post(f"/client/sessions/{target}/bookings", headers=mine)
    assert blocked.status_code == 409 and blocked.json()["detail"] == "no_show_limit"
    assert book(client, headers, target, joined["client_id"]).status_code == 201  # staff still can

    policy(client, headers, no_show_limit=None)
    other = new_session(client, studio, 2, local_today() + timedelta(days=6))
    allowed = client.post(f"/client/sessions/{other}/bookings", headers=mine)
    assert allowed.status_code == 201, allowed.text
