"""Emailing client notifications (the send-emails job; see app/jobs/).

The text comes from the shared translation files: packages/i18n/messages is the source and
app/messages holds the API's checked-in copy (pnpm --filter @business-os/i18n export:api), so
both the API image and the jobs can render emails. A notification is emailed once, within a
day of happening; older ones, and ones for clients without an email address, are skipped."""

import json
import re
import smtplib
import ssl
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.messaging import email_layout as layout
from app.messaging.push import PushSender, push_to_user

MESSAGES_DIR = Path(__file__).resolve().parent.parent / "messages"
FRESH_FOR = timedelta(days=1)
MAX_ATTEMPTS = 3
BATCH = 200


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str | None = None  # a designed version; otherwise the text is put in the MyBiz layout
    locale: str = "he"
    details: tuple[tuple[str, str], ...] = ()  # label/value lines shown in a card (class, time)
    kind: str | None = None  # picks the icon in the layout (a notification kind, "roster", ...)
    reply_to: str | None = None  # where replies go (the business's or branch's own address)
    from_name: str | None = None  # the business or branch shown as the sender's name
    list_unsubscribe: str | None = None  # the opt-out link of an ad (List-Unsubscribe header)
    website: str | None = None  # the business's or branch's site, shown in the footer


def _unsubscribe_headers(link: str) -> dict[str, str]:
    return {"List-Unsubscribe": f"<{link}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def _html(email: Email) -> str:
    if email.html is not None:
        return email.html
    lang = email.locale if email.locale in ("he", "en") else "he"
    greeting, _, rest = email.text.partition("\n\n")
    card = layout.detail_card(list(email.details), lang) if email.details else ""
    body = (
        layout.text_block(greeting, lang)
        + card
        + "".join(layout.text_block(block, lang) for block in rest.split("\n\n") if block.strip())
    )
    footer = (
        "הודעה אוטומטית, אין צורך להשיב."
        if lang == "he"
        else "Automated message, no need to reply."
    )
    return layout.shell(
        [layout.Section(lang, layout.title(email.subject, lang) + body)],
        subject=email.subject,
        preheader=greeting.split("\n")[0],
        brand=layout.BRAND,
        footer=[(lang, " · ".join(p for p in (layout.BRAND, footer, email.website) if p))],
        kind=email.kind,
    )


class Sender(Protocol):
    def send(self, email: Email) -> None: ...


class LogSender:
    """Prints instead of sending (local development and dry runs)."""

    def __init__(self) -> None:
        self.sent: list[Email] = []

    def send(self, email: Email) -> None:
        self.sent.append(email)
        print(f"email to {email.to}: {email.subject}")


def _from_header(default: str, name: str | None) -> str:
    """The configured sender address with the business's name as the display name."""
    if not name:
        return default
    address = parseaddr(default)[1]
    return formataddr((name.replace('"', "").replace("\n", " ")[:80], address))


class ResendSender:
    """Resend's HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    def send(self, email: Email) -> None:
        payload: dict[str, Any] = {
            "from": _from_header(self.sender, email.from_name),
            "to": [email.to],
            "subject": email.subject,
            "text": email.text,
            "html": _html(email),
        }
        if email.reply_to:
            payload["reply_to"] = email.reply_to
        if email.list_unsubscribe:
            payload["headers"] = _unsubscribe_headers(email.list_unsubscribe)
        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 (fixed https URL)
            response.read()


class SmtpSender:
    """Plain SMTP over TLS. With Gmail (an app password, no domain needed) this is the free
    option for a prototype: it sends from the Gmail address, up to a few hundred a day."""

    def __init__(self, host: str, port: int, username: str, password: str, sender: str) -> None:
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.sender = sender

    def message(self, email: Email) -> EmailMessage:
        message = EmailMessage()
        message["From"] = _from_header(self.sender, email.from_name)
        message["To"] = email.to
        if email.reply_to:
            message["Reply-To"] = email.reply_to
        message["Subject"] = email.subject
        if email.list_unsubscribe:
            for name, value in _unsubscribe_headers(email.list_unsubscribe).items():
                message[name] = value
        message.set_content(email.text)
        message.add_alternative(_html(email), subtype="html")
        return message

    def send(self, email: Email) -> None:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=20) as server:
            server.login(self.username, self.password)
            server.send_message(self.message(email))


def load_all_messages(locale: str, directory: Path = MESSAGES_DIR) -> dict[str, Any]:
    return json.loads((directory / f"{locale}.json").read_text(encoding="utf-8"))


def load_messages(locale: str, directory: Path = MESSAGES_DIR) -> dict[str, Any]:
    return load_all_messages(locale, directory)["email"]


def _fill(template: str, values: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), template)


def _when(value: Any, time_zone: str) -> str:
    if not value:
        return ""
    instant = datetime.fromisoformat(str(value))
    return instant.astimezone(ZoneInfo(time_zone)).strftime("%d/%m %H:%M")


def _day(value: Any) -> str:
    if not value:
        return ""
    return datetime.fromisoformat(str(value)).strftime("%d/%m")


def render(
    messages: dict[str, Any], kind: str, payload: dict[str, Any], row: dict[str, Any]
) -> tuple[str, str]:
    if kind == "booked_by_studio" and payload.get("status") == "waitlisted":
        kind = "waitlisted_by_studio"
    values = {
        "name": row["first_name"],
        "business": row["business"],
        "service": str(payload.get("service_name", "")),
        "when": _when(payload.get("starts_at"), row["time_zone"]),
        "previous": _when(payload.get("previous_starts_at"), row["time_zone"]),
        "note": str(payload.get("note") or ""),
        "plan": str(payload.get("plan_name", "")),
        "date": _day(payload.get("ends_on")),
        "from": _day(payload.get("starts_on")),
        "friend": str(payload.get("from_name", "")),
    }
    subject = _fill(messages["subject"][kind], values)
    lines = [_fill(messages["greeting"], values), "", _fill(messages["body"][kind], values)]
    if values["note"]:
        lines.append(_fill(messages["note"], values))
    lines += ["", _fill(messages["footer"], values)]
    return subject, "\n".join(lines)


def details_of(messages: dict[str, Any], payload: dict[str, Any], row: dict[str, Any]) -> tuple:
    """The class and time of a booking-style notification, for the email's detail card."""
    service, when = payload.get("service_name"), _when(payload.get("starts_at"), row["time_zone"])
    if not (service and when):
        return ()
    labels = messages.get("details", {})
    return ((labels.get("service", "Class"), str(service)), (labels.get("when", "When"), when))


EMAIL_DETAILS = json.dumps({"channel": "email", "automated": True})


def _reply_to(conn: Connection, tenant_id: Any, cache: dict[Any, str | None]) -> str | None:
    """Replies to a business's emails go to its reply-to address (the owner's by default)."""
    if tenant_id not in cache:
        from app.messaging.contact_emails import resolve_email

        cache[tenant_id] = resolve_email(conn, tenant_id, "reply_to")
    return cache[tenant_id]


def send_emails(
    conn: Connection,
    sender: Sender | None,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
    push: PushSender | None = None,
) -> dict[str, int]:
    """Emails pending notifications; clients who use the app and registered a phone get a push
    instead, with the email as the fallback. Returns counts per outcome."""
    now = now or datetime.now(UTC)
    skipped = conn.execute(
        text("""
            UPDATE app.notifications n SET email_status = 'skipped'
            FROM app.clients c
            WHERE n.email_status = 'pending' AND c.id = n.client_id
              AND (n.created_at < :oldest OR c.erased_at IS NOT NULL
                   OR (c.email IS NULL AND (c.user_id IS NULL OR :push = false)))
        """),
        {"oldest": now - FRESH_FOR, "push": push is not None},
    ).rowcount
    rows = (
        conn.execute(
            text("""
                SELECT n.id, n.tenant_id, n.kind, n.payload, c.email, c.first_name, c.user_id,
                       t.name AS business, t.website_url,
                       t.locale, t.time_zone
                FROM app.notifications n
                JOIN app.clients c ON c.id = n.client_id
                JOIN app.tenants t ON t.id = n.tenant_id
                WHERE n.email_status = 'pending'
                ORDER BY n.created_at LIMIT :batch
                FOR UPDATE OF n SKIP LOCKED
            """),
            {"batch": BATCH},
        )
        .mappings()
        .all()
    )
    messages: dict[str, dict[str, Any]] = {}
    reply_cache: dict[Any, str | None] = {}
    sent = failed = pushed = 0
    per_tenant: dict[Any, int] = {}
    for row in rows:
        locale = row["locale"] if row["locale"] in ("he", "en") else "en"
        if locale not in messages:
            messages[locale] = load_messages(locale, messages_dir)
        subject, body = render(messages[locale], row["kind"], row["payload"], row)
        if push and push_to_user(conn, push, row["user_id"], subject, body.split("\n\n", 1)[-1]):
            pushed += 1
            conn.execute(
                text("""
                    UPDATE app.notifications
                    SET email_status = 'sent', emailed_at = now(),
                        email_attempts = email_attempts + 1
                    WHERE id = :id
                """),
                {"id": row["id"]},
            )
            continue
        if (
            sender is None or not row["email"]
        ):  # reachable only by push, and that did not go through
            skipped += 1
            conn.execute(
                text("UPDATE app.notifications SET email_status = 'skipped' WHERE id = :id"),
                {"id": row["id"]},
            )
            continue
        try:
            sender.send(
                Email(
                    to=row["email"],
                    subject=subject,
                    text=body,
                    locale=locale,
                    details=details_of(messages[locale], row["payload"], row),
                    kind=row["kind"],
                    reply_to=_reply_to(conn, row["tenant_id"], reply_cache),
                    from_name=row["business"],
                    website=row["website_url"],
                )
            )
        except Exception as error:  # a provider error must not stop the batch
            failed += 1
            print(f"email {row['id']} failed: {error}")
            conn.execute(
                text("""
                    UPDATE app.notifications
                    SET email_attempts = email_attempts + 1,
                        email_status = CASE WHEN email_attempts + 1 >= :max THEN 'failed'
                                            ELSE 'pending' END
                    WHERE id = :id
                """),
                {"id": row["id"], "max": MAX_ATTEMPTS},
            )
            continue
        sent += 1
        conn.execute(
            text("""
                UPDATE app.notifications
                SET email_status = 'sent', emailed_at = now(), email_attempts = email_attempts + 1
                WHERE id = :id
            """),
            {"id": row["id"]},
        )
        per_tenant[row["tenant_id"]] = per_tenant.get(row["tenant_id"], 0) + 1
    # Every email sent is usage of the business (meter "messages", channel email).
    for tenant_id, count in per_tenant.items():
        conn.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
                VALUES (:t, 'messages', :n, CAST(:details AS jsonb), 'notification_emails')
            """),
            {"t": tenant_id, "n": count, "details": EMAIL_DETAILS},
        )
    counts = {"sent": sent, "failed": failed, "skipped": skipped}
    return counts | {"pushed": pushed} if push else counts


class SuppressingSender:
    """Never mails an address the provider reported as bounced or as a spam complaint."""

    def __init__(self, inner: Sender, is_suppressed: Callable[[str], bool]) -> None:
        self.inner = inner
        self.is_suppressed = is_suppressed

    def send(self, email: Email) -> None:
        if self.is_suppressed(email.to):
            print(f"email to {email.to} skipped: address is suppressed")
            return
        self.inner.send(email)


def _is_suppressed(address: str) -> bool:
    """Fails open: a database hiccup must not stop sign-in codes and receipts."""
    from app.core.db import get_engine

    try:
        with get_engine().connect() as conn:
            query = text("SELECT app.email_is_suppressed(:a)")
            return bool(conn.execute(query, {"a": address}).scalar())
    except Exception as error:
        print(f"suppression check failed, sending anyway: {error}")
        return False


def sender_from_settings() -> Sender | None:
    sender = _provider_sender()
    return SuppressingSender(sender, _is_suppressed) if sender is not None else None


def _provider_sender() -> Sender | None:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.email_provider == "log":
        return LogSender()
    if settings.email_provider == "resend":
        if settings.email_api_key is None:
            raise SystemExit("API_EMAIL_API_KEY is required for the resend provider")
        return ResendSender(settings.email_api_key.get_secret_value(), settings.email_from)
    if settings.email_provider in ("gmail", "smtp"):
        if settings.email_api_key is None:
            raise SystemExit("API_EMAIL_API_KEY (the SMTP password) is required")
        # Gmail signs in with the sending address itself.
        username = settings.email_smtp_user or parseaddr(settings.email_from)[1]
        host = "smtp.gmail.com" if settings.email_provider == "gmail" else settings.email_smtp_host
        return SmtpSender(
            host,
            settings.email_smtp_port,
            username,
            settings.email_api_key.get_secret_value(),
            settings.email_from,
        )
    return None
