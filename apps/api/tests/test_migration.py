from datetime import date, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders

FUTURE = date.today() + timedelta(days=40)
SOON = date.today() + timedelta(days=10)

SERVICES = b"Service,Duration,Capacity,Price\nYoga,60,15,80\nPilates,55,12,0\n"
STAFF = b"Name,Email,Role\nNoa Staff,noa@example.com,Trainer\nBad Boss,boss@example.com,Owner\n"
CLIENTS = (
    b"First name,Last name,Phone,Email\n"
    b"Dana,Levi,0501234567,dana@example.com\n"
    b"Yossi,Cohen,0521112233,\n"
)
MEMBERSHIPS = (
    "Client,Phone,Plan,Left,Valid until\n"
    f"Dana Levi,0501234567,10 entries,7,{FUTURE}\n"
    f"Yossi Cohen,,Monthly,,{FUTURE}\n"
    f"Ghost Person,,Monthly,,{FUTURE}\n"
    "Dana Levi,0501234567,Old card,3,2020-01-01\n"
).encode()
APPOINTMENTS = (
    f"Client,Service,Date,Time\nDana Levi,Yoga,{SOON},10:30\nDana Levi,Yoga,2020-01-01,10:30\n"
).encode()


def start(client: TestClient, headers: dict) -> str:
    response = client.post(
        "/migration/sessions", json={"origin": "other", "rights_confirmed": True}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add(client: TestClient, headers: dict, session: str, name: str, content: bytes) -> dict:
    response = client.post(
        f"/migration/sessions/{session}/files", files={"file": (name, content)}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_all(client: TestClient, headers: dict) -> str:
    session = start(client, headers)
    for name, content in (
        ("services.csv", SERVICES),
        ("staff.csv", STAFF),
        ("clients.csv", CLIENTS),
        ("memberships.csv", MEMBERSHIPS),
        ("appointments.csv", APPOINTMENTS),
    ):
        add(client, headers, session, name, content)
    return session


def count(engine: Engine, sql: str) -> int:
    with engine.connect() as connection:
        return connection.execute(text(sql)).scalar_one()


def test_rights_must_be_confirmed(client: TestClient, studio: dict) -> None:
    response = client.post(
        "/migration/sessions",
        json={"origin": "other", "rights_confirmed": False},
        headers=studio["headers"],
    )
    assert response.status_code == 422 and response.json()["detail"] == "rights_not_confirmed"


def test_files_are_recognized_and_kept_in_the_imports_folder(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    session = start(client, studio["headers"])
    kinds = {
        name: add(client, studio["headers"], session, name, content)["kind"]
        for name, content in (
            ("services.csv", SERVICES),
            ("staff.csv", STAFF),
            ("clients.csv", CLIENTS),
            ("memberships.csv", MEMBERSHIPS),
            ("appointments.csv", APPOINTMENTS),
        )
    }
    assert kinds == {
        "services.csv": "services",
        "staff.csv": "staff",
        "clients.csv": "clients",
        "memberships.csv": "memberships",
        "appointments.csv": "appointments",
    }
    with engine.connect() as connection:
        kept = connection.execute(
            text("""
                SELECT count(*), bool_and(f.expires_at IS NOT NULL) FROM app.business_files f
                JOIN app.file_folders d ON d.id = f.folder_id WHERE d.system_key = 'imports'
            """)
        ).one()
    assert kept == (5, True)

    detail = client.get(f"/migration/sessions/{session}", headers=studio["headers"]).json()
    memberships = next(f for f in detail["files"] if f["kind"] == "memberships")
    assert memberships["mapping"] == [
        "client_name", "client_phone", "plan_name", "credits_left", "ends_on"
    ]  # fmt: skip
    assert memberships["columns"][2] == {"name": "Plan", "example": "10 entries"}


def test_dry_run_changes_nothing_and_import_creates_everything(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session = upload_all(client, headers)

    preview = client.post(f"/migration/sessions/{session}/preview", headers=headers).json()
    assert preview["committed"] is False and preview["invitations"] == []
    assert count(engine, "SELECT count(*) FROM app.clients") == 0
    assert count(engine, "SELECT count(*) FROM app.import_batches") == 0

    result = client.post(f"/migration/sessions/{session}/import", headers=headers)
    assert result.status_code == 200, result.text
    report = result.json()
    by_kind = {f["kind"]: f for f in report["files"]}
    assert (by_kind["services"]["ready"], by_kind["services"]["duplicates"]) == (1, 1)
    assert (by_kind["staff"]["ready"], by_kind["staff"]["invalid"]) == (1, 1)
    assert by_kind["clients"]["ready"] == 2
    assert (by_kind["memberships"]["ready"], by_kind["memberships"]["invalid"]) == (2, 1)
    assert by_kind["memberships"]["skipped"] == 1  # the expired card
    assert {issue["code"] for issue in by_kind["memberships"]["issues"]} == {
        "client_not_found", "expired"
    }  # fmt: skip
    assert (by_kind["appointments"]["ready"], by_kind["appointments"]["skipped"]) == (1, 1)
    assert [i["email"] for i in report["invitations"]] == ["noa@example.com"]
    assert report["invitations"][0]["role"] == "staff" and report["invitations"][0]["token"]

    assert count(engine, "SELECT count(*) FROM app.clients") == 2
    assert count(engine, "SELECT count(*) FROM app.services WHERE name = 'Yoga'") == 1
    assert count(engine, "SELECT count(*) FROM app.bookings WHERE status = 'booked'") == 1
    with engine.connect() as connection:
        card = connection.execute(
            text("""
                SELECT e.kind, e.credits, e.ends_on, p.active FROM app.entitlements e
                JOIN app.plans p ON p.id = e.plan_id WHERE e.name = '10 entries'
            """)
        ).one()
    assert card == ("punch_card", 7, FUTURE, False)

    session_state = client.get(f"/migration/sessions/{session}", headers=headers).json()
    assert session_state["status"] == "imported"
    assert session_state["batches"][0]["counts"]["clients"] == 2
    assert session_state["batches"][0]["can_undo"] is True
    again = client.post(f"/migration/sessions/{session}/import", headers=headers)
    assert again.status_code == 409 and again.json()["detail"] == "session_closed"


def test_undo_removes_the_batch_but_keeps_what_was_edited(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session = upload_all(client, headers)
    batch = client.post(f"/migration/sessions/{session}/import", headers=headers).json()["batch_id"]
    dana = next(
        c
        for c in client.get("/clients", headers=headers).json()["items"]
        if c["first_name"] == "Dana"
    )
    client.patch(f"/clients/{dana['id']}", json={"notes": "Edited by hand"}, headers=headers)

    preview = client.post(
        f"/migration/batches/{batch}/undo-preview", json={}, headers=headers
    ).json()
    assert preview["removed"]["client"] == 1 and preview["kept"]["client"] == 1
    assert count(engine, "SELECT count(*) FROM app.clients") == 2  # a preview removes nothing

    undone = client.post(f"/migration/batches/{batch}/undo", json={}, headers=headers).json()
    assert undone["removed"]["booking"] == 1 and undone["removed"]["entitlement"] == 2
    assert undone["kept"] == {
        "booking": 0, "session": 0, "entitlement": 0, "plan": 0, "invitation": 0, "service": 0,
        "client": 1,
    }  # fmt: skip
    assert count(engine, "SELECT count(*) FROM app.clients") == 1
    assert count(engine, "SELECT count(*) FROM app.services") == 1  # Pilates from the fixture
    assert count(engine, "SELECT count(*) FROM app.invitations") == 0

    final = client.post(
        f"/migration/batches/{batch}/undo", json={"include_edited": True}, headers=headers
    ).json()
    assert final["removed"]["client"] == 1
    assert count(engine, "SELECT count(*) FROM app.clients") == 0
    state = client.get(f"/migration/sessions/{session}", headers=headers).json()
    assert state["batches"][0]["status"] == "undone"
    assert (
        client.post(f"/migration/batches/{batch}/undo", json={}, headers=headers).status_code == 409
    )


def test_data_added_after_the_import_blocks_its_undo(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    headers = studio["headers"]
    session = upload_all(client, headers)
    batch = client.post(f"/migration/sessions/{session}/import", headers=headers).json()["batch_id"]
    yossi = next(
        c
        for c in client.get("/clients", headers=headers).json()["items"]
        if c["first_name"] == "Yossi"
    )
    client.post(
        f"/clients/{yossi['id']}/notes", json={"body": "Asked about the summer"}, headers=headers
    )

    undone = client.post(
        f"/migration/batches/{batch}/undo", json={"include_edited": True}, headers=headers
    ).json()

    assert undone["kept"]["client"] == 1  # the note hangs on Yossi, so he stays
    assert count(engine, "SELECT count(*) FROM app.client_notes") == 1


def test_undo_window_closes_after_14_days(client: TestClient, studio: dict, engine: Engine) -> None:
    headers = studio["headers"]
    session = upload_all(client, headers)
    batch = client.post(f"/migration/sessions/{session}/import", headers=headers).json()["batch_id"]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.import_batches SET undo_until = now() - interval '1 s'")
        )

    response = client.post(f"/migration/batches/{batch}/undo", json={}, headers=headers)

    assert response.status_code == 409 and response.json()["detail"] == "undo_closed"


def test_mapping_can_be_corrected_and_bad_input_is_rejected(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    session = start(client, headers)
    unknown = add(client, headers, session, "mystery.csv", b"Alpha,Beta\n1,2\n")
    assert unknown["kind"] is None
    nothing = client.post(f"/migration/sessions/{session}/import", headers=headers)
    assert nothing.json()["detail"] == "unmapped_file"

    fixed = client.put(
        f"/migration/sessions/{session}/files/{unknown['id']}",
        json={"kind": "services", "mapping": ["name", "capacity"]},
        headers=headers,
    )
    assert fixed.status_code == 200 and fixed.json()["mapping"] == ["name", "capacity"]
    wrong = client.put(
        f"/migration/sessions/{session}/files/{unknown['id']}",
        json={"mapping": ["name", "role"]},
        headers=headers,
    )
    assert wrong.json()["detail"] == "invalid_mapping"
    assert (
        client.post(
            f"/migration/sessions/{session}/files",
            files={"file": ("x.csv", b"A\n")},
            headers=headers,
        ).json()["detail"]
        == "empty_file"
    )

    removed = client.delete(f"/migration/sessions/{session}/files/{unknown['id']}", headers=headers)
    assert removed.status_code == 204
    assert (
        client.post(f"/migration/sessions/{session}/preview", headers=headers).json()["detail"]
        == "no_files"
    )


def test_other_businesses_and_staff_are_kept_out(
    client: TestClient, studio: dict, auth: AuthHeaders
) -> None:
    session = start(client, studio["headers"])
    coach = auth(studio["coach"], studio["tenant_id"])
    assert client.get("/migration/sessions", headers=coach).status_code == 403

    stranger = uuid4()
    tenant = UUID(client.post("/tenants", json=STUDIO, headers=auth(stranger)).json()["id"])
    theirs = auth(stranger, tenant)
    assert client.get(f"/migration/sessions/{session}", headers=theirs).status_code == 404
    assert client.get("/migration/sessions", headers=theirs).json() == []
