import io
import json
from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import Engine, text

from app.catalog.importing import parse_rows, read_table, suggest_mapping
from tests.conftest import AuthHeaders

HEBREW_CSV = (
    'שם פרטי,שם משפחה,טלפון,דוא"ל,תאריך לידה,סטטוס\n'
    "דנה,לוי,050-1234567,dana@example.com,14/03/1990,פעילה\n"
    "יוסי,כהן,0521112233,,1985-07-01,ליד\n"
    ",בלי שם,0539998877,,,\n"
    "נועה,ברק,+972 54 555 6666,not-an-email,,\n"
)


def upload(client: TestClient, headers: dict, content: bytes, name: str = "clients.csv", **form):
    data = {key: json.dumps(value) if key == "mapping" else str(value).lower()
            for key, value in form.items()}  # fmt: skip
    return client.post(
        "/clients/import", files={"file": (name, content)}, data=data, headers=headers
    )


def test_hebrew_windows_csv_is_detected_and_previewed(client: TestClient, studio: dict) -> None:
    response = upload(client, studio["headers"], HEBREW_CSV.encode("cp1255"))

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mapping"] == [
        "first_name", "last_name", "phone", "email", "date_of_birth", "status",
    ]  # fmt: skip
    assert result["rows"] == 4
    assert result["ready"] == 2 and result["invalid"] == 2 and result["duplicates"] == 0
    assert result["imported"] is False
    codes = {(issue["line"], issue["code"]) for issue in result["issues"]}
    assert codes == {(4, "missing_name"), (5, "invalid_email")}
    assert client.get("/clients", headers=studio["headers"]).json()["total"] == 0  # preview only


def test_import_creates_clients_and_skips_duplicates(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    client.post(
        "/clients",
        json={"first_name": "Existing", "phone": "054-555-6666"},
        headers=studio["headers"],
    )
    content = (
        b"Name,Email,Mobile\n"
        b"Dana Levi,Dana@Example.com,0501234567\n"
        b"Dana L,dana@example.com,\n"  # same email as the row above
        b"Noa Barak,,+972-54-555-6666\n"  # same phone as the existing client
        b"Avi,,\n"
    )

    result = upload(client, studio["headers"], content, commit=True, source="website").json()

    assert result["imported"] is True
    assert (result["ready"], result["duplicates"], result["invalid"]) == (2, 2, 0)
    clients = client.get("/clients", headers=studio["headers"]).json()["items"]
    dana = next(c for c in clients if c["first_name"] == "Dana")
    assert dana["last_name"] == "Levi" and dana["email"] == "Dana@example.com"
    assert dana["source"] == "website" and dana["status"] == "active"
    with engine.connect() as connection:
        details = connection.execute(
            text("SELECT details FROM app.audit_log WHERE action = 'clients.import'")
        ).scalar_one()
    assert details["created"] == 2 and details["duplicates"] == 2

    again = upload(client, studio["headers"], content, commit=True).json()
    assert again["ready"] == 0 and again["imported"] is False


def test_excel_file_with_custom_mapping(client: TestClient, studio: dict) -> None:
    book = Workbook()
    sheet = book.active
    sheet.append(["Client", "Cell", "Born", "Comment"])
    sheet.append(["Maya Raz", 501112222, date(1992, 5, 17), "Knee injury"])
    buffer = io.BytesIO()
    book.save(buffer)

    preview = upload(client, studio["headers"], buffer.getvalue(), name="list.xlsx").json()
    assert preview["mapping"] == ["full_name", "phone", None, None]
    assert preview["examples"] == ["Maya Raz", "501112222", "1992-05-17", "Knee injury"]

    result = upload(
        client,
        studio["headers"],
        buffer.getvalue(),
        name="list.xlsx",
        mapping=["full_name", "phone", "date_of_birth", "notes"],
        commit=True,
    ).json()

    assert result["ready"] == 1
    [maya] = client.get("/clients", headers=studio["headers"]).json()["items"]
    assert maya["phone"] == "0501112222"  # leading zero restored
    assert maya["date_of_birth"] == "1992-05-17" and maya["notes"] == "Knee injury"


def test_bad_files_and_mappings_are_rejected(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    assert upload(client, headers, b"Name\n").json()["detail"] == "empty_file"
    assert upload(client, headers, b"PK\x03\x04broken", name="x.xlsx").json()["detail"] == (
        "unreadable_file"
    )
    duplicate_target = upload(client, headers, b"A,B\nx,y\n", mapping=["email", "email"])
    assert duplicate_target.json()["detail"] == "invalid_mapping"
    wrong_length = upload(client, headers, b"A,B\nx,y\n", mapping=["first_name"])
    assert wrong_length.status_code == 422
    too_big = upload(client, headers, b"Name\n" + b"x" * (2 * 1024 * 1024 + 10))
    assert too_big.json()["detail"] == "file_too_large"


def test_import_needs_clients_write(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    coach = auth(studio["coach"], studio["tenant_id"])
    assert upload(client, coach, b"Name\nDana\n").status_code == 403


def test_import_stays_in_its_business(client: TestClient, studio: dict, auth: AuthHeaders) -> None:
    other_owner = uuid4()
    other = client.post(
        "/tenants",
        json={"name": "Other", "vertical": "fitness", "locale": "en",
              "time_zone": "UTC", "currency": "USD"},
        headers=auth(other_owner),
    ).json()  # fmt: skip
    other_headers = auth(other_owner, other["id"])
    client.post(
        "/clients", json={"first_name": "A", "email": "a@example.com"}, headers=other_headers
    )

    result = upload(client, studio["headers"], b"Name,Email\nA,a@example.com\n", commit=True).json()

    assert result["ready"] == 1  # the other business's client is not a duplicate here
    assert client.get("/clients", headers=other_headers).json()["total"] == 1


def test_parsing_helpers() -> None:
    table = read_table(b"Full Name;Phone\nDana  Levi Cohen;052-1234567\n", "x.csv")
    mapping = suggest_mapping(table[0])
    [row] = parse_rows(table, mapping)
    assert mapping == ["full_name", "phone"]
    assert row.values["first_name"] == "Dana" and row.values["last_name"] == "Levi Cohen"
    assert suggest_mapping(["Name", "First name", "Last name"]) == [
        None, "first_name", "last_name",
    ]  # fmt: skip
