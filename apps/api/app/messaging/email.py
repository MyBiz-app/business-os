"""Emailing client notifications (the send-emails job; see app/jobs.py).

The text comes from the shared translation files: packages/i18n/messages is the source and
app/messages holds the API's checked-in copy (pnpm --filter @business-os/i18n export:api), so
both the API image and the jobs can render emails. A notification is emailed once, within a
day of happening; older ones, and ones for clients without an email address, are skipped."""

import html
import json
import re
import smtplib
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

MESSAGES_DIR = Path(__file__).resolve().parent.parent / "messages"
FRESH_FOR = timedelta(days=1)
MAX_ATTEMPTS = 3
BATCH = 200


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str | None = None  # a designed version; otherwise the text is turned into HTML


def _html(email: Email) -> str:
    if email.html is not None:
        return email.html
    return (
        '<div dir="auto">'
        + "<br>".join(html.escape(line) for line in email.text.split("\n"))
        + "</div>"
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


class ResendSender:
    """Resend's HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    def send(self, email: Email) -> None:
        body = json.dumps(
            {
                "from": self.sender,
                "to": [email.to],
                "subject": email.subject,
                "text": email.text,
                "html": _html(email),
            }
        ).encode()
        request = urllib.request.Request(
            "https://api.resend.com/emails",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=15) as response:
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
        message["From"] = self.sender
        message["To"] = email.to
        message["Subject"] = email.subject
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
    }
    subject = _fill(messages["subject"][kind], values)
    lines = [_fill(messages["greeting"], values), "", _fill(messages["body"][kind], values)]
    if values["note"]:
        lines.append(_fill(messages["note"], values))
    lines += ["", _fill(messages["footer"], values)]
    return subject, "\n".join(lines)


EMAIL_DETAILS = json.dumps({"channel": "email", "automated": True})


def send_emails(
    conn: Connection,
    sender: Sender,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
) -> dict[str, int]:
    """Emails pending notifications. Returns counts per outcome."""
    now = now or datetime.now(UTC)
    skipped = conn.execute(
        text("""
            UPDATE app.notifications n SET email_status = 'skipped'
            FROM app.clients c
            WHERE n.email_status = 'pending' AND c.id = n.client_id
              AND (n.created_at < :oldest OR c.email IS NULL OR c.erased_at IS NOT NULL)
        """),
        {"oldest": now - FRESH_FOR},
    ).rowcount
    rows = (
        conn.execute(
            text("""
                SELECT n.id, n.tenant_id, n.kind, n.payload, c.email, c.first_name,
                       t.name AS business,
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
    sent = failed = 0
    per_tenant: dict[Any, int] = {}
    for row in rows:
        locale = row["locale"] if row["locale"] in ("he", "en") else "en"
        if locale not in messages:
            messages[locale] = load_messages(locale, messages_dir)
        subject, body = render(messages[locale], row["kind"], row["payload"], row)
        try:
            sender.send(Email(to=row["email"], subject=subject, text=body))
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
    return {"sent": sent, "failed": failed, "skipped": skipped}


def sender_from_settings() -> Sender | None:
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
