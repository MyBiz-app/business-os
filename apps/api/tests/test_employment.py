from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.payroll.credit_points import compute
from tests.conftest import AuthHeaders, add_member

TERMS = {
    "employment_type": "global",
    "monthly_amount_minor": 1200000,
    "scope_pct": "100",
    "work_days_per_week": 5,
    "job_title": "Coach",
    "pension": {"fund_name": "Migdal"},
    "bank": {"bank_code": "10", "branch": "800", "account": "123453311"},
}
ANSWERS = {
    "full_name": "Dana Levi",
    "birth_date": "1995-03-12",
    "gender": "female",
    "address": "Herzl 1, Tel Aviv",
    "marital_status": "single",
    "children": [],
}


def test_credit_points_follow_the_answers() -> None:
    base = {"resident": True, "gender": "male", "children": []}
    assert compute(base, 2026) == Decimal("2.25")
    assert compute({**base, "gender": "female"}, 2026) == Decimal("2.75")
    mother = {
        **base,
        "gender": "female",
        "children": [{"birth_year": 2026}, {"birth_year": 2023}, {"birth_year": 2015}],
    }
    assert compute(mother, 2026) == Decimal("2.75") + Decimal("1.5") + Decimal("2.5") + 1
    assert compute({**base, "disability_percent": 100}, 2026) == Decimal("4.25")
    assert compute({**base, "academic_degree_year": 2025}, 2026) == Decimal("3.25")
    assert compute({**base, "resident": False}, 2026) == Decimal("0.00")
    # New immigrant from 1 Jan 2026: 12 months at 3 points, spread over the year.
    assert compute({**base, "new_immigrant_date": date(2026, 1, 1)}, 2026) == Decimal("5.25")
    # Discharged soldier in July: six months at 2 points = 1.
    assert compute({**base, "discharged_soldier_date": date(2026, 7, 1)}, 2026) == Decimal("3.25")


def test_employment_terms_are_kept_with_the_bank_masked(
    client: TestClient, engine: Engine, studio: dict
) -> None:
    headers, coach = studio["headers"], studio["coach"]
    assert client.get(f"/staff/{coach}/employment", headers=headers).json()["exists"] is False

    saved = client.put(f"/staff/{coach}/employment", json=TERMS, headers=headers)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["bank_last4"] == "3311" and body["can_reveal_bank"] is True
    assert "123453311" not in saved.text and body["pension"]["employer_pct"] == "6.5"
    with engine.begin() as connection:
        blob = connection.execute(
            text("SELECT bank_encrypted FROM app.employment_profiles")
        ).scalar()
    assert b"123453311" not in bytes(blob)

    # Saving again without a bank keeps the stored account.
    again = {**TERMS, "job_title": "Head coach"}
    del again["bank"]
    kept = client.put(f"/staff/{coach}/employment", json=again, headers=headers).json()
    assert kept["bank_last4"] == "3311" and kept["job_title"] == "Head coach"

    revealed = client.post(f"/staff/{coach}/employment/bank/reveal", headers=headers)
    assert revealed.json() == {"bank_code": "10", "branch": "800", "account": "123453311"}
    with engine.begin() as connection:
        actions = (
            connection.execute(
                text("SELECT action FROM app.audit_log WHERE action LIKE 'payroll.%' ORDER BY id")
            )
            .scalars()
            .all()
        )
    assert actions[-1] == "payroll.bank_revealed"


def test_terms_are_validated(client: TestClient, studio: dict) -> None:
    headers, coach = studio["headers"], studio["coach"]
    hourly = {**TERMS, "employment_type": "hourly", "monthly_amount_minor": None}
    refused = client.put(f"/staff/{coach}/employment", json=hourly, headers=headers)
    assert refused.status_code == 422 and refused.json()["detail"] == "hourly_rate_required"
    no_amount = {**TERMS, "monthly_amount_minor": None}
    assert (
        client.put(f"/staff/{coach}/employment", json=no_amount, headers=headers).json()["detail"]
        == "monthly_amount_required"
    )
    other_place = {**TERMS, "billing_location_id": str(uuid4())}
    assert (
        client.put(f"/staff/{coach}/employment", json=other_place, headers=headers).json()["detail"]
        == "invalid_reference"
    )


