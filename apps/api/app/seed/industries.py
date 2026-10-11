"""What some industries add to a demo business: pets and children, on-site jobs, quotes and
events, and a practice's retainers, time, bills and documents."""

import json
import random
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import Connection, text

from app.catalog.verticals import VERTICAL_PACKS
from app.seed.common import _insert

PET_NAMES = ("רקס", "לונה", "מקס", "בל", "צ׳ארלי", "נלה", "רוקי", "שוקו", "לולה", "בונו", "מילו",
             "קיווי", "טופי", "סימבה", "פיצה", "ג׳ינג׳ר")  # fmt: skip
CHILD_NAMES = ("נועה", "איתי", "מאיה", "יואב", "תמר", "אורי", "שירה", "עידו", "ליה", "רועי")
BREEDS = ("מעורב", "פודל", "שיצו", "גולדן רטריבר", "לברדור", "מלטז", "בורדר קולי", "יורקשייר")


def _seed_dependents(
    conn: Connection, tenant_id: UUID, vertical: str, client_ids: list[UUID], rng: random.Random
) -> int:
    """Pets or children for most clients of an industry that keeps them (#43), with the
    industry's details filled in, and each booking for one of its client's dependents."""
    pack = VERTICAL_PACKS[vertical]
    if pack.dependents is None:
        return 0
    names = PET_NAMES if pack.dependents == "pet" else CHILD_NAMES
    rows = []
    for client_id in client_ids:
        if not pack.dependent_required and rng.random() < 0.3:
            continue
        for name in rng.sample(names, k=rng.choices((1, 2, 3), weights=(70, 25, 5))[0]):
            details: dict[str, object] = {}
            for f in pack.dependent_fields:
                if f.kind == "select":
                    details[f.key] = rng.choice(f.options[:2] if f.key == "species" else f.options)
                elif f.key == "breed":
                    details[f.key] = rng.choice(BREEDS)
                elif f.key == "weight_kg":
                    details[f.key] = rng.randint(3, 40)
            years = rng.randint(1, 12)
            rows.append(
                {
                    "tenant_id": tenant_id,
                    "client_id": client_id,
                    "kind": pack.dependents,
                    "name": name,
                    "birth": date.today() - timedelta(days=365 * years + rng.randint(0, 300)),
                    "details": json.dumps(details, ensure_ascii=False),
                }
            )
    _insert(conn, """
        INSERT INTO app.dependents (tenant_id, client_id, kind, name, birth_date, details)
        VALUES (:tenant_id, :client_id, :kind, :name, :birth, CAST(:details AS jsonb))
    """, rows)  # fmt: skip
    # Every booking is for one of its client's pets / children (when they have any).
    conn.execute(
        text("""
            UPDATE app.bookings b SET dependent_id = (
                SELECT d.id FROM app.dependents d
                WHERE d.client_id = b.client_id ORDER BY random() LIMIT 1
            )
            WHERE b.tenant_id = :t
        """),
        {"t": tenant_id},
    )
    return len(rows)


STREETS = ("הרצל", "ויצמן", "ז׳בוטינסקי", "רוטשילד", "בן גוריון", "סוקולוב", "אחד העם", "הנשיא",
           "העצמאות", "המייסדים", "הגפן", "התאנה")  # fmt: skip
CITIES = ("פתח תקווה", "ראש העין", "כפר סבא", "הוד השרון", "רעננה", "תל אביב", "רמת גן", "גבעתיים")
ENTRY_NOTES = ("קוד בשער 1234#", "אינטרקום לא עובד, להתקשר", "חניה ברחוב בלבד", "כלב בחצר, לצלצל",
               None, None, None)  # fmt: skip


