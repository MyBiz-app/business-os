"""What round 7 adds to a demo business, so every screen has something to show.

Round 6 filled pay, hours, a payroll run and a move. This layer fills the rest of what a business
can open: quotes and events, branded documents, promo codes and plan freezes, AI conversations and
actions waiting for approval, announcements with consent, the team's planning (templates, swaps,
time off, coverage, closed days, roles, pay components), a website order, WhatsApp chats, client
addresses, children, friends and an audit trail.

It only adds and is safe to run again: every area first checks whether the business already has
rows of its kind and skips if so, so a business with real activity is never touched. Nothing is
sent to anyone and no AI model is called (conversations and actions are written as data).

`NO_DEMO` lists the tenant tables that deliberately have no demo rows, each with a reason; a test
fails when a new table appears that is neither filled here nor listed there.

Features that are not on main yet are marked `HOOK` below: when they land, fill them here.
"""

import hashlib
import json
import random
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import Connection, text

from app.api.issued_documents import IssueRequest, LineIn, issue
from app.seed.round6 import _as_tenant, _month, _team
from app.websites.brief import Brief
from app.websites.pricing import price_for

GYM_NETWORK = "Adir fitness"
SALON = "Studio Bloom"
PIZZA = "Urban Slice"

# Tenant tables that have no demo rows on purpose (table -> why).
NO_DEMO: dict[str, str] = {
    "ai_agent_avatars": "uploaded images of custom agents; the demo agents use presets",
    "checkouts": "payment-provider sessions; paid providers stay off until go-live",
    "client_documents": "files a client uploads; the demo has no real documents to show",
    "client_locations": "a client's saved places in the client app; added by the person",
    "client_social": "a client's own social links, entered by the client",
    "contact_requests": "leads from the public MyBiz site; they belong to the platform demo",
    "data_exports": "privacy exports are files made on request",
    "form101_forms": "answers are encrypted with the business key, filled in by the employee",
    "import_batch_items": "created by a real import run, undone or kept by the owner",
    "import_batches": "created by a real import run; the move session shows the flow",
    "invitations": "live sign-up links that would email a real address",
    "mcp_connections": "tokens of connected AI tools; secrets are never seeded",
    "payslip_corrections": "need a paid run; the demo runs are not paid",
    "person_identities": "ID numbers, written only through the encrypted identity form",
    "platform_ai_pauses": "set by the MyBiz team in the console",
    "product_events": "usage analytics of real visits",
    "retainers": "only for industries that bill by time, none of the curated three",
    "room_hours": "only for industries that rent rooms, none of the curated three",
    "service_rooms": "only for industries that rent rooms, none of the curated three",
    "social_pending": "OAuth candidates that wait for a real sign-in with the network",
    "support_grants": "temporary access the owner gives the MyBiz team",
    "tenant_integrations": "provider credentials; secrets are never seeded",
    "time_entries": "billed hours of time-based businesses, none of the curated three",
}

# HOOK: features still in the merge queue when this layer was written. When one lands, add its
# demo rows here (and remove it from this list); the coverage test already fails for its new
# tenant tables until it is filled or listed in NO_DEMO.
PENDING_FEATURES = (
    "R30 waitlist 2.0 (range, day, appointments, resources)",
    "R31 staff over capacity",
    "R32 business cancellation policy",
    "R33 MyBiz subscription cancellation",
    "R35 branches map",
    "R37b MCP connector for ChatGPT",
    "R28 solo mode (one business without staff)",
    "R25a / R25b site-only track and the CRM website area",
)

QUOTES = {
    GYM_NETWORK: (
        (
            "סדנת כושר לחברה",
            "משרדי החברה, תל אביב",
            (("סדנת כושר קבוצתית", 1, 180_000), ("מאמן נוסף", 2, 40_000)),
        ),
        (
            "ריטריט קרוספיט לצוות",
            "חוף הים, הרצליה",
            (("יום קרוספיט מלא", 1, 350_000), ("ארוחת בוקר", 20, 4_500)),
        ),
        ("חבילת אימונים לעובדי הייטק", "קמפוס החברה", (("אימון קבוצתי שבועי", 8, 25_000),)),
        ("יום ספורט משפחתי", "פארק הירקון", (("הפעלה למשפחות", 1, 120_000),)),
    ),
    SALON: (
        (
            "כלה ושושבינות",
            "הסלון, סניף מרכז",
            (("תסרוקת כלה", 1, 120_000), ("תסרוקת שושבינה", 4, 35_000)),
        ),
        ("צילומי אופנה", "אולפן צילום, יפו", (("סטיילינג שיער", 3, 60_000),)),
        ("ערב בנות", "הסלון", (("החלקה ותסרוקת", 6, 45_000),)),
        ("חתונה בגן אירועים", "גן אירועים, כפר סבא", (("צוות עיצוב שיער", 1, 280_000),)),
    ),
    PIZZA: (
        (
            "קייטרינג לחברה",
            "משרדי החברה, רמת גן",
            (("פיצה משפחתית", 30, 6_500), ("סלט גדול", 6, 9_000)),
        ),
        ("יום הולדת בפיצרייה", "הסניף", (("מנת ילדים", 12, 4_200), ("עוגה", 1, 15_000))),
        ("אירוע חברה בחוץ", "פארק הירקון", (("עמדת פיצה חיה", 1, 220_000),)),
        ("ארוחת צוות", "הסניף", (("פיצה אישית", 15, 5_500),)),
    ),
}
QUOTE_STATUSES = ("draft", "sent", "accepted", "declined")

