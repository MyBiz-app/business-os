"""Emailing client notifications (the send-emails job; see app/jobs.py).

The text comes from the shared translation files (packages/i18n/messages/<locale>.json,
key "email"), so the job runs from a full checkout of the repository (GitHub Actions), not
from the API image. A notification is emailed once, within a day of happening; older ones,
and ones for clients without an email address, are skipped."""

import html
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

MESSAGES_DIR = Path(__file__).resolve().parents[3] / "packages" / "i18n" / "messages"
FRESH_FOR = timedelta(days=1)
MAX_ATTEMPTS = 3
BATCH = 200


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


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
                "html": "<br>".join(html.escape(line) for line in email.text.split("\n")),
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


def load_messages(locale: str, directory: Path = MESSAGES_DIR) -> dict[str, Any]:
    return json.loads((directory / f"{locale}.json").read_text(encoding="utf-8"))["email"]


def _fill(template: str, values: dict[str, str]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), template)


def _when(value: Any, time_zone: str) -> str:
    if not value:
        return ""
    instant = datetime.fromisoformat(str(value))
    return instant.astimezone(ZoneInfo(time_zone)).strftime("%d/%m %H:%M")


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
    }
    subject = _fill(messages["subject"][kind], values)
    lines = [_fill(messages["greeting"], values), "", _fill(messages["body"][kind], values)]
    if values["note"]:
        lines.append(_fill(messages["note"], values))
    lines += ["", _fill(messages["footer"], values)]
    return subject, "\n".join(lines)


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
                SELECT n.id, n.kind, n.payload, c.email, c.first_name, t.name AS business,
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
    return None
