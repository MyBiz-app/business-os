from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.identity import InvalidIdentity, check_digit_valid, normalize
from tests.conftest import STUDIO, AuthHeaders, add_member
from tests.test_bookings import new_client
from tests.test_client_app import join, join_code

VALID = "123456782"  # passes the Israeli check digit


@pytest.mark.parametrize(
    ("number", "ok"),
    [
        ("123456782", True),
        ("12345678", False),
        ("000000000", False),
        ("12345678a", False),
        ("1234567890", False),
        ("18", True),
    ],
)
def test_the_israeli_check_digit(number: str, ok: bool) -> None:
    assert check_digit_valid(number) is ok


def test_normalising_pads_and_validates() -> None:
    assert normalize("il_id", "12-345-6782 ", None) == ("123456782", "IL")
    assert normalize("il_id", "18", None) == ("000000018", "IL")
    assert normalize("passport", "ab 123456", "us") == ("AB123456", "US")
    for id_type, number, country in [
        ("il_id", "123456789", None),
        ("passport", "AB123456", None),
        ("passport", "A1", "US"),
        ("bogus", "123456782", None),
    ]:
        with pytest.raises(InvalidIdentity):
            normalize(id_type, number, country)


def test_a_member_id_is_stored_masked_and_revealed_only_to_owners(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    headers, coach = studio["headers"], studio["coach"]
    body = {"id_type": "il_id", "number": VALID}

    absent = client.get(f"/staff/{coach}/identity", headers=headers).json()
    assert absent["present"] is False

    saved = client.put(f"/staff/{coach}/identity", json=body, headers=headers)
    assert saved.status_code == 200
    assert saved.json() == {
        "present": True,
        "id_type": "il_id",
        "country": "IL",
        "last4": "6782",
        "can_reveal": True,
    }
    assert VALID not in saved.text

    # Stored encrypted, never as text.
    with engine.begin() as connection:
        stored = connection.execute(
            text("SELECT id_number_encrypted, id_hash FROM app.person_identities")
        ).one()
    assert VALID.encode() not in bytes(stored[0]) and VALID not in stored[1]

    revealed = client.post(f"/staff/{coach}/identity/reveal", headers=headers)
    assert revealed.json() == {"number": VALID}
    with engine.begin() as connection:
        actions = (
            connection.execute(
                text("SELECT action FROM app.audit_log WHERE action LIKE 'identity.%' ORDER BY id")
            )
            .scalars()
            .all()
        )
    assert actions == ["identity.set", "identity.revealed"]

    # A manager sees the last four only and cannot reveal.
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    manager_headers = auth(manager, studio["tenant_id"])
    seen = client.get(f"/staff/{coach}/identity", headers=manager_headers).json()
    assert seen["last4"] == "6782" and seen["can_reveal"] is False
    assert (
        client.post(f"/staff/{coach}/identity/reveal", headers=manager_headers).status_code == 403
    )

    assert client.delete(f"/staff/{coach}/identity", headers=headers).status_code == 204
    assert client.get(f"/staff/{coach}/identity", headers=headers).json()["present"] is False


def test_a_bad_or_duplicate_number_is_refused(
    client: TestClient, engine: Engine, studio: dict
) -> None:
    headers, coach = studio["headers"], studio["coach"]
    bad = client.put(
        f"/staff/{coach}/identity",
        json={"id_type": "il_id", "number": "123456789"},
        headers=headers,
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "invalid_id_number"
    no_country = client.put(
        f"/staff/{coach}/identity",
        json={"id_type": "passport", "number": "AB123456"},
        headers=headers,
    )
    assert no_country.json()["detail"] == "invalid_id_country"

    other = uuid4()
    add_member(engine, studio["tenant_id"], other, "staff")
    body = {"id_type": "il_id", "number": VALID}
    assert client.put(f"/staff/{coach}/identity", json=body, headers=headers).status_code == 200
    clash = client.put(f"/staff/{other}/identity", json=body, headers=headers)
    assert clash.status_code == 409 and clash.json()["detail"] == "id_number_in_use"
    # The same number replaced on the same person is fine.
    assert client.put(f"/staff/{coach}/identity", json=body, headers=headers).status_code == 200


def test_a_member_keeps_their_own_id(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    coach_headers = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/me/identity", headers=coach_headers).json()["present"] is False
    body = {"id_type": "passport", "number": "x1234567", "country": "fr"}
    saved = client.put("/me/identity", json=body, headers=coach_headers).json()
    assert saved["last4"] == "4567" and saved["country"] == "FR"
    assert client.post("/me/identity/reveal", headers=coach_headers).json() == {
        "number": "X1234567"
    }
    # A plain team member cannot read someone else's.
    owner = studio["owner"]
    assert client.get(f"/staff/{owner}/identity", headers=coach_headers).status_code == 403


def test_clients_are_asked_only_when_the_business_turns_it_on(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    client_id = new_client(client, headers, "Dana")
    body = {"id_type": "il_id", "number": VALID}

    assert client.get(f"/clients/{client_id}/identity", headers=headers).json()["mode"] == "off"
    refused = client.put(f"/clients/{client_id}/identity", json=body, headers=headers)
    assert refused.status_code == 409 and refused.json()["detail"] == "client_id_off"

    on = client.patch("/tenants/current", json={"client_id_number": "optional"}, headers=headers)
    assert on.json()["client_id_number"] == "optional"
    saved = client.put(f"/clients/{client_id}/identity", json=body, headers=headers).json()
    assert saved["last4"] == "6782" and saved["mode"] == "optional"
    assert client.post(f"/clients/{client_id}/identity/reveal", headers=headers).json() == {
        "number": VALID
    }

    # Erasing the client removes the number.
    client.post(f"/clients/{client_id}/erase", json={"confirm": True}, headers=headers)
    assert client.get(f"/clients/{client_id}/identity", headers=headers).json()["present"] is False


def test_a_client_manages_their_own_id_in_the_app(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    joiner = uuid4()
    join(client, auth, joiner, join_code(client, studio))
    app_headers = auth(joiner, studio["tenant_id"])
    body = {"id_type": "il_id", "number": VALID}

    assert client.get("/client/identity", headers=app_headers).json()["mode"] == "off"
    assert client.put("/client/identity", json=body, headers=app_headers).status_code == 409
    client.patch("/tenants/current", json={"client_id_number": "required"}, headers=headers)
    saved = client.put("/client/identity", json=body, headers=app_headers)
    assert saved.status_code == 200 and saved.json()["last4"] == "6782"
    assert client.post("/client/identity/reveal", headers=app_headers).json() == {"number": VALID}
    assert client.delete("/client/identity", headers=app_headers).status_code == 204


def test_ids_are_isolated_between_businesses(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    owner2 = uuid4()
    tenant2 = client.post("/tenants", json=STUDIO, headers=auth(owner2)).json()["id"]
    h2 = auth(owner2, tenant2)
    client.put("/me/identity", json={"id_type": "il_id", "number": VALID}, headers=h2)
    # The first business's owner has no ID of their own just because another business has this one.
    assert client.get("/me/identity", headers=studio["headers"]).json()["present"] is False
    # And the same number can be filed in two businesses.
    saved = client.put(
        "/me/identity", json={"id_type": "il_id", "number": VALID}, headers=studio["headers"]
    )
    assert saved.status_code == 200
