# ruff: noqa: F811, F401
"""The console agents' knowledge libraries (slice C3a): documents with versions, search by words in
Hebrew and English, the tool `search_library`, the notes an agent always gets, and the rules (the
team reads, billing.manage changes, a switched-off document is not used, embeddings are off)."""

import importlib.util
import io
import json
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai import embeddings, knowledge, library_fetch
from app.ai.untrusted import unwrap
from tests.conftest import AuthHeaders, make_staff
from tests.test_assistant import FakeProvider, calls, says, use_provider

PRIVACY_HE = """# חוק הגנת הפרטיות

מאגר מידע חייב להיות רשום אצל הרשם כאשר הוא כולל מידע על יותר מ-10,000 אנשים.

## זכות העיון

כל אדם זכאי לעיין במידע שנשמר עליו במאגר מידע.
"""
REFUNDS = """# Refund policy

We refund by card only. Cash refunds are not given.

# Cancellation

A trial can be cancelled at any time before it ends.
"""


def member(engine: Engine, auth: AuthHeaders, *permissions: str, level: str = "employee"):
    user = uuid4()
    make_staff(engine, user, level, tuple(permissions))
    return auth(user)


@pytest.fixture
def editor(engine: Engine, auth: AuthHeaders) -> dict:
    return member(engine, auth, "billing.manage", "inbox.manage", "businesses.read")


def add(client: TestClient, headers: dict, agent: str = "product", **fields):
    body = {"kind": "note", "title": "Refunds", "body": REFUNDS, **fields}
    return client.post(f"/platform/ai/agents/{agent}/library", json=body, headers=headers)


def audit_actions(engine: Engine) -> list[str]:
    with engine.begin() as connection:
        return [
            r.action
            for r in connection.execute(
                text("SELECT action FROM app.platform_audit ORDER BY occurred_at")
            )
        ]


# --- The pure parts ---------------------------------------------------------------------------


def test_text_is_cut_at_headings_into_chunks_that_name_their_section() -> None:
    chunks = knowledge.chunks_of(REFUNDS)
    assert [c["heading"] for c in chunks] == ["Refund policy", "Cancellation"]
    assert "card only" in chunks[0]["content"]


def test_a_long_text_is_cut_into_chunks_of_bounded_size() -> None:
    paragraph = "This sentence is one of many. " * 200  # one paragraph of 6000 characters
    body = "# Long\n\n" + paragraph + "\n\n" + "Short end."
    chunks = knowledge.chunks_of(body)
    assert len(chunks) > 4
    assert all(len(c["content"]) <= knowledge.MAX_CHUNK for c in chunks)
    assert chunks[-1]["content"] == "Short end."


def test_the_words_query_drops_filler_and_tries_hebrew_words_without_their_prefix() -> None:
    query = knowledge.words_query("What is the refund policy?")
    assert query == "refund:* | policy:*"
    hebrew = knowledge.words_query("האם הפרטיות שלי נשמרת")
    assert "הפרטיות:*" in hebrew and "פרטיות:*" in hebrew
    assert knowledge.words_query("the of a") is None
    # No operator can get through: the query is made of words only.
    assert "&" not in (knowledge.words_query("a & b | !c ' ; drop") or "")


def test_files_are_read_as_text() -> None:
    assert knowledge.extract_text("a.txt", "שלום\r\n\r\n\r\n\r\nworld".encode()) == "שלום\n\nworld"
    html = b"<html><body><h1>Title</h1><p>One</p><script>x()</script><p>Two</p></body></html>"
    assert knowledge.extract_text("a.html", html) == "# Title\n\nOne\n\nTwo"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>First &amp; one</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Second</w:t></w:r></w:p></w:body></w:document>",
        )
    assert knowledge.extract_text("a.docx", buffer.getvalue()) == "First & one\n\nSecond"
    with pytest.raises(knowledge.UnsupportedFile, match="unsupported_file"):
        knowledge.extract_text("a.exe", b"MZ")
    with pytest.raises(knowledge.UnsupportedFile, match="empty_file"):
        knowledge.extract_text("a.txt", b"  \n ")
    with pytest.raises(knowledge.UnsupportedFile, match="unreadable_file"):
        knowledge.extract_text("a.pdf", b"not a pdf")
    with pytest.raises(knowledge.UnsupportedFile, match="unreadable_file"):
        knowledge.extract_text("a.docx", b"not a zip")


