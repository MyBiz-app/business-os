"""The business 360 card in the MyBiz console (K2)."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders, make_staff
from tests.test_billing import end_trial


def staff(engine: Engine, auth: AuthHeaders, *permissions: str) -> tuple[dict, str]:
    user = uuid4()
    email = make_staff(engine, user, "employee", tuple(permissions))
    return auth(user), email


def test_the_card_needs_console_permissions(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    tenant = studio["tenant_id"]
    for path in ("card", "notes", "timeline"):
        denied = client.get(f"/platform/businesses/{tenant}/{path}", headers=studio["headers"])
        assert denied.status_code == 403
    assert client.get("/platform/trials-ending", headers=studio["headers"]).status_code == 403

    reader, _ = staff(engine, auth, "businesses.read")
    assert client.get(f"/platform/businesses/{tenant}/card", headers=reader).status_code == 200
    body = {"body": "Called the owner"}
    assert (
        client.post(f"/platform/businesses/{tenant}/notes", json=body, headers=reader).status_code
        == 403
    )
    card = {"tags": ["vip"], "account_owner": None}
    assert (
        client.put(f"/platform/businesses/{tenant}/card", json=card, headers=reader).status_code
        == 403
    )

    actor, _ = staff(engine, auth, "businesses.read", "businesses.act")
    assert (
        client.post(f"/platform/businesses/{tenant}/notes", json=body, headers=actor).status_code
        == 201
    )
    assert (
        client.put(f"/platform/businesses/{tenant}/card", json=card, headers=actor).status_code
        == 200
    )


def test_unknown_business_is_not_found(
    client: TestClient, engine: Engine, auth: AuthHeaders
) -> None:
    headers, _ = staff(engine, auth, "businesses.read", "businesses.act")
    missing = uuid4()
    assert client.get(f"/platform/businesses/{missing}/card", headers=headers).status_code == 404
    assert (
        client.get(f"/platform/businesses/{missing}/timeline", headers=headers).status_code == 404
    )
    answer = client.post(
        f"/platform/businesses/{missing}/notes", json={"body": "x"}, headers=headers
    )
    assert answer.status_code == 404


def test_notes_are_kept_with_their_author(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    tenant = studio["tenant_id"]
    headers, email = staff(engine, auth, "businesses.read", "businesses.act")
    url = f"/platform/businesses/{tenant}/notes"
    assert client.get(url, headers=headers).json() == []
    assert client.post(url, json={"body": "   "}, headers=headers).status_code == 422
    client.post(url, json={"body": "First call"}, headers=headers)
    notes = client.post(url, json={"body": "  Wants a second branch "}, headers=headers).json()
    assert [n["body"] for n in notes] == ["Wants a second branch", "First call"]
    assert {n["author_email"] for n in notes} == {email}
    # Internal: the business itself cannot read them.
    assert client.get(url, headers=studio["headers"]).status_code == 403


def test_tags_and_account_owner(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    tenant = studio["tenant_id"]
    headers, email = staff(engine, auth, "businesses.read", "businesses.act")
    url = f"/platform/businesses/{tenant}/card"
    empty = client.get(url, headers=headers).json()
    assert empty["tags"] == [] and empty["account_owner"] is None

    saved = client.put(
        url,
        json={"tags": [" VIP ", "vip", "Gym", ""], "account_owner": email.upper()},
        headers=headers,
    ).json()
    assert saved["tags"] == ["gym", "vip"] and saved["account_owner"] == email
    assert saved["updated_by"] == email

    bad_owner = client.put(
        url, json={"tags": [], "account_owner": "nobody@example.com"}, headers=headers
    )
    assert bad_owner.status_code == 422
    long_tag = client.put(url, json={"tags": ["x" * 31], "account_owner": None}, headers=headers)
    assert long_tag.status_code == 422
    assert client.put(url, json={"tags": ["a"] * 13}, headers=headers).status_code == 422
    cleared = client.put(url, json={"tags": [], "account_owner": ""}, headers=headers).json()
    assert cleared["tags"] == [] and cleared["account_owner"] is None


def test_timeline_joins_what_the_console_knows(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    tenant = studio["tenant_id"]
    everything, _ = staff(
        engine, auth, "businesses.read", "businesses.act", "billing.manage", "inbox.manage"
    )
    base = f"/platform/businesses/{tenant}"
    client.post(f"{base}/notes", json={"body": "Interested in more modules"}, headers=everything)
    client.post(f"{base}/trial", json={"days": 7}, headers=everything)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO app.contact_requests (name, email, message, locale, tenant_id) "
                "VALUES ('Dana', 'd@example.com', 'help', 'he', :t)"
            ),
            {"t": tenant},
        )
    events = client.get(f"{base}/timeline", headers=everything).json()
    kinds = [e["kind"] for e in events]
    assert {"signup", "trial_ends", "note", "change", "request"} <= set(kinds)
    assert [e["at"] for e in events] == sorted((e["at"] for e in events), reverse=True)
    change = next(e for e in events if e["kind"] == "change")
    assert (
        change["details"]["action"] == "business.trial_extended" and change["details"]["days"] == 7
    )
    # The note-added entry of the console log is not repeated next to the note itself.
    assert all(e["details"].get("action") != "business.note_added" for e in events)

    # Without billing and inbox rights those parts are left out.
    reader, _ = staff(engine, auth, "businesses.read")
    limited = {e["kind"] for e in client.get(f"{base}/timeline", headers=reader).json()}
    assert "request" not in limited and "invoice" not in limited and "note" in limited


def test_trials_ending_soon(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    tenant = studio["tenant_id"]
    headers, _ = staff(engine, auth, "businesses.read")
    [row] = client.get("/platform/trials-ending", headers=headers).json() or [None]
    assert row is None  # a new business has two weeks or more left

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.tenants SET trial_ends_at = now() + interval '3 days' WHERE id = :t"),
            {"t": tenant},
        )
    [row] = client.get("/platform/trials-ending", headers=headers).json()
    assert row["tenant_id"] == str(tenant) and row["has_card"] is False
    assert row["owner_email"] and row["account_owner"] is None
    assert client.get("/platform/trials-ending?days=1", headers=headers).json() == []
    assert client.get("/platform/trials-ending?days=31", headers=headers).status_code == 422

    # Ended two days ago still shows (to win it back); ended long ago or closed does not.
    end_trial(engine, tenant, days_ago=2)
    assert len(client.get("/platform/trials-ending", headers=headers).json()) == 1
    end_trial(engine, tenant, days_ago=10)
    assert client.get("/platform/trials-ending", headers=headers).json() == []
