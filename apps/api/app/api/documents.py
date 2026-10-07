"""Client documents (#45, decision X14): contracts, reports and the client's own papers.

Files go through the storage provider (X13): the built-in `database` provider keeps the bytes
in the row; another provider keeps them elsewhere under a key. Staff upload documents and choose
what the client sees; clients upload their papers in the app and sign documents that ask for it
by writing their name."""

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.common import ensure_not_erased, not_found
from app.api.deps import AnonymousSessionDep, ClientDep, TenantContext, require
from app.core.config import get_settings
from app.permissions import Permission
from app.providers.choice import choose
from app.signed_links import sign, verify

router = APIRouter(tags=["documents"])
public_router = APIRouter(tags=["documents"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

DocumentKind = Literal["contract", "report", "client_file", "other"]
MAX_SIZE = 10 * 1024 * 1024
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
    storage = choose(db, None, "storage").instance
    key = None
    if not storage.in_database:
        key = f"documents/{tenant_id}/{client_id}/{uuid4()}"
        storage.put(key, content, content_type)
    try:
        row = (
            db.execute(
                text(f"""
                    INSERT INTO app.client_documents
                        (tenant_id, client_id, name, kind, content_type, size, content,
                         storage_key, shared, uploaded_by_client, sign_requested, created_by)
                    VALUES (:tenant_id, :client_id, :name, :kind, :content_type, :size,
                            :content, :key, :shared, :by_client, :sign, app.current_user_id())
                    RETURNING {COLUMNS}
                """),
                {
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
    content = (
        bytes(row["content"])
        if row["content"] is not None
        else choose(db, None, "storage").instance.get(row["storage_key"])
    )
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
        choose(db, None, "storage").instance.delete(key[0])


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
    content = (
        bytes(row["content"])
        if row["content"] is not None
        else choose(session, None, "storage").instance.get(row["storage_key"])
    )
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