def test_search_by_meaning_is_off_by_default() -> None:
    assert embeddings.provider() is None


# --- The library in the console ---------------------------------------------------------------


def test_reading_needs_the_team_and_the_agent_and_changing_needs_billing_manage(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict, editor: dict
) -> None:
    path = "/platform/ai/agents/product/library"
    # A business owner is not on MyBiz's team.
    assert client.get(path, headers=studio["headers"]).status_code == 403
    reader = member(engine, auth, "inbox.manage")
    assert client.get(path, headers=reader).status_code == 200
    body = {"kind": "note", "title": "x", "body": "y"}
    assert client.post(path, json=body, headers=reader).status_code == 403
    # A member who may not ask the billing agent may not open its library.
    assert client.get("/platform/ai/agents/billing/library", headers=reader).status_code == 403
    created = add(client, editor)
    assert created.status_code == 201, created.text
    doc = created.json()
    only_reader = member(engine, auth, "inbox.manage")
    for method, url in (
        ("put", f"/platform/ai/library/{doc['id']}"),
        ("put", f"/platform/ai/library/{doc['id']}/enabled"),
        ("post", f"/platform/ai/library/{doc['id']}/restore"),
        ("delete", f"/platform/ai/library/{doc['id']}"),
    ):
        sent = client.request(
            method.upper(),
            url,
            json={"kind": "note", "title": "x", "enabled": False, "version": 1},
            headers=only_reader,
        )
        assert sent.status_code == 403, (method, url, sent.text)
    assert client.post("/platform/ai/library/reindex", headers=only_reader).status_code == 403