def test_who_may_see_and_change_terms(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    headers, coach = studio["headers"], studio["coach"]
    client.put(f"/staff/{coach}/employment", json=TERMS, headers=headers)
    tenant_id = studio["tenant_id"]
    manager, branch_manager = uuid4(), uuid4()
    add_member(engine, tenant_id, manager, "manager")
    add_member(engine, tenant_id, branch_manager, "branch_manager")

    manager_headers = auth(manager, tenant_id)
    assert client.get(f"/staff/{coach}/employment", headers=manager_headers).status_code == 200
    seen = client.get(f"/staff/{coach}/employment", headers=manager_headers).json()
    assert seen["can_reveal_bank"] is False
    changed = client.put(f"/staff/{coach}/employment", json=TERMS, headers=manager_headers)
    assert changed.status_code == 200
    assert (
        client.post(f"/staff/{coach}/employment/bank/reveal", headers=manager_headers).status_code
        == 403
    )

    # A branch manager sees hours only, never pay; a coach never sees a colleague's.
    branch_headers = auth(branch_manager, tenant_id)
    assert client.get(f"/staff/{coach}/employment", headers=branch_headers).status_code == 403
    coach_headers = auth(coach, tenant_id)
    owner = studio["owner"]
    assert client.get(f"/staff/{owner}/employment", headers=coach_headers).status_code == 403
    mine = client.get("/me/employment", headers=coach_headers).json()
    assert mine["monthly_amount_minor"] == 1200000 and mine["can_reveal_bank"] is False


def test_form101_request_sign_and_override(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    headers, coach = studio["headers"], studio["coach"]
    coach_headers = auth(coach, studio["tenant_id"])

    requested = client.post(f"/staff/{coach}/form101", json={"tax_year": 2026}, headers=headers)
    assert requested.status_code == 201 and requested.json()["status"] == "requested"
    again = client.post(f"/staff/{coach}/form101", json={"tax_year": 2026}, headers=headers)
    assert again.status_code == 409 and again.json()["detail"] == "form_exists"
    assert client.get("/me/form101", headers=coach_headers).json()[0]["status"] == "requested"

    signed = client.put(
        "/me/form101/2026",
        json={"answers": ANSWERS, "signed_name": "Dana Levi"},
        headers=coach_headers,
    )
    assert signed.status_code == 200, signed.text
    form = signed.json()
    assert form["status"] == "submitted" and form["credit_points"] == "2.75"
    assert form["answers"]["full_name"] == "Dana Levi" and form["signed_name"] == "Dana Levi"
    with engine.begin() as connection:
        blob = connection.execute(text("SELECT answers_encrypted FROM app.form101_forms")).scalar()
    assert b"Dana" not in bytes(blob)
    # The signed form is filed in the employee's own documents too.
    mine = client.get("/files/mine", headers=coach_headers).json()
    assert [f["name"] for f in mine] == ["form-101-2026-Dana-Levi.pdf"]

    # The payroll manager sees the answers and may overwrite the points, with a note.
    seen = client.get(f"/staff/{coach}/form101/2026", headers=headers).json()
    assert seen["answers"]["address"] == "Herzl 1, Tel Aviv"
    fixed = client.put(
        f"/staff/{coach}/form101/2026/credit-points",
        json={"points": "3.25", "note": "Accountant: degree"},
        headers=headers,
    ).json()
    assert fixed["credit_points"] == "3.25" and fixed["computed_points"] == "2.75"
    cleared = client.put(
        f"/staff/{coach}/form101/2026/credit-points", json={"points": None}, headers=headers
    ).json()
    assert cleared["credit_points"] == "2.75" and cleared["override_note"] is None

    # Signing again replaces the answers and drops the correction.
    client.put(f"/staff/{coach}/form101/2026/credit-points", json={"points": "9"}, headers=headers)
    resigned = client.put(
        "/me/form101/2026",
        json={"answers": {**ANSWERS, "gender": "male"}, "signed_name": "Dana Levi"},
        headers=coach_headers,
    ).json()
    assert resigned["credit_points"] == "2.25"


def test_form101_is_private_to_the_employee_and_payroll(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    coach, tenant_id = studio["coach"], studio["tenant_id"]
    coach_headers = auth(coach, tenant_id)
    client.put(
        "/me/form101/2026",
        json={"answers": ANSWERS, "signed_name": "Dana Levi"},
        headers=coach_headers,
    )
    colleague = uuid4()
    add_member(engine, tenant_id, colleague, "staff")
    colleague_headers = auth(colleague, tenant_id)
    assert client.get(f"/staff/{coach}/form101/2026", headers=colleague_headers).status_code == 403
    assert client.get("/me/form101/2026", headers=colleague_headers).status_code == 404
    bad = client.put(
        "/me/form101/2026",
        json={"answers": ANSWERS, "signed_name": "D"},
        headers=colleague_headers,
    )
    assert bad.status_code == 422


@pytest.mark.parametrize("path", ["/me/form101/2026/pdf"])
def test_the_signed_form_is_a_pdf(
    client: TestClient, studio: dict, auth: AuthHeaders, path: str
) -> None:
    coach_headers = auth(studio["coach"], studio["tenant_id"])
    assert client.get(path, headers=coach_headers).status_code == 404
    client.put(
        "/me/form101/2026",
        json={"answers": ANSWERS, "signed_name": "Dana Levi"},
        headers=coach_headers,
    )
    pdf = client.get(path, headers=coach_headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    owner_pdf = client.get(f"/staff/{studio['coach']}/form101/2026/pdf", headers=studio["headers"])
    assert owner_pdf.status_code == 200
