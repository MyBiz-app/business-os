import random
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text

from app.api.settings import israeli_number_valid
from app.seed import (
    AC_COMPANY,
    ACCOUNTING_FIRM,
    GROOMING_SALON,
    PADEL_CLUB,
    PHOTO_STUDIO,
    seed,
    seed_demo,
    seed_platform,
)
from app.seed.curate import curate
from app.seed.profiles import _add_crossfit_branch, enrich_profiles
from app.seed.social import CUSTOMER_EMAIL, seed_social


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


def test_demo_club_rents_its_courts(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'club-owner@example.com')"),
            {"id": owner},
        )
        tenant_id = seed(connection, "club-owner@example.com", 1, random.Random(3), PADEL_CLUB)

    with engine.connect() as connection:
        reservations, overlapping, paid_twice, courts = connection.execute(
            text("""
                SELECT (SELECT count(*) FROM app.sessions WHERE tenant_id = :t AND reserved),
                       (SELECT count(*) FROM app.sessions a JOIN app.sessions b
                            ON a.room_id = b.room_id AND a.id < b.id
                           AND a.starts_at < b.ends_at AND b.starts_at < a.ends_at
                        WHERE a.tenant_id = :t),
                       (SELECT count(*) FROM (
                            SELECT booking_id FROM app.payments
                            WHERE tenant_id = :t AND booking_id IS NOT NULL
                            GROUP BY booking_id HAVING count(*) > 1) twice),
                       (SELECT count(*) FROM app.rooms WHERE tenant_id = :t AND bookable)
            """),
            {"t": tenant_id},
        ).one()
    assert reservations > 300 and overlapping == 0 and paid_twice == 0 and courts == 3


def test_demo_salon_books_owners_pets(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'salon-owner@example.com')"),
            {"id": owner},
        )
        tenant_id = seed(connection, "salon-owner@example.com", 1, random.Random(5), GROOMING_SALON)

    with engine.connect() as connection:
        pets, owners_without, bookings, without_pet, foreign = connection.execute(
            text("""
                SELECT (SELECT count(*) FROM app.dependents WHERE tenant_id = :t AND kind = 'pet'),
                       (SELECT count(*) FROM app.clients c WHERE c.tenant_id = :t
                            AND NOT EXISTS (SELECT 1 FROM app.dependents d
                                            WHERE d.client_id = c.id)),
                       (SELECT count(*) FROM app.bookings WHERE tenant_id = :t),
                       (SELECT count(*) FROM app.bookings
                        WHERE tenant_id = :t AND dependent_id IS NULL),
                       (SELECT count(*) FROM app.bookings b JOIN app.dependents d
                            ON d.id = b.dependent_id WHERE b.tenant_id = :t
                           AND d.client_id <> b.client_id)
            """),
            {"t": tenant_id},
        ).one()
    # A groomer needs to know which pet comes: every owner has one, every booking names one.
    assert pets >= GROOMING_SALON.clients and owners_without == 0
    assert bookings > 100 and without_pet == 0 and foreign == 0


def test_demo_ac_company_has_jobs_at_addresses(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'ac-owner@example.com')"),
            {"id": owner},
        )
        tenant_id = seed(connection, "ac-owner@example.com", 1, random.Random(9), AC_COMPANY)

    with engine.connect() as connection:
        jobs, without_address, done, on_site = connection.execute(
            text("""
                SELECT count(*) FILTER (WHERE s.job_status IS NOT NULL),
                       count(*) FILTER (WHERE s.job_status IS NOT NULL AND s.address IS NULL),
                       count(*) FILTER (WHERE s.job_status = 'done'),
                       (SELECT count(*) FROM app.services WHERE tenant_id = :t AND on_site)
                FROM app.sessions s WHERE s.tenant_id = :t
            """),
            {"t": tenant_id},
        ).one()
    assert on_site >= 3 and jobs > 100 and without_address == 0 and done > 0