def test_a_document_keeps_every_version_and_an_old_one_can_come_back(
    client: TestClient, engine: Engine, editor: dict
) -> None:
    doc = add(client, editor).json()
    assert doc["version"] == 1
    base = f"/platform/ai/library/{doc['id']}"
    changed = client.put(
        base,
        json={
            "kind": "note",
            "title": "Refunds",
            "body": "Refunds go to the card or cash.",
            "change_note": "Cash too",
        },
        headers=editor,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    # Changing only the title or the source does not make a new version.
    renamed = client.put(
        base,
        json={"kind": "note", "title": "Refund rules", "body": "Refunds go to the card or cash."},
        headers=editor,
    ).json()
    assert (renamed["version"], renamed["title"]) == (2, "Refund rules")
    versions = client.get(f"{base}/versions", headers=editor).json()
    assert [(v["version"], v["change_note"]) for v in versions] == [(2, "Cash too"), (1, None)]
    old = client.get(f"{base}/versions/1", headers=editor).json()
    assert "card only" in old["body"] and old["version"] == 1
    assert client.get(f"{base}/versions/9", headers=editor).status_code == 404

    restored = client.post(f"{base}/restore", json={"version": 1}, headers=editor).json()
    assert restored["version"] == 3 and "card only" in restored["body"]
    found = client.get(
        "/platform/ai/agents/product/library/search", params={"q": "cash"}, headers=editor
    ).json()
    assert [h["text"] for h in found if "Cash refunds" in h["text"]]  # v3 has the old text
    assert client.put(base, json={"kind": "file", "title": "x"}, headers=editor).status_code == 422


def test_the_agent_finds_hebrew_and_english_with_the_document_and_the_section(
    client: TestClient, editor: dict
) -> None:
    add(
        client,
        editor,
        kind="file",
        title="חוק הגנת הפרטיות",
        body=PRIVACY_HE,
        source_url="https://example.gov.il/privacy",
        source_org="הרשות להגנת הפרטיות",
        country="il",
        reviewed_on="2026-10-01",
    )
    add(client, editor)
    url = "/platform/ai/agents/product/library/search"
    hits = client.get(url, params={"q": "האם הפרטיות שלי מוגנת? מאגר מידע"}, headers=editor).json()
    assert hits
    top = hits[0]
    assert top["document"] == "חוק הגנת הפרטיות"
    assert top["source_url"] == "https://example.gov.il/privacy"
    assert top["country"] == "il" and top["last_reviewed"] == "2026-10-01"
    assert top["section"] in ("חוק הגנת הפרטיות", "זכות העיון")
    english = client.get(url, params={"q": "how do we refund?"}, headers=editor).json()
    assert [h["section"] for h in english][:1] == ["Refund policy"]
    assert client.get(url, params={"q": "zzzqq"}, headers=editor).json() == []


def test_each_agent_has_its_own_library_and_the_chief_reads_them_all(
    client: TestClient, editor: dict
) -> None:
    add(client, editor, agent="product")
    other = client.get(
        "/platform/ai/agents/success/library/search", params={"q": "refund"}, headers=editor
    )
    assert other.json() == []
    chief = client.get(
        "/platform/ai/agents/manager/library/search", params={"q": "refund"}, headers=editor
    )
    assert chief.json()
    assert client.get("/platform/ai/agents/success/library", headers=editor).json() == []


def test_a_switched_off_document_is_not_found_and_a_deleted_one_is_gone(
    client: TestClient, engine: Engine, editor: dict
) -> None:
    doc = add(client, editor).json()
    base = f"/platform/ai/library/{doc['id']}"
    search = lambda: client.get(  # noqa: E731
        "/platform/ai/agents/product/library/search", params={"q": "refund"}, headers=editor
    ).json()
    assert search()
    off = client.put(f"{base}/enabled", json={"enabled": False}, headers=editor)
    assert off.status_code == 200 and off.json()["enabled"] is False
    assert search() == []
    listed = client.get("/platform/ai/agents/product/library", headers=editor).json()
    assert [(d["title"], d["enabled"], d["chunks"] > 0) for d in listed] == [
        ("Refunds", False, True)
    ]
    client.put(f"{base}/enabled", json={"enabled": True}, headers=editor)
    assert search()
    assert client.delete(base, headers=editor).status_code == 204
    assert client.get(base, headers=editor).status_code == 404
    assert search() == []
    changes = [a for a in audit_actions(engine) if a == "ai.library"]
    assert len(changes) == 4  # created, off, on, deleted: every change is logged


def test_a_file_is_uploaded_and_read(client: TestClient, editor: dict) -> None:
    sent = client.post(
        "/platform/ai/agents/product/library/upload",
        files={"file": ("refunds.md", REFUNDS.encode(), "text/markdown")},
        data={"country": "all", "source_org": "MyBiz"},
        headers=editor,
    )
    assert sent.status_code == 201, sent.text
    doc = sent.json()
    assert (doc["kind"], doc["title"], doc["country"]) == ("file", "refunds", "all")
    bad = client.post(
        "/platform/ai/agents/product/library/upload",
        files={"file": ("virus.exe", b"MZ", "application/octet-stream")},
        headers=editor,
    )
    assert (bad.status_code, bad.json()["detail"]) == (422, "unsupported_file")
    link = add(
        client,
        editor,
        kind="link",
        title="Official page",
        body=None,
        source_url="https://example.gov.il/x",
    )
    assert link.status_code == 201 and link.json()["body"] is None
    assert add(client, editor, kind="note", body="").status_code == 422  # a note needs its text


def test_reindex_does_nothing_while_embeddings_are_off(client: TestClient, editor: dict) -> None:
    add(client, editor)
    assert client.post("/platform/ai/library/reindex", headers=editor).json() == {"embedded": 0}


# --- The agent in a conversation --------------------------------------------------------------


def test_the_agent_gets_the_notes_and_the_search_tool_and_cites_its_source(
    client: TestClient, engine: Engine, auth: AuthHeaders, editor: dict, use_provider
) -> None:
    add(client, editor, kind="summary", title="What matters", body="Never promise a refund date.")
    add(client, editor, kind="file", title="Refund handbook", body=REFUNDS)
    off = add(client, editor, kind="note", title="Old rule", body="Refund within 3 days.").json()
    client.put(f"/platform/ai/library/{off['id']}/enabled", json={"enabled": False}, headers=editor)

    provider = FakeProvider(
        [
            calls("search_library", {"question": "refund policy"}),
            says("We refund by card (Refund handbook, Refund policy)."),
        ]
    )
    use_provider(provider)
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "product"}, headers=editor
    ).json()
    reply = client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "What is our refund policy?"},
        headers=editor,
    )
    assert reply.status_code == 200, reply.text

    first = provider.calls[0]
    assert "search_library" in {t["name"] for t in first["tools"]}
    assert "Never promise a refund date." in first["system"]  # the approved summary is always there
    assert "Refund within 3 days." not in first["system"]  # a switched-off note is not
    assert "I did not find this in the library" in first["system"]  # the rule to cite or say so
    result = json.loads(unwrap(provider.calls[1]["messages"][-1]["content"][0]["content"]))
    assert result["results"][0]["document"] == "Refund handbook"
    assert result["results"][0]["section"] == "Refund policy"
    assert "ai.library" in audit_actions(engine) and "ai.tool.search_library" in audit_actions(
        engine
    )


