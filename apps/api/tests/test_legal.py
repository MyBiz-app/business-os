"""Legal documents: versions, acceptance records and the re-accept banner."""

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.legal.documents import VERSIONS
from tests.conftest import STUDIO, AuthHeaders

BRAND = Path(__file__).resolve().parents[3] / "packages" / "i18n" / "brand.json"


def rows(engine: Engine) -> list:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT document, version, context, business_id FROM app.legal_acceptances")
        ).all()


def test_versions_match_brand_json() -> None:
    web = json.loads(BRAND.read_text(encoding="utf-8"))["legal"]["versions"]
    assert {key: web[key]["version"] for key in VERSIONS} == VERSIONS


def test_signup_stores_the_accepted_versions(
    client: TestClient, auth: AuthHeaders, engine: Engine
) -> None:
    owner = uuid4()
    created = client.post(
        "/tenants", json={**STUDIO, "accepted_legal": dict(VERSIONS)}, headers=auth(owner)
    )
    assert created.status_code == 201, created.text
    stored = rows(engine)
    assert sorted(r.document for r in stored) == ["dpa", "privacy", "terms"]
    assert {r.context for r in stored} == {"signup"}
    assert {str(r.business_id) for r in stored} == {created.json()["id"]}
    me = client.get("/me", headers=auth(owner, created.json()["id"])).json()
    assert me["legal_pending"] == []


def test_signup_rejects_an_old_version(client: TestClient, auth: AuthHeaders) -> None:
    old = {**VERSIONS, "terms": "2020-01-01"}
    response = client.post(
        "/tenants", json={**STUDIO, "accepted_legal": old}, headers=auth(uuid4())
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "legal_outdated"


def test_banner_until_accepted_then_again_after_a_new_version(
    client: TestClient, auth: AuthHeaders, engine: Engine, monkeypatch
) -> None:
    owner = uuid4()
    tenant_id = client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"]
    headers = auth(owner, tenant_id)
    pending = client.get("/me", headers=headers).json()["legal_pending"]
    assert {p["document"] for p in pending} == {"terms", "privacy", "dpa"}

    accepted = client.post("/me/legal", json={"documents": dict(VERSIONS)}, headers=headers)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json() == []
    assert {r.context for r in rows(engine)} == {"reaccept"}
    # Accepting twice is harmless.
    client.post("/me/legal", json={"documents": dict(VERSIONS)}, headers=headers)
    assert len(rows(engine)) == 3

    monkeypatch.setitem(VERSIONS, "terms", "2099-01-01")
    pending = client.get("/me/legal", headers=headers).json()
    assert pending == [{"document": "terms", "version": "2099-01-01"}]


def test_clients_are_not_asked_for_the_business_terms(
    client: TestClient, auth: AuthHeaders
) -> None:
    person = uuid4()
    pending = client.get("/me/legal", headers=auth(person)).json()
    assert {p["document"] for p in pending} == {"terms", "privacy"}


def test_join_stores_the_acceptance(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    code = client.get("/tenants/current", headers=studio["headers"]).json()["join_code"]
    person = uuid4()
    joined = client.post(
        "/client/businesses",
        json={
            "code": code,
            "accepted_legal": {"terms": VERSIONS["terms"], "privacy": VERSIONS["privacy"]},
        },
        headers=auth(person),
    )
    assert joined.status_code == 201, joined.text
    stored = [r for r in rows(engine) if r.context == "client_join"]
    assert sorted(r.document for r in stored) == ["privacy", "terms"]
    assert {str(r.business_id) for r in stored} == {str(studio["tenant_id"])}
    assert client.get("/me/legal", headers=auth(person)).json() == []


def test_one_person_cannot_read_anothers_acceptances(client: TestClient, auth: AuthHeaders) -> None:
    first, second = uuid4(), uuid4()
    client.post("/me/legal", json={"documents": dict(VERSIONS)}, headers=auth(first))
    pending = client.get("/me/legal", headers=auth(second)).json()
    assert {p["document"] for p in pending} == {"terms", "privacy"}
