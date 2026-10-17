"""Alerts to the MyBiz team's phones (go-live, GL13): a push through the app and an email.

Recipients are the active owners of the MyBiz team (platform staff with level `owner` or
`primary_owner`) who have signed in, so their phone has registered a push token. The push goes
first; the email always follows, so an alert still arrives when the phone has no app installed or
the push service is down. Used when a background job fails or stops running (app/jobs/)."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Connection, text

from app.messaging.email import Email, Sender
from app.messaging.push import PushSender, push_to_user

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlertResult:
    recipients: int = 0
    pushed: int = 0
    emailed: int = 0


def team_recipients(conn: Connection) -> list[tuple[str, UUID | None]]:
    """(email, user id) of every active MyBiz owner; the id is None until they first sign in."""
    rows = conn.execute(
        text("""
            SELECT s.email, u.id
            FROM app.platform_staff s
            LEFT JOIN app.users u ON lower(u.email) = s.email
            WHERE NOT s.disabled AND s.level IN ('primary_owner', 'owner')
            ORDER BY s.email
        """)
    ).all()
    return [(email, user_id) for email, user_id in rows]


def alert_team(
    conn: Connection,
    title: str,
    body: str,
    push: PushSender | None,
    sender: Sender | None,
) -> AlertResult:
    """Tells every MyBiz owner. A channel that is off (None) or fails is skipped, never raised:
    an alert about a failure must not become another failure."""
    recipients = team_recipients(conn)
    pushed = emailed = 0
    for address, user_id in recipients:
        if push is not None and user_id is not None:
            try:
                pushed += push_to_user(conn, push, user_id, title, body)
            except Exception:
                logger.exception("alert push failed")
        if sender is not None:
            try:
                sender.send(Email(to=address, subject=title, text=body, locale="en", kind="alert"))
                emailed += 1
            except Exception:
                logger.exception("alert email failed")
    return AlertResult(len(recipients), pushed, emailed)
