"""Demo data: businesses with branches and months of realistic history, for any industry.

    uv run python -m app.seed --owner-email you@example.com [--demo studio|owner]
        [--owner-name "..."] [--replace] [--months 3] [--seed 7]

The owner must have signed up once (so their profile exists). The script creates businesses
owned by them, each with branches, services and plans from its industry (or its own), staff
per branch, a weekly timetable for classes and booked appointments, clients with a home branch,
plans sold over time (simulated payments) and bookings with attendance, no-shows, late
cancellations and waitlists. Staff are demo profiles that cannot sign in.

It writes with the migration (owner) connection, so it is for local and staging use only.
Everything is generated from --seed, so the same arguments produce the same studio.
"""

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, create_engine, text

from app.api.modules import set_modules
from app.api.routes import apply_vertical_pack
from app.billing import bill_businesses
from app.core.config import get_settings
from app.health import FITNESS_FORM
from app.modules import PRESETS
from app.scheduling import local_to_utc
from app.verticals import VERTICAL_PACKS

TIME_ZONE = "Asia/Jerusalem"

SOURCES = ("walk_in", "referral", "instagram", "facebook", "google", "website")
SOURCE_WEIGHTS = (3, 4, 5, 2, 2, 1)
CLIENTS = 170
LEADS = 15  # the newest clients: interested, never bought

FIRST_NAMES = [
    "נועה",
    "מאיה",
    "תמר",
    "יעל",
    "שירה",
    "אביגיל",
    "רוני",
    "מיכל",
    "ליה",
    "הדר",
    "אלה",
    "עדי",
    "נטע",
    "גלי",
    "דנה",
    "אורי",
    "טל",
    "רותם",
    "שני",
    "ענבל",
    "קרן",
    "ליאת",
    "סיון",
    "הילה",
    "מורן",
    "איתי",
    "יונתן",
    "עומר",
    "אריאל",
    "דניאל",
    "נדב",
    "גיא",
    "עידו",
    "אסף",
    "רועי",
]
LAST_NAMES = [
    "כהן",
    "לוי",
    "מזרחי",
    "פרץ",
    "ביטון",
    "אברהם",
    "פרידמן",
    "אזולאי",
    "דהן",
    "אוחיון",
    "חדד",
    "גבאי",
    "שפירא",
    "קליין",
    "רוזן",
    "אשכנזי",
    "גולן",
    "ברק",
    "שלום",
    "יוסף",
]

# (name he, name en, minutes, capacity, color, popularity 0..1)
SERVICES = (
    ("פילאטיס מזרן", "Mat Pilates", 55, 12, "#6366f1", 0.85),
    ("פילאטיס מכשירים", "Reformer Pilates", 50, 6, "#ec4899", 0.95),
    ("יוגה פלואו", "Yoga Flow", 60, 15, "#10b981", 0.7),
    ("HIIT", "HIIT", 45, 14, "#f59e0b", 0.65),
    ("בר", "Barre", 50, 12, "#8b5cf6", 0.6),
)
INSTRUCTORS = (("מאיה", "רז"), ("אורן", "שגיא"), ("ליאור", "נחום"), ("שירן", "בן דוד"))

# Weekly timetable: (weekday 0=Mon..6=Sun, "HH:MM", service index, room index, instructor index)
TIMETABLE = (
    (6, "07:00", 0, 0, 0), (6, "09:00", 2, 0, 2), (6, "18:00", 1, 1, 1), (6, "19:15", 3, 0, 3),
    (0, "07:00", 1, 1, 1), (0, "08:30", 4, 0, 0), (0, "18:30", 0, 0, 2), (0, "19:30", 1, 1, 1),
    (1, "07:00", 3, 0, 3), (1, "09:30", 2, 0, 2), (1, "18:00", 1, 1, 0), (1, "19:15", 4, 0, 0),
    (2, "07:00", 0, 0, 0), (2, "12:00", 2, 0, 2), (2, "18:00", 1, 1, 1), (2, "19:15", 3, 0, 3),
    (3, "07:00", 1, 1, 1), (3, "09:00", 4, 0, 0), (3, "18:30", 0, 0, 2), (3, "19:30", 2, 0, 2),
    (4, "08:00", 1, 1, 1), (4, "09:30", 0, 0, 0), (4, "11:00", 2, 0, 2),
    (5, "09:00", 3, 0, 3), (5, "10:30", 2, 0, 2),
)  # fmt: skip


@dataclass
class Entitlement:
    id: UUID
    kind: str
    starts_on: date
    ends_on: date
    credits: int | None
    used: int = 0

    def usable(self, day: date) -> bool:
        has_credit = self.credits is None or self.used < self.credits
        return self.starts_on <= day <= self.ends_on and has_credit


@dataclass
class Client:
    id: UUID
    joined: date
    churns_on: date | None
    habit: float  # chance to book any fitting class
    favorite_hours: set[int]
    entitlements: list[Entitlement] = field(default_factory=list)

    def plan_on(self, day: date) -> Entitlement | None:
        usable = [e for e in self.entitlements if e.usable(day)]
        usable.sort(key=lambda e: (e.credits is not None, e.ends_on))
        return usable[0] if usable else None


def _insert(conn: Connection, sql: str, rows: list[dict]) -> None:
    if rows:
        conn.execute(text(sql), rows)


@dataclass(frozen=True)
class BranchSpec:
    name: str
    address: str


@dataclass(frozen=True)
class BusinessSpec:
    """One demo business: its industry (a catalog key), branches and size. Services, plans and
    client details come from the industry catalog unless the spec brings its own."""

    name: str
    vertical: str
    color: str
    billing_name: str
    branches: tuple[BranchSpec, ...]
    clients: int = CLIENTS
    staff_per_branch: int = 2
    # The classic studio keeps its hand-made services and timetable (tests rely on it).
    custom_services: tuple[tuple[str, str, int, int, str, float], ...] | None = None
    timetable: tuple[tuple[int, str, int, int, int], ...] | None = None


