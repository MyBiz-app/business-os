"""What a demo business adds for its workspace: its registration number and a cover image, job
titles and reporting lines, branch opening hours and staff shifts around today.

Everything is synthetic: the registration number is a random number with a valid check digit,
the cover is a gradient drawn from the business's color, and people are the demo's own."""

import random
import struct
import zlib
from datetime import date, time, timedelta
from uuid import UUID

from sqlalchemy import Connection, text

from app.api.settings import israeli_number_valid
from app.schedule.scheduling import local_to_utc
from app.seed.common import TIME_ZONE

# Opening hours per category: weekday (0 = Monday) -> intervals; a day left out is closed.
# Sunday to Thursday are full days in Israel, Friday is short and Saturday mostly closed.
WEEKDAYS = (6, 0, 1, 2, 3)
OPENING_HOURS: dict[str, dict[int, tuple[tuple[str, str], ...]]] = {
    "food": {
        **{d: (("11:00", "23:30"),) for d in WEEKDAYS},
        4: (("11:00", "16:00"),),
        5: (("19:00", "23:30"),),
    },
    "fitness": {
        **{d: (("06:00", "23:00"),) for d in WEEKDAYS},
        4: (("06:00", "16:00"),),
        5: (("08:00", "14:00"),),
    },
    "beauty": {
        **{d: (("09:00", "13:30"), ("14:00", "20:00")) for d in WEEKDAYS},
        4: (("08:30", "14:00"),),
    },
}
DEFAULT_HOURS = {**{d: (("09:00", "19:00"),) for d in WEEKDAYS}, 4: (("09:00", "14:00"),)}

# Job titles (owner, branch manager, team) and the positions shifts are staffed for.
TITLES = {
    "food": ("בעלים", "מנהל/ת סניף", ("טבח/ית", "פיצאיולו", "קופה", "שליח/ה")),
    "fitness": ("בעלים", "מנהל/ת סניף", ("מאמן/ת", "מדריך/ת סטודיו", "קבלה")),
    "beauty": ("בעלים", "מנהל/ת סניף", ("סטייליסט/ית", "צבעי/ת", "קבלה")),
}
DEFAULT_TITLES = ("בעלים", "מנהל/ת צוות", ("איש/אשת צוות",))
MAX_SHIFT = timedelta(hours=9)


def seed_workspace(
    conn: Connection,
    tenant_id: UUID,
    owner: UUID,
    category: str,
    color: str,
    staff: dict[UUID, list[UUID]],
    today: date,
    rng: random.Random,
) -> int:
    """Adds the workspace details to a demo business; returns how many shifts it created."""
    conn.execute(
        text("""
            UPDATE app.tenants
            SET legal_entity_type = 'company', business_number = :number,
                cover = :cover, cover_content_type = 'image/png', cover_updated_at = now()
            WHERE id = :t
        """),
        {"t": tenant_id, "number": company_number(rng), "cover": cover_png(color)},
    )

    owner_title, manager_title, team_titles = TITLES.get(category, DEFAULT_TITLES)
    _member(conn, tenant_id, owner, owner_title, None)
    for team in staff.values():
        manager, *others = team
        _member(conn, tenant_id, manager, manager_title, owner)
        for index, person in enumerate(others):
            _member(conn, tenant_id, person, team_titles[index % len(team_titles)], manager)

    hours = OPENING_HOURS.get(category, DEFAULT_HOURS)
    conn.execute(
        text("""
            INSERT INTO app.location_hours (tenant_id, location_id, weekday, opens, closes)
            VALUES (:t, :l, :w, :opens, :closes)
        """),
        [
            {"t": tenant_id, "l": branch, "w": weekday, "opens": opens, "closes": closes}
            for branch in staff
            for weekday, intervals in hours.items()
            for opens, closes in intervals
        ],
    )

    # Shifts from two weeks back to three weeks ahead. Everyone works five of the open days
    # (two fixed days off each); a long day splits into a morning and an evening shift.
    rows = []
    first = today - timedelta(days=14)
    for branch, team in staff.items():
        days_off = {person: set(rng.sample(range(7), 2)) for person in team}
        positions = [None, *(team_titles[i % len(team_titles)] for i in range(len(team) - 1))]
        for offset in range(35):
            day = first + timedelta(days=offset)
            intervals = hours.get(day.weekday())
            if not intervals:
                continue
            opens = time.fromisoformat(intervals[0][0])
            closes = time.fromisoformat(intervals[-1][1])
            for index, person in enumerate(team):
                if day.weekday() in days_off[person]:
                    continue
                starts = local_to_utc(day, opens, TIME_ZONE)
                ends = local_to_utc(day, closes, TIME_ZONE)
                if ends - starts > MAX_SHIFT:
                    if (index + offset) % 2:
                        starts = ends - MAX_SHIFT
                    else:
                        ends = starts + MAX_SHIFT
                rows.append(
                    {
                        "t": tenant_id,
                        "l": branch,
                        "u": person,
                        "s": starts,
                        "e": ends,
                        "position": positions[index],
                    }
                )
    if rows:
        conn.execute(
            text("""
                INSERT INTO app.shifts (tenant_id, location_id, user_id, starts_at, ends_at,
                                        position, created_by)
                VALUES (:t, :l, :u, :s, :e, :position, NULL)
            """),
            rows,
        )
    return len(rows)


def _member(
    conn: Connection, tenant_id: UUID, user: UUID, title: str, manager: UUID | None
) -> None:
    conn.execute(
        text("""
            UPDATE app.tenant_members SET job_title = :title, reports_to = :manager
            WHERE tenant_id = :t AND user_id = :u
        """),
        {"t": tenant_id, "u": user, "title": title, "manager": manager},
    )


def company_number(rng: random.Random) -> str:
    """A made-up company number (starts with 51, like Israeli companies) with a valid check
    digit."""
    body = "51" + "".join(str(rng.randint(0, 9)) for _ in range(6))
    return next(body + str(d) for d in range(10) if israeli_number_valid(body + str(d)))


def cover_png(color: str, width: int = 1200, height: int = 320) -> bytes:
    """A wide cover: the business's color fading diagonally into a deep shade of it."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # no filter
        for x in range(width):
            shade = 1.1 - 0.75 * (x / width * 0.7 + y / height * 0.3)
            raw += bytes(min(255, int(c * shade)) for c in (r, g, b))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
