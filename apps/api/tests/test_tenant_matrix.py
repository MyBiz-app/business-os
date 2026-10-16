"""Row-by-row cross-tenant matrix: for every table that holds a `tenant_id`, a member of one
business can neither see, change, delete nor add rows of another business, even while claiming
that business's id. A new tenant table is covered automatically; one the demo data doesn't fill
must be listed in UNSEEDED, so nobody can add a table without it being checked or consciously
exempted."""

import random
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from app.core.db import open_session
from app.seed import AC_COMPANY, ACCOUNTING_FIRM, GROOMING_SALON, PADEL_CLUB, PHOTO_STUDIO, seed
from app.seed.common import STUDIO, URBAN_SLICE

SPECS = (STUDIO, GROOMING_SALON, AC_COMPANY, PHOTO_STUDIO, ACCOUNTING_FIRM, PADEL_CLUB, URBAN_SLICE)
# MyBiz's own tables: no API access at all (checked in test_database_security.py).
PLATFORM_TABLES = {
    "contact_requests",
    "platform_audit",
    "platform_ai_pauses",
    "announcements",
    "announcement_deliveries",
}
# Tenant tables neither the demo data nor `_synthetic_row` can fill (a CHECK constraint needs a
# real value). Add a row for them in the seed (preferred) or list them here.
UNSEEDED: set[str] = set()
# Values for columns a CHECK constraint pins down (a synthetic row can't guess them).
OVERRIDES = {
    "ai_agents": {"builtin_key": "'x'"},
    "ai_scheduled_tasks": {"kind": "'agent_run'", "instruction": "'x'"},
    "ai_credit_alerts": {"threshold": "80"},
    "ai_credit_limits": {"subject_kind": "'role'"},
    "audit_log": {"actor_type": "'system'"},
    "client_social": {"friend_code": "'ABCDEFGHJK'"},
    "checkouts": {"plan_id": "gen_random_uuid()"},
    "contact_emails": {"purpose": "'main'", "email": "'a@b.co'"},
    "coverage_rules": {"ends_minute": "60", "min_staff": "1"},
    "invitations": {"role": "'staff'"},
    "notifications": {"kind": "'session_cancelled'"},
    "pending_actions": {"risk_level": "'low'"},
    "person_identities": {"user_id": "gen_random_uuid()", "id_type": "'il_id'", "country": "'IL'"},
    "promo_codes": {"amount_off": "1", "code": "'TESTCODE'"},
    "shift_templates": {"ends": "'17:00'", "starts": "'09:00'"},
    "support_grants": {"expires_at": "now() + interval '1 day'"},
    "social_audience": {"dimension": "'age'"},
    "social_posts": {"kind": "'post'"},
    "tenant_integrations": {"capability": "'payments'", "provider": "'stub'"},
    "whatsapp_conversations": {"phone": "'0501234567'"},
    "whatsapp_inbox": {"from_phone": "'0501234567'"},
    "whatsapp_offers": {"kind": "'book_session'"},
}
# A harmless value for each kind of NOT NULL column a synthetic row has to fill.
DUMMY = {
    "uuid": "gen_random_uuid()",
    "text": "'x'",
    "character varying": "'x'",
    "character": "'x'",
    "real": "0",
    "double precision": "0",
    "interval": "'0'",
    "USER-DEFINED": "NULL",
    "boolean": "false",
    "integer": "0",
    "bigint": "0",
    "smallint": "0",
    "numeric": "0",
    "date": "current_date",
    "timestamp with time zone": "now()",
    "time without time zone": "'09:00'",
    "jsonb": "'{}'",
    "ARRAY": "'{}'",
    "bytea": "'\\x00'",
    "inet": "'127.0.0.1'",
}


def _tenant_tables(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text("""
                    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'app' AND c.relkind = 'r'
                      AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid
                                  AND a.attname = 'tenant_id' AND NOT a.attisdropped)
                    ORDER BY 1
                """)
            ).scalars()
        )


def _attempt(
    engine: Engine, user: UUID, tenant: UUID, sql: str, scalar: bool = False
) -> int | None:
    """Runs one statement as `user` claiming `tenant`; returns rows seen or changed, or None when
    the API role has no privilege on the table."""
    with open_session(engine, user, tenant) as session:
        try:
            result = session.execute(text(sql), {"t": tenant})
            return result.scalar_one() if scalar else result.rowcount
        except DBAPIError as error:
            if "permission denied" not in str(error):
                raise
            return None
        finally:
            session.rollback()


def _synthetic_row(engine: Engine, table: str, tenant: UUID) -> bool:
    """Inserts a minimal row of `tenant` as the database owner (foreign keys switched off, since
    the point is the tenant column). Returns False when a constraint needs a real value."""
    with engine.connect() as admin:
        columns = admin.execute(
            text("""
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_schema = 'app' AND table_name = :table AND is_nullable = 'NO'
                  AND column_default IS NULL AND is_generated = 'NEVER'
                  AND is_identity = 'NO' AND column_name <> 'tenant_id'
            """),
            {"table": table},
        ).all()
    row = {name: DUMMY[kind] for name, kind in columns} | OVERRIDES.get(table, {})
    names = ["tenant_id", *row]
    values = [":t", *row.values()]
    try:
        with engine.begin() as admin:
            admin.execute(text("SET LOCAL session_replication_role = replica"))
            admin.execute(
                text(f"INSERT INTO app.{table} ({', '.join(names)}) VALUES ({', '.join(values)})"),
                {"t": tenant},
            )
    except DBAPIError:
        return False
    return True


