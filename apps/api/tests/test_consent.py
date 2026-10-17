from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders
from tests.test_messaging import add_client, with_messaging


def token_of(engine: Engine, client_id: str) -> str:
    with engine.begin() as connection:
        return connection.execute(
            text("SELECT unsubscribe_token FROM app.clients WHERE id = :id"), {"id": client_id}
        ).scalar_one()


def events(engine: Engine, client_id: str) -> list[tuple[str, str]]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT action, source FROM app.consent_events WHERE client_id = :id "
                "ORDER BY created_at, id"
            ),
            {"id": client_id},
        )
        return [(r[0], r[1]) for r in rows]


def agree(client: TestClient, headers: dict, client_id: str, source: str = "desk_verbal") -> None:
    response = client.put(
        f"/clients/{client_id}/marketing-consent",
        json={"consent": True, "source": source},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_every_consent_change_is_kept_with_its_source(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    dana = add_client(client, headers, "Dana", "050-1111111")

    agree(client, headers, dana, "desk_signed")
    agree(client, headers, dana)  # no change: no new event
    withdrawn = client.put(
        f"/clients/{dana}/marketing-consent", json={"consent": False}, headers=headers
    )
    assert withdrawn.json()["marketing_consent"] is False

    assert events(engine, dana) == [("granted", "desk_signed"), ("withdrawn", "desk_other")]
    trail = client.get(f"/clients/{dana}/consent-events", headers=headers).json()
    assert [(e["action"], e["source"]) for e in trail] == [
        ("withdrawn", "desk_other"),
        ("granted", "desk_signed"),
    ]


def test_the_profile_toggle_records_the_app_as_source(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    dana = add_client(client, headers, "Dana", "050-1111111")
    with engine.begin() as connection:
        user = connection.execute(
            text("SELECT id FROM app.users ORDER BY created_at LIMIT 1")
        ).scalar_one()
        connection.execute(
            text("UPDATE app.clients SET user_id = :u WHERE id = :c"), {"u": user, "c": dana}
        )

    response = client.put(
        "/me/marketing-consent",
        json={"consent": True, "source": "app_join"},
        headers=auth(UUID(str(user))),
    )
    assert response.status_code == 204, response.text
    assert events(engine, dana) == [("granted", "app_join")]
    with engine.begin() as connection:
        mine = connection.execute(
            text(
                "SELECT action, source FROM app.consent_events "
                "WHERE user_id = :u AND client_id IS NULL"
            ),
            {"u": user},
        ).all()
    assert [tuple(r) for r in mine] == [("granted", "app_join")]


def test_an_ad_goes_only_to_clients_who_agreed_and_carries_the_opt_out(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    dana = add_client(client, headers, "Dana", "050-1111111")
    add_client(client, headers, "Noa", "050-2222222")
    agree(client, headers, dana)

    ad = {"audience": "active", "body": "Hi {first_name}", "promotional": True}
    preview = client.post("/messages/campaigns", json={**ad, "dry_run": True}, headers=headers)
    assert preview.json()["recipients"] == 1
    assert preview.json()["preview"].startswith("פרסומת: Hi Dana\n")
    assert f"/u/{token_of(engine, dana)}" in preview.json()["preview"]

    sent = client.post("/messages/campaigns", json=ad, headers=headers).json()
    log = client.get("/messages", params={"campaign_id": sent["id"]}, headers=headers).json()
    assert len(log) == 1 and f"/u/{token_of(engine, dana)}" in log[0]["body"]

    # A service message is sent to everyone, as is.
    service = client.post(
        "/messages/campaigns", json={**ad, "promotional": False, "dry_run": True}, headers=headers
    )
    assert service.json()["recipients"] == 2 and service.json()["preview"] == "Hi Dana"


def test_leads_never_get_an_ad(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers, "crm")
    lead = client.post(
        "/leads", json={"first_name": "Lia", "phone": "050-3333333"}, headers=headers
    )
    assert lead.status_code == 201, lead.text
    body = {"audience": "open_leads", "body": "Hi", "dry_run": True}
    assert client.post("/messages/campaigns", json=body, headers=headers).json()["recipients"] == 1
    ad = client.post("/messages/campaigns", json={**body, "promotional": True}, headers=headers)
    assert ad.json()["recipients"] == 0


def test_an_ad_too_long_for_the_opt_out_is_refused(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    add_client(client, headers, "Dana", "050-1111111")
    response = client.post(
        "/messages/campaigns",
        json={"audience": "active", "body": "x" * 950, "promotional": True},
        headers=headers,
    )
    assert response.status_code == 422 and response.json()["detail"] == "ad_too_long"


def test_the_opt_out_link_works_in_one_tap_and_is_recorded(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    with_messaging(client, headers)
    dana = add_client(client, headers, "Dana", "050-1111111")
    agree(client, headers, dana)
    token = token_of(engine, dana)

    page = client.get(f"/u/{token}")
    assert page.status_code == 200 and 'lang="he"' in page.text and 'lang="en"' in page.text
    assert events(engine, dana) == [("granted", "desk_verbal"), ("withdrawn", "unsubscribe_link")]
    after = client.get(f"/clients/{dana}", headers=headers).json()
    assert after["marketing_consent"] is False and after["marketing_opted_out_at"]

    ad = {"audience": "active", "body": "Hi", "promotional": True, "dry_run": True}
    assert client.post("/messages/campaigns", json=ad, headers=headers).json()["recipients"] == 0

    # The mail app's own button (POST) is fine twice; an unknown token changes nothing.
    assert client.post(f"/u/{token}").status_code == 204
    assert client.get("/u/not-a-real-token-123").status_code == 400
    assert client.get("/u/x").status_code == 400

    # Agreeing again at the desk clears the opt-out.
    agree(client, headers, dana)
    assert client.post("/messages/campaigns", json=ad, headers=headers).json()["recipients"] == 1


def test_opting_out_affects_only_that_business(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    dana = add_client(client, headers, "Dana", "050-1111111")
    agree(client, headers, dana)
    other = add_client(client, headers, "Noa", "050-2222222")
    agree(client, headers, other)
    client.get(f"/u/{token_of(engine, dana)}")
    still = client.get(f"/clients/{other}", headers=headers).json()
    assert still["marketing_consent"] is True


def test_the_trail_is_private_to_the_business(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    dana = add_client(client, studio["headers"], "Dana", None)
    agree(client, studio["headers"], dana)
    with engine.connect() as connection:
        connection.execute(text("SET ROLE app_api"))
        visible = connection.execute(text("SELECT count(*) FROM app.consent_events")).scalar_one()
    assert visible == 0  # no business is set on this connection
