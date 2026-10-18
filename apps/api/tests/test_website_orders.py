"""MyBiz Sites (R24): the brief, the order's journey, the console board, files and visits."""

import io
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.websites.brief import Brief, missing_for_submit
from app.websites.pricing import price_for
from app.websites.prompt import build_prompt
from tests.conftest import AuthHeaders, add_member, make_staff

VISIT_ID = "-".join(["visit", "id", "for", "tests"])

FULL = {
    "goals": ["leads", "bookings"],
    "main_action": "Book a free trial",
    "unique": "A small studio with personal training",
    "sections": ["hero", "services", "booking", "contact"],
    "style": "warm",
    "motion": "subtle",
    "copy_by": "you",
    "domain": "temporary",
    "languages": ["he"],
    "inspiration": [{"url": "https://example.com/site", "likes": "the colors"}],
}


def console(client: TestClient, engine: Engine, auth: AuthHeaders):
    admin = uuid4()
    make_staff(engine, admin)
    return auth(admin)


def test_the_brief_is_a_draft_until_it_is_sent(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    empty = client.get("/website/order", headers=headers).json()
    assert empty["order"] is None and "goals" in empty["missing"]
    assert empty["price"] == {
        "product": "landing_with_system",
        "currency": "ILS",
        "setup": 49000,
        "monthly": 2900,
    }

    partial = client.put("/website/order", json={"brief": {"goals": ["leads"]}}, headers=headers)
    assert partial.status_code == 200 and partial.json()["order"]["stage"] == "briefing"
    early = client.post("/website/order/submit", headers=headers)
    assert early.status_code == 422 and early.json()["detail"] == "brief_incomplete"

    saved = client.put("/website/order", json={"brief": FULL}, headers=headers).json()
    assert saved["missing"] == [] and saved["order"]["brief"]["style"] == "warm"
    sent = client.post("/website/order/submit", headers=headers).json()["order"]
    assert sent["stage"] == "received" and sent["setup_price"] == 49000
    # Until building starts the brief can still change.
    again = client.put(
        "/website/order", json={"brief": {**FULL, "style": "clean"}}, headers=headers
    )
    assert again.status_code == 200 and again.json()["order"]["brief"]["style"] == "clean"


def test_a_brief_rejects_what_the_wizard_never_sends(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    for bad in (
        {"style": "neon"},
        {"colors": ["red"]},
        {"surprise": 1},
        {"inspiration": [{"url": "x"}]},
    ):
        response = client.put("/website/order", json={"brief": bad}, headers=headers)
        assert response.status_code == 422


def test_booking_needs_the_system() -> None:
    brief = Brief.model_validate({**FULL, "sections": ["booking"]})
    assert missing_for_submit(brief, with_system=True) == []
    assert missing_for_submit(brief, with_system=False) == ["booking_needs_system"]


def test_only_owners_order_a_site(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    headers = auth(desk, studio["tenant_id"])
    assert client.get("/website/order", headers=headers).status_code == 403
    assert client.put("/website/order", json={"brief": {}}, headers=headers).status_code == 403


def test_another_business_sees_nothing(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    client.put("/website/order", json={"brief": FULL}, headers=studio["headers"])
    owner = uuid4()
    created = client.post(
        "/tenants",
        json={
            "name": "Other",
            "vertical": "fitness",
            "locale": "he",
            "time_zone": "Asia/Jerusalem",
            "currency": "ILS",
        },
        headers=auth(owner),
    ).json()
    theirs = client.get("/website/order", headers=auth(owner, created["id"])).json()
    assert theirs["order"] is None


def test_the_order_goes_through_the_board_to_live(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    staff = console(client, engine, auth)
    # A brief still being written is not on the board work yet.
    client.put("/website/order", json={"brief": FULL}, headers=headers)
    order = client.get("/platform/website-orders", headers=staff).json()[0]
    assert order["stage"] == "briefing" and order["tenant_name"] == "Studio Flow"
    blocked = client.patch(
        f"/platform/website-orders/{order['id']}", json={"stage": "building"}, headers=staff
    )
    assert blocked.status_code == 422 and blocked.json()["detail"] == "not_submitted"

    client.post("/website/order/submit", headers=headers)
    board = client.get("/platform/website-orders", headers=staff).json()
    assert board[0]["stage"] == "received"
    assert "# Build a landing page" in board[0]["prompt"]
    assert "Studio Flow" in board[0]["prompt"] and "Book a free trial" in board[0]["prompt"]
    assert "Israeli Standard 5568" in board[0]["prompt"]
    oid = board[0]["id"]

    moved = client.patch(
        f"/platform/website-orders/{oid}",
        json={"stage": "building", "notes": "Started with Claude Code"},
        headers=staff,
    ).json()
    assert (
        moved[0]["stage"] == "building" and moved[0]["internal_notes"] == "Started with Claude Code"
    )
    locked = client.put("/website/order", json={"brief": FULL}, headers=headers)
    assert locked.status_code == 409 and locked.json()["detail"] == "locked"

    client.patch(
        f"/platform/website-orders/{oid}",
        json={"stage": "review", "message": "Ready to look at"},
        headers=staff,
    )
    state = client.get("/website/order", headers=headers).json()["order"]
    assert state["stage"] == "review" and state["customer_message"] == "Ready to look at"
    nothing = client.post("/website/order/respond", json={"action": "changes"}, headers=headers)
    assert nothing.status_code == 422
    changes = client.post(
        "/website/order/respond",
        json={"action": "changes", "message": "Bigger logo"},
        headers=headers,
    ).json()["order"]
    assert changes["stage"] == "building" and changes["change_request"] == "Bigger logo"
    assert (
        client.get("/platform/website-orders", headers=staff).json()[0]["change_request"]
        == "Bigger logo"
    )

    client.patch(f"/platform/website-orders/{oid}", json={"stage": "review"}, headers=staff)
    approved = client.post("/website/order/respond", json={"action": "approve"}, headers=headers)
    assert approved.json()["order"]["approved_at"] is not None

    no_address = client.patch(
        f"/platform/website-orders/{oid}", json={"stage": "live"}, headers=staff
    )
    assert no_address.status_code == 422 and no_address.json()["detail"] == "site_url_required"
    live = client.patch(
        f"/platform/website-orders/{oid}",
        json={"stage": "live", "site_url": "https://studio.example.com"},
        headers=staff,
    ).json()
    assert live[0]["stage"] == "live" and live[0]["live_at"] is not None
    # The business now has the address (R22).
    with engine.begin() as connection:
        url = connection.execute(
            text("SELECT website_url FROM app.tenants WHERE id = :t"), {"t": studio["tenant_id"]}
        ).scalar_one()
    assert url == "https://studio.example.com"


def test_the_console_board_is_for_the_team(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    assert client.get("/platform/website-orders", headers=studio["headers"]).status_code == 403
    reader = uuid4()
    make_staff(engine, reader, "employee", ("businesses.read",))
    assert client.get("/platform/website-orders", headers=auth(reader)).status_code == 403


def test_visits_are_counted_only_for_live_sites(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    staff = console(client, engine, auth)
    client.put("/website/order", json={"brief": FULL}, headers=headers)
    client.post("/website/order/submit", headers=headers)
    with engine.begin() as connection:
        key = connection.execute(text("SELECT tracking_key FROM app.website_orders")).scalar_one()
    visit = {"key": key, "source": "search"}
    assert client.post("/public/website-visits", json=visit).status_code == 202
    with engine.begin() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM app.website_visits_daily")).scalar_one()
            == 0
        )

    oid = client.get("/platform/website-orders", headers=staff).json()[0]["id"]
    client.patch(
        f"/platform/website-orders/{oid}",
        json={"stage": "live", "site_url": "https://studio.example.com"},
        headers=staff,
    )
    for _ in range(2):
        client.post("/public/website-visits", json=visit)
    client.post("/public/website-visits", json={"key": "0" * 24, "source": "direct"})
    with engine.begin() as connection:
        rows = connection.execute(text("SELECT source, visits FROM app.website_visits_daily")).all()
    assert rows == [("search", 2)]
    assert client.post("/public/website-visits", json={"key": "nope!"}).status_code == 422


def test_the_images_come_as_one_zip(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    staff = console(client, engine, auth)
    state = client.get("/website/order", headers=headers).json()
    uploaded = client.post(
        "/files",
        data={"folder_id": state["files_folder_id"]},
        files={"file": ("logo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]
    brief = {**FULL, "images": [{"file_id": file_id, "note": "Our studio"}]}
    client.put("/website/order", json={"brief": brief}, headers=headers)
    oid = client.get("/platform/website-orders", headers=staff).json()[0]["id"]
    response = client.get(f"/platform/website-orders/{oid}/files.zip", headers=staff)
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    assert zipfile.ZipFile(io.BytesIO(response.content)).namelist() == ["logo.png"]


def test_the_prompt_carries_the_owner_words_and_the_hooks() -> None:
    brief = Brief.model_validate(FULL).model_dump(mode="json")
    prompt = build_prompt(
        brief=brief,
        snapshot={
            "business": {
                "name": "Studio Flow",
                "vertical": "fitness",
                "join_code": "ABC123",
                "primary_color": "#112233",
            },
            "branches": [{"name": "Main", "address": "Herzl 1"}],
            "services": [{"name": "Pilates", "price": "60", "currency": "ILS"}],
        },
        tracking_key=VISIT_ID,
        api_url="https://api.example.com/",
        with_system=True,
    )
    assert "A small studio with personal training" in prompt
    assert "POST https://api.example.com/public/businesses/ABC123/inquiries" in prompt
    assert "https://api.example.com/public/website-visits" in prompt and VISIT_ID in prompt
    assert "Pilates: 60 ILS" in prompt and "Herzl 1" in prompt


def test_the_public_price_list_is_the_orders_price_list(client: TestClient) -> None:
    for currency in ("ILS", "USD", "EUR"):
        body = client.get("/public/website-prices", params={"currency": currency}).json()
        assert body["currency"] == currency
        for product in ("landing_only", "landing_with_system"):
            setup, monthly = price_for(product, currency)
            assert body[product] == {"setup": setup, "monthly": monthly}
    # An unknown currency falls back to USD, like the orders.
    assert (
        client.get("/public/website-prices", params={"currency": "JPY"}).json()["currency"] == "USD"
    )
