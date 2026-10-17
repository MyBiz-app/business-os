import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.documents import issuing
from tests.test_bookings import new_client


def make_licensed(client: TestClient, headers: dict, entity_type: str = "licensed_dealer") -> None:
    changed = client.patch(
        "/tenants/current",
        json={
            "legal_entity_type": entity_type,
            "business_number": "515555555",
            "address_line": "Herzl 10",
            "address_city": "Rishon LeZion",
        },
        headers=headers,
    )
    assert changed.status_code == 200, changed.text


def issue(client: TestClient, headers: dict, **fields: object) -> dict:
    body = {
        "kind": "tax_invoice_receipt",
        "client_name": "Yael Cohen",
        "payment_method": "cash",
        "lines": [{"description": "Monthly membership", "quantity": 1, "unit_price": 35000}],
        **fields,
    }
    response = client.post("/issued-documents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_vat_is_split_out_of_the_total() -> None:
    assert issuing.split_vat(35000, 1800) == (29661, 5339)
    assert issuing.split_vat(35000, 0) == (35000, 0)
    assert issuing.needs_allocation("tax_invoice", 500_001, "ILS")
    assert not issuing.needs_allocation("tax_invoice", 500_000, "ILS")
    assert not issuing.needs_allocation("quote", 900_000, "ILS")


def test_each_kind_has_its_own_running_number(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)

    first = issue(client, headers)
    second = issue(client, headers)
    invoice = issue(client, headers, kind="tax_invoice", due_date="2026-11-30")
    quote = issue(client, headers, kind="quote", valid_until="2026-11-30")

    assert (first["number"], second["number"]) == (1001, 1002)
    assert (invoice["number"], quote["number"]) == (1001, 1001)
    assert (first["net"], first["vat"], first["total"]) == (29661, 5339, 35000)
    rows = {
        r["kind"]: r["next_number"]
        for r in client.get("/issued-documents/series", headers=headers).json()
    }
    assert rows["tax_invoice_receipt"] == 1003 and rows["credit_note"] == 1001


def test_the_stored_file_is_the_original_and_a_copy_is_rendered_again(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)
    doc = issue(client, headers, kind="transaction_invoice")

    original = client.get(f"/issued-documents/{doc['id']}.pdf", headers=headers)
    again = client.get(f"/issued-documents/{doc['id']}.pdf", headers=headers)
    copy = client.get(f"/issued-documents/{doc['id']}.pdf?copy=true", headers=headers)

    assert original.content.startswith(b"%PDF") and original.content == again.content
    assert hashlib.sha256(original.content).hexdigest() == doc["content_hash"]
    assert copy.content.startswith(b"%PDF") and copy.content != original.content
    assert client.get(f"/issued-documents/{doc['id']}", headers=headers).json()["id"] == doc["id"]


@pytest.mark.parametrize("kind", ["quote", "transaction_invoice"])
def test_an_exempt_dealer_issues_no_vat(client: TestClient, studio: dict, kind: str) -> None:
    headers = studio["headers"]
    make_licensed(client, headers, "exempt_dealer")

    doc = issue(client, headers, kind=kind)

    assert (doc["vat_rate_bp"], doc["vat"], doc["net"]) == (0, 0, 35000)


@pytest.mark.parametrize("kind", ["tax_invoice_receipt", "tax_invoice"])
def test_an_exempt_dealer_cannot_issue_a_tax_invoice(
    client: TestClient, studio: dict, kind: str
) -> None:
    headers = studio["headers"]
    make_licensed(client, headers, "exempt_dealer")

    refused = client.post(
        "/issued-documents",
        json={
            "kind": kind,
            "client_name": "Yael",
            "payment_method": "cash",
            "lines": [{"description": "x", "unit_price": 100}],
        },
        headers=headers,
    )

    assert refused.status_code == 409 and refused.json()["detail"] == "exempt_dealer_no_tax_invoice"
    assert client.get("/issued-documents", headers=headers).json() == []


def test_a_tax_invoice_needs_the_business_details(client: TestClient, studio: dict) -> None:
    refused = client.post(
        "/issued-documents",
        json={
            "kind": "tax_invoice",
            "client_name": "Yael",
            "lines": [{"description": "x", "unit_price": 100}],
        },
        headers=studio["headers"],
    )
    assert refused.status_code == 409 and refused.json()["detail"] == "legal_details_missing"


def test_a_big_tax_invoice_waits_for_an_allocation_number(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)

    big = issue(
        client,
        headers,
        kind="tax_invoice",
        lines=[{"description": "Corporate package", "unit_price": 900_000}],
    )
    small = issue(client, headers, kind="tax_invoice")
    given = issue(
        client,
        headers,
        kind="tax_invoice",
        allocation_number="123456789",
        lines=[{"description": "Corporate package", "unit_price": 900_000}],
    )

    assert big["allocation_required"] and big["allocation_number"] is None
    assert not small["allocation_required"]
    assert given["allocation_required"] and given["allocation_number"] == "123456789"


def test_a_credit_note_credits_an_invoice_up_to_its_total(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)
    invoice = issue(client, headers, kind="tax_invoice")

    def credit(amount: int) -> object:
        return client.post(
            "/issued-documents",
            json={
                "kind": "credit_note",
                "reference_id": invoice["id"],
                "lines": [{"description": "Refund", "unit_price": amount}],
            },
            headers=headers,
        )

    first = credit(20000)
    assert first.status_code == 201, first.text
    assert first.json()["client_name"] == "Yael Cohen"
    too_much = credit(20000)
    assert too_much.status_code == 422 and too_much.json()["detail"] == "credit_exceeds_invoice"
    assert credit(15000).status_code == 201


def test_a_credit_note_needs_a_reference_and_only_it_has_one(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)
    lines = [{"description": "x", "unit_price": 100}]
    no_reference = client.post(
        "/issued-documents", json={"kind": "credit_note", "lines": lines}, headers=headers
    )
    stray = client.post(
        "/issued-documents",
        json={
            "kind": "quote",
            "client_name": "Y",
            "lines": lines,
            "reference_id": "00000000-0000-0000-0000-000000000001",
        },
        headers=headers,
    )
    assert no_reference.status_code == 422 and stray.status_code == 422


def test_a_client_can_be_named_by_id(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)
    dana = new_client(client, headers, "Dana")

    doc = issue(client, headers, kind="quote", client_name=None, client_id=dana)

    assert doc["client_id"] == dana and doc["client_name"].startswith("Dana")
    listed = client.get("/issued-documents", params={"client_id": dana}, headers=headers).json()
    assert [d["id"] for d in listed] == [doc["id"]]


def test_a_failed_issue_leaves_no_hole_in_the_series(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)
    issue(client, headers, kind="quote")
    bad = client.post(
        "/issued-documents",
        json={
            "kind": "quote",
            "client_id": "00000000-0000-0000-0000-000000000001",
            "lines": [{"description": "x", "unit_price": 100}],
        },
        headers=headers,
    )
    assert bad.status_code == 422
    assert issue(client, headers, kind="quote")["number"] == 1002


def test_issued_documents_are_isolated_and_never_changed(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    make_licensed(client, headers)
    doc = issue(client, headers)

    with engine.begin() as connection:
        connection.execute(text("SET LOCAL ROLE app_api"))
        for statement in (
            "UPDATE app.issued_documents SET total = 1",
            "DELETE FROM app.issued_documents",
        ):
            with pytest.raises(Exception, match="permission denied"), connection.begin_nested():
                connection.execute(text(statement))
    assert client.get(f"/issued-documents/{doc['id']}", headers=headers).status_code == 200
