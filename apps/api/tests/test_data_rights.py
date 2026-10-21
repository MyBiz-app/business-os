"""Go-live GL8: client data registry, whole-business export, erase of AI chats, and platform
invoices that outlive a deleted business."""

import csv
import io
import zipfile
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app import jobs
from app.commerce.billing import bill_businesses
from app.core.data_rights import CLIENT_TABLES
from tests.conftest import AuthHeaders, add_member
from tests.test_billing import end_trial
from tests.test_closure import backdate, close
from tests.test_documents_time import PDF, upload
from tests.test_privacy import app_member


def test_every_table_with_a_client_id_is_in_the_registry(engine: Engine) -> None:
    """A new table that holds client data must say how it is exported and erased."""
    with engine.connect() as connection:
        tables = set(
            connection.execute(
                text("""
                    SELECT c.table_name FROM information_schema.columns c
                    JOIN information_schema.tables t USING (table_schema, table_name)
                    WHERE c.table_schema = 'app' AND c.column_name = 'client_id'
                      AND t.table_type = 'BASE TABLE'
                """)
            ).scalars()
        )
    assert tables == set(CLIENT_TABLES), (
        f"add to CLIENT_TABLES: {sorted(tables - set(CLIENT_TABLES))}; "
        f"remove: {sorted(set(CLIENT_TABLES) - tables)}"
    )


def test_client_export_has_a_section_for_every_registered_table(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    joined, _ = app_member(client, auth, studio)
    document = client.get(
        f"/clients/{joined['client_id']}/export", headers=studio["headers"]
    ).json()
    missing = {t.export for t in CLIENT_TABLES.values()} - set(document)
    assert not missing
    assert "app_ai_conversations" in document


def test_erase_removes_the_clients_chats_with_the_in_app_assistant(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    joined, _ = app_member(client, auth, studio)
    with engine.begin() as connection:
        user = connection.execute(
            text("SELECT user_id FROM app.clients WHERE id = :id"), {"id": joined["client_id"]}
        ).scalar_one()
        connection.execute(
            text("""
                INSERT INTO app.ai_conversations (tenant_id, user_id, messages)
                VALUES (:t, :u, CAST('[{"role":"user","content":"my knee hurts"}]' AS jsonb))
            """),
            {"t": studio["tenant_id"], "u": user},
        )
    exported = client.get(f"/clients/{joined['client_id']}/export", headers=studio["headers"])
    assert len(exported.json()["app_ai_conversations"]) == 1

    erased = client.post(
        f"/clients/{joined['client_id']}/erase", json={"confirm": True}, headers=studio["headers"]
    )
    assert erased.status_code == 200, erased.text
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM app.ai_conversations WHERE user_id = :u"), {"u": user}
            ).scalar_one()
            == 0
        )


def read_zip(content: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(content))