CHATS = {
    GYM_NETWORK: (
        "chief",
        "כמה לקוחות פעילים יש לנו החודש?",
        "יש כרגע {n} לקוחות עם מנוי פעיל. רוצה פירוט לפי סניף?",
    ),
    SALON: ("secretary", "מה יש ביומן מחר?", "מחר יש {n} תורים. הראשון בתשע בבוקר. להציג את כולם?"),
    PIZZA: (
        "analyst",
        "איזה סניף מכר הכי הרבה השבוע?",
        "הסניף המרכזי מוביל השבוע. אפשר להשוות בין הסניפים לפי יום.",
    ),
}
MORE_CHATS = (
    (
        "marketing",
        "תכין לי הודעה על מבצע סוף חודש",
        "הנה טיוטה קצרה להודעה. שמרתי אותה כטיוטה ולא נשלח דבר.",
    ),
    (
        "care",
        "מי מהלקוחות לא הגיע בחודש האחרון?",
        "זיהיתי לקוחות שלא הגיעו שלושה שבועות. להכין להם הודעה אישית?",
    ),
    (
        "finance",
        "כמה הכנסנו החודש לעומת החודש שעבר?",
        "ההכנסות החודש גבוהות מהחודש שעבר. פירוט לפי שירות בדוח המספרים.",
    ),
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _has(conn: Connection, table: str, tenant_id: UUID) -> bool:
    """Whether the business already has rows in one of this module's own tables."""
    assert table.isidentifier()  # a table name written in this file, never user input
    found = conn.execute(
        text("SELECT 1 FROM app." + table + " WHERE tenant_id = :t LIMIT 1"), {"t": tenant_id}
    ).first()
    return found is not None


def _clients(conn: Connection, tenant_id: UUID, limit: int) -> list:
    return list(
        conn.execute(
            text("""
                SELECT id, first_name, last_name, email, phone FROM app.clients
                WHERE tenant_id = :t AND status = 'active' AND erased_at IS NULL
                ORDER BY created_at, id LIMIT :n
            """),
            {"t": tenant_id, "n": limit},
        ).all()
    )


def _quotes(
    conn: Connection,
    tenant_id: UUID,
    owner: UUID,
    currency: str,
    name: str,
    clients: list,
    today: date,
    rng: random.Random,
) -> int:
    """Quotes and events in every status, with lines, an event date and place, and the counter."""
    if _has(conn, "quotes", tenant_id) or name not in QUOTES:
        return 0
    for number, ((title, place, lines), status) in enumerate(
        zip(QUOTES[name], QUOTE_STATUSES, strict=True), start=1
    ):
        client = clients[(number * 3) % len(clients)]
        sent = (
            None
            if status == "draft"
            else datetime.now().astimezone() - timedelta(days=rng.randint(3, 20))
        )
        quote_id = conn.execute(
            text("""
                INSERT INTO app.quotes
                    (tenant_id, client_id, number, title, status, currency, deposit_percent,
                     valid_until, event_starts_at, event_place, notes, sent_at, accepted_at,
                     accepted_name, declined_at, created_by)
                VALUES (:t, :c, :n, :title, :status, :currency, :deposit, :valid, :event, :place,
                        :notes, :sent, :accepted, :accepted_name, :declined, :owner)
                RETURNING id
            """),
            {
                "t": tenant_id,
                "c": client[0],
                "n": number,
                "title": title,
                "status": status,
                "currency": currency,
                "deposit": 30 if status != "declined" else 0,
                "valid": today + timedelta(days=30),
                "event": datetime.combine(
                    today + timedelta(days=14 + number * 9), time(18, 0)
                ).astimezone(),
                "place": place,
                "notes": "הצעה לדוגמה (נתוני דמו)",
                "sent": sent,
                "accepted": sent + timedelta(days=2) if status == "accepted" else None,
                "accepted_name": f"{client[1]} {client[2] or ''}".strip()
                if status == "accepted"
                else None,
                "declined": sent + timedelta(days=4) if status == "declined" else None,
                "owner": owner,
            },
        ).scalar_one()
        for position, (description, quantity, unit_price) in enumerate(lines, start=1):
            conn.execute(
                text("""
                    INSERT INTO app.quote_lines
                        (tenant_id, quote_id, position, description, quantity, unit_price)
                    VALUES (:t, :q, :p, :d, :qty, :price)
                """),
                {
                    "t": tenant_id,
                    "q": quote_id,
                    "p": position,
                    "d": description,
                    "qty": quantity,
                    "price": unit_price,
                },
            )
    conn.execute(
        text("""
            INSERT INTO app.quote_counters (tenant_id, last) VALUES (:t, :n)
            ON CONFLICT (tenant_id) DO UPDATE SET last = greatest(app.quote_counters.last, :n)
        """),
        {"t": tenant_id, "n": len(QUOTE_STATUSES)},
    )
    return len(QUOTE_STATUSES)


def _documents(conn: Connection, tenant_id: UUID, owner: UUID, clients: list, today: date) -> int:
    """Branded documents issued the way the API does (real PDFs, real numbering): invoice-receipts,
    a tax invoice, a transaction invoice, a quote and a credit note for the first invoice."""
    if _has(conn, "issued_documents", tenant_id):
        return 0
    made = 0
    conn.execute(  # a tax document needs the business's address (only filled where it is empty)
        text("""
            UPDATE app.tenants
            SET address_line = coalesce(address_line, 'רחוב הרצל 10'),
                address_city = coalesce(address_city, 'תל אביב')
            WHERE id = :t
        """),
        {"t": tenant_id},
    )
    with _as_tenant(conn, tenant_id, owner) as db:
        context = SimpleNamespace(session=db)
        first = None
        plan = (
            ("tax_invoice_receipt", "card", "מנוי חודשי", 1, 28_000),
            ("tax_invoice_receipt", "cash", "כרטיסיית 10 כניסות", 1, 45_000),
            ("tax_invoice", None, "שירות חודשי", 1, 120_000),
            ("transaction_invoice", None, "מקדמה לאירוע", 1, 90_000),
            ("quote", None, "הצעת מחיר לאירוע", 1, 250_000),
        )
        for i, (kind, method, description, quantity, price) in enumerate(plan):
            client = clients[i % len(clients)]
            request = IssueRequest(
                kind=kind,
                client_id=client[0],
                lines=[LineIn(description=description, quantity=quantity, unit_price=price)],
                payment_method=method,
                due_date=today + timedelta(days=30) if kind == "tax_invoice" else None,
                valid_until=today + timedelta(days=30) if kind == "quote" else None,
                notes="מסמך דוגמה (נתוני דמו)",
            )
            document = issue(request, context)
            first = first or document
            made += 1
        credit = IssueRequest(
            kind="credit_note",
            reference_id=first.id,
            lines=[LineIn(description="זיכוי חלקי", quantity=1, unit_price=5_000)],
        )
        issue(credit, context)
        made += 1
    return made


def _sales(conn: Connection, tenant_id: UUID, owner: UUID, today: date) -> int:
    """Promo codes and two plan freezes (one running now, one in the future)."""
    added = 0
    if not _has(conn, "promo_codes", tenant_id):
        for code, percent, amount in (("WELCOME10", 10, None), ("SUMMER", None, 5_000)):
            conn.execute(
                text("""
                    INSERT INTO app.promo_codes
                        (tenant_id, code, percent_off, amount_off, starts_on, ends_on, max_uses)
                    VALUES (:t, :code, :percent, :amount, :start, :end, 100)
                """),
                {
                    "t": tenant_id,
                    "code": code,
                    "percent": percent,
                    "amount": amount,
                    "start": today - timedelta(days=10),
                    "end": today + timedelta(days=60),
                },
            )
            added += 1
    if not _has(conn, "entitlement_freezes", tenant_id):
        rows = (
            conn.execute(
                text("""
                SELECT id FROM app.entitlements
                WHERE tenant_id = :t AND status = 'active'
                  AND starts_on <= :today - 2 AND ends_on >= :today + 20
                ORDER BY created_at LIMIT 2
            """),
                {"t": tenant_id, "today": today},
            )
            .scalars()
            .all()
        )
        for entitlement_id, (start, days, reason) in zip(
            rows, ((-2, 14, "חופשה משפחתית"), (10, 7, "פציעה, חזרה בעוד שבוע")), strict=False
        ):
            starts = today + timedelta(days=start)
            ends = starts + timedelta(days=days - 1)
            conn.execute(
                text("""
                    INSERT INTO app.entitlement_freezes
                        (tenant_id, entitlement_id, starts_on, ends_on, reason, created_by)
                    VALUES (:t, :e, :s, :end, :reason, :owner)
                """),
                {
                    "t": tenant_id,
                    "e": entitlement_id,
                    "s": starts,
                    "end": ends,
                    "reason": reason,
                    "owner": owner,
                },
            )
            conn.execute(
                text("UPDATE app.entitlements SET ends_on = ends_on + :d WHERE id = :e"),
                {"d": days, "e": entitlement_id},
            )
            added += 1
    return added


def _ai(
    conn: Connection, tenant_id: UUID, owner: UUID, name: str, clients: list, today: date
) -> int:
    """Conversations with several agents, two actions waiting for approval, usage alerts and a
    team on the map. No model is called: the texts are written here."""
    added = 0
    month = today.replace(day=1)
    if not _has(conn, "ai_conversations", tenant_id):
        chats = [CHATS[name], *MORE_CHATS] if name in CHATS else list(MORE_CHATS)
        for i, (agent, question, answer) in enumerate(chats):
            started = datetime.now().astimezone() - timedelta(days=i * 2, hours=3)
            messages = [
                {"role": "user", "content": question},
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": answer.format(n=len(clients) + 120 * i)}],
                },
            ]
            conversation_id = conn.execute(
                text("""
                    INSERT INTO app.ai_conversations
                        (tenant_id, user_id, agent_key, title, messages, created_at, updated_at)
                    VALUES (:t, :u, :agent, :title, CAST(:messages AS jsonb), :at, :at)
                    RETURNING id
                """),
                {
                    "t": tenant_id,
                    "u": owner,
                    "agent": agent,
                    "title": question[:60],
                    "messages": _json(messages),
                    "at": started,
                },
            ).scalar_one()
            if i == 0 and clients:
                added += _pending_actions(conn, tenant_id, owner, conversation_id, agent, clients)
            added += 1
    if not _has(conn, "ai_credit_alerts", tenant_id):
        for threshold in (80, 100):
            conn.execute(
                text(
                    "INSERT INTO app.ai_credit_alerts (tenant_id, month_start, threshold) VALUES "
                    "(:t, :m, :th)"
                ),
                {"t": tenant_id, "m": month, "th": threshold},
            )
        conn.execute(
            text(
                "INSERT INTO app.quota_alerts (tenant_id, meter, month_start, threshold) VALUES "
                "(:t, 'messages', :m, 80)"
            ),
            {"t": tenant_id, "m": month},
        )
        added += 3
    if not _has(conn, "ai_agent_teams", tenant_id):
        team_id = conn.execute(
            text("""
                INSERT INTO app.ai_agent_teams (id, tenant_id, name, color, lead_key)
                VALUES (:id, :t, 'צוות צמיחה', '#7C3AED', 'marketing') RETURNING id
            """),
            {"id": uuid4(), "t": tenant_id},
        ).scalar_one()
        conn.execute(
            text("""
                INSERT INTO app.ai_agents (tenant_id, builtin_key, team_id, reports_to_key)
                VALUES (:t, 'marketing', :team, 'chief')
                ON CONFLICT (tenant_id, builtin_key) DO UPDATE SET team_id = :team
            """),
            {"t": tenant_id, "team": team_id},
        )
        conn.execute(
            text("""
                INSERT INTO app.ai_agents (tenant_id, builtin_key, team_id, reports_to_key)
                VALUES (:t, 'creative', :team, 'marketing')
                ON CONFLICT (tenant_id, builtin_key) DO UPDATE SET team_id = :team
            """),
            {"t": tenant_id, "team": team_id},
        )
        added += 1
    return added


