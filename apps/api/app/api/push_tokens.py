"""Registering a phone for push notifications (the sending side comes later)."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.deps import SessionDep, UserDep

router = APIRouter(prefix="/me/push-tokens", tags=["account"])


class PushTokenBody(BaseModel):
    token: str = Field(min_length=10, max_length=300)
    platform: Literal["ios", "android"]


@router.put("", status_code=204)
def register_push_token(body: PushTokenBody, user: UserDep, session: SessionDep) -> Response:
    """Remember this device's push token for the signed-in person; safe to call on every launch."""
    session.execute(
        text("""
            INSERT INTO app.push_tokens (user_id, token, platform)
            VALUES (:user, :token, :platform)
            ON CONFLICT (user_id, token) DO UPDATE SET platform = :platform, updated_at = now()
        """),
        {"user": user.id, "token": body.token, "platform": body.platform},
    )
    return Response(status_code=204)


@router.delete("", status_code=204)
def unregister_push_token(body: PushTokenBody, user: UserDep, session: SessionDep) -> Response:
    """Forget a device's token, e.g. when the person signs out of it."""
    session.execute(
        text("DELETE FROM app.push_tokens WHERE user_id = :user AND token = :token"),
        {"user": user.id, "token": body.token},
    )
    return Response(status_code=204)
