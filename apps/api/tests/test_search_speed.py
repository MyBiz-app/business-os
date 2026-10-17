"""Searching clients stays fast at 20,000 clients, and the trigram index is what answers it
(go-live GL17)."""

import time

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.test_leads import with_crm

CLIENTS = 20_000


def _fill(engine: Engine, tenant_id: object) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.clients (tenant_id, first_name, last_name, email, phone)
                SELECT :tenant, 'First' || n, 'Last' || (n % 997),
                       'person' || n || '@example.com', '05' || lpad(n::text, 8, '0')
                FROM generate_series(1, :count) AS n
            """),
            {"tenant": tenant_id, "count": CLIENTS},
        )
        connection.execute(text("ANALYZE app.clients"))


def test_client_search_is_fast_with_20000_clients(
    client: TestClient, studio: dict, engine: Engine
) -> None:
    with_crm(client, studio)
    _fill(engine, studio["tenant_id"])
    headers = studio["headers"]

    started = time.perf_counter()
    found = client.get("/clients", params={"search": "person19999@"}, headers=headers)
    elapsed = time.perf_counter() - started

    assert found.status_code == 200
    assert [c["email"] for c in found.json()["items"]] == ["person19999@example.com"]
    # Most of the time is the app and the connection; the query itself is a few milliseconds.
    assert elapsed < 0.5, f"search took {elapsed * 1000:.0f} ms"


def test_client_search_function_uses_the_trigram_index(engine: Engine, studio: dict) -> None:
    from app.api.clients import SEARCH_TEXT

    _fill(engine, studio["tenant_id"])
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL enable_seqscan = off"))
        plan = connection.execute(
            text(f"EXPLAIN SELECT id FROM app.clients WHERE {SEARCH_TEXT} ILIKE '%person19999%'")
        ).scalars()
        plan_text = "\n".join(plan)
    assert "clients_search_trgm_idx" in plan_text, plan_text


def test_extensions_live_outside_public(engine: Engine) -> None:
    with engine.connect() as connection:
        schemas = dict(
            connection.execute(
                text("""
                    SELECT e.extname, n.nspname FROM pg_extension e
                    JOIN pg_namespace n ON n.oid = e.extnamespace
                    WHERE e.extname IN ('pg_trgm', 'btree_gist')
                """)
            ).all()
        )
    assert schemas == {"pg_trgm": "extensions", "btree_gist": "extensions"}
