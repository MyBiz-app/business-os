"""Push notifications to people's phones, through Expo's push service.

Phones register their Expo token with `PUT /me/push-tokens` (migration 0072). The notify jobs
try a push first and fall back to email when the person has no registered phone or the push
service could not deliver it. Tokens that Expo reports as no longer valid are forgotten."""

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import Connection, text

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
BATCH = 100  # Expo accepts at most 100 messages per request
BODY_LIMIT = 300


@dataclass(frozen=True)
class PushResult:
    delivered: int = 0  # tokens the push service accepted
    dead: list[str] = field(default_factory=list)  # tokens that are no longer valid


class PushSender(Protocol):
    def send(self, tokens: list[str], title: str, body: str) -> PushResult: ...


class LogPushSender:
    """Records instead of sending (tests and dry runs)."""

    def __init__(self) -> None:
        self.sent: list[tuple[list[str], str, str]] = []

    def send(self, tokens: list[str], title: str, body: str) -> PushResult:
        self.sent.append((tokens, title, body))
        return PushResult(delivered=len(tokens))


class ExpoPushSender:
    """Expo's push API (https://docs.expo.dev/push-notifications/sending-notifications/)."""

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def send(self, tokens: list[str], title: str, body: str) -> PushResult:
        delivered, dead = 0, []
        for start in range(0, len(tokens), BATCH):
            chunk = tokens[start : start + BATCH]
            messages = [
                {"to": token, "title": title, "body": body[:BODY_LIMIT], "sound": "default"}
                for token in chunk
            ]
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            request = urllib.request.Request(
                EXPO_PUSH_URL, data=json.dumps(messages).encode(), method="POST", headers=headers
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                tickets: list[dict[str, Any]] = json.loads(response.read()).get("data", [])
            for token, ticket in zip(chunk, tickets, strict=False):
                if ticket.get("status") == "ok":
                    delivered += 1
                elif (ticket.get("details") or {}).get("error") == "DeviceNotRegistered":
                    dead.append(token)
        return PushResult(delivered=delivered, dead=dead)


def tokens_for(conn: Connection, user_id: UUID | None) -> list[str]:
    if user_id is None:
        return []
    return list(
        conn.execute(
            text("SELECT token FROM app.push_tokens WHERE user_id = :u ORDER BY updated_at DESC"),
            {"u": user_id},
        ).scalars()
    )


def push_to_user(
    conn: Connection, push: PushSender, user_id: UUID | None, title: str, body: str
) -> bool:
    """Pushes to every phone the person registered; True when at least one accepted it. A push
    service error counts as not delivered, so the caller falls back to email."""
    tokens = tokens_for(conn, user_id)
    if not tokens:
        return False
    try:
        result = push.send(tokens, title, body)
    except Exception as error:  # the push service being down must not stop the batch
        print(f"push to {user_id} failed: {error}")
        return False
    if result.dead:
        conn.execute(
            text(
                "DELETE FROM app.push_tokens WHERE user_id = :u AND token = ANY(CAST(:t AS text[]))"
            ),
            {"u": user_id, "t": result.dead},
        )
    return result.delivered > 0


def push_sender_from_settings() -> PushSender | None:
    """Expo's push service needs no account for basic use; set API_PUSH_PROVIDER=off to disable."""
    from app.core.config import get_settings

    settings = get_settings()
    if settings.push_provider == "off":
        return None
    if settings.push_provider == "log":
        return LogPushSender()
    token = settings.expo_access_token
    return ExpoPushSender(token.get_secret_value() if token else None)
