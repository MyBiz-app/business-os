"""Morning scenarios (demo slice D4): the twelve hero clients and the edge cases a business owner
finds when they open the app in the morning.

Everything is computed relative to today, so a demo seeded on any day is fresh. It only adds and
runs once per business: a business that already has a hero client is skipped. Nothing is sent to
anyone; AI proposals are written as pending actions that wait for the owner.

The tennis club's courts (how many per branch) belong to slice D5; the court scenarios here
use whatever courts exist and skip what needs them when there are none.

Not modelled here (the data model has no place for them yet): a coach's licence that expires
in 20 days, a shift nobody covers tomorrow, the cross-business "network" of friends (slice D5).
"""

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Connection, text

from app.schedule.scheduling import local_to_utc
from app.seed.common import TIME_ZONE
from app.seed.roles import role_of
from app.seed.round6 import _team

HERO_KEY = "demo_hero"
RON_EMAIL = "ron.ohayon.demo@example.invalid"


@dataclass
class Ctx:
    conn: Connection
    tenant: UUID
    owner: UUID
    today: date
    rng: random.Random
    locations: list[tuple[UUID, str]]
    team: list[tuple[UUID, UUID]]
    services: list = field(default_factory=list)

    @property
    def now(self) -> datetime:
        return datetime.now(UTC)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _at(ctx: Ctx, offset: int, hour: int, minute: int = 0) -> datetime:
    """A wall-clock time `offset` days from today, in the business's time zone."""
    return local_to_utc(ctx.today + timedelta(days=offset), time(hour, minute), TIME_ZONE)


def _location(ctx: Ctx, *words: str) -> UUID:
    for location_id, name in ctx.locations:
        if any(word in name for word in words):
            return location_id
    return ctx.locations[0][0]


def _service(ctx: Ctx, mode: str | None = None, word: str | None = None) -> UUID:
    rows = [s for s in ctx.services if mode is None or s.booking_mode == mode]
    rows = rows or ctx.services
    if word:
        rows = [s for s in rows if word in s.name] or rows
    return rows[0].id


def _client(
    ctx: Ctx,
    slug: str,
    first: str,
    last: str,
    location: UUID,
    source: str = "other",
    days_ago: int = 90,
    email: str | None = None,
    **fields: object,
) -> UUID:
    phone = f"05{ctx.rng.randint(0, 9)}-{ctx.rng.randint(100, 999)}-{ctx.rng.randint(1000, 9999)}"
    return ctx.conn.execute(
        text("""
            INSERT INTO app.clients
                (tenant_id, first_name, last_name, email, phone, status, source, home_location_id,
                 custom_fields, created_at, updated_at)
            VALUES (:t, :first, :last, :email, :phone, 'active', :source, :loc,
                    CAST(:fields AS jsonb), :created, :created)
            RETURNING id
        """),
        {
            "t": ctx.tenant, "first": first, "last": last, "phone": phone, "source": source,
            "email": email or f"hero.{slug}@example.invalid", "loc": location,
            "fields": _json({HERO_KEY: slug, **fields}),
            "created": ctx.now - timedelta(days=days_ago),
        },
    ).scalar_one()  # fmt: skip


def _note(ctx: Ctx, client: UUID, body: str) -> None:
    ctx.conn.execute(
        text("""
            INSERT INTO app.client_notes (tenant_id, client_id, author_user_id, body)
            VALUES (:t, :c, :u, :body)
        """),
        {"t": ctx.tenant, "c": client, "u": ctx.owner, "body": body},
    )


def _plan(ctx: Ctx, kind: str) -> tuple[UUID, str, int]:
    row = ctx.conn.execute(
        text("""
            SELECT id, name, price_amount FROM app.plans
            WHERE tenant_id = :t AND active AND kind = :k ORDER BY price_amount, id LIMIT 1
        """),
        {"t": ctx.tenant, "k": kind},
    ).first()
    if row is None:  # an industry without that kind of plan: any plan, sold as that kind
        row = ctx.conn.execute(
            text("""
                SELECT id, name, price_amount FROM app.plans
                WHERE tenant_id = :t AND active ORDER BY price_amount, id LIMIT 1
            """),
            {"t": ctx.tenant},
        ).one()
    return row[0], row[1], row[2]


