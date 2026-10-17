import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.core import signed_links
from app.core.config import get_settings
from app.core.identity import number_hash
from app.providers import secrets
from app.secrets_rotation import rotate_secrets
from tests.test_identities import VALID

OLD, NEW = Fernet.generate_key().decode(), Fernet.generate_key().decode()


@pytest.fixture
def use_keys(monkeypatch: pytest.MonkeyPatch):
    """Sets the platform's keys (generated, never the real ones) for the rest of the test."""

    def use(keys: str | None, single: str | None = None, id_hash: str | None = None) -> None:
        for name, value in (
            ("API_SECRETS_KEYS", keys),
            ("API_SECRETS_KEY", single),
            ("API_ID_HASH_KEY", id_hash),
        ):
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        get_settings.cache_clear()

    yield use
    monkeypatch.undo()
    get_settings.cache_clear()


def test_the_newest_key_encrypts_and_every_listed_key_decrypts(use_keys) -> None:
    use_keys(None, single=OLD)
    blob = secrets.encrypt({"token": "t"})
    assert secrets.is_current(blob)

    use_keys(f"{NEW},{OLD}")
    assert secrets.decrypt(blob) == {"token": "t"}  # still opens with the old key
    assert not secrets.is_current(blob)
    rotated = secrets.rotate(blob)
    assert secrets.is_current(rotated) and secrets.decrypt(rotated) == {"token": "t"}

    use_keys(NEW)  # the old key retired
    assert secrets.decrypt(rotated) == {"token": "t"}
    with pytest.raises(secrets.SecretsKeyMissing):
        secrets.decrypt(blob)


def test_a_single_key_setting_still_works_and_the_list_wins(use_keys) -> None:
    use_keys(None, single=OLD)
    assert get_settings().secret_keys() == [OLD]
    use_keys(f" {NEW} , {OLD} ", single=OLD)
    assert get_settings().secret_keys() == [NEW, OLD]


def test_signed_links_survive_a_rotation(use_keys) -> None:
    use_keys(None, single=OLD)
    link = signed_links.sign("file:1")
    use_keys(f"{NEW},{OLD}")
    assert signed_links.verify(link) == "file:1"
    assert signed_links.verify(signed_links.sign("file:2")) == "file:2"
    use_keys(NEW)  # a link signed with the retired key no longer opens
    assert signed_links.verify(link) is None


def test_the_id_hash_stays_while_a_newer_key_comes_in_front(use_keys) -> None:
    use_keys(None, single=OLD)
    before = number_hash("11111111-1111-1111-1111-111111111111", VALID)  # type: ignore[arg-type]
    use_keys(f"{NEW},{OLD}")
    assert number_hash("11111111-1111-1111-1111-111111111111", VALID) == before  # type: ignore[arg-type]
    use_keys(NEW, id_hash=OLD)  # pinned before the old key is retired
    assert number_hash("11111111-1111-1111-1111-111111111111", VALID) == before  # type: ignore[arg-type]


def test_rotate_secrets_re_encrypts_stored_values(
    client: TestClient, engine: Engine, studio: dict, use_keys
) -> None:
    use_keys(None, single=OLD)
    headers, coach = studio["headers"], studio["coach"]
    body = {"id_type": "il_id", "number": VALID}
    assert client.put(f"/staff/{coach}/identity", json=body, headers=headers).status_code == 200
    with engine.begin() as connection:
        stored_hash = connection.execute(text("SELECT id_hash FROM app.person_identities")).scalar()

    use_keys(f"{NEW},{OLD}")
    with engine.begin() as connection:
        dry = rotate_secrets(connection)
    assert dry["person_identities.id_number_encrypted"] == {"stale": 1, "rotated": 0}

    with engine.begin() as connection:
        done = rotate_secrets(connection, apply=True)
    assert done["person_identities.id_number_encrypted"] == {"stale": 1, "rotated": 1}
    with engine.begin() as connection:
        again = rotate_secrets(connection, apply=True)
    assert all(part["stale"] == 0 for part in again.values())  # nothing left; safe to repeat

    use_keys(NEW, id_hash=OLD)  # the old key retired
    revealed = client.post(f"/staff/{coach}/identity/reveal", headers=headers)
    assert revealed.json() == {"number": VALID}
    with engine.begin() as connection:
        assert connection.execute(text("SELECT id_hash FROM app.person_identities")).scalar() == (
            stored_hash
        )


def test_rotate_secrets_covers_sealed_files(engine: Engine, studio: dict, use_keys) -> None:
    use_keys(None, single=OLD)
    sealed = secrets.encrypt_bytes(b"payslip bytes")
    with engine.begin() as connection:
        folder = connection.execute(
            text("""
                INSERT INTO app.file_folders (tenant_id, name, sensitive)
                VALUES (:t, 'Payslips', true) RETURNING id
            """),
            {"t": studio["tenant_id"]},
        ).scalar()
        connection.execute(
            text("""
                INSERT INTO app.business_files
                    (tenant_id, folder_id, name, content_type, size, content, encrypted)
                VALUES (:t, :f, 'p.pdf', 'application/pdf', 13, :c, true)
            """),
            {"t": studio["tenant_id"], "f": folder, "c": sealed},
        )
    use_keys(f"{NEW},{OLD}")
    with engine.begin() as connection:
        report = rotate_secrets(connection, apply=True)
    assert report["business_files"] == {"stale": 1, "rotated": 1}
    use_keys(NEW)
    with engine.begin() as connection:
        content = connection.execute(text("SELECT content FROM app.business_files")).scalar()
    assert secrets.decrypt_bytes(bytes(content)) == b"payslip bytes"
