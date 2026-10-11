"""Client documents (#45, decision X14): contracts, reports and the client's own papers.

Files go through the storage provider (X13, T80): the built-in `database` provider keeps the
bytes in the row; an object store (Supabase Storage) keeps them under a key that starts with the
business, and the row keeps only the key. Staff upload documents and choose
what the client sees; clients upload their papers in the app and sign documents that ask for it
by writing their name."""

from contextlib import suppress
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.common import ensure_not_erased, not_found
from app.api.deps import AnonymousSessionDep, ClientDep, TenantContext, require
from app.commerce.modules import allowance
from app.core.config import get_settings
from app.core.permissions import Permission
from app.core.signed_links import sign, verify
from app.providers.choice import choose
from app.providers.storage import StorageError, StorageProvider, tenant_key

router = APIRouter(tags=["documents"])
public_router = APIRouter(tags=["documents"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

DocumentKind = Literal["contract", "report", "client_file", "other"]
MAX_SIZE = 10 * 1024 * 1024
LINK_SECONDS = 600  # a signed link opens the file for 10 minutes
TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class Document(BaseModel):
    id: UUID
    client_id: UUID
    name: str
    kind: DocumentKind
    content_type: str
    size: int
    shared: bool = Field(description="The client sees it in the app")
    uploaded_by_client: bool
    sign_requested: bool
    signed_at: datetime | None
    signed_name: str | None
    created_at: datetime


class DocumentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: DocumentKind | None = None
    shared: bool | None = None
    sign_requested: bool | None = None


class DocumentLink(BaseModel):
    url: str = Field(description="Opens the file without signing in, for 10 minutes")


class Signature(BaseModel):
    name: str = Field(min_length=1, max_length=120)


COLUMNS = """id, client_id, name, kind, content_type, size, shared, uploaded_by_client,
    sign_requested, signed_at, signed_name, created_at"""


def _storage_unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="storage_down")


def _forget(storage: StorageProvider, key: str) -> None:
    """Removes an object whose row is gone; a failure leaves an orphan, never a broken row."""
    with suppress(StorageError):
        storage.delete(key)


def _content(db: Session, row: dict) -> bytes:
    if row["content"] is not None:
        return bytes(row["content"])
    try:
        return choose(db, None, "storage").instance.get(row["storage_key"])
    except (StorageError, LookupError) as error:
        raise _storage_unavailable() from error


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


async def _read(file: UploadFile) -> tuple[bytes, str]:
    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in TYPES:
        raise _unprocessable("unsupported_type")
    content = await file.read(MAX_SIZE + 1)
    if not content:
        raise _unprocessable("empty_file")
    if len(content) > MAX_SIZE:
        raise _unprocessable("too_large")
    return content, content_type


def _check_space(db: Session, tenant_id: UUID, size: int) -> None:
    """New files stop at the business's space allowance (#104, the owner chose the soft limit:
    messages keep going, uploads stop); deleting files or a bigger bundle makes room."""
    modules = db.execute(
        text("SELECT module_key FROM app.tenant_modules WHERE tenant_id = :t"), {"t": tenant_id}
    ).scalars()
    _, allowed = allowance(list(modules))
    used = db.execute(text("SELECT app.storage_used()")).scalar_one()
    if used + size > allowed.storage_bytes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="storage_full")


def _store(
    db: Session,
    tenant_id: UUID,
    client_id: UUID,
    *,
    name: str,
    kind: str,
    content: bytes,
    content_type: str,
    shared: bool,
    sign_requested: bool,
    by_client: bool,
) -> Document:
    ensure_not_erased(db, client_id)
    _check_space(db, tenant_id, len(content))
    storage = choose(db, None, "storage").instance
    document_id = uuid4()
    key = None
    if not storage.in_database:
        key = tenant_key(tenant_id, "documents", client_id, document_id)
        try:
            storage.put(key, content, content_type)
        except StorageError as error:
            raise _storage_unavailable() from error
        # The row and the object live or die together: if the row is never saved, the object
        # goes too.
        event.listen(db, "after_rollback", lambda _session: _forget(storage, key), once=True)
    try:
        row = (
            db.execute(
                text(f"""
                    INSERT INTO app.client_documents
                        (id, tenant_id, client_id, name, kind, content_type, size, content,
                         storage_key, shared, uploaded_by_client, sign_requested, created_by)
                    VALUES (:id, :tenant_id, :client_id, :name, :kind, :content_type, :size,
                            :content, :key, :shared, :by_client, :sign, app.current_user_id())
                    RETURNING {COLUMNS}
                """),
                {
                    "id": document_id,
                    "tenant_id": tenant_id,
                    "client_id": client_id,
                    "name": name.strip()[:200] or "document",
                    "kind": kind,
                    "content_type": content_type,
                    "size": len(content),
                    "content": content if key is None else None,
                    "key": key,
                    "shared": shared or sign_requested,
                    "by_client": by_client,
                    "sign": sign_requested,
                },
            )
            .mappings()
            .one()
        )
    except IntegrityError as error:  # no such client in this business
        raise not_found() from error
    return Document.model_validate(dict(row))