def _entitlement(
    ctx: Ctx,
    client: UUID,
    location: UUID,
    kind: str = "membership",
    started_ago: int = 20,
    ends_in: int = 10,
    credits: int | None = None,
    auto_renew: bool = False,
) -> UUID:
    plan, name, price = _plan(ctx, kind)
    starts, ends = ctx.today - timedelta(days=started_ago), ctx.today + timedelta(days=ends_in)
    renew = auto_renew and kind == "membership"
    entitlement = ctx.conn.execute(
        text("""
            INSERT INTO app.entitlements
                (tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
                 price_amount, price_currency, location_id, billing_cycle, auto_renew,
                 next_billing_on, created_at, updated_at)
            VALUES (:t, :c, :plan, :name, :kind, :credits, :starts, :ends, :price, 'ILS', :loc,
                    CASE WHEN :renew THEN 'monthly' END, :renew,
                    CASE WHEN :renew THEN CAST(:ends AS date) + 1 END, :created, :created)
            RETURNING id
        """),
        {
            "t": ctx.tenant, "c": client, "plan": plan, "name": name, "kind": kind,
            "credits": credits if kind == "punch_card" else None, "starts": starts, "ends": ends,
            "price": price, "loc": location, "renew": renew,
            "created": ctx.now - timedelta(days=started_ago),
        },
    ).scalar_one()  # fmt: skip
    ctx.conn.execute(
        text("""
            INSERT INTO app.payments
                (tenant_id, client_id, entitlement_id, amount, currency, status, provider,
                 method, idempotency_key, location_id, created_at)
            VALUES (:t, :c, :e, :amount, 'ILS', 'succeeded', 'simulated', 'card', :key, :loc,
                    :created)
        """),
        {
            "t": ctx.tenant, "c": client, "e": entitlement, "amount": price, "loc": location,
            "key": f"scn-sale-{entitlement}", "created": ctx.now - timedelta(days=started_ago),
        },
    )  # fmt: skip
    return entitlement


def _session(
    ctx: Ctx,
    location: UUID,
    service: UUID,
    starts: datetime,
    minutes: int = 60,
    capacity: int = 1,
    room: UUID | None = None,
    reserved: bool = False,
    notes: str | None = None,
) -> UUID:
    instructor = next((user for user, where in ctx.team if where == location), None)
    return ctx.conn.execute(
        text("""
            INSERT INTO app.sessions
                (tenant_id, service_id, location_id, room_id, instructor_user_id, capacity,
                 starts_at, ends_at, status, reserved, notes, price_amount, price_currency)
            VALUES (:t, :service, :loc, :room, :instructor, :capacity, :starts,
                    CAST(:starts AS timestamptz) + make_interval(mins => :minutes), 'scheduled',
                    :reserved, :notes, 0, 'ILS')
            RETURNING id
        """),
        {
            "t": ctx.tenant, "service": service, "loc": location, "room": room,
            "instructor": instructor, "capacity": capacity, "starts": starts, "minutes": minutes,
            "reserved": reserved, "notes": notes,
        },
    ).scalar_one()  # fmt: skip


def _book(
    ctx: Ctx,
    session: UUID,
    client: UUID,
    status: str,
    entitlement: UUID | None = None,
    late_cancel: bool = False,
    dependent: UUID | None = None,
) -> UUID:
    return ctx.conn.execute(
        text("""
            INSERT INTO app.bookings
                (tenant_id, session_id, client_id, status, entitlement_id, dependent_id,
                 late_cancel, waitlisted_at, cancelled_at, checked_in_at)
            SELECT :t, s.id, :c, CAST(:status AS text), CAST(:e AS uuid), CAST(:d AS uuid),
                   CAST(:late AS boolean),
                   CASE WHEN CAST(:status AS text) = 'waitlisted'
                        THEN now() - interval '2 days' END,
                   CASE WHEN CAST(:status AS text) = 'cancelled'
                        THEN s.starts_at - interval '3 hours' END,
                   CASE WHEN CAST(:status AS text) = 'checked_in' THEN s.starts_at END
            FROM app.sessions s WHERE s.id = :s
            RETURNING id
        """),
        {"t": ctx.tenant, "s": session, "c": client, "status": status, "e": entitlement,
         "d": dependent, "late": late_cancel},
    ).scalar_one()  # fmt: skip


def _visit(
    ctx: Ctx,
    client: UUID,
    location: UUID,
    service: UUID,
    offset: int,
    hour: int,
    status: str,
    entitlement: UUID | None = None,
    **session: object,
) -> UUID:
    """One session `offset` days from today with one booking; returns the booking."""
    made = _session(ctx, location, service, _at(ctx, offset, hour), **session)  # type: ignore[arg-type]
    return _book(ctx, made, client, status, entitlement)


