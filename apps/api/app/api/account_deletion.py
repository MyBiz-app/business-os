"""Deleting your own account from the app (go-live, GL8; Apple and Google require it).

The person is disconnected from every business and their profile is emptied; what businesses
keep about them as clients stays with the business, and payroll and accounting records that
point to them are kept (the profile row stays, anonymous). Someone who still owns an open
business must close it or hand it over first."""

import json
import logging
import urllib.error
import urllib.request
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import SessionDep, UserDep
from app.core.config import get_settings
from app.core.logging import log

router = APIRouter(prefix="/me", tags=["account"])


class DeleteAccountRequest(BaseModel):
    confirm: bool = Field(description="Must be true: deleting cannot be undone")


def remove_sign_in(user_id: UUID) -> bool:
    """Deletes the person's login at Supabase Auth, when the service key is set."""
    settings = get_settings()
    if not settings.supabase_url or settings.supabase_service_key is None:
        return False
    key = settings.supabase_service_key.get_secret_value()
    request = urllib.request.Request(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}",
        method="DELETE",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        data=json.dumps({"should_soft_delete": False}).encode(),
    )
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10):
            return True
    except (urllib.error.URLError, TimeoutError) as error:
        log(logging.ERROR, "sign-in removal failed", error=type(error).__name__)
        return False


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(body: DeleteAccountRequest, user: UserDep, session: SessionDep) -> None:
    if not body.confirm:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="confirm")
    try:
        session.execute(text("SELECT app.delete_my_account()"))
    except DBAPIError as error:
        session.rollback()
        if "owns_business" in str(error.orig):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="owns_business"
            ) from error
        raise
    session.commit()
    remove_sign_in(user.id)