def _pending_actions(
    conn: Connection, tenant_id: UUID, owner: UUID, conversation_id: UUID, agent: str, clients: list
) -> int:
    """Two things an agent proposed that wait for the owner (one sensitive)."""
    session = conn.execute(
        text("""
            SELECT s.id, s.starts_at FROM app.sessions s
            WHERE s.tenant_id = :t AND s.status = 'scheduled' AND s.starts_at > now()
            ORDER BY s.starts_at LIMIT 1
        """),
        {"t": tenant_id},
    ).first()
    if session is None:
        return 0
    client = clients[0]
    proposals = (
        (
            "book_client",
            {"session_id": str(session[0]), "client_id": str(client[0])},
            {"kind": "book_client", "client": f"{client[1]} {client[2] or ''}".strip()},
            "low",
        ),
        (
            "cancel_booking",
            {"booking_id": str(uuid4())},
            {"kind": "cancel_booking", "client": f"{client[1]} {client[2] or ''}".strip()},
            "sensitive",
        ),
    )
    for tool, payload, preview, risk in proposals:
        canonical = json.dumps({"tool": tool, "payload": payload}, sort_keys=True)
        conn.execute(
            text("""
                INSERT INTO app.pending_actions
                    (tenant_id, conversation_id, requested_by, agent_key, tool_name, payload,
                     payload_hash, preview, risk_level, expires_at)
                VALUES (:t, :c, :u, :agent, :tool, CAST(:payload AS jsonb), :hash,
                        CAST(:preview AS jsonb), :risk, now() + interval '2 days')
            """),
            {
                "t": tenant_id,
                "c": conversation_id,
                "u": owner,
                "agent": agent,
                "tool": tool,
                "payload": _json(payload),
                "hash": hashlib.sha256(canonical.encode()).hexdigest(),
                "preview": _json(preview),
                "risk": risk,
            },
        )
    return len(proposals)