def _failed_payment(ctx: Ctx, client: UUID, location: UUID, amount: int, days_ago: int = 1) -> None:
    ctx.conn.execute(
        text("""
            INSERT INTO app.payments
                (tenant_id, client_id, amount, currency, status, provider, method,
                 idempotency_key, location_id, description, created_at)
            VALUES (:t, :c, :amount, 'ILS', 'failed', 'simulated', 'card', :key, :loc,
                    'החיוב נכשל: הכרטיס נדחה', :created)
        """),
        {
            "t": ctx.tenant, "c": client, "amount": amount, "loc": location,
            "key": f"scn-failed-{uuid4()}", "created": ctx.now - timedelta(days=days_ago),
        },
    )  # fmt: skip


def _propose(ctx: Ctx, tool: str, payload: dict, preview: dict, risk: str) -> None:
    canonical = json.dumps({"tool": tool, "payload": payload}, sort_keys=True)
    ctx.conn.execute(
        text("""
            INSERT INTO app.pending_actions
                (tenant_id, requested_by, agent_key, tool_name, payload, payload_hash, preview,
                 risk_level, expires_at)
            VALUES (:t, :u, 'front_desk', :tool, CAST(:payload AS jsonb), :hash,
                    CAST(:preview AS jsonb), :risk, now() + interval '2 days')
        """),
        {
            "t": ctx.tenant, "u": ctx.owner, "tool": tool, "payload": _json(payload),
            "hash": hashlib.sha256(canonical.encode()).hexdigest(), "preview": _json(preview),
            "risk": risk,
        },
    )  # fmt: skip


def _name(row: object) -> str:
    return f"{row[0]} {row[1] or ''}".strip()  # type: ignore[index]


def _nearly_empty_card(ctx: Ctx, location: UUID, service: UUID, credits: int, left: int) -> int:
    """A punch card with `left` visits remaining, sold to a client who has no card yet."""
    client = ctx.conn.execute(
        text("""
            SELECT c.id FROM app.clients c
            WHERE c.tenant_id = :t AND c.status = 'active' AND NOT (c.custom_fields ? :key)
              AND NOT EXISTS (SELECT 1 FROM app.entitlements e WHERE e.client_id = c.id)
            ORDER BY c.created_at, c.id LIMIT 1
        """),
        {"t": ctx.tenant, "key": HERO_KEY},
    ).scalar_one_or_none()
    if client is None:
        return 0
    card = _entitlement(ctx, client, location, "punch_card", 60, 30, credits)
    for index in range(credits - left):
        _visit(ctx, client, location, service, -2 - index * 4, 10 + index % 6, "checked_in", card)
    return 1


# --- the hero clients -------------------------------------------------------------------------


def _gym_heroes(ctx: Ctx) -> int:
    ta = _location(ctx, "תל אביב")
    rg = _location(ctx, "רמת גן")
    haifa = _location(ctx, "חיפה")
    jlm = _location(ctx, "ירושלים")
    cls = _service(ctx, "class")
    # Noa signed up yesterday, has no health declaration and a class tonight.
    noa = _client(ctx, "noa", "נועה", "לוי", ta, "instagram", 1)
    _visit(ctx, noa, ta, cls, 0, 21, "booked", _entitlement(ctx, noa, ta, started_ago=1),
           capacity=12)  # fmt: skip
    # Omer hurt his knee at the strength branch and was referred to the clinic.
    omer = _client(ctx, "omer", "עומר", "כהן", ta, "referral", 200)
    _entitlement(ctx, omer, ta, started_ago=40, ends_in=20, auto_renew=True)
    _note(ctx, omer, "נפצע בברך באימון כוח, הופנה לפיזיותרפיה במרחב (פתח תקווה)")
    # Tamar: the pilates membership ends in three days, first on tomorrow's waiting list.
    tamar = _client(ctx, "tamar", "תמר", "אברהם", rg, "walk_in", 150)
    _entitlement(ctx, tamar, rg, started_ago=27, ends_in=3)
    full = _session(ctx, rg, cls, _at(ctx, 1, 18, 30), capacity=2)
    for other in _other_clients(ctx, 2):
        _book(ctx, full, other, "booked")
    _book(ctx, full, tamar, "waitlisted")
    # Yonatan: the last card payment failed, 450 shekels are open.
    yonatan = _client(ctx, "yonatan", "יונתן", "פרץ", haifa, "facebook", 120)
    _entitlement(ctx, yonatan, haifa, started_ago=31, ends_in=0)
    _failed_payment(ctx, yonatan, haifa, 45000)
    # Dana: two children at the martial arts branch, one without a medical approval.
    dana = _client(ctx, "dana", "דנה", "שגיא", jlm, "referral", 180)
    for name, born, belt, approved, notes in (
        ("נועם", 9, "צהובה", True, "עלה חגורה בשבוע שעבר"),
        ("יובל", 7, "לבנה", False, "חסר אישור רפואי"),
    ):
        ctx.conn.execute(
            text("""
                INSERT INTO app.dependents (tenant_id, client_id, kind, name, birth_date, details,
                                            notes)
                VALUES (:t, :c, 'child', :name, :born, CAST(:details AS jsonb), :notes)
            """),
            {
                "t": ctx.tenant, "c": dana, "name": name,
                "born": ctx.today.replace(year=ctx.today.year - born) - timedelta(days=40),
                "details": _json({"belt": belt, "medical_approval": approved}), "notes": notes,
            },
        )  # fmt: skip
    _failed_payment(ctx, dana, jlm, 28000, 2)
    _ron(ctx, ta, cls)
    # Itai: an Instagram lead who asked to be called back yesterday; nobody did.
    itai_phone = "052-555-0142"
    ctx.conn.execute(
        text("""
            INSERT INTO app.leads (tenant_id, first_name, last_name, phone, interest, source, stage,
                                   follow_up_on, owner_user_id, created_at, updated_at,
                                   stage_changed_at)
            VALUES (:t, 'איתי', 'רוזן', :phone, 'ביקש שיחזרו אליו אתמול, אף אחד לא חזר',
                    'instagram', 'new', :due, :u, now() - interval '2 days',
                    now() - interval '2 days', now() - interval '2 days')
        """),
        {"t": ctx.tenant, "phone": itai_phone, "due": ctx.today - timedelta(days=1),
         "u": ctx.owner},
    )  # fmt: skip
    _whatsapp_waiting(ctx, itai_phone, "היי, ראיתי אתכם באינסטגרם. אפשר שיחזרו אליי?", 26)
    # Maya asked to freeze her membership for a trip and waits for approval.
    maya = _client(ctx, "maya", "מאיה", "בירן", rg, "app", 100)
    entitlement = _entitlement(ctx, maya, rg, started_ago=25, ends_in=20)
    _freeze_request(ctx, maya, entitlement)
    return 8


