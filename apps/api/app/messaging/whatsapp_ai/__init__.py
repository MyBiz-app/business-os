"""AI replies on WhatsApp (module `whatsapp_ai`, migration 0078).

A client writes to the business's WhatsApp number; the AI answers with a few client-facing
tools that only ever see the business's public schedule and that one client's own bookings
(the client is identified by the phone number, never chosen by the model). The AI never books:
`offer_booking` stores a booking offer, and the server adds a fixed line asking the client to
reply 1. That reply (or the provider's button, `accept:<offer id>`) is handled here without the
model: the offer must still be pending, unexpired and unchanged, the module on and the session
still bookable; then it is booked once and written in the audit log.

Numbers that match no client (or several) get no answer: the bot speaks only to the business's
own clients. A test conversation (the business trying the bot) runs the same way, but nothing
is sent and an accepted offer books nothing.

The code lives by step: `base.py` (types, lookups), `tools.py`, `conversation.py`, `handle.py`
(the entry point) and `inbox.py` (the job)."""

from app.messaging.whatsapp_ai.handle import handle as handle
from app.messaging.whatsapp_ai.inbox import answer_inbox as answer_inbox