def _messages(conn: Connection, tenant_id: UUID, owner: UUID, name: str, clients: list) -> int:
    """Marketing consent (given by most, withdrawn by a few), one announcement sent to those who
    agreed and one draft, and the client notifications."""
    added = 0
    if not _has(conn, "consent_events", tenant_id):
        sources = ("app_join", "app_profile", "desk_signed", "desk_verbal")
        for i, client in enumerate(clients):
            if i % 5 == 4:
                continue  # one in five never answered
            conn.execute(
                text("""
                    INSERT INTO app.consent_events
                        (tenant_id, client_id, action, source, recorded_by, created_at)
                    VALUES (:t, :c, 'granted', :source, :by, now() - make_interval(days => :d))
                """),
                {
                    "t": tenant_id,
                    "c": client[0],
                    "source": sources[i % 4],
                    "by": owner if i % 4 >= 2 else None,
                    "d": 60 - i,
                },
            )
            conn.execute(
                text("""
                    UPDATE app.clients SET marketing_consent_at = now() - make_interval(days => :d),
                                           marketing_consent_source = :source
                    WHERE id = :c AND marketing_consent_at IS NULL
                """),
                {"c": client[0], "source": sources[i % 4], "d": 60 - i},
            )
            added += 1
            if i % 9 == 8:  # and a few took it back
                conn.execute(
                    text("""
                        INSERT INTO app.consent_events
                            (tenant_id, client_id, action, source, created_at)
                        VALUES (:t, :c, 'withdrawn', 'unsubscribe_link', now() - interval '5 days')
                    """),
                    {"t": tenant_id, "c": client[0]},
                )
                conn.execute(
                    text(
                        "UPDATE app.clients SET marketing_opted_out_at = now() - interval '5 "
                        "days' WHERE id = :c"
                    ),
                    {"c": client[0]},
                )
    if not _has(conn, "announcements", tenant_id):
        agreed = [c for i, c in enumerate(clients) if i % 5 != 4][:8]
        ids = []
        for status, subject, body, sent in (
            (
                "sent",
                f"חדש ב-{name}",
                "יש לנו מבצע מיוחד לחברים: שבוע ניסיון לחבר שמצטרף איתך.",
                True,
            ),
            ("draft", "תזכורת לפני החגים", "שעות הפעילות לקראת החג יתפרסמו בקרוב.", False),
        ):
            content = {"subject": subject, "body": body}
            ids.append(
                conn.execute(
                    text("""
                        INSERT INTO app.announcements
                            (issuer, tenant_id, kind, channels, audience, content, status,
                             recipient_count, created_by, sent_at)
                        VALUES ('tenant', :t, 'marketing', ARRAY['email', 'push'],
                                CAST(:audience AS jsonb), CAST(:content AS jsonb), :status,
                                :count, :by, CASE WHEN :sent THEN now() - interval '3 days' END)
                        RETURNING id
                    """),
                    {
                        "t": tenant_id,
                        "audience": _json({"client_ids": [str(c[0]) for c in agreed]}),
                        "content": _json({"he": content, "en": content}),
                        "status": status,
                        "count": len(agreed) if sent else None,
                        "by": str(owner),
                        "sent": sent,
                    },
                ).scalar_one()
            )
        for i, client in enumerate(agreed):
            for channel in ("email", "push"):
                conn.execute(
                    text("""
                        INSERT INTO app.announcement_deliveries
                            (announcement_id, channel, person_key, client_id, tenant_id, email,
                             locale, status, sent_at, first_name)
                        VALUES (:a, :channel, :key, :c, :t, :email, 'he', :status,
                                CASE WHEN :status = 'sent' THEN now() - interval '3 days' END,
                                :first)
                    """),
                    {
                        "a": ids[0],
                        "channel": channel,
                        "key": f"client:{client[0]}",
                        "c": client[0],
                        "t": tenant_id,
                        "email": client[3],
                        "status": "failed" if i == 0 and channel == "push" else "sent",
                        "first": client[1],
                    },
                )
        added += 2
    if not _has(conn, "notifications", tenant_id):
        kinds = ("plan_ending", "session_reminder", "friend_request", "health_approved")
        for i, client in enumerate(clients[:8]):
            kind = kinds[i % 4]
            payload = (
                {"plan_name": "מנוי חודשי", "ends_on": str(date.today() + timedelta(days=2))}
                if kind == "plan_ending"
                else {}
            )
            conn.execute(
                text("""
                    INSERT INTO app.notifications
                        (tenant_id, client_id, kind, payload, created_at, read_at, email_status)
                    VALUES (:t, :c, :kind, CAST(:payload AS jsonb), now() - make_interval(hours
                    => :h),
                            CASE WHEN :h > 30 THEN now() END, 'skipped')
                """),
                {
                    "t": tenant_id,
                    "c": client[0],
                    "kind": kind,
                    "payload": _json(payload),
                    "h": 6 + i * 9,
                },
            )
            added += 1
    return added


