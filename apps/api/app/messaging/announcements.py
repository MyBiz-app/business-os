"""The broadcast center's sender (round 5, M1; the send-announcements job in app/jobs/).

A due announcement is resolved to one delivery per person and channel, then sent:
- email through the platform's email provider (a marketing one carries "Ad" in the subject and
  a signed opt-out link),
- push to the person's phones,
- pop-up: nothing to send, the person's next visit shows it (app.my_announcements()),
- WhatsApp / SMS: queued in the businesses' outbox for the clients that have a phone; the paid
  providers stay disabled adapters, so these go through the simulated provider until one is
  connected.

A failure of one delivery is kept on its row and never stops the others."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text

from app.core.config import get_settings
from app.core.signed_links import sign
from app.messaging import email_layout as layout
from app.messaging.contact_emails import resolve_email, sender_name
from app.messaging.email import Email, Sender, load_messages
from app.messaging.placeholders import client_values, lead_values, render_placeholders
from app.messaging.push import PushSender, push_to_user

BATCH = 200
MAX_ATTEMPTS = 3
UNSUBSCRIBE_TTL = 365 * 24 * 3600
MESSAGE_LIMIT = 1100  # app.messages.body


def content_for(content: dict[str, Any], locale: str) -> dict[str, str]:
    """The texts in the person's language; the other language when theirs is empty."""
    primary = content.get(locale) or {}
    other = content.get("en" if locale == "he" else "he") or {}
    return {
        key: str(primary.get(key) or other.get(key) or "")
        for key in ("subject", "body", "cta_label", "cta_url", "image_url")
    }


def unsubscribe_link(email: str, announcement_id: UUID) -> str:
    token = sign(f"unsub|{email}|{announcement_id}", ttl=UNSUBSCRIBE_TTL)
    return f"{get_settings().api_url}/public/announcements/unsubscribe?t={token}"


def _lang(locale: str) -> str:
    return locale if locale in ("he", "en") else "he"


def personalize(texts: dict[str, str], values: dict[str, str] | None) -> dict[str, str]:
    """A business's message may use the placeholders; MyBiz's own never does (`values` None)."""
    if values is None:
        return texts
    return {key: render_placeholders(value, values) for key, value in texts.items()}


def _email(
    row: dict[str, Any],
    texts: dict[str, str],
    messages: dict[str, Any],
    brand: str | None = None,
    reply_to: str | None = None,
) -> Email:
    """`brand` is the issuing business, when it is not MyBiz itself."""
    broadcast = messages["broadcast"]
    brand_name = brand or layout.BRAND
    marketing = row["kind"] == "marketing"
    lang = _lang(row["locale"])
    subject = texts["subject"]
    if marketing:
        subject = broadcast["adSubject"].replace("{subject}", subject)
    parts = [texts["body"]]
    if texts["cta_url"]:
        parts.append(f"{texts['cta_label']}: {texts['cta_url']}".lstrip(": "))
    link = unsubscribe_link(row["email"], row["announcement_id"]) if marketing else None
    foot = (
        broadcast["footerMarketing"]
        if marketing
        else broadcast["footerService"].replace("{brand}", brand_name)
    )
    if link:
        parts.append(f"{foot}\n{broadcast['unsubscribe']}: {link}")
    else:
        parts.append(foot)

    image = (
        f'<img src="{layout.e(texts["image_url"])}" alt="" width="100%" '
        'style="display:block;max-width:100%;border-radius:12px;margin:0 0 16px">'
        if texts["image_url"]
        else ""
    )
    body = (
        layout.title(subject, lang)
        + image
        + "".join(layout.text_block(b, lang) for b in texts["body"].split("\n\n") if b.strip())
        + (
            layout.button(texts["cta_label"] or texts["cta_url"], texts["cta_url"])
            if texts["cta_url"]
            else ""
        )
        + layout.paragraph(foot, lang, muted=True)
        + (layout.link_fallback(link, lang) if link else "")
    )
    html = layout.shell(
        [layout.Section(lang, body)],
        subject=subject,
        preheader=texts["body"].split("\n")[0],
        brand=brand_name,
        footer=[(lang, brand_name)],
        kind="broadcast",
    )
    return Email(
        to=row["email"],
        subject=subject,
        text="\n\n".join(part for part in parts if part),
        html=html,
        locale=lang,
        kind="broadcast",
        reply_to=reply_to,
        from_name=brand,
        list_unsubscribe=link,
    )


