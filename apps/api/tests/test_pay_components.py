from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.payroll.components import split_evenly
from tests.conftest import AuthHeaders, add_member

TERMS = {"employment_type": "global", "monthly_amount_minor": 1200000}


def _with_file(client: TestClient, headers: dict, user_id: UUID) -> None:
    assert (
        client.put(f"/staff/{user_id}/employment", json=TERMS, headers=headers).status_code == 200
    )


def test_shares_add_up_exactly() -> None:
    assert split_evenly(350000, 7) == [50000] * 7
    shares = split_evenly(100, 3)
    assert shares == [34, 33, 33] and sum(shares) == 100


def test_components_get_defaults_by_kind_and_are_changed_and_removed(
    client: TestClient, studio: dict
) -> None:
    headers, coach = studio["headers"], studio["coach"]
    travel = client.post(
        f"/staff/{coach}/pay-components",
        json={"kind": "travel", "name": "Travel", "amount_minor": 2260, "cap_minor": 49720},
        headers=headers,
    )
    assert travel.status_code == 201, travel.text
    made = travel.json()
    assert made["calc"] == "per_work_day"
    assert (made["taxable"], made["social_security_liable"], made["pension_base"]) == (
        False,
        False,
        False,
    )
    addition = client.post(
        f"/staff/{coach}/pay-components",
        json={"kind": "fixed_addition", "name": "Seniority", "amount_minor": 50000},
        headers=headers,
    ).json()
    assert addition["taxable"] and addition["pension_base"]

    changed = client.patch(
        f"/pay-components/{made['id']}",
        json={"amount_minor": 2400, "taxable": True},
        headers=headers,
    )
    assert changed.json()["amount_minor"] == 2400 and changed.json()["taxable"] is True
    listed = client.get(f"/staff/{coach}/pay-components", headers=headers).json()
    assert [row["name"] for row in listed] == ["Travel", "Seniority"]

    assert client.delete(f"/pay-components/{made['id']}", headers=headers).status_code == 204
    assert len(client.get(f"/staff/{coach}/pay-components", headers=headers).json()) == 1


def test_component_validation(client: TestClient, studio: dict) -> None:
    headers, coach = studio["headers"], studio["coach"]
    url = f"/staff/{coach}/pay-components"
    no_amount = client.post(url, json={"kind": "phone", "name": "Phone"}, headers=headers)
    assert no_amount.status_code == 422 and no_amount.json()["detail"] == "amount_required"
    typed_monthly = client.post(
        url, json={"kind": "travel", "name": "Travel", "calc": "by_month"}, headers=headers
    )
    assert typed_monthly.status_code == 201 and typed_monthly.json()["amount_minor"] is None
    backwards = client.post(
        url,
        json={
            "kind": "phone",
            "name": "Phone",
            "amount_minor": 1,
            "valid_from": "2026-05-01",
            "valid_to": "2026-04-01",
        },
        headers=headers,
    )
    assert backwards.status_code == 422
    missing = client.patch(f"/pay-components/{uuid4()}", json={"amount_minor": 1}, headers=headers)
    assert missing.status_code == 404


