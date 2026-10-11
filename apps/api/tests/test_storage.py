"""Object storage for documents (T80): Supabase Storage's HTTP API, faked in memory."""

import json
import urllib.error
from email.message import Message
from io import BytesIO
from urllib.parse import unquote, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app import jobs
from app.providers import choice, storage
from app.providers.registry import REGISTRY
from tests.test_bookings import new_client
from tests.test_client_app import join, join_code
from tests.test_documents_time import PDF, upload

SETTINGS = {"url": "https://project.supabase.co", "service_key": "secret", "bucket": "files"}


class FakeStore:
    """Answers like Supabase Storage: upload, authenticated download, delete, sign."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.down = False

    def urlopen(self, request, timeout: float):
        assert request.get_header("Authorization") == "Bearer secret"
        assert request.get_header("Apikey") == "secret"
        if self.down:
            raise urllib.error.HTTPError(request.full_url, 503, "down", Message(), None)
        path = unquote(urlparse(request.full_url).path).removeprefix("/storage/v1/")
        method = request.get_method()
        if method == "POST" and path.startswith("object/sign/files/"):
            key = path.removeprefix("object/sign/files/")
            assert json.loads(request.data)["expiresIn"] == 600
            return BytesIO(json.dumps({"signedURL": f"/object/sign/files/{key}?token=t"}).encode())
        if method == "POST" and path.startswith("object/files/"):
            assert request.get_header("X-upsert") == "true"
            self.objects[path.removeprefix("object/files/")] = request.data
            return BytesIO(b"{}")
        if method == "GET" and path.startswith("object/authenticated/files/"):
            key = path.removeprefix("object/authenticated/files/")
            if key not in self.objects:
                raise urllib.error.HTTPError(request.full_url, 400, "missing", Message(), None)
            return BytesIO(self.objects[key])
        if method == "DELETE" and path == "object/files":
            for key in json.loads(request.data)["prefixes"]:
                self.objects.pop(key, None)
            return BytesIO(b"[]")
        raise AssertionError(f"unexpected {method} {path}")


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr(storage.urllib.request, "urlopen", fake.urlopen)
    original = choice.platform_default

    def platform_default(capability: str) -> tuple[str, dict[str, str]]:
        return ("supabase", SETTINGS) if capability == "storage" else original(capability)

    monkeypatch.setattr(choice, "platform_default", platform_default)
    return fake


def stored(engine: Engine, document_id: str) -> tuple[bytes | None, str | None]:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT content, storage_key FROM app.client_documents WHERE id = :id"),
            {"id": document_id},
        ).one()
    return row[0], row[1]


def test_supabase_provider_is_registered_with_a_secret_key() -> None:
    info = REGISTRY.get("storage", "supabase")
    assert {f.key: f.secret for f in info.fields} == {
        "url": False,
        "service_key": True,
        "bucket": False,
    }
    assert info.factory({"url": "https://x.supabase.co/", "service_key": "k"}).bucket == "files"


def test_documents_live_in_the_object_store_under_their_business(
    client: TestClient, studio: dict, engine: Engine, store: FakeStore
) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    document = upload(client, headers, dana, "contract.pdf")

    content, key = stored(engine, document["id"])
    assert content is None
    assert key == f"tenants/{studio['tenant_id']}/documents/{dana}/{document['id']}"
    assert store.objects[key] == PDF
    downloaded = client.get(f"/documents/{document['id']}/file", headers=headers)
    assert downloaded.status_code == 200 and downloaded.content == PDF

    assert client.delete(f"/documents/{document['id']}", headers=headers).status_code == 204
    assert store.objects == {}


def test_signed_link_sends_the_phone_straight_to_the_store(
    client: TestClient, studio: dict, auth, store: FakeStore
) -> None:
    user = uuid4()
    joined = join(client, auth, user, join_code(client, studio))
    shared = upload(client, studio["headers"], joined["client_id"], "report.pdf", shared=True)
    link = client.post(
        f"/client/documents/{shared['id']}/link", headers=auth(user, studio["tenant_id"])
    )
    path = link.json()["url"].split("8000", 1)[1]
    opened = client.get(path, follow_redirects=False)
    assert opened.status_code == 302
    location = opened.headers["location"]
    assert location.startswith("https://project.supabase.co/storage/v1/object/sign/files/tenants/")
    assert location.endswith(f"/{shared['id']}?token=t")


def test_a_store_outage_saves_nothing(
    client: TestClient, studio: dict, engine: Engine, store: FakeStore
) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    store.down = True
    failed = client.post(
        f"/clients/{dana}/documents",
        files={"file": ("a.pdf", PDF, "application/pdf")},
        headers=headers,
    )
    assert failed.status_code == 503 and failed.json()["detail"] == "storage_down"
    assert client.get(f"/clients/{dana}/documents", headers=headers).json() == []


def test_an_unsaved_row_takes_its_object_with_it(
    client: TestClient, studio: dict, store: FakeStore
) -> None:
    missing_client = uuid4()  # not a client of this business: the row is refused
    created = client.post(
        f"/clients/{missing_client}/documents",
        files={"file": ("a.pdf", PDF, "application/pdf")},
        headers=studio["headers"],
    )
    assert created.status_code == 404
    assert store.objects == {}


def test_move_files_job_empties_the_database_in_batches(
    client: TestClient, studio: dict, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    first = upload(client, headers, dana, "a.pdf")  # kept in the database (default provider)
    second = upload(client, headers, dana, "b.pdf")
    assert stored(engine, first["id"])[0] is not None

    with engine.begin() as connection:
        assert "nothing to move" in jobs.move_files(connection)

    fake = FakeStore()
    monkeypatch.setattr(storage.urllib.request, "urlopen", fake.urlopen)
    original = choice.platform_default
    monkeypatch.setattr(
        choice,
        "platform_default",
        lambda c: ("supabase", SETTINGS) if c == "storage" else original(c),
    )
    with engine.begin() as connection:
        assert jobs.move_files(connection, batch=1) == {"moved": 1, "left": 1}
    with engine.begin() as connection:
        assert jobs.move_files(connection) == {"moved": 1, "left": 0}

    for document in (first, second):
        content, key = stored(engine, document["id"])
        assert content is None and fake.objects[key] == PDF
        downloaded = client.get(f"/documents/{document['id']}/file", headers=headers)
        assert downloaded.content == PDF
