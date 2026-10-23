"""Profile pictures for a demo account, the gym network's third branch and round-6 data.

Fills an owner's demo businesses with logos (business and branch), portraits for staff and
clients, and gives "Adir fitness" a crossfit branch next to its strength and pilates ones. It also
adds the round-6 pay terms, hours, payroll run and move (see `round6`). It only adds: a logo or a
portrait that is already set is kept, and nothing is deleted, so it is safe to run on an account
that has real activity. The images are drawn by
`scripts/generate_demo_images.py` (synthetic: no photos of real people).

    uv run python -m app.seed --owner-email you@example.com --demo profiles
"""

import json
from datetime import datetime
from functools import cache
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.seed.common import TIME_ZONE
from app.seed.guard import refuse_blocked_owner
from app.seed.round6 import seed_round6
from app.seed.round7 import seed_round7
from app.seed.workspace import OPENING_HOURS

ASSETS = Path(__file__).parent / "assets"
GYM_NETWORK = "Adir fitness"
CROSSFIT_BRANCH = ("חיפה - קרוספיט", "הנמל 12, חיפה")
CROSSFIT_COACHES = (("אורן", "שגיא"), ("שירן", "בן דוד"), ("גיא", "מזרחי"))
CLIENTS_WITH_PORTRAIT = 100_000  # clients who get a demo sign-in profile to hold a portrait
FULL_AI_SET = 400  # AI portraits per gender that are enough for every client
BUSIEST_CLIENTS = 12  # per business: the busiest clients get an AI portrait
NO_PHOTO_ONE_IN = 10  # clients left without a picture on purpose, as in real life

FEMALE = {
    "נועה", "מאיה", "תמר", "יעל", "שירה", "אביגיל", "מיכל", "ליה", "הדר", "אלה", "נטע", "גלי",
    "דנה", "רותם", "שני", "ענבל", "קרן", "ליאת", "סיון", "הילה", "מורן", "שירן", "רונה", "נועם",
}  # fmt: skip
MALE = {
    "איתי", "יונתן", "עומר", "אריאל", "דניאל", "נדב", "גיא", "עידו", "אסף", "רועי", "אורן",
    "ליאור", "רון", "יוסי",
}  # fmt: skip


def _manifest() -> dict:
    return json.loads((ASSETS / "manifest.json").read_text())


def _read(name: str) -> bytes:
    return (ASSETS / name).read_bytes()


def _is_female(full_name: str | None, key: str) -> bool:
    first = (full_name or "").replace("ד״ר", "").split()[0] if full_name else ""
    if first in FEMALE:
        return True
    if first in MALE:
        return False
    return sum(key.encode()) % 2 == 0  # unknown or neutral name: a stable pick


@cache
def _pool(kind: str, gender: str) -> tuple[Path, ...]:
    """The AI-drawn portraits ("ai", a few dozen) or the illustrated avatars ("illustrated")."""
    return tuple(sorted((ASSETS / "portraits" / kind).glob(f"{gender}*.jpg")))


def _portrait(
    manifest: dict, full_name: str | None, user_id: UUID, *, most_active: bool = True
) -> bytes:
    """AI portraits go to the team and the busiest clients, illustrations to everyone else."""
    gender = "f" if _is_female(full_name, str(user_id)) else "m"
    ai = _pool("ai", gender)
    # With only a few dozen AI portraits they go to the busiest; a full set goes to everyone.
    pool = ai if most_active or len(ai) >= FULL_AI_SET else _pool("illustrated", gender)
    if pool:
        return pool[user_id.int % len(pool)].read_bytes()
    pool = manifest["portraits"][gender]
    return _read(pool[user_id.int % len(pool)])


def _set_avatar(
    conn: Connection,
    manifest: dict,
    user_id: UUID,
    full_name: str | None,
    *,
    most_active: bool = True,
) -> None:
    conn.execute(
        text("""
            UPDATE app.users
            SET avatar = :data, avatar_content_type = 'image/jpeg',
                avatar_updated_at = now(), updated_at = now()
            WHERE id = :id AND avatar IS NULL
        """),
        {
            "id": user_id,
            "data": _portrait(manifest, full_name, user_id, most_active=most_active),
        },
    )


def _add_crossfit_branch(conn: Connection, tenant_id: UUID) -> UUID | None:
    """The third branch of the gym network: crossfit, with its own hours, rooms and coaches."""
    exists = conn.execute(
        text("SELECT 1 FROM app.locations WHERE tenant_id = :t AND kind = 'crossfit'"),
        {"t": tenant_id},
    ).first()
    if exists:
        return None
    name, address = CROSSFIT_BRANCH
    location = conn.execute(
        text("""
            INSERT INTO app.locations (tenant_id, name, address, kind, created_at)
            VALUES (:t, :name, :address, 'crossfit', clock_timestamp()) RETURNING id
        """),
        {"t": tenant_id, "name": name, "address": address},
    ).scalar_one()
    conn.execute(
        text("""
            INSERT INTO app.location_hours (tenant_id, location_id, weekday, opens, closes)
            VALUES (:t, :l, :w, :opens, :closes)
        """),
        [
            {"t": tenant_id, "l": location, "w": weekday, "opens": opens, "closes": closes}
            for weekday, intervals in OPENING_HOURS["fitness"].items()
            for opens, closes in intervals
        ],
    )
    for order, station in enumerate(("בוקס ראשי", "אזור הרמות", "חצר חיצונית")):
        conn.execute(
            text("""
                INSERT INTO app.stations (tenant_id, location_id, name, sort_order)
                VALUES (:t, :l, :name, :order)
            """),
            {"t": tenant_id, "l": location, "name": station, "order": order},
        )
    for index, (first, last) in enumerate(CROSSFIT_COACHES):
        user_id = uuid4()
        conn.execute(
            text("INSERT INTO app.users (id, email, full_name) VALUES (:id, :email, :name)"),
            {
                "id": user_id,
                "email": f"demo-coach-{user_id.hex[:8]}@example.invalid",
                "name": f"{first} {last}",
            },
        )
        conn.execute(
            text("""
                INSERT INTO app.tenant_members
                    (tenant_id, user_id, role, location_ids, home_location_id, job_title)
                VALUES (:t, :u, 'staff', :branches, :l, :title)
            """),
            {
                "t": tenant_id,
                "u": user_id,
                "branches": [location],
                "l": location,
                "title": "מנהל/ת סניף" if index == 0 else "מאמן/ת",
            },
        )
    return location


