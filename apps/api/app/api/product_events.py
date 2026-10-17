"""The sign-up steps the browser reports, so the console can show where people drop out
(go-live, GL21). No sign-in and no personal data: a random visitor id, an event and a step."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import AnonymousSessionDep
from app.core import events

public_router = APIRouter(tags=["public"])


class SignupStep(BaseModel):
    visitor_id: UUID = Field(description="Random id the browser made for this visit")
    event: Literal["signup_started", "signup_step"]
    step: events.SignupStepName | None = None


@public_router.post("/public/events", status_code=status.HTTP_204_NO_CONTENT)
def report_signup_step(body: SignupStep, session: AnonymousSessionDep) -> None:
    """A step of the sign-up journey was reached."""
    events.record_signup_step(session, body.visitor_id, body.event, body.step)
