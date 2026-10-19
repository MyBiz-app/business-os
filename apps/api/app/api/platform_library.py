"""The agents' libraries in the console (slice C3a): add, edit, version, switch off and delete
the documents, files and notes of each console AI agent.

Anyone on the MyBiz team may read a library of an agent they may ask; changing needs
`billing.manage`, like the other agent settings. Every change is written to the console audit
log by the database function."""

import datetime as dt
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai import console, console_agents, knowledge, library_fetch
from app.api.common import not_found
from app.api.platform import BillingDep, StaffDep, rule_errors

router = APIRouter(prefix="/platform/ai", tags=["platform"])

Kind = Literal["file", "link", "note", "summary"]
Country = Literal["il", "us", "eu", "all"]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class LibraryDocument(BaseModel):
    id: UUID
    agent_key: console_agents.AgentKey
    kind: Kind
    title: str
    source_url: str | None
    source_org: str | None
    country: Country | None
    reviewed_on: dt.date | None
    enabled: bool
    version: int
    chars: int = Field(description="Length of the current text; 0 for a link without text")
    chunks: int = Field(description="Pieces the agent can find; 0 means it cannot find it yet")
    updated_by: str
    updated_at: dt.datetime


class LibraryDocumentBody(BaseModel):
    id: UUID
    agent_key: console_agents.AgentKey
    kind: Kind
    title: str
    source_url: str | None
    source_org: str | None
    country: Country | None
    reviewed_on: dt.date | None
    enabled: bool
    version: int
    body: str | None
    updated_by: str
    updated_at: dt.datetime


class LibraryVersion(BaseModel):
    version: int
    change_note: str | None
    created_by: str
    created_at: dt.datetime
    chars: int


class LibraryChange(BaseModel):
    kind: Kind
    title: str = Field(min_length=1, max_length=200)
    source_url: str | None = Field(default=None, max_length=1000, pattern=r"^https?://\S+$")
    source_org: str | None = Field(default=None, max_length=200)
    country: Country | None = None
    reviewed_on: dt.date | None = None
    enabled: bool = True
    body: str | None = Field(default=None, max_length=knowledge.MAX_TEXT)
    change_note: str | None = Field(default=None, max_length=300)


class LibraryRestore(BaseModel):
    version: int = Field(ge=1)


class LibraryEnabled(BaseModel):
    enabled: bool


class ReindexResult(BaseModel):
    embedded: int = Field(description="Pieces embedded now; 0 while search by meaning is off")


class RefreshResult(BaseModel):
    id: UUID
    title: str
    result: Literal["updated", "unchanged", "failed"]
    error: str | None = None


class RefreshReport(BaseModel):
    results: list[RefreshResult]
    remaining: int = Field(description="Sources still to read; call again with a later offset")


class LibrarySearchHit(BaseModel):
    document: str
    source_url: str | None
    source_org: str | None
    country: str | None
    last_reviewed: str | None
    section: str | None
    text: str


def _agent_for_reading(db: Session, key: str) -> None:
    """The team member may open the library of an agent they may ask (the chief: all)."""
    permissions = console.permissions_of(db)
    if not console_agents.can_use(console_agents.CATALOG[key], permissions):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


