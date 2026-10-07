"""Notifications from outside providers (decision X13).

A provider calls `/webhooks/payments/{provider}/{tenant_id}` when a payment ends. The business's
payments provider verifies the notification (its signature, with the business's secret) and
translates it; only then is the checkout completed, for exactly the amount it was opened for."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import AnonymousSessionDep
from app.providers.choice import choose
from app.providers.payments import WebhookRejected

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/payments/{provider}/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def payment_webhook(
    provider: str, tenant_id: UUID, request: Request, session: AnonymousSessionDep
) -> None:
    chosen = choose(session, tenant_id, "payments")
    if chosen.info.name != provider or chosen.instance.simulated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    body = await request.body()
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
                    SELECT app.complete_provider_checkout(:id, :provider, :ref, :amount,
                                                          :currency)
                """),
                {
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
