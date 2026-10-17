"""The whole-business export: a ZIP with one CSV per table the business holds, plus its files.

Built from the business's own session, so row-level security keeps it to this business. The
tables are found in the database, not listed by hand: a new tenant table is exported without
anyone remembering to add it (secrets and binary columns are left out, see data_rights)."""

import csv
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.brand import NAME
from app.core.data_rights import BUSINESS_EXPORT_SKIP, SECRET_COLUMN_PARTS
from app.files import read_file
from app.providers.storage import StorageError

# The archive is built in memory; past this the remaining files are listed but not included.
MAX_FILE_BYTES = 150 * 1024 * 1024

README = """Your business data from {brand}
Exported: {when}

data/*.csv     one file per kind of record (UTF-8, opens in Excel).
files/         the files of your business (the Files area).
client_documents/<client id>/   files kept on each client's card.
skipped_files.txt  files left out because the archive reached its size limit (if any).

Left out on purpose: passwords and sign-in tokens, keys of connected services, ID numbers
(kept encrypted, a client's ID can be exported from their card) and card data.
"""


def _columns(db: Session, table: str) -> list[str]:
    rows = db.execute(
        text("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'app' AND table_name = :t ORDER BY ordinal_position
        """),
        {"t": table},
    ).all()
    return [
        name
        for name, kind in rows
        if kind != "bytea" and not any(part in name for part in SECRET_COLUMN_PARTS)
    ]


def _tables(db: Session) -> list[tuple[str, str]]:
    """(table, the column holding the business) for every readable table of the business."""
    rows = db.execute(
        text("""
            SELECT c.relname, 'tenant_id' FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = 'app' AND c.relkind = 'r' AND a.attname = 'tenant_id'
              AND NOT a.attisdropped AND has_table_privilege(c.oid, 'SELECT')
            ORDER BY c.relname
        """)
    ).all()
    found = [(t, col) for t, col in rows if t not in BUSINESS_EXPORT_SKIP]
    return [("tenants", "id"), *found]


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _csv(db: Session, table: str, scope: str, tenant_id: UUID) -> tuple[bytes, int] | None:
    columns = _columns(db, table)
    if not columns:
        return None
    names = ", ".join(f'"{c}"' for c in columns)
    result = db.execute(
        text(f'SELECT {names} FROM app."{table}" WHERE "{scope}" = :t'),
        {"t": tenant_id},
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    count = 0
    while chunk := result.fetchmany(1000):
        for row in chunk:
            writer.writerow([_cell(v) for v in row])
            count += 1
    return out.getvalue().encode("utf-8-sig"), count


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip() or "file"


def build_archive(db: Session, tenant_id: UUID) -> tuple[bytes, int]:
    """The ZIP and how many files (CSVs and uploads) it holds."""
    buffer = io.BytesIO()
    files = 0
    skipped: list[str] = []
    size = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.txt", README.format(brand=NAME, when=datetime.now(UTC).isoformat())
        )
        for table, scope in _tables(db):
            built = _csv(db, table, scope, tenant_id)
            if built is not None:
                archive.writestr(f"data/{table}.csv", built[0])
                files += 1

        def add(path: str, row: dict[str, Any]) -> None:
            nonlocal files, size
            if size + (row.get("size") or 0) > MAX_FILE_BYTES:
                skipped.append(path)
                return
            try:
                payload = read_file(db, row)
            except (HTTPException, StorageError, LookupError):
                skipped.append(path)
                return
            size += len(payload)
            archive.writestr(path, payload)
            files += 1

        for row in db.execute(
            text("""
                SELECT f.id, f.name, f.content_type, f.size, f.content, f.storage_key, f.encrypted,
                       coalesce(d.name, '') AS folder
                FROM app.business_files f LEFT JOIN app.file_folders d ON d.id = f.folder_id
                WHERE f.tenant_id = :t ORDER BY f.created_at
            """),
            {"t": tenant_id},
        ).mappings():
            add(
                f"files/{_safe(row['folder'])}/{str(row['id'])[:8]}_{_safe(row['name'])}", dict(row)
            )
        for row in db.execute(
            text("""
                SELECT id, client_id, name, size, content, storage_key, false AS encrypted
                FROM app.client_documents
                WHERE tenant_id = :t ORDER BY created_at
            """),
            {"t": tenant_id},
        ).mappings():
            add(
                f"client_documents/{row['client_id']}/{str(row['id'])[:8]}_{_safe(row['name'])}",
                dict(row),
            )
        if skipped:
            archive.writestr("skipped_files.txt", "\n".join(skipped))
    return buffer.getvalue(), files