def enrich_profiles(conn: Connection, owner_email: str) -> dict[str, int]:
    """Adds logos and portraits (and the crossfit branch) to the owner's businesses."""
    refuse_blocked_owner(owner_email)
    manifest = _manifest()
    counts = {
        "businesses": 0,
        "branches": 0,
        "staff": 0,
        "clients": 0,
        "new_branches": 0,
        "pay_setups": 0,
        "payroll_runs": 0,
        "move_sessions": 0,
        "round7": 0,
    }
    today = datetime.now(ZoneInfo(TIME_ZONE)).date()
    tenants = conn.execute(
        text("""
            SELECT t.id, t.name FROM app.tenants t
            JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
            JOIN app.users u ON u.id = m.user_id
            WHERE lower(u.email) = lower(:email) ORDER BY t.created_at
        """),
        {"email": owner_email},
    ).all()
    for tenant_id, tenant_name in tenants:
        if tenant_name == GYM_NETWORK and _add_crossfit_branch(conn, tenant_id):
            counts["new_branches"] += 1

        entry = manifest["tenants"].get(tenant_name)
        if entry:
            result = conn.execute(
                text("""
                    UPDATE app.tenants
                    SET logo = :logo, logo_content_type = 'image/png', logo_updated_at = now(),
                        primary_color = coalesce(primary_color, :color)
                    WHERE id = :t AND logo IS NULL
                """),
                {"t": tenant_id, "logo": _read(entry["file"]), "color": entry["color"]},
            )
            counts["businesses"] += result.rowcount

        for location_id, name, kind in conn.execute(
            text("SELECT id, name, kind FROM app.locations WHERE tenant_id = :t"), {"t": tenant_id}
        ).all():
            branch = manifest["branches"].get(f"{tenant_name}/{name}") or manifest["branches"].get(
                f"kind:{kind}"
            )
            if branch:
                result = conn.execute(
                    text("""
                        UPDATE app.locations
                        SET logo = :logo, logo_content_type = 'image/png',
                            logo_updated_at = now(),
                            primary_color = coalesce(primary_color, :color)
                        WHERE id = :l AND logo IS NULL
                    """),
                    {"l": location_id, "logo": _read(branch["file"]), "color": branch["color"]},
                )
                counts["branches"] += result.rowcount

        # Everyone on the team: the owner, branch managers and staff.
        for user_id, full_name in conn.execute(
            text("""
                SELECT u.id, u.full_name FROM app.tenant_members m
                JOIN app.users u ON u.id = m.user_id
                WHERE m.tenant_id = :t AND u.avatar IS NULL
            """),
            {"t": tenant_id},
        ).all():
            _set_avatar(conn, manifest, user_id, full_name)
            counts["staff"] += 1

        # Clients get a sign-in profile (a demo one that cannot be used to sign in) so their
        # portrait has a place to live: the client's picture is their profile's.
        linked = conn.execute(
            text("""
                SELECT count(*) FROM app.clients c JOIN app.users u ON u.id = c.user_id
                WHERE c.tenant_id = :t AND u.email LIKE 'demo-client-%@example.invalid'
            """),
            {"t": tenant_id},
        ).scalar_one()
        clients = conn.execute(
            text("""
                SELECT c.id, c.first_name, c.last_name,
                       (SELECT count(*) FROM app.bookings b
                        WHERE b.tenant_id = c.tenant_id AND b.client_id = c.id) AS visits
                FROM app.clients c
                WHERE c.tenant_id = :t AND c.user_id IS NULL AND c.status = 'active'
                  AND c.email IS NOT NULL AND c.email LIKE '%@example.invalid'
                ORDER BY visits DESC, c.created_at LIMIT :n
            """),
            {"t": tenant_id, "n": max(0, CLIENTS_WITH_PORTRAIT - linked)},
        ).all()
        for rank, (client_id, first, last, _visits) in enumerate(clients):
            if client_id.int % NO_PHOTO_ONE_IN == 0:
                continue
            user_id = uuid4()
            full_name = f"{first} {last or ''}".strip()
            conn.execute(
                text("INSERT INTO app.users (id, email, full_name) VALUES (:id, :email, :name)"),
                {
                    "id": user_id,
                    "email": f"demo-client-{user_id.hex[:10]}@example.invalid",
                    "name": full_name,
                },
            )
            _set_avatar(conn, manifest, user_id, full_name, most_active=rank < BUSIEST_CLIENTS)
            conn.execute(
                text("UPDATE app.clients SET user_id = :u WHERE id = :c"),
                {"u": user_id, "c": client_id},
            )
            counts["clients"] += 1

        # Round 6: pay terms, approved hours, a payroll run and (the gym) a move in progress.
        added = seed_round6(conn, tenant_id, tenant_name, today)
        for key in ("pay_setups", "payroll_runs", "move_sessions"):
            counts[key] += added[key]

        # Round 7: quotes, documents, AI chats, announcements, planning, a website and more.
        counts["round7"] += sum(seed_round7(conn, tenant_id, tenant_name, today).values())
    return counts