def _other_clients(ctx: Ctx, count: int) -> list[UUID]:
    return list(
        ctx.conn.execute(
            text("""
                SELECT id FROM app.clients
                WHERE tenant_id = :t AND status = 'active' AND NOT (custom_fields ? :key)
                ORDER BY created_at, id LIMIT :n
            """),
            {"t": ctx.tenant, "key": HERO_KEY, "n": count},
        ).scalars()
    )


def _freeze_request(ctx: Ctx, client: UUID, entitlement: UUID) -> None:
    ctx.conn.execute(
        text("""
            INSERT INTO app.tenant_freeze_rules
                (tenant_id, allow_requests, min_days, max_days, yearly_bank_days, notice_days,
                 auto_approve_reasons)
            VALUES (:t, true, 3, 30, 45, 1, ARRAY['illness', 'reserve_duty'])
            ON CONFLICT (tenant_id) DO NOTHING
        """),
        {"t": ctx.tenant},
    )
    ctx.conn.execute(
        text("""
            INSERT INTO app.freeze_requests
                (tenant_id, client_id, entitlement_id, starts_on, ends_on, reason, note, status)
            VALUES (:t, :c, :e, :s, :end, 'travel', 'טיסה לחו״ל', 'pending')
        """),
        {"t": ctx.tenant, "c": client, "e": entitlement, "s": ctx.today + timedelta(days=5),
         "end": ctx.today + timedelta(days=14)},
    )  # fmt: skip


def _whatsapp_waiting(ctx: Ctx, phone: str, body: str, hours_ago: int) -> None:
    ctx.conn.execute(
        text("""
            INSERT INTO app.whatsapp_inbox
                (tenant_id, provider, provider_ref, from_phone, body, status, received_at)
            VALUES (:t, 'simulated', :ref, :phone, :body, 'received',
                    now() - make_interval(hours => :h))
        """),
        {"t": ctx.tenant, "ref": f"scn-{uuid4()}", "phone": phone, "body": body, "h": hours_ago},
    )


