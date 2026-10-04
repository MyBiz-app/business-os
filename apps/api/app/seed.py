"""Demo data: a boutique fitness studio with months of realistic history.

    uv run python -m app.seed --owner-email you@example.com [--months 3] [--seed 7]

The owner must have signed in once (so their profile exists). The script creates a new
business owned by them, with locations, services, instructors, a weekly timetable, clients,
plans sold over time (simulated payments) and bookings with attendance, no-shows, late
cancellations and waitlists. Instructors are demo profiles that cannot sign in.

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


def seed(conn: Connection, owner_email: str, months: int, rng: random.Random) -> UUID:
    owner = conn.execute(
        text("SELECT id FROM app.users WHERE lower(email) = lower(:email)"), {"email": owner_email}
    ).scalar()
    if owner is None:
        sys.exit(f"No profile for {owner_email}: sign in to the web app once, then run again.")

    today = datetime.now(ZoneInfo(TIME_ZONE)).date()
    start = today - timedelta(days=30 * months)
    horizon = today + timedelta(days=28)

    tenant_id = conn.execute(
        text("""
            INSERT INTO app.tenants (name, vertical, locale, time_zone, currency, primary_color,
                                     created_at, trial_ends_at)
            VALUES ('סטודיו פלואו (דמו)', 'fitness', 'he', :tz, 'ILS', '#0f766e', :created,
                    CAST(:created AS timestamptz) + interval '14 days')
            RETURNING id
        """),
        {"tz": TIME_ZONE, "created": local_to_utc(start - timedelta(days=90), time(9), TIME_ZONE)},
    ).scalar_one()
    conn.execute(
        text("INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'owner')"),
        {"t": tenant_id, "u": owner},
    )
    apply_vertical_pack(conn, tenant_id, "fitness", "he", "ILS")
    # Show everything: the richest preset plus the CRM.
    set_modules(conn, tenant_id, {**dict.fromkeys(PRESETS["ai_powered"], 1), "crm": 1})
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
    membership, card10, single = plans[0], plans[1], plans[2]

    # Place, services, team.
    location = conn.execute(
        text("""
            INSERT INTO app.locations (tenant_id, name, address)
            VALUES (:t, 'תל אביב - פלורנטין', 'הרצל 120, תל אביב') RETURNING id
        """),
        {"t": tenant_id},
    ).scalar_one()
    rooms = [
        conn.execute(
            text("""
                INSERT INTO app.rooms (tenant_id, location_id, name) VALUES (:t, :l, :n)
                RETURNING id
            """),
            {"t": tenant_id, "l": location, "n": name},
        ).scalar_one()
        for name in ("סטודיו גדול", "חדר מכשירים")
    ]
    services = [
        conn.execute(
            text("""
                INSERT INTO app.services
                    (tenant_id, name, duration_minutes, capacity, price_amount, price_currency,
                     color)
                VALUES (:t, :name, :minutes, :capacity, 7000, 'ILS', :color) RETURNING id
            """),
            {"t": tenant_id, "name": he, "minutes": minutes, "capacity": cap, "color": color},
        ).scalar_one()
        for he, _en, minutes, cap, color, _pop in SERVICES
    ]
    instructors = []
    for first, last in INSTRUCTORS:
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
            text(
                "INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'staff')"
            ),
            {"t": tenant_id, "u": user_id},
        )
        instructors.append(user_id)

    # Timetable as weekly series, expanded from `start` to `horizon`.
    sessions: list[dict] = []
    for weekday, at, service_index, room_index, coach_index in TIMETABLE:
        _he, _en, minutes, capacity, _color, popularity = SERVICES[service_index]
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
                "s": services[service_index],
                "l": location,
                "r": rooms[room_index],
                "i": instructors[coach_index],
                "c": capacity,
                "w": [weekday],
                "at": start_time,
                "m": minutes,
                "from": start,
                "to": horizon,
            },
        ).scalar_one()
        day = start + timedelta(days=(weekday - start.weekday()) % 7)
        while day <= horizon:
            starts_at = local_to_utc(day, start_time, TIME_ZONE)
            sessions.append(
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "series_id": series_id,
                    "service_id": services[service_index],
                    "location_id": location,
                    "room_id": rooms[room_index],
                    "instructor": instructors[coach_index],
                    "capacity": capacity,
                    "starts_at": starts_at,
                    "ends_at": starts_at + timedelta(minutes=minutes),
                    # A few cancelled classes (holidays, sick instructor).
                    "status": "cancelled" if rng.random() < 0.015 else "scheduled",
                    "day": day,
                    "hour": start_time.hour,
                    "popularity": popularity,
                }
            )
            day += timedelta(days=7)
    _insert(conn, """
        INSERT INTO app.sessions
            (id, tenant_id, series_id, service_id, location_id, room_id, instructor_user_id,
             capacity, starts_at, ends_at, status)
        VALUES (:id, :tenant_id, :series_id, :service_id, :location_id, :room_id, :instructor,
                :capacity, :starts_at, :ends_at, :status)
    """, sessions)  # fmt: skip

    # Clients: a base at the start, then steady growth; some churn.
    clients: list[Client] = []
    client_rows: list[dict] = []
    total_days = (today - start).days
    for index in range(CLIENTS):
        # The first 70 were members before the history starts, with staggered renewals.
        joined = (
            start - timedelta(days=rng.randrange(60))
            if index < 70
            else start + timedelta(days=rng.randrange(total_days))
        )
        churns = rng.random() < 0.18
        churns_on = joined + timedelta(days=rng.randrange(30, 120)) if churns else None
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        status = (
            "lead"
            if index >= CLIENTS - LEADS
            else ("inactive" if churns_on and churns_on < today else "active")
        )
        client = Client(
            id=uuid4(),
            joined=joined,
            churns_on=churns_on,
            # Some members keep paying but stopped coming (a retention scenario).
            habit=0.01 if rng.random() < 0.08 else rng.uniform(0.12, 0.45),
            favorite_hours=set(rng.sample([7, 8, 9, 10, 11, 12, 18, 19], k=rng.randint(2, 4))),
        )
        clients.append(client)
        client_rows.append(
            {
                "id": client.id,
                "tenant_id": tenant_id,
                "first_name": first,
                "last_name": last,
                "email": f"demo{index:03d}@example.invalid",
                "phone": f"05{rng.randint(0, 9)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
                "status": status,
                "source": rng.choices(SOURCES, weights=SOURCE_WEIGHTS)[0],
                "created_at": local_to_utc(joined, time(12), TIME_ZONE),
            }
        )
    _insert(conn, """
        INSERT INTO app.clients (id, tenant_id, first_name, last_name, email, phone, status,
                                 source, created_at, updated_at)
        VALUES (:id, :tenant_id, :first_name, :last_name, :email, :phone, :status, :source,
                :created_at, :created_at)
    """, client_rows)  # fmt: skip

    # Health declarations: members signed when they joined (renewed yearly); a few answered
    # "yes" somewhere, and most of those were approved by the studio.
    declaration_rows: list[dict] = []
    for index, (client, row) in enumerate(zip(clients, client_rows, strict=True)):
        if index >= CLIENTS - LEADS:
            continue
        signed_on = max(client.joined, today - timedelta(days=rng.randrange(30, 330)))
        yes = rng.choice(list(FITNESS_FORM.questions)) if rng.random() < 0.08 else None
        status = "valid" if yes is None else ("approved" if rng.random() < 0.7 else "needs_review")
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
            (tenant_id, client_id, form_key, locale, answers, statement, all_clear, signed_name,
             signed_at, valid_until, status)
        VALUES (:tenant_id, :client_id, :form_key, 'he', :answers, :statement, :all_clear,
                :signed_name, :signed_at, :valid_until, :status)
    """, declaration_rows)  # fmt: skip

    # Plans: each client buys a membership or a card when they join and renews while active.
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
                "created_at": sold_at,
            }
        )

    decline_from, decline_to = today - timedelta(days=60), today - timedelta(days=30)
    for client in clients[: CLIENTS - LEADS]:
        prefers = rng.choices([membership, card10, single], weights=[5, 4, 1])[0]
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

    # Bookings, session by session in time order.
    booking_rows: list[dict] = []
    now = datetime.now(UTC)
    for session in sorted(sessions, key=lambda s: s["starts_at"]):
        if session["status"] == "cancelled":
            continue
        day, past = session["day"], session["starts_at"] < now
        demand = session["popularity"] * (1.25 if session["hour"] in (7, 18, 19) else 0.8)
        if not past:  # the future fills up as it gets closer
            demand *= max(0.15, 1 - (session["day"] - today).days / 21)
        candidates = [
            c
            for c in clients
            if c.joined <= day
            and (c.churns_on is None or day < c.churns_on)
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
                if waitlisted >= 4:
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

    _insert(conn, """
        INSERT INTO app.entitlements
            (id, tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
             price_amount, price_currency, sold_by, created_at, updated_at)
        VALUES (:id, :tenant_id, :client_id, :plan_id, :name, :kind, :credits, :starts_on,
                :ends_on, :price, 'ILS', NULL, :created_at, :created_at)
    """, entitlement_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.payments
            (tenant_id, client_id, entitlement_id, amount, currency, status, provider,
             idempotency_key, created_at)
        VALUES (:tenant_id, :client_id, :entitlement_id, :amount, 'ILS', 'succeeded', 'simulated',
                :key, :created_at)
    """, payment_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.payments
            (tenant_id, client_id, amount, currency, status, provider, idempotency_key,
             created_at)
        VALUES (:tenant_id, :client_id, :amount, 'ILS', 'failed', 'simulated', :key, :created_at)
    """, failed_rows)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.bookings
            (id, tenant_id, session_id, client_id, entitlement_id, status, waitlisted_at,
             cancelled_at, late_cancel, checked_in_at, created_at, updated_at)
        VALUES (:id, :tenant_id, :session_id, :client_id, :entitlement_id, :status,
                :waitlisted_at, :cancelled_at, :late_cancel, :checked_in_at, :created_at,
                :created_at)
    """, booking_rows)  # fmt: skip

    # The fitness pack's profile fields and a few coach notes from recent classes.
    goals = ("weight_loss", "strength", "flexibility", "rehab", "general")
    profile_rows = [
        {"id": c.id, "fields": json.dumps({"goal": rng.choice(goals)})}
        for c in clients
        if rng.random() < 0.4
    ]
    _insert(conn, "UPDATE app.clients SET custom_fields = CAST(:fields AS jsonb) WHERE id = :id",
            profile_rows)  # fmt: skip
    by_id = {s["id"]: s for s in sessions}
    attended = [b for b in booking_rows if b.get("status") == "checked_in"]
    note_rows = [
        {
            "tenant_id": tenant_id,
            "client_id": b["client_id"],
            "booking_id": b["id"],
            "author": by_id[b["session_id"]]["instructor"],
            "body": rng.choice(COACH_NOTES),
            "at": by_id[b["session_id"]]["ends_at"] + timedelta(minutes=10),
        }
        for b in rng.sample(attended, k=min(60, len(attended)))
    ]
    _insert(conn, """
        INSERT INTO app.client_notes
            (tenant_id, client_id, booking_id, author_user_id, body, created_at)
        VALUES (:tenant_id, :client_id, :booking_id, :author, :body, :at)
    """, note_rows)  # fmt: skip

    # MyBiz's own (simulated) billing: a test card on file, monthly invoices since the trial.
    conn.execute(
        text("""
            INSERT INTO app.billing_accounts
                (tenant_id, billing_name, billing_email, card_brand, card_last4, card_exp)
            VALUES (:t, 'סטודיו פלואו בע״מ', :email, 'visa', '4242', '12/29')
        """),
        {"t": tenant_id, "email": owner_email},
    )
    bill_businesses(conn, tenant_id=tenant_id)

    lead_count = _seed_leads(conn, tenant_id, [owner, *instructors], clients, today, rng)

    print(
        f"Created demo business {tenant_id}: {len(clients)} clients, {lead_count} leads, "
        f"{len(sessions)} sessions, "
        f"{len(entitlement_rows)} plans sold, {len(booking_rows)} bookings."
    )
    return tenant_id


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
            "interest": rng.choice(LEAD_INTERESTS), "source": source, "stage": stage,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--months", type=int, default=3, choices=range(1, 13))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    args = parser.parse_args()

    engine = create_engine(args.database_url or get_settings().database_url)
    with engine.begin() as conn:
        seed(conn, args.owner_email, args.months, random.Random(args.seed))


if __name__ == "__main__":
    main()
