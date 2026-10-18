"""Corrective payslips of approved months and the annual summary."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.test_payroll_runs import _setup
from tests.test_payslips import _approve

BODY = {"reason": "Missed bonus", "items": [{"label": "Goal bonus", "amount_minor": 20000}]}


def test_only_an_approved_month_can_be_corrected(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    headers, coach = ctx["headers"], ctx["coach"]
    client.post("/payroll/runs", json={"period": "2026-03"}, headers=headers)
    url = f"/payroll/runs/2026-03/payslips/{coach}/corrections"
    early = client.post(url, json=BODY, headers=headers)
    assert early.status_code == 409 and early.json()["detail"] == "run_not_approved"


def test_a_correction_is_a_new_version_with_the_difference_and_a_pdf(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    headers, coach = ctx["headers"], ctx["coach"]
    _approve(client, headers, ctx)
    before = next(
        p
        for p in client.get("/payroll/runs/2026-03/net", headers=headers).json()["people"]
        if p["user_id"] == coach
    )
    url = f"/payroll/runs/2026-03/payslips/{coach}/corrections"
    first = client.post(url, json=BODY, headers=headers)
    assert first.status_code == 201, first.text
    one = first.json()
    assert one["version"] == 1 and one["previous_net_minor"] == before["net_minor"]
    assert one["difference_minor"] == one["net_minor"] - before["net_minor"] > 0
    # Tax and insurance take part of the extra pay: the net grows by less than the bonus.
    assert one["difference_minor"] <= 20000

    second = client.post(
        url,
        json={"reason": "Bonus reversed", "items": [{"label": "Undo", "amount_minor": -20000}]},
        headers=headers,
    ).json()
    assert second["version"] == 2 and second["previous_net_minor"] == one["net_minor"]
    assert second["net_minor"] == before["net_minor"]
    assert [c["version"] for c in client.get(url, headers=headers).json()] == [1, 2]

    # The approved month itself is untouched.
    after = next(
        p
        for p in client.get("/payroll/runs/2026-03/net", headers=headers).json()["people"]
        if p["user_id"] == coach
    )
    assert after == before

    # Each corrective payslip is also filed in the payroll folder and in the person's own files.
    folders = client.get("/files/folders", headers=headers).json()
    payroll = next(f for f in folders if f["system_key"] == "payroll")
    filed = [
        f["name"]
        for f in client.get("/files", params={"folder_id": payroll["id"]}, headers=headers).json()
    ]
    assert sum(n.startswith("payslip-2026-03-") and n.endswith("-v1.pdf") for n in filed) == 1
    assert sum(n.startswith("payslip-2026-03-") and n.endswith("-v2.pdf") for n in filed) == 1

    base = f"/payroll/runs/2026-03/payslips/{coach}/pdf"
    for params in ({}, {"version": 0}, {"version": 1}):
        pdf = client.get(base, params=params, headers=headers)
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(base, params={"version": 9}, headers=headers).status_code == 404
    # The signed-in owner sees the corrections of their own payslip.
    own = f"/payroll/runs/2026-03/payslips/{ctx['owner']}/corrections"
    assert client.post(own, json=BODY, headers=headers).status_code == 201
    mine = client.get("/me/payslips", headers=headers).json()
    assert mine[0]["corrections"] == 1
    assert client.get("/me/payslips/2026-03/pdf", headers=headers).status_code == 200


def test_a_correction_needs_a_real_change_and_a_non_negative_net(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    headers, coach = ctx["headers"], ctx["coach"]
    _approve(client, headers, ctx)
    url = f"/payroll/runs/2026-03/payslips/{coach}/corrections"
    zero = client.post(
        url,
        json={
            "reason": "x",
            "items": [{"label": "a", "amount_minor": 5}, {"label": "b", "amount_minor": -5}],
        },
        headers=headers,
    )
    assert zero.status_code == 422 and zero.json()["detail"] == "nothing_to_correct"
    huge = client.post(
        url,
        json={"reason": "x", "items": [{"label": "a", "amount_minor": -99_000_000}]},
        headers=headers,
    )
    assert huge.status_code == 422 and huge.json()["detail"] == "negative_net"
    assert client.post(url, json={"reason": "x", "items": []}, headers=headers).status_code == 422


def test_the_annual_summary_adds_up_approved_months_and_uses_corrections(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    headers, coach = ctx["headers"], ctx["coach"]
    empty = client.get("/payroll/annual/2026", headers=headers).json()
    assert empty["people"] == []
    _approve(client, headers, ctx)
    plain = client.get("/payroll/annual/2026", headers=headers).json()
    person = next(p for p in plain["people"] if p["user_id"] == coach)
    assert person["months"] == 1 and person["corrected_months"] == 0 and plain["draft"] is True
    assert person["net_minor"] == person["gross_minor"] - sum(
        person[k]
        for k in (
            "income_tax_minor",
            "national_insurance_minor",
            "health_minor",
            "pension_employee_minor",
            "study_fund_employee_minor",
            "other_deductions_minor",
        )
    )
    client.post(f"/payroll/runs/2026-03/payslips/{coach}/corrections", json=BODY, headers=headers)
    corrected = client.get("/payroll/annual/2026", headers=headers).json()
    again = next(p for p in corrected["people"] if p["user_id"] == coach)
    assert again["corrected_months"] == 1 and again["gross_minor"] == person["gross_minor"] + 20000
    other_year = client.get("/payroll/annual/2025", headers=headers).json()
    assert other_year["people"] == []
    for fmt in ("csv", "xlsx"):
        export = client.get("/payroll/annual/2026/export", params={"format": fmt}, headers=headers)
        assert export.status_code == 200 and len(export.content) > 50
