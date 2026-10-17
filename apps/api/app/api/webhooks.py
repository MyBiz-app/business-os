"""Notifications from outside providers (decision X13).

A provider calls `/webhooks/payments/{provider}/{tenant_id}` when a payment ends. The business's
payments provider verifies the notification (its signature, with the business's secret) and
translates it; only then is the checkout completed, for exactly the amount it was opened for.

`/webhooks/whatsapp/{provider}/{tenant_id}` receives clients' WhatsApp messages the same way: the
business's messaging provider verifies and translates them, and they wait in the inbox for the
AI replies (module `whatsapp_ai`). Closed while the provider is the simulated one."""

import base64
import hashlib
import hmac
import json
import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import AnonymousSessionDep
from app.core.config import get_settings
from app.providers.choice import choose
from app.providers.payments import WebhookRejected

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _raw_body(request: Request) -> bytes:
    return await request.body()


RawBody = Annotated[bytes, Depends(_raw_body)]


@router.post("/payments/{provider}/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def payment_webhook(
    provider: str, tenant_id: UUID, request: Request, body: RawBody, session: AnonymousSessionDep
) -> None:
    chosen = choose(session, tenant_id, "payments")
    if chosen.info.name != provider or chosen.instance.simulated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    try:
        event = chosen.instance.parse_webhook(dict(request.headers), body)
    except WebhookRejected as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="rejected") from error
    if event.status != "succeeded":
        return  # the checkout stays pending: the client can try again
    try:
        with session.begin_nested():
            session.execute(
                text("""
                    SELECT app.complete_provider_checkout(:tenant, :id, :provider, :ref,
                                                          :amount, :currency)
                """),
                {
                    "tenant": tenant_id,
                    "id": event.checkout_id,
                    "provider": provider,
                    "ref": event.provider_ref,
                    "amount": event.amount,
                    "currency": event.currency,
                },
            )
    except DBAPIError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code == "P0002":
            raise HTTPException(status_code=404, detail="not_found") from error
        if code == "22023":
            raise HTTPException(status_code=409, detail="amount_mismatch") from error
        raise


@router.post("/whatsapp/{provider}/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def whatsapp_webhook(
    provider: str, tenant_id: UUID, request: Request, body: RawBody, session: AnonymousSessionDep
) -> None:
    chosen = choose(session, tenant_id, "messaging")
    parse = getattr(chosen.instance, "parse_inbound", None)
    if chosen.info.name != provider or chosen.instance.simulated or parse is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    try:
        incoming = parse(dict(request.headers), body)
    except WebhookRejected as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="rejected") from error
    for message in incoming:
        # Filed only while the business has the module; a retried notification is ignored.
        session.execute(
            text("SELECT app.receive_whatsapp(:tenant, :provider, :ref, :phone, :body)"),
            {
                "tenant": tenant_id,
                "provider": provider,
                "ref": message.provider_ref,
                "phone": message.from_phone,
                "body": message.body,
            },
        )


SVIX_TOLERANCE_SECONDS = 300


def _verify_svix(headers: dict[str, str], body: bytes, secret: str) -> None:
    """Resend signs webhooks with Svix: HMAC-SHA256 over `id.timestamp.body`, key = the
    base64 part of the `whsec_` secret; the header may list several `v1,<signature>` values."""
    msg_id = headers.get("svix-id", "")
    stamp = headers.get("svix-timestamp", "")
    try:
        key = base64.b64decode(secret.removeprefix("whsec_"))
        age = abs(time.time() - int(stamp))
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="rejected") from error
    expected = base64.b64encode(
        hmac.new(key, f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    offered = [part.partition(",")[2] for part in headers.get("svix-signature", "").split()]
    if age > SVIX_TOLERANCE_SECONDS or not any(hmac.compare_digest(expected, o) for o in offered):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="rejected")


@router.post("/email/resend", status_code=status.HTTP_204_NO_CONTENT)
def email_webhook(request: Request, body: RawBody, session: AnonymousSessionDep) -> None:
    """Hard bounces and spam complaints from Resend: the address is never mailed again.
    Closed (404) until `API_EMAIL_WEBHOOK_SECRET` is set."""
    secret = get_settings().email_webhook_secret
    if secret is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    headers = {k.lower(): v for k, v in request.headers.items()}
    _verify_svix(headers, body, secret.get_secret_value())
    try:
        event = json.loads(body)
        kind = event["type"]
        data = event.get("data") or {}
    except (ValueError, KeyError, TypeError) as error:
        raise HTTPException(status_code=422, detail="invalid_event") from error
    if kind == "email.complained":
        reason = "complained"
    elif kind == "email.bounced" and (data.get("bounce") or {}).get("type") == "Permanent":
        reason = "bounced"
    else:
        return  # delivered, opened, soft bounces and the rest need no action
    for address in data.get("to") or []:
        session.execute(
            text("SELECT app.suppress_email(:address, :reason, :ref)"),
            {"address": str(address), "reason": reason, "ref": data.get("email_id")},
        )
