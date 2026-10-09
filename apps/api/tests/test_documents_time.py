"""Documents, time entries, retainers and bills (#45)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import STUDIO, AuthHeaders, add_member
from tests.test_bookings import new_client
from tests.test_client_app import join, join_code

PDF = b"%PDF-1.4 a small test document"


def upload(client: TestClient, headers: dict, client_id: str, name: str, **form) -> dict:
    created = client.post(
        f"/clients/{client_id}/documents",
        files={"file": (name, PDF, "application/pdf")},
        data={"name": name, **{k: str(v).lower() for k, v in form.items()}},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_documents_shared_signed_and_private(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    me = auth(user, studio["tenant_id"])
    dana = joined["client_id"]

    internal = upload(client, headers, dana, "internal-notes.pdf", kind="report")
    contract = upload(client, headers, dana, "contract.pdf", kind="contract", sign_requested=True)
    assert contract["shared"] is True and internal["shared"] is False
    downloaded = client.get(f"/documents/{contract['id']}/file", headers=headers)
    assert downloaded.content == PDF and "contract.pdf" in downloaded.headers["content-disposition"]

    bad = client.post(
        f"/clients/{dana}/documents",
        files={"file": ("x.exe", b"MZ", "application/x-msdownload")},
        headers=headers,
    )
    assert bad.status_code == 422 and bad.json()["detail"] == "unsupported_type"

    # The client sees the shared contract only, signs it, uploads their own paper.
    mine = client.get("/client/documents", headers=me).json()
    assert [d["name"] for d in mine] == ["contract.pdf"]
    assert client.get(f"/client/documents/{internal['id']}/file", headers=me).status_code == 404
    signed = client.post(
        f"/client/documents/{contract['id']}/sign", json={"name": "Dana Levi"}, headers=me
    )
    assert signed.status_code == 200 and signed.json()["signed_name"] == "Dana Levi"
    again = client.post(
        f"/client/documents/{contract['id']}/sign", json={"name": "Dana"}, headers=me
    )
    assert again.status_code == 409
    paper = client.post(
        "/client/documents",
        files={"file": ("id-card.png", b"\x89PNG fake", "image/png")},
        headers=me,
        data={"name": "ID card"},
    )
    assert paper.status_code == 201 and paper.json()["uploaded_by_client"] is True
    on_card = client.get(f"/clients/{dana}/documents", headers=headers).json()
    assert {d["name"] for d in on_card} == {"internal-notes.pdf", "contract.pdf", "ID card"}

    shared = client.patch(f"/documents/{internal['id']}", json={"shared": True}, headers=headers)
    assert shared.json()["shared"] is True
    assert len(client.get("/client/documents", headers=me).json()) == 3
    assert client.delete(f"/documents/{internal['id']}", headers=headers).status_code == 204


def test_time_retainer_and_bill(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    retainer = client.put(
        f"/clients/{dana}/retainer",
        json={"monthly_amount": 300000, "included_minutes": 600, "hourly_rate": 40000},
        headers=headers,
    )
    assert retainer.status_code == 200 and retainer.json()["currency"] == "ILS"
    for day, minutes in (("2026-09-03", 300), ("2026-09-10", 240), ("2026-09-24", 150)):
        logged = client.post(
            "/time",
            json={"client_id": dana, "day": day, "minutes": minutes, "description": "Bookkeeping"},
            headers=headers,
        )
        assert logged.status_code == 201, logged.text
    client.post(
        "/time",
        json={"client_id": dana, "day": "2026-09-25", "minutes": 60, "description": "Coffee",
              "billable": False},
        headers=headers,
    )  # fmt: skip
    client.post(
        "/time",
        json={"client_id": dana, "day": "2026-10-01", "minutes": 60, "description": "Next month"},
        headers=headers,
    )

    bill = client.post(f"/clients/{dana}/bills", json={"month": "2026-09"}, headers=headers)
    assert bill.status_code == 201, bill.text
    body = bill.json()
    # 690 billable minutes, 600 included: the fee + 1.5 hours at 400.
    assert body["kind"] == "bill" and body["status"] == "accepted"
    assert body["total"] == 300000 + 60000
    assert [line["unit_price"] for line in body["lines"]] == [300000, 40000]
    assert body["deposit_due"] == 360000  # the whole bill is due
    public = client.get(f"/public/quotes/{body['token']}").json()
    assert public["kind"] == "bill" and public["deposit_due"] == 360000

    again = client.post(f"/clients/{dana}/bills", json={"month": "2026-09"}, headers=headers)
    # The time is billed; only the fee would be left, which is billed again only by choice:
    assert again.status_code == 201 and again.json()["total"] == 300000
    entries = client.get("/time", params={"client_id": dana}, headers=headers).json()
    billed = [e for e in entries if e["bill_id"]]
    assert len(billed) == 3 and all(e["bill_number"] == body["number"] for e in billed)
    locked = client.patch(f"/time/{billed[0]['id']}", json={"minutes": 10}, headers=headers)
    assert locked.status_code == 409


def test_hourly_only_and_permissions(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    nothing = client.post(f"/clients/{dana}/bills", json={"month": "2026-09"}, headers=headers)
    assert nothing.status_code == 409
    client.put(
        f"/clients/{dana}/retainer",
        json={"monthly_amount": 0, "included_minutes": 0, "hourly_rate": 30000},
        headers=headers,
    )
    coach = uuid4()
    add_member(engine, studio["tenant_id"], coach, "staff")
    coach_headers = auth(coach, studio["tenant_id"])
    mine = client.post(
        "/time",
        json={"client_id": dana, "day": "2026-09-05", "minutes": 90, "description": "Meeting"},
        headers=coach_headers,
    ).json()
    owner_entry = client.post(
        "/time",
        json={"client_id": dana, "day": "2026-09-06", "minutes": 30, "description": "Call"},
        headers=headers,
    ).json()
    assert (
        client.patch(
            f"/time/{owner_entry['id']}", json={"minutes": 5}, headers=coach_headers
        ).status_code
        == 403
    )
    assert [
        e["id"] for e in client.get("/time", params={"mine": True}, headers=coach_headers).json()
    ] == [mine["id"]]
    assert (
        client.post(
            f"/clients/{dana}/bills", json={"month": "2026-09"}, headers=coach_headers
        ).status_code
        == 403
    )  # billing is for sales
    bill = client.post(f"/clients/{dana}/bills", json={"month": "2026-09"}, headers=headers).json()
    assert bill["total"] == 60000  # 2 hours at 300


def test_isolated_between_businesses(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    dana = new_client(client, studio["headers"], "Dana")
    document = upload(client, studio["headers"], dana, "a.pdf")
    owner = uuid4()
    other = client.post("/tenants", json={**STUDIO, "name": "Other"}, headers=auth(owner)).json()
    other_headers = auth(owner, other["id"])
    assert client.get(f"/documents/{document['id']}/file", headers=other_headers).status_code == 404
    assert client.get("/time", headers=other_headers).json() == []
    planted = client.post(
        "/time",
        json={"client_id": dana, "day": "2026-09-05", "minutes": 5, "description": "x"},
        headers=other_headers,
    )
    assert planted.status_code in (404, 422)


def test_signed_links_open_one_file_for_a_while(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    from app.signed_links import sign, verify

    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    me = auth(user, studio["tenant_id"])
    shared = upload(client, studio["headers"], joined["client_id"], "report.pdf", shared=True)
    link = client.post(f"/client/documents/{shared['id']}/link", headers=me)
    assert link.status_code == 200, link.text
    path = link.json()["url"].split("8000", 1)[1]
    opened = client.get(path)
    assert opened.status_code == 200 and opened.content == PDF
    token = path.rsplit("/", 1)[1]
    assert client.get(f"/public/files/{token[:-2]}xx").status_code == 404  # tampered
    assert verify(sign("document:x:y", ttl=-1)) is None  # expired
    other = upload(client, studio["headers"], joined["client_id"], "private.pdf")
    assert client.post(f"/client/documents/{other['id']}/link", headers=me).status_code == 404


def test_billing_run_previews_and_bills_the_month(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    noa = new_client(client, headers, "Noa")
    idle = new_client(client, headers, "Idle")  # neither a retainer nor time: not listed
    client.put(
        f"/clients/{dana}/retainer",
        json={"monthly_amount": 200000, "included_minutes": 120, "hourly_rate": 30000},
        headers=headers,
    )
    for who, minutes in ((dana, 180), (noa, 90)):
        client.post(
            "/time",
            json={"client_id": who, "day": "2026-09-08", "minutes": minutes, "description": "Work"},
            headers=headers,
        )
    client.put(
        f"/clients/{noa}/retainer",
        json={"monthly_amount": 0, "included_minutes": 0, "hourly_rate": 20000},
        headers=headers,
    )

    preview = client.get("/bills/preview", params={"month": "2026-09"}, headers=headers)
    assert preview.status_code == 200, preview.text
    rows = {row["client_id"]: row for row in preview.json()}
    assert set(rows) == {dana, noa} and idle not in rows
    assert rows[dana]["total"] == 200000 + 30000 and rows[dana]["extra_minutes"] == 60
    assert rows[noa]["total"] == 30000 and rows[noa]["billed"] is False

    run = client.post(
        "/bills/run", json={"month": "2026-09", "client_ids": [dana, noa, idle]}, headers=headers
    )
    assert run.status_code == 200, run.text
    result = run.json()
    assert sorted(b["total"] for b in result["bills"]) == [30000, 230000]
    assert result["skipped"] == [idle]

    # Once billed, the month is marked and a second run bills nobody twice.
    again = client.get("/bills/preview", params={"month": "2026-09"}, headers=headers).json()
    assert all(row["billed"] for row in again if row["client_id"] == dana)
    second = client.post(
        "/bills/run", json={"month": "2026-09", "client_ids": [dana, noa]}, headers=headers
    ).json()
    assert second["bills"] == [] and set(second["skipped"]) == {dana, noa}
    bad = client.get("/bills/preview", params={"month": "2026-13"}, headers=headers)
    assert bad.status_code == 422


def test_links_are_never_signed_with_the_public_development_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.providers.secrets import SecretsKeyMissing
    from app.signed_links import sign

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "secrets_key", None)
    with pytest.raises(SecretsKeyMissing):
        sign("document:x:y")