def test_demo_photo_studio_has_quotes_and_events(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'photo-owner@example.com')"),
            {"id": owner},
        )
        tenant_id = seed(connection, "photo-owner@example.com", 1, random.Random(11), PHOTO_STUDIO)

    with engine.connect() as connection:
        quotes, accepted, paid_quotes, receipts, numbers = connection.execute(
            text("""
                SELECT count(*), count(*) FILTER (WHERE status = 'accepted'),
                       (SELECT count(DISTINCT quote_id) FROM app.payments
                        WHERE tenant_id = :t AND quote_id IS NOT NULL),
                       (SELECT count(*) FROM app.receipts r JOIN app.payments p
                            ON p.id = r.payment_id WHERE p.tenant_id = :t
                           AND p.quote_id IS NOT NULL),
                       count(DISTINCT number)
                FROM app.quotes WHERE tenant_id = :t
            """),
            {"t": tenant_id},
        ).one()
    assert quotes >= 30 and accepted > 10 and paid_quotes == accepted
    assert receipts >= accepted and numbers == quotes


def test_demo_accounting_firm_bills_by_time(engine: Engine) -> None:
    owner = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, 'cpa-owner@example.com')"),
            {"id": owner},
        )
        tenant_id = seed(connection, "cpa-owner@example.com", 1, random.Random(13), ACCOUNTING_FIRM)

    with engine.connect() as connection:
        retainers, entries, bills, unbilled_past, documents, signed = connection.execute(
            text("""
                SELECT (SELECT count(*) FROM app.retainers WHERE tenant_id = :t),
                       (SELECT count(*) FROM app.time_entries WHERE tenant_id = :t),
                       (SELECT count(*) FROM app.quotes WHERE tenant_id = :t AND kind = 'bill'),
                       (SELECT count(*) FROM app.time_entries WHERE tenant_id = :t
                          AND bill_id IS NULL
                          AND day < date_trunc('month', now())::date),
                       (SELECT count(*) FROM app.client_documents WHERE tenant_id = :t),
                       (SELECT count(*) FROM app.client_documents
                        WHERE tenant_id = :t AND signed_at IS NOT NULL)
            """),
            {"t": tenant_id},
        ).one()
    assert retainers == ACCOUNTING_FIRM.clients and entries > 200 and bills > 60
    assert unbilled_past == 0 and documents > 30 and signed > 10


def test_networks_demo_has_three_networks_with_their_workspace(engine: Engine) -> None:
    owner = uuid4()
    email = f"networks-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        seed_demo(connection, email, "networks", 1, random.Random(4))
    # Seeding again with --replace keeps one copy of each network.
    with engine.begin() as connection:
        tenants = seed_demo(connection, email, "networks", 1, random.Random(5), replace=True)

    with engine.connect() as connection:
        rows = (
            connection.execute(
                text("""
                SELECT t.id, t.name, t.vertical, t.business_number, t.cover IS NOT NULL AS cover,
                       (SELECT count(*) FROM app.locations l WHERE l.tenant_id = t.id) AS branches,
                       (SELECT count(DISTINCT h.location_id) FROM app.location_hours h
                        WHERE h.tenant_id = t.id) AS branches_with_hours,
                       (SELECT count(DISTINCT s.location_id) FROM app.shifts s
                        WHERE s.tenant_id = t.id) AS branches_with_shifts,
                       (SELECT count(DISTINCT s.station_id) FROM app.shifts s
                        WHERE s.tenant_id = t.id) AS stations_used,
                       (SELECT count(*) FROM app.shifts a JOIN app.shifts b
                            ON a.station_id = b.station_id AND a.id < b.id
                           AND a.starts_at < b.ends_at AND b.starts_at < a.ends_at
                        WHERE a.tenant_id = t.id) AS shared_stations,
                       (SELECT count(*) FROM app.tenant_members m
                        WHERE m.tenant_id = t.id AND m.role <> 'owner'
                          AND (m.reports_to IS NULL OR m.job_title IS NULL)) AS unplaced,
                       (SELECT count(*) FROM app.shifts a JOIN app.shifts b
                            ON a.tenant_id = b.tenant_id AND a.user_id = b.user_id
                           AND a.id < b.id AND a.starts_at < b.ends_at AND b.starts_at < a.ends_at
                        WHERE a.tenant_id = t.id) AS overlaps
                FROM app.tenants t JOIN app.tenant_members m ON m.tenant_id = t.id
                WHERE m.user_id = :owner AND m.role = 'owner'
            """),
                {"owner": owner},
            )
            .mappings()
            .all()
        )

    assert {row["id"] for row in rows} == set(tenants)
    by_name = {row["name"]: row for row in rows}
    assert {name: row["vertical"] for name, row in by_name.items()} == {
        "Urban Slice": "pizzeria",
        "Pulse Fitness": "gym",
        "Studio Bloom": "hair_salon",
    }
    assert [by_name[n]["branches"] for n in ("Urban Slice", "Pulse Fitness", "Studio Bloom")] == [
        4,
        2,
        3,
    ]
    for row in rows:
        assert israeli_number_valid(row["business_number"]) and row["cover"]
        assert row["branches_with_hours"] == row["branches_with_shifts"] == row["branches"]
        assert row["unplaced"] == 0 and row["overlaps"] == 0
        # Shifts are planned into rooms, and on busy stretches two people share one.
        assert row["stations_used"] >= 2 and row["shared_stations"] > 0