def _planning(
    conn: Connection, tenant_id: UUID, owner: UUID, team: list, today: date, rng: random.Random
) -> int:
    """Shift templates, coverage rules, time off and requests, closed days, swaps, a custom role,
    clock rules and pay components with a bonus."""
    added = 0
    locations = (
        conn.execute(
            text("SELECT id FROM app.locations WHERE tenant_id = :t ORDER BY created_at"),
            {"t": tenant_id},
        )
        .scalars()
        .all()
    )
    if not _has(conn, "shift_templates", tenant_id):
        for location in locations:
            for label, opens, closes in (("בוקר", time(7), time(15)), ("ערב", time(14), time(22))):
                conn.execute(
                    text("""
                        INSERT INTO app.shift_templates (tenant_id, location_id, name, starts,
                        ends, position)
                        VALUES (:t, :l, :name, :s, :e, 'צוות')
                    """),
                    {"t": tenant_id, "l": location, "name": label, "s": opens, "e": closes},
                )
                added += 1
    if not _has(conn, "coverage_rules", tenant_id):
        for location in locations:
            for weekday in (0, 1, 2, 3, 6):  # Sunday to Thursday
                conn.execute(
                    text("""
                        INSERT INTO app.coverage_rules
                            (tenant_id, location_id, weekday, starts_minute, ends_minute, min_staff)
                        VALUES (:t, :l, :w, 480, 1200, 2)
                    """),
                    {"t": tenant_id, "l": location, "w": weekday},
                )
                added += 1
    if not _has(conn, "closed_days", tenant_id):
        for offset, reason in ((12, "יום שבתון"), (26, "יום הכשרה לצוות")):
            conn.execute(
                text(
                    "INSERT INTO app.closed_days (tenant_id, day, reason, created_by) VALUES "
                    "(:t, :d, :r, :by)"
                ),
                {"t": tenant_id, "d": today + timedelta(days=offset), "r": reason, "by": owner},
            )
            added += 1
    if team and not _has(conn, "staff_time_off", tenant_id):
        start = today + timedelta(days=9)
        approved = conn.execute(
            text("""
                INSERT INTO app.staff_time_off (tenant_id, user_id, starts_on, ends_on, reason)
                VALUES (:t, :u, :s, :e, 'חופשה משפחתית') RETURNING id
            """),
            {"t": tenant_id, "u": team[0][0], "s": start, "e": start + timedelta(days=3)},
        ).scalar_one()
        added += 1
        requests = (
            ("approved", start, 3, approved, owner),
            ("pending", today + timedelta(days=20), 1, None, None),
            ("declined", today + timedelta(days=5), 0, None, owner),
        )
        for i, (status, first, days, time_off, decider) in enumerate(requests):
            user = team[min(i, len(team) - 1)][0]
            conn.execute(
                text("""
                    INSERT INTO app.time_off_requests
                        (tenant_id, user_id, starts_on, ends_on, reason, status, decided_by,
                         decided_at, decision_note, time_off_id)
                    VALUES (:t, :u, :s, :e, :reason, :status, CAST(:by AS uuid),
                            CASE WHEN CAST(:by AS uuid) IS NOT NULL THEN now() - interval '1
                            day' END, :note, :off)
                """),
                {
                    "t": tenant_id,
                    "u": user,
                    "s": first,
                    "e": first + timedelta(days=days),
                    "reason": "בקשת חופשה",
                    "status": status,
                    "by": decider,
                    "note": "אין כיסוי באותו יום" if status == "declined" else None,
                    "off": time_off,
                },
            )
            added += 1
    if len(team) >= 2 and not _has(conn, "shift_swaps", tenant_id):
        shifts = conn.execute(
            text("""
                SELECT id, user_id, starts_at, ends_at, "position", location_id FROM app.shifts
                WHERE tenant_id = :t AND user_id = :u AND starts_at > now() ORDER BY starts_at
                LIMIT 3
            """),
            {"t": tenant_id, "u": team[0][0]},
        ).all()
        for shift, status in zip(
            shifts, ("pending_manager", "approved", "pending_colleague"), strict=False
        ):
            conn.execute(
                text("""
                    INSERT INTO app.shift_swaps
                        (tenant_id, shift_id, from_user_id, to_user_id, note, status, colleague_at,
                         decided_by, decided_at)
                    VALUES (:t, :s, :a, :b, 'אפשר להחליף? יש לי אירוע משפחתי', :status,
                            CASE WHEN :status <> 'pending_colleague' THEN now() - interval '1
                            day' END,
                            CASE WHEN :status = 'approved' THEN CAST(:by AS uuid) END,
                            CASE WHEN :status = 'approved' THEN now() END)
                """),
                {
                    "t": tenant_id,
                    "s": shift[0],
                    "a": team[0][0],
                    "b": team[1][0],
                    "status": status,
                    "by": str(owner),
                },
            )
            added += 1
        if shifts:
            conn.execute(
                text("""
                    INSERT INTO app.shift_changes
                        (tenant_id, user_id, shift_id, before_starts, before_ends,
                        before_branch, before_position)
                    SELECT :t, :u, :s, :start - interval '1 hour', :end - interval '1 hour',
                    l.name, :pos
                    FROM app.locations l WHERE l.id = :l
                """),
                {
                    "t": tenant_id,
                    "u": team[0][0],
                    "s": shifts[0][0],
                    "start": shifts[0][2],
                    "end": shifts[0][3],
                    "pos": shifts[0][4],
                    "l": shifts[0][5],
                },
            )
            added += 1
    if not _has(conn, "tenant_roles", tenant_id):
        conn.execute(
            text(
                "INSERT INTO app.tenant_roles (tenant_id, name, permissions) VALUES (:t, 'מנהל "
                "קבלה', :perms)"
            ),
            {
                "t": tenant_id,
                "perms": [
                    "clients.read",
                    "clients.write",
                    "schedule.read",
                    "bookings.manage",
                    "sales.manage",
                ],
            },
        )
        added += 1
    if not _has(conn, "time_clock_rules", tenant_id):
        conn.execute(
            text("INSERT INTO app.time_clock_rules (tenant_id) VALUES (:t) ON CONFLICT DO NOTHING"),
            {"t": tenant_id},
        )
        added += 1
    if team and not _has(conn, "pay_components", tenant_id):
        for user_id, _location in team[:2]:
            for kind, label, calc, amount in (
                ("travel", "החזר נסיעות", "per_work_day", 2_500),
                ("meals", "ארוחות", "monthly", 30_000),
            ):
                conn.execute(
                    text("""
                        INSERT INTO app.pay_components
                            (tenant_id, user_id, kind, name, calc, amount_minor, currency, taxable,
                             social_security_liable, pension_base, valid_from)
                        SELECT :t, :u, :kind, :name, :calc, :amount, t.currency, false, false,
                        false,
                               '2025-01-01'
                        FROM app.tenants t WHERE t.id = :t
                    """),
                    {
                        "t": tenant_id,
                        "u": user_id,
                        "kind": kind,
                        "name": label,
                        "calc": calc,
                        "amount": amount,
                    },
                )
                added += 1
    if team and not _has(conn, "pay_adjustments", tenant_id):
        period = _month(today)
        for i, status in enumerate(("approved", "proposed")):
            conn.execute(
                text("""
                    INSERT INTO app.pay_adjustments
                        (tenant_id, user_id, period, kind, amount_minor, currency, note, taxable,
                         social_security_liable, pension_base, status, proposed_by, decided_by,
                         decided_at, created_by)
                    SELECT :t, :u, :period, 'bonus', :amount, t.currency, :note, true, true, true,
                           :status, :by, CASE WHEN :status = 'approved' THEN CAST(:by AS uuid) END,
                           CASE WHEN :status = 'approved' THEN now() END, :by
                    FROM app.tenants t WHERE t.id = :t
                """),
                {
                    "t": tenant_id,
                    "u": team[min(i, len(team) - 1)][0],
                    "period": period,
                    "amount": 50_000 + 25_000 * i,
                    "note": "בונוס על חודש מצוין",
                    "status": status,
                    "by": owner,
                },
            )
            added += 1
    return added