def _seed_jobs(
    conn: Connection, tenant_id: UUID, client_ids: list[UUID], rng: random.Random
) -> int:
    """For on-site services (#42): an address per client and every appointment of those
    services a job at its client's address, past ones done and today's on the move."""
    on_site = conn.execute(
        text("SELECT count(*) FROM app.services WHERE tenant_id = :t AND on_site"),
        {"t": tenant_id},
    ).scalar_one()
    if not on_site:
        return 0
    rows = [
        {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "street": f"{rng.choice(STREETS)} {rng.randint(1, 120)}",
            "city": rng.choice(CITIES),
            "details": f"קומה {rng.randint(0, 12)}, דירה {rng.randint(1, 48)}"
            if rng.random() < 0.7
            else None,
            "notes": rng.choice(ENTRY_NOTES),
        }
        for client_id in client_ids
    ]
    _insert(conn, """
        INSERT INTO app.client_addresses (tenant_id, client_id, street, city, details, notes)
        VALUES (:tenant_id, :client_id, :street, :city, :details, :notes)
    """, rows)  # fmt: skip
    return conn.execute(
        text("""
            WITH jobs AS (
                SELECT DISTINCT ON (s.id) s.id, sv.travel_minutes, a.id AS address_id,
                       concat_ws(', ', a.street, a.details, a.city) AS address,
                       CASE WHEN b.status = 'checked_in' THEN 'done'
                            WHEN s.starts_at::date = now()::date AND s.starts_at < now()
                                THEN 'in_progress'
                            WHEN s.starts_at::date = now()::date
                                 AND s.starts_at < now() + interval '1 hour' THEN 'on_the_way'
                            ELSE 'scheduled' END AS job_status
                FROM app.sessions s
                JOIN app.services sv ON sv.id = s.service_id AND sv.on_site
                JOIN app.bookings b ON b.session_id = s.id AND b.status <> 'cancelled'
                JOIN app.client_addresses a ON a.client_id = b.client_id
                WHERE s.tenant_id = :t
                ORDER BY s.id, b.created_at
            )
            UPDATE app.sessions s
            SET travel_minutes = j.travel_minutes, address_id = j.address_id,
                address = j.address, job_status = j.job_status
            FROM jobs j WHERE s.id = j.id
        """),
        {"t": tenant_id},
    ).rowcount


QUOTE_PACKAGES = (
    ("צילום חתונה", (("חבילת יום מלא", 1, 850000), ("שעת צילום נוספת", 2, 60000),
                     ("אלבום מעוצב", 1, 180000))),
    ("צילום בר מצווה", (("צילומי חוץ", 1, 250000), ("צילום האירוע", 1, 450000))),
    ("צילומי משפחה", (("סשן חוץ של שעה", 1, 90000), ("תמונות מעובדות", 20, 3000))),
    ("אירוע חברה", (("צילום כנס חצי יום", 1, 320000), ("עריכה ומסירה מהירה", 1, 80000))),
)  # fmt: skip
PLACES = ("גן אירועים, הרצליה", "אולם ביפו", "בית הכנסת הגדול, רמת גן", "חוף הצוק, תל אביב",
          "מלון בירושלים")  # fmt: skip