def _location(announcement: dict[str, Any]) -> UUID | None:
    value = (announcement["audience"] or {}).get("location_id")
    return UUID(value) if value else None


def sender_name_for(conn: Connection, announcement: dict[str, Any]) -> str:
    """The issuing business's name as the sender (its branch when it has a contact of its own)."""
    return sender_name(conn, announcement["tenant_id"], _location(announcement)) or layout.BRAND


def _queue_deliveries(conn: Connection, announcement: dict[str, Any]) -> int:
    """One row per person and channel they can be reached on. Idempotent: a run that stopped
    half-way is simply run again (the unique key skips what exists)."""
    if announcement["issuer"] == "tenant":
        people = (
            conn.execute(
                text(
                    "SELECT * FROM app.tenant_announcement_recipients("
                    "CAST(:t AS uuid), CAST(:a AS jsonb), :kind)"
                ),
                {
                    "t": announcement["tenant_id"],
                    "a": json.dumps(announcement["audience"]),
                    "kind": announcement["kind"],
                },
            )
            .mappings()
            .all()
        )
    else:
        people = (
            conn.execute(
                text("SELECT * FROM app.announcement_recipients(CAST(:a AS jsonb), :kind)"),
                {"a": json.dumps(announcement["audience"]), "kind": announcement["kind"]},
            )
            .mappings()
            .all()
        )
    for person in people:
        for channel in announcement["channels"]:
            reachable = {
                "email": bool(person["email"]),
                "push": bool(person["has_push"]),
                "popup": person["user_id"] is not None,
                "whatsapp": bool(person["phone"]) and person["client_id"] is not None,
                "sms": bool(person["phone"]) and person["client_id"] is not None,
            }[channel]
            conn.execute(
                text("""
                    INSERT INTO app.announcement_deliveries
                        (announcement_id, channel, person_key, user_id, client_id, tenant_id,
                         email, phone, locale, status, first_name)
                    VALUES (:a, :channel, :key, :user, :client, :tenant, :email, :phone,
                            :locale, :status, :first_name)
                    ON CONFLICT (announcement_id, channel, person_key) DO NOTHING
                """),
                {
                    "a": announcement["id"],
                    "channel": channel,
                    "key": person["person_key"],
                    "user": person["user_id"],
                    "client": person["client_id"],
                    "tenant": person["tenant_id"],
                    "email": person["email"],
                    "phone": person["phone"],
                    "locale": _lang(person["locale"] or "he"),
                    "status": "queued" if reachable else "skipped",
                    "first_name": person.get("first_name"),
                },
            )
    conn.execute(
        text("UPDATE app.announcements SET recipient_count = :n, updated_at = now() WHERE id = :a"),
        {"n": len(people), "a": announcement["id"]},
    )
    return len(people)


def _finish_delivery(
    conn: Connection, delivery_id: UUID, status: str, error: str | None = None, final: bool = True
) -> None:
    conn.execute(
        text("""
            UPDATE app.announcement_deliveries
            SET attempts = attempts + 1, error = :error,
                status = CASE WHEN :status = 'queued' AND NOT :final THEN 'queued'
                              WHEN :status = 'queued' THEN 'failed' ELSE :status END,
                sent_at = CASE WHEN :status = 'sent' THEN now() END
            WHERE id = :id
        """),
        {"id": delivery_id, "status": status, "error": error, "final": final},
    )


