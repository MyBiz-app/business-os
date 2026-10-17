"""The business's files area (round 6, F1): system folders, per-folder permissions, archive-only
retention, sealed folders, a folder ZIP, "My documents" and the expiring imports folder."""

import io
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.files import purge_expired_files, store_file, system_folder_id
from tests.conftest import AuthHeaders, add_member

PDF = b"%PDF-1.4 test"


def folders(client: TestClient, headers: dict) -> dict:
    found = client.get("/files/folders", headers=headers)
    assert found.status_code == 200, found.text
    return {f["system_key"] or f["name"]: f for f in found.json()}


def upload(client: TestClient, headers: dict, folder_id: str, name: str = "a.pdf", **data):
    return client.post(
        "/files",
        files={"file": (name, PDF, "application/pdf")},
        data={"folder_id": folder_id, **data},
        headers=headers,
    )


def test_system_folders_and_permissions(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner = studio["headers"]
    mine = folders(client, owner)
    assert set(mine) == {"payroll", "employees", "business_docs", "imports", "general"}
    assert mine["payroll"]["can_upload"] is False and mine["general"]["can_upload"] is True

    # A front desk member opens nothing; a manager opens all but the payslips.
    desk, manager = uuid4(), uuid4()
    for user, role in (
        (desk, "front_desk"),
        (manager, "manager"),
    ):
        add_member(engine, studio["tenant_id"], user, role)
    tenant = studio["tenant_id"]
    assert folders(client, auth(desk, tenant)) == {}
    # Managers hold payroll.read, business.settings and staff.manage, so they see every folder.
    assert set(folders(client, auth(manager, tenant))) == {
        "payroll",
        "employees",
        "business_docs",
        "imports",
        "general",
    }

    # Uploading: the folder's own rule decides.
    assert upload(client, owner, mine["payroll"]["id"]).status_code == 403
    assert upload(client, auth(desk, tenant), mine["general"]["id"]).status_code == 404
    made = upload(client, auth(manager, tenant), mine["general"]["id"])
    assert made.status_code == 201, made.text
    # The folder is hidden for those without its permission, files by id included.
    hidden = client.get(f"/files/{made.json()['id']}/file", headers=auth(desk, tenant))
    assert hidden.status_code == 404
    assert (
        client.get(
            f"/files?folder_id={mine['payroll']['id']}", headers=auth(desk, tenant)
        ).status_code
        == 404
    )


def test_custom_folders_archive_and_delete(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    general = folders(client, owner)["general"]
    sub = client.post(
        "/files/folders", json={"name": "Contracts", "parent_id": general["id"]}, headers=owner
    )
    assert sub.status_code == 201, sub.text
    again = client.post(
        "/files/folders", json={"name": "contracts", "parent_id": general["id"]}, headers=owner
    )
    assert again.status_code == 409
    file = upload(client, owner, sub.json()["id"], name="lease.pdf").json()
    assert (
        client.get(f"/files?folder_id={sub.json()['id']}", headers=owner).json()[0]["name"]
        == "lease.pdf"
    )
    download = client.get(f"/files/{file['id']}/file", headers=owner)
    assert download.content == PDF and "lease.pdf" in download.headers["content-disposition"]

    # Archive and bring back; a folder with files can't be removed, an empty one can.
    archived = client.patch(f"/files/{file['id']}", json={"archived": True}, headers=owner)
    assert archived.json()["archived_at"] is not None
    assert client.get(f"/files?folder_id={sub.json()['id']}", headers=owner).json() == []
    assert client.get(f"/files?folder_id={sub.json()['id']}&archived=true", headers=owner).json()
    assert client.delete(f"/files/folders/{sub.json()['id']}", headers=owner).status_code == 409
    assert client.delete(f"/files/{file['id']}", headers=owner).status_code == 204
    assert client.delete(f"/files/folders/{sub.json()['id']}", headers=owner).status_code == 204
    system = client.delete(f"/files/folders/{general['id']}", headers=owner)
    assert system.status_code == 409


def test_accounting_papers_are_archive_only(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    docs = folders(client, owner)["business_docs"]
    file = upload(client, owner, docs["id"], name="license.pdf").json()
    assert client.delete(f"/files/{file['id']}", headers=owner).status_code == 409
    assert (
        client.patch(f"/files/{file['id']}", json={"archived": True}, headers=owner).status_code
        == 200
    )


def test_sensitive_folders_are_sealed_and_my_documents(
    client: TestClient, studio: dict, engine: Engine, auth: AuthHeaders
) -> None:
    owner = studio["headers"]
    tenant = studio["tenant_id"]
    employee = uuid4()
    add_member(engine, tenant, employee, "staff")
    employees = folders(client, owner)["employees"]
    made = upload(client, owner, employees["id"], name="form-101.pdf", owner_user_id=str(employee))
    assert made.status_code == 201, made.text
    with engine.begin() as connection:
        stored = connection.execute(
            text("SELECT content, encrypted FROM app.business_files WHERE id = :id"),
            {"id": made.json()["id"]},
        ).one()
    assert stored.encrypted and PDF not in bytes(stored.content)

    theirs = auth(employee, tenant)
    assert folders(client, theirs) == {}  # no folder, but their own papers
    mine = client.get("/files/mine", headers=theirs).json()
    assert [f["name"] for f in mine] == ["form-101.pdf"]
    assert client.get(f"/files/{mine[0]['id']}/file", headers=theirs).content == PDF
    other = client.get("/files/mine", headers=auth(uuid4(), tenant))
    assert other.status_code in (403, 404) or other.json() == []
    # They can't archive it: that is the folder's rule.
    assert (
        client.patch(f"/files/{mine[0]['id']}", json={"archived": True}, headers=theirs).status_code
        == 403
    )


def test_zip_of_a_folder(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    general = folders(client, owner)["general"]
    sub = client.post(
        "/files/folders", json={"name": "Menus", "parent_id": general["id"]}, headers=owner
    ).json()
    upload(client, owner, general["id"], name="one.pdf")
    upload(client, owner, sub["id"], name="two.pdf")
    done = client.get(f"/files/folders/{general['id']}/zip", headers=owner)
    assert done.status_code == 200 and done.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(done.content)).namelist()
    assert len(names) == 2 and any("Menus" in n and "two.pdf" in n for n in names)


def test_imports_expire_and_count_toward_space(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    tenant = studio["tenant_id"]
    with engine.begin() as connection:
        connection.execute(
            text(
                "SELECT set_config('app.tenant_id', :t, true), set_config('app.user_id', :u, true)"
            ),
            {"t": str(tenant), "u": str(studio["owner"])},
        )
        folder = system_folder_id(connection, tenant, "imports")
        row = store_file(
            connection, tenant, folder, name="clients.csv", content=b"a,b", content_type="text/csv"
        )
        assert row["expires_at"] is not None
        used = connection.execute(text("SELECT app.storage_used()")).scalar_one()
        assert used >= 3
        connection.execute(
            text("UPDATE app.business_files SET expires_at = now() - interval '1 day'")
        )
        assert purge_expired_files(connection) == 1


def test_a_signed_link_opens_a_sealed_file(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    employees = folders(client, owner)["employees"]
    made = upload(client, owner, employees["id"], name="note.pdf").json()
    link = client.post(f"/files/{made['id']}/link", headers=owner)
    assert link.status_code == 200, link.text
    path = "/public/business-files/" + link.json()["url"].rsplit("/", 1)[1]
    opened = client.get(path)
    assert opened.status_code == 200 and opened.content == PDF
    assert client.get("/public/business-files/forged").status_code == 404
