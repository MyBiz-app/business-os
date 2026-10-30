"""Demo account housekeeping: who owns the demo businesses, and an owner who is also a client.

    uv run python -m app.seed --owner-email new@real.mail --move-owner-from old@fake.mail
    uv run python -m app.seed --owner-email you@real.mail --demo ownerclient

`move_owner` hands every business membership of one account to another (both must have signed
in once, so both have a profile); nothing is deleted except the old account's memberships.
`owner_as_client` makes the owner a client of their own fitness studio too, with a plan and a
class tomorrow, so one login shows both the owner's and the client's side of the app.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import Connection, text

from app.seed.social import _book, _client_of, _entitlement, _session, _user

# The memberships' dependants carry (tenant_id, user_id) foreign keys into tenant_members.
_DEPENDANTS = """
    SELECT c.conrelid::regclass::text AS tbl,
           (SELECT a.attname FROM pg_attribute a WHERE a.attrelid = c.conrelid
             AND a.attnum = c.conkey[array_position(c.confkey, u.attnum)]) AS user_col,
           (SELECT a.attname FROM pg_attribute a WHERE a.attrelid = c.conrelid
             AND a.attnum = c.conkey[array_position(c.confkey, t.attnum)]) AS tenant_col
    FROM pg_constraint c
    JOIN pg_attribute u ON u.attrelid = c.confrelid AND u.attname = 'user_id'
    JOIN pg_attribute t ON t.attrelid = c.confrelid AND t.attname = 'tenant_id'
    WHERE c.contype = 'f' AND c.confrelid = 'app.tenant_members'::regclass
      AND u.attnum = ANY (c.confkey) AND t.attnum = ANY (c.confkey)
"""


def move_owner(conn: Connection, old_email: str, new_email: str) -> dict[str, int]:
    """Moves the old account's business memberships (and their shifts, appointments, ...) to the
    new account. Businesses where the new account is already a member are left alone."""
    ids = {}
    for label, email in (("old", old_email), ("new", new_email)):
        found = _user(conn, email)
        if found is None:
            raise SystemExit(f"No account for {email}: sign in with it once, then run again.")
        ids[label] = found
    old, new = ids["old"], ids["new"]
    if old == new:
        return {"moved": 0, "clients": 0}
    moving: list[UUID] = list(
        conn.execute(
            text("""
                SELECT m.tenant_id FROM app.tenant_members m
                WHERE m.user_id = :old AND NOT EXISTS (
                    SELECT 1 FROM app.tenant_members x
                    WHERE x.tenant_id = m.tenant_id AND x.user_id = :new)
            """),
            {"old": old, "new": new},
        ).scalars()
    )
    if moving:
        columns = conn.execute(
            text("""
                SELECT string_agg(format('%I', column_name), ', ' ORDER BY ordinal_position)
                FROM information_schema.columns
                WHERE table_schema = 'app' AND table_name = 'tenant_members'
                  AND column_name <> 'user_id'
            """)
        ).scalar_one()
        conn.execute(
            text(
                f"INSERT INTO app.tenant_members (user_id, {columns}) "
                f"SELECT :new, {columns} FROM app.tenant_members "
                "WHERE user_id = :old AND tenant_id = ANY(:moving)"
            ),
            {"old": old, "new": new, "moving": moving},
        )
        for tbl, user_col, tenant_col in conn.execute(text(_DEPENDANTS)).all():
            conn.execute(
                text(
                    f"UPDATE {tbl} SET {user_col} = :new "
                    f"WHERE {user_col} = :old AND {tenant_col} = ANY(:moving)"
                ),
                {"old": old, "new": new, "moving": moving},
            )
        conn.execute(
            text("DELETE FROM app.tenant_members WHERE user_id = :old AND tenant_id = ANY(:m)"),
            {"old": old, "m": moving},
        )
    clients = conn.execute(
        text("""
            UPDATE app.clients c SET user_id = :new
            WHERE c.user_id = :old AND NOT EXISTS (
                SELECT 1 FROM app.clients x WHERE x.tenant_id = c.tenant_id AND x.user_id = :new)
        """),
        {"old": old, "new": new},
    ).rowcount
    return {"moved": len(moving), "clients": clients}


def owner_as_client(conn: Connection, owner_email: str) -> dict[str, int]:
    """Makes the owner a client of each business they own (the first branch is home), with a
    membership that ends in a month where the business sells one and a class tomorrow where it
    runs classes. Idempotent."""
    owner = _user(conn, owner_email)
    if owner is None:
        raise SystemExit(f"No account for {owner_email}: sign in with it once, then run again.")
    done = bookings = 0
    for tenant_id, branch in conn.execute(
        text("""
            SELECT t.id, (SELECT l.id FROM app.locations l WHERE l.tenant_id = t.id
                          ORDER BY l.created_at, l.id LIMIT 1)
            FROM app.tenants t JOIN app.tenant_members m ON m.tenant_id = t.id
            WHERE m.user_id = :u AND m.role = 'owner'
        """),
        {"u": owner},
    ).all():
        if branch is None:
            continue
        me = _client_of(conn, tenant_id, owner, branch)
        membership = _entitlement(conn, tenant_id, me, branch, "membership", 30, None)
        session = _session(conn, tenant_id, branch, timedelta(hours=14))
        if session:
            _book(conn, tenant_id, session[0], me, membership)
            bookings += 1
        done += 1
    return {"businesses": done, "bookings": bookings}


def delete_businesses(conn: Connection, owner_email: str, tenant_ids: list[str]) -> int:
    """Removes demo businesses by id. Only businesses the account owns alone are removed; any
    other id is refused so a typo can never reach someone else's business."""
    owner = _user(conn, owner_email)
    if owner is None:
        raise SystemExit(f"No account for {owner_email}.")
    removed = 0
    for raw in tenant_ids:
        tenant_id = UUID(raw)
        owners = conn.execute(
            text("SELECT user_id FROM app.tenant_members WHERE tenant_id = :t AND role = 'owner'"),
            {"t": tenant_id},
        ).scalars().all()  # fmt: skip
        if owners != [owner]:
            raise SystemExit(f"Business {raw} is not owned by {owner_email} alone: not removed.")
        removed += conn.execute(
            text("DELETE FROM app.tenants WHERE id = :t"), {"t": tenant_id}
        ).rowcount
    return removed


def delete_account(conn: Connection, email: str) -> dict[str, int]:
    """Removes an account that holds nothing: no business memberships and no client records.
    Refuses otherwise, so hand its businesses over first (`move_owner`)."""
    user = conn.execute(
        text("SELECT id FROM app.users WHERE lower(email) = lower(:e)"), {"e": email}
    ).scalar()
    if user is None:
        return {"app_users": 0, "auth_users": 0}
    held = conn.execute(
        text("""
            SELECT (SELECT count(*) FROM app.tenant_members WHERE user_id = :u)
                 + (SELECT count(*) FROM app.clients WHERE user_id = :u)
        """),
        {"u": user},
    ).scalar_one()
    if held:
        raise SystemExit(f"{email} still holds {held} memberships or client records: not removed.")
    auth = 0
    if conn.execute(text("SELECT to_regclass('auth.users') IS NOT NULL")).scalar():
        auth = conn.execute(text("DELETE FROM auth.users WHERE id = :u"), {"u": user}).rowcount
    remaining = conn.execute(text("DELETE FROM app.users WHERE id = :u"), {"u": user}).rowcount
    return {"app_users": remaining, "auth_users": auth}