def _send_batch(
    conn: Connection,
    announcement: dict[str, Any],
    sender: Sender | None,
    push: PushSender | None,
    counts: dict[str, int],
) -> int:
    rows = (
        conn.execute(
            text("""
                SELECT d.id, d.announcement_id, d.channel, d.user_id, d.client_id, d.tenant_id,
                       d.email, d.phone, d.locale, d.attempts, d.first_name, a.kind, a.issuer,
                       a.audience
                FROM app.announcement_deliveries d
                JOIN app.announcements a ON a.id = d.announcement_id
                WHERE d.announcement_id = :a AND d.status = 'queued'
                ORDER BY d.created_at LIMIT :batch
                FOR UPDATE OF d SKIP LOCKED
            """),
            {"a": announcement["id"], "batch": BATCH},
        )
        .mappings()
        .all()
    )
    mailbox: dict[str, dict[str, Any]] = {}
    business = None
    location_id = None
    if announcement["issuer"] == "tenant":
        business = sender_name_for(conn, announcement)
        location_id = _location(announcement)
    values: dict[Any, dict[str, str]] = {}
    if business is not None:
        values = client_values(
            conn,
            announcement["tenant_id"],
            [r["client_id"] for r in rows if r["client_id"]],
            business,
        )
    for row in rows:
        lang = _lang(row["locale"])
        person = None
        if business is not None:  # staff and others without a client record: name and contact
            person = values.get(row["client_id"]) or lead_values(
                {"first_name": row["first_name"], "phone": row["phone"], "email": row["email"]},
                business,
            )
        texts = personalize(content_for(announcement["content"], lang), person)
        channel = row["channel"]
        try:
            if channel == "popup":
                conn.execute(
                    text(
                        "UPDATE app.announcement_deliveries SET status = 'sent', sent_at = now()"
                        " WHERE id = :id"
                    ),
                    {"id": row["id"]},
                )
            elif channel == "email":
                if sender is None:
                    _finish_delivery(conn, row["id"], "skipped", "no email provider")
                    counts["skipped"] += 1
                    continue
                if lang not in mailbox:
                    mailbox[lang] = load_messages(lang)
                reply_to = (
                    resolve_email(conn, announcement["tenant_id"], "reply_to", location_id)
                    if business
                    else None
                )
                sender.send(_email(dict(row), texts, mailbox[lang], business, reply_to))
                _finish_delivery(conn, row["id"], "sent")
            elif channel == "push":
                if push is None or not push_to_user(
                    conn, push, row["user_id"], texts["subject"], texts["body"]
                ):
                    _finish_delivery(conn, row["id"], "skipped", "no push delivered")
                    counts["skipped"] += 1
                    continue
                _finish_delivery(conn, row["id"], "sent")
            else:  # whatsapp / sms: the business's outbox sends it through its provider
                body = "\n".join(p for p in (texts["body"], texts["cta_url"]) if p)
                conn.execute(
                    text("""
                        INSERT INTO app.messages
                            (tenant_id, client_id, channel, to_phone, body, status)
                        VALUES (:tenant, :client, :channel, :phone, :body, 'queued')
                    """),
                    {
                        "tenant": row["tenant_id"],
                        "client": row["client_id"],
                        "channel": channel,
                        "phone": row["phone"][:30],
                        "body": body[:MESSAGE_LIMIT] or "-",
                    },
                )
                _finish_delivery(conn, row["id"], "sent")
            counts["sent"] += 1
        except Exception as error:  # one provider error must not stop the batch
            counts["failed"] += 1
            print(f"announcement delivery {row['id']} failed: {error}")
            _finish_delivery(
                conn,
                row["id"],
                "queued",
                str(error)[:500],
                final=row["attempts"] + 1 >= MAX_ATTEMPTS,
            )
    return len(rows)


def send_announcements(
    conn: Connection,
    sender: Sender | None,
    push: PushSender | None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Starts the announcements that are due and sends a batch of each one running."""
    now = now or datetime.now(UTC)
    conn.execute(
        text("""
            UPDATE app.announcements SET status = 'sending', updated_at = now()
            WHERE status = 'scheduled' AND coalesce(scheduled_at, now()) <= :now
        """),
        {"now": now},
    )
    running = (
        conn.execute(
            text("SELECT * FROM app.announcements WHERE status = 'sending' ORDER BY scheduled_at")
        )
        .mappings()
        .all()
    )
    counts = {"started": 0, "sent": 0, "failed": 0, "skipped": 0, "finished": 0}
    for announcement in running:
        announcement = dict(announcement)
        if announcement["recipient_count"] is None:
            _queue_deliveries(conn, announcement)
            counts["started"] += 1
        _send_batch(conn, announcement, sender, push, counts)
        left = conn.execute(
            text(
                "SELECT count(*) FROM app.announcement_deliveries"
                " WHERE announcement_id = :a AND status = 'queued'"
            ),
            {"a": announcement["id"]},
        ).scalar_one()
        if left == 0:
            conn.execute(
                text("""
                    UPDATE app.announcements
                    SET status = 'sent', sent_at = now(), updated_at = now() WHERE id = :a
                """),
                {"a": announcement["id"]},
            )
            counts["finished"] += 1
    return counts
