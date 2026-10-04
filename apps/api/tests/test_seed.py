import random
from uuid import uuid4

from sqlalchemy import Engine, text

from app.seed import seed


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
