"""A demo: the businesses it creates for one owner."""

import random
from uuid import UUID

from sqlalchemy import Connection, text

from app.seed.business import seed
from app.seed.common import DEMOS, profile_id


def seed_demo(
    conn: Connection,
    owner_email: str,
    demo: str,
    months: int,
    rng: random.Random,
    owner_name: str | None = None,
    replace: bool = False,
) -> list[UUID]:
    """Creates a demo's businesses for one owner. With `replace`, the owner's earlier copies
    of these businesses (same names, owned by them) are removed first."""
    specs = DEMOS[demo]
    profile_id(conn, owner_email)  # the name below needs the profile
    if owner_name:
        conn.execute(
            text("UPDATE app.users SET full_name = :name WHERE lower(email) = lower(:email)"),
            {"name": owner_name, "email": owner_email},
        )
    if replace:
        conn.execute(
            text("""
                DELETE FROM app.tenants t
                WHERE t.name = ANY(:names) AND EXISTS (
                    SELECT 1 FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                    WHERE m.tenant_id = t.id AND m.role = 'owner'
                      AND lower(u.email) = lower(:email)
                )
            """),
            {"names": [spec.name for spec in specs], "email": owner_email},
        )
        # Demo staff profiles left without a business.
        conn.execute(
            text("""
                DELETE FROM app.users u
                WHERE u.email LIKE 'demo-coach-%@example.invalid'
                  AND NOT EXISTS (SELECT 1 FROM app.tenant_members m WHERE m.user_id = u.id)
            """)
        )
    return [seed(conn, owner_email, months, rng, spec) for spec in specs]
