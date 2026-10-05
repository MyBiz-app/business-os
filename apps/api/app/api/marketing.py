"""The marketing site's contact form: businesses interested in MyBiz (see migration 0026).

Until an email provider is connected, requests are stored and shown to platform admins in the
console; nobody is emailed."""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.common import blank_to_none
from app.api.deps import AnonymousSessionDep
from app.verticals import CATALOG

router = APIRouter(prefix="/public", tags=["public"])


class ContactCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    business: str | None = Field(default=None, max_length=160)
    vertical: str | None = Field(
        default=None,
        max_length=40,
        description='A catalog industry (also a coming-soon one) or "other"',
    )
    message: str | None = Field(default=None, max_length=4000)
    locale: Literal["he", "en"] = "he"
    # A field people never see: bots that fill every input fill it too.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("vertical")
    @classmethod
    def known_vertical(cls, value: str | None) -> str | None:
        if value is not None and value != "other" and value not in CATALOG:
            raise ValueError("unknown vertical")
        return value

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone", "business", "message", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


@router.post("/contact", status_code=status.HTTP_202_ACCEPTED)
def contact(body: ContactCreate, db: AnonymousSessionDep) -> None:
    if body.website:
        return  # a bot: accept quietly, store nothing
    try:
        with db.begin_nested():
            db.execute(
                text("""
                    SELECT app.submit_contact_request(
                        :name, :email, :phone, :business, :vertical, :message, :locale)
                """),
                body.model_dump(exclude={"website"}),
            )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "P0001":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="too_many_requests"
            ) from error
        raise
