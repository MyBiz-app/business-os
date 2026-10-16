"""Branch managers (round 5, G2): who manages a branch, and who reports to them.

A branch manager is a member with the `branch_manager` role whose `location_ids` are the branches
they manage. The business's owner manages every branch until someone else is appointed. These
helpers keep three things in step: `locations.manager_user_id`, the member's role and branch
list, and the suggested `reports_to` of the people who work at the branch (the org chart)."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

# Members a branch manager may look after: nobody above their own level.
TEAM_ROLES = frozenset({"staff", "front_desk"})


def member_row(session: Session, user_id: UUID) -> tuple[str, list[UUID]] | None:
    row = session.execute(
        text("""
            SELECT role, location_ids FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
        """),
        {"user_id": user_id},
    ).first()
    return None if row is None else (row.role, list(row.location_ids))


def suggest_reports_to(session: Session, user_id: UUID) -> None:
    """A staff or front desk member without a manager gets their branch's manager (their home
    branch, else their only branch). It is a suggestion: the owner can change it afterwards."""
    manager = session.execute(
        text("""
            SELECT l.manager_user_id
            FROM app.tenant_members m
            JOIN app.locations l ON l.id = coalesce(
                m.home_location_id,
                CASE WHEN cardinality(m.location_ids) = 1 THEN m.location_ids[1] END
            )
            WHERE m.tenant_id = app.current_tenant_id() AND m.user_id = :user_id
              AND m.role IN ('staff', 'front_desk') AND m.reports_to IS NULL
              AND l.manager_user_id IS NOT NULL AND l.manager_user_id <> m.user_id
        """),
        {"user_id": user_id},
    ).scalar()
    if manager is None:
        return
    try:
        with session.begin_nested():
            session.execute(
                text("""
                    UPDATE app.tenant_members SET reports_to = :manager
                    WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
                """),
                {"manager": manager, "user_id": user_id},
            )
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) != "23514":  # a reporting cycle: leave it
            raise


def release_branch(session: Session, location_id: UUID, user_id: UUID) -> None:
    """A branch manager stops managing a branch. They keep working there as staff when it was
    their last one (never left with no branches, which would mean all of them)."""
    row = member_row(session, user_id)
    if row is None or row[0] != "branch_manager":
        return
    remaining = [b for b in row[1] if b != location_id]
    if remaining:
        session.execute(
            text("""
                UPDATE app.tenant_members SET location_ids = CAST(:ids AS uuid[])
                WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
            """),
            {"ids": [str(b) for b in remaining], "user_id": user_id},
        )
    else:
        session.execute(
            text("""
                UPDATE app.tenant_members SET role = 'staff'
                WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
            """),
            {"user_id": user_id},
        )


def forget_manager(session: Session, user_id: UUID, kept: list[UUID] | None = None) -> None:
    """Clears the user as manager of every branch (or every branch outside `kept`)."""
    session.execute(
        text("""
            UPDATE app.locations SET manager_user_id = NULL
            WHERE tenant_id = app.current_tenant_id() AND manager_user_id = :user_id
              AND NOT (id = ANY(CAST(:kept AS uuid[])))
        """),
        {"user_id": user_id, "kept": [str(b) for b in kept or []]},
    )


def appoint(session: Session, location_id: UUID, user_id: UUID) -> None:
    """Makes `user_id` the manager of the branch. Staff become branch managers kept to the
    branches they manage; owners and managers already reach every branch, so only the branch's
    record changes. A custom role is replaced: a branch manager is always the system role."""
    row = member_row(session, user_id)
    if row is None:
        raise LookupError("not_a_member")
    role, branches = row
    previous = session.execute(
        text("SELECT manager_user_id FROM app.locations WHERE id = :id"), {"id": location_id}
    ).scalar()
    if role in ("staff", "front_desk", "branch_manager"):
        session.execute(
            text("""
                UPDATE app.tenant_members
                SET role = 'branch_manager', custom_role_id = NULL,
                    location_ids = CAST(:ids AS uuid[])
                WHERE tenant_id = app.current_tenant_id() AND user_id = :user_id
            """),
            {"ids": [str(b) for b in sorted({*branches, location_id})], "user_id": user_id},
        )
    if previous is not None and previous != user_id:
        release_branch(session, location_id, previous)
    session.execute(
        text("UPDATE app.locations SET manager_user_id = :user_id WHERE id = :id"),
        {"user_id": user_id, "id": location_id},
    )
    # People who reported to the previous manager (or to nobody) now report to the new one.
    for member in (
        session.execute(
            text("""
            SELECT user_id FROM app.tenant_members
            WHERE tenant_id = app.current_tenant_id() AND user_id <> :manager
              AND (home_location_id = :id OR location_ids = ARRAY[CAST(:id AS uuid)])
              AND (reports_to IS NULL OR reports_to = :previous)
        """),
            {"manager": user_id, "id": location_id, "previous": previous},
        )
        .scalars()
        .all()
    ):
        session.execute(
            text("""
                UPDATE app.tenant_members SET reports_to = NULL
                WHERE tenant_id = app.current_tenant_id() AND user_id = :member
            """),
            {"member": member},
        )
        suggest_reports_to(session, member)


def step_down(session: Session, location_id: UUID) -> None:
    """The branch has no appointed manager any more."""
    previous = session.execute(
        text("SELECT manager_user_id FROM app.locations WHERE id = :id"), {"id": location_id}
    ).scalar()
    session.execute(
        text("UPDATE app.locations SET manager_user_id = NULL WHERE id = :id"), {"id": location_id}
    )
    if previous is not None:
        release_branch(session, location_id, previous)
