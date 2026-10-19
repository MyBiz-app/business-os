"""The console's read-only catalog and price list (K5)."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.commerce.modules import MODULES
from tests.conftest import AuthHeaders, make_staff


def test_catalog_is_for_the_team_only(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    assert client.get("/platform/catalog", headers=studio["headers"]).status_code == 403
    member = uuid4()
    make_staff(engine, member, "employee", ())
    assert client.get("/platform/catalog", headers=auth(member)).status_code == 200


def test_catalog_lists_modules_and_prices_from_code(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    member = uuid4()
    make_staff(engine, member, "employee", ())
    board = client.get("/platform/catalog", headers=auth(member)).json()
    assert {m["key"] for m in board["modules"]} == set(MODULES)
    crm = next(m for m in board["modules"] if m["key"] == "crm")
    assert crm["prices"] == MODULES["crm"].prices
    assert board["core"][0]["up_to_clients"] == 100
    assert {"fitness", "beauty"} <= {i["key"] for i in board["industries"]}
    assert all(i["requests"] is None for i in board["industries"])  # no inbox permission


def test_request_counts_need_the_inbox_permission(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    with engine.begin() as connection:
        for n in range(2):
            connection.execute(
                text("""
                    INSERT INTO app.contact_requests (name, email, vertical, locale)
                    VALUES (:name, 'x@example.com', 'beauty', 'en')
                """),
                {"name": f"Visitor {n}"},
            )
    reader = uuid4()
    make_staff(engine, reader, "employee", ("inbox.manage",))
    board = client.get("/platform/catalog", headers=auth(reader)).json()
    counts = {i["key"]: i["requests"] for i in board["industries"]}
    assert counts["beauty"] >= 2 and counts["fitness"] >= 0
