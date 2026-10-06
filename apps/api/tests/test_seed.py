import random
from uuid import uuid4

from sqlalchemy import Engine, text

from app.seed import seed, seed_demo


def test_demo_studio_respects_the_invariants(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'demo-owner@example.com')"),
            {"id": owner},
        )
        tenant_id = seed(connection, "demo-owner@example.com", 2, random.Random(1))

    with engine.connect() as connection:
        over_capacity = connection.execute(
            text("""
                SELECT count(*) FROM app.sessions s
                WHERE s.tenant_id = :t AND s.capacity < (
                    SELECT count(*) FROM app.bookings b
                    WHERE b.session_id = s.id AND b.status IN ('booked', 'checked_in', 'no_show')
                )
            """),
            {"t": tenant_id},
        ).scalar_one()
        overspent = connection.execute(
            text("""
                SELECT count(*) FROM app.entitlements e
                WHERE e.tenant_id = :t AND e.credits < (
                    SELECT count(*) FROM app.bookings b
                    WHERE b.entitlement_id = e.id AND (b.status <> 'cancelled' OR b.late_cancel)
                )
            """),
            {"t": tenant_id},
        ).scalar_one()
        counts = connection.execute(
            text("""
                SELECT (SELECT count(*) FROM app.clients WHERE tenant_id = :t),
                       (SELECT count(*) FROM app.bookings WHERE tenant_id = :t
                            AND status = 'checked_in'),
                       (SELECT count(*) FROM app.payments WHERE tenant_id = :t),
                       (SELECT count(*) FROM app.health_declarations WHERE tenant_id = :t
                            AND valid_until >= current_date)
            """),
            {"t": tenant_id},
        ).one()

    assert over_capacity == 0
    assert overspent == 0
    clients, attended, payments, declarations = counts
    assert clients == 170 and attended > 500 and payments > 100
    assert declarations == 155  # every client but the leads
    with engine.connect() as connection:
        stages = dict(
            connection.execute(
                text("SELECT stage, count(*) FROM app.leads WHERE tenant_id = :t GROUP BY 1"),
                {"t": tenant_id},
            ).all()
        )
        won_without_client = connection.execute(
            text("""
                SELECT count(*) FROM app.leads
                WHERE tenant_id = :t AND stage = 'won' AND client_id IS NULL
            """),
            {"t": tenant_id},
        ).scalar_one()
    assert set(stages) == {"new", "contacted", "trial", "offer", "won", "lost"}
    assert won_without_client == 0  # won leads are clients
    with engine.connect() as connection:
        to_clients, to_leads, campaign_recipients, campaign_sent = connection.execute(
            text("""
                SELECT count(*) FILTER (WHERE client_id IS NOT NULL),
                       count(*) FILTER (WHERE lead_id IS NOT NULL),
                       (SELECT sum(recipients) FROM app.campaigns WHERE tenant_id = :t),
                       count(*) FILTER (WHERE campaign_id IS NOT NULL)
                FROM app.messages WHERE tenant_id = :t AND simulated
            """),
            {"t": tenant_id},
        ).one()
    assert to_clients > 10 and to_leads > 0  # the messages screens have history to show
    assert campaign_recipients == campaign_sent
    with engine.connect() as connection:
        invoices = (
            connection.execute(
                text("SELECT status FROM app.platform_invoices WHERE tenant_id = :t"),
                {"t": tenant_id},
            )
            .scalars()
            .all()
        )
    assert len(invoices) >= 4 and set(invoices) == {"paid"}  # 2 months of data + 90 days before


def test_owner_demo_has_two_businesses_with_branches(engine: Engine) -> None:
    owner = uuid4()
    email = f"owner-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        first = seed_demo(connection, email, "owner", 1, random.Random(2), owner_name="Owner")
    # Running it again with --replace leaves one copy of each business.
    with engine.begin() as connection:
        tenants = seed_demo(connection, email, "owner", 1, random.Random(3), replace=True)

    with engine.connect() as connection:
        owned = (
            connection.execute(
                text("""
                SELECT t.id, t.vertical,
                       (SELECT count(*) FROM app.locations l WHERE l.tenant_id = t.id) AS branches,
                       (SELECT quantity FROM app.tenant_modules m
                        WHERE m.tenant_id = t.id AND m.module_key = 'extra_location') AS extra,
                       (SELECT count(DISTINCT s.location_id) FROM app.sessions s
                        WHERE s.tenant_id = t.id) AS branches_with_sessions,
                       (SELECT count(DISTINCT p.location_id) FROM app.payments p
                        WHERE p.tenant_id = t.id AND p.location_id IS NOT NULL) AS selling_branches,
                       (SELECT count(*) FROM app.bookings b JOIN app.sessions s
                            ON s.id = b.session_id JOIN app.services v ON v.id = s.service_id
                        WHERE b.tenant_id = t.id AND v.booking_mode = 'appointment')
                           AS appointments
                FROM app.tenants t JOIN app.tenant_members m ON m.tenant_id = t.id
                WHERE m.user_id = :owner ORDER BY t.created_at, t.vertical
            """),
                {"owner": owner},
            )
            .mappings()
            .all()
        )
        name = connection.execute(
            text("SELECT full_name FROM app.users WHERE id = :id"), {"id": owner}
        ).scalar_one()

    assert {row["id"] for row in owned} == set(tenants) and not set(first) & set(tenants)
    by_vertical = {row["vertical"]: row for row in owned}
    assert by_vertical["pilates"]["branches"] == 5 and by_vertical["pilates"]["extra"] == 4
    assert by_vertical["barbershop"]["branches"] == 3 and by_vertical["barbershop"]["extra"] == 2
    for row in owned:
        assert row["branches_with_sessions"] == row["branches"] == row["selling_branches"]
        assert row["appointments"] > 0
    assert name == "Owner"
