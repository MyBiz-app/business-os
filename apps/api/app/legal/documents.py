"""Versions of the legal documents people accept, and the record of who accepted what.

The versions live here for the API and in packages/i18n/brand.json (`legal.versions`) for the web
and the apps; `tests/test_legal.py` fails when the two drift apart. Raise a version (and its date)
whenever the text of a document changes: everyone then sees a banner asking them to accept again."""

from typing import Literal
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import client_address

LegalDocument = Literal["terms", "privacy", "dpa"]
AcceptContext = Literal["signup", "client_join", "reaccept"]

# document -> current version (also the date of its last change).
VERSIONS: dict[str, str] = {
    "terms": "2026-10-16",
    "privacy": "2026-10-16",
    "dpa": "2026-10-17",
}

# Every person accepts these; a person who owns a business also accepts the data processing terms.
EVERYONE: tuple[str, ...] = ("terms", "privacy")
BUSINESS_OWNERS: tuple[str, ...] = ("dpa",)

USER_AGENT_LIMIT = 200


def check_versions(accepted: dict[str, str]) -> None:
    """Rejects an unknown document or a version that is no longer the current one."""
    for document, version in accepted.items():
        if document not in VERSIONS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_document")
        if version != VERSIONS[document]:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="legal_outdated")


def record_acceptance(
    session: Session,
    request: Request,
    user_id: UUID,
    accepted: dict[str, str],
    context: AcceptContext,
    business_id: UUID | None = None,
) -> None:
    """Stores who accepted which version, when, and from where. Accepting twice is a no-op."""
    check_versions(accepted)
    settings = get_settings()
    address = client_address(
        request,
        settings.trust_forwarded_for,
        settings.internal_token.get_secret_value() if settings.internal_token else None,
    )
    agent = request.headers.get("user-agent", "")[:USER_AGENT_LIMIT]
    for document, version in accepted.items():
        session.execute(
            text("""
                INSERT INTO app.legal_acceptances
                    (user_id, business_id, document, version, context, ip_address, user_agent)
                VALUES (:user, :business, :document, :version, :context, :ip, :agent)
                ON CONFLICT DO NOTHING
            """),
            {
                "user": user_id,
                "business": business_id,
                "document": document,
                "version": version,
                "context": context,
                "ip": address,
                "agent": agent,
            },
        )


def pending_documents(session: Session, user_id: UUID) -> list[dict[str, str]]:
    """The documents whose current version this person has not accepted yet."""
    owns_business = session.execute(
        text("""
            SELECT EXISTS (SELECT 1 FROM app.tenant_members
                           WHERE user_id = :user AND role = 'owner')
        """),
        {"user": user_id},
    ).scalar_one()
    required = EVERYONE + (BUSINESS_OWNERS if owns_business else ())
    accepted = {
        (row.document, row.version)
        for row in session.execute(
            text("SELECT document, version FROM app.legal_acceptances WHERE user_id = :user"),
            {"user": user_id},
        )
    }
    return [
        {"document": document, "version": VERSIONS[document]}
        for document in required
        if (document, VERSIONS[document]) not in accepted
    ]
