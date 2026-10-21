"""Retention and closure jobs: purging old rows, deleting closed businesses."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, text

from app.core.retention import CLOSED_BUSINESS_GRACE_DAYS
from app.core.tenant_scope import tenant_scope
from app.files import forget, purge_expired_files
from app.providers.choice import choose

RETENTION_MONTHS = {
    "leads": 12,
    "contact_requests": 12,
    "ai_conversations": 12,
    "whatsapp_conversations": 12,  # AI chats, on WhatsApp
    "whatsapp_inbox": 12,  # the clients' messages those chats answered
    "messages": 24,
    "audit_log": 24,  # the owner's record of who did what
}


PURGE_BATCH = 5000  # rows per DELETE


def purge_expired(conn: Connection, now: datetime | None = None) -> dict[str, int]:
    """Deletes what has passed its time: leads that never became clients and nobody touched,
    website and in-app requests, the AI's conversations (in the app and on WhatsApp) with the
    WhatsApp messages they answered, the message log, the audit log and files past their expiry."""
    now = now or datetime.now(UTC)

    def before(kind: str) -> datetime:
        return now - timedelta(days=round(RETENTION_MONTHS[kind] * 30.44))

    # Each statement deletes at most PURGE_BATCH rows; _delete_in_batches repeats it.
    statements = {
        "leads": """
            DELETE FROM app.leads WHERE ctid = ANY(ARRAY(
                SELECT l.ctid FROM app.leads l
                WHERE l.client_id IS NULL
                  AND greatest(l.updated_at, coalesce((SELECT max(a.occurred_at)
                      FROM app.lead_activities a WHERE a.lead_id = l.id), l.updated_at)) < :before
                LIMIT :batch))
        """,
        "contact_requests": """
            DELETE FROM app.contact_requests WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.contact_requests
                WHERE created_at < :before LIMIT :batch))
        """,
        "ai_conversations": """
            DELETE FROM app.ai_conversations WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.ai_conversations
                WHERE updated_at < :before LIMIT :batch))
        """,
        "whatsapp_conversations": """
            DELETE FROM app.whatsapp_conversations WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.whatsapp_conversations
                WHERE updated_at < :before LIMIT :batch))
        """,
        "whatsapp_inbox": """
            DELETE FROM app.whatsapp_inbox WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.whatsapp_inbox
                WHERE received_at < :before LIMIT :batch))
        """,
        "messages": """
            DELETE FROM app.messages WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.messages
                WHERE created_at < :before LIMIT :batch))
        """,
        "audit_log": """
            DELETE FROM app.audit_log WHERE ctid = ANY(ARRAY(
                SELECT ctid FROM app.audit_log
                WHERE occurred_at < :before LIMIT :batch))
        """,
    }
    deleted = {
        kind: _delete_in_batches(conn, sql, before(kind)) for kind, sql in statements.items()
    }
    deleted["data_exports"] = purge_expired_exports(conn)
    deleted["files"] = purge_expired_files(conn)  # e.g. the imports folder keeps files 30 days
    return deleted


def _delete_in_batches(conn: Connection, sql: str, before: datetime) -> int:
    """Runs a statement that deletes up to :batch rows until it deletes fewer, so no single
    statement holds millions of rows (and their locks) at once."""
    total = 0
    while True:
        count = conn.execute(text(sql), {"before": before, "batch": PURGE_BATCH}).rowcount
        total += count
        if count < PURGE_BATCH:
            return total


def purge_expired_exports(conn: Connection) -> int:
    """Deletes business exports past their 24 hours, from storage too."""
    rows = conn.execute(
        text("DELETE FROM app.data_exports WHERE expires_at < now() RETURNING storage_key")
    ).all()
    _forget_keys(conn, [key for (key,) in rows if key])
    return len(rows)


def _forget_keys(conn: Connection, keys: list[str]) -> None:
    storage = None
    for key in keys:
        storage = storage or choose(conn, None, "storage").instance
        forget(storage, key)


def delete_closed_businesses(
    conn: Connection, now: datetime | None = None, apply: bool = False
) -> dict[str, int | list[str]]:
    """Deletes businesses whose owner closed the account more than CLOSED_BUSINESS_GRACE_DAYS ago,
    with everything under them (every tenant table cascades). Irreversible, so it only reports
    what it would delete unless `apply` is true. People's sign-in accounts are kept: they may
    own or work in other businesses. Each deletion is noted in the MyBiz audit log."""
    now = now or datetime.now(UTC)
    due = (
        conn.execute(
            text("""
                SELECT id, name, closed_at FROM app.tenants
                WHERE closed_at < :before ORDER BY closed_at
            """),
            {"before": now - timedelta(days=CLOSED_BUSINESS_GRACE_DAYS)},
        )
        .mappings()
        .all()
    )
    if apply:
        for business in due:
            with tenant_scope(conn, business["id"]):
                conn.execute(
                    text("""
                        INSERT INTO app.platform_audit (actor_email, action, details)
                        VALUES ('system', 'business.deleted', jsonb_build_object(
                            'business_id', CAST(:id AS text), 'name', CAST(:name AS text),
                            'closed_at', CAST(:closed_at AS text)))
                    """),
                    {
                        "id": business["id"],
                        "name": business["name"],
                        "closed_at": business["closed_at"],
                    },
                )
                # The files in the storage provider are not under the tenant row, so they go first.
                keys = conn.execute(
                    text("""
                        SELECT storage_key FROM app.client_documents
                            WHERE tenant_id = :id AND storage_key IS NOT NULL
                        UNION ALL SELECT storage_key FROM app.business_files
                            WHERE tenant_id = :id AND storage_key IS NOT NULL
                        UNION ALL SELECT storage_key FROM app.data_exports
                            WHERE tenant_id = :id AND storage_key IS NOT NULL
                    """),
                    {"id": business["id"]},
                ).scalars()
                _forget_keys(conn, list(keys))
                conn.execute(text("DELETE FROM app.tenants WHERE id = :id"), {"id": business["id"]})
    return {
        "dry_run": 0 if apply else 1,
        "businesses": len(due),
        "ids": [str(business["id"]) for business in due],
    }