STUDIO = BusinessSpec(
    name="סטודיו פלואו (דמו)",
    vertical="fitness",
    color="#0f766e",
    billing_name="סטודיו פלואו בע״מ",
    branches=(BranchSpec("תל אביב - פלורנטין", "הרצל 120, תל אביב"),),
    staff_per_branch=len(INSTRUCTORS),
    custom_services=SERVICES,
    timetable=TIMETABLE,
)

# The owner's demo (decision T78): a chain with five branches and a barbershop with three.
PILATES_CHAIN = BusinessSpec(
    name="פילאטיס פלוס",
    vertical="pilates",
    color="#7c3aed",
    billing_name="פילאטיס פלוס בע״מ",
    branches=(
        BranchSpec("תל אביב - רוטשילד", "שדרות רוטשילד 45, תל אביב"),
        BranchSpec("רמת גן - הבורסה", "ז׳בוטינסקי 7, רמת גן"),
        BranchSpec("הרצליה פיתוח", "אבא אבן 10, הרצליה"),
        BranchSpec("ירושלים - המושבה הגרמנית", "עמק רפאים 30, ירושלים"),
        BranchSpec("חיפה - כרמל", "שדרות הנשיא 120, חיפה"),
    ),
    clients=420,
    staff_per_branch=3,
)
BARBERSHOP = BusinessSpec(
    name="בלייד ברברס",
    vertical="barbershop",
    color="#b45309",
    billing_name="בלייד ברברס בע״מ",
    branches=(
        BranchSpec("תל אביב - דיזנגוף", "דיזנגוף 200, תל אביב"),
        BranchSpec("גבעתיים", "כצנלסון 60, גבעתיים"),
        BranchSpec("ראשון לציון", "רוטשילד 30, ראשון לציון"),
    ),
    clients=300,
    staff_per_branch=3,
)
DEMOS: dict[str, tuple[BusinessSpec, ...]] = {
    "studio": (STUDIO,),
    "owner": (PILATES_CHAIN, BARBERSHOP),
    "platform": (),  # MyBiz's own view: many small businesses (PLATFORM_BUSINESSES)
}

# The platform demo: small businesses of several industries, each with a fictitious owner, so
# the MyBiz console has businesses, invoices and requests to show.
PLATFORM_BUSINESSES: tuple[tuple[BusinessSpec, str], ...] = tuple(
    (
        BusinessSpec(
            name=name,
            vertical=vertical,
            color=color,
            billing_name=f"{name} בע״מ",
            branches=(BranchSpec(branch, address),),
            clients=clients,
            staff_per_branch=2,
        ),
        owner,
    )
    for name, vertical, color, branch, address, clients, owner in (
        ("יוגה בגבעה", "yoga", "#059669", "זכרון יעקב", "המייסדים 40, זכרון יעקב", 90, "מיכל לוי"),
        (
            "קרוספיט צפון",
            "crossfit",
            "#dc2626",
            "קריית ביאליק",
            "דרך עכו 210, קריית ביאליק",
            120,
            "רון אברהם",
        ),
        (
            "פיזיו פלוס",
            "physiotherapy",
            "#0284c7",
            "פתח תקווה",
            "ז׳בוטינסקי 100, פתח תקווה",
            70,
            "ד״ר נועה שגיא",
        ),
        ("סטודיו מחול רונה", "dance", "#db2777", "רחובות", "הרצל 150, רחובות", 110, "רונה כהן"),
        ("מספרת הדר", "hair_salon", "#a16207", "באר שבע", "רגר 30, באר שבע", 80, "הדר מזרחי"),
        ("מוסך המומחים", "garage", "#475569", "חולון", "המלאכה 12, חולון", 60, "יוסי ביטון"),
    )
)
PLATFORM_REQUESTS = (
    (
        "שירה גולן",
        "shira@example.invalid",
        "סטודיו שירה",
        "pilates",
        "מעוניינת להעביר את הסטודיו מהמערכת הקודמת, אפשר עזרה בייבוא לקוחות?",
        "new",
    ),
    (
        "עמית ברק",
        "amit@example.invalid",
        "ברק כושר",
        "gym",
        "יש לנו שלושה סניפים, כמה עולה סניף נוסף?",
        "new",
    ),
    (
        "ליאת חן",
        "liat@example.invalid",
        "קליניקת ליאת",
        "aesthetics",
        "רוצה לשמוע על אפליקציית הלקוחות עם הלוגו שלנו",
        "in_progress",
    ),
    (
        "דני פרץ",
        "dani@example.invalid",
        "פרץ גראז׳",
        "garage",
        "שאלה על חשבוניות ללקוחות עסקיים",
        "done",
    ),
)

# Staff hours for appointments: weekday (0 = Monday) -> (opens, closes); Friday until 14:00.
WORK_HOURS = {6: (9, 19), 0: (9, 19), 1: (9, 19), 2: (9, 19), 3: (9, 19), 4: (9, 14)}
CLASS_HOURS = ("07:00", "08:30", "09:30", "12:00", "17:30", "18:30", "19:30", "20:30")
GENERIC_NOTES = (
    "מרוצה מאוד מהתוצאה",
    "ביקש/ה תור קבוע כל חודש",
    "מעדיף/ה שעות בוקר",
    "להזכיר יום לפני התור הבא",
    "הגיע/ה עם חבר/ה, אולי לקוח/ה חדש/ה",
)
GENERIC_REVIEWS = {
    5: ("שירות מעולה!", "מקצועיים ונעימים", "בדיוק מה שרציתי"),
    4: ("טוב מאוד, חיכיתי קצת", "נהניתי", "אחלה אווירה"),
    3: ("היה בסדר", "קצת יקר"),
    2: ("התחיל באיחור", "לא בדיוק מה שביקשתי"),
    1: ("התור בוטל ברגע האחרון",),
}


