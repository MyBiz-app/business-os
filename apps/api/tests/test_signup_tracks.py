"""Sign-up tracks and business size (R25a): "website only" businesses, the account check and the
brief that starts filled in."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders


def create(client: TestClient, auth: AuthHeaders, **extra: object) -> tuple[dict, dict]:
    owner = uuid4()
    tenant = client.post("/tenants", json={**STUDIO, **extra}, headers=auth(owner)).json()
    return tenant, auth(owner, tenant["id"])


def test_business_size_and_track_are_kept(client: TestClient, auth: AuthHeaders) -> None:
    tenant, headers = create(client, auth, business_size="small")
    assert tenant["business_size"] == "small" and tenant["product_track"] == "full"
    # The size can change later ("I grew"); the track only through adding the system.
    grown = client.patch("/tenants/current", json={"business_size": "medium"}, headers=headers)
    assert grown.json()["business_size"] == "medium"
    bad = client.post("/tenants", json={**STUDIO, "business_size": "huge"}, headers=auth(uuid4()))
    assert bad.status_code == 422
    # Older sign-ups never gave a size.
    plain, _ = create(client, auth)
    assert plain["business_size"] is None


def test_website_only_business_has_no_modules_and_the_stand_alone_price(
    client: TestClient, auth: AuthHeaders
) -> None:
    tenant, headers = create(client, auth, product_track="website_only", business_size="solo")
    assert tenant["product_track"] == "website_only"
    assert client.get("/tenants/current/modules", headers=headers).json()["modules"] == {}
    state = client.get("/website/order", headers=headers).json()
    assert state["with_system"] is False
    assert state["price"] == {
        "product": "landing_only",
        "currency": "ILS",
        "setup": 79000,
        "monthly": 4900,
    }
    # Booking needs the system.
    assert "booking" not in state["prefill"]["sections"]
    draft = {"brief": {"goals": ["leads"], "sections": ["hero", "booking"]}}
    saved = client.put("/website/order", json=draft, headers=headers).json()
    assert "booking_needs_system" in saved["missing"]


def test_adding_the_system_needs_no_new_sign_up(client: TestClient, auth: AuthHeaders) -> None:
    _, headers = create(client, auth, product_track="website_only")
    added = client.post("/website/add-system", headers=headers)
    assert added.status_code == 200 and added.json()["with_system"] is True
    assert added.json()["price"]["product"] == "landing_with_system"
    assert client.get("/tenants/current", headers=headers).json()["product_track"] == "full"
    assert client.get("/tenants/current/modules", headers=headers).json()["modules"] != {}
    again = client.post("/website/add-system", headers=headers)
    assert again.status_code == 409 and again.json()["detail"] == "already_has_system"


def test_the_brief_starts_with_what_is_known(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    client.patch(
        "/tenants/current",
        json={"website_url": "https://studio.example.com/home", "primary_color": "#2563EB"},
        headers=headers,
    )
    prefill = client.get("/website/order", headers=headers).json()["prefill"]
    assert prefill["sections"][0] == "hero" and "services" in prefill["sections"]
    assert "booking" in prefill["sections"] and "bookings" in prefill["goals"]
    assert prefill["languages"] == ["he"] and prefill["colors"] == ["#2563EB"]
    assert prefill["domain"] == "have" and prefill["domain_name"] == "studio.example.com"


def test_account_check_says_yes_or_no_and_is_rate_limited(
    client: TestClient, engine: Engine
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'Dana@Example.com')"),
            {"id": uuid4()},
        )
    ask = lambda email: client.post("/public/accounts/exists", json={"email": email})  # noqa: E731
    assert ask("dana@example.com").json() == {"exists": True}
    assert ask("nobody@example.com").json() == {"exists": False}
    assert ask("not an email").status_code == 422