def test_categories_demo_has_one_business_per_kind_of_calendar(engine: Engine) -> None:
    owner = uuid4()
    email = f"cats-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        tenants = seed_demo(connection, email, "categories", 1, random.Random(4))
    assert len(tenants) == 3
    with engine.connect() as connection:
        kinds = {
            (vertical, kind)
            for vertical, kind in connection.execute(
                text("""
                    SELECT t.vertical, l.kind FROM app.locations l
                    JOIN app.tenants t ON t.id = l.tenant_id WHERE t.id = ANY(:ids)
                """),
                {"ids": tenants},
            )
        }
        sessions = connection.execute(
            text("SELECT count(*) FROM app.sessions WHERE tenant_id = ANY(:ids)"),
            {"ids": tenants},
        ).scalar_one()
    assert kinds == {
        ("gym", "gym"),
        ("gym", "pilates"),
        ("gym", "crossfit"),
        ("padel_tennis", "padel_tennis"),
        ("hair_salon", "hair_salon"),
    }
    assert sessions > 0


def test_profiles_add_logos_portraits_and_a_crossfit_branch_without_repeating(
    engine: Engine,
) -> None:
    owner = uuid4()
    email = f"pics-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        (tenant,) = seed_demo(connection, email, "club", 1, random.Random(4))
        added = _add_crossfit_branch(connection, tenant)
        again = _add_crossfit_branch(connection, tenant)
        first = enrich_profiles(connection, email)
        second = enrich_profiles(connection, email)
    assert added is not None and again is None
    assert first["businesses"] == 1 and first["branches"] >= 1
    assert first["staff"] > 0 and first["clients"] > 0
    assert not any(second.values())
    with engine.connect() as connection:
        row = connection.execute(
            text("""
                SELECT (SELECT count(*) FROM app.clients c JOIN app.users u ON u.id = c.user_id
                        WHERE c.tenant_id = :t AND u.avatar IS NOT NULL) AS client_portraits,
                       (SELECT count(*) FROM app.locations
                        WHERE tenant_id = :t AND logo IS NULL) AS without_logo
            """),
            {"t": tenant},
        ).one()
    assert row.client_portraits == first["clients"] and row.without_logo == 0