def _file(db: Session, document_id: UUID) -> Response:
    row = (
        db.execute(
            text("""
                SELECT name, content_type, content, storage_key FROM app.client_documents
                WHERE id = :id
            """),
            {"id": document_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    content = _content(db, row)
    filename = row["name"].replace('"', "")
    return Response(
        content=content,
        media_type=row["content_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _list(db: Session, client_id: UUID) -> list[Document]:
    rows = db.execute(
        text(f"""
            SELECT {COLUMNS} FROM app.client_documents WHERE client_id = :id
            ORDER BY created_at DESC
        """),
        {"id": client_id},
    ).mappings()
    return [Document.model_validate(dict(row)) for row in rows]


# --- Staff ------------------------------------------------------------------------------------


@router.get("/clients/{client_id}/documents")
def client_documents(client_id: UUID, context: ReadDep) -> list[Document]:
    return _list(context.session, client_id)


@router.post("/clients/{client_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    client_id: UUID,
    context: WriteDep,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form(max_length=200)] = None,
    kind: Annotated[DocumentKind, Form()] = "other",
    shared: Annotated[bool, Form()] = False,
    sign_requested: Annotated[bool, Form()] = False,
) -> Document:
    content, content_type = await _read(file)
    return _store(
        context.session,
        context.tenant_id,
        client_id,
        name=name or file.filename or "document",
        kind=kind,
        content=content,
        content_type=content_type,
        shared=shared,
        sign_requested=sign_requested,
        by_client=False,
    )


@router.get("/documents/{document_id}/file")
def document_file(document_id: UUID, context: ReadDep) -> Response:
    return _file(context.session, document_id)


@router.patch("/documents/{document_id}")
def update_document(document_id: UUID, body: DocumentUpdate, context: WriteDep) -> Document:
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if changes.get("sign_requested"):
        changes["shared"] = True  # asking to sign shares it
    db = context.session
    if changes:
        # Keys come from the model's fields, never from user input.
        assignments = ", ".join(f"{column} = :{column}" for column in changes)
        sql = f"UPDATE app.client_documents SET {assignments} WHERE id = :id RETURNING {COLUMNS}"
        row = db.execute(text(sql), {**changes, "id": document_id}).mappings().first()
    else:
        row = (
            db.execute(
                text(f"SELECT {COLUMNS} FROM app.client_documents WHERE id = :id"),
                {"id": document_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        raise not_found()
    return Document.model_validate(dict(row))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, context: WriteDep) -> None:
    db = context.session
    key = db.execute(
        text("DELETE FROM app.client_documents WHERE id = :id RETURNING storage_key"),
        {"id": document_id},
    ).first()
    if key is None:
        raise not_found()
    if key[0]:
        # Only once the row is really gone, so a failed request never loses the file.
        storage = choose(db, None, "storage").instance
        event.listen(db, "after_commit", lambda _session: _forget(storage, key[0]), once=True)


# --- Client app -------------------------------------------------------------------------------


@client_router.get("/documents")
def my_documents(context: ClientDep) -> list[Document]:
    """What the business shared with me and what I uploaded."""
    return _list(context.session, context.client_id)


@client_router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_my_document(
    context: ClientDep,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form(max_length=200)] = None,
) -> Document:
    content, content_type = await _read(file)
    return _store(
        context.session,
        context.tenant_id,
        context.client_id,
        name=name or file.filename or "document",
        kind="client_file",
        content=content,
        content_type=content_type,
        shared=False,
        sign_requested=False,
        by_client=True,
    )


@client_router.get("/documents/{document_id}/file")
def my_document_file(document_id: UUID, context: ClientDep) -> Response:
    return _file(context.session, document_id)


@client_router.post("/documents/{document_id}/link")
def my_document_link(document_id: UUID, context: ClientDep) -> DocumentLink:
    """A short-lived link to open the file on a phone (the browser can't send the sign-in)."""
    found = context.session.execute(
        text("SELECT 1 FROM app.client_documents WHERE id = :id"), {"id": document_id}
    ).first()
    if found is None:
        raise not_found()
    token = sign(f"document:{context.tenant_id}:{document_id}")
    return DocumentLink(url=f"{get_settings().api_url}/public/files/{token}")


@public_router.get("/public/files/{token}")
def signed_file(token: str, session: AnonymousSessionDep) -> Response:
    subject = verify(token)
    if subject is None or not subject.startswith("document:"):
        raise not_found()
    _, tenant_id, document_id = subject.split(":")
    row = (
        session.execute(
            text("SELECT * FROM app.document_file(:id, :tenant)"),
            {"id": document_id, "tenant": tenant_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    if row["storage_key"] is not None:
        # Straight from the object store: the bytes don't pass through the API.
        try:
            url = choose(session, None, "storage").instance.signed_url(
                row["storage_key"], LINK_SECONDS
            )
        except StorageError as error:
            raise _storage_unavailable() from error
        if url:
            return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
    content = _content(session, row)
    return Response(
        content=content,
        media_type=row["content_type"],
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(row['name'], safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@client_router.post("/documents/{document_id}/sign")
def sign_document(document_id: UUID, body: Signature, context: ClientDep) -> Document:
    db = context.session
    try:
        with db.begin_nested():
            db.execute(
                text("SELECT app.sign_document(:id, :name)"),
                {"id": document_id, "name": body.name},
            )
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0002":
            raise HTTPException(status_code=409, detail="nothing_to_sign") from error
        if code == "22004":
            raise _unprocessable("name_required") from error
        raise
    row = (
        db.execute(
            text(f"SELECT {COLUMNS} FROM app.client_documents WHERE id = :id"),
            {"id": document_id},
        )
        .mappings()
        .one()
    )
    return Document.model_validate(dict(row))
