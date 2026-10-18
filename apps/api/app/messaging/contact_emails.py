"""Contact emails of a business and its branches: which address to use for which purpose.

A branch may set its own; otherwise it uses the business's, and a business with none set uses its
owner's sign-in email. Only verified addresses are used (the owner's own always is)."""

from typing import Literal
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.signed_links import sign
from app.messaging import email_layout as layout
from app.messaging.email import Email, load_messages

Purpose = Literal["main", "inbox", "billing", "reply_to", "notifications"]
PURPOSES: tuple[Purpose, ...] = ("main", "inbox", "billing", "reply_to", "notifications")
# What a purpose falls back to when it is not set, in order (the main address is the last resort).
FALLBACKS: dict[str, tuple[str, ...]] = {
    "main": (),
    "inbox": ("main",),
    "billing": ("main",),
    "reply_to": ("inbox", "main"),
    "notifications": ("main",),
}
CONFIRM_TTL = 7 * 24 * 3600
SUBJECT_PREFIX = "contact-email"

Db = Session | Connection


def _owner_email(db: Db, tenant_id: UUID) -> str | None:
    return db.execute(
        text("""
            SELECT u.email FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = :t AND m.role = 'owner'
            ORDER BY m.created_at LIMIT 1
        """),
        {"t": tenant_id},
    ).scalar()


def resolve_email_with_source(
    db: Db, tenant_id: UUID, purpose: str, location_id: UUID | None = None
) -> tuple[str | None, Literal["branch", "business", "owner"]]:
    """The address to use and where it came from. A branch's own addresses come first (its
    purpose, then the fallbacks), then the business's, then the owner's."""
    rows = db.execute(
        text("""
            SELECT location_id, purpose, email FROM app.contact_emails
            WHERE tenant_id = :t AND verified_at IS NOT NULL
              AND (location_id IS NULL OR location_id = :l)
        """),
        {"t": tenant_id, "l": location_id},
    ).all()
    found = {(row.location_id, row.purpose): row.email for row in rows}
    chain = (purpose, *FALLBACKS[purpose])
    scopes: list[tuple[UUID | None, Literal["branch", "business"]]] = (
        [(location_id, "branch")] if location_id else []
    ) + [(None, "business")]
    for scope, source in scopes:
        for step in chain:
            if (scope, step) in found:
                return found[(scope, step)], source
    return _owner_email(db, tenant_id), "owner"


def resolve_email(
    db: Db, tenant_id: UUID, purpose: str, location_id: UUID | None = None
) -> str | None:
    return resolve_email_with_source(db, tenant_id, purpose, location_id)[0]


def sender_name(db: Db, tenant_id: UUID, location_id: UUID | None = None) -> str:
    """The name shown as the sender: the branch with its own contact, else the business."""
    return (
        db.execute(
            text("""
            SELECT CASE WHEN CAST(:l AS uuid) IS NOT NULL AND EXISTS (
                            SELECT 1 FROM app.contact_emails c
                            WHERE c.tenant_id = t.id AND c.location_id = :l)
                        THEN t.name || ' - ' || coalesce(
                            (SELECT name FROM app.locations WHERE id = :l AND tenant_id = t.id),
                            '')
                        ELSE t.name END
            FROM app.tenants t WHERE t.id = :t
        """),
            {"t": tenant_id, "l": location_id},
        ).scalar()
        or ""
    )


def website_of(db: Db, tenant_id: UUID, location_id: UUID | None = None) -> str | None:
    """The site shown in a message's footer: the branch's own, else the business's."""
    return db.execute(
        text("""
            SELECT coalesce(
                (SELECT website_url FROM app.locations WHERE id = :l AND tenant_id = :t),
                (SELECT website_url FROM app.tenants WHERE id = :t))
        """),
        {"t": tenant_id, "l": location_id},
    ).scalar()


def confirm_token(tenant_id: UUID, row_id: UUID, email: str) -> str:
    return sign(f"{SUBJECT_PREFIX}:{tenant_id}:{row_id}:{email.lower()}", ttl=CONFIRM_TTL)


def parse_subject(subject: str) -> tuple[UUID, UUID, str] | None:
    parts = subject.split(":", 3)
    if len(parts) != 4 or parts[0] != SUBJECT_PREFIX:
        return None
    try:
        return UUID(parts[1]), UUID(parts[2]), parts[3]
    except ValueError:
        return None


def confirmation_email(to: str, business: str, purpose: str, token: str, locale: str) -> Email:
    lang = locale if locale in ("he", "en") else "en"
    texts = load_messages(lang)["contactConfirm"]
    link = f"{get_settings().api_url.rstrip('/')}/public/contact-emails/confirm?token={token}"
    subject = texts["subject"].replace("{business}", business)
    intro = (
        texts["intro"]
        .replace("{business}", business)
        .replace("{purpose}", texts["purposes"][purpose])
    )
    body = (
        layout.title(subject, lang)
        + layout.text_block(intro, lang)
        + layout.button(texts["button"], link)
        + layout.link_fallback(link, lang)
        + layout.text_block(texts["ignore"], lang, muted=True)
    )
    html = layout.shell(
        [layout.Section(lang, body)],
        subject=subject,
        preheader=intro,
        brand=layout.BRAND,
        footer=[(lang, layout.BRAND)],
        kind=None,
    )
    return Email(
        to=to,
        subject=subject,
        text=f"{intro}\n\n{link}\n\n{texts['ignore']}",
        html=html,
        locale=lang,
    )
