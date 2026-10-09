"""One demo business with its branches, staff, timetable, clients, plans and months of history."""

import json
import random
import sys
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.api.modules import set_modules
from app.api.routes import apply_vertical_pack, apply_vertical_rooms
from app.catalog.health import FITNESS_FORM
from app.catalog.verticals import VERTICAL_PACKS
from app.commerce.billing import bill_businesses
from app.commerce.modules import PRESETS
from app.schedule.scheduling import local_to_utc
from app.seed.activity import (
    COACH_NOTES,
    LEAD_INTERESTS,
    REVIEW_COMMENTS,
    _seed_leads,
    _seed_messages,
    _seed_reservations,
)
from app.seed.common import (
    CLASS_HOURS,
    CLIENTS,
    FIRST_NAMES,
    GENERIC_NOTES,
    GENERIC_REVIEWS,
    INSTRUCTORS,
    LAST_NAMES,
    LEADS,
    SOURCE_WEIGHTS,
    SOURCES,
    STUDIO,
    TIME_ZONE,
    WORK_HOURS,
    BusinessSpec,
    Client,
    Entitlement,
    _insert,
    profile_id,
)
from app.seed.industries import _seed_dependents, _seed_jobs, _seed_practice, _seed_quotes


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
    dependents = _seed_dependents(conn, tenant_id, spec.vertical, [c.id for c in clients], rng)
    jobs = _seed_jobs(conn, tenant_id, [c.id for c in clients], rng)
    quotes = _seed_quotes(conn, tenant_id, owner, [c.id for c in clients], pack, today, rng)
    hours = _seed_practice(
        conn, tenant_id, [owner, *instructors], [c.id for c in clients], pack, today, rng
    )
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
    reservations = 0
    if any(s["booking_mode"] == "resource" for s in service_rows):
        apply_vertical_rooms(conn, tenant_id, spec.vertical, "he")
        reservations = _seed_reservations(
            conn, tenant_id, [c.id for c in clients], start, today, horizon, rng
        )
    _seed_messages(conn, tenant_id, owner, today, rng)

    print(
        f"Created demo business {tenant_id} ({spec.name}): {len(branches)} branches, "
        f"{len(clients)} clients, {lead_count} leads, {len(sessions)} sessions, "
        f"{len(entitlement_rows)} plans sold, {len(booking_rows)} bookings, "
        f"{reservations} reservations, {dependents} pets / children, {jobs} on-site jobs, "
        f"{quotes} quotes, {hours} hours logged."
    )
    return tenant_id
