"""Friends inside a business: find, request, accept, and invite a friend to a class.

Friendship belongs to one business (switching business switches the friend list). A client finds
a friend only by a personal code or the friend's exact phone / email, never by browsing the
client list. What one client may read about another goes through database functions that
return a few fields only (see migration 0082). Whether friends exist at all follows the catalog's
`social` flag of the branch or business."""

import json
import math
import re
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.bookings import lock_session, place_booking
from app.api.client_app import ClientSession, _load_session
from app.api.common import blank_to_none, not_found
from app.api.deps import ClientContext, ClientDep
from app.api.health import ensure_may_book
from app.api.locations import kind_pack
from app.api.settings import IMAGE_RESPONSES, image_response
from app.core.rate_limit import MemoryStore

router = APIRouter(prefix="/client", tags=["friends"])

INVITE_HOLD = timedelta(hours=2)  # how long an invited spot is kept for the friend
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
LOOKUPS_PER_HOUR = 20
_lookups = MemoryStore()  # per API process, like the other limiters

Friendship = Literal["none", "friends", "request_sent", "request_received"]


class Person(BaseModel):
    """What a client may see of another: friends see the full name, others the first name."""

    client_id: UUID
    first_name: str
    last_name: str | None = Field(description="Friends only")
    status_text: str | None = Field(description="The status they wrote in their profile")
    avatar_url: str | None
    friendship: Friendship
    friendship_id: UUID | None = Field(description="Accept or cancel the request with this id")
    friends_since: datetime | None
    shared_classes: int = Field(description="Classes the two of us did together")


class SharedByService(BaseModel):
    service_id: UUID
    service_name: str
    shared_classes: int


class PersonProfile(Person):
    by_service: list[SharedByService] = Field(
        description="Shared classes per class type (friends only)"
    )


class FriendSettings(BaseModel):
    enabled: bool = Field(description="The business offers friends (catalog `social` flag)")
    friend_code: str = Field(description="Personal code: share it as a link or a QR")
    visible: bool = Field(description="Show me in participant lists of classes")


class FriendSettingsUpdate(BaseModel):
    visible: bool


class FriendRequestCreate(BaseModel):
    code: str | None = Field(default=None, max_length=16)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=254)

    @field_validator("code", "phone", "email", mode="before")
    @classmethod
    def _blank(cls, value: object) -> object:
        return blank_to_none(value)

    @model_validator(mode="after")
    def _one_way_to_find(self) -> "FriendRequestCreate":
        if not (self.code or self.phone or self.email):
            raise ValueError("code, phone or email is required")
        return self


class FriendRequests(BaseModel):
    incoming: list[Person]
    outgoing: list[Person]


class InviteCreate(BaseModel):
    friend_id: UUID


InviteStatus = Literal["pending", "accepted", "declined", "cancelled", "expired"]


class Invite(BaseModel):
    id: UUID
    direction: Literal["received", "sent"]
    session_id: UUID
    service_name: str
    starts_at: datetime
    expires_at: datetime = Field(description="The spot is held for the friend until then")
    status: InviteStatus
    other_client_id: UUID
    other_first_name: str | None = Field(description="Who invited me / whom I invited")


# --- helpers -------------------------------------------------------------------------------


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _forbidden_unless_enabled(db: Session) -> None:
    """Friends exist only where the catalog says so: the business's category or any branch kind
    with `social` on. Categories that are off (clinics, beauty, ...) have no friends at all."""
    vertical = db.execute(
        text("SELECT vertical FROM app.tenants WHERE id = app.client_tenant_id()")
    ).scalar_one()
    kinds = set(db.execute(text("SELECT DISTINCT kind FROM app.locations")).scalars())
    if not any(kind_pack(vertical, kind).social == "on" for kind in {*kinds, None}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="friends_disabled")