def _website(
    conn: Connection,
    tenant_id: UUID,
    owner: UUID,
    name: str,
    currency: str,
    today: date,
    rng: random.Random,
) -> int:
    """A website order: the gym's site is live and gets visits, the salon's is being built."""
    if name not in (GYM_NETWORK, SALON) or _has(conn, "website_orders", tenant_id):
        return 0
    live = name == GYM_NETWORK
    brief = Brief(
        goals=["leads", "bookings"],
        main_action="לקבוע שיעור ניסיון",
        unique="סטודיו קטן עם מאמנים אישיים",
        audience="מתאמנים בני 25 עד 45",
        area="תל אביב והמרכז",
        sections=["hero", "services", "team", "testimonials", "contact", "booking"],
        style="vibrant" if live else "luxury",
        motion="subtle",
    ).model_dump(mode="json", exclude_none=True)
    setup, monthly = price_for("landing_with_system", currency.strip())
    now = datetime.now().astimezone()
    conn.execute(
        text("""
            INSERT INTO app.website_orders
                (tenant_id, product, stage, brief, snapshot, currency, setup_price, monthly_price,
                 site_url, customer_message, created_by, submitted_at, approved_at, live_at)
            VALUES (:t, 'landing_with_system', :stage, CAST(:brief AS jsonb),
                    CAST(:snapshot AS jsonb), :currency, :setup, :monthly, :url, :message, :by,
                    :submitted, :approved, :live)
        """),
        {
            "t": tenant_id,
            "stage": "live" if live else "building",
            "brief": _json(brief),
            "snapshot": _json({"business": {"name": name}, "branches": [], "services": []}),
            "currency": currency.strip(),
            "setup": setup,
            "monthly": monthly,
            "url": "https://adir-fitness.example.com" if live else None,
            "message": "האתר באוויר, בהצלחה!" if live else "אנחנו בונים את האתר ונעדכן בקרוב.",
            "by": owner,
            "submitted": now - timedelta(days=30),
            "approved": now - timedelta(days=20) if live else None,
            "live": now - timedelta(days=14) if live else None,
        },
    )
    if live:
        for offset in range(30):
            for source, weight in (("direct", 12), ("search", 20), ("social", 9), ("other", 3)):
                conn.execute(
                    text("""
                        INSERT INTO app.website_visits_daily (tenant_id, day, source, visits)
                        VALUES (:t, :d, :source, :n) ON CONFLICT DO NOTHING
                    """),
                    {
                        "t": tenant_id,
                        "d": today - timedelta(days=offset),
                        "source": source,
                        "n": max(0, int(rng.gauss(weight, weight / 3))),
                    },
                )
    return 1


