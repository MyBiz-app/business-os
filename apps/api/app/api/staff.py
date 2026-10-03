import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.common import not_found, set_clause
from app.api.deps import SessionDep, TenantContext, UserDep, require
from app.api.routes import ensure_profile
from app.permissions import ROLE_PERMISSIONS, Permission

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
    custom_role_id: UUID | None
    custom_role_name: str | None
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
    """Either a system role, or a custom role (the member's system role becomes `staff`)."""

    role: Role | None = None
    custom_role_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "MemberUpdate":
        if (self.role is None) == (self.custom_role_id is None):
            raise ValueError("give either role or custom_role_id")
        return self


PermissionKey = Literal[tuple(p.value for p in Permission)]  # type: ignore[valid-type]


class RoleFields(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    permissions: list[PermissionKey] = Field(max_length=len(Permission))  # type: ignore[valid-type]

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    permissions: list[PermissionKey] | None = None  # type: ignore[valid-type]


class SystemRole(BaseModel):
    key: Role
    permissions: list[str]


class CustomRole(BaseModel):
    id: UUID
    name: str
    permissions: list[str]
    members: int


class Roles(BaseModel):
    permissions: list[str] = Field(description="Every permission key, in display order")
    system: list[SystemRole]
    custom: list[CustomRole]


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
            SELECT m.user_id, u.email, u.full_name, m.role, m.custom_role_id,
                   r.name AS custom_role_name, m.created_at AS joined_at
            FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
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


def _load_member(session: Session, user_id: UUID) -> Member:
    row = (
        session.execute(
            text("""
                SELECT m.user_id, u.email, u.full_name, m.role, m.custom_role_id,
                       r.name AS custom_role_name, m.created_at AS joined_at
                FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
                WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        .mappings()
        .one()
    )
    return Member.model_validate(dict(row))


def _check_within_own(context: TenantContext, permissions: list[str]) -> None:
    """Nobody can hand out permissions they do not have themselves."""
    if not set(permissions) <= context.permissions:
        raise _forbidden("exceeds_own_permissions")


@router.patch("/staff/{user_id}")
def update_member(user_id: UUID, body: MemberUpdate, user: UserDep, context: ManageDep) -> Member:
    current = _member_role(context.session, user_id)
    if current is None:
        raise not_found()
    # Owners may step down (if another owner remains); nobody else changes their own role.
    if user_id == user.id and context.role != "owner":
        raise _forbidden("cannot_change_own_role")
    _check_can_grant(context, current)
    new_role = body.role or "staff"
    _check_can_grant(context, new_role)
    if current == "owner" and new_role != "owner" and _owner_count(context.session) == 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="last_owner")
    if body.custom_role_id is not None:
        permissions = context.session.execute(
            text("SELECT permissions FROM app.tenant_roles WHERE id = :id"),
            {"id": body.custom_role_id},
        ).scalar()
        if permissions is None:
            raise HTTPException(status_code=422, detail="invalid_reference")
        _check_within_own(context, permissions)
    context.session.execute(
        text("""
            UPDATE app.tenant_members SET role = :role, custom_role_id = :custom_role_id
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
        """),
        {"role": new_role, "custom_role_id": body.custom_role_id, "user_id": user_id},
    )
    return _load_member(context.session, user_id)


ROLE_SELECT = """
    SELECT r.id, r.name, r.permissions,
           (SELECT count(*) FROM app.tenant_members m WHERE m.custom_role_id = r.id) AS members
    FROM app.tenant_roles r
"""


def _load_role(session: Session, role_id: UUID) -> CustomRole:
    row = session.execute(text(f"{ROLE_SELECT} WHERE r.id = :id"), {"id": role_id}).mappings()
    found = row.first()
    if found is None:
        raise not_found()
    return CustomRole.model_validate(dict(found))


def _name_taken(error: IntegrityError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="name_taken")


@router.get("/roles")
def list_roles(context: ReadDep) -> Roles:
    rows = context.session.execute(text(f"{ROLE_SELECT} ORDER BY lower(r.name)")).mappings()
    return Roles(
        permissions=[p.value for p in Permission],
        system=[
            SystemRole(key=key, permissions=sorted(p.value for p in perms))  # type: ignore[arg-type]
            for key, perms in ROLE_PERMISSIONS.items()
        ],
        custom=[CustomRole.model_validate(dict(row)) for row in rows],
    )


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def create_role(body: RoleFields, context: ManageDep) -> CustomRole:
    _check_within_own(context, body.permissions)
    try:
        role_id = context.session.execute(
            text("""
                INSERT INTO app.tenant_roles (tenant_id, name, permissions)
                VALUES (:tenant_id, :name, :permissions) RETURNING id
            """),
            {"tenant_id": context.tenant_id, "name": body.name, "permissions": body.permissions},
        ).scalar_one()
    except IntegrityError as error:
        raise _name_taken(error) from error
    return _load_role(context.session, role_id)


@router.patch("/roles/{role_id}")
def update_role(role_id: UUID, body: RoleUpdate, context: ManageDep) -> CustomRole:
    _load_role(context.session, role_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "permissions" in changes:
        _check_within_own(context, changes["permissions"])
    if changes:
        try:
            context.session.execute(
                text(f"UPDATE app.tenant_roles SET {set_clause(changes)} WHERE id = :id"),
                {**changes, "id": role_id},
            )
        except IntegrityError as error:
            raise _name_taken(error) from error
    return _load_role(context.session, role_id)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: UUID, context: ManageDep) -> None:
    role = _load_role(context.session, role_id)
    if role.members:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="role_in_use")
    context.session.execute(text("DELETE FROM app.tenant_roles WHERE id = :id"), {"id": role_id})


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
