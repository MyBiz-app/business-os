import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.api.common import blank_to_none, not_found, set_clause
from app.api.deps import SessionDep, TenantContext, UserDep, require
from app.api.routes import ensure_profile
from app.core.audit import record
from app.core.business_size import grow_from_solo
from app.core.permissions import ROLE_PERMISSIONS, Permission, effective_permissions
from app.schedule.branch_managers import (
    TEAM_ROLES,
    forget_manager,
    member_row,
    suggest_reports_to,
)

router = APIRouter(tags=["staff"])

Role = Literal["owner", "manager", "branch_manager", "staff", "front_desk"]
InvitationStatus = Literal["pending", "expired", "accepted"]

ReadDep = Annotated[TenantContext, Depends(require(Permission.STAFF_READ))]
ManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]

INVITATION_TTL = timedelta(days=7)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _check_can_grant(context: TenantContext, role: str) -> None:
    """Only owners can create, change or remove owners; someone kept to some branches (a branch
    manager) works with staff and front desk only, never at or above their own level."""
    if role == "owner" and context.role != "owner":
        raise _forbidden("only_owners_manage_owners")
    if context.branches is not None and role not in TEAM_ROLES:
        raise _forbidden("exceeds_own_level")


def _ensure_branches_within(context: TenantContext, location_ids: list[UUID]) -> None:
    """A person kept to some branches can only name those branches."""
    if context.branches is not None and not set(location_ids) <= context.branches:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_branch"
        )


def _ensure_member_in_reach(context: TenantContext, user_id: UUID) -> str:
    """The member's role, for a request that reads or changes them. Someone kept to some branches
    reaches only people kept to branches of their own: everyone else is "not found"."""
    row = member_row(context.session, user_id)
    if row is None:
        raise not_found()
    role, location_ids = row
    if context.branches is not None and not (
        location_ids and set(location_ids) <= context.branches
    ):
        raise not_found()
    return role


def _ensure_unscoped(context: TenantContext) -> None:
    """Business-wide things (custom roles) are not for people kept to some branches."""
    if context.branches is not None:
        raise _forbidden("forbidden")


def _ensure_branch_bound_has_branches(role: str, location_ids: list[UUID]) -> None:
    if role == "branch_manager" and not location_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="branch_manager_needs_branch"
        )


