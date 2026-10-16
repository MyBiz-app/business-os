"""Contact emails of a business and its branches: fallbacks, confirmation, use when sending."""

from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.messaging.contact_emails import confirm_token, resolve_email, resolve_email_with_source
from app.messaging.email import Email, LogSender, ResendSender, SmtpSender
from app.messaging.roster import notify_roster
from tests.conftest import AuthHeaders
from tests.test_push import seed_published_shift


def put(client: TestClient, studio: dict, purpose: str, email: str, location: str | None = None):
    params = {"location_id": location} if location else {}
    return client.put(
        f"/contact-emails/{purpose}",
        json={"email": email},
        params=params,
        headers=studio["headers"],
    )


def verify_link(client: TestClient, tenant: str, row: UUID, email: str) -> str:
    token = confirm_token(UUID(tenant), row, email)
    response = client.get(
        "/public/contact-emails/confirm", params={"token": token}, follow_redirects=False
    )
    assert response.status_code in (302, 307)
    return parse_qs(urlparse(response.headers["location"]).query)["status"][0]


def row_id(engine: Engine, email: str) -> UUID:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT id FROM app.contact_emails WHERE email = :e"), {"e": email}
        ).scalar_one()


def test_unset_purposes_use_the_owner_and_a_new_address_waits_for_confirmation(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    tenant = studio["headers"]["X-Tenant-Id"]
    start = client.get("/contact-emails", headers=studio["headers"]).json()
    assert {p["purpose"] for p in start["purposes"]} == {
        "main",
        "inbox",
        "billing",
        "reply_to",
        "notifications",
    }
    assert all(p["email"] is None and p["effective_source"] == "owner" for p in start["purposes"])

    saved = put(client, studio, "inbox", "Hello@Example.com")
    assert saved.status_code == 200
    inbox = next(p for p in saved.json()["purposes"] if p["purpose"] == "inbox")
    assert inbox["email"] == "hello@example.com" and inbox["verified"] is False
    # Unconfirmed addresses are never used.
    assert inbox["effective_source"] == "owner"

    assert (
        verify_link(client, tenant, row_id(engine, "hello@example.com"), "hello@example.com")
        == "ok"
    )
    after = client.get("/contact-emails", headers=studio["headers"]).json()
    inbox = next(p for p in after["purposes"] if p["purpose"] == "inbox")
    reply = next(p for p in after["purposes"] if p["purpose"] == "reply_to")
    assert inbox["verified"] and inbox["effective_email"] == "hello@example.com"
    # reply_to is not set, so it falls back to the inquiries address.
    assert reply["effective_email"] == "hello@example.com"
    assert reply["effective_source"] == "business"


def test_a_changed_address_invalidates_the_old_link_and_a_forged_one_fails(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    tenant = studio["headers"]["X-Tenant-Id"]
    put(client, studio, "main", "a@example.com")
    old = row_id(engine, "a@example.com")
    put(client, studio, "main", "b@example.com")
    assert verify_link(client, tenant, old, "a@example.com") == "invalid"
    assert verify_link(client, tenant, old, "b@example.com") == "ok"
    bad = client.get(
        "/public/contact-emails/confirm", params={"token": "nonsense"}, follow_redirects=False
    )
    assert "status=invalid" in bad.headers["location"]


def test_the_owners_own_email_needs_no_confirmation(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    with engine.connect() as connection:
        owner = connection.execute(text("SELECT email FROM app.users LIMIT 1")).scalar_one()
    saved = put(client, studio, "billing", owner.upper()).json()
    billing = next(p for p in saved["purposes"] if p["purpose"] == "billing")
    assert billing["verified"] is True and billing["effective_email"] == owner


def test_a_branch_uses_its_own_address_else_the_businesss(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    tenant = studio["headers"]["X-Tenant-Id"]
    main = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=studio["headers"]).json()[
        "id"
    ]
    put(client, studio, "main", "hq@example.com")
    verify_link(client, tenant, row_id(engine, "hq@example.com"), "hq@example.com")
    put(client, studio, "reply_to", "south@example.com", south)
    verify_link(client, tenant, row_id(engine, "south@example.com"), "south@example.com")

    with engine.connect() as connection:
        t = UUID(tenant)
        assert resolve_email_with_source(connection, t, "reply_to", UUID(south)) == (
            "south@example.com",
            "branch",
        )
        # The main branch set nothing: it inherits the business's.
        assert resolve_email_with_source(connection, t, "reply_to", UUID(main)) == (
            "hq@example.com",
            "business",
        )
        assert resolve_email(connection, t, "reply_to") == "hq@example.com"

    view = client.get("/contact-emails", params={"location_id": south}, headers=studio["headers"])
    reply = next(p for p in view.json()["purposes"] if p["purpose"] == "reply_to")
    assert reply["email"] == "south@example.com" and reply["effective_source"] == "branch"
    inbox = next(p for p in view.json()["purposes"] if p["purpose"] == "inbox")
    assert inbox["email"] is None and inbox["effective_email"] == "hq@example.com"
    assert inbox["effective_source"] == "business"

    assert (
        client.delete(
            "/contact-emails/reply_to", params={"location_id": south}, headers=studio["headers"]
        ).status_code
        == 204
    )
    with engine.connect() as connection:
        assert resolve_email(connection, UUID(tenant), "reply_to", UUID(south)) == "hq@example.com"


def test_emails_of_other_businesses_branches_and_roles_are_off_limits(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    other_owner = uuid4()
    other = client.post(
        "/tenants",
        json={
            "name": "Other",
            "vertical": "fitness",
            "locale": "en",
            "time_zone": "UTC",
            "currency": "USD",
        },
        headers=auth(other_owner),
    ).json()
    theirs = client.get("/locations", headers=auth(other_owner, other["id"])).json()[0]["id"]
    assert put(client, studio, "main", "x@example.com", theirs).status_code == 404

    stranger = auth(uuid4(), studio["headers"]["X-Tenant-Id"])
    assert client.get("/contact-emails", headers=stranger).status_code in (403, 404)
    assert put(client, studio, "main", "not-an-email").status_code == 422


def test_senders_put_the_business_name_and_reply_to_on_the_message() -> None:
    email = Email(
        to="client@example.com",
        subject="Hi",
        text="Hello",
        reply_to="hq@example.com",
        from_name="Studio Flow",
    )
    smtp = SmtpSender("h", 465, "u", "p", "MyBiz <no-reply@example.com>").message(email)
    assert smtp["Reply-To"] == "hq@example.com"
    assert smtp["From"] == "Studio Flow <no-reply@example.com>"
    plain = SmtpSender("h", 465, "u", "p", "MyBiz <no-reply@example.com>").message(
        Email(to="c@example.com", subject="s", text="t")
    )
    assert plain["From"] == "MyBiz <no-reply@example.com>" and plain["Reply-To"] is None
    assert ResendSender("key", "MyBiz <no-reply@example.com>").sender.endswith(
        "<no-reply@example.com>"
    )


def test_the_roster_email_replies_to_the_branch(engine: Engine) -> None:
    seed_published_shift(engine, with_token=False, email="d@example.com")
    with engine.begin() as c:
        c.execute(text("SELECT set_config('app.bypass_rls', 'on', true)"))
        c.execute(
            text("""
                INSERT INTO app.contact_emails
                    (tenant_id, location_id, purpose, email, verified_at)
                SELECT tenant_id, id, 'reply_to', 'branch@example.com', now()
                FROM app.locations WHERE name = 'Main'
            """)
        )
    sender = LogSender()
    with engine.begin() as c:
        notify_roster(c, sender)
    [email] = sender.sent
    assert email.reply_to == "branch@example.com"
    assert email.from_name and email.from_name.startswith("Biz")


def test_clients_see_only_a_confirmed_main_email_never_the_owners(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    from tests.test_client_app import join, join_code

    user = uuid4()
    join(client, auth, user, join_code(client, studio))
    headers = auth(user, studio["tenant_id"])
    assert client.get("/client/locations", headers=headers).json()[0]["contact_email"] is None

    tenant = studio["headers"]["X-Tenant-Id"]
    put(client, studio, "main", "front@example.com")
    assert client.get("/client/locations", headers=headers).json()[0]["contact_email"] is None
    verify_link(client, tenant, row_id(engine, "front@example.com"), "front@example.com")
    assert (
        client.get("/client/locations", headers=headers).json()[0]["contact_email"]
        == "front@example.com"
    )
