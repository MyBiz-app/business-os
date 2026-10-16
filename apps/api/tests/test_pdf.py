import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.documents import brand, render
from tests.conftest import AuthHeaders
from tests.test_billing import end_trial, run_billing
from tests.test_bookings import new_client
from tests.test_checkouts import setup
from tests.test_receipts import sell

ROOT = Path(__file__).resolve().parents[3]


def test_company_details_match_brand_json() -> None:
    legal = json.loads((ROOT / "packages/i18n/brand.json").read_text("utf-8"))["legal"]
    assert legal["companyName"] == brand.COMPANY_NAME
    assert legal["address"] == brand.ADDRESS
    assert legal["companyNumber"] == brand.COMPANY_NUMBER
    assert legal["vatNumber"] == brand.VAT_NUMBER
    assert (legal["email"], legal["website"]) == (brand.EMAIL, brand.WEBSITE)
    assert legal["fictitious"] is brand.FICTITIOUS


def test_money_follows_the_language() -> None:
    assert render.money(125000, "ILS", "he") == "1,250.00₪"
    assert render.money(125000, "ILS", "en") == "₪1,250.00"
    assert render.money(500, "JPY", "en") == "JPY 500"


def test_a_receipt_downloads_as_pdf(client: TestClient, studio: dict) -> None:
    dana = new_client(client, studio["headers"], "דנה")
    sold = sell(client, studio, dana)

    response = client.get(
        f"/documents/render/receipt/{sold['receipt_id']}.pdf", headers=studio["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "receipt-1001.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_a_client_downloads_only_their_own_receipt(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    _, headers, card = setup(client, auth, studio)
    checkout = client.post(
        "/client/checkouts", json={"plan_id": card["id"]}, headers=headers
    ).json()
    paid = client.post(f"/client/checkouts/{checkout['id']}/simulate-payment", headers=headers)
    other = sell(client, studio, new_client(client, studio["headers"], "Noa"))

    mine = paid.json()["entitlement"]["receipt_id"]
    got = client.get(f"/client/receipts/{mine}.pdf", headers=headers)
    assert got.status_code == 200, got.text
    assert got.content[:4] == b"%PDF"
    assert (
        client.get(f"/client/receipts/{other['receipt_id']}.pdf", headers=headers).status_code
        == 404
    )


def test_a_platform_invoice_downloads_as_pdf(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    client.put("/tenants/current/modules", json={"modules": {"client_app": 1}}, headers=headers)
    end_trial(engine, studio["tenant_id"], days_ago=40)
    run_billing(engine)
    invoice = client.get("/billing", headers=headers).json()["invoices"][0]

    response = client.get(
        f"/documents/render/platform_invoice/{invoice['id']}.pdf", headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF")
    missing = client.get(
        "/documents/render/platform_invoice/00000000-0000-0000-0000-000000000000.pdf",
        headers=headers,
    )
    assert missing.status_code == 404
