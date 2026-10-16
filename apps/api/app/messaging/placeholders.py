"""Variables in message texts: `{first_name}`, `{plan_name|dear member}` and the rest.

One function, `render_placeholders`, fills them for every channel (WhatsApp, SMS, email, push,
pop-up, the lead follow-up). The text a business writes may name any variable in `GROUPS`; a
variable followed by `|` carries the value to use when the person has none. Braces that name
nothing known are left as typed.

The full ID number is never a variable: messages leave through WhatsApp, SMS and email, so only
the last four digits (`{id_last4}`) can be used."""

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.config import get_settings

# The groups the editor lists, in order.
GROUPS: dict[str, tuple[str, ...]] = {
    "client": (
        "first_name",
        "last_name",
        "full_name",
        "phone",
        "email",
        "birthday",
        "id_last4",
    ),
    "plan": ("plan_name", "plan_expires", "sessions_left"),
    "booking": ("next_booking", "next_service", "staff_name"),
    "business": (
        "business",
        "branch",
        "branch_address",
        "app_link",
        "join_code",
        "booking_link",
    ),
}
KNOWN = frozenset(name for names in GROUPS.values() for name in names)

# A made-up client for the editor's live preview (shown in the person's own language by the web).
SAMPLE: dict[str, str] = {
    "first_name": "Dana",
    "last_name": "Levi",
    "full_name": "Dana Levi",
    "phone": "050-1234567",
    "email": "dana@example.com",
    "birthday": "14/03/1990",
    "id_last4": "4821",
    "plan_name": "Monthly membership",
    "plan_expires": "30/11/2026",
    "sessions_left": "6",
    "next_booking": "21/10/2026 18:00",
    "next_service": "Pilates",
    "staff_name": "Maya",
    "branch": "Main branch",
    "branch_address": "1 Herzl St, Tel Aviv",
}

_TOKEN = re.compile(r"\{([a-z0-9_]+)(?:\|([^{}]*))?\}")
_DATE = "%d/%m/%Y"
_LIVE_BOOKING = ("booked", "checked_in", "no_show")


def used_variables(body: str) -> dict[str, bool]:
    """The known variables a text uses, each with whether it carries a fallback value."""
    found: dict[str, bool] = {}
    for name, fallback in _TOKEN.findall(body):
        if name in KNOWN:
            found[name] = found.get(name, True) and bool(fallback)
    return found


def render_placeholders(body: str, values: Mapping[str, str | None]) -> str:
    """Fills the variables of `body`. A variable the person has no value for becomes its fallback
    (`{name|fallback}`), or nothing; unknown braces stay as typed."""

    def fill(match: re.Match[str]) -> str:
        name, fallback = match.group(1), match.group(2)
        if name not in KNOWN:
            return match.group(0)
        value = (values.get(name) or "").strip()
        return value or (fallback or "").strip()

    return _TOKEN.sub(fill, body)


def missing_counts(body: str, people: Iterable[Mapping[str, str | None]]) -> dict[str, int]:
    """For each used variable without a fallback: how many people have no value for it."""
    needed = [name for name, has_fallback in used_variables(body).items() if not has_fallback]
    counts = dict.fromkeys(needed, 0)
    for person in people:
        for name in needed:
            if not (person.get(name) or "").strip():
                counts[name] += 1
    return {name: n for name, n in counts.items() if n}