def profile_id(conn: Connection, email: str) -> UUID | None:
    """The person's profile; created from their sign-up (Supabase auth) when they have not
    used the app yet, e.g. when they could not log in before their email was confirmed."""
    if conn.execute(text("SELECT to_regclass('auth.users') IS NOT NULL")).scalar():
        conn.execute(
            text("""
                INSERT INTO app.users (id, email)
                SELECT id, lower(email) FROM auth.users WHERE lower(email) = lower(:email)
                ON CONFLICT DO NOTHING
            """),
            {"email": email},
        )
    return conn.execute(
        text("SELECT id FROM app.users WHERE lower(email) = lower(:email)"), {"email": email}
    ).scalar()


def seed(
    conn: Connection,
    owner_email: str,
    months: int,
    rng: random.Random,
    spec: BusinessSpec = STUDIO,
) -> UUID:
    """Creates one demo business owned by `owner_email` and returns its id."""
    owner = profile_id(conn, owner_email)
    if owner is None:
        sys.exit(f"No account for {owner_email}: sign up on the site first, then run again.")
    pack = VERTICAL_PACKS[spec.vertical]
    category = pack.category

    today = datetime.now(ZoneInfo(TIME_ZONE)).date()
    start = today - timedelta(days=30 * months)
    horizon = today + timedelta(days=28)

    tenant_id = conn.execute(
        text("""
            INSERT INTO app.tenants (name, vertical, locale, time_zone, currency, primary_color,
                                     created_at, trial_ends_at)
            VALUES (:name, :vertical, 'he', :tz, 'ILS', :color, :created,
                    CAST(:created AS timestamptz) + interval '14 days')
            RETURNING id
        """),
        {
            "name": spec.name,
            "vertical": spec.vertical,
            "color": spec.color,
            "tz": TIME_ZONE,
            "created": local_to_utc(start - timedelta(days=90), time(9), TIME_ZONE),
        },
    ).scalar_one()
    conn.execute(
        text("INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'owner')"),
        {"t": tenant_id, "u": owner},
    )
    apply_vertical_pack(conn, tenant_id, spec.vertical, "he", "ILS")
    # Show everything: the richest preset plus the CRM and messaging.
    modules = {**dict.fromkeys(PRESETS["ai_powered"], 1), "crm": 1, "whatsapp": 1}
    set_modules(conn, tenant_id, modules)

    # Branches (the extra-branch charge follows them), each with rooms for classes.
    branches: list[UUID] = []
    for branch in spec.branches:
        branches.append(
            conn.execute(
                text("""
                    INSERT INTO app.locations (tenant_id, name, address, created_at)
                    VALUES (:t, :name, :address, clock_timestamp()) RETURNING id
                """),
                {"t": tenant_id, "name": branch.name, "address": branch.address},
            ).scalar_one()
        )

    # Services: the spec's own, or the industry's starter services.
    if spec.custom_services:
        for he, _en, minutes, cap, color, _pop in spec.custom_services:
            conn.execute(
                text("""
                    INSERT INTO app.services
                        (tenant_id, name, duration_minutes, capacity, price_amount,
                         price_currency, color)
                    VALUES (:t, :name, :minutes, :capacity, 7000, 'ILS', :color)
                """),
                {"t": tenant_id, "name": he, "minutes": minutes, "capacity": cap, "color": color},
            )
    service_rows = (
        conn.execute(
            text("""
                SELECT id, name, duration_minutes, capacity, booking_mode, price_amount
                FROM app.services WHERE tenant_id = :t ORDER BY created_at, name
            """),
            {"t": tenant_id},
        )
        .mappings()
        .all()
    )
    popularity = {
        s["id"]: (spec.custom_services[i][5] if spec.custom_services else rng.uniform(0.6, 0.95))
        for i, s in enumerate(service_rows)
    }
    classes = [s for s in service_rows if s["booking_mode"] == "class"]
    appointments = [s for s in service_rows if s["booking_mode"] == "appointment"]

    rooms: dict[UUID, list[UUID]] = {}
    if classes:
        for branch in branches:
            rooms[branch] = [
                conn.execute(
                    text("""
                        INSERT INTO app.rooms (tenant_id, location_id, name) VALUES (:t, :l, :n)
                        RETURNING id
                    """),
                    {"t": tenant_id, "l": branch, "n": name},
                ).scalar_one()
                for name in ("סטודיו גדול", "חדר מכשירים")
            ]

    # Plans: the industry's, or a single visit and a five-visit card priced from the services.
    plans = (
        conn.execute(
            text("""
                SELECT id, name, kind, credits, validity_days, price_amount FROM app.plans
                WHERE tenant_id = :t ORDER BY kind, price_amount DESC
            """),
            {"t": tenant_id},
        )
        .mappings()
        .all()
    )
    if not plans:
        average = sum(s["price_amount"] for s in service_rows) // max(len(service_rows), 1)
        for name, credits, days, price in (
            ("ביקור בודד", 1, 30, average),
            ("כרטיסיית 5 ביקורים", 5, 180, round(average * 4.5 / 100) * 100),
        ):
            conn.execute(
                text("""
                    INSERT INTO app.plans
                        (tenant_id, name, kind, validity_days, credits, price_amount,
                         price_currency)
                    VALUES (:t, :name, 'punch_card', :days, :credits, :price, 'ILS')
                """),
                {"t": tenant_id, "name": name, "days": days, "credits": credits, "price": price},
            )
        plans = (
            conn.execute(
                text("""
                    SELECT id, name, kind, credits, validity_days, price_amount FROM app.plans
                    WHERE tenant_id = :t ORDER BY kind, price_amount DESC
                """),
                {"t": tenant_id},
            )
            .mappings()
            .all()
        )
    plan_weights = [5 if p["kind"] == "membership" else 4 if (p["credits"] or 0) > 1 else 2
                    for p in plans]  # fmt: skip

    # The team: demo profiles that cannot sign in, each working at one branch.
    staff: dict[UUID, list[UUID]] = {}
    instructors: list[UUID] = []
    names = list(INSTRUCTORS) if spec.custom_services else []
    for branch in branches:
        staff[branch] = []
        for _ in range(spec.staff_per_branch):
            first, last = (
                names.pop(0) if names else (rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
            )
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
                    INSERT INTO app.tenant_members (tenant_id, user_id, role, location_ids)
                    VALUES (:t, :u, 'staff', :branches)
                """),
                {"t": tenant_id, "u": user_id, "branches": [branch] if len(branches) > 1 else []},
            )
            staff[branch].append(user_id)
            instructors.append(user_id)

    # Sessions: classes as weekly series; appointments as single slots per staff member.
    sessions: list[dict] = []

    def add_session(service: dict, branch: UUID, room: UUID | None, coach: UUID, day: date,
                    at: time, series_id: UUID | None) -> None:  # fmt: skip
        starts_at = local_to_utc(day, at, TIME_ZONE)
        sessions.append(
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "series_id": series_id,
                "service_id": service["id"],
                "location_id": branch,
                "room_id": room,
                "instructor": coach,
                "capacity": service["capacity"] if service["booking_mode"] == "class" else 1,
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(minutes=service["duration_minutes"]),
                # A few cancelled classes (holidays, sick instructor).
                "status": "cancelled" if rng.random() < 0.015 else "scheduled",
                "day": day,
                "hour": at.hour,
                "popularity": popularity[service["id"]],
                "appointment": service["booking_mode"] == "appointment",
            }
        )

    def weekly(service: dict, branch: UUID, room: UUID, coach: UUID, weekday: int, at: str):
        start_time = time.fromisoformat(at)
        series_id = conn.execute(
            text("""
                INSERT INTO app.session_series
                    (tenant_id, service_id, location_id, room_id, instructor_user_id, capacity,
                     weekdays, start_time, duration_minutes, starts_on, ends_on, open_ended)
                VALUES (:t, :s, :l, :r, :i, :c, :w, :at, :m, :from, :to, true) RETURNING id
            """),
            {
                "t": tenant_id,
                "s": service["id"],
                "l": branch,
                "r": room,
                "i": coach,
                "c": service["capacity"],
                "w": [weekday],
                "at": start_time,
                "m": service["duration_minutes"],
                "from": start,
                "to": horizon,
            },
        ).scalar_one()
        day = start + timedelta(days=(weekday - start.weekday()) % 7)
        while day <= horizon:
            add_session(service, branch, room, coach, day, start_time, series_id)
            day += timedelta(days=7)

    if spec.timetable:
        branch = branches[0]
        by_index = {s["name"]: s for s in service_rows}
        for weekday, at, service_index, room_index, coach_index in spec.timetable:
            service = by_index[spec.custom_services[service_index][0]]  # type: ignore[index]
            weekly(service, branch, rooms[branch][room_index], staff[branch][coach_index],
                   weekday, at)  # fmt: skip
    elif classes:
        for branch in branches:
            for weekday in (6, 0, 1, 2, 3, 4, 5):  # Sunday first, as the week runs in Israel
                count = 1 if weekday == 5 else 2 if weekday == 4 else rng.randint(3, 4)
                for at in sorted(rng.sample(CLASS_HOURS, k=count)):
                    service = rng.choice(classes)
                    room = rooms[branch][0 if service["capacity"] > 8 else -1]
                    weekly(service, branch, room, rng.choice(staff[branch]), weekday, at)

    if appointments:
        # Staff hours (Sunday to Thursday all day, Friday morning), and slots inside them;
        # only the slots someone booked are kept.
        busy = not classes  # an appointments-only business fills whole days
        hours_rows = []
        for branch in branches:
            for coach in staff[branch]:
                for weekday, (opens, closes) in WORK_HOURS.items():
                    hours_rows.append(
                        {
                            "t": tenant_id,
                            "u": coach,
                            "w": weekday,
                            "s": time(opens),
                            "e": time(closes),
                        }
                    )
                    day = start + timedelta(days=(weekday - start.weekday()) % 7)
                    while day <= horizon:
                        minute = opens * 60
                        while minute < closes * 60:
                            service = rng.choice(appointments)
                            if minute + service["duration_minutes"] > closes * 60:
                                break
                            if busy or rng.random() < 0.15:
                                at = time(minute // 60, minute % 60)
                                add_session(service, branch, None, coach, day, at, None)
                            minute += service["duration_minutes"]
                        day += timedelta(days=7)
        _insert(conn, """
            INSERT INTO app.staff_hours (tenant_id, user_id, weekday, starts, ends)
            VALUES (:t, :u, :w, :s, :e)
        """, hours_rows)  # fmt: skip

    # Clients: a base at the start, then steady growth; some churn. Each has a home branch
    # (the first branches are the bigger ones) and mostly comes there.
    leads = max(5, spec.clients * LEADS // CLIENTS)
    base = spec.clients * 70 // CLIENTS
    branch_weights = [max(1, len(branches) - i) for i in range(len(branches))]
    clients: list[Client] = []
    client_rows: list[dict] = []
    home: dict[UUID, UUID] = {}
    total_days = (today - start).days
    for index in range(spec.clients):
        # The first ones were clients before the history starts, with staggered renewals.
        joined = (
            start - timedelta(days=rng.randrange(60))
            if index < base
            else start + timedelta(days=rng.randrange(total_days))
        )
        churns = rng.random() < 0.18
        churns_on = joined + timedelta(days=rng.randrange(30, 120)) if churns else None
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        status = (
            "lead"
            if index >= spec.clients - leads
            else ("inactive" if churns_on and churns_on < today else "active")
        )
        client = Client(
            id=uuid4(),
            joined=joined,
            churns_on=churns_on,
            # Some keep paying but stopped coming (a retention scenario).
            habit=0.01 if rng.random() < 0.08 else rng.uniform(0.12, 0.45),
            favorite_hours=set(rng.sample([7, 8, 9, 10, 11, 12, 17, 18, 19], k=rng.randint(2, 4))),
        )
        home[client.id] = rng.choices(branches, weights=branch_weights)[0]
        clients.append(client)
        client_rows.append(
            {
                "id": client.id,
                "tenant_id": tenant_id,
                "first_name": first,
                "last_name": last,
                "email": f"demo{index:03d}-{tenant_id.hex[:4]}@example.invalid",
                "phone": f"05{rng.randint(0, 9)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
                "status": status,
                "source": rng.choices(SOURCES, weights=SOURCE_WEIGHTS)[0],
                "home": home[client.id],
                "created_at": local_to_utc(joined, time(12), TIME_ZONE),
            }
        )
    _insert(conn, """
        INSERT INTO app.clients (id, tenant_id, first_name, last_name, email, phone, status,
                                 source, home_location_id, created_at, updated_at)
        VALUES (:id, :tenant_id, :first_name, :last_name, :email, :phone, :status, :source,
                :home, :created_at, :created_at)
    """, client_rows)  # fmt: skip
    buyers = clients[: spec.clients - leads]

    # Health declarations, where the industry asks for one: clients signed when they joined
    # (renewed yearly); a few answered "yes" somewhere, most of those approved.
    if pack.health_form:
        declaration_rows: list[dict] = []
        for client, row in zip(buyers, client_rows, strict=False):
            signed_on = max(client.joined, today - timedelta(days=rng.randrange(30, 330)))
            yes = rng.choice(list(FITNESS_FORM.questions)) if rng.random() < 0.08 else None
            status = (
                "valid" if yes is None else ("approved" if rng.random() < 0.7 else "needs_review")
            )
            declaration_rows.append(
                {
                    "tenant_id": tenant_id,
                    "client_id": client.id,
                    "form_key": FITNESS_FORM.key,
                    "answers": json.dumps(
                        [
                            {"id": key, "question": texts["he"], "answer": key == yes}
                            for key, texts in FITNESS_FORM.questions.items()
                        ],
                        ensure_ascii=False,
                    ),
                    "statement": FITNESS_FORM.statement["he"],
                    "all_clear": yes is None,
                    "signed_name": f"{row['first_name']} {row['last_name']}",
                    "signed_at": local_to_utc(signed_on, time(12), TIME_ZONE),
                    "valid_until": signed_on + timedelta(days=FITNESS_FORM.validity_days),
                    "status": status,
                }
            )
        _insert(conn, """
            INSERT INTO app.health_declarations
                (tenant_id, client_id, form_key, locale, answers, statement, all_clear,
                 signed_name, signed_at, valid_until, status)
            VALUES (:tenant_id, :client_id, :form_key, 'he', :answers, :statement, :all_clear,
                    :signed_name, :signed_at, :valid_until, :status)
        """, declaration_rows)  # fmt: skip

    # Plans: each client buys a plan when they join and renews while active.
    entitlement_rows: list[dict] = []
    payment_rows: list[dict] = []
    failed_rows: list[dict] = []

    def sell(client: Client, plan: dict, on: date) -> None:
        entitlement = Entitlement(
            id=uuid4(),
            kind=plan["kind"],
            starts_on=on,
            ends_on=on + timedelta(days=plan["validity_days"] - 1),
            credits=plan["credits"],
        )
        client.entitlements.append(entitlement)
        sold_at = local_to_utc(on, time(10), TIME_ZONE)
        # Sold at the client's home branch (filed there by the database as well).
        entitlement_rows.append(
            {
                "id": entitlement.id,
                "tenant_id": tenant_id,
                "client_id": client.id,
                "plan_id": plan["id"],
                "name": plan["name"],
                "kind": plan["kind"],
                "credits": plan["credits"],
                "starts_on": on,
                "ends_on": entitlement.ends_on,
                "price": plan["price_amount"],
                "branch": home[client.id],
                "created_at": sold_at,
            }
        )
        if rng.random() < 0.05:  # a declined card, then a successful retry
            failed_rows.append(
                {
                    "tenant_id": tenant_id,
                    "client_id": client.id,
                    "amount": plan["price_amount"],
                    "key": f"seed-failed-{entitlement.id}",
                    "branch": home[client.id],
                    "created_at": sold_at - timedelta(hours=2),
                }
            )
        payment_rows.append(
            {
                "tenant_id": tenant_id,
                "client_id": client.id,
                "entitlement_id": entitlement.id,
                "amount": plan["price_amount"],
                "key": f"seed-{entitlement.id}",
                "branch": home[client.id],
                "created_at": sold_at,
            }
        )

    decline_from, decline_to = today - timedelta(days=60), today - timedelta(days=30)
    for client in buyers:
        prefers = rng.choices(plans, weights=plan_weights)[0]
        day = client.joined
        last_day = min(client.churns_on or horizon, today + timedelta(days=3))
        while day <= last_day:
            # A weak month: a third of the renewals two months ago did not happen.
            if client.entitlements and decline_from <= day < decline_to and rng.random() < 0.35:
                client.churns_on = day
                break
            sell(client, prefers, day)
            current = client.entitlements[-1]
            # Renew when it ends (or soon after a card is used up, approximated below).
            day = current.ends_on + timedelta(days=rng.choice([1, 1, 2, 5]))

    # Bookings, session by session in time order; clients mostly come to their home branch.
    booking_rows: list[dict] = []
    now = datetime.now(UTC)
    for session in sorted(sessions, key=lambda s: s["starts_at"]):
        if session["status"] == "cancelled":
            continue
        day, past = session["day"], session["starts_at"] < now
        demand = session["popularity"] * (1.25 if session["hour"] in (7, 18, 19) else 0.8)
        if session["appointment"]:
            demand *= 3  # one chair: a handful of interested clients fill it
        if not past:  # the future fills up as it gets closer
            demand *= max(0.15, 1 - (session["day"] - today).days / 21)
        candidates = [
            c
            for c in clients
            if c.joined <= day
            and (c.churns_on is None or day < c.churns_on)
            and (home[c.id] == session["location_id"] or rng.random() < 0.06)
            and rng.random()
            < c.habit * demand * (1.6 if session["hour"] in c.favorite_hours else 0.5)
        ]
        rng.shuffle(candidates)
        booked = 0
        waitlisted = 0
        for client in candidates:
            plan = client.plan_on(day)
            if plan is None:
                continue
            created = session["starts_at"] - timedelta(hours=rng.uniform(2, 96))
            row = {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "session_id": session["id"],
                "client_id": client.id,
                "entitlement_id": plan.id,
                "created_at": created,
                "waitlisted_at": None,
                "cancelled_at": None,
                "late_cancel": False,
                "checked_in_at": None,
            }
            if booked >= session["capacity"]:
                if session["appointment"] or waitlisted >= 4:
                    break
                waitlisted += 1
                row["status"] = "waitlisted" if not past else "cancelled"
                row["waitlisted_at"] = created
                if past:  # never got a spot
                    row["cancelled_at"] = session["starts_at"]
                else:
                    plan.used += 1
                booking_rows.append(row)
                continue
            booked += 1
            plan.used += 1
            roll = rng.random()
            if past and roll < 0.06:
                row["status"] = "no_show"
            elif roll < 0.13 and (past or rng.random() < 0.3):
                # In time means before the 2-hour window; a late booking can only cancel late.
                latest_in_time = session["starts_at"] - timedelta(hours=2, minutes=5)
                row["status"] = "cancelled"
                row["late_cancel"] = roll < 0.085 or latest_in_time <= created
                row["cancelled_at"] = (
                    session["starts_at"] - timedelta(hours=rng.uniform(0.3, 1.8))
                    if row["late_cancel"]
                    else created + (latest_in_time - created) * rng.uniform(0.2, 1)
                )
                booked -= 1
                if not row["late_cancel"]:
                    plan.used -= 1
            elif past:
                row["status"] = "checked_in"
                row["checked_in_at"] = session["starts_at"] - timedelta(minutes=rng.randint(2, 15))
            else:
                row["status"] = "booked"
            booking_rows.append(row)
            if session["appointment"]:
                break  # one client per appointment

    # Only the appointment slots someone booked exist; classes are all on the timetable.
    booked_sessions = {b["session_id"] for b in booking_rows}
    sessions = [s for s in sessions if not s["appointment"] or s["id"] in booked_sessions]
    _insert(conn, """
        INSERT INTO app.sessions
            (id, tenant_id, series_id, service_id, location_id, room_id, instructor_user_id,
             capacity, starts_at, ends_at, status)
        VALUES (:id, :tenant_id, :series_id, :service_id, :location_id, :room_id, :instructor,
                :capacity, :starts_at, :ends_at, :status)
    """, sessions)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.entitlements
            (id, tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
             price_amount, price_currency, sold_by, location_id, created_at, updated_at)
        VALUES (:id, :tenant_id, :client_id, :plan_id, :name, :kind, :credits, :starts_on,
                :ends_on, :price, 'ILS', NULL, :branch, :created_at, :created_at)
    """, entitlement_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.payments
            (tenant_id, client_id, entitlement_id, amount, currency, status, provider,
             idempotency_key, location_id, created_at)
        VALUES (:tenant_id, :client_id, :entitlement_id, :amount, 'ILS', 'succeeded', 'simulated',
                :key, :branch, :created_at)
    """, payment_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.payments
            (tenant_id, client_id, amount, currency, status, provider, idempotency_key,
             location_id, created_at)
        VALUES (:tenant_id, :client_id, :amount, 'ILS', 'failed', 'simulated', :key, :branch,
                :created_at)
    """, failed_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.bookings
            (id, tenant_id, session_id, client_id, entitlement_id, status, waitlisted_at,
             cancelled_at, late_cancel, checked_in_at, created_at, updated_at)
        VALUES (:id, :tenant_id, :session_id, :client_id, :entitlement_id, :status,
                :waitlisted_at, :cancelled_at, :late_cancel, :checked_in_at, :created_at,
                :created_at)
    """, booking_rows)  # fmt: skip

    # The industry's client details for some clients (a choice where the field offers one).
    choices = [f for f in pack.client_fields if f.kind == "select"]
    profile_rows = [
        {"id": c.id, "fields": json.dumps({f.key: rng.choice(f.options) for f in choices})}
        for c in clients
        if choices and rng.random() < 0.4
    ]
    _insert(conn, "UPDATE app.clients SET custom_fields = CAST(:fields AS jsonb) WHERE id = :id",
            profile_rows)  # fmt: skip
    by_id = {s["id"]: s for s in sessions}
    attended = [b for b in booking_rows if b.get("status") == "checked_in"]
    notes = COACH_NOTES if category == "fitness" else GENERIC_NOTES
    note_rows = [
        {
            "tenant_id": tenant_id,
            "client_id": b["client_id"],
            "booking_id": b["id"],
            "author": by_id[b["session_id"]]["instructor"],
            "body": rng.choice(notes),
            "at": by_id[b["session_id"]]["ends_at"] + timedelta(minutes=10),
        }
        for b in rng.sample(attended, k=min(60, len(attended)))
    ]
    _insert(conn, """
        INSERT INTO app.client_notes
            (tenant_id, client_id, booking_id, author_user_id, body, created_at)
        VALUES (:tenant_id, :client_id, :booking_id, :author, :body, :at)
    """, note_rows)  # fmt: skip

    conn.execute(
        text("""
            INSERT INTO app.message_templates (tenant_id, name, body) VALUES
                (:t, 'תזכורת', 'היי {first_name}, מחכים לך היום 🙂'),
                (:t, 'מתגעגעים', 'היי {first_name}, מזמן לא ראינו אותך! נשמח לראות אותך השבוע.')
        """),
        {"t": tenant_id},
    )

    # Ratings clients left after their visits, mostly happy.
    comments = REVIEW_COMMENTS if category == "fitness" else GENERIC_REVIEWS
    review_rows = []
    for b in rng.sample(attended, k=min(220 * len(branches), len(attended))):
        rating = rng.choices((5, 4, 3, 2, 1), weights=(52, 30, 11, 5, 2))[0]
        session = by_id[b["session_id"]]
        review_rows.append(
            {
                "tenant_id": tenant_id,
                "client_id": b["client_id"],
                "booking_id": b["id"],
                "service_id": session["service_id"],
                "staff": session["instructor"],
                "rating": rating,
                "comment": rng.choice(comments[rating]) if rng.random() < 0.35 else None,
                "at": session["ends_at"] + timedelta(hours=rng.randint(1, 30)),
            }
        )
    _insert(conn, """
        INSERT INTO app.reviews
            (tenant_id, client_id, booking_id, service_id, staff_user_id, rating, comment,
             created_at)
        VALUES (:tenant_id, :client_id, :booking_id, :service_id, :staff, :rating, :comment, :at)
    """, review_rows)  # fmt: skip

    # MyBiz's own (simulated) billing: a test card on file, monthly invoices since the trial.
    conn.execute(
        text("""
            INSERT INTO app.billing_accounts
                (tenant_id, billing_name, billing_email, card_brand, card_last4, card_exp)
            VALUES (:t, :name, :email, 'visa', '4242', '12/29')
        """),
        {"t": tenant_id, "name": spec.billing_name, "email": owner_email},
    )
    bill_businesses(conn, tenant_id=tenant_id)

    interests = (
        LEAD_INTERESTS
        if category == "fitness"
        else (*(f"מתעניין/ת ב{s['name']}" for s in service_rows), "מה המחירים?", None)
    )
    lead_count = _seed_leads(conn, tenant_id, [owner, *instructors], clients, today, rng, interests)

    print(
        f"Created demo business {tenant_id} ({spec.name}): {len(branches)} branches, "
        f"{len(clients)} clients, {lead_count} leads, {len(sessions)} sessions, "
        f"{len(entitlement_rows)} plans sold, {len(booking_rows)} bookings."
    )
    return tenant_id


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


REVIEW_COMMENTS = {
    5: ("שיעור מעולה, יצאתי עם אנרגיות!", "המדריכה הכי טובה שיש", "בדיוק מה שהייתי צריכה"),
    4: ("שיעור טוב, קצת צפוף", "נהניתי מאוד", "אחלה אווירה"),
    3: ("היה בסדר", "המוזיקה הייתה חזקה מדי"),
    2: ("החדר היה חם מדי", "התחיל באיחור"),
    1: ("השיעור בוטל ברגע האחרון",),
}
COACH_NOTES = (
    "עבדנו על יציבה בגב התחתון, להמשיך בשבוע הבא",
    "התקדמות יפה בכוח הליבה",
    "להקל בתרגילי ברכיים",
    "ביקש/ה תרגילים לבית, שלחתי",
    "עלה/תה רמה במשקולות",
)
LEAD_INTERESTS = (
    "פילאטיס מכשירים למתחילים",
    "שיעורי בוקר לפני העבודה",
    "יוגה אחרי לידה",
    "כרטיסייה לחברה ואני",
    "מה המחיר למנוי חודשי?",
    "אימון כוח פעמיים בשבוע",
    None,
)
LEAD_NOTES = (
    "לא ענה/תה, לנסות שוב מחר",
    "מעוניין/ת בשיעור ניסיון ביום ראשון",
    "שלחתי מחירון בוואטסאפ",
    "הגיע/ה לשיעור ניסיון, נהנה/תה",
    "מתלבט/ת בין כרטיסייה למנוי",
)


def _seed_leads(
    conn: Connection,
    tenant_id: UUID,
    team: list[UUID],
    clients: list[Client],
    today: date,
    rng: random.Random,
    interests: tuple[str | None, ...] = LEAD_INTERESTS,
) -> int:
    """A CRM pipeline: open leads in every stage, and recent ones that were won or lost."""
    recent = sorted((c for c in clients if c.joined > today - timedelta(days=60)),
                    key=lambda c: c.joined)[-8:]  # fmt: skip
    plan: list[tuple[str, Client | None]] = [
        *(
            (stage, None)
            for stage in ["new"] * 7 + ["contacted"] * 5 + ["trial"] * 4 + ["offer"] * 3
        ),
        *(("won", client) for client in recent),
        *(("lost", None) for _ in range(5)),
    ]
    lead_rows: list[dict] = []
    activity_rows: list[dict] = []
    path = ["new", "contacted", "trial", "offer"]
    for stage, client in plan:
        lead_id = uuid4()
        age = rng.randint(1, 50) if stage in ("won", "lost") else rng.randint(0, 25)
        created = datetime.combine(today - timedelta(days=age), time(rng.randint(8, 20)),
                                   ZoneInfo(TIME_ZONE))  # fmt: skip
        changed = created + timedelta(days=rng.randint(0, max(age - 1, 0)), hours=2)
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        source = rng.choices(("form", "instagram", "referral", "walk_in", "facebook", "google"),
                             weights=(5, 5, 3, 2, 2, 1))[0]  # fmt: skip
        open_lead = stage not in ("won", "lost")
        lead_rows.append({
            "id": lead_id, "tenant_id": tenant_id, "first_name": first, "last_name": last,
            "email": f"lead-{lead_id.hex[:6]}@example.invalid",
            "phone": f"05{rng.randint(0, 9)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
            "interest": rng.choice(interests), "source": source, "stage": stage,
            "lost_reason": rng.choice(("רחוק מהבית", "יקר מדי", "בחר/ה מקום אחר"))
            if stage == "lost" else None,
            "follow_up_on": today + timedelta(days=rng.randint(-2, 6))
            if open_lead and rng.random() < 0.6 else None,
            "owner_user_id": rng.choice(team) if rng.random() < 0.8 else None,
            "client_id": client.id if client else None,
            "created_at": created, "stage_changed_at": changed,
        })  # fmt: skip
        activity_rows.append({"tenant_id": tenant_id, "lead_id": lead_id, "kind": "created",
                              "note": None, "to_stage": "new", "at": created})  # fmt: skip
        steps = path[1 : path.index(stage) + 1] if stage in path else path[1:3]
        for step_index, step in enumerate(steps):
            at = created + (changed - created) * (step_index + 1) / (len(steps) + 1)
            activity_rows.append({"tenant_id": tenant_id, "lead_id": lead_id, "kind": "call",
                                  "note": rng.choice(LEAD_NOTES), "to_stage": None,
                                  "at": at - timedelta(minutes=5)})  # fmt: skip
            activity_rows.append({"tenant_id": tenant_id, "lead_id": lead_id, "kind": "stage",
                                  "note": None, "to_stage": step, "at": at})  # fmt: skip
        if not open_lead:
            activity_rows.append({"tenant_id": tenant_id, "lead_id": lead_id,
                                  "kind": "converted" if stage == "won" else "stage",
                                  "note": None, "to_stage": stage, "at": changed})  # fmt: skip
    _insert(conn, """
        INSERT INTO app.leads
            (id, tenant_id, first_name, last_name, email, phone, interest, source, stage,
             lost_reason, follow_up_on, owner_user_id, client_id, created_at, updated_at,
             stage_changed_at)
        VALUES (:id, :tenant_id, :first_name, :last_name, :email, :phone, :interest, :source,
                :stage, :lost_reason, :follow_up_on, :owner_user_id, :client_id, :created_at,
                :stage_changed_at, :stage_changed_at)
    """, lead_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.lead_activities (tenant_id, lead_id, kind, note, to_stage, occurred_at)
        VALUES (:tenant_id, :lead_id, :kind, :note, :to_stage, :at)
    """, activity_rows)  # fmt: skip
    return len(lead_rows)


