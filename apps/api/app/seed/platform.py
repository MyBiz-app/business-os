"""The MyBiz side of the demo: small businesses, invoices and requests for the team."""

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