def _whatsapp(conn: Connection, tenant_id: UUID, clients: list) -> int:
    """Two chats with clients, incoming messages (one waiting) and a booking offer to confirm."""
    if _has(conn, "whatsapp_conversations", tenant_id) or len(clients) < 2:
        return 0
    added = 0
    session = conn.execute(
        text("""
            SELECT s.id, s.starts_at, sv.name FROM app.sessions s
            JOIN app.services sv ON sv.id = s.service_id
            WHERE s.tenant_id = :t AND s.status = 'scheduled' AND s.starts_at > now() + interval
            '1 day'
            ORDER BY s.starts_at LIMIT 1
        """),
        {"t": tenant_id},
    ).first()
    for i, client in enumerate(clients[:2]):
        phone = client[4] or f"05012340{i}0"
        key = "".join(ch for ch in phone if ch.isdigit())[-9:]
        messages = [
            {
                "role": "user",
                "text": "היי, אפשר להירשם לשיעור מחר?",
                "at": str(datetime.now().astimezone() - timedelta(hours=5)),
            },
            {
                "role": "assistant",
                "text": "בטח! יש מקום בשיעור הערב. לרשום אותך?",
                "at": str(datetime.now().astimezone() - timedelta(hours=5)),
            },
        ]
        conversation_id = conn.execute(
            text("""
                INSERT INTO app.whatsapp_conversations (tenant_id, phone, phone_key, client_id,
                messages)
                VALUES (:t, :phone, :key, :c, CAST(:messages AS jsonb)) RETURNING id
            """),
            {
                "t": tenant_id,
                "phone": phone,
                "key": key,
                "c": client[0],
                "messages": _json(messages),
            },
        ).scalar_one()
        added += 1
        conn.execute(
            text("""
                INSERT INTO app.whatsapp_inbox
                    (tenant_id, provider, provider_ref, from_phone, body, status, handled_at)
                VALUES (:t, 'simulated', :ref, :phone, 'היי, אפשר להירשם לשיעור מחר?', :status,
                        CASE WHEN :status = 'answered' THEN now() END)
            """),
            {
                "t": tenant_id,
                "ref": f"demo-{conversation_id}",
                "phone": phone,
                "status": "answered" if i == 0 else "received",
            },
        )
        if i == 0 and session:
            payload = {"session_id": str(session[0]), "client_id": str(client[0])}
            canonical = json.dumps({"tool": "book_session", "payload": payload}, sort_keys=True)
            conn.execute(
                text("""
                    INSERT INTO app.whatsapp_offers
                        (tenant_id, conversation_id, client_id, kind, payload, payload_hash,
                        preview, expires_at)
                    VALUES (:t, :conv, :c, 'book_session', CAST(:payload AS jsonb), :hash,
                            CAST(:preview AS jsonb), now() + interval '1 day')
                """),
                {
                    "t": tenant_id,
                    "conv": conversation_id,
                    "c": client[0],
                    "payload": _json(payload),
                    "hash": hashlib.sha256(canonical.encode()).hexdigest(),
                    "preview": _json({"service": session[2], "starts_at": str(session[1])}),
                },
            )
            added += 1
    return added