def _session_has_lists(db: Session, session_id: UUID) -> bool:
    row = db.execute(
        text("""
            SELECT t.vertical, l.kind
            FROM app.sessions s
            JOIN app.tenants t ON t.id = s.tenant_id
            LEFT JOIN app.locations l ON l.id = s.location_id
            WHERE s.id = :id
        """),
        {"id": session_id},
    ).first()
    if row is None:
        raise not_found()
    return kind_pack(row.vertical, row.kind).social == "on"


def _person(row: dict) -> Person:
    avatar = row.pop("avatar_updated_at")
    row["avatar_url"] = (
        f"/client/people/{row['client_id']}/avatar?v={int(avatar.timestamp())}" if avatar else None
    )
    row["shared_classes"] = row.pop("together")
    return Person.model_validate(row)


def _people(db: Session, sql: str, params: dict | None = None) -> list[Person]:
    rows = db.execute(text(sql), params or {}).mappings()
    return [_person(dict(row)) for row in rows]


def _one_person(db: Session, client_id: UUID) -> Person:
    found = _people(db, "SELECT * FROM app.social_person(:id)", {"id": client_id})
    if not found:
        raise not_found()
    return found[0]


def _social_row(context: ClientContext) -> dict:
    """The client's friend code and visibility, created on first use."""
    db = context.session
    for _ in range(5):
        try:
            with db.begin_nested():
                db.execute(
                    text("""
                        INSERT INTO app.client_social (tenant_id, client_id, friend_code)
                        VALUES (:tenant, :client, :code)
                        ON CONFLICT (tenant_id, client_id) DO NOTHING
                    """),
                    {
                        "tenant": context.tenant_id,
                        "client": context.client_id,
                        "code": "".join(secrets.choice(CODE_ALPHABET) for _ in range(10)),
                    },
                )
            break
        except IntegrityError:  # the code collided with someone else's: draw another
            continue
    return dict(
        db.execute(
            text("SELECT friend_code, visible FROM app.client_social WHERE client_id = :c"),
            {"c": context.client_id},
        )
        .mappings()
        .one()
    )


def _my_first_name(context: ClientContext) -> str:
    return context.session.execute(
        text("SELECT first_name FROM app.clients WHERE id = :id"), {"id": context.client_id}
    ).scalar_one()