def test_curate_reduces_an_account_to_three_businesses_and_leaves_others_alone(
    engine: Engine,
) -> None:
    owner, other = uuid4(), uuid4()
    email, other_email = f"cur-{owner.hex[:6]}@example.com", f"oth-{other.hex[:6]}@example.com"
    with engine.begin() as connection:
        for user, address in ((owner, email), (other, other_email)):
            connection.execute(
                text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
                {"id": user, "email": address},
            )
        (foreign,) = seed_demo(connection, other_email, "club", 1, random.Random(5))
        seed_demo(connection, email, "categories", 1, random.Random(4))
        connection.execute(
            text("UPDATE app.tenants t SET name = 'Iron & Flow' WHERE t.name = 'Adir fitness'")
        )  # an account seeded before the rename
    with engine.begin() as connection:  # a run of its own, as on staging
        first = curate(connection, email, 1, random.Random(4))
    with engine.begin() as connection:
        again = curate(connection, email, 1, random.Random(4))
    assert first["removed"] == 2 and first["created"] == 2  # Padel Nation, Glow Beauty out
    assert again["removed"] == 0 and again["created"] == 0
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT t.name, array_agg(DISTINCT l.kind) FILTER (WHERE l.kind IS NOT NULL)
                FROM app.tenants t
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                JOIN app.users u ON u.id = m.user_id AND u.email = :email
                LEFT JOIN app.locations l ON l.tenant_id = t.id GROUP BY t.name
            """),
            {"email": email},
        ).all()
        foreign_left = connection.execute(
            text("SELECT count(*) FROM app.tenants WHERE id = :id"), {"id": foreign}
        ).scalar_one()
    kinds = dict(rows)
    assert set(kinds) == {"Adir fitness", "Studio Bloom", "Urban Slice"}
    assert {"gym", "pilates", "crossfit"} <= set(kinds["Adir fitness"])
    assert foreign_left == 1


def test_full_demo_builds_four_businesses_with_eleven_branches(engine: Engine) -> None:
    from app.catalog.verticals import CATALOG

    owner = uuid4()
    email = f"full-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        seed_demo(connection, email, "networks", 1, random.Random(4))  # the old three go away
    with engine.begin() as connection:
        first = curate(connection, email, 1, random.Random(4), "full")
    with engine.begin() as connection:
        again = curate(connection, email, 1, random.Random(4), "full")
    assert first["removed"] == 3 and first["created"] == 4
    assert again["removed"] == 0 and again["created"] == 0
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT t.name, t.vertical, count(DISTINCT l.id), array_agg(DISTINCT l.kind),
                  (SELECT count(*) FROM app.quotes q WHERE q.tenant_id = t.id),
                  (SELECT count(*) FROM app.ai_conversations c WHERE c.tenant_id = t.id)
                FROM app.tenants t
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                JOIN app.users u ON u.id = m.user_id AND u.email = :email
                LEFT JOIN app.locations l ON l.tenant_id = t.id GROUP BY t.id, t.name, t.vertical
            """),
            {"email": email},
        ).all()
    by_name = {r[0]: r for r in rows}
    assert set(by_name) == {"אדיר פיטנס", "טניס קלאב השרון", "בלייד ברברס", "מרחב - בריאות ותנועה"}
    assert sum(r[2] for r in rows) == 11
    assert [by_name[n][2] for n in ("אדיר פיטנס", "טניס קלאב השרון")] == [5, 2]
    with engine.connect() as connection:
        courts = dict(
            connection.execute(
                text("""
                    SELECT l.name, count(*) FROM app.rooms r
                    JOIN app.locations l ON l.id = r.location_id
                    JOIN app.tenants t ON t.id = r.tenant_id
                    WHERE t.name = 'טניס קלאב השרון' AND r.bookable GROUP BY l.name
                """)
            ).all()
        )
        pilates_classes = {
            row[0]
            for row in connection.execute(
                text("""
                    SELECT DISTINCT sv.name FROM app.sessions s
                    JOIN app.services sv ON sv.id = s.service_id
                    JOIN app.locations l ON l.id = s.location_id
                    WHERE l.name = 'רמת גן - פילאטיס ויוגה' AND sv.booking_mode = 'class'
                """)
            )
        }
    assert courts["הרצליה"] >= 6 and courts["ראשון לציון"] >= 4
    assert pilates_classes == {"פילאטיס מכשירים", "פילאטיס מזרן", "יוגה פלואו"}
    for _name, vertical, _branches, kinds, quotes, chats in rows:
        category = CATALOG[CATALOG[vertical].category]
        assert set(kinds) <= {category.key, vertical, *category.branch_kinds}
        assert quotes == 4 and chats >= 1  # tailored by role, not by the business name


