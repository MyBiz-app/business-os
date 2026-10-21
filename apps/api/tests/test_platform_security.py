"""The security and legal centers in the MyBiz console (K4)."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core.mfa import RISK_VERSION
from app.legal.documents import VERSIONS
from tests.conftest import AuthHeaders, make_staff


def owner_headers(engine: Engine, auth: AuthHeaders) -> dict:
    user = uuid4()
    make_staff(engine, user, "owner")
    return auth(user)


def test_centers_are_for_owners_only(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    paths = ["/platform/security/owners", "/platform/security/visits", "/platform/legal"]
    employee = uuid4()
    make_staff(engine, employee, "employee", ("businesses.read", "usage.read"))
    for path in paths:
        assert client.get(path, headers=studio["headers"]).status_code == 403
        assert client.get(path, headers=auth(employee)).status_code == 403
        assert client.get(path, headers=owner_headers(engine, auth)).status_code == 200


def test_owners_without_two_step_sign_in_are_listed_until_they_confirm(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    headers = owner_headers(engine, auth)
    board = client.get("/platform/security/owners", headers=headers).json()
    assert board["risk_version"] == RISK_VERSION and board["owners"] >= 1
    assert board["rows"][0]["business_name"]
    if board["with_mfa"] is None:  # a plain Postgres has no sign-in provider to ask
        assert board["exposed"] is None
        assert all(o["mfa_enrolled"] is None for o in board["rows"])
    mine = [o for o in board["rows"] if o["business_id"] == str(studio["tenant_id"])]
    assert mine and mine[0]["risk_acknowledged_at"] is None

    answer = client.post("/me/security/mfa-risk-acknowledgement", headers=studio["headers"])
    assert answer.status_code in (200, 201, 204)
    after = client.get("/platform/security/owners", headers=headers).json()
    mine = [o for o in after["rows"] if o["business_id"] == str(studio["tenant_id"])]
    assert mine[0]["risk_acknowledged_at"] is not None
    assert after["acknowledged_risk"] == board["acknowledged_risk"] + 1


def test_team_visits_are_counted_per_person_and_business(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, action, details)
                VALUES (:t, 'platform', 'platform.view', '{"email": "a@mybiz.test"}'),
                       (:t, 'platform', 'platform.view', '{"email": "a@mybiz.test"}'),
                       (:t, 'platform', 'platform.change', '{"email": "a@mybiz.test"}')
            """),
            {"t": studio["tenant_id"]},
        )
    board = client.get("/platform/security/visits", headers=owner_headers(engine, auth)).json()
    [visit] = [v for v in board["visits"] if v["business_id"] == str(studio["tenant_id"])]
    assert (visit["actor_email"], visit["views"], visit["changes"]) == ("a@mybiz.test", 2, 1)


def test_legal_center_shows_versions_acceptances_and_privacy_requests(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.legal_acceptances (user_id, document, version, context)
                SELECT m.user_id, 'terms', :v, 'signup' FROM app.tenant_members m
                WHERE m.tenant_id = :t AND m.role = 'owner' ON CONFLICT DO NOTHING
            """),
            {"t": studio["tenant_id"], "v": VERSIONS["terms"]},
        )
        connection.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, action)
                VALUES (:t, 'user', 'clients.erase'), (:t, 'user', 'clients.export')
            """),
            {"t": studio["tenant_id"]},
        )
        connection.execute(
            text("UPDATE app.tenants SET closed_at = now() WHERE id = :t"),
            {"t": studio["tenant_id"]},
        )
    board = client.get("/platform/legal", headers=owner_headers(engine, auth)).json()
    versions = {d["document"]: d["version"] for d in board["documents"]}
    assert versions == VERSIONS
    terms = next(d for d in board["documents"] if d["document"] == "terms")
    assert terms["accepted"] >= 1 and terms["eligible"] >= terms["accepted"]
    assert any(a["document"] == "terms" for a in board["acceptances"])
    kinds = {r["kind"] for r in board["privacy_requests"]}
    assert {"client_erasure", "client_export", "business_closure"} <= kinds
    closure = next(r for r in board["privacy_requests"] if r["kind"] == "business_closure")
    assert closure["delete_after"] is not None
