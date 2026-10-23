import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.catalog.terms import TERM_KEYS
from tests.conftest import STUDIO, AuthHeaders

MESSAGES = Path(__file__).parents[3] / "packages" / "i18n" / "messages"


def test_the_renameable_words_are_the_translated_ones() -> None:
    for locale in ("he", "en"):
        sets = json.loads((MESSAGES / f"{locale}.json").read_text(encoding="utf-8"))["terms"]
        for name, words in sets.items():
            # Only the word with a count in it stays fixed.
            assert set(words) - {"sessionsToday"} == set(TERM_KEYS), f"{locale}.{name}"


def business(client: TestClient, auth: AuthHeaders) -> dict[str, str]:
    owner = uuid4()
    tenant = client.post("/tenants", json=STUDIO, headers=auth(owner)).json()
    return auth(owner, tenant["id"])


def test_a_business_starts_with_no_words_of_its_own(client: TestClient, auth: AuthHeaders) -> None:
    headers = business(client, auth)
    assert client.get("/tenants/current", headers=headers).json()["terms_override"] == {}


def test_the_owner_renames_words_and_clients_see_them(
    client: TestClient, auth: AuthHeaders
) -> None:
    headers = business(client, auth)
    saved = client.patch(
        "/tenants/current",
        json={"terms_override": {"he": {"clients": "  חברי   המועדון ", "client": ""}}},
        headers=headers,
    )
    assert saved.status_code == 200
    # Trimmed and tidied; an empty word is dropped (back to the industry's).
    assert saved.json()["terms_override"] == {"he": {"clients": "חברי המועדון"}}
    # A later save replaces the whole set.
    cleared = client.patch("/tenants/current", json={"terms_override": {}}, headers=headers)
    assert cleared.json()["terms_override"] == {}


def test_unknown_words_languages_and_long_texts_are_refused(
    client: TestClient, auth: AuthHeaders
) -> None:
    headers = business(client, auth)

    def save(value: dict) -> tuple[int, str]:
        response = client.patch("/tenants/current", json={"terms_override": value}, headers=headers)
        return response.status_code, response.json().get("detail")

    assert save({"he": {"sessionsToday": "x"}}) == (422, "unknown_term")
    assert save({"fr": {"clients": "x"}}) == (422, "unknown_locale")
    assert save({"he": {"clients": "x" * 61}}) == (422, "term_too_long")


def test_only_settings_managers_change_words(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()
    tenant = client.post("/tenants", json=STUDIO, headers=auth(owner)).json()
    outsider = auth(uuid4(), tenant["id"])
    denied = client.patch(
        "/tenants/current", json={"terms_override": {"he": {"clients": "x"}}}, headers=outsider
    )
    assert denied.status_code in (403, 404)
