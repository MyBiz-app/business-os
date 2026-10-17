"""Re-encrypts what is stored under an older `API_SECRETS_KEYS` key with the newest one (GL6).

Run `python -m app.jobs rotate-secrets` (a dry run that only counts) and then with `--apply`.
Every run is safe to repeat or to stop half-way: a value the newest key already opens is left
alone, and each one is rewritten on its own. Steps are in docs/runbooks/key-rotation.md."""

from sqlalchemy import Connection, text

from app.providers.choice import choose
from app.providers.secrets import is_current, rotate

BATCH = 200

# (table, encrypted bytea column): every place the platform key seals a database value.
COLUMNS: tuple[tuple[str, str], ...] = (
    ("tenant_integrations", "secrets"),
    ("social_accounts", "secrets"),
    ("social_pending", "candidates"),
    ("person_identities", "id_number_encrypted"),
    ("employment_profiles", "bank_encrypted"),
    ("form101_forms", "answers_encrypted"),
)


def _rotate_column(conn: Connection, table: str, column: str, apply: bool) -> dict[str, int]:
    stale = done = 0
    after = None
    while True:
        rows = conn.execute(
            text(f"""
                SELECT ctid::text AS pos, {column} AS blob FROM app.{table}
                WHERE {column} IS NOT NULL AND (CAST(:after AS text) IS NULL
                      OR ctid > CAST(:after AS tid))
                ORDER BY ctid LIMIT :batch
            """),
            {"after": after, "batch": BATCH},
        ).all()
        if not rows:
            return {"stale": stale, "rotated": done}
        for pos, blob in rows:
            if is_current(blob):
                continue
            stale += 1
            if apply:
                conn.execute(
                    text(f"UPDATE app.{table} SET {column} = :blob WHERE ctid = CAST(:pos AS tid)"),
                    {"blob": rotate(blob), "pos": pos},
                )
                done += 1
        after = rows[-1][0]


def _rotate_files(conn: Connection, apply: bool) -> dict[str, int]:
    """Sealed files (payslips, employee papers): kept in the database or in the object store."""
    stale = done = 0
    rows = conn.execute(
        text("""
            SELECT id, tenant_id, content_type, content, storage_key FROM app.business_files
            WHERE encrypted
        """)
    ).mappings()
    for row in list(rows):
        if row["storage_key"] is None:
            payload = bytes(row["content"])
        else:
            storage = choose(conn, row["tenant_id"], "storage").instance
            payload = storage.get(row["storage_key"])
        if is_current(payload):
            continue
        stale += 1
        if not apply:
            continue
        sealed = rotate(payload)
        if row["storage_key"] is None:
            conn.execute(
                text("UPDATE app.business_files SET content = :c WHERE id = :id"),
                {"c": sealed, "id": row["id"]},
            )
        else:
            storage.put(row["storage_key"], sealed, row["content_type"])
        done += 1
    return {"stale": stale, "rotated": done}


def rotate_secrets(conn: Connection, apply: bool = False) -> dict[str, dict[str, int]]:
    """Per place: how many values the newest key does not open yet (`stale`) and how many were
    re-encrypted (`rotated`, only with `apply`). Fails on a value no listed key opens."""
    report = {
        f"{table}.{column}": _rotate_column(conn, table, column, apply) for table, column in COLUMNS
    }
    report["business_files"] = _rotate_files(conn, apply)
    return report
