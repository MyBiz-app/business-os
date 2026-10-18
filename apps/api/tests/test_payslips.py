"""Net pay, the payslip PDF and the bank file."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.payroll import masav
from app.payroll.net import Funds, compute_net
from app.payroll.rates import resolve
from tests.test_identities import VALID
from tests.test_payroll_runs import _line, _setup

RATES = resolve({})
FUNDS = Funds(Decimal(6), Decimal("6.5"), Decimal(6))


def test_net_is_gross_less_tax_insurance_and_pension() -> None:
    # 10,000.00 a month, 2.25 credit points: tax on the brackets less the credit.
    net = compute_net(1_000_000, 1_000_000, 1_000_000, 1_000_000, 0, Decimal("2.25"), FUNDS, RATES)
    bracket_tax = 701_000 * 10 // 100 + (1_000_000 - 701_000) * 14 // 100  # 70100 + 41860
    assert net.tax_minor == bracket_tax - round(Decimal("2.25") * 24200)
    reduced, full = 752_200, 1_000_000 - 752_200
    assert net.national_insurance_minor == round(reduced * 0.0104 + full * 0.07)
    assert net.health_minor == round(reduced * 0.0323 + full * 0.0517)
    assert net.pension_minor == 60_000
    assert net.net_minor == 1_000_000 - net.total_deductions_minor
    assert [line.code for line in net.employer][:2] == ["pension_employer", "severance"]
    assert net.problems == []


def test_credit_points_never_make_the_tax_negative_and_deductions_can_empty_the_net() -> None:
    low = compute_net(300_000, 300_000, 300_000, 300_000, 0, Decimal(9), FUNDS, RATES)
    assert low.tax_minor == 0
    broke = compute_net(300_000, 300_000, 300_000, 300_000, 500_000, Decimal(0), FUNDS, RATES)
    assert broke.net_minor < 0 and broke.problems == ["negative_net"]


def test_pay_above_the_insurance_ceiling_is_not_charged_further() -> None:
    capped = compute_net(9_000_000, 9_000_000, 9_000_000, 0, 0, Decimal(0), FUNDS, RATES)
    same = compute_net(5_191_000, 5_191_000, 5_191_000, 0, 0, Decimal(0), FUNDS, RATES)
    assert capped.national_insurance_minor == same.national_insurance_minor


def test_the_rates_table_wins_over_the_examples() -> None:
    table = {"credit_point_monthly": {"minor": 30000}}
    assert resolve(table).credit_point_minor == 30000
    assert "income_tax_brackets" in resolve(table).example_keys
    assert resolve(table).tax_brackets == RATES.tax_brackets


def test_the_bank_file_has_fixed_width_records() -> None:
    sender = masav.Sender("12345678", "98765", "Studio")
    payee = masav.Payee("Dana", "123456782", "10", "800", "123453311", 564_000, "2026-03")
    body = masav.build(sender, date(2026, 4, 9), date(2026, 4, 1), date(2026, 3, 1), [payee])
    lines = body.decode("cp862").splitlines()
    assert [line[0] for line in lines] == ["K", "1", "5", "9"]
    assert {len(line) for line in lines} == {masav.WIDTH}
    assert "0000000564000" in lines[1] and lines[1][9:11] == "00"
    assert lines[2][36:51] == "000000000564000"  # the credit total


def _approve(client: TestClient, headers: dict, ctx: dict) -> None:
    coach, owner = ctx["coach"], ctx["owner"]
    client.post("/payroll/runs", json={"period": "2026-03"}, headers=headers)
    client.put(f"/time-clock/people/{coach}/approval", params={"month": "2026-03"}, headers=headers)
    for stage in ("additions", "review"):
        client.post("/payroll/runs/2026-03/stage", json={"stage": stage}, headers=headers)
    run = client.get("/payroll/runs/2026-03", headers=headers).json()
    for user in (coach, owner):
        for warning in _line(run, user)["warnings"]:
            client.post(
                f"/payroll/runs/2026-03/lines/{user}/acknowledge",
                json={"key": warning["key"]},
                headers=headers,
            )
    approved = client.post(
        "/payroll/runs/2026-03/stage", json={"stage": "approved"}, headers=headers
    )
    assert approved.status_code == 200, approved.text


def test_net_is_frozen_when_the_month_is_approved_and_payslips_open(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    headers, coach = ctx["headers"], ctx["coach"]
    client.post("/payroll/runs", json={"period": "2026-03"}, headers=headers)
    live = client.get("/payroll/runs/2026-03/net", headers=headers).json()
    assert live["payslips_draft"] is True and not any(p["frozen"] for p in live["people"])
    assert "income_tax_brackets" in live["example_rates"]
    person = next(p for p in live["people"] if p["user_id"] == coach)
    assert person["gross_minor"] == 56600
    assert person["net_minor"] == person["gross_minor"] - person["total_deductions_minor"]
    assert live["net_minor"] == sum(p["net_minor"] for p in live["people"])

    _approve(client, headers, ctx)
    # Every payslip is filed in the payroll folder, and in the person's own documents.
    folders = client.get("/files/folders", headers=headers).json()
    payroll = next(f for f in folders if f["system_key"] == "payroll")
    names = [
        f["name"]
        for f in client.get("/files", params={"folder_id": payroll["id"]}, headers=headers).json()
    ]
    assert sum(n.startswith("payslip-2026-03-") and n.endswith(".pdf") for n in names) == 2
    assert not any(n.endswith("-final.pdf") for n in names)
    assert any(
        f["name"].startswith("payslip-2026-03-")
        for f in client.get("/files/mine", headers=headers).json()
    )
    frozen = client.get("/payroll/runs/2026-03/net", headers=headers).json()
    assert all(p["frozen"] for p in frozen["people"])
    # A later rates row changes nothing for the approved month.
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.payroll_rates (rate_key, valid_from, value, source)
                VALUES ('credit_point_monthly', '2026-03-01', '{"minor": 1}', 'test')
            """)
        )
    try:
        again = client.get("/payroll/runs/2026-03/net", headers=headers).json()
        assert again["people"] == frozen["people"]
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM app.payroll_rates WHERE source = 'test'"))

    pdf = client.get(f"/payroll/runs/2026-03/payslips/{coach}/pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    mine = client.get("/me/payslips", headers=headers).json()
    assert mine and mine[0]["period"] == "2026-03-01" and mine[0]["draft"] is True
    assert client.get("/me/payslips/2026-03/pdf", headers=headers).status_code == 200
    assert client.get("/me/payslips/2026-04/pdf", headers=headers).status_code == 404
    checked = client.post("/payroll/runs/2026-03/accountant-check", headers=headers)
    assert checked.status_code == 204
    names = [
        f["name"]
        for f in client.get("/files", params={"folder_id": payroll["id"]}, headers=headers).json()
    ]
    assert sum(n.endswith("-final.pdf") for n in names) == 2


def test_the_bank_file_needs_an_approved_month_and_complete_payees(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    ctx = _setup(client, studio, engine)
    headers, coach, owner = ctx["headers"], ctx["coach"], ctx["owner"]
    body = {
        "institution_code": "12345678",
        "sending_code": "98765",
        "institution_name": "Studio",
        "pay_date": "2026-04-09",
    }
    client.post("/payroll/runs", json={"period": "2026-03"}, headers=headers)
    early = client.post("/payroll/runs/2026-03/bank-file", json=body, headers=headers)
    assert early.status_code == 409 and early.json()["detail"] == "run_not_approved"

    _approve(client, headers, ctx)
    missing = client.post("/payroll/runs/2026-03/bank-file", json=body, headers=headers)
    assert missing.status_code == 422 and missing.json()["detail"] == "payees_incomplete"

    bank = {"bank_code": "10", "branch": "800", "account": "123453311"}
    for user, number in ((coach, VALID), (owner, "039337423")):
        terms = client.get(f"/staff/{user}/employment", headers=headers).json()
        client.put(
            f"/staff/{user}/employment",
            json={
                **{
                    k: terms[k]
                    for k in ("employment_type", "monthly_amount_minor", "hourly_rate_minor")
                },
                "bank": bank,
            },
            headers=headers,
        )
        client.put(
            f"/staff/{user}/identity",
            json={"id_type": "il_id", "number": number},
            headers=headers,
        )
    ok = client.post("/payroll/runs/2026-03/bank-file", json=body, headers=headers)
    assert ok.status_code == 200, ok.text
    lines = ok.content.decode("cp862").splitlines()
    assert [line[0] for line in lines] == ["K", "1", "1", "5", "9"]
    nets = client.get("/payroll/runs/2026-03/net", headers=headers).json()
    assert int(lines[3][36:51]) == nets["net_minor"]