def test_who_sees_components(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    headers, coach, tenant_id = studio["headers"], studio["coach"], studio["tenant_id"]
    client.post(
        f"/staff/{coach}/pay-components",
        json={"kind": "phone", "name": "Phone", "amount_minor": 5000},
        headers=headers,
    )
    manager, other_manager = uuid4(), uuid4()
    add_member(engine, tenant_id, manager, "manager")
    add_member(engine, tenant_id, other_manager, "manager")
    manager_headers = auth(manager, tenant_id)
    assert client.get(f"/staff/{coach}/pay-components", headers=manager_headers).status_code == 200
    # Nobody sees the pay of a peer or of the owner, except the owner.
    peer = client.get(f"/staff/{other_manager}/pay-components", headers=manager_headers)
    assert peer.status_code == 404
    owner = client.get(f"/staff/{studio['owner']}/pay-components", headers=manager_headers)
    assert owner.status_code == 404
    assert client.get(f"/staff/{other_manager}/pay-components", headers=headers).status_code == 200

    coach_headers = auth(coach, tenant_id)
    assert client.get(f"/staff/{coach}/pay-components", headers=coach_headers).status_code == 403
    mine = client.get("/me/pay-components", headers=coach_headers).json()
    assert [row["name"] for row in mine] == ["Phone"]


def test_rates_come_dated_and_unverified(client: TestClient, engine: Engine, studio: dict) -> None:
    headers = studio["headers"]
    with engine.begin() as connection:  # the test database is emptied between tests
        connection.execute(
            text("""
                INSERT INTO app.payroll_rates (rate_key, valid_from, value, source) VALUES
                ('min_wage_hourly', '2024-04-01', '{"minor": 3000}', 'test'),
                ('min_wage_hourly', '2025-04-01', '{"minor": 3432}', 'test'),
                ('overtime_tiers', '2025-01-01',
                 '{"tiers": [{"hours": 2, "pct": 125}, {"hours": null, "pct": 150}]}', 'test')
            """)
        )
    rates = {row["rate_key"]: row for row in client.get("/payroll/rates", headers=headers).json()}
    assert rates["min_wage_hourly"]["value"]["minor"] == 3432
    assert rates["overtime_tiers"]["value"]["tiers"][0] == {"hours": 2, "pct": 125}
    assert not any(row["verified"] for row in rates.values())
    earlier = client.get("/payroll/rates?as_of=2024-06-01", headers=headers).json()
    assert [row["value"]["minor"] for row in earlier] == [3000]
    assert client.get("/payroll/rates?as_of=2020-01-01", headers=headers).json() == []


def test_group_bonus_goes_to_everyone_with_a_payroll_file(
    client: TestClient, engine: Engine, studio: dict
) -> None:
    headers, coach, tenant_id = studio["headers"], studio["coach"], studio["tenant_id"]
    second, no_file = uuid4(), uuid4()
    add_member(engine, tenant_id, second, "staff")
    add_member(engine, tenant_id, no_file, "staff")
    _with_file(client, headers, coach)
    _with_file(client, headers, second)
    location = studio["location"]["id"]
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.tenant_members SET location_ids = ARRAY[CAST(:l AS uuid)]"
                " WHERE role = 'staff'"
            ),
            {"l": location},
        )

    body = {
        "target": {"kind": "location", "location_id": location},
        "kind": "bonus",
        "period": "2026-10-17",
        "amount_mode": "split_total",
        "amount_minor": 100001,
        "note": "Targets",
    }
    preview = client.post("/payroll/bonuses/preview", json=body, headers=headers).json()
    assert [row["amount_minor"] for row in preview["recipients"]] == [50001, 50000]
    assert preview["total_minor"] == 100001 and preview["without_payroll_file"] == 1

    created = client.post("/payroll/bonuses", json=body, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "approved" and created.json()["period"] == "2026-10-01"
    listed = client.get("/payroll/bonuses?period=2026-10-20", headers=headers).json()
    assert sorted(row["amount_minor"] for row in listed) == [50000, 50001]
    assert all(row["status"] == "approved" and row["taxable"] for row in listed)

    gift = {**body, "kind": "holiday_gift", "amount_mode": "each", "amount_minor": 30000}
    gift["target"] = {"kind": "employee", "user_ids": [str(coach)]}
    created_gift = client.post("/payroll/bonuses", json=gift, headers=headers).json()
    assert created_gift["count"] == 1
    gifts = client.get(f"/payroll/bonuses?user_id={coach}", headers=headers).json()
    assert {row["kind"] for row in gifts} == {"bonus", "holiday_gift"}
    assert not next(row for row in gifts if row["kind"] == "holiday_gift")["taxable"]

    one = listed[0]["id"]
    assert client.delete(f"/payroll/adjustments/{one}", headers=headers).status_code == 204


def test_bonus_target_and_amount_are_validated(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    base = {"kind": "bonus", "period": "2026-10-01", "amount_minor": 1000}
    incomplete = client.post(
        "/payroll/bonuses",
        json={**base, "target": {"kind": "location"}},
        headers=headers,
    )
    assert incomplete.status_code == 422
    nobody = client.post(
        "/payroll/bonuses", json={**base, "target": {"kind": "everyone"}}, headers=headers
    )
    assert nobody.status_code == 422 and nobody.json()["detail"] == "no_recipients"
    zero = client.post(
        "/payroll/bonuses",
        json={**base, "amount_minor": 0, "target": {"kind": "everyone"}},
        headers=headers,
    )
    assert zero.status_code == 422


def test_branch_manager_proposes_and_the_owner_decides(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    headers, coach, tenant_id = studio["headers"], studio["coach"], studio["tenant_id"]
    location = studio["location"]["id"]
    _with_file(client, headers, coach)
    far_away = uuid4()
    add_member(engine, tenant_id, far_away, "staff")
    _with_file(client, headers, far_away)
    branch_manager = uuid4()
    add_member(engine, tenant_id, branch_manager, "branch_manager")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.tenant_members SET location_ids = ARRAY[CAST(:l AS uuid)]"
                " WHERE user_id IN (:a, :b)"
            ),
            {"l": location, "a": coach, "b": branch_manager},
        )
    proposer = auth(branch_manager, tenant_id)
    body = {
        "target": {"kind": "everyone"},
        "kind": "bonus",
        "period": "2026-10-01",
        "amount_minor": 50000,
        "note": "Great month",
    }
    preview = client.post("/payroll/bonuses/preview", json=body, headers=proposer).json()
    # Only the coach is at the branch: the other one and the owner are out of reach.
    assert [row["user_id"] for row in preview["recipients"]] == [str(coach)]
    assert preview["out_of_reach"] >= 2

    proposed = client.post("/payroll/bonuses", json=body, headers=proposer)
    assert proposed.status_code == 201 and proposed.json()["status"] == "proposed"
    batch = proposed.json()["batch_id"]
    # The proposer sees only their own proposal; they cannot decide it, or see pay.
    assert len(client.get("/payroll/bonuses", headers=proposer).json()) == 1
    denied = client.post(
        f"/payroll/bonuses/{batch}/decision", json={"approve": True}, headers=proposer
    )
    assert denied.status_code == 403
    assert client.get("/payroll/rates", headers=proposer).status_code == 403

    decided = client.post(
        f"/payroll/bonuses/{batch}/decision", json={"approve": True}, headers=headers
    )
    assert decided.status_code == 200 and decided.json()["status"] == "approved"
    again = client.post(
        f"/payroll/bonuses/{batch}/decision", json={"approve": False}, headers=headers
    )
    assert again.status_code == 404
    rows = client.get(f"/payroll/bonuses?user_id={coach}", headers=headers).json()
    assert [row["status"] for row in rows] == ["approved"]

    # A proposal still waiting can be withdrawn by its proposer, nothing else can.
    second = client.post("/payroll/bonuses", json=body, headers=proposer).json()
    line = client.get("/payroll/bonuses?status=proposed", headers=proposer).json()[0]["id"]
    assert second["status"] == "proposed"
    assert client.delete(f"/payroll/adjustments/{line}", headers=proposer).status_code == 204
    approved_line = rows[0]["id"]
    assert (
        client.delete(f"/payroll/adjustments/{approved_line}", headers=proposer).status_code == 404
    )

    with engine.begin() as connection:
        actions = (
            connection.execute(
                text(
                    "SELECT action FROM app.audit_log WHERE action LIKE 'payroll.bonus%'"
                    " ORDER BY id"
                )
            )
            .scalars()
            .all()
        )
    assert actions == ["payroll.bonus_proposed", "payroll.bonus_approved", "payroll.bonus_proposed"]


def test_a_branch_manager_cannot_reach_staff_above_them(
    client: TestClient, engine: Engine, studio: dict, auth: AuthHeaders
) -> None:
    headers, tenant_id = studio["headers"], studio["tenant_id"]
    location = studio["location"]["id"]
    branch_manager, manager = uuid4(), uuid4()
    add_member(engine, tenant_id, branch_manager, "branch_manager")
    add_member(engine, tenant_id, manager, "manager")
    _with_file(client, headers, manager)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE app.tenant_members SET location_ids = ARRAY[CAST(:l AS uuid)]"
                " WHERE user_id IN (:a, :b)"
            ),
            {"l": location, "a": branch_manager, "b": manager},
        )
    response = client.post(
        "/payroll/bonuses",
        json={
            "target": {"kind": "employee", "user_ids": [str(manager)]},
            "period": "2026-10-01",
            "amount_minor": 1000,
        },
        headers=auth(branch_manager, tenant_id),
    )
    assert response.status_code == 422 and response.json()["detail"] == "no_recipients"