def test_owner_exports_the_whole_business(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    headers = studio["headers"]
    dana = client.post("/clients", json={"first_name": "Dana"}, headers=headers).json()["id"]
    upload(client, headers, dana, "terms.pdf")

    started = client.post("/tenants/current/data-exports", headers=headers)
    assert started.status_code == 202, started.text
    [export] = client.get("/tenants/current/data-exports", headers=headers).json()
    assert export["status"] == "ready" and export["file_count"] > 3

    link = client.post(f"/tenants/current/data-exports/{export['id']}/link", headers=headers)
    token = link.json()["url"].rsplit("/", 1)[1]
    downloaded = client.get(f"/public/data-exports/{token}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    assert downloaded.headers["cache-control"] == "no-store"

    archive = read_zip(downloaded.content)
    names = archive.namelist()
    assert "README.txt" in names and "data/clients.csv" in names and "data/tenants.csv" in names
    rows = list(csv.DictReader(io.StringIO(archive.read("data/clients.csv").decode("utf-8-sig"))))
    assert [r["first_name"] for r in rows] == ["Dana"]
    assert any(n.startswith(f"client_documents/{dana}/") for n in names)
    assert any(n.endswith("terms.pdf") and archive.read(n) == PDF for n in names)
    # Secrets and the export files themselves stay out.
    assert "data/tenant_integrations.csv" not in names and "data/data_exports.csv" not in names
    for name in names:
        if name.startswith("data/"):
            header = archive.read(name).decode("utf-8-sig").splitlines()[0].lower()
            assert "token" not in header and "password" not in header, name

    with engine.connect() as connection:
        actions = set(
            connection.execute(
                text("SELECT action FROM app.audit_log WHERE action LIKE 'business.export%'")
            ).scalars()
        )
    assert {"business.export_requested", "business.exported", "business.export_link"} <= actions


def test_export_is_only_for_the_owner_and_stays_in_the_business(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    manager = uuid4()
    add_member(engine, studio["tenant_id"], manager, "manager")
    denied = client.post(
        "/tenants/current/data-exports", headers=auth(manager, studio["tenant_id"])
    )
    assert denied.status_code == 403

    other_owner = uuid4()
    other = client.post("/tenants", json={**studio_payload()}, headers=auth(other_owner)).json()
    other_headers = auth(other_owner, other["id"])
    client.post("/clients", json={"first_name": "Secret"}, headers=other_headers)
    client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"])
    client.post("/tenants/current/data-exports", headers=studio["headers"])
    [export] = client.get("/tenants/current/data-exports", headers=studio["headers"]).json()
    url = client.post(
        f"/tenants/current/data-exports/{export['id']}/link", headers=studio["headers"]
    ).json()["url"]
    archive = read_zip(client.get(f"/public/data-exports/{url.rsplit('/', 1)[1]}").content)
    assert b"Secret" not in archive.read("data/clients.csv")
    # Another business can't ask for this export's link.
    assert (
        client.post(
            f"/tenants/current/data-exports/{export['id']}/link", headers=other_headers
        ).status_code
        == 404
    )


def studio_payload() -> dict:
    from tests.conftest import STUDIO

    return dict(STUDIO)


def test_a_forged_or_expired_export_link_is_refused(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    client.post("/tenants/current/data-exports", headers=headers)
    [export] = client.get("/tenants/current/data-exports", headers=headers).json()
    url = client.post(f"/tenants/current/data-exports/{export['id']}/link", headers=headers).json()[
        "url"
    ]
    token = url.rsplit("/", 1)[1]
    assert client.get(f"/public/data-exports/{token}x").status_code == 404
    assert client.get("/public/data-exports/nonsense").status_code == 404
    with engine.begin() as connection:
        connection.execute(text("UPDATE app.data_exports SET expires_at = now() - interval '1 h'"))
    assert client.get(f"/public/data-exports/{token}").status_code == 404
    with engine.begin() as connection:
        assert jobs.purge_expired_exports(connection) == 1


def test_a_closed_business_can_still_export_its_data(client: TestClient, studio: dict) -> None:
    close(client, studio)
    started = client.post("/tenants/current/data-exports", headers=studio["headers"])
    assert started.status_code == 202, started.text
    [export] = client.get("/tenants/current/data-exports", headers=studio["headers"]).json()
    assert export["status"] == "ready"


def test_platform_invoices_outlive_the_deleted_business(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    end_trial(engine, studio["tenant_id"], 40)
    with engine.begin() as connection:
        assert bill_businesses(connection, datetime.now(UTC)) >= 1
    with engine.connect() as connection:
        before = (
            connection.execute(
                text("SELECT business_name FROM app.platform_invoices WHERE tenant_id = :t"),
                {"t": studio["tenant_id"]},
            )
            .scalars()
            .all()
        )
    assert before and set(before) == {"Studio Flow"}

    close(client, studio)
    backdate(engine, studio["tenant_id"], 91)
    with engine.begin() as connection:
        assert jobs.delete_closed_businesses(connection, apply=True)["businesses"] == 1
    with engine.connect() as connection:
        kept = connection.execute(
            text("""
                SELECT tenant_id, business_name FROM app.platform_invoices
                WHERE business_name = 'Studio Flow' AND tenant_id IS NULL
            """)
        ).all()
    assert len(kept) == len(before)


class FakeStorage:
    in_database = False

    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, key: str) -> None:
        self.deleted.append(key)


def test_deleting_a_business_removes_its_files_from_storage(
    client: TestClient, studio: dict, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    dana = client.post("/clients", json={"first_name": "Dana"}, headers=studio["headers"]).json()[
        "id"
    ]
    upload(client, studio["headers"], dana, "terms.pdf")
    key = f"tenants/{studio['tenant_id']}/client_documents/x"
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.client_documents SET storage_key = :k, content = NULL"), {"k": key}
        )
    storage = FakeStorage()

    class Chosen:
        instance = storage

    monkeypatch.setattr(jobs.retention, "choose", lambda *_args, **_kwargs: Chosen())
    close(client, studio)
    backdate(engine, studio["tenant_id"], 91)
    with engine.begin() as connection:
        jobs.delete_closed_businesses(connection, apply=True)
    assert storage.deleted == [key]


def test_deleting_my_account_disconnects_me_and_empties_my_profile(
    client: TestClient, studio: dict, auth: AuthHeaders, engine: Engine
) -> None:
    joined, member_headers = app_member(client, auth, studio)
    assert client.get("/me", headers=member_headers).status_code == 200

    refused = client.request("DELETE", "/me", json={"confirm": False}, headers=member_headers)
    assert refused.status_code == 422
    deleted = client.request("DELETE", "/me", json={"confirm": True}, headers=member_headers)
    assert deleted.status_code == 204, deleted.text

    with engine.connect() as connection:
        user = connection.execute(
            text("SELECT email, full_name, deleted_at FROM app.users WHERE email LIKE 'deleted-%'")
        ).one()
        kept = connection.execute(
            text("SELECT first_name, user_id FROM app.clients WHERE id = :id"),
            {"id": joined["client_id"]},
        ).one()
    assert user.deleted_at is not None and user.full_name is None
    assert kept.first_name and kept.user_id is None  # the business keeps its client record
    # The same sign-in can't come back to life.
    assert client.get("/me", headers=member_headers).status_code == 403


def test_an_owner_of_an_open_business_must_close_it_before_deleting_the_account(
    client: TestClient, studio: dict
) -> None:
    blocked = client.request(
        "DELETE",
        "/me",
        json={"confirm": True},
        headers={"Authorization": studio["headers"]["Authorization"]},
    )
    assert blocked.status_code == 409 and blocked.json()["detail"] == "owns_business"
    close(client, studio)
    done = client.request(
        "DELETE",
        "/me",
        json={"confirm": True},
        headers={"Authorization": studio["headers"]["Authorization"]},
    )
    assert done.status_code == 204
