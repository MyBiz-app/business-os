"""Where a network sends the owner back after the consent page (content studio).

No sign-in header arrives here, only the network's `code` and our signed `state` (business,
person, connector; valid ten minutes). The accounts found are stored encrypted and the owner
lands on the content page with the result in the address."""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import EngineDep, open_session
from app.social.oauth import callback_url, read_state
from app.social.providers import ReauthNeeded, social_provider
from app.social.sync import add_account, sync_account

public_router = APIRouter(prefix="/social", tags=["social"])


def _back(**result: str | int) -> RedirectResponse:
    page = f"{get_settings().web_url.rstrip('/')}/content"
    return RedirectResponse(f"{page}?{urlencode(result)}", status_code=302)


@public_router.get("/callback/{family}", include_in_schema=False)
def social_callback(
    family: str,
    engine: EngineDep,
    state: str = "",
    code: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    parsed = read_state(state)
    if parsed is None:
        return _back(social_error="invalid_state")
    tenant_id, user_id, name = parsed
    provider = social_provider(name)
    if provider is None or getattr(provider, "callback", None) != family:
        return _back(social_error="invalid_state")
    if error or not code:  # the owner said no, or the network refused
        return _back(social_error="denied")
    session: Session = open_session(engine, user_id, tenant_id)
    try:
        accounts = provider.exchange_code(code, callback_url(family))
        ids = [
            add_account(session, tenant_id, provider.name, info, connected_by=user_id)
            for info in accounts
        ]
        for account_id in ids:
            try:
                with session.begin_nested():
                    sync_account(session, tenant_id, account_id)
            except Exception:  # connected is connected; the next sync fills the numbers
                pass
        session.commit()
    except ReauthNeeded:
        session.rollback()
        return _back(social_error="denied")
    except Exception:
        session.rollback()
        return _back(social_error="connect_failed")
    finally:
        session.close()
    return _back(social_connected=len(ids), social_network=provider.name)