def seed_platform(
    conn: Connection,
    staff_email: str,
    months: int,
    rng: random.Random,
    staff_name: str | None = None,
    replace: bool = False,
) -> list[UUID]:
    """MyBiz's own demo: `staff_email` becomes the primary owner of the MyBiz team, and the
    platform gets small businesses of several industries (fictitious owners), their monthly
    invoices (some paid by card, some still open) and requests from the contact form."""
    from app.billing import bill_businesses  # billing imports nothing from here

    profile_id(conn, staff_email)
    if staff_name:
        conn.execute(
            text("UPDATE app.users SET full_name = :name WHERE lower(email) = lower(:email)"),
            {"name": staff_name, "email": staff_email},
        )
    conn.execute(
        text("""
            INSERT INTO app.platform_staff (email, level, added_by)
            VALUES (lower(:email), 'owner', 'demo generator') ON CONFLICT DO NOTHING
        """),
        {"email": staff_email},
    )
    if replace:
        conn.execute(
            text("""
                DELETE FROM app.tenants t WHERE EXISTS (
                    SELECT 1 FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                    WHERE m.tenant_id = t.id AND u.email LIKE 'demo-owner-%@example.invalid'
                )
            """)
        )
        conn.execute(text("DELETE FROM app.contact_requests WHERE email LIKE '%@example.invalid'"))
    tenants = []
    for index, (spec, owner_name) in enumerate(PLATFORM_BUSINESSES, start=1):
        email = f"demo-owner-{index}@example.invalid"
        conn.execute(
            text("""
                INSERT INTO app.users (id, email, full_name) VALUES (gen_random_uuid(), :e, :n)
                ON CONFLICT DO NOTHING
            """),
            {"e": email, "n": owner_name},
        )
        tenant_id = seed(conn, email, months, rng, spec)
        if index % 3:  # two in three pay by card; the rest have open invoices
            conn.execute(
                text("""
                    INSERT INTO app.billing_accounts
                        (tenant_id, billing_name, billing_email, card_brand, card_last4, card_exp)
                    VALUES (:t, :name, :email, 'visa', :last4, '12/29')
                    ON CONFLICT (tenant_id) DO UPDATE SET card_last4 = EXCLUDED.card_last4
                """),
                {
                    "t": tenant_id,
                    "name": spec.billing_name,
                    "email": email,
                    "last4": f"{4000 + index * 7}",
                },
            )
        bill_businesses(conn, tenant_id=tenant_id)
        tenants.append(tenant_id)
    for name, email, business, vertical, message, status in PLATFORM_REQUESTS:
        conn.execute(
            text("""
                INSERT INTO app.contact_requests
                    (name, email, business, vertical, message, locale, status, created_at)
                VALUES (:name, :email, :business, :vertical, :message, 'he', :status,
                        now() - make_interval(days => :days))
            """),
            {
                "name": name,
                "email": email,
                "business": business,
                "vertical": vertical,
                "message": message,
                "status": status,
                "days": rng.randint(0, 12),
            },
        )
    print(
        f"Platform demo: {len(tenants)} businesses, {len(PLATFORM_REQUESTS)} requests, "
        f"{staff_email} is a MyBiz owner."
    )
    return tenants


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--owner-email", required=True)
    parser.add_argument(
        "--demo",
        default="studio",
        choices=sorted(DEMOS),
        help="studio: one fitness studio; owner: a pilates chain with five branches and a "
        "barbershop with three; platform: the owner email becomes a MyBiz team owner and the "
        "platform gets small businesses, invoices and requests",
    )
    parser.add_argument("--owner-name", default=None, help="Sets the owner's display name")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remove the owner's earlier copies of the demo businesses first",
    )
    parser.add_argument("--months", type=int, default=3, choices=range(1, 13))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    args = parser.parse_args()

    engine = create_engine(args.database_url or get_settings().database_url)
    with engine.begin() as conn:
        if args.demo == "platform":
            seed_platform(
                conn,
                args.owner_email,
                args.months,
                random.Random(args.seed),
                staff_name=args.owner_name,
                replace=args.replace,
            )
            return
        seed_demo(
            conn,
            args.owner_email,
            args.demo,
            args.months,
            random.Random(args.seed),
            owner_name=args.owner_name,
            replace=args.replace,
        )


if __name__ == "__main__":
    main()
