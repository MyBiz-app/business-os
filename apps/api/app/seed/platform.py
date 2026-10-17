"""The MyBiz side of the demo: small businesses, invoices and requests for the team."""

import json
import random
from uuid import UUID

from sqlalchemy import Connection, text

from app.commerce.billing import bill_businesses
from app.seed.business import seed
from app.seed.common import PLATFORM_BUSINESSES, PLATFORM_REQUESTS, profile_id


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
        conn.execute(text("DELETE FROM app.announcements WHERE created_by = 'demo generator'"))
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
    _seed_announcements(conn, len(tenants))
    print(
        f"Platform demo: {len(tenants)} businesses, {len(PLATFORM_REQUESTS)} requests, "
        f"{staff_email} is a platform team owner."
    )
    return tenants


def _seed_announcements(conn: Connection, owners: int) -> None:
    """The broadcast center: a pop-up already sent to business owners and an email draft."""
    for kind, channels, status, content in (
        (
            "service",
            ["popup"],
            "sent",
            {
                "he": {"subject": "צוות ה-AI שלכם הגיע", "body": "כל סוכן עם תפקיד משלו."},
                "en": {"subject": "Your AI team is here", "body": "Each agent has its own role."},
            },
        ),
        (
            "marketing",
            ["email"],
            "draft",
            {
                "he": {"subject": "סטודיו התוכן נפתח", "body": "כל הרשתות החברתיות בדשבורד אחד."},
                "en": {"subject": "The content studio is open",
                       "body": "Every social network in one dashboard."},
            },
        ),
    ):  # fmt: skip
        conn.execute(
            text("""
                INSERT INTO app.announcements
                    (issuer, kind, channels, audience, content, status, recipient_count,
                     created_by, sent_at)
                VALUES ('platform', :kind, :channels, CAST(:audience AS jsonb),
                        CAST(:content AS jsonb), :status, :count, 'demo generator',
                        CASE WHEN :status = 'sent' THEN now() - interval '1 day' END)
            """),
            {
                "kind": kind,
                "channels": channels,
                "audience": json.dumps(
                    {
                        "groups": ["owners"],
                        "verticals": [],
                        "locales": [],
                        "business_ids": [],
                        "modules": [],
                        "status": None,
                    }
                ),
                "content": json.dumps(content),
                "status": status,
                "count": owners if status == "sent" else None,
            },
        )