def _courts_heroes(ctx: Ctx) -> int:
    herzliya = _location(ctx, "הרצליה")
    rishon = _location(ctx, "ראשון")
    service = _service(ctx, "resource")
    rooms = ctx.conn.execute(
        text("""
            SELECT r.id, r.location_id FROM app.rooms r
            JOIN app.service_rooms sr ON sr.room_id = r.id AND sr.service_id = :s
            WHERE r.tenant_id = :t AND r.bookable ORDER BY r.location_id, r.name
        """),
        {"t": ctx.tenant, "s": service},
    ).all()
    herzliya_rooms = [room for room, where in rooms if where == herzliya]
    # Ariel plays every Tuesday at 19:00; three past weeks and the coming three.
    ariel = _client(ctx, "ariel", "אריאל", "גבאי", herzliya, "referral", 200)
    card = _entitlement(ctx, ariel, herzliya, "punch_card", 45, 45, 10)
    tuesday = ctx.today + timedelta(days=(1 - ctx.today.weekday()) % 7)
    booked = 0
    for week in range(-3, 4):
        day = tuesday + timedelta(days=7 * week)
        start = local_to_utc(day, time(19), TIME_ZONE)
        room = _free_room(ctx, herzliya_rooms, start, start + timedelta(hours=1))
        if room is None:
            continue
        made = _session(ctx, herzliya, service, start, 60, 1, room, True)
        past = start < ctx.now
        _book(ctx, made, ariel, "checked_in" if past else "booked", card if past else None)
        booked += 1
    # Tomorrow evening it rains: the agent proposes moving the open-air games.
    tomorrow = ctx.conn.execute(
        text("""
            SELECT b.id, c.first_name, c.last_name FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.clients c ON c.id = b.client_id
            WHERE b.tenant_id = :t AND b.status = 'booked' AND s.reserved AND s.location_id = :l
              AND s.starts_at >= :from AND s.starts_at < :to
            ORDER BY s.starts_at, b.id LIMIT 4
        """),
        {"t": ctx.tenant, "l": herzliya, "from": _at(ctx, 1, 17), "to": _at(ctx, 1, 23)},
    ).all()
    for booking, first, last in tomorrow:
        _propose(
            ctx, "cancel_booking", {"booking_id": str(booking)},
            {"kind": "cancel_booking", "client": _name((first, last)), "reason": "תחזית גשם"},
            "sensitive",
        )  # fmt: skip
    # Court 3 in Herzliya is closed for repairs this week: its free hours are blocked.
    if len(herzliya_rooms) >= 3:
        for day in range(0, 7):
            for hour in range(7, 23):
                start = _at(ctx, day, hour)
                if (
                    start < ctx.now
                    or _free_room(ctx, herzliya_rooms[2:3], start, start + timedelta(hours=1))
                    is None
                ):
                    continue
                _session(ctx, herzliya, service, start, 60, 1, herzliya_rooms[2], True,
                         "מגרש סגור לשיפוץ")  # fmt: skip
    # A 10-hour card with one hour left.
    _nearly_empty_card(ctx, herzliya, service, 10, 1)
    ron = _client(ctx, "ron", "רון", "אוחיון", rishon, "referral", 150, email=RON_EMAIL)
    membership = _entitlement(ctx, ron, rishon, started_ago=25, ends_in=5, auto_renew=True)
    rishon_rooms = [room for room, where in rooms if where == rishon]
    for offset, hour in ((-9, 20), (-2, 20), (3, 20)):
        start = _at(ctx, offset, hour)
        room = _free_room(ctx, rishon_rooms, start, start + timedelta(hours=1))
        if room is not None:
            made = _session(ctx, rishon, service, start, 60, 1, room, True)
            _book(ctx, made, ron, "checked_in" if offset < 0 else "booked", membership)
    return booked + 1 + len(tomorrow)


def _free_room(ctx: Ctx, rooms: list[UUID], start: datetime, end: datetime) -> UUID | None:
    for room in rooms:
        clash = ctx.conn.execute(
            text("""
                SELECT 1 FROM app.sessions
                WHERE room_id = :r AND reserved AND status = 'scheduled'
                  AND tstzrange(starts_at, ends_at) && tstzrange(:a, :b) LIMIT 1
            """),
            {"r": room, "a": start, "b": end},
        ).first()
        if clash is None:
            return room
    return None


def _barber_heroes(ctx: Ctx) -> int:
    tlv = _location(ctx, "תל אביב", "פלורנטין")
    ashdod = _location(ctx, "אשדוד")
    cut = _service(ctx, "appointment", "תספורת")
    # Lior missed three appointments in a row: a deposit is now required.
    lior = _client(ctx, "lior", "ליאור", "מזרחי", tlv, "walk_in", 150, deposit_required=True)
    for offset in (-21, -14, -7):
        _visit(ctx, lior, tlv, cut, offset, 18, "no_show", minutes=30)
    _note(ctx, lior, "3 אי־הגעות ברצף. דורש מקדמה בתור הבא")
    # Gali left a two-star review that nobody answered.
    gali = _client(ctx, "gali", "גלי", "עמר", ashdod, "google", 120)
    booking = _visit(ctx, gali, ashdod, cut, -3, 11, "checked_in", minutes=30)
    ctx.conn.execute(
        text("""
            INSERT INTO app.reviews (tenant_id, client_id, booking_id, service_id, rating, comment)
            SELECT :t, :c, b.id, s.service_id, 2, 'חיכיתי 40 דקות והתספורת לא כמו שביקשתי'
            FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id WHERE b.id = :b
        """),
        {"t": ctx.tenant, "c": gali, "b": booking},
    )
    # An appointment at 10:00 today where nobody showed up.
    stranger = _other_clients(ctx, 1)
    if stranger:
        past = _at(ctx, 0, 10) < ctx.now
        _visit(ctx, stranger[0], tlv, cut, 0, 10, "no_show" if past else "booked", minutes=30)
    # The tenth haircut is free: a loyalty card with one visit left.
    _nearly_empty_card(ctx, tlv, cut, 10, 1)
    return 6 + _ron(ctx, tlv, cut, 1)


