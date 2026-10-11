"""Activity on a demo business: reviews, notes, sent messages, court reservations and leads."""

import random
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from app.schedule.scheduling import local_to_utc
from app.seed.common import FIRST_NAMES, LAST_NAMES, TIME_ZONE, Client, _insert

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


MESSAGE_BODIES = {
    "reminder": "היי {first_name}, תזכורת: מחכים לך מחר 🙂",
    "plan_ending": "היי {first_name}, המנוי שלך מסתיים בקרוב. רוצה שנחדש לך?",
    "lead": "היי {first_name}, תודה שפנית אלינו! מתי נוח לך להגיע לשיעור ניסיון?",
    "missing": "היי {first_name}, מזמן לא ראינו אותך! נשמח לראות אותך השבוע.",
}


def _seed_messages(conn: Connection, tenant_id: UUID, owner: UUID, today: date,
                   rng: random.Random) -> None:  # fmt: skip
    """A month of (simulated) WhatsApp messages: one campaign to clients who stopped coming,
    reminders and renewal notes to clients, and first replies to new leads."""

    def recent(days: int) -> datetime:
        return datetime.combine(today - timedelta(days=rng.randint(0, days)),
                                time(rng.randint(8, 20), rng.choice((0, 15, 30, 45))),
                                ZoneInfo(TIME_ZONE))  # fmt: skip

    people = conn.execute(
        text("""
            SELECT id, first_name, phone FROM app.clients
            WHERE tenant_id = :t AND phone IS NOT NULL AND status = 'active'
        """),
        {"t": tenant_id},
    ).all()
    leads = conn.execute(
        text("""
            SELECT id, first_name, phone FROM app.leads
            WHERE tenant_id = :t AND phone IS NOT NULL
        """),
        {"t": tenant_id},
    ).all()
    if not people:
        return
    missing = rng.sample(people, k=min(12, len(people)))
    sent_at = recent(20)
    campaign_id = conn.execute(
        text("""
            INSERT INTO app.campaigns
                (tenant_id, audience, channel, body, recipients, created_by, created_at)
            VALUES (:t, 'inactive', 'whatsapp', :body, :n, :owner, :at) RETURNING id
        """),
        {"t": tenant_id, "body": MESSAGE_BODIES["missing"], "n": len(missing), "owner": owner,
         "at": sent_at},
    ).scalar_one()  # fmt: skip

    def row(person, kind: str, at: datetime, *, lead: bool = False, campaign=None) -> dict:
        return {"tenant_id": tenant_id, "campaign_id": campaign,
                "client_id": None if lead else person.id, "lead_id": person.id if lead else None,
                "to_phone": person.phone,
                "body": MESSAGE_BODIES[kind].replace("{first_name}", person.first_name),
                "status": "failed" if rng.random() < 0.03 else "sent", "owner": owner,
                "at": at}  # fmt: skip

    rows = [row(p, "missing", sent_at, campaign=campaign_id) for p in missing]
    rows += [row(p, rng.choice(("reminder", "plan_ending")), recent(30))
             for p in rng.sample(people, k=min(18, len(people)))]  # fmt: skip
    rows += [row(p, "lead", recent(14), lead=True) for p in rng.sample(leads, k=min(6, len(leads)))]
    _insert(conn, """
        INSERT INTO app.messages
            (tenant_id, campaign_id, client_id, lead_id, channel, to_phone, body, status,
             simulated, created_by, created_at)
        VALUES (:tenant_id, :campaign_id, :client_id, :lead_id, 'whatsapp', :to_phone, :body,
                :status, true, :owner, :at)
    """, rows)  # fmt: skip