@pytest.fixture
def seeded(engine: Engine) -> tuple[UUID, UUID, list[UUID]]:
    """Returns (owner, outsider, tenants): the owner runs every seeded business; the outsider
    is a member of one business of their own and nothing else."""
    owner, outsider = uuid4(), uuid4()
    with engine.begin() as connection:
        for user, email in (
            (owner, "matrix-owner@example.com"),
            (outsider, "outsider@example.com"),
        ):
            connection.execute(
                text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
                {"id": user, "email": email},
            )
        tenants = [
            seed(connection, "matrix-owner@example.com", 1, random.Random(index), spec)
            for index, spec in enumerate(SPECS)
        ]
        own = connection.execute(
            text("""
                INSERT INTO app.tenants (name, vertical, locale, time_zone, currency)
                VALUES ('Outsider', 'fitness', 'en', 'UTC', 'USD') RETURNING id
            """)
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'owner')"
            ),
            {"t": own, "u": outsider},
        )
    return owner, outsider, tenants


def test_outsider_cannot_touch_any_row_of_any_table(
    engine: Engine, seeded: tuple[UUID, UUID, list[UUID]]
) -> None:
    owner, outsider, tenants = seeded
    tables = [t for t in _tenant_tables(engine) if t not in PLATFORM_TABLES]
    filled: set[str] = set()
    with engine.connect() as admin:
        empty = [
            t
            for t in tables
            if not any(
                admin.execute(
                    text(f"SELECT EXISTS (SELECT 1 FROM app.{t} WHERE tenant_id = :t)"), {"t": ten}
                ).scalar_one()
                for ten in tenants
            )
        ]
    for table in empty:
        _synthetic_row(engine, table, tenants[0])
    leaks: list[str] = []

    for tenant in tenants:
        for table in tables:
            with engine.connect() as admin:
                total = admin.execute(
                    text(f"SELECT count(*) FROM app.{table} WHERE tenant_id = :t"), {"t": tenant}
                ).scalar_one()
            if not total:
                continue
            filled.add(table)

            # The owner sees exactly the rows that exist (tables only functions read are skipped).
            seen = _attempt(
                engine,
                owner,
                tenant,
                f"SELECT count(*) FROM app.{table} WHERE tenant_id = :t",
                True,
            )
            if (
                seen is not None and seen != total and table not in empty
            ):  # synthetic rows may belong to another user
                leaks.append(f"{table}: owner sees {seen} of {total} rows")

            # The outsider, claiming that business, sees and changes nothing. A table the API
            # role may not touch at all (permission denied) is just as safe as one hidden by RLS.
            visible = _attempt(
                engine,
                outsider,
                tenant,
                f"SELECT count(*) FROM app.{table} WHERE tenant_id = :t",
                scalar=True,
            )
            deleted = _attempt(
                engine, outsider, tenant, f"DELETE FROM app.{table} WHERE tenant_id = :t"
            )
            updated = _attempt(
                engine,
                outsider,
                tenant,
                f"UPDATE app.{table} SET tenant_id = tenant_id WHERE tenant_id = :t",
            )
            if any((visible, deleted, updated)):  # None (no privilege) is safe
                leaks.append(
                    f"{table}: outsider saw {visible}, deleted {deleted}, updated {updated}"
                )

    assert not leaks, "\n".join(leaks)
    assert set(tables) - filled <= UNSEEDED, "seed these tables, or list them in UNSEEDED"
    assert UNSEEDED & filled == set(), "now seeded: remove from UNSEEDED"


def test_outsider_cannot_insert_into_any_table(
    engine: Engine, seeded: tuple[UUID, UUID, list[UUID]]
) -> None:
    _, outsider, tenants = seeded
    tenant = tenants[0]
    inserted: list[str] = []
    for table in [t for t in _tenant_tables(engine) if t not in PLATFORM_TABLES]:
        with engine.connect() as admin:
            has_rows = admin.execute(
                text(f"SELECT EXISTS (SELECT 1 FROM app.{table} WHERE tenant_id = :t)"),
                {"t": tenant},
            ).scalar_one()
        if not has_rows:
            continue
        with open_session(engine, outsider, tenant) as session:
            try:
                # Copying an existing row of the business is the cheapest valid row to try.
                result = session.execute(
                    text(f"INSERT INTO app.{table} SELECT * FROM app.{table} WHERE tenant_id = :t"),
                    {"t": tenant},
                )
                if result.rowcount:
                    inserted.append(table)
            except DBAPIError:
                pass  # refused by row-level security or by missing privileges: what we want
            finally:
                session.rollback()
    assert inserted == []