def test_full_demo_has_the_hero_clients_and_morning_scenarios(engine: Engine) -> None:
    owner = uuid4()
    email = f"heroes-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        curate(connection, email, 1, random.Random(4), "full")
    with engine.connect() as connection:
        heroes = connection.execute(
            text("""
                SELECT t.name, c.custom_fields->>'demo_hero', c.id FROM app.clients c
                JOIN app.tenants t ON t.id = c.tenant_id
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                JOIN app.users u ON u.id = m.user_id AND u.email = :email
                WHERE c.custom_fields ? 'demo_hero'
            """),
            {"email": email},
        ).all()
        by_hero: dict[str, set[str]] = {}
        for business, slug, _ in heroes:
            by_hero.setdefault(slug, set()).add(business)
        assert set(by_hero) == {
            "noa", "omer", "tamar", "yonatan", "dana", "ariel", "lior", "shira", "maya", "gali",
            "ron",
        }  # fmt: skip
        assert len(by_hero["ron"]) == 4 and len(by_hero["omer"]) == 2
        ids = {slug: cid for _, slug, cid in heroes if slug != "omer" and slug != "ron"}

        def one(sql: str, **params: object) -> object:
            return connection.execute(text(sql), params).scalar_one()

        # Noa has no health declaration; Tamar is first in line and her membership ends soon.
        noa_declarations = one(
            "SELECT count(*) FROM app.health_declarations WHERE client_id = :c", c=ids["noa"]
        )
        assert noa_declarations == 0
        assert (
            one(
                "SELECT count(*) FROM app.bookings WHERE client_id = :c AND status = 'waitlisted'",
                c=ids["tamar"],
            )
            == 1
        )
        assert one(
            "SELECT ends_on - current_date FROM app.entitlements WHERE client_id = :c",
            c=ids["tamar"],
        ) in (2, 3)  # the local date may be a day behind UTC
        assert (
            one(
                "SELECT sum(amount) FROM app.payments WHERE client_id = :c AND status = 'failed'",
                c=ids["yonatan"],
            )
            == 45000
        )
        assert (
            one(
                "SELECT count(*) FROM app.dependents WHERE client_id = :c "
                "AND NOT (details->>'medical_approval')::boolean",
                c=ids["dana"],
            )
            == 1
        )
        assert (
            one(
                "SELECT count(*) FROM app.bookings WHERE client_id = :c AND status = 'no_show'",
                c=ids["lior"],
            )
            == 3
        )
        assert one("SELECT rating FROM app.reviews WHERE client_id = :c", c=ids["gali"]) == 2
        assert (
            one("SELECT status FROM app.freeze_requests WHERE client_id = :c", c=ids["maya"])
            == "pending"
        )
        assert (
            one(
                "SELECT count(*) FROM app.promo_codes pc JOIN app.tenants t ON t.id = pc.tenant_id "
                "JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner' "
                "JOIN app.users u ON u.id = m.user_id AND u.email = :email "
                "WHERE pc.code = 'LASTCALL'",
                email=email,
            )
            == 4
        )


def test_networks_demo_has_the_round_5_features(engine: Engine) -> None:
    owner = uuid4()
    email = f"ai-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        tenants = seed_demo(connection, email, "networks", 1, random.Random(4))
    with engine.connect() as connection:
        for tenant in tenants:
            counts = connection.execute(
                text("""
                    SELECT
                      (SELECT count(*) FROM app.location_groups WHERE tenant_id = :t),
                      (SELECT count(*) FROM app.tenant_members
                         WHERE tenant_id = :t AND role = 'branch_manager'),
                      (SELECT count(*) FROM app.ai_agents WHERE tenant_id = :t),
                      (SELECT count(*) FROM app.ai_scheduled_tasks
                         WHERE tenant_id = :t AND status = 'active'),
                      (SELECT count(*) FROM app.ai_task_runs WHERE tenant_id = :t),
                      (SELECT count(*) FROM app.social_accounts WHERE tenant_id = :t),
                      (SELECT count(*) FROM app.social_posts WHERE tenant_id = :t),
                      (SELECT count(*) FROM app.social_drafts WHERE tenant_id = :t),
                      (SELECT count(*) FROM app.contact_emails WHERE tenant_id = :t),
                      (SELECT sum(quantity) FROM app.usage_events
                         WHERE tenant_id = :t AND meter = 'ai_credits')
                """),
                {"t": tenant},
            ).one()
            (
                groups,
                managers,
                agents,
                tasks,
                runs,
                accounts,
                posts,
                drafts,
                emails,
                credits,
            ) = counts
            assert groups == 2 and managers == 1  # every network has several branches
            assert agents == 2 and tasks == 1 and runs == 3
            assert accounts == 6 and posts > 0 and drafts == 3 and emails == 3
            assert 0 < credits < 400  # inside the plan's monthly credits