def _pair(db: Session, me: UUID, other: UUID) -> dict | None:
    row = (
        db.execute(
            text("""
                SELECT id, requester_id, addressee_id, status FROM app.client_friendships
                WHERE least(requester_id, addressee_id) = least(CAST(:a AS uuid), CAST(:b AS uuid))
                  AND greatest(requester_id, addressee_id) =
                      greatest(CAST(:a AS uuid), CAST(:b AS uuid))
            """),
            {"a": me, "b": other},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


# --- my friend code and privacy ---------------------------------------------------------------


@router.get("/friends/settings")
def friend_settings(context: ClientDep) -> FriendSettings:
    try:
        _forbidden_unless_enabled(context.session)
        enabled = True
    except HTTPException:
        enabled = False
    return FriendSettings(enabled=enabled, **_social_row(context))


@router.patch("/friends/settings")
def update_friend_settings(body: FriendSettingsUpdate, context: ClientDep) -> FriendSettings:
    _forbidden_unless_enabled(context.session)
    _social_row(context)
    context.session.execute(
        text("UPDATE app.client_social SET visible = :v, updated_at = now() WHERE client_id = :c"),
        {"v": body.visible, "c": context.client_id},
    )
    return FriendSettings(enabled=True, **_social_row(context))


# --- finding, requesting, accepting -------------------------------------------------------------


@router.get("/friends")
def my_friends(context: ClientDep) -> list[Person]:
    _forbidden_unless_enabled(context.session)
    return _people(
        context.session,
        """
        SELECT * FROM app.social_connections() WHERE friendship = 'friends'
        ORDER BY first_name, last_name
        """,
    )


@router.get("/friends/requests")
def friend_requests(context: ClientDep) -> FriendRequests:
    _forbidden_unless_enabled(context.session)
    people = _people(
        context.session,
        "SELECT * FROM app.social_connections() WHERE friendship LIKE 'request_%' "
        "ORDER BY first_name",
    )
    return FriendRequests(
        incoming=[p for p in people if p.friendship == "request_received"],
        outgoing=[p for p in people if p.friendship == "request_sent"],
    )


def _check_lookup_rate(client_id: UUID) -> None:
    """Exact phone / email / code search is the only way to find someone, so it is rationed."""
    now = time.time()
    count, ends = _lookups.hit(f"friends:{client_id}", 3600, now)
    if count > LOOKUPS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="friends_rate_limited",
            headers={"Retry-After": str(max(1, math.ceil(ends - now)))},
        )


@router.post("/friends/requests", status_code=status.HTTP_201_CREATED)
def send_friend_request(body: FriendRequestCreate, context: ClientDep) -> Person:
    """Asks someone to be friends. They are found by their personal code or exact phone / email;
    if they already asked me, the two requests become a friendship."""
    db = context.session
    _forbidden_unless_enabled(db)
    _check_lookup_rate(context.client_id)
    digits = re.sub(r"\D", "", body.phone or "") or None
    code = body.code.strip().upper() if body.code else None
    target = db.execute(
        text("SELECT app.social_find(:code, :phone, :email)"),
        {"code": code, "phone": digits, "email": body.email},
    ).scalar()
    if target is None:
        raise not_found()
    return _request_friendship(context, target)


@router.post("/people/{client_id}/friend-request", status_code=status.HTTP_201_CREATED)
def request_friendship_with(client_id: UUID, context: ClientDep) -> Person:
    """Asks a person met in a class to be friends (the "add friend" button on their profile).
    Only people the profile endpoint would show me can be asked."""
    _forbidden_unless_enabled(context.session)
    _check_lookup_rate(context.client_id)
    person_profile(client_id, context)  # 404 unless I may see them
    return _request_friendship(context, client_id)


def _request_friendship(context: ClientDep, target: UUID) -> Person:
    db = context.session
    existing = _pair(db, context.client_id, target)
    if existing is not None:
        if existing["status"] == "accepted":
            raise _conflict("already_friends")
        if existing["requester_id"] == context.client_id:
            raise _conflict("already_requested")
        _accept(db, existing["id"], context.client_id)  # they asked first
        return _one_person(db, target)
    db.execute(
        text("""
            INSERT INTO app.client_friendships (tenant_id, requester_id, addressee_id)
            VALUES (:tenant, :me, :other)
        """),
        {"tenant": context.tenant_id, "me": context.client_id, "other": target},
    )
    db.execute(
        text("SELECT app.social_notify(:to, 'friend_request', CAST(:payload AS jsonb))"),
        {"to": target, "payload": json.dumps({"from_name": _my_first_name(context)})},
    )
    return _one_person(db, target)


def _accept(db: Session, friendship_id: UUID, me: UUID) -> UUID:
    other = db.execute(
        text("""
            UPDATE app.client_friendships SET status = 'accepted', responded_at = now()
            WHERE id = :id AND addressee_id = :me AND status = 'pending'
            RETURNING requester_id
        """),
        {"id": friendship_id, "me": me},
    ).scalar()
    if other is None:
        raise not_found()
    return other


@router.post("/friends/requests/{friendship_id}/accept")
def accept_friend_request(friendship_id: UUID, context: ClientDep) -> Person:
    _forbidden_unless_enabled(context.session)
    other = _accept(context.session, friendship_id, context.client_id)
    return _one_person(context.session, other)


@router.delete("/friends/requests/{friendship_id}", status_code=status.HTTP_204_NO_CONTENT)
def drop_friend_request(friendship_id: UUID, context: ClientDep) -> Response:
    """Declines a request I received, or withdraws one I sent."""
    deleted = context.session.execute(
        text("DELETE FROM app.client_friendships WHERE id = :id AND status = 'pending'"),
        {"id": friendship_id},
    ).rowcount
    if not deleted:
        raise not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/friends/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(client_id: UUID, context: ClientDep) -> Response:
    pair = _pair(context.session, context.client_id, client_id)
    if pair is None or pair["status"] != "accepted":
        raise not_found()
    context.session.execute(
        text("DELETE FROM app.client_friendships WHERE id = :id"), {"id": pair["id"]}
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- people met in a class ------------------------------------------------------------------


@router.get("/people/{client_id}")
def person_profile(client_id: UUID, context: ClientDep) -> PersonProfile:
    """A friend, a pending request, or someone from a class I am in: the few things shown about
    them. Others see no phone, email or history."""
    db = context.session
    _forbidden_unless_enabled(db)
    person = _one_person(db, client_id)
    if person.friendship == "none":
        # Met in a class: only where the class's branch has participant lists at all.
        places = list(
            db.execute(
                text("SELECT location_id FROM app.social_shared_locations(:id)"), {"id": client_id}
            ).scalars()
        )
        vertical = db.execute(
            text("SELECT vertical FROM app.tenants WHERE id = app.client_tenant_id()")
        ).scalar_one()
        kinds = dict(db.execute(text("SELECT id, kind FROM app.locations")).all())
        if not any(kind_pack(vertical, kinds.get(place)).social == "on" for place in places):
            raise not_found()
    by_service: list[SharedByService] = []
    if person.friendship == "friends":
        rows = db.execute(
            text("SELECT * FROM app.social_together_by_service(:id)"), {"id": client_id}
        ).mappings()
        by_service = [
            SharedByService(
                service_id=row["service_id"],
                service_name=row["service_name"],
                shared_classes=row["together"],
            )
            for row in rows
        ]
    return PersonProfile(**person.model_dump(), by_service=by_service)


@router.get("/people/{client_id}/avatar", response_class=Response, responses=IMAGE_RESPONSES)
def person_avatar(client_id: UUID, context: ClientDep) -> Response:
    row = context.session.execute(
        text("SELECT avatar, content_type FROM app.social_avatar(:id)"), {"id": client_id}
    ).first()
    if row is None:
        raise not_found()
    return image_response(row.avatar, row.content_type)


MAX_BATCH_SESSIONS = 60


@router.get("/sessions/participants")
def sessions_participants(
    context: ClientDep,
    session_ids: Annotated[list[UUID], Query(max_length=MAX_BATCH_SESSIONS)],
) -> dict[UUID, list[Person]]:
    """Participants of many classes in one request (a day's schedule), keyed by class id.
    Classes in categories without participant lists, or not visible to the client, are left out."""
    db = context.session
    rows = db.execute(
        text("""
            SELECT s.id, t.vertical, l.kind
            FROM app.sessions s
            JOIN app.tenants t ON t.id = s.tenant_id
            LEFT JOIN app.locations l ON l.id = s.location_id
            WHERE s.id = ANY(:ids)
        """),
        {"ids": session_ids},
    ).all()
    return {
        row.id: _people(
            db,
            "SELECT * FROM app.social_participants(:id) "
            "ORDER BY (friendship = 'friends') DESC, first_name",
            {"id": row.id},
        )
        for row in rows
        if kind_pack(row.vertical, row.kind).social == "on"
    }


@router.get("/sessions/{session_id}/participants")
def session_participants(session_id: UUID, context: ClientDep) -> list[Person]:
    """Who else is booked into a class (first name, picture, status), for the class block.
    Empty where the category has no participant lists; people who hid themselves are left out,
    except friends."""
    db = context.session
    if not _session_has_lists(db, session_id):
        return []
    return _people(
        db,
        "SELECT * FROM app.social_participants(:id) "
        "ORDER BY (friendship = 'friends') DESC, first_name",
        {"id": session_id},
    )


# --- inviting a friend to a class -------------------------------------------------------------

INVITE_SELECT = """
    SELECT i.id, i.session_id, sv.name AS service_name, s.starts_at, i.expires_at, i.status,
           i.inviter_id, i.invitee_id
    FROM app.class_invites i
    JOIN app.sessions s ON s.id = i.session_id
    JOIN app.services sv ON sv.id = s.service_id
"""


INVITE_BY_ID = INVITE_SELECT + " WHERE i.id = :id"
INVITES_HELD = (
    INVITE_SELECT
    + " WHERE i.status = 'pending' AND i.expires_at > now() ORDER BY s.starts_at, i.created_at"
)


def _invite(row: dict, me: UUID, names: dict[UUID, str]) -> Invite:
    received = row["invitee_id"] == me
    other = row["inviter_id"] if received else row["invitee_id"]
    return Invite(
        id=row["id"],
        direction="received" if received else "sent",
        session_id=row["session_id"],
        service_name=row["service_name"],
        starts_at=row["starts_at"],
        expires_at=row["expires_at"],
        status=row["status"],
        other_client_id=other,
        other_first_name=names.get(other),
    )


def _invite_by_id(db: Session, invite_id: UUID) -> Invite:
    row = db.execute(text(INVITE_BY_ID), {"id": invite_id}).mappings().one()
    me = db.execute(text("SELECT app.current_client_id()")).scalar_one()
    return _invite(dict(row), me, _names(db))


def _names(db: Session) -> dict[UUID, str]:
    return {
        row["client_id"]: row["first_name"]
        for row in db.execute(text("SELECT client_id, first_name FROM app.social_connections()"))
        .mappings()
        .all()
    }


@router.get("/invites")
def my_invites(context: ClientDep) -> list[Invite]:
    """Invitations I received and sent that still hold a spot, soonest class first."""
    db = context.session
    _forbidden_unless_enabled(db)
    rows = db.execute(text(INVITES_HELD)).mappings()
    names = _names(db)
    return [_invite(dict(row), context.client_id, names) for row in rows]


@router.post("/sessions/{session_id}/invites", status_code=status.HTTP_201_CREATED)
def invite_friend(session_id: UUID, body: InviteCreate, context: ClientDep) -> Invite:
    """Holds a spot in a class I am booked into for a friend, for two hours (never past the
    class's cancellation deadline). The friend gets a notification and a push."""
    db = context.session
    _forbidden_unless_enabled(db)
    if not _session_has_lists(db, session_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="friends_disabled")
    session = lock_session(db, session_id)  # serializes spots for this class
    if session["status"] == "cancelled":
        raise _conflict("session_cancelled")
    window = db.execute(
        text("SELECT cancellation_window_minutes FROM app.tenants WHERE id = :t"),
        {"t": context.tenant_id},
    ).scalar_one()
    now = datetime.now(UTC)
    expires_at = min(now + INVITE_HOLD, session["starts_at"] - timedelta(minutes=window))
    if expires_at <= now:
        raise _conflict("invite_window_closed")
    mine = db.execute(
        text("""
            SELECT 1 FROM app.bookings
            WHERE session_id = :s AND client_id = :c AND dependent_id IS NULL
              AND status IN ('booked', 'checked_in')
        """),
        {"s": session_id, "c": context.client_id},
    ).first()
    if mine is None:
        raise _conflict("not_booked")
    pair = _pair(db, context.client_id, body.friend_id)
    if pair is None or pair["status"] != "accepted":
        raise not_found()
    if db.execute(
        text("SELECT app.social_has_booking(:f, :s)"), {"f": body.friend_id, "s": session_id}
    ).scalar():
        raise _conflict("already_booked")
    db.execute(
        text("""
            UPDATE app.class_invites SET status = 'expired'
            WHERE session_id = :s AND invitee_id = :f AND status = 'pending' AND expires_at <= now()
        """),
        {"s": session_id, "f": body.friend_id},
    )
    booked, _ = db.execute(
        text("SELECT booked, waitlisted FROM app.session_counts(:id)"), {"id": session_id}
    ).one()
    if booked >= session["capacity"]:
        raise _conflict("session_full")
    try:
        with db.begin_nested():
            invite_id = db.execute(
                text("""
                    INSERT INTO app.class_invites
                        (tenant_id, session_id, inviter_id, invitee_id, expires_at)
                    VALUES (:t, :s, :me, :f, :expires)
                    RETURNING id
                """),
                {
                    "t": context.tenant_id,
                    "s": session_id,
                    "me": context.client_id,
                    "f": body.friend_id,
                    "expires": expires_at,
                },
            ).scalar_one()
    except IntegrityError as error:
        raise _conflict("already_invited") from error
    invite = _invite_by_id(db, invite_id)
    payload = json.dumps(
        {
            "from_name": _my_first_name(context),
            "invite_id": str(invite_id),
            "session_id": str(session_id),
            "service_name": invite.service_name,
            "starts_at": invite.starts_at.isoformat(),
        }
    )
    db.execute(
        text("SELECT app.social_notify(:to, 'class_invite', CAST(:payload AS jsonb))"),
        {"to": body.friend_id, "payload": payload},
    )
    return invite


@router.post("/invites/{invite_id}/accept")
def accept_invite(invite_id: UUID, context: ClientDep) -> ClientSession:
    """Takes the held spot: books the class (the same rules as booking it myself)."""
    db = context.session
    _forbidden_unless_enabled(db)
    row = db.execute(
        text("""
            SELECT session_id, expires_at FROM app.class_invites
            WHERE id = :id AND invitee_id = :me AND status = 'pending'
        """),
        {"id": invite_id, "me": context.client_id},
    ).first()
    if row is None:
        raise not_found()
    session = lock_session(db, row.session_id)
    if row.expires_at <= datetime.now(UTC) or session["starts_at"] <= datetime.now(UTC):
        db.execute(
            text("UPDATE app.class_invites SET status = 'expired' WHERE id = :id"),
            {"id": invite_id},
        )
        db.commit()
        raise _conflict("invite_expired")
    if session["status"] == "cancelled":
        raise _conflict("session_cancelled")
    # The hold stops counting once the invite is answered, then the booking takes the spot.
    db.execute(
        text("""
            UPDATE app.class_invites SET status = 'accepted', responded_at = now() WHERE id = :id
        """),
        {"id": invite_id},
    )
    ensure_may_book(db, context.tenant_id, context.client_id)
    requires_plan = db.execute(
        text("SELECT booking_requires_plan FROM app.tenants WHERE id = :id"),
        {"id": context.tenant_id},
    ).scalar_one()
    booking_id = place_booking(
        db,
        context.tenant_id,
        row.session_id,
        context.client_id,
        requires_plan=requires_plan,
    )
    db.execute(
        text("UPDATE app.class_invites SET booking_id = :b WHERE id = :id"),
        {"b": booking_id, "id": invite_id},
    )
    return _load_session(db, row.session_id)


@router.post("/invites/{invite_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_invite(invite_id: UUID, context: ClientDep) -> Response:
    return _end_invite(context, invite_id, "declined", "invitee")


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invite(invite_id: UUID, context: ClientDep) -> Response:
    """The inviter takes the invitation back and frees the spot."""
    return _end_invite(context, invite_id, "cancelled", "inviter")


def _end_invite(context: ClientContext, invite_id: UUID, new_status: str, who: str) -> Response:
    changed = context.session.execute(
        text("""
            UPDATE app.class_invites SET status = :status, responded_at = now()
            WHERE id = :id AND status = 'pending'
              AND CASE :who WHEN 'invitee' THEN invitee_id ELSE inviter_id END = :me
        """),
        {"status": new_status, "id": invite_id, "me": context.client_id, "who": who},
    ).rowcount
    if not changed:
        raise not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
