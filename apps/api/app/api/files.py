"""The business's files area (round 6, F1): folders with their own permissions, files kept 7
years where the law says so, a ZIP of a folder, and "My documents" for each employee.

A folder names the permission that opens it (payslips: `payroll.read`, employees:
`staff.manage`, business documents: `business.settings`, the rest: `files.read`); owners open
everything. Files in folders marked `retain` are archived, never deleted. Files that belong to
an employee are always open to that employee, whatever the folder."""

import io
import zipfile
from datetime import datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import (
    AnonymousSessionDep,
    TenantContext,
    TenantDep,
    ensure_branch_allowed,
    ensure_branch_visible,
    require,
)
from app.api.documents import TYPES
from app.core.config import get_settings
from app.core.permissions import Permission
from app.core.signed_links import sign, verify
from app.files import (
    FILE_COLUMNS,
    FOLDER_COLUMNS,
    MAX_SIZE,
    ensure_system_folders,
    forget,
    read_file,
    store_file,
)
from app.providers.choice import choose

router = APIRouter(prefix="/files", tags=["files"])
public_router = APIRouter(tags=["files"])

ManageDep = Annotated[TenantContext, Depends(require(Permission.FILES_MANAGE))]
# Who may open a folder is decided by the folder itself (its `read_permission`).
MemberDep = TenantDep

ZIP_MAX_FILES = 300
ZIP_MAX_BYTES = 80 * 1024 * 1024
MAX_DEPTH = 4


class FolderOut(BaseModel):
    id: UUID
    parent_id: UUID | None
    name: str
    system_key: str | None = Field(description="Set for the folders every business has")
    retain: bool = Field(description="Files here are archived, never deleted")
    sensitive: bool = Field(description="Files here are sealed at rest")
    can_upload: bool
    file_count: int
    total_size: int


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: UUID | None = None


class FolderRename(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class FileOut(BaseModel):
    id: UUID
    folder_id: UUID
    name: str
    content_type: str
    size: int
    owner_user_id: UUID | None
    owner_name: str | None = None
    location_id: UUID | None
    archived_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class FileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None


def _allowed(context: TenantContext, permission: str | None) -> bool:
    """Owners open everything, including keys the system adds later."""
    return permission is not None and (context.role == "owner" or permission in context.permissions)


def _folders(context: TenantContext) -> list[dict]:
    db = context.session
    ensure_system_folders(db, context.tenant_id)
    rows = db.execute(
        text(f"""
            SELECT {FOLDER_COLUMNS},
                   (SELECT count(*) FROM app.business_files f
                    WHERE f.folder_id = fo.id AND f.archived_at IS NULL) AS file_count,
                   (SELECT coalesce(sum(f.size), 0) FROM app.business_files f
                    WHERE f.folder_id = fo.id AND f.archived_at IS NULL) AS total_size
            FROM app.file_folders fo ORDER BY (system_key IS NULL), created_at, name
        """)
    ).mappings()
    return [dict(row) for row in rows]


def _readable(context: TenantContext) -> list[dict]:
    return [f for f in _folders(context) if _allowed(context, f["read_permission"])]


def _folder(context: TenantContext, folder_id: UUID) -> dict:
    """A folder the caller may open; anything else is "not found" so folders don't leak."""
    row = (
        context.session.execute(
            text(f"SELECT {FOLDER_COLUMNS} FROM app.file_folders WHERE id = :id"),
            {"id": folder_id},
        )
        .mappings()
        .first()
    )
    if row is None or not _allowed(context, row["read_permission"]):
        raise not_found()
    return dict(row)


def _can_upload(context: TenantContext, folder: dict) -> bool:
    return _allowed(context, folder["write_permission"])


def _out(context: TenantContext, folder: dict) -> FolderOut:
    return FolderOut(
        **{k: folder[k] for k in ("id", "parent_id", "name", "system_key", "retain", "sensitive")},
        can_upload=_can_upload(context, folder),
        file_count=folder["file_count"],
        total_size=folder["total_size"],
    )


@router.get("/folders")
def list_folders(context: MemberDep) -> list[FolderOut]:
    return [_out(context, f) for f in _readable(context)]


@router.post("/folders", status_code=status.HTTP_201_CREATED)
def create_folder(body: FolderCreate, context: ManageDep) -> FolderOut:
    """A folder of the business's own, below one it may open; it keeps the parent's rules."""
    db = context.session
    ensure_system_folders(db, context.tenant_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="name")
    if body.parent_id is None:
        parent = {
            "read_permission": "files.read",
            "write_permission": "files.manage",
            "retain": False,
            "sensitive": False,
        }
    else:
        parent = _folder(context, body.parent_id)
        if not _can_upload(context, parent):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        depth = db.execute(
            text("""
                WITH RECURSIVE up AS (
                    SELECT id, parent_id, 1 AS depth FROM app.file_folders WHERE id = :id
                    UNION ALL
                    SELECT p.id, p.parent_id, up.depth + 1
                    FROM app.file_folders p JOIN up ON p.id = up.parent_id
                ) SELECT max(depth) FROM up
            """),
            {"id": body.parent_id},
        ).scalar_one()
        if depth >= MAX_DEPTH:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="deep")
    try:
        with db.begin_nested():
            row = (
                db.execute(
                    text(f"""
                        INSERT INTO app.file_folders
                            (tenant_id, parent_id, name, read_permission, write_permission,
                             retain, sensitive, created_by)
                        VALUES (:t, :parent, :name, :read, :write, :retain, :sensitive,
                                app.current_user_id())
                        RETURNING {FOLDER_COLUMNS}
                    """),
                    {
                        "t": context.tenant_id,
                        "parent": body.parent_id,
                        "name": name[:120],
                        "read": parent["read_permission"],
                        "write": parent["write_permission"],
                        "retain": parent["retain"],
                        "sensitive": parent["sensitive"],
                    },
                )
                .mappings()
                .one()
            )
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="name_taken") from error
    return _out(context, {**dict(row), "file_count": 0, "total_size": 0})


