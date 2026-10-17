"""A website for the business and for each branch (round 7, R22): validation, inheritance, and
where it shows (join page, client app, issued documents, AI context)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.assistant import _context_block
from app.core.website import normalize_website
from tests.conftest import AuthHeaders
from tests.test_client_app import join, join_code


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("example.com", "https://example.com"),
        ("  WWW.Example.COM/Menu  ", "https://www.example.com/Menu"),
        ("http://example.co.il/", "http://example.co.il"),
        ("https://example.com:8443/a?b=1", "https://example.com:8443/a?b=1"),
        ("אתר.co.il", "https://אתר.co.il"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_addresses_are_cleaned(typed: str | None, stored: str | None) -> None:
    assert normalize_website(typed) == stored


@pytest.mark.parametrize(
    "bad",
    [
        "javascript:alert(1)",
        "mailto:a@b.com",
        "ftp://example.com",
        "https://",
        "localhost",
        "not a site",
        "https://user:pw@example.com",
        "https://example.com:notaport",
        "https://" + "a" * 300 + ".com",
    ],
)
def test_other_things_are_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_website(bad)


def test_the_business_site_is_saved_cleared_and_validated(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    saved = client.patch(
        "/tenants/current", json={"website_url": "Studio.example"}, headers=headers
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["website_url"] == "https://studio.example"

    bad = client.patch(
        "/tenants/current", json={"website_url": "javascript:alert(1)"}, headers=headers
    )
    assert bad.status_code == 422
    assert client.get("/tenants/current", headers=headers).json()["website_url"] == (
        "https://studio.example"
    )

    cleared = client.patch("/tenants/current", json={"website_url": None}, headers=headers)
    assert cleared.json()["website_url"] is None


def test_a_branch_inherits_the_business_site_until_it_has_its_own(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    client.patch("/tenants/current", json={"website_url": "studio.example"}, headers=headers)
    created = client.post("/locations", json={"name": "Haifa"}, headers=headers)
    assert created.status_code == 201, created.text
    branch = created.json()
    assert (branch["website_url"], branch["effective_website_url"]) == (
        None,
        "https://studio.example",
    )

    own = client.patch(
        f"/locations/{branch['id']}", json={"website_url": "haifa.studio.example"}, headers=headers
    ).json()
    assert (own["website_url"], own["effective_website_url"]) == (
        "https://haifa.studio.example",
        "https://haifa.studio.example",
    )

    assert (
        client.patch(
            f"/locations/{branch['id']}", json={"website_url": "ftp://x.example"}, headers=headers
        ).status_code
        == 422
    )
    back = client.patch(f"/locations/{branch['id']}", json={"website_url": ""}, headers=headers)
    assert back.json()["website_url"] is None
    assert back.json()["effective_website_url"] == "https://studio.example"

    with_site = client.post(
        "/locations", json={"name": "Eilat", "website_url": "eilat.example"}, headers=headers
    ).json()
    assert with_site["website_url"] == "https://eilat.example"


def test_clients_see_the_site_before_and_after_joining(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    from uuid import uuid4

    headers = studio["headers"]
    client.patch("/tenants/current", json={"website_url": "studio.example"}, headers=headers)
    branch = client.post(
        "/locations", json={"name": "Haifa", "website_url": "haifa.example"}, headers=headers
    ).json()
    code = join_code(client, studio)

    assert client.get(f"/public/businesses/{code}").json()["website_url"] == (
        "https://studio.example"
    )

    user = uuid4()
    join(client, auth, user, code)
    mine = client.get("/client/businesses", headers=auth(user)).json()
    assert mine[0]["website_url"] == "https://studio.example"
    branches = {
        b["name"]: b["website_url"]
        for b in client.get("/client/locations", headers=auth(user, studio["tenant_id"])).json()
    }
    assert branches["Haifa"] == "https://haifa.example"
    assert all(url for url in branches.values())  # the others use the business's
    assert branch["id"]


def test_the_database_refuses_a_malformed_address(engine: Engine, studio: dict) -> None:
    with engine.begin() as connection, pytest.raises(Exception, match="website_url_check"):
        connection.execute(
            text("UPDATE app.tenants SET website_url = 'javascript:alert(1)' WHERE id = :id"),
            {"id": studio["tenant_id"]},
        )


def test_the_ai_context_names_the_site_only_when_there_is_one() -> None:
    from types import SimpleNamespace

    tenant = SimpleNamespace(role="owner")
    with_site = _context_block(tenant, "UTC", "Studio", "ILS", website="https://studio.example")  # type: ignore[arg-type]
    without = _context_block(tenant, "UTC", "Studio", "ILS")  # type: ignore[arg-type]
    assert "website: https://studio.example" in with_site["text"]
    assert "website" not in without["text"]
