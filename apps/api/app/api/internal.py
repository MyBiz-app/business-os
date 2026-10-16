"""Endpoints for our own automation, not for people: they need the shared internal token."""

import hmac
import threading
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app import jobs
from app.core.config import get_settings
from app.core.db import EngineDep

router = APIRouter(prefix="/internal", tags=["system"])

# One tick at a time per process: a tick that is still running makes the next one a no-op.
_tick = threading.Lock()


class Tick(BaseModel):
    started: bool


def _authorised(supplied: str | None) -> bool:
    token = get_settings().internal_token
    return bool(token and supplied) and hmac.compare_digest(
        (supplied or "").encode(),
        token.get_secret_value().encode(),  # type: ignore[union-attr]
    )


@router.post("/jobs/tick", status_code=status.HTTP_202_ACCEPTED)
def tick(engine: EngineDep, x_internal_token: Annotated[str | None, Header()] = None) -> Tick:
    """Runs the scheduled AI tasks that are due. Called every few minutes by the keep-awake
    workflow (and, later, by a worker every minute). Answers at once; the work continues in the
    background, so a slow model call never holds the caller."""
    if not _authorised(x_internal_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorised")
    if not _tick.acquire(blocking=False):
        return Tick(started=False)

    def work() -> None:
        try:
            jobs.run_job(engine, "run-ai-tasks")
        except Exception:  # recorded in app.job_runs by run_job
            pass
        finally:
            _tick.release()

    threading.Thread(target=work, daemon=True).start()
    return Tick(started=True)