def _seed_quotes(
    conn: Connection,
    tenant_id: UUID,
    owner: UUID,
    client_ids: list[UUID],
    pack: object,
    today: date,
    rng: random.Random,
) -> int:
    """Quotes for an industry that works by quotes (#44): drafts, sent, accepted with deposits
    (some fully paid) and events in the coming months, a few declined."""
    if getattr(pack, "category", None) != "events":
        return 0
    count = 0
    for client_id in rng.sample(client_ids, k=min(45, len(client_ids))):
        title, lines = rng.choice(QUOTE_PACKAGES)
        status = rng.choices(("draft", "sent", "accepted", "declined"), weights=(10, 25, 55, 10))[0]
        created = today - timedelta(days=rng.randint(1, 60))
        event = today + timedelta(days=rng.randint(5, 200))
        number = conn.execute(
            text("""
                INSERT INTO app.quote_counters AS c (tenant_id, last) VALUES (:t, 1001)
                ON CONFLICT (tenant_id) DO UPDATE SET last = c.last + 1 RETURNING last
            """),
            {"t": tenant_id},
        ).scalar_one()
        quote_id = conn.execute(
            text("""
                INSERT INTO app.quotes
                    (tenant_id, client_id, number, title, status, currency, deposit_percent,
                     valid_until, event_starts_at, event_place, notes, sent_at, accepted_at,
                     accepted_name, declined_at, created_by, created_at)
                SELECT :t, c.id, :number, :title, :status, 'ILS', 30, :valid, :event,
                       :place, 'כולל עריכה ומסירה תוך 30 יום.',
                       CASE WHEN :status <> 'draft' THEN CAST(:created AS timestamptz) END,
                       CASE WHEN :status = 'accepted'
                            THEN CAST(:created AS timestamptz) + interval '2 days' END,
                       CASE WHEN :status = 'accepted'
                            THEN trim(c.first_name || ' ' || coalesce(c.last_name, '')) END,
                       CASE WHEN :status = 'declined'
                            THEN CAST(:created AS timestamptz) + interval '3 days' END,
                       :owner, :created
                FROM app.clients c WHERE c.id = :client
                RETURNING id
            """),
            {
                "t": tenant_id,
                "client": client_id,
                "number": number,
                "title": title,
                "status": status,
                "valid": created + timedelta(days=30),
                "event": datetime.combine(event, time(17, 0), tzinfo=UTC),
                "place": rng.choice(PLACES),
                "created": datetime.combine(created, time(10, 0), tzinfo=UTC),
                "owner": owner,
            },
        ).scalar_one()
        total = 0
        for position, (description, quantity, price) in enumerate(lines):
            total += quantity * price
            conn.execute(
                text("""
                    INSERT INTO app.quote_lines
                        (tenant_id, quote_id, position, description, quantity, unit_price)
                    VALUES (:t, :q, :p, :d, :n, :u)
                """),
                {
                    "t": tenant_id,
                    "q": quote_id,
                    "p": position,
                    "d": description,
                    "n": quantity,
                    "u": price,
                },
            )
        if status == "accepted":
            payments = [round(total * 0.3)]
            if rng.random() < 0.3:
                payments.append(total - payments[0])  # the balance too
            for i, amount in enumerate(payments):
                conn.execute(
                    text("""
                        INSERT INTO app.payments
                            (tenant_id, client_id, amount, currency, status, provider, method,
                             idempotency_key, quote_id, description, created_at)
                        VALUES (:t, :c, :a, 'ILS', 'succeeded', 'simulated', :m, :k, :q, :d, :at)
                    """),
                    {
                        "t": tenant_id,
                        "c": client_id,
                        "a": amount,
                        "m": "card" if i == 0 else "transfer",
                        "k": f"seed-quote-{quote_id}-{i}",
                        "q": quote_id,
                        "d": f"{title} · {number}",
                        "at": datetime.combine(
                            created + timedelta(days=2 + i * 20), time(12, 0), tzinfo=UTC
                        ),
                    },
                )
        count += 1
    return count


WORK_DONE = ("הנהלת חשבונות חודשית", "דיווח מע״מ", "התאמות בנק", "פגישה עם הלקוח",
             "הכנת דוח רווח והפסד", "תכנון מס", "שיחה עם רשות המסים", "תלושי שכר")  # fmt: skip
DOCUMENTS = (
    ("הסכם התקשרות.pdf", "contract", True, True),
    ("דוח שנתי 2025.pdf", "report", True, False),
    ("טופס 106.pdf", "client_file", False, False),
)
SAMPLE_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]"
    b"/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)