def _people(conn: Connection, tenant_id: UUID, owner: UUID, name: str, clients: list) -> int:
    """Client addresses, children, friends with a class invitation, and an audit trail."""
    added = 0
    if not _has(conn, "client_addresses", tenant_id):
        for i, (client, street, city) in enumerate(
            zip(
                clients,
                ("הרצל", "דיזנגוף", "ביאליק", "הנביאים"),
                ("תל אביב", "תל אביב", "רמת גן", "חיפה"),
                strict=False,
            )
        ):
            conn.execute(
                text("""
                    INSERT INTO app.client_addresses (tenant_id, client_id, label, street, city,
                    house_number)
                    VALUES (:t, :c, :label, :street, :city, :house)
                """),
                {
                    "t": tenant_id,
                    "c": client[0],
                    "label": "בית" if i % 2 == 0 else "עבודה",
                    "street": street,
                    "city": city,
                    "house": str(10 + i * 7),
                },
            )
            added += 1
    if not _has(conn, "dependents", tenant_id):
        for client, child, birth in zip(
            clients[2:5], ("נועם", "מאיה", "אורי"), (2016, 2014, 2018), strict=False
        ):
            conn.execute(
                text("""
                    INSERT INTO app.dependents (tenant_id, client_id, kind, name, birth_date, notes)
                    VALUES (:t, :c, 'child', :name, :birth, 'ילד לדוגמה (נתוני דמו)')
                """),
                {"t": tenant_id, "c": client[0], "name": child, "birth": date(birth, 6, 15)},
            )
            added += 1
    if len(clients) >= 3 and not _has(conn, "client_friendships", tenant_id):
        for requester, addressee, status in ((0, 1, "accepted"), (0, 2, "pending")):
            conn.execute(
                text("""
                    INSERT INTO app.client_friendships
                        (tenant_id, requester_id, addressee_id, status, responded_at)
                    VALUES (:t, :a, :b, :status, CASE WHEN :status = 'accepted' THEN now() END)
                """),
                {
                    "t": tenant_id,
                    "a": clients[requester][0],
                    "b": clients[addressee][0],
                    "status": status,
                },
            )
            added += 1
        session = conn.execute(
            text("""
                SELECT id FROM app.sessions
                WHERE tenant_id = :t AND status = 'scheduled' AND starts_at > now() + interval
                '2 days'
                ORDER BY starts_at LIMIT 1
            """),
            {"t": tenant_id},
        ).scalar()
        if session:
            conn.execute(
                text("""
                    INSERT INTO app.class_invites
                        (tenant_id, session_id, inviter_id, invitee_id, expires_at)
                    VALUES (:t, :s, :a, :b, now() + interval '2 days')
                """),
                {"t": tenant_id, "s": session, "a": clients[0][0], "b": clients[1][0]},
            )
            added += 1
    if not _has(conn, "audit_log", tenant_id):
        for action, entity, details in (
            ("plan.sold", "entitlement", {"plan": "מנוי חודשי"}),
            ("staff.role_changed", "member", {"role": "manager"}),
            ("client.exported", "client", {"format": "csv"}),
            ("settings.updated", "tenant", {"field": "opening_hours"}),
        ):
            conn.execute(
                text("""
                    INSERT INTO app.audit_log
                        (tenant_id, actor_type, actor_id, action, entity_type, details, occurred_at)
                    VALUES (:t, 'user', :u, :action, :entity, CAST(:details AS jsonb),
                            now() - make_interval(hours => :h))
                """),
                {
                    "t": tenant_id,
                    "u": owner,
                    "action": action,
                    "entity": entity,
                    "details": _json({**details, "demo": True}),
                    "h": 4 + added * 3,
                },
            )
            added += 1
    return added


def seed_round7(conn: Connection, tenant_id: UUID, tenant_name: str, today: date) -> dict[str, int]:
    """Adds the round-7 demo data to one business; returns what was added per area."""
    owner = conn.execute(
        text("""
            SELECT user_id FROM app.tenant_members
            WHERE tenant_id = :t AND role = 'owner' ORDER BY created_at LIMIT 1
        """),
        {"t": tenant_id},
    ).scalar_one()
    currency = conn.execute(
        text("SELECT currency FROM app.tenants WHERE id = :t"), {"t": tenant_id}
    ).scalar_one()
    rng = random.Random(tenant_id.int ^ 7)
    clients = _clients(conn, tenant_id, 40)
    if len(clients) < 5:
        return {}
    team = _team(conn, tenant_id)
    counts = {
        "quotes": _quotes(conn, tenant_id, owner, currency, tenant_name, clients, today, rng),
        "documents": _documents(conn, tenant_id, owner, clients, today),
        "sales": _sales(conn, tenant_id, owner, today),
        "ai": _ai(conn, tenant_id, owner, tenant_name, clients, today),
        "messages": _messages(conn, tenant_id, owner, tenant_name, clients),
        "planning": _planning(conn, tenant_id, owner, team, today, rng),
        "website": _website(conn, tenant_id, owner, tenant_name, currency, today, rng),
        "whatsapp": _whatsapp(conn, tenant_id, clients),
        "people": _people(conn, tenant_id, owner, tenant_name, clients),
    }
    return counts
