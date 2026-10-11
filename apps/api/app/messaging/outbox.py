"""Work handed to outside providers by the jobs (decision X13): messages waiting in the outbox
and receipts waiting for their legal document. Each business's own provider is used (or the
platform default). A failure is kept on the row and tried again on the next run, up to
MAX_ATTEMPTS; one provider's failure never stops the others."""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import Connection, text

from app.providers.choice import Chosen, choose
from app.providers.invoicing import DocumentLine, InvoiceDocument
from app.providers.messaging import OutgoingMessage

MAX_ATTEMPTS = 5
BATCH = 500


def _per_tenant(conn: Connection, capability: str) -> Callable[[UUID], Chosen | None]:
    cache: dict[UUID, Chosen | None] = {}

    def get(tenant_id: UUID) -> Chosen | None:
        if tenant_id not in cache:
            try:
                cache[tenant_id] = choose(conn, tenant_id, capability)  # type: ignore[arg-type]
            except Exception:  # a broken connection: those rows wait, others go on
                cache[tenant_id] = None
        return cache[tenant_id]

    return get


def send_messages(conn: Connection) -> dict[str, int]:
    """Sends queued WhatsApp / SMS messages through each business's messaging provider."""
    rows = (
        conn.execute(
            text("""
                SELECT id, tenant_id, channel, to_phone, body, attempts FROM app.messages
                WHERE status = 'queued' AND attempts < :max
                ORDER BY created_at LIMIT :batch
                FOR UPDATE SKIP LOCKED
            """),
            {"max": MAX_ATTEMPTS, "batch": BATCH},
        )
        .mappings()
        .all()
    )
    provider_of = _per_tenant(conn, "messaging")
    counts = {"sent": 0, "failed": 0, "waiting": 0}
    for row in rows:
        chosen = provider_of(row["tenant_id"])
        if chosen is None:
            counts["waiting"] += 1
            continue
        try:
            result = chosen.instance.send(
                OutgoingMessage(
                    message_id=str(row["id"]),
                    channel=row["channel"],
                    to=row["to_phone"],
                    body=row["body"],
                )
            )
            status, ref, error = result.status, result.provider_ref, result.error
        except Exception as caught:  # the provider is down: try again next run
            status, ref, error = "queued", None, str(caught)[:500]
        final = status == "failed" or row["attempts"] + 1 >= MAX_ATTEMPTS
        conn.execute(
            text("""
                UPDATE app.messages
                SET status = CASE WHEN :status = 'queued' AND :final THEN 'failed'
                                  ELSE :status END,
                    provider = :provider, provider_ref = :ref, error = :error,
                    attempts = attempts + 1, simulated = :simulated,
                    sent_at = CASE WHEN :status = 'sent' THEN now() END
                WHERE id = :id
            """),
            {
                "status": status,
                "final": final,
                "provider": chosen.info.name,
                "ref": ref,
                "error": error,
                "simulated": chosen.instance.simulated,
                "id": row["id"],
            },
        )
        counts["sent" if status == "sent" else "failed" if status == "failed" else "waiting"] += 1
    return counts


def issue_documents(conn: Connection) -> dict[str, int]:
    """Issues each new receipt's legal document with the business's invoicing provider; the
    built-in `internal` provider keeps the receipt itself as the document."""
    rows = (
        conn.execute(
            text("""
                SELECT r.id, r.tenant_id, r.number, r.issued_at, r.business_name, r.client_name,
                       r.client_email, r.description, r.amount, r.currency, r.method,
                       r.document_attempts, t.locale
                FROM app.receipts r JOIN app.tenants t ON t.id = r.tenant_id
                WHERE r.document_status = 'pending' AND r.document_attempts < :max
                ORDER BY r.issued_at LIMIT :batch
                FOR UPDATE OF r SKIP LOCKED
            """),
            {"max": MAX_ATTEMPTS, "batch": BATCH},
        )
        .mappings()
        .all()
    )
    provider_of = _per_tenant(conn, "invoicing")
    counts = {"issued": 0, "internal": 0, "failed": 0, "waiting": 0}
    for row in rows:
        chosen = provider_of(row["tenant_id"])
        if chosen is None:
            counts["waiting"] += 1
            continue
        document = InvoiceDocument(
            receipt_id=str(row["id"]),
            receipt_number=row["number"],
            issued_at=row["issued_at"],
            business_name=row["business_name"],
            client_name=row["client_name"],
            client_email=row["client_email"],
            lines=(DocumentLine(row["description"] or "", 1, row["amount"]),),
            total=row["amount"],
            currency=row["currency"],
            payment_method=row["method"] or "card",
            locale=row["locale"],
        )
        try:
            issued = chosen.instance.issue(document)
            if issued.number is None and issued.url is None:
                status, error = "internal", None
            else:
                status, error = "issued", None
        except Exception as caught:  # InvoicingUnavailable or a broken provider: retry later
            issued, error = None, str(caught)[:500]
            status = "failed" if row["document_attempts"] + 1 >= MAX_ATTEMPTS else "pending"
        conn.execute(
            text("""
                UPDATE app.receipts
                SET document_status = :status, document_provider = :provider,
                    document_number = :number, document_url = :url, document_error = :error,
                    document_attempts = document_attempts + 1
                WHERE id = :id
            """),
            {
                "status": status,
                "provider": chosen.info.name,
                "number": issued.number if issued else None,
                "url": issued.url if issued else None,
                "error": error,
                "id": row["id"],
            },
        )
        counts[status if status != "pending" else "waiting"] += 1
    return counts
