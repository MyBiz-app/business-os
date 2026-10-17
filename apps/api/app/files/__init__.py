"""The business's files area (round 6, F1): folders with their own permissions, and the files in
them.

Files go through the storage provider (X13, T80) like client documents do. Folders marked
`sensitive` (payslips, employee papers) are sealed with the platform's `API_SECRETS_KEY` before
they are stored, so neither the database nor the object store holds their readable bytes. Other
parts of the system (payroll, document templates, the migration hub) add their files with
`store_file`."""

from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import Connection, event, text
from sqlalchemy.orm import Session

from app.commerce.modules import allowance
from app.files.content import ensure_matches
from app.files.scan import ensure_clean
from app.providers.choice import choose
from app.providers.secrets import decrypt_bytes, encrypt_bytes
from app.providers.storage import StorageError, StorageProvider, tenant_key

MAX_SIZE = 10 * 1024 * 1024
LINK_SECONDS = 600  # a signed link opens the file for 10 minutes

# Folders every business has. `read` opens the folder, `write` adds files by hand (None: only the
# system adds files there). `retain`: files are archived, never deleted (accounting papers are kept
# 7 years). `sensitive`: sealed at rest. Names are the English defaults; the apps translate by key.
SYSTEM_FOLDERS: tuple[dict, ...] = (
    {
        "key": "payroll",
        "name": "Payslips",
        "read": "payroll.read",
        "write": None,
        "retain": True,
        "sensitive": True,
    },
    {
        "key": "employees",
        "name": "Employees",
        "read": "staff.manage",
        "write": "staff.manage",
        "retain": True,
        "sensitive": True,
    },
    {
        "key": "business_docs",
        "name": "Business documents",
        "read": "business.settings",
        "write": "business.settings",
        "retain": True,
        "sensitive": False,
    },
    {
        "key": "imports",
        "name": "Imports",
        "read": "files.manage",
        "write": None,
        "retain": False,
        "sensitive": False,
    },
    {
        "key": "general",
        "name": "General",
        "read": "files.read",
        "write": "files.manage",
        "retain": False,
        "sensitive": False,
    },
)
IMPORT_DAYS = 30


@dataclass(frozen=True)
class Folder:
    id: UUID
    parent_id: UUID | None
    name: str
    system_key: str | None
    read_permission: str
    write_permission: str | None
    retain: bool
    sensitive: bool


FOLDER_COLUMNS = (
    "id, parent_id, name, system_key, read_permission, write_permission, retain, sensitive"
)


def ensure_system_folders(db: Session, tenant_id: UUID) -> None:
    """Creates the folders a business always has; safe to call again."""
    for folder in SYSTEM_FOLDERS:
        db.execute(
            text("""
                INSERT INTO app.file_folders
                    (tenant_id, name, system_key, read_permission, write_permission, retain,
                     sensitive)
                VALUES (:t, :name, :key, :read, :write, :retain, :sensitive)
                ON CONFLICT (tenant_id, system_key) WHERE system_key IS NOT NULL DO NOTHING
            """),
            {"t": tenant_id, **folder},
        )


def system_folder_id(db: Session, tenant_id: UUID, key: str) -> UUID:
    ensure_system_folders(db, tenant_id)
    return db.execute(
        text("SELECT id FROM app.file_folders WHERE tenant_id = :t AND system_key = :k"),
        {"t": tenant_id, "k": key},
    ).scalar_one()


def check_space(db: Session, tenant_id: UUID, size: int) -> None:
    """New files stop at the business's space allowance (#104, the owner chose the soft limit:
    messages keep going, uploads stop); deleting files or a bigger bundle makes room."""
    modules = db.execute(
        text("SELECT module_key FROM app.tenant_modules WHERE tenant_id = :t"), {"t": tenant_id}
    ).scalars()
    _, allowed = allowance(list(modules))
    used = db.execute(text("SELECT app.storage_used()")).scalar_one()
    if used + size > allowed.storage_bytes:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="storage_full")


def storage_down() -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="storage_down")


def forget(storage: StorageProvider, key: str) -> None:
    """Removes an object whose row is gone; a failure leaves an orphan, never a broken row."""
    with suppress(StorageError):
        storage.delete(key)


def store_file(
    db: Session,
    tenant_id: UUID,
    folder_id: UUID,
    *,
    name: str,
    content: bytes,
    content_type: str,
    owner_user_id: UUID | None = None,
    location_id: UUID | None = None,
    expires_at: datetime | None = None,
) -> dict:
    """Saves a file in a folder (the folder's own rules decide sealing); the caller has already
    checked who may add it. Returns the new row's columns."""
    folder = (
        db.execute(
            text("SELECT sensitive, system_key FROM app.file_folders WHERE id = :id"),
            {"id": folder_id},
        )
        .mappings()
        .first()
    )
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    ensure_matches(content, content_type)
    check_space(db, tenant_id, len(content))
    ensure_clean(content)
    sealed = bool(folder["sensitive"])
    payload = encrypt_bytes(content) if sealed else content
    storage = choose(db, None, "storage").instance
    file_id = uuid4()
    key = None
    if not storage.in_database:
        key = tenant_key(tenant_id, "files", folder_id, file_id)
        try:
            storage.put(key, payload, "application/octet-stream" if sealed else content_type)
        except StorageError as error:
            raise storage_down() from error
        # The row and the object live or die together.
        event.listen(db, "after_rollback", lambda _session: forget(storage, key), once=True)
    if expires_at is None and folder["system_key"] == "imports":
        expires_at = db.execute(
            text("SELECT now() + make_interval(days => :d)"), {"d": IMPORT_DAYS}
        ).scalar_one()
    row = (
        db.execute(
            text(f"""
                INSERT INTO app.business_files
                    (id, tenant_id, folder_id, name, content_type, size, content, storage_key,
                     encrypted, owner_user_id, location_id, expires_at, created_by)
                VALUES (:id, :tenant_id, :folder_id, :name, :content_type, :size, :content,
                        :key, :encrypted, :owner, :location, :expires, app.current_user_id())
                RETURNING {FILE_COLUMNS}
            """),
            {
                "id": file_id,
                "tenant_id": tenant_id,
                "folder_id": folder_id,
                "name": name.strip()[:200] or "file",
                "content_type": content_type,
                "size": len(content),
                "content": payload if key is None else None,
                "key": key,
                "encrypted": sealed,
                "owner": owner_user_id,
                "location": location_id,
                "expires": expires_at,
            },
        )
        .mappings()
        .one()
    )
    return dict(row)


FILE_COLUMNS = """id, folder_id, name, content_type, size, encrypted, owner_user_id, location_id,
    archived_at, expires_at, created_at"""


def read_file(db: Session, row: dict) -> bytes:
    """The file's bytes, opened if they were sealed. `row` has content, storage_key, encrypted."""
    if row["content"] is not None:
        payload = bytes(row["content"])
    else:
        try:
            payload = choose(db, None, "storage").instance.get(row["storage_key"])
        except (StorageError, LookupError) as error:
            raise storage_down() from error
    return decrypt_bytes(payload) if row["encrypted"] else payload


def purge_expired_files(db: Session | Connection) -> int:
    """Deletes files whose time is up (the imports folder keeps a file 30 days); returns how many.
    Runs as a job over every business, so it sees all rows."""
    rows = db.execute(
        text("""
            DELETE FROM app.business_files
            WHERE expires_at IS NOT NULL AND expires_at < now()
            RETURNING storage_key
        """)
    ).all()
    storage = None
    for (key,) in rows:
        if key:
            storage = storage or choose(db, None, "storage").instance
            forget(storage, key)
    return len(rows)
