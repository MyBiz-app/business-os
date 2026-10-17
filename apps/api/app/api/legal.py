"""Legal documents: which versions the signed-in person still has to accept, and accepting them."""

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, UserDep
from app.api.routes import ensure_profile
from app.legal.documents import pending_documents, record_acceptance

router = APIRouter(tags=["legal"])


class PendingDocument(BaseModel):
    document: str = Field(description="terms, privacy or dpa")
    version: str = Field(description="The current version, which is also its date")


class AcceptRequest(BaseModel):
    documents: dict[str, str] = Field(
        min_length=1, description="Document -> the version being accepted (must be the current)"
    )


@router.get("/me/legal")
def my_pending_documents(user: UserDep, session: SessionDep) -> list[PendingDocument]:
    ensure_profile(session, user.id, user.email)
    return [PendingDocument(**item) for item in pending_documents(session, user.id)]


@router.post("/me/legal", status_code=status.HTTP_201_CREATED)
def accept_documents(
    body: AcceptRequest, request: Request, user: UserDep, session: SessionDep
) -> list[PendingDocument]:
    """Accepts the current version of the given documents (the banner after a document changed)."""
    ensure_profile(session, user.id, user.email)
    record_acceptance(session, request, user.id, body.documents, "reaccept")
    return [PendingDocument(**item) for item in pending_documents(session, user.id)]