def _document(db: Session, doc_id: UUID) -> LibraryDocumentBody:
    row = (
        db.execute(text("SELECT * FROM app.platform_kb_document(:id)"), {"id": doc_id})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    _agent_for_reading(db, row["agent_key"])
    return LibraryDocumentBody.model_validate(dict(row))


def _save(db: Session, doc_id: UUID | None, agent: str, change: LibraryChange) -> UUID:
    if change.kind in ("note", "summary") and not change.body:
        raise HTTPException(status_code=422, detail="body_required")
    with rule_errors(db):
        return knowledge.save(
            db,
            doc_id=doc_id,
            agent=agent,
            kind=change.kind,
            title=change.title,
            url=change.source_url,
            org=change.source_org,
            country=change.country,
            reviewed_on=change.reviewed_on,
            enabled=change.enabled,
            body=change.body,
            note=change.change_note,
        )


@router.get("/agents/{key}/library")
def list_library(
    key: console_agents.AgentKey,
    db: StaffDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
) -> list[LibraryDocument]:
    """The documents of one agent's library: at most 200, the list of a few dozen in practice."""
    _agent_for_reading(db, key)
    rows = db.execute(text("SELECT * FROM app.platform_kb_documents(:key)"), {"key": key})
    return [LibraryDocument.model_validate(dict(r)) for r in rows.mappings()][:limit]


@router.post("/agents/{key}/library", status_code=status.HTTP_201_CREATED)
def add_library_document(
    key: console_agents.AgentKey, body: LibraryChange, db: BillingDep
) -> LibraryDocumentBody:
    """Adds a note, a summary, a link or pasted text to an agent's library."""
    return _document(db, _save(db, None, key, body))


@router.post("/agents/{key}/library/upload", status_code=status.HTTP_201_CREATED)
def upload_library_file(
    key: console_agents.AgentKey,
    file: Annotated[UploadFile, File()],
    db: BillingDep,
    title: Annotated[str | None, Form(max_length=200)] = None,
    source_url: Annotated[str | None, Form(max_length=1000, pattern=r"^https?://\S+$")] = None,
    source_org: Annotated[str | None, Form(max_length=200)] = None,
    country: Annotated[Country | None, Form()] = None,
    reviewed_on: Annotated[dt.date | None, Form()] = None,
) -> LibraryDocumentBody:
    """Adds a file (text, Markdown, HTML, Word or PDF) to an agent's library."""
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    name = file.filename or "document"
    try:
        body = knowledge.extract_text(name, data)
    except knowledge.UnsupportedFile as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    change = LibraryChange(
        kind="file",
        title=(title or name.rsplit(".", 1)[0])[:200] or "document",
        source_url=source_url or None,
        source_org=source_org or None,
        country=country,
        reviewed_on=reviewed_on,
        body=body,
        change_note=f"Uploaded {name}"[:300],
    )
    return _document(db, _save(db, None, key, change))


@router.get("/library/{doc_id}")
def get_library_document(doc_id: UUID, db: StaffDep) -> LibraryDocumentBody:
    return _document(db, doc_id)


@router.put("/library/{doc_id}")
def change_library_document(
    doc_id: UUID, body: LibraryChange, db: BillingDep
) -> LibraryDocumentBody:
    """Saves a change. A changed text is a new version; the earlier ones stay."""
    current = _document(db, doc_id)
    if body.kind != current.kind:
        raise HTTPException(status_code=422, detail="kind_cannot_change")
    _save(db, doc_id, current.agent_key, body)
    return _document(db, doc_id)


@router.get("/library/{doc_id}/versions")
def library_versions(doc_id: UUID, db: StaffDep) -> list[LibraryVersion]:
    """Every saved version of a document, newest first (at most 100)."""
    _document(db, doc_id)
    rows = db.execute(text("SELECT * FROM app.platform_kb_versions(:id)"), {"id": doc_id})
    return [LibraryVersion.model_validate(dict(r)) for r in rows.mappings()]


@router.get("/library/{doc_id}/versions/{version}")
def library_version(doc_id: UUID, version: int, db: StaffDep) -> LibraryDocumentBody:
    """The document as it was in one version."""
    current = _document(db, doc_id)
    body = db.execute(
        text("SELECT app.platform_kb_version_body(:id, :version)"),
        {"id": doc_id, "version": version},
    ).scalar()
    exists = db.execute(
        text("SELECT 1 FROM app.platform_kb_versions(:id) v WHERE v.version = :version"),
        {"id": doc_id, "version": version},
    ).first()
    if exists is None:
        raise not_found()
    return current.model_copy(update={"body": body, "version": version})


@router.post("/library/{doc_id}/restore")
def restore_library_version(
    doc_id: UUID, body: LibraryRestore, db: BillingDep
) -> LibraryDocumentBody:
    """Brings an earlier version back as a new version (nothing is lost)."""
    current = _document(db, doc_id)
    old = library_version(doc_id, body.version, db)
    change = LibraryChange(
        kind=current.kind,
        title=current.title,
        source_url=current.source_url,
        source_org=current.source_org,
        country=current.country,
        reviewed_on=current.reviewed_on,
        enabled=current.enabled,
        body=old.body,
        change_note=f"Restored version {body.version}",
    )
    _save(db, doc_id, current.agent_key, change)
    return _document(db, doc_id)


@router.put("/library/{doc_id}/enabled")
def switch_library_document(
    doc_id: UUID, body: LibraryEnabled, db: BillingDep
) -> LibraryDocumentBody:
    """Switches a document off (the agent stops using it) or on, without deleting it."""
    _document(db, doc_id)
    with rule_errors(db):
        db.execute(
            text("SELECT app.platform_kb_set_enabled(:id, :enabled)"),
            {"id": doc_id, "enabled": body.enabled},
        )
    return _document(db, doc_id)


@router.delete("/library/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library_document(doc_id: UUID, db: BillingDep) -> None:
    _document(db, doc_id)
    with rule_errors(db):
        db.execute(text("SELECT app.platform_kb_delete(:id)"), {"id": doc_id})


REFRESH_PER_CALL = 4  # each page may take up to 15 seconds


def _refresh_one(db: Session, doc_id: UUID) -> RefreshResult:
    doc = _document(db, doc_id)
    if not doc.source_url or doc.kind not in ("file", "link"):
        raise HTTPException(status_code=422, detail="no_source")
    try:
        body = library_fetch.fetch_text(doc.source_url)
    except library_fetch.FetchError as error:
        return RefreshResult(id=doc.id, title=doc.title, result="failed", error=str(error))
    change = LibraryChange(
        kind=doc.kind,
        title=doc.title,
        source_url=doc.source_url,
        source_org=doc.source_org,
        country=doc.country,
        reviewed_on=dt.datetime.now(dt.UTC).date(),  # "last checked"
        enabled=doc.enabled,
        body=body,
        change_note="Read from the source",
    )
    _save(db, doc.id, doc.agent_key, change)
    again = _document(db, doc.id)
    return RefreshResult(
        id=doc.id,
        title=doc.title,
        result="updated" if again.version != doc.version else "unchanged",
    )


@router.post("/library/{doc_id}/refresh")
def refresh_library_document(doc_id: UUID, db: BillingDep) -> RefreshResult:
    """Reads the document's source link again; a changed text is a new version, and the
    "last reviewed" date becomes today (the source was checked)."""
    return _refresh_one(db, doc_id)


@router.post("/agents/{key}/library/refresh")
def refresh_library(
    key: console_agents.AgentKey,
    db: BillingDep,
    offset: Annotated[int, Query(ge=0, le=1000)] = 0,
) -> RefreshReport:
    """Reads the sources of an agent's library, a few at a time: call again with the offset
    advanced by the number of results until `remaining` is 0."""
    rows = db.execute(
        text("SELECT * FROM app.platform_kb_documents(:key)"), {"key": key}
    ).mappings()
    todo = [r for r in rows if r["source_url"] and r["kind"] in ("file", "link") and r["enabled"]]
    batch = todo[offset : offset + REFRESH_PER_CALL]
    return RefreshReport(
        results=[_refresh_one(db, r["id"]) for r in batch],
        remaining=max(0, len(todo) - offset - len(batch)),
    )


@router.post("/library/reindex")
def reindex_library(db: BillingDep) -> ReindexResult:
    """Embeds the pieces that are not yet embedded, for search by meaning. Nothing happens
    while the embeddings provider is off (the default)."""
    with rule_errors(db):
        return ReindexResult(embedded=knowledge.embed_pending(db))


@router.get("/agents/{key}/library/search")
def search_library(
    key: console_agents.AgentKey,
    db: StaffDep,
    q: Annotated[str, Query(min_length=1, max_length=300)],
) -> list[LibrarySearchHit]:
    """What the agent would find for a question, to check a library before trusting it."""
    _agent_for_reading(db, key)
    hits = knowledge.search(db, None if key == console_agents.CHIEF else key, q)
    return [LibrarySearchHit.model_validate(h) for h in hits]
