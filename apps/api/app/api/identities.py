"""ID numbers of team members and clients (round 6, K1).

The number is stored encrypted (see `app.core.identity`). Screens get only the type and the last
four characters; the full number is revealed by `POST .../reveal` to someone with `identity.read`
(owners), or to the person themselves, and every reveal is written to the business's audit log.
Clients are asked only when the business turned that on (`tenants.client_id_number`)."""

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import (
    ClientDep,
    TenantContext,
    TenantDep,
    UserDep,
    ensure_branch_visible,
    require,
)
from app.api.staff import _ensure_member_in_reach
from app.core import identity
from app.core.permissions import Permission

router = APIRouter(tags=["identity"])

StaffReadDep = Annotated[TenantContext, Depends(require(Permission.STAFF_READ))]
StaffManageDep = Annotated[TenantContext, Depends(require(Permission.STAFF_MANAGE))]
ClientsReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
ClientsWriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]
RevealDep = Annotated[TenantContext, Depends(require(Permission.IDENTITY_READ))]


class IdentityBody(BaseModel):
    id_type: identity.IdType
    number: str = Field(min_length=1, max_length=40)
    country: str | None = Field(
        default=None, max_length=2, description="ISO country, for a passport or foreign ID"
    )

    @field_validator("number", "country", mode="before")
    @classmethod
    def trimmed(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class IdentitySummary(BaseModel):
    """What a screen may show: never the full number."""

    present: bool
    id_type: identity.IdType | None = None
    country: str | None = None
    last4: str | None = None
    can_reveal: bool = False


class ClientIdentity(IdentitySummary):
    mode: str = Field(description="off, optional or required: whether this business asks")


class Revealed(BaseModel):
    number: str


def _summary(row: Any, can_reveal: bool = False) -> IdentitySummary:
    if row is None:
        return IdentitySummary(present=False, can_reveal=can_reveal)
    return IdentitySummary(
        present=True,
        id_type=row["id_type"],
        country=row["country"],
        last4=row["id_last4"],
        can_reveal=can_reveal,
    )


def _row(session: Session, column: str, subject_id: UUID) -> Any:
    return (
        session.execute(
            text(
                f"SELECT id_type, country, id_last4, id_number_encrypted"
                f" FROM app.person_identities WHERE {column} = :id"
            ),
            {"id": subject_id},
        )
        .mappings()
        .first()
    )


def _audit(
    session: Session, tenant_id: UUID, action: str, entity_type: str, entity_id: UUID
) -> None:
    session.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES (:tenant_id, 'user', app.current_user_id(), :action, :entity_type, :entity_id,
                    CAST(:details AS jsonb))
        """),
        {
            "tenant_id": tenant_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": json.dumps({}),
        },
    )


def _store(
    session: Session, tenant_id: UUID, column: str, subject_id: UUID, body: IdentityBody
) -> IdentitySummary:
    try:
        number, country = identity.normalize(body.id_type, body.number, body.country)
    except identity.InvalidIdentity as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"invalid_id_{error}"
        ) from error
    try:
        session.execute(
            text(f"""
                INSERT INTO app.person_identities
                    (tenant_id, {column}, id_type, country, id_number_encrypted, id_hash,
                     id_last4)
                VALUES (:tenant_id, :subject, :id_type, :country, :encrypted, :hash, :last4)
                ON CONFLICT (tenant_id, {column}) WHERE {column} IS NOT NULL DO UPDATE
                SET id_type = excluded.id_type, country = excluded.country,
                    id_number_encrypted = excluded.id_number_encrypted,
                    id_hash = excluded.id_hash, id_last4 = excluded.id_last4, updated_at = now()
            """),
            {
                "tenant_id": tenant_id,
                "subject": subject_id,
                "id_type": body.id_type,
                "country": country,
                "encrypted": identity.encrypt_number(number),
                "hash": identity.number_hash(tenant_id, number),
                "last4": identity.last4(number),
            },
        )
    except IntegrityError as error:  # the same number belongs to someone else here
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="id_number_in_use"
        ) from error
    return _summary(_row(session, column, subject_id))


def _reveal(
    session: Session, tenant_id: UUID, column: str, subject_id: UUID, entity_type: str
) -> Revealed:
    row = _row(session, column, subject_id)
    if row is None:
        raise not_found()
    _audit(session, tenant_id, "identity.revealed", entity_type, subject_id)
    return Revealed(number=identity.decrypt_number(row["id_number_encrypted"]))


def _remove(session: Session, tenant_id: UUID, column: str, subject_id: UUID, kind: str) -> None:
    removed = session.execute(
        text(f"DELETE FROM app.person_identities WHERE {column} = :id"),
        {"id": subject_id},
    ).rowcount
    if removed:
        _audit(session, tenant_id, "identity.removed", kind, subject_id)


# Team members -------------------------------------------------------------------------------


@router.get("/staff/{user_id}/identity")
def get_member_identity(user_id: UUID, context: StaffReadDep) -> IdentitySummary:
    _ensure_member_in_reach(context, user_id)
    return _summary(
        _row(context.session, "user_id", user_id),
        Permission.IDENTITY_READ in context.permissions,
    )


@router.put("/staff/{user_id}/identity")
def set_member_identity(
    user_id: UUID, body: IdentityBody, context: StaffManageDep
) -> IdentitySummary:
    _ensure_member_in_reach(context, user_id)
    summary = _store(context.session, context.tenant_id, "user_id", user_id, body)
    _audit(context.session, context.tenant_id, "identity.set", "member", user_id)
    summary.can_reveal = Permission.IDENTITY_READ in context.permissions
    return summary


@router.delete("/staff/{user_id}/identity", status_code=status.HTTP_204_NO_CONTENT)
def delete_member_identity(user_id: UUID, context: StaffManageDep) -> None:
    _ensure_member_in_reach(context, user_id)
    _remove(context.session, context.tenant_id, "user_id", user_id, "member")


@router.post("/staff/{user_id}/identity/reveal")
def reveal_member_identity(user_id: UUID, context: RevealDep) -> Revealed:
    _ensure_member_in_reach(context, user_id)
    return _reveal(context.session, context.tenant_id, "user_id", user_id, "member")


# The signed-in team member's own ID ("My details") ---------------------------------------------


@router.get("/me/identity")
def get_own_identity(user: UserDep, context: TenantDep) -> IdentitySummary:
    return _summary(_row(context.session, "user_id", user.id), can_reveal=True)


@router.put("/me/identity")
def set_own_identity(body: IdentityBody, user: UserDep, context: TenantDep) -> IdentitySummary:
    summary = _store(context.session, context.tenant_id, "user_id", user.id, body)
    _audit(context.session, context.tenant_id, "identity.set", "member", user.id)
    summary.can_reveal = True
    return summary


@router.delete("/me/identity", status_code=status.HTTP_204_NO_CONTENT)
def delete_own_identity(user: UserDep, context: TenantDep) -> None:
    _remove(context.session, context.tenant_id, "user_id", user.id, "member")


@router.post("/me/identity/reveal")
def reveal_own_identity(user: UserDep, context: TenantDep) -> Revealed:
    return _reveal(context.session, context.tenant_id, "user_id", user.id, "member")


# Clients (when the business asks for them) ----------------------------------------------------


def _client_in_reach(context: TenantContext, client_id: UUID) -> None:
    row = (
        context.session.execute(
            text("SELECT home_location_id FROM app.clients WHERE id = :id"), {"id": client_id}
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    ensure_branch_visible(context, row["home_location_id"])


def _mode(session: Session, tenant_column: str) -> str:
    return session.execute(
        text(f"SELECT client_id_number FROM app.tenants WHERE id = {tenant_column}")
    ).scalar_one()


def _client_summary(row: Any, mode: str, can_reveal: bool) -> ClientIdentity:
    return ClientIdentity(**_summary(row, can_reveal).model_dump(), mode=mode)


@router.get("/clients/{client_id}/identity")
def get_client_identity(client_id: UUID, context: ClientsReadDep) -> ClientIdentity:
    _client_in_reach(context, client_id)
    return _client_summary(
        _row(context.session, "client_id", client_id),
        _mode(context.session, "app.current_tenant_id()"),
        Permission.IDENTITY_READ in context.permissions,
    )


@router.put("/clients/{client_id}/identity")
def set_client_identity(
    client_id: UUID, body: IdentityBody, context: ClientsWriteDep
) -> ClientIdentity:
    _client_in_reach(context, client_id)
    mode = _mode(context.session, "app.current_tenant_id()")
    if mode == "off":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="client_id_off")
    summary = _store(context.session, context.tenant_id, "client_id", client_id, body)
    _audit(context.session, context.tenant_id, "identity.set", "client", client_id)
    return ClientIdentity(
        **summary.model_dump(exclude={"can_reveal"}),
        can_reveal=Permission.IDENTITY_READ in context.permissions,
        mode=mode,
    )


@router.delete("/clients/{client_id}/identity", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_identity(client_id: UUID, context: ClientsWriteDep) -> None:
    _client_in_reach(context, client_id)
    _remove(context.session, context.tenant_id, "client_id", client_id, "client")


@router.post("/clients/{client_id}/identity/reveal")
def reveal_client_identity(client_id: UUID, context: RevealDep) -> Revealed:
    _client_in_reach(context, client_id)
    return _reveal(context.session, context.tenant_id, "client_id", client_id, "client")


# The client's own ID in the client app --------------------------------------------------------


@router.get("/client/identity")
def get_own_client_identity(context: ClientDep) -> ClientIdentity:
    return _client_summary(
        _row(context.session, "client_id", context.client_id),
        _mode(context.session, "app.client_tenant_id()"),
        can_reveal=True,
    )


@router.put("/client/identity")
def set_own_client_identity(body: IdentityBody, context: ClientDep) -> ClientIdentity:
    mode = _mode(context.session, "app.client_tenant_id()")
    if mode == "off":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="client_id_off")
    summary = _store(context.session, context.tenant_id, "client_id", context.client_id, body)
    _audit(context.session, context.tenant_id, "identity.set", "client", context.client_id)
    return ClientIdentity(**summary.model_dump(exclude={"can_reveal"}), can_reveal=True, mode=mode)


@router.delete("/client/identity", status_code=status.HTTP_204_NO_CONTENT)
def delete_own_client_identity(context: ClientDep) -> None:
    _remove(context.session, context.tenant_id, "client_id", context.client_id, "client")


@router.post("/client/identity/reveal")
def reveal_own_client_identity(context: ClientDep) -> Revealed:
    return _reveal(context.session, context.tenant_id, "client_id", context.client_id, "client")