def test_platform_demo_has_broadcasts(engine: Engine) -> None:
    staff = uuid4()
    email = f"plat-{staff.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": staff, "email": email},
        )
        seed_platform(connection, email, 1, random.Random(2))
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT status FROM app.announcements WHERE created_by = 'demo generator'")
        ).scalars().all()  # fmt: skip
    assert sorted(rows) == ["draft", "sent"]


def test_curated_demo_has_round_6_pay_hours_run_and_move_without_repeating(
    engine: Engine,
) -> None:
    owner = uuid4()
    email = f"r6-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
    with engine.begin() as connection:
        first = curate(connection, email, 1, random.Random(4))
    with engine.begin() as connection:
        again = enrich_profiles(connection, email)
    assert first["pay_setups"] > 0 and first["payroll_runs"] == 3 and first["move_sessions"] == 1
    assert again["pay_setups"] == 0 and again["payroll_runs"] == 0 and again["move_sessions"] == 0
    with engine.connect() as connection:
        rows = connection.execute(
            text("""
                SELECT t.name,
                  (SELECT count(*) FROM app.employment_profiles p WHERE p.tenant_id = t.id),
                  (SELECT count(*) FROM app.time_clock_approvals a WHERE a.tenant_id = t.id),
                  (SELECT count(*) FROM app.payroll_runs r WHERE r.tenant_id = t.id
                     AND r.stage = 'hours'),
                  (SELECT count(*) FROM app.payroll_run_lines l WHERE l.tenant_id = t.id
                     AND l.gross_minor > 0),
                  (SELECT count(*) FROM app.import_files i WHERE i.tenant_id = t.id
                     AND i.kind = 'clients' AND i.row_count = 14 AND i.file_id IS NOT NULL)
                FROM app.tenants t
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                WHERE m.user_id = :owner
            """),
            {"owner": owner},
        ).all()
    assert len(rows) == 3
    for name, profiles, approvals, runs, paid_lines, move_files in rows:
        assert profiles == approvals and profiles > 0
        assert runs == 1 and paid_lines == profiles
        assert move_files == (1 if name == "Adir fitness" else 0)


