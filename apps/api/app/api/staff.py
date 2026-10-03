import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import SessionDep, TenantContext, UserDep, require
from app.api.routes import ensure_profile
from app.permissions import Permission

router = APIRouter(tags=["staff"])

Role = Literal["owner", "manager", "staff", "front_desk"]
InvitationStatus = Literal["pending", "expired", "accepted"]

ReadDep = Annotated[TenantContext, Depends(require(Permission.STAFF_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]

INVITATION_TTL = timedelta(days=7)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _check_can_grant(context: TenantContext, role: str) -> None:
    """Only owners can create, change or remove owners."""
    if role == "owner" and context.role != "owner":
        raise _forbidden("only_owners_manage_owners")


class Member(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    role: Role
    joined_at: datetime


class Invitation(BaseModel):
    id: UUID
    email: str
    role: Role
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class Team(BaseModel):
    members: list[Member]
    invitations: list[Invitation]


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Role

    @field_validator("email")
    @classmethod
    def lowercase(cls, value: str) -> str:
        return value.lower()


class CreatedInvitation(Invitation):
    token: str  # Returned only once; the database keeps just its hash.


class MemberUpdate(BaseModel):
    role: Role


class InvitationPreview(BaseModel):
    tenant_name: str
    role: Role
    email: str
    status: InvitationStatus


class AcceptInvitation(BaseModel):
    token: str


class Accepted(BaseModel):
    tenant_id: UUID


INVITATION_SELECT = """
    SELECT id, email, role, expires_at, created_at,
           CASE WHEN accepted_at IS NOT NULL THEN 'accepted'
                WHEN expires_at < now() THEN 'expired' ELSE 'pending' END AS status
    FROM app.invitations
"""


def _member_role(session: Session, user_id: UUID) -> str | None:
    return session.execute(
        text("""
            SELECT role FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
        """),
        {"user_id": user_id},
    ).scalar()


def _owner_count(session: Session) -> int:
    return session.execute(
        text("""
            SELECT count(*) FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND role = 'owner'
        """)
    ).scalar_one()


@router.get("/staff")
def get_team(context: ReadDep) -> Team:
    members = context.session.execute(
        text("""
            SELECT m.user_id, u.email, u.full_name, m.role, m.created_at AS joined_at
            FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = app.current_tenant_id()
            ORDER BY m.created_at
        """)
    ).mappings()
    invitations = context.session.execute(
        text(f"{INVITATION_SELECT} WHERE accepted_at IS NULL ORDER BY created_at DESC")
    ).mappings()
    return Team(
        members=[Member.model_validate(dict(row)) for row in members],
        invitations=[Invitation.model_validate(dict(row)) for row in invitations],
    )


@router.post("/staff/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: InvitationCreate, user: UserDep, context: ManageDep
) -> CreatedInvitation:
    _check_can_grant(context, body.role)
    already_member = context.session.execute(
        text("""
            SELECT 1 FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = app.current_tenant_id() AND lower(u.email) = lower(:email)
        """),
        {"email": body.email},
    ).first()
    if already_member:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already_member")

    token = secrets.token_urlsafe(32)
    row = (
        context.session.execute(
            text(f"""
                WITH created AS (
                    INSERT INTO app.invitations
                        (tenant_id, email, role, token_hash, invited_by, expires_at)
                    VALUES (:tenant_id, :email, :role, :token_hash, :invited_by, :expires_at)
                    RETURNING *
                )
                {INVITATION_SELECT.replace("FROM app.invitations", "FROM created")}
            """),
            {
                "tenant_id": context.tenant_id,
                "email": body.email,
                "role": body.role,
                "token_hash": _hash(token),
                "invited_by": user.id,
                "expires_at": datetime.now(UTC) + INVITATION_TTL,
            },
        )
        .mappings()
        .one()
    )
    return CreatedInvitation(**row, token=token)


@router.delete("/staff/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: UUID, context: ManageDep) -> None:
    role = context.session.execute(
        text("SELECT role FROM app.invitations WHERE id = :id"), {"id": invitation_id}
    ).scalar()
    if role is None:
        raise not_found()
    _check_can_grant(context, role)
    context.session.execute(
        text("DELETE FROM app.invitations WHERE id = :id"), {"id": invitation_id}
    )


@router.patch("/staff/{user_id}")
def update_member(user_id: UUID, body: MemberUpdate, context: ManageDep) -> Member:
    current = _member_role(context.session, user_id)
    if current is None:
        raise not_found()
    _check_can_grant(context, current)
    _check_can_grant(context, body.role)
    if current == "owner" and body.role != "owner" and _owner_count(context.session) == 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="last_owner")
    row = (
        context.session.execute(
            text("""
                WITH updated AS (
                    UPDATE app.tenant_members SET role = :role
                    WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
                    RETURNING user_id, role, created_at
                )
                SELECT u.user_id, users.email, users.full_name, u.role, u.created_at AS joined_at
                FROM updated u JOIN app.users users ON users.id = u.user_id
            """),
            {"role": body.role, "user_id": user_id},
        )
        .mappings()
        .one()
    )
    return Member.model_validate(dict(row))


@router.delete("/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: UUID, user: UserDep, context: ManageDep) -> None:
    current = _member_role(context.session, user_id)
    if current is None:
        raise not_found()
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot_remove_self")
    _check_can_grant(context, current)
    if current == "owner" and _owner_count(context.session) == 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="last_owner")
    context.session.execute(
        text("""
            DELETE FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
        """),
        {"user_id": user_id},
    )


@router.get("/invitations/{token}")
def preview_invitation(token: str, session: SessionDep) -> InvitationPreview:
    row = (
        session.execute(text("SELECT * FROM app.invitation_preview(:hash)"), {"hash": _hash(token)})
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return InvitationPreview.model_validate(dict(row))


@router.post("/invitations/accept")
def accept_invitation(body: AcceptInvitation, user: UserDep, session: SessionDep) -> Accepted:
    ensure_profile(session, user.id, user.email)
    try:
        tenant_id = session.execute(
            text("SELECT app.accept_invitation(:hash)"), {"hash": _hash(body.token)}
        ).scalar_one()
    except DBAPIError as error:
        message = str(error.orig)
        for reason, code in [
            ("invitation_not_found", status.HTTP_404_NOT_FOUND),
            ("invitation_not_pending", status.HTTP_410_GONE),
            ("invitation_email_mismatch", status.HTTP_403_FORBIDDEN),
        ]:
            if reason in message:
                raise HTTPException(status_code=code, detail=reason) from error
        raise
    return Accepted(tenant_id=tenant_id)
