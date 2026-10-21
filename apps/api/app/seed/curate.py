"""Tidies an owner's demo account down to the curated set of businesses.

    uv run python -m app.seed --owner-email you@example.com --demo curated

The account ends with exactly the businesses of the `curated` demo: the gym "Adir fitness"
(branches of different kinds in one business: strength, pilates and crossfit) and two others.
An earlier "Iron & Flow" is renamed to "Adir fitness" in place; any other business this
account solely owns is removed (with its demo staff and clients); a missing one is created.
Logos and portraits are then filled in. Only businesses the account owns alone are touched,
never anyone else's.
"""

import random
import sys

from sqlalchemy import Connection, text

from app.geo.backfill import locate_branches
from app.seed.business import seed
from app.seed.common import DEMOS, profile_id
from app.seed.guard import refuse_blocked_owner
from app.seed.profiles import enrich_profiles
from app.seed.residence import place_residents

RENAMES = {"Iron & Flow": "Adir fitness"}
# Branches that moved to other cities so the demo map has branches across the country
# (business, old branch name) -> (new name, new address).
BRANCH_MOVES = {
    ("Urban Slice", "רמת גן - מרום נווה"): ("ירושלים - מחנה יהודה", "אגריפס 42, ירושלים"),
    ("Urban Slice", "חולון - קריית שרת"): ("באר שבע - העיר החדשה", "רגר 12, באר שבע"),
    ("Studio Bloom", "מודיעין"): ("אשדוד - הרובע", "הרצל 22, אשדוד"),
}


def _owned(conn: Connection, user: object) -> list[tuple[object, str]]:
    """The businesses this person is the only owner of."""
    return list(
        conn.execute(
            text("""
                SELECT t.id, t.name FROM app.tenants t
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                WHERE m.user_id = :u AND NOT EXISTS (
                    SELECT 1 FROM app.tenant_members o
                    WHERE o.tenant_id = t.id AND o.role = 'owner' AND o.user_id <> :u
                )
                ORDER BY t.created_at
            """),
            {"u": user},
        ).all()
    )


def move_branches(conn: Connection, owner_email: str) -> int:
    """Applies `BRANCH_MOVES` to the owner's businesses: the branch takes its new name and
    address and loses its old point (and city), so the next locating run places it again."""
    owner = profile_id(conn, owner_email)
    moved = 0
    for (business, old), (name, address) in BRANCH_MOVES.items():
        moved += conn.execute(
            text("""
                UPDATE app.locations l SET
                    name = :name, address = :address, city_code = NULL, street_code = NULL,
                    house_number = NULL, street_unlisted = NULL, address_details = NULL,
                    latitude = NULL, longitude = NULL, geocoded_at = NULL
                FROM app.tenants t
                WHERE l.tenant_id = t.id AND t.name = :business AND l.name = :old
                  AND EXISTS (SELECT 1 FROM app.tenant_members m
                              WHERE m.tenant_id = t.id AND m.role = 'owner' AND m.user_id = :owner)
            """),
            {"business": business, "old": old, "name": name, "address": address, "owner": owner},
        ).rowcount
    return moved


def place_branches(conn: Connection, owner_email: str) -> dict[str, int]:
    """Moves the demo branches that changed city, then gives every branch without a point its
    place on the map (one request a second to the map service)."""
    refuse_blocked_owner(owner_email)
    moved = move_branches(conn, owner_email)
    return {"moved": moved, **locate_branches(conn, pause=1.1)}


def curate(
    conn: Connection, owner_email: str, months: int, rng: random.Random
) -> dict[str, object]:
    refuse_blocked_owner(owner_email)
    owner = profile_id(conn, owner_email)
    if owner is None:
        sys.exit(f"No account for {owner_email}: sign up on the site first, then run again.")
    specs = DEMOS["curated"]
    keep = {spec.name for spec in specs}

    owned = _owned(conn, owner)
    names = {name for _, name in owned}
    for old, new in RENAMES.items():
        if old in names and new not in names:
            conn.execute(
                text("""
                    UPDATE app.tenants SET name = :new, logo = NULL, logo_content_type = NULL,
                                           logo_updated_at = NULL, updated_at = now()
                    WHERE id = ANY(:ids) AND name = :old
                """),
                {"new": new, "old": old, "ids": [i for i, n in owned if n == old]},
            )
    owned = _owned(conn, owner)

    # Keep the oldest copy of each wanted business, remove everything else.
    first: dict[str, object] = {}
    remove = []
    for tenant_id, name in owned:
        if name in keep and name not in first:
            first[name] = tenant_id
        else:
            remove.append(tenant_id)
    if remove:
        conn.execute(text("DELETE FROM app.tenants WHERE id = ANY(:ids)"), {"ids": remove})
        # Demo people left without a business.
        conn.execute(
            text("""
                DELETE FROM app.users u
                WHERE (u.email LIKE 'demo-coach-%@example.invalid'
                       OR u.email LIKE 'demo-client-%@example.invalid')
                  AND NOT EXISTS (SELECT 1 FROM app.tenant_members m WHERE m.user_id = u.id)
                  AND NOT EXISTS (SELECT 1 FROM app.clients c WHERE c.user_id = u.id)
            """)
        )
    created = [
        seed(conn, owner_email, months, rng, spec) for spec in specs if spec.name not in first
    ]
    result = enrich_profiles(conn, owner_email)
    places = place_branches(conn, owner_email)
    residents = place_residents(conn, [tenant for tenant, _ in _owned(conn, owner)])
    return {
        "removed": len(remove),
        "created": len(created),
        "kept": sorted(first),
        **result,
        "places": places,
        "residents": residents,
    }