def _custom_folder(context: TenantContext, folder_id: UUID) -> dict:
    folder = _folder(context, folder_id)
    if folder["system_key"] is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="system_folder")
    if not _can_upload(context, folder):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return folder


@router.patch("/folders/{folder_id}")
def rename_folder(folder_id: UUID, body: FolderRename, context: ManageDep) -> FolderOut:
    _custom_folder(context, folder_id)
    try:
        with context.session.begin_nested():
            context.session.execute(
                text("UPDATE app.file_folders SET name = :name WHERE id = :id"),
                {"name": body.name.strip()[:120], "id": folder_id},
            )
    except IntegrityError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="name_taken") from error
    return next(_out(context, f) for f in _folders(context) if f["id"] == folder_id)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: UUID, context: ManageDep) -> None:
    """Only an empty folder of the business's own goes."""
    _custom_folder(context, folder_id)
    db = context.session
    busy = db.execute(
        text("""
            SELECT EXISTS (SELECT 1 FROM app.business_files WHERE folder_id = :id)
                OR EXISTS (SELECT 1 FROM app.file_folders WHERE parent_id = :id)
        """),
        {"id": folder_id},
    ).scalar_one()
    if busy:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="folder_not_empty")
    db.execute(text("DELETE FROM app.file_folders WHERE id = :id"), {"id": folder_id})


def _visible_branches(context: TenantContext) -> list[UUID] | None:
    return None if context.branches is None else list(context.branches)


def _list_files(context: TenantContext, where: str, params: dict) -> list[FileOut]:
    rows = context.session.execute(
        text(f"""
            SELECT {", ".join(f"f.{c.strip()}" for c in FILE_COLUMNS.split(","))},
                   u.full_name AS owner_name
            FROM app.business_files f
            LEFT JOIN app.users u ON u.id = f.owner_user_id
            WHERE {where}
              AND (CAST(:branches AS uuid[]) IS NULL OR f.location_id IS NULL
                   OR f.location_id = ANY(CAST(:branches AS uuid[])))
            ORDER BY f.created_at DESC
        """),
        {**params, "branches": _visible_branches(context)},
    ).mappings()
    return [FileOut.model_validate(dict(row)) for row in rows]