def _seed_reservations(
    conn: Connection,
    tenant_id: UUID,
    clients: list[UUID],
    start: date,
    today: date,
    horizon: date,
    rng: random.Random,
) -> int:
    """Courts and rooms by the hour: reservations in their opening hours, busier in the
    evening and at weekends, each with its booking (past ones mostly attended) and, when paid,
    its payment (in the app, or at the venue for some). No two overlap in a room."""
    services = (
        conn.execute(
            text("""
            SELECT s.id, s.name, s.min_minutes, s.max_minutes, s.step_minutes, s.price_per_hour,
                   array_agg(sr.room_id) AS rooms
            FROM app.services s JOIN app.service_rooms sr ON sr.service_id = s.id
            WHERE s.tenant_id = :t AND s.booking_mode = 'resource'
            GROUP BY s.id
        """),
            {"t": tenant_id},
        )
        .mappings()
        .all()
    )
    rooms = {
        row.id: row
        for row in conn.execute(
            text("SELECT id, name, location_id FROM app.rooms WHERE tenant_id = :t AND bookable"),
            {"t": tenant_id},
        )
    }
    hours = {
        (row.room_id, row.weekday): (row.starts, row.ends)
        for row in conn.execute(
            text("SELECT room_id, weekday, starts, ends FROM app.room_hours WHERE tenant_id = :t"),
            {"t": tenant_id},
        )
    }
    by_room = {room: s for s in services for room in s["rooms"]}  # one service per court
    sessions, bookings, payments = [], [], []
    now = datetime.now(UTC)
    day = start
    while day <= horizon:
        weekend = day.weekday() in (4, 5)
        for room_id, service in by_room.items():
            opening = hours.get((room_id, day.weekday()))
            if opening is None:
                continue
            at = datetime.combine(day, opening[0])
            close = datetime.combine(day, opening[1])
            lengths = list(range(service["min_minutes"], service["max_minutes"] + 1,
                                 service["step_minutes"]))  # fmt: skip
            while at < close:
                chance = 0.55 if at.hour >= 17 else 0.3 if weekend or at.hour < 9 else 0.18
                minutes = rng.choice(lengths)
                if at + timedelta(minutes=minutes) > close or rng.random() > chance:
                    at += timedelta(minutes=30)
                    continue
                starts = local_to_utc(day, at.time(), TIME_ZONE)
                ends = starts + timedelta(minutes=minutes)
                price = (service["price_per_hour"] * minutes + 30) // 60
                session_id, booking_id = uuid4(), uuid4()
                client = rng.choice(clients)
                past = ends < now
                made = starts - timedelta(days=rng.randint(0, 6), hours=rng.randint(1, 12))
                sessions.append({
                    "id": session_id, "tenant_id": tenant_id, "service_id": service["id"],
                    "location_id": rooms[room_id].location_id, "room_id": room_id,
                    "starts_at": starts, "ends_at": ends, "price": price, "created_at": made,
                })  # fmt: skip
                no_show = past and rng.random() < 0.04
                bookings.append({
                    "id": booking_id, "tenant_id": tenant_id, "session_id": session_id,
                    "client_id": client,
                    "status": ("no_show" if no_show else "checked_in") if past else "booked",
                    "checked_in_at": starts if past and not no_show else None, "created_at": made,
                })  # fmt: skip
                at_venue = rng.random() < 0.25
                if not at_venue or past:
                    payments.append({
                        "tenant_id": tenant_id, "client_id": client, "amount": price,
                        "provider": "venue" if at_venue else "simulated",
                        "method": rng.choice(("cash", "card")) if at_venue else "card",
                        "key": f"demo-reservation-{booking_id.hex}", "booking_id": booking_id,
                        "description": f"{service['name']} · {rooms[room_id].name} · "
                                       f"{day.strftime('%d/%m')} {at.strftime('%H:%M')}",
                        "location_id": rooms[room_id].location_id,
                        "created_at": starts if at_venue else made,
                    })  # fmt: skip
                at += timedelta(minutes=minutes)
        day += timedelta(days=1)
    _insert(conn, """
        INSERT INTO app.sessions
            (id, tenant_id, service_id, location_id, room_id, capacity, starts_at, ends_at,
             reserved, price_amount, price_currency, created_at, updated_at)
        VALUES (:id, :tenant_id, :service_id, :location_id, :room_id, 1, :starts_at, :ends_at,
                true, :price, 'ILS', :created_at, :created_at)
    """, sessions)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.bookings
            (id, tenant_id, session_id, client_id, status, checked_in_at, created_at, updated_at)
        VALUES (:id, :tenant_id, :session_id, :client_id, :status, :checked_in_at, :created_at,
                :created_at)
    """, bookings)  # fmt: skip
    _insert(conn, """
        INSERT INTO app.payments
            (tenant_id, client_id, amount, currency, status, provider, method, idempotency_key,
             booking_id, description, location_id, created_at)
        VALUES (:tenant_id, :client_id, :amount, 'ILS', 'succeeded', :provider, :method, :key,
                :booking_id, :description, :location_id, :created_at)
    """, payments)  # fmt: skip
    return len(sessions)


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