def person_values(row: Mapping[str, Any], business: str, tz: str = "UTC") -> dict[str, str]:
    """The values for one person from a database row (see `client_values`)."""
    settings = get_settings()
    first = (row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    app_link = settings.client_app_url.rstrip("/")
    values: dict[str, str | None] = {
        "first_name": first,
        "last_name": last,
        "full_name": f"{first} {last}".strip(),
        "phone": row.get("phone"),
        "email": row.get("email"),
        "id_last4": row.get("id_last4"),
        "business": business,
        "branch": row.get("branch"),
        "branch_address": row.get("branch_address"),
        "plan_name": row.get("plan_name"),
        "next_service": row.get("next_service"),
        "staff_name": row.get("staff_name"),
        "join_code": row.get("join_code"),
        "app_link": app_link,
        "booking_link": f"{app_link}/reserve" if row.get("client_id") else None,
    }
    born: date | None = row.get("date_of_birth")
    values["birthday"] = born.strftime(_DATE) if born else None
    ends: date | None = row.get("plan_expires")
    values["plan_expires"] = ends.strftime(_DATE) if ends else None
    left = row.get("sessions_left")
    values["sessions_left"] = str(left) if left is not None else None
    starts: datetime | None = row.get("next_booking")
    values["next_booking"] = (
        starts.astimezone(ZoneInfo(tz)).strftime(f"{_DATE} %H:%M") if starts else None
    )
    return {k: (v or "") for k, v in values.items()}


def client_values(
    db: Session | Connection, tenant_id: UUID, client_ids: list[UUID], business: str
) -> dict[UUID, dict[str, str]]:
    """The values of each client, in one query. Filters by tenant itself, so it works for a
    request (row security) and for the background job alike."""
    if not client_ids:
        return {}
    rows = (
        db.execute(
            text("""
                SELECT c.id AS client_id, c.first_name, c.last_name, c.phone,
                       lower(c.email) AS email, c.date_of_birth, i.id_last4,
                       t.join_code, t.time_zone AS tz,
                       l.name AS branch, l.address AS branch_address,
                       e.name AS plan_name, e.ends_on AS plan_expires,
                       CASE WHEN e.kind = 'punch_card'
                            THEN greatest(e.credits - (
                                SELECT count(*) FROM app.bookings u
                                WHERE u.entitlement_id = e.id AND u.status = ANY(:live)), 0)
                       END AS sessions_left,
                       nb.starts_at AS next_booking, nb.service AS next_service,
                       nb.staff AS staff_name
                FROM app.clients c
                JOIN app.tenants t ON t.id = c.tenant_id
                LEFT JOIN app.person_identities i
                       ON i.client_id = c.id AND i.tenant_id = c.tenant_id
                LEFT JOIN app.locations l
                       ON l.id = c.home_location_id AND l.tenant_id = c.tenant_id
                LEFT JOIN LATERAL (
                    SELECT p.name, p.ends_on, p.kind, p.credits, p.id
                    FROM app.entitlements p
                    WHERE p.tenant_id = c.tenant_id AND p.client_id = c.id
                      AND p.status = 'active'
                      AND p.ends_on >= (now() AT TIME ZONE t.time_zone)::date
                    ORDER BY p.ends_on DESC LIMIT 1
                ) e(name, ends_on, kind, credits, id) ON true
                LEFT JOIN LATERAL (
                    SELECT s.starts_at, sv.name AS service,
                           nullif(trim(coalesce(u.full_name, '')), '') AS staff
                    FROM app.bookings b
                    JOIN app.sessions s ON s.id = b.session_id AND s.tenant_id = b.tenant_id
                    JOIN app.services sv ON sv.id = s.service_id AND sv.tenant_id = s.tenant_id
                    LEFT JOIN app.users u ON u.id = s.instructor_user_id
                    WHERE b.tenant_id = c.tenant_id AND b.client_id = c.id
                      AND b.status = 'booked' AND s.status = 'scheduled' AND s.starts_at > now()
                    ORDER BY s.starts_at LIMIT 1
                ) nb ON true
                WHERE c.tenant_id = :t AND c.id = ANY(CAST(:ids AS uuid[]))
            """),
            {"t": tenant_id, "ids": client_ids, "live": list(_LIVE_BOOKING)},
        )
        .mappings()
        .all()
    )
    return {r["client_id"]: person_values(r, business, r["tz"]) for r in rows}


def lead_values(row: Mapping[str, Any], business: str) -> dict[str, str]:
    """A lead has a name, a phone and an email; the rest stays empty."""
    return person_values({**row, "client_id": None}, business)
