"""Product events (go-live, GL21): where businesses get stuck, without anyone's personal data.

An event is a short name, an optional step and a few small values (never names, emails or
amounts). The sign-up steps come from the browser before the business exists, under a random
visitor id; everything else is written by the API inside the business's own session."""

import json
from typing import Final, Literal, get_args
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

# The sign-up wizard's steps the browser may report, in order (the extras and services groups
# stand for several screens each).
SignupStepName = Literal["account", "industry", "business", "base", "extras", "services", "summary"]
SIGNUP_STEPS: Final = get_args(SignupStepName)

Value = str | int | bool


def record(
    db: Session,
    event: str,
    step: str | None = None,
    *,
    once: bool = False,
    **properties: Value,
) -> None:
    """Records an event for the current business. `once` keeps only the first of its kind."""
    db.execute(
        text("SELECT app.record_event(:event, :step, :once, CAST(:properties AS jsonb))"),
        {"event": event, "step": step, "once": once, "properties": json.dumps(properties)},
    )


def record_signup_step(db: Session, visitor_id: UUID, event: str, step: str | None) -> None:
    """A sign-up step reported by the browser (no business yet)."""
    db.execute(
        text("SELECT app.record_signup_step(:visitor, :event, :step)"),
        {"visitor": visitor_id, "event": event, "step": step},
    )