def test_curated_demo_fills_every_tenant_table_or_says_why_not(engine: Engine) -> None:
    from app.seed.round7 import NO_DEMO

    owner = uuid4()
    email = f"r7-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
    with engine.begin() as connection:
        curate(connection, email, 1, random.Random(4))
    with engine.begin() as connection:
        again = enrich_profiles(connection, email)
    assert again["round7"] == 0  # safe to run again

    with engine.connect() as connection:
        tables = (
            connection.execute(
                text("""
                    SELECT c.table_name FROM information_schema.columns c
                    JOIN information_schema.tables t
                      ON t.table_schema = c.table_schema AND t.table_name = c.table_name
                    WHERE c.table_schema = 'app' AND c.column_name = 'tenant_id'
                      AND t.table_type = 'BASE TABLE'
                    ORDER BY 1
                """)
            )
            .scalars()
            .all()
        )
        tenants = connection.execute(
            text("""
                SELECT t.id FROM app.tenants t
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                WHERE m.user_id = :owner
            """),
            {"owner": owner},
        ).scalars().all()  # fmt: skip
        assert len(tenants) == 3
        filled = {
            table: connection.execute(
                text(
                    f"SELECT count(DISTINCT tenant_id) FROM app.{table} WHERE tenant_id = ANY(:t)"
                ),
                {"t": tenants},
            ).scalar_one()
            for table in tables
        }
    # Platform-wide data (no per-business rows by design) is not a business table.
    missing = sorted(t for t, n in filled.items() if n == 0 and t not in NO_DEMO)
    assert not missing, f"tables with no demo rows and no reason in NO_DEMO: {missing}"
    stale = sorted(t for t in NO_DEMO if t not in filled)
    assert not stale, f"NO_DEMO names tables that do not exist: {stale}"
    wrong = sorted(t for t in NO_DEMO if filled.get(t))
    assert not wrong, f"NO_DEMO lists tables that now have demo rows: {wrong}"
    # The features of round 7 are open in all three businesses.
    for table in (
        "quotes",
        "issued_documents",
        "ai_conversations",
        "pending_actions",
        "announcements",
        "consent_events",
        "shift_templates",
        "time_off_requests",
        "promo_codes",
        "whatsapp_conversations",
        "client_addresses",
        "audit_log",
    ):
        assert filled[table] == 3, table
    assert filled["subscription_cancellations"] == 1
    assert filled["website_orders"] == 2 and filled["entitlement_freezes"] >= 1
    for table in (
        "waitlist_requests",
        "freeze_requests",
        "tenant_freeze_rules",
        "client_documents",
    ):
        assert filled[table] == 3, table
    with engine.connect() as connection:
        sizes = connection.execute(
            text("SELECT business_size FROM app.tenants WHERE id = ANY(:t)"), {"t": tenants}
        ).scalars().all()  # fmt: skip
    assert None not in sizes and "solo" not in sizes