def _clinic_heroes(ctx: Ctx) -> int:
    pt = _location(ctx, "פתח תקווה")
    ks = _location(ctx, "כפר סבא")
    visit = _service(ctx, "appointment")
    # Omer's ten treatments: eight done, two left.
    omer = _client(ctx, "omer", "עומר", "כהן", pt, "referral", 60)
    card = _entitlement(ctx, omer, pt, "punch_card", 55, 35, 10)
    for index in range(8):
        _visit(ctx, omer, pt, visit, -3 - index * 6, 9 + index % 5, "checked_in", card)
    _visit(ctx, omer, pt, visit, 2, 9, "booked", card)
    _note(ctx, omer, "הופנה מחדר הכושר אחרי פגיעה בברך. נותרו 2 טיפולים בסדרה, צריך לחדש")
    # Shira has an appointment tomorrow and the health fund referral is missing.
    shira = _client(ctx, "shira", "שירה", "דהן", ks, "website", 30, referral="missing")
    _visit(ctx, shira, ks, visit, 1, 10, "booked")
    _note(ctx, shira, "חסרה הפניה מקופת החולים לפגישה מחר")
    # A late cancellation, less than 24 hours before the visit.
    late = _other_clients(ctx, 1)
    if late:
        made = _session(ctx, ks, visit, _at(ctx, 1, 8))
        _book(ctx, made, late[0], "cancelled", late_cancel=True)
    return 5 + _ron(ctx, ks, visit, 1)


def _ron(ctx: Ctx, location: UUID, service: UUID, capacity: int = 12) -> int:
    """Ron Ohayon is a client of every business: he trains, plays tennis, gets a haircut and
    sees the dietitian. The same email in each business lets slice D5 link them to one account."""
    ron = _client(ctx, "ron", "רון", "אוחיון", location, "referral", 150, email=RON_EMAIL)
    card = _entitlement(ctx, ron, location, started_ago=25, ends_in=5, auto_renew=True)
    for offset in (-9, -2):
        _visit(ctx, ron, location, service, offset, 18, "checked_in", card, capacity=capacity)
    _visit(ctx, ron, location, service, 3, 18, "booked", card, capacity=capacity)
    return 1


# --- edge cases that every business has -------------------------------------------------------


def _expiring_memberships(ctx: Ctx) -> int:
    """Memberships that end this week and were not renewed, with a renewal message waiting."""
    rows = ctx.conn.execute(
        text("""
            SELECT e.id, c.id, c.first_name, c.last_name FROM app.entitlements e
            JOIN app.clients c ON c.id = e.client_id
            WHERE e.tenant_id = :t AND e.status = 'active' AND e.kind = 'membership'
              AND e.ends_on >= :today + 10 AND e.starts_on < :today
              AND NOT (c.custom_fields ? :key)
              AND NOT EXISTS (SELECT 1 FROM app.bookings b
                              JOIN app.sessions s ON s.id = b.session_id
                              WHERE b.entitlement_id = e.id AND s.starts_at > :today + 1)
            ORDER BY e.created_at, e.id LIMIT 4
        """),
        {"t": ctx.tenant, "today": ctx.today, "key": HERO_KEY},
    ).all()
    for index, (entitlement, client, first, last) in enumerate(rows):
        ctx.conn.execute(
            text("""
                UPDATE app.entitlements SET ends_on = :end, auto_renew = false,
                       ending_notified_at = NULL, updated_at = now()
                WHERE id = :e
            """),
            {"end": ctx.today + timedelta(days=index + 1), "e": entitlement},
        )
        if index < 3:
            body = "היי, המנוי שלך מסתיים בקרוב. רוצה לחדש?"
            _propose(
                ctx, "send_message",
                {"client_id": str(client), "channel": "whatsapp", "body": body},
                {"kind": "send_message", "client": _name((first, last)), "channel": "whatsapp",
                 "body": body}, "sensitive",
            )  # fmt: skip
    return len(rows)