class Member(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None
    role: Role
    custom_role_id: UUID | None
    custom_role_name: str | None
    location_ids: list[UUID] = Field(description="Branches they work at; empty means all")
    home_location_id: UUID | None = Field(
        description="The branch they normally work at (informational: shifts elsewhere are cover)"
    )
    joined_at: datetime
    job_title: str | None
    reports_to: UUID | None = Field(description="Who they report to (never grants access)")
    phone: str | None
    avatar_url: str | None = Field(description="Path of their picture on this API, if any")
    permissions: list[str] = Field(description="What they can actually do (their role's switches)")

    @model_validator(mode="before")
    @classmethod
    def with_permissions(cls, data: Any) -> Any:
        if isinstance(data, dict) and "permissions" not in data:
            data = {**data}
            custom = data.pop("custom_permissions", None)
            order = [p.value for p in Permission]
            effective = effective_permissions(data["role"], custom, data.pop("ai_access", None))
            data["permissions"] = [p for p in order if p in effective]
        return data


class Invitation(BaseModel):
    id: UUID
    email: str
    role: Role
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    location_ids: list[UUID] = Field(description="Branches the new member will be kept to")


class Team(BaseModel):
    members: list[Member]
    invitations: list[Invitation]


class InvitationCreate(BaseModel):
    email: EmailStr
    role: Role
    location_ids: list[UUID] = Field(
        default_factory=list,
        max_length=200,
        description="Branches the new member is kept to (empty: all; a branch manager's own)",
    )

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


MEMBER_SELECT = """
    SELECT m.user_id, u.email, u.full_name, m.role, m.custom_role_id,
           r.name AS custom_role_name, r.permissions AS custom_permissions, m.ai_access,
           m.location_ids, m.created_at AS joined_at,
           m.job_title, m.reports_to, m.home_location_id, u.phone,
           CASE WHEN u.avatar_updated_at IS NULL THEN NULL
                ELSE '/staff/' || u.id || '/avatar?v='
                     || extract(epoch FROM u.avatar_updated_at)::bigint END AS avatar_url
    FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
    LEFT JOIN app.tenant_roles r ON r.id = m.custom_role_id
    WHERE m.tenant_id = app.current_tenant_id()
"""

INVITATION_SELECT = """
    SELECT id, email, role, expires_at, created_at, location_ids,
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
def get_team(user: UserDep, context: ReadDep) -> Team:
    members = context.session.execute(text(f"{MEMBER_SELECT} ORDER BY m.created_at")).mappings()
    invitations = context.session.execute(
        text(f"{INVITATION_SELECT} WHERE accepted_at IS NULL ORDER BY created_at DESC")
    ).mappings()
    team = Team(
        members=[Member.model_validate(dict(row)) for row in members],
        invitations=[Invitation.model_validate(dict(row)) for row in invitations],
    )
    if context.branches is not None:  # a branch manager sees their own branches' people
        branches = context.branches
        team.members = [
            m
            for m in team.members
            if m.user_id == user.id or (m.location_ids and set(m.location_ids) & branches)
        ]
        team.invitations = [
            i for i in team.invitations if i.location_ids and set(i.location_ids) <= branches
        ]
    return team


@router.post("/staff/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    body: InvitationCreate, user: UserDep, context: ManageDep
) -> CreatedInvitation:
    _check_can_grant(context, body.role)
    location_ids = sorted(set(body.location_ids))
    if not location_ids and context.branches is not None:
        location_ids = sorted(context.branches)  # a branch manager invites into their branches
    _ensure_branches_within(context, location_ids)
    _ensure_branch_bound_has_branches(body.role, location_ids)
    if location_ids and context.session.execute(
        text("SELECT count(*) FROM app.locations WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [str(i) for i in location_ids]},
    ).scalar_one() != len(location_ids):
        raise HTTPException(status_code=422, detail="unknown_branch")
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
                        (tenant_id, email, role, token_hash, invited_by, expires_at, location_ids)
                    VALUES (:tenant_id, :email, :role, :token_hash, :invited_by, :expires_at,
                            CAST(:location_ids AS uuid[]))
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
                "location_ids": [str(i) for i in location_ids],
            },
        )
        .mappings()
        .one()
    )
    record(
        context.session,
        "staff.invited",
        entity_type="invitation",
        entity_id=row["id"],
        email=body.email,
        role=body.role,
    )
    grow_from_solo(context.session, context.tenant_id)  # the first employee ends solo mode
    return CreatedInvitation(**row, token=token)


@router.delete("/staff/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: UUID, context: ManageDep) -> None:
    invitation = context.session.execute(
        text("SELECT role, location_ids FROM app.invitations WHERE id = :id"), {"id": invitation_id}
    ).first()
    if invitation is None:
        raise not_found()
    role = invitation.role
    if context.branches is not None and not (
        invitation.location_ids and set(invitation.location_ids) <= context.branches
    ):
        raise not_found()
    _check_can_grant(context, role)
    context.session.execute(
        text("DELETE FROM app.invitations WHERE id = :id"), {"id": invitation_id}
    )
    record(
        context.session,
        "staff.invitation_revoked",
        entity_type="invitation",
        entity_id=invitation_id,
        role=role,
    )


def _load_member(session: Session, user_id: UUID) -> Member:
    row = (
        session.execute(
            text(f"{MEMBER_SELECT} AND m.user_id = :user_id"),
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
    current = _ensure_member_in_reach(context, user_id)
    # Owners may step down (if another owner remains); nobody else changes their own role.
    if user_id == user.id and context.role != "owner":
        raise _forbidden("cannot_change_own_role")
    _check_can_grant(context, current)
    new_role = body.role or "staff"
    _check_can_grant(context, new_role)
    if new_role == "branch_manager":
        # Appointing goes through the branch (PUT /locations/{id}/manager); here only a member
        # who is already kept to branches can be given the role.
        row = member_row(context.session, user_id)
        _ensure_branch_bound_has_branches(new_role, row[1] if row else [])
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
    if current == "branch_manager" and new_role != "branch_manager":
        forget_manager(context.session, user_id)
    record(
        context.session,
        "staff.role_changed",
        entity_type="member",
        entity_id=user_id,
        old_role=current,
        new_role=new_role,
        custom_role_id=body.custom_role_id,
    )
    return _load_member(context.session, user_id)


class MemberBranches(BaseModel):
    location_ids: list[UUID] = Field(max_length=200, description="Empty means all branches")


@router.put("/staff/{user_id}/branches")
def set_member_branches(user_id: UUID, body: MemberBranches, context: ManageDep) -> Member:
    """The branches a team member works at (they see these first); none means all."""
    role = _ensure_member_in_reach(context, user_id)
    ids = sorted(set(body.location_ids))
    _ensure_branches_within(context, ids)
    if context.branches is not None and not ids:
        raise HTTPException(status_code=422, detail="unknown_branch")  # empty would mean all
    _ensure_branch_bound_has_branches(role, ids)
    known = context.session.execute(
        text("SELECT count(*) FROM app.locations WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": [str(i) for i in ids]},
    ).scalar_one()
    if known != len(ids):
        raise HTTPException(status_code=422, detail="unknown_branch")
    context.session.execute(
        text("""
            UPDATE app.tenant_members SET location_ids = CAST(:ids AS uuid[])
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
        """),
        {"ids": [str(i) for i in ids], "user_id": user_id},
    )
    if role == "branch_manager":  # they manage only the branches they still have
        forget_manager(context.session, user_id, kept=ids)
    suggest_reports_to(context.session, user_id)
    record(
        context.session,
        "staff.branches_set",
        entity_type="member",
        entity_id=user_id,
        location_ids=[str(i) for i in ids],
    )
    return _load_member(context.session, user_id)


class HomeBranch(BaseModel):
    location_id: UUID | None = Field(description="None clears it")


@router.put("/staff/{user_id}/home-branch")
def set_home_branch(user_id: UUID, body: HomeBranch, context: ManageDep) -> Member:
    """Where a member normally works. It never limits where a shift can be placed: a shift at
    another branch is simply shown as cover."""
    _ensure_member_in_reach(context, user_id)
    if body.location_id is not None:
        _ensure_branches_within(context, [body.location_id])
        known = context.session.execute(
            text("SELECT 1 FROM app.locations WHERE id = :id"), {"id": body.location_id}
        ).first()
        if known is None:
            raise HTTPException(status_code=422, detail="unknown_branch")
    context.session.execute(
        text("""
            UPDATE app.tenant_members SET home_location_id = :location
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
        """),
        {"location": body.location_id, "user_id": user_id},
    )
    suggest_reports_to(context.session, user_id)
    return _load_member(context.session, user_id)


class MemberOrganization(BaseModel):
    """A member's place in the business: their title and who they report to. Reporting is for
    the org chart only and never changes what anyone may see or do."""

    job_title: str | None = Field(default=None, max_length=80)
    reports_to: UUID | None = None

    @field_validator("job_title", mode="before")
    @classmethod
    def blank_title(cls, value: object) -> object:
        return blank_to_none(value)


@router.patch("/staff/{user_id}/organization")
def set_member_organization(user_id: UUID, body: MemberOrganization, context: ManageDep) -> Member:
    _ensure_member_in_reach(context, user_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return _load_member(context.session, user_id)
    if changes.get("reports_to") is not None:
        if changes["reports_to"] == user_id:
            raise HTTPException(status_code=422, detail="reporting_cycle")
        if _member_role(context.session, changes["reports_to"]) is None:
            raise HTTPException(status_code=422, detail="invalid_reference")
        if context.branches is not None:  # only within their own branches' people (or themselves)
            boss = member_row(context.session, changes["reports_to"])
            if boss is None or not (boss[1] and set(boss[1]) & context.branches):
                raise HTTPException(status_code=422, detail="invalid_reference")
    assignments = set_clause(changes, MemberOrganization.model_fields, touch=False)
    try:
        with context.session.begin_nested():
            context.session.execute(
                text(f"""
                    UPDATE app.tenant_members SET {assignments}
                    WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
                """),
                {**changes, "user_id": user_id},
            )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) == "23514":
            raise HTTPException(status_code=422, detail="reporting_cycle") from error
        raise
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
    _ensure_unscoped(context)
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
    record(
        context.session,
        "role.created",
        entity_type="role",
        entity_id=role_id,
        name=body.name,
        permissions=sorted(body.permissions),
    )
    return _load_role(context.session, role_id)


@router.patch("/roles/{role_id}")
def update_role(role_id: UUID, body: RoleUpdate, context: ManageDep) -> CustomRole:
    _ensure_unscoped(context)
    _load_role(context.session, role_id)
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "permissions" in changes:
        _check_within_own(context, changes["permissions"])
    if changes:
        assignments = set_clause(changes, RoleUpdate.model_fields)
        try:
            context.session.execute(
                text(f"UPDATE app.tenant_roles SET {assignments} WHERE id = :id"),
                {**changes, "id": role_id},
            )
        except IntegrityError as error:
            raise _name_taken(error) from error
    record(
        context.session,
        "role.updated",
        entity_type="role",
        entity_id=role_id,
        changed=sorted(changes),
        permissions=sorted(changes["permissions"]) if "permissions" in changes else None,
    )
    return _load_role(context.session, role_id)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: UUID, context: ManageDep) -> None:
    _ensure_unscoped(context)
    role = _load_role(context.session, role_id)
    if role.members:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="role_in_use")
    context.session.execute(text("DELETE FROM app.tenant_roles WHERE id = :id"), {"id": role_id})
    record(context.session, "role.deleted", entity_type="role", entity_id=role_id, name=role.name)


@router.delete("/staff/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: UUID, user: UserDep, context: ManageDep) -> None:
    current = _ensure_member_in_reach(context, user_id)
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot_remove_self")
    _check_can_grant(context, current)
    if current == "owner" and _owner_count(context.session) == 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="last_owner")
    removed = context.session.execute(
        text("SELECT email FROM app.users WHERE id = :id"), {"id": user_id}
    ).scalar()
    record(
        context.session,
        "staff.removed",
        entity_type="member",
        entity_id=user_id,
        email=removed,
        role=current,
    )
    forget_manager(context.session, user_id)
    # Their ID number goes with them (payslips, once kept, have their own retention).
    context.session.execute(
        text("DELETE FROM app.person_identities WHERE user_id = :user_id"), {"user_id": user_id}
    )
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