def _seed_practice(
    conn: Connection,
    tenant_id: UUID,
    staff: list[UUID],
    client_ids: list[UUID],
    pack: object,
    today: date,
    rng: random.Random,
) -> int:
    """For industries that bill by time (#45): retainers, three months of time entries, the
    past months billed (most bills paid), and documents (an engagement letter signed, a report
    shared, a client's own paper)."""
    if not getattr(pack, "time_billing", False):
        return 0
    minutes_total = 0
    first_this_month = today.replace(day=1)
    for client_id in client_ids:
        monthly = rng.choice((0, 150000, 250000, 400000))
        rate = rng.choice((30000, 40000, 50000))
        included = 0 if monthly == 0 else rng.choice((240, 480, 600))
        conn.execute(
            text("""
                INSERT INTO app.retainers
                    (tenant_id, client_id, monthly_amount, included_minutes, hourly_rate,
                     currency)
                VALUES (:t, :c, :m, :i, :r, 'ILS')
            """),
            {"t": tenant_id, "c": client_id, "m": monthly, "i": included, "r": rate},
        )
        for back in (2, 1, 0):
            month_start = (first_this_month - timedelta(days=28 * back)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            last_day = min(month_end, today)
            worked = 0
            entry_ids = []
            for _ in range(rng.randint(2, 6)):
                minutes = rng.choice((30, 45, 60, 90, 120, 180))
                day = month_start + timedelta(days=rng.randint(0, (last_day - month_start).days))
                worked += minutes
                entry_ids.append(
                    conn.execute(
                        text("""
                            INSERT INTO app.time_entries
                                (tenant_id, client_id, user_id, day, minutes, description,
                                 billable)
                            VALUES (:t, :c, :u, :d, :m, :w, true) RETURNING id
                        """),
                        {
                            "t": tenant_id,
                            "c": client_id,
                            "u": rng.choice(staff),
                            "d": day,
                            "m": minutes,
                            "w": rng.choice(WORK_DONE),
                        },
                    ).scalar_one()
                )
            minutes_total += worked
            if back == 0:
                continue  # this month is not billed yet
            extra = max(worked - included, 0) if monthly else worked
            lines = ([("ריטיינר", 1, monthly)] if monthly else []) + (
                [("שעות עבודה", round(extra / 60, 2), rate)] if extra else []
            )
            if not lines:
                continue
            number = conn.execute(
                text("""
                    INSERT INTO app.quote_counters AS c (tenant_id, last) VALUES (:t, 1001)
                    ON CONFLICT (tenant_id) DO UPDATE SET last = c.last + 1 RETURNING last
                """),
                {"t": tenant_id},
            ).scalar_one()
            billed_at = datetime.combine(month_end + timedelta(days=1), time(9, 0), tzinfo=UTC)
            bill_id = conn.execute(
                text("""
                    INSERT INTO app.quotes
                        (tenant_id, client_id, number, kind, title, status, currency,
                         deposit_percent, period_start, period_end, sent_at, accepted_at,
                         created_by, created_at)
                    VALUES (:t, :c, :n, 'bill', :title, 'accepted', 'ILS', 100, :s, :e, :at,
                            :at, :u, :at)
                    RETURNING id
                """),
                {
                    "t": tenant_id,
                    "c": client_id,
                    "n": number,
                    "title": f"חשבון {month_start:%m/%Y}",
                    "s": month_start,
                    "e": month_end,
                    "at": billed_at,
                    "u": staff[0],
                },
            ).scalar_one()
            total = 0
            for position, (description, quantity, price) in enumerate(lines):
                total += round(quantity * price)
                conn.execute(
                    text("""
                        INSERT INTO app.quote_lines
                            (tenant_id, quote_id, position, description, quantity, unit_price)
                        VALUES (:t, :q, :p, :d, :n, :u)
                    """),
                    {
                        "t": tenant_id,
                        "q": bill_id,
                        "p": position,
                        "d": description,
                        "n": quantity,
                        "u": price,
                    },
                )
            conn.execute(
                text("UPDATE app.time_entries SET bill_id = :b WHERE id = ANY(:ids)"),
                {"b": bill_id, "ids": entry_ids},
            )
            if back == 2 or rng.random() < 0.7:  # older bills are paid, most recent ones too
                conn.execute(
                    text("""
                        INSERT INTO app.payments
                            (tenant_id, client_id, amount, currency, status, provider, method,
                             idempotency_key, quote_id, description, created_at)
                        VALUES (:t, :c, :a, 'ILS', 'succeeded', 'simulated', 'transfer', :k,
                                :q, :d, :at)
                    """),
                    {
                        "t": tenant_id,
                        "c": client_id,
                        "a": total,
                        "k": f"seed-bill-{bill_id}",
                        "q": bill_id,
                        "d": f"חשבון {month_start:%m/%Y} · {number}",
                        "at": billed_at + timedelta(days=rng.randint(1, 10)),
                    },
                )
        for name, kind, shared, sign in DOCUMENTS:
            if rng.random() < 0.6:
                conn.execute(
                    text("""
                        INSERT INTO app.client_documents
                            (tenant_id, client_id, name, kind, content_type, size, content,
                             shared, uploaded_by_client, sign_requested, signed_at,
                             signed_name)
                        SELECT :t, c.id, :name, :kind, 'application/pdf', :size, :content,
                               :shared, :by_client, :sign,
                               CASE WHEN :sign THEN now() - interval '20 days' END,
                               CASE WHEN :sign
                                    THEN trim(c.first_name || ' ' || coalesce(c.last_name, ''))
                               END
                        FROM app.clients c WHERE c.id = :c
                    """),
                    {
                        "t": tenant_id,
                        "c": client_id,
                        "name": name,
                        "kind": kind,
                        "size": len(SAMPLE_PDF),
                        "content": SAMPLE_PDF,
                        "shared": shared,
                        "by_client": kind == "client_file",
                        "sign": sign,
                    },
                )
    return minutes_total // 60