def _open_debts(ctx: Ctx) -> int:
    rows = ctx.conn.execute(
        text("""
            SELECT c.id, coalesce(c.home_location_id, :loc) FROM app.clients c
            WHERE c.tenant_id = :t AND c.status = 'active' AND NOT (c.custom_fields ? :key)
              AND EXISTS (SELECT 1 FROM app.entitlements e WHERE e.client_id = c.id
                          AND e.status = 'active' AND e.ends_on >= :today)
            ORDER BY c.created_at DESC, c.id LIMIT 2
        """),
        {"t": ctx.tenant, "key": HERO_KEY, "today": ctx.today, "loc": ctx.locations[0][0]},
    ).all()
    for (client, location), amount in zip(rows, (18000, 29000), strict=False):
        _failed_payment(ctx, client, location, amount, 2)
    return len(rows)


def _yesterday(ctx: Ctx) -> int:
    """No-shows and late cancellations from yesterday's sessions."""
    start, end = _at(ctx, -1, 0), _at(ctx, 0, 0)
    bookings = ctx.conn.execute(
        text("""
            SELECT b.id FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
            WHERE b.tenant_id = :t AND b.status = 'checked_in' AND s.starts_at >= :a
              AND s.starts_at < :b
            ORDER BY s.starts_at, b.id LIMIT 5
        """),
        {"t": ctx.tenant, "a": start, "b": end},
    ).scalars().all()  # fmt: skip
    for index, booking in enumerate(bookings):
        if index < 3:
            sql = "UPDATE app.bookings SET status = 'no_show', checked_in_at = NULL WHERE id = :b"
        else:
            sql = """
                UPDATE app.bookings b SET status = 'cancelled', late_cancel = true,
                       cancelled_at = s.starts_at - interval '2 hours', checked_in_at = NULL
                FROM app.sessions s WHERE s.id = b.session_id AND b.id = :b
            """
        ctx.conn.execute(text(sql), {"b": booking})
    # The owner waives the last late cancellation (the visit is given back). Round 7 gives
    # visits back too; having one here keeps it from doing so again on a later run.
    if len(bookings) > 3:
        ctx.conn.execute(
            text("""
                UPDATE app.bookings SET credit_released = true, waived_by = :u, waived_at = now(),
                       waive_reason = 'תקלה בתחבורה, ויתרנו על הביטול המאוחר'
                WHERE id = :b
                  AND NOT EXISTS (SELECT 1 FROM app.bookings
                                  WHERE tenant_id = :t AND credit_released)
            """),
            {"u": ctx.owner, "b": bookings[-1], "t": ctx.tenant},
        )
    return len(bookings)


def _birthdays(ctx: Ctx) -> int:
    clients = _other_clients(ctx, 3)
    for client, age in zip(clients, (24, 37, 52), strict=False):
        day = 28 if (ctx.today.month, ctx.today.day) == (2, 29) else ctx.today.day
        ctx.conn.execute(
            text("UPDATE app.clients SET date_of_birth = :d WHERE id = :c"),
            {"d": date(ctx.today.year - age, ctx.today.month, day), "c": client},
        )
    return len(clients)


def _late_leads(ctx: Ctx) -> int:
    for index, (name, interest, source) in enumerate(
        (("מורן", "ביקשה הצעת מחיר ולא קיבלה", "google"), ("עידו", "השאיר פרטים באתר", "website"))
    ):
        due = ctx.today - timedelta(days=2 + index * 2)
        ctx.conn.execute(
            text("""
                INSERT INTO app.leads (tenant_id, first_name, phone, interest, source, stage,
                                       follow_up_on, owner_user_id, created_at, updated_at,
                                       stage_changed_at)
                VALUES (:t, :name, :phone, :interest, :source, 'new', :due, :u,
                        now() - interval '5 days', now() - interval '5 days',
                        now() - interval '5 days')
            """),
            {"t": ctx.tenant, "name": name, "interest": interest, "source": source, "due": due,
             "phone": f"05{ctx.rng.randint(0, 9)}-{ctx.rng.randint(100, 999)}-"
                      f"{ctx.rng.randint(1000, 9999)}", "u": ctx.owner},
        )  # fmt: skip
    return 2


def _promo(ctx: Ctx) -> int:
    return ctx.conn.execute(
        text("""
            INSERT INTO app.promo_codes (tenant_id, code, percent_off, starts_on, ends_on, active)
            VALUES (:t, 'LASTCALL', 15, :start, :end, true)
            ON CONFLICT (tenant_id, code) DO NOTHING
        """),
        {"t": ctx.tenant, "start": ctx.today - timedelta(days=14),
         "end": ctx.today + timedelta(days=1)},
    ).rowcount  # fmt: skip