def test_the_seed_refuses_the_primary_owner_account(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.seed.guard import refuse_blocked_owner

    for call in (
        lambda c: curate(c, "Adire7399@gmail.com", 1, random.Random(1)),
        lambda c: enrich_profiles(c, "adire7399@gmail.com"),
        lambda c: seed_demo(c, "adire7399@gmail.com", "studio", 1, random.Random(1)),
    ):
        with engine.begin() as connection, pytest.raises(SystemExit, match="primary owner"):
            call(connection)
    monkeypatch.setenv("API_SEED_BLOCKED_EMAILS", " Someone@Example.com ,other@example.com")
    with pytest.raises(SystemExit):
        refuse_blocked_owner("someone@example.com")
    refuse_blocked_owner("fine@example.com")  # anyone else is allowed


class _CityCentres:
    """A map service that knows streets only on Herzl Street, and every city's centre."""

    def __init__(self) -> None:
        self.asked: list[dict] = []

    def find(self, *, street: str | None, house_number: str | None, city: str):
        from app.geo.geocoder import Point

        self.asked.append({"street": street, "house": house_number, "city": city})
        if street and street != "הרצל":
            return None
        return Point(31.0, 34.0)


def test_branches_without_a_point_get_their_city_street_and_point(engine: Engine) -> None:
    from app.geo.backfill import locate_branches, split_address

    assert split_address("הרצל 120, תל אביב (קומה 2)") == ("הרצל", "120", "תל אביב")
    assert split_address("שדרות רוטשילד 45, תל אביב") == ("שדרות רוטשילד", "45", "תל אביב")
    assert split_address("חיפה") == (None, None, "חיפה")

    owner = uuid4()
    email = f"geo-{owner.hex[:6]}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        tenant_id = seed(connection, email, 1, random.Random(2))
        connection.execute(
            text("UPDATE app.locations SET address = 'הרצל 20, באר שבע' WHERE tenant_id = :t"),
            {"t": tenant_id},
        )
        connection.execute(
            text("""
                INSERT INTO app.locations (tenant_id, name, address)
                VALUES (:t, 'No street match', 'ככה ככה 7, אילת'),
                       (:t, 'No city', 'שם 3, עיר שאינה קיימת')
            """),
            {"t": tenant_id},
        )
        fake = _CityCentres()
        first = locate_branches(connection, geocoder=fake)
        again = locate_branches(connection, geocoder=fake)
        rows = connection.execute(
            text("""
                SELECT name, city_code IS NOT NULL, latitude IS NOT NULL
                FROM app.locations WHERE tenant_id = :t ORDER BY name
            """),
            {"t": tenant_id},
        ).all()
    assert first["located"] >= 1 and first["city_only"] == 1 and first["unplaced"] == 1
    assert all(asked["street"] for asked in fake.asked)  # a city's centre is stored, not asked
    assert again == {"located": 0, "city_only": 0, "unplaced": 1}  # only the unplaced one is tried
    by_name = {name: (has_city, has_point) for name, has_city, has_point in rows}
    assert by_name["No street match"] == (True, True)  # fell back to the city's centre
    assert by_name["No city"] == (False, False)


def test_full_demo_connects_the_plus_logins_the_test_customer_and_friends(engine: Engine) -> None:
    owner, customer, friend = uuid4(), uuid4(), uuid4()
    tag = owner.hex[:6]
    email = f"social-{tag}@example.com"
    plus = {t: (uuid4(), f"social-{tag}+{t}@example.com") for t in ("manager", "branch", "coach")}
    with engine.begin() as connection:
        for user, address in (
            (owner, email),
            (customer, f"cust-{tag}@example.com"),
            (friend, f"social-{tag}+friend@example.com"),
            *plus.values(),
        ):
            connection.execute(
                text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
                {"id": user, "email": address},
            )
    with engine.begin() as connection:
        curate(connection, email, 1, random.Random(4), "full")
        first = seed_social(connection, email, f"cust-{tag}@example.com")
        again = seed_social(connection, email, f"cust-{tag}@example.com")
    assert first["logins"]["skipped"] and len(first["logins"]["linked"]) == 3
    assert again["shared"]["records_added"] == 0
    with engine.connect() as connection:
        roles = dict(
            connection.execute(
                text("""
                    SELECT m.user_id, m.role || ':' || cardinality(m.location_ids)
                    FROM app.tenant_members m WHERE m.user_id = ANY(:ids)
                """),
                {"ids": [u for u, _ in plus.values()]},
            ).all()
        )
        assert roles[plus["manager"][0]] == "manager:0"
        assert roles[plus["branch"][0]] == "branch_manager:1"
        assert roles[plus["coach"][0]] == "staff:1"
        businesses = connection.execute(
            text("""
                SELECT count(DISTINCT c.tenant_id) FROM app.clients c WHERE c.user_id = :u
            """),
            {"u": customer},
        ).scalar_one()
        assert businesses == 4
        friends = connection.execute(
            text("""
                SELECT count(*) FROM app.client_friendships f
                JOIN app.clients c ON c.id IN (f.requester_id, f.addressee_id)
                WHERE c.user_id = :u AND f.status = 'accepted'
            """),
            {"u": customer},
        ).scalar_one()
        shared = connection.execute(
            text("""
                SELECT count(*) FROM (SELECT user_id FROM app.clients WHERE user_id IS NOT NULL
                    GROUP BY user_id HAVING count(DISTINCT tenant_id) >= 3) s
            """)
        ).scalar_one()
        assert friends >= 5 and shared >= 4
        invites = connection.execute(
            text("""
                SELECT count(*) FROM app.class_invites i JOIN app.clients c ON c.id = i.invitee_id
                WHERE c.user_id = :u AND i.status = 'pending'
            """),
            {"u": customer},
        ).scalar_one()
        declarations = connection.execute(
            text("""
                SELECT count(*) FROM app.health_declarations d
                JOIN app.clients c ON c.id = d.client_id
                WHERE c.user_id = :u
            """),
            {"u": customer},
        ).scalar_one()
        assert invites >= 1 and declarations == 0
        # The customer and two friends in one class, plus a haircut if the barber has a slot.
        assert first["test_customer"]["bookings"] in (3, 4)
    assert CUSTOMER_EMAIL != "adire7399@gmail.com"  # a client, never the primary owner