@router.get("")
def list_files(context: MemberDep, folder_id: UUID, archived: bool = False) -> list[FileOut]:
    _folder(context, folder_id)
    where = "f.folder_id = :folder AND (f.archived_at IS NOT NULL) = :archived"
    return _list_files(context, where, {"folder": folder_id, "archived": archived})


@router.get("/mine")
def my_files(context: MemberDep) -> list[FileOut]:
    """ "My documents": what the business filed for me (payslips, my employment papers)."""
    where = "f.owner_user_id = app.current_user_id() AND f.archived_at IS NULL"
    return _list_files(context, where, {})


def _file_row(context: TenantContext, file_id: UUID) -> dict:
    """A file the caller may open: in a folder they can read, or filed for them."""
    row = (
        context.session.execute(
            text("""
                SELECT f.id, f.folder_id, f.name, f.content_type, f.content, f.storage_key,
                       f.encrypted, f.location_id, f.owner_user_id,
                       f.owner_user_id = app.current_user_id() AS mine,
                       fo.read_permission, fo.write_permission, fo.retain
                FROM app.business_files f JOIN app.file_folders fo ON fo.id = f.folder_id
                WHERE f.id = :id
            """),
            {"id": file_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    ensure_branch_visible(context, row["location_id"])
    if not (row["mine"] or _allowed(context, row["read_permission"])):
        raise not_found()
    return dict(row)


def _download(row: dict, content: bytes) -> Response:
    return Response(
        content=content,
        media_type=row["content_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row['name'], safe='')}",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{file_id}/file")
def download_file(file_id: UUID, context: MemberDep) -> Response:
    row = _file_row(context, file_id)
    return _download(row, read_file(context.session, row))


class FileLink(BaseModel):
    url: str = Field(description="Opens the file without signing in, for 10 minutes")


@router.post("/{file_id}/link")
def file_link(file_id: UUID, context: MemberDep) -> FileLink:
    """A short-lived link to open the file on a phone (the browser can't send the sign-in)."""
    _file_row(context, file_id)
    token = sign(f"bfile:{context.tenant_id}:{file_id}")
    return FileLink(url=f"{get_settings().api_url}/public/business-files/{token}")


@public_router.get("/public/business-files/{token}")
def signed_business_file(token: str, session: AnonymousSessionDep) -> Response:
    subject = verify(token)
    if subject is None or not subject.startswith("bfile:"):
        raise not_found()
    _, tenant_id, file_id = subject.split(":")
    row = (
        session.execute(
            text("SELECT * FROM app.business_file(:id, :tenant)"),
            {"id": file_id, "tenant": tenant_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    response = _download(dict(row), read_file(session, dict(row)))
    response.headers["Content-Disposition"] = response.headers["Content-Disposition"].replace(
        "attachment", "inline", 1
    )
    return response


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_file(
    context: MemberDep,
    folder_id: Annotated[UUID, Form()],
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form(max_length=200)] = None,
    owner_user_id: Annotated[UUID | None, Form()] = None,
    location_id: Annotated[UUID | None, Form()] = None,
) -> FileOut:
    folder = _folder(context, folder_id)
    if not _can_upload(context, folder):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    ensure_branch_allowed(context, location_id)
    content_type = (file.content_type or "").split(";")[0].strip()
    if content_type not in TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unsupported_type"
        )
    content = file.file.read(MAX_SIZE + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="empty_file")
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="too_large")
    db = context.session
    if owner_user_id is not None:
        member = db.execute(
            text("SELECT 1 FROM app.tenant_members WHERE user_id = :u"), {"u": owner_user_id}
        ).first()
        if member is None:
            raise not_found()
    try:
        with db.begin_nested():
            row = store_file(
                db,
                context.tenant_id,
                folder_id,
                name=name or file.filename or "file",
                content=content,
                content_type=content_type,
                owner_user_id=owner_user_id,
                location_id=location_id,
            )
    except IntegrityError as error:  # no such branch in this business
        raise not_found() from error
    return FileOut.model_validate({**row, "owner_name": None})


@router.patch("/{file_id}")
def update_file(file_id: UUID, body: FileUpdate, context: MemberDep) -> FileOut:
    """Rename a file, or move it to the archive and back. Archived files stay (and count toward
    the space) but leave the folder's list."""
    row = _file_row(context, file_id)
    if not _allowed(context, row["write_permission"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    changes = body.model_dump(exclude_unset=True)
    db = context.session
    if body.name is not None:
        db.execute(
            text("UPDATE app.business_files SET name = :name WHERE id = :id"),
            {"name": body.name.strip()[:200], "id": file_id},
        )
    if "archived" in changes and body.archived is not None:
        db.execute(
            text("""
                UPDATE app.business_files
                SET archived_at = CASE WHEN :archived THEN coalesce(archived_at, now()) END
                WHERE id = :id
            """),
            {"archived": body.archived, "id": file_id},
        )
    return _list_files(context, "f.id = :id", {"id": file_id})[0]


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: UUID, context: MemberDep) -> None:
    """Deleting is for ordinary files; payslips and accounting papers can only be archived."""
    row = _file_row(context, file_id)
    if not _allowed(context, row["write_permission"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if row["retain"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="archive_only")
    db = context.session
    db.execute(text("DELETE FROM app.business_files WHERE id = :id"), {"id": file_id})
    if row["storage_key"]:
        # Only once the row is really gone, so a failed request never loses the file.
        storage = choose(db, None, "storage").instance
        event.listen(db, "after_commit", lambda _s: forget(storage, row["storage_key"]), once=True)


def _folder_tree(db: Session, folder_id: UUID) -> list[dict]:
    return [
        dict(r)
        for r in db.execute(
            text(f"""
                WITH RECURSIVE tree AS (
                    SELECT {FOLDER_COLUMNS}, name AS path FROM app.file_folders WHERE id = :id
                    UNION ALL
                    SELECT {", ".join(f"c.{c.strip()}" for c in FOLDER_COLUMNS.split(","))},
                           tree.path || '/' || c.name
                    FROM app.file_folders c JOIN tree ON c.parent_id = tree.id
                ) SELECT * FROM tree
            """),
            {"id": folder_id},
        ).mappings()
    ]


@router.get("/folders/{folder_id}/zip")
def download_zip(folder_id: UUID, context: MemberDep) -> Response:
    """The folder's current files (and its subfolders') as one ZIP."""
    _folder(context, folder_id)
    db = context.session
    buffer = io.BytesIO()
    count = total = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in _folder_tree(db, folder_id):
            if not _allowed(context, folder["read_permission"]):
                continue
            rows = (
                db.execute(
                    text("""
                        SELECT id, name, content, storage_key, encrypted, location_id, size
                        FROM app.business_files
                        WHERE folder_id = :id AND archived_at IS NULL ORDER BY created_at
                    """),
                    {"id": folder["id"]},
                )
                .mappings()
                .all()
            )
            for row in rows:
                if context.branches is not None and (
                    row["location_id"] is not None and row["location_id"] not in context.branches
                ):
                    continue
                count += 1
                total += row["size"]
                if count > ZIP_MAX_FILES or total > ZIP_MAX_BYTES:
                    raise HTTPException(status_code=413, detail="too_many_files")
                archive.writestr(
                    f"{folder['path']}/{row['id'].hex[:6]}-{row['name']}".replace("\\", "_"),
                    read_file(db, dict(row)),
                )
    name = next(f["name"] for f in _readable(context) if f["id"] == folder_id)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name + '.zip', safe='')}",
            "Cache-Control": "private, no-store",
        },
    )