def _waiting_message(ctx: Ctx) -> int:
    row = ctx.conn.execute(
        text("""
            SELECT phone FROM app.clients
            WHERE tenant_id = :t AND status = 'active' AND phone IS NOT NULL
              AND NOT (custom_fields ? :key)
            ORDER BY created_at DESC, id LIMIT 1
        """),
        {"t": ctx.tenant, "key": HERO_KEY},
    ).scalar_one_or_none()
    if row is None:
        return 0
    _whatsapp_waiting(ctx, row, "היי, אפשר להזיז את התור שלי למחר?", 3)
    return 1


def _staff(ctx: Ctx) -> int:
    """A time-off request that waits, and someone who forgot to clock out yesterday."""
    if len(ctx.team) < 2:
        return 0
    asker, _ = ctx.team[0]
    added = 0
    if not ctx.conn.execute(
        text("SELECT 1 FROM app.time_off_requests WHERE tenant_id = :t AND status = 'pending'"),
        {"t": ctx.tenant},
    ).first():
        ctx.conn.execute(
            text("""
                INSERT INTO app.time_off_requests (tenant_id, user_id, starts_on, ends_on, reason,
                                                   status)
                VALUES (:t, :u, :s, :e, 'חופשה משפחתית', 'pending')
            """),
            {"t": ctx.tenant, "u": asker, "s": ctx.today + timedelta(days=9),
             "e": ctx.today + timedelta(days=11)},
        )  # fmt: skip
        added += 1
    open_now = set(
        ctx.conn.execute(
            text(
                "SELECT user_id FROM app.time_clock_entries "
                "WHERE tenant_id = :t AND clock_out IS NULL"
            ),
            {"t": ctx.tenant},
        ).scalars()
    )
    forgetful = next(((user, where) for user, where in ctx.team if user not in open_now), None)
    if forgetful is None:
        return added
    ctx.conn.execute(
        text("""
            INSERT INTO app.time_clock_entries (tenant_id, user_id, location_id, clock_in, source)
            VALUES (:t, :u, :l, :at, 'clock')
        """),
        {"t": ctx.tenant, "u": forgetful[0], "l": forgetful[1], "at": _at(ctx, -1, 8)},
    )
    return added + 1


HEROES = {
    "gym": _gym_heroes,
    "courts": _courts_heroes,
    "barber": _barber_heroes,
    "clinic": _clinic_heroes,
}


def seed_scenarios(
    conn: Connection, tenant_id: UUID, tenant_name: str, today: date
) -> dict[str, int]:
    """Adds the hero clients (for the kinds of business that have them) and the morning edge
    cases to one business; returns what was added per area. Runs once per business."""
    # Done already when the business has a hero client or the "last call" promo code.
    found = conn.execute(
        text("""
            SELECT 1 FROM app.clients WHERE tenant_id = :t AND custom_fields ? :key
            UNION ALL
            SELECT 1 FROM app.promo_codes WHERE tenant_id = :t AND code = 'LASTCALL' LIMIT 1
        """),
        {"t": tenant_id, "key": HERO_KEY},
    ).first()
    role = role_of(conn, tenant_id)
    if found is not None or role is None:
        return {}
    owner = conn.execute(
        text("""
            SELECT user_id FROM app.tenant_members
            WHERE tenant_id = :t AND role = 'owner' ORDER BY created_at LIMIT 1
        """),
        {"t": tenant_id},
    ).scalar_one()
    locations = [
        (row[0], row[1])
        for row in conn.execute(
            text("SELECT id, name FROM app.locations WHERE tenant_id = :t ORDER BY created_at, id"),
            {"t": tenant_id},
        )
    ]
    services = conn.execute(
        text("""
            SELECT id, name, booking_mode FROM app.services
            WHERE tenant_id = :t AND active ORDER BY created_at, id
        """),
        {"t": tenant_id},
    ).all()
    if not locations or not services:
        return {}
    ctx = Ctx(conn, tenant_id, owner, today, random.Random(tenant_id.int ^ 11), locations,
              _team(conn, tenant_id), list(services))  # fmt: skip
    counts: dict[str, int] = {}
    if role in HEROES and role != "salon":
        counts["heroes"] = HEROES[role](ctx)
    for key, step in (
        ("expiring", _expiring_memberships),
        ("debts", _open_debts),
        ("yesterday", _yesterday),
        ("birthdays", _birthdays),
        ("late_leads", _late_leads),
        ("promo", _promo),
        ("waiting_message", _waiting_message),
        ("staff", _staff),
    ):
        counts[key] = step(ctx)
    return counts