def test_the_search_tool_says_so_when_the_library_has_nothing(
    client: TestClient, editor: dict, use_provider
) -> None:
    provider = FakeProvider(
        [
            calls("search_library", {"question": "tax on whales"}),
            says("I did not find this in the library."),
        ]
    )
    use_provider(provider)
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "manager"}, headers=editor
    ).json()
    client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": "Whales?"},
        headers=editor,
    )
    result = json.loads(unwrap(provider.calls[1]["messages"][-1]["content"][0]["content"]))
    assert result == {"results": [], "note": "Nothing found in the library for this question."}


# --- Search by meaning (needs pgvector in the test database; plain PostgreSQL skips it) --------


class FakeEmbeddings:
    """Texts about the same thing get the same direction: refunds, privacy, or anything else."""

    topics = (("refund", "money back"), ("privacy", "personal data"))

    def embed(self, texts: list[str], *, query: bool) -> list[list[float]]:
        vectors = []
        for body in texts:
            axis = next(
                (i for i, words in enumerate(self.topics) if any(w in body.lower() for w in words)),
                len(self.topics),
            )
            vectors.append([1.0 if i == axis else 0.0 for i in range(embeddings.DIMENSIONS)])
        return vectors


def test_with_embeddings_on_the_agent_also_finds_by_meaning(
    client: TestClient, engine: Engine, editor: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    with engine.connect() as connection:
        ready = connection.execute(text("SELECT app.platform_kb_vector_ready()")).scalar()
    if not ready:
        pytest.skip("pgvector is not in this database")
    search = "/platform/ai/agents/product/library/search"
    add(client, editor)
    # Off (the default): "money back" shares no word with the refund policy.
    assert client.get(search, params={"q": "money back"}, headers=editor).json() == []

    monkeypatch.setattr(embeddings, "provider", lambda: FakeEmbeddings())
    assert client.post("/platform/ai/library/reindex", headers=editor).json() == {"embedded": 2}
    assert client.post("/platform/ai/library/reindex", headers=editor).json() == {"embedded": 0}
    hits = client.get(search, params={"q": "money back"}, headers=editor).json()
    assert hits and hits[0]["section"] == "Refund policy"
    # A new document is embedded when it is saved.
    add(client, editor, title="Privacy", body="# Privacy\n\nWe keep personal data safe.")
    assert client.post("/platform/ai/library/reindex", headers=editor).json() == {"embedded": 0}
    hits = client.get(search, params={"q": "personal data"}, headers=editor).json()
    assert hits[0]["document"] == "Privacy"


# --- Official sources: seeded as links, read on request ---------------------------------------


def seed(engine: Engine) -> None:
    """Loads the sources of migration 0148 again (the tests empty the tables first)."""
    path = Path(__file__).parents[1] / "migrations/versions/0148_agent_knowledge_library.py"
    spec = importlib.util.spec_from_file_location("kb_migration", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    with engine.begin() as connection:
        module.seed_sources(connection)


def test_the_seeded_sources_are_well_formed() -> None:
    path = Path(__file__).parents[1] / "migrations/versions/0148_agent_knowledge_library.py"
    spec = importlib.util.spec_from_file_location("kb_migration", path)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    keys = [(agent, url) for agent, _, _, url, _, _ in module.SOURCES]
    assert len(keys) == len(set(keys))
    assert {a for a, *_ in module.SOURCES} <= set(module.ROLES)
    assert all(url.startswith("https://") for _, url in keys)


def test_the_libraries_start_with_official_sources_that_are_read_on_request(
    client: TestClient, engine: Engine, editor: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed(engine)
    legal = client.get("/platform/ai/agents/legal/library", headers=editor).json()
    assert len(legal) >= 8 and all(d["kind"] == "link" and d["chunks"] == 0 for d in legal)
    assert {d["country"] for d in legal} == {"il", "us", "eu"}
    assert all(d["source_url"].startswith("https://") and d["updated_by"] == "seed" for d in legal)

    pages = {
        "https://oag.ca.gov/privacy/ccpa": "# CCPA\n\nConsumers may ask a business to delete data.",
    }

    def fetch(url: str) -> str:
        if url in pages:
            return pages[url]
        raise library_fetch.FetchError("http_404")

    monkeypatch.setattr(library_fetch, "fetch_text", fetch)
    search = "/platform/ai/agents/legal/library/search"
    assert client.get(search, params={"q": "delete data"}, headers=editor).json() == []

    results, offset = [], 0
    while True:  # a few sources at a time, until every source was tried
        report = client.post(
            "/platform/ai/agents/legal/library/refresh", params={"offset": offset}, headers=editor
        ).json()
        results += report["results"]
        offset += len(report["results"])
        if not report["remaining"]:
            break
    assert len(results) == len(legal)
    hits = client.get(search, params={"q": "delete data"}, headers=editor).json()
    assert hits and hits[0]["document"] == "CCPA, California privacy law"
    assert hits[0]["last_reviewed"] is not None and hits[0]["country"] == "us"

    ccpa = next(
        d
        for d in client.get("/platform/ai/agents/legal/library", headers=editor).json()
        if d["title"].startswith("CCPA")
    )
    again = client.post(f"/platform/ai/library/{ccpa['id']}/refresh", headers=editor).json()
    assert (again["result"], again["error"]) == ("unchanged", None)
    pages["https://oag.ca.gov/privacy/ccpa"] += "\n\nNew section about opting out."
    assert (
        client.post(f"/platform/ai/library/{ccpa['id']}/refresh", headers=editor).json()["result"]
        == "updated"
    )
    versions = client.get(f"/platform/ai/library/{ccpa['id']}/versions", headers=editor).json()
    assert [v["version"] for v in versions] == [3, 2, 1]
    failed = [r for r in results if r["result"] == "failed"]
    assert all(r["error"] == "http_404" for r in failed)
    note = add(client, editor)
    assert (
        client.post(f"/platform/ai/library/{note.json()['id']}/refresh", headers=editor).status_code
        == 422
    )  # a note has no source


@pytest.mark.parametrize(
    ("url", "why"),
    [
        ("http://example.com/", "https_only"),
        ("https://127.0.0.1/", "address_not_allowed"),
        ("https://169.254.169.254/latest/meta-data/", "address_not_allowed"),
        ("https://10.0.0.5/", "address_not_allowed"),
        ("https://[::1]/", "address_not_allowed"),
        ("https://localhost/", "address_not_allowed"),
        ("file:///etc/passwd", "https_only"),
    ],
)
def test_only_public_https_addresses_are_read(url: str, why: str) -> None:
    with pytest.raises(library_fetch.FetchError, match=why):
        library_fetch.fetch_text(url)
