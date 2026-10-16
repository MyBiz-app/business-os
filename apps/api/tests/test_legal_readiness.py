"""Legal readiness (round 6, K2): address, employer file, optional licence with a reminder,
and what each piece unlocks. Nothing here blocks the product."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.legal_readiness import evaluate
from tests.conftest import AuthHeaders, local_today


def readiness(client: TestClient, headers) -> dict:
    response = client.get("/tenants/current/readiness", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def done(card: dict) -> dict[str, bool]:
    return {item["key"]: item["done"] for item in card["items"]}


def test_the_card_shows_what_each_missing_piece_unlocks(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers = studio["headers"]
    card = readiness(client, headers)
    assert not any(done(card).values())
    assert (card["tax_invoice"], card["payroll"]) == (False, False)

    client.patch(
        "/tenants/current",
        json={"legal_entity_type": "licensed_dealer", "business_number": "000000018"},
        headers=headers,
    )
    card = readiness(client, headers)
    assert done(card)["entity_type"] and done(card)["business_number"]
    assert card["tax_invoice"] is False  # the address is still missing

    tenant = client.patch(
        "/tenants/current",
        json={"address_line": " 12 Herzl St ", "address_city": "Holon"},
        headers=headers,
    ).json()
    assert tenant["address_line"] == "12 Herzl St"
    card = readiness(client, headers)
    assert (card["tax_invoice"], card["payroll"]) == (True, False)

    client.patch("/tenants/current", json={"employer_file_number": "940123456"}, headers=headers)
    assert readiness(client, headers)["payroll"] is True


def test_an_exempt_dealer_gets_receipts_only(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    client.patch(
        "/tenants/current",
        json={
            "legal_entity_type": "exempt_dealer",
            "business_number": "000000018",
            "address_line": "1 Main St",
            "address_city": "Haifa",
        },
        headers=headers,
    )
    card = readiness(client, headers)
    assert (card["receipts_only"], card["tax_invoice"]) == (True, False)


def test_a_company_number_off_the_51_prefix_is_a_warning_not_a_block(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    saved = client.patch(
        "/tenants/current",
        json={"legal_entity_type": "company", "business_number": "000000018"},
        headers=headers,
    )
    assert saved.status_code == 200
    number = next(i for i in readiness(client, headers)["items"] if i["key"] == "business_number")
    assert number["done"] and number["warning"] == "company_prefix"
    client.patch("/tenants/current", json={"business_number": "515555555"}, headers=headers)
    number = next(i for i in readiness(client, headers)["items"] if i["key"] == "business_number")
    assert number["warning"] is None


def test_the_licence_is_optional_and_reminded_sixty_days_ahead(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    assert readiness(client, headers)["license_status"] == "none"
    assert "license_expiring" not in {e["kind"] for e in client.get("/attention", headers=headers).json()}

    def set_expiry(days: int) -> None:
        client.patch(
            "/tenants/current",
            json={
                "business_license_number": "L-77",
                "business_license_expires_on": (local_today() + timedelta(days=days)).isoformat(),
            },
            headers=headers,
        )

    set_expiry(200)
    assert readiness(client, headers)["license_status"] == "valid"
    set_expiry(30)
    card = readiness(client, headers)
    assert (card["license_status"], card["license_days_left"]) == ("expiring", 30)
    lists = {e["kind"]: e for e in client.get("/attention", headers=headers).json()}
    assert lists["license_expiring"]["count"] == 1
    set_expiry(-3)
    assert readiness(client, headers)["license_status"] == "expired"
    # Clearing the licence removes the reminder.
    client.patch(
        "/tenants/current",
        json={"business_license_number": None, "business_license_expires_on": None},
        headers=headers,
    )
    assert readiness(client, headers)["license_status"] == "none"


def test_only_settings_managers_see_these_details(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    client.patch(
        "/tenants/current", json={"address_line": "1 Main St"}, headers=studio["headers"]
    )
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/tenants/current", headers=coach).json()["address_line"] is None
    assert client.get("/tenants/current/readiness", headers=coach).status_code == 403


def test_evaluate_outside_israel_has_no_prefix_warning() -> None:
    card = evaluate(
        currency="USD",
        entity_type="company",
        business_number="12-3456789",
        address_line="1 Main St",
        address_city="NYC",
        employer_file=None,
        license_number=None,
        license_expires_on=None,
        today=local_today(),
    )
    assert all(item.warning is None for item in card.items)
