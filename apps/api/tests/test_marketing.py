from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, make_staff

LEAD = {
    "name": "Dana Levi",
    "email": "Dana@Example.com",
    "phone": "050-1234567",
    "business": "Dana Hair",
    "vertical": "beauty",
    "message": "Interested in the client app",
    "locale": "en",
}


def test_public_pricing_needs_no_sign_in(client: TestClient) -> None:
    response = client.get("/public/pricing", params={"currency": "ILS"})

    assert response.status_code == 200
    catalog = response.json()
    assert catalog["currency"] == "ILS" and catalog["core"][0]["price"] > 0
    assert {m["key"] for m in catalog["modules"]} >= {"client_app", "ai_basic"}


def test_contact_requests_reach_platform_admins_only(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    sent = client.post("/public/contact", json=LEAD)
    bot = client.post("/public/contact", json={**LEAD, "name": "Bot", "website": "spam.example"})

    assert sent.status_code == 202, sent.text
    assert bot.status_code == 202  # accepted quietly, not stored
    user = uuid4()
    client.get("/me", headers=auth(user))
    assert client.get("/platform/contact-requests", headers=auth(user)).status_code == 403
    make_staff(engine, user, "employee", ("inbox.manage",))
    requests = client.get("/platform/contact-requests", headers=auth(user)).json()
    assert [(r["name"], r["email"], r["vertical"]) for r in requests] == [
        ("Dana Levi", "dana@example.com", "beauty")
    ]


def test_contact_form_is_rate_limited_and_validated(client: TestClient) -> None:
    for _ in range(3):
        assert client.post("/public/contact", json=LEAD).status_code == 202
    limited = client.post("/public/contact", json=LEAD)
    invalid = client.post("/public/contact", json={**LEAD, "email": "not-an-email"})

    assert limited.status_code == 429
    assert limited.json()["detail"] == "too_many_requests"
    assert invalid.status_code == 422
