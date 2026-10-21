"""The AI's view of the insights map (W4-6): counts per city, nothing below 5, no names."""

import json
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.untrusted import unwrap
from tests.conftest import local_today
from tests.test_assistant import FakeProvider, ask, calls, conversation, says
from tests.test_assistant import use_provider as use_provider
from tests.test_business_map import KIRYAT_SHMONA, TEL_AVIV, add_clients, add_leads

PERIOD = {
    "start_date": (local_today() - timedelta(days=30)).isoformat(),
    "end_date": (local_today() + timedelta(days=1)).isoformat(),
}


def run_tool(client: TestClient, studio: dict, use_provider) -> tuple[dict, str]:
    provider = FakeProvider([calls("map_areas", PERIOD), says("Done.")])
    use_provider(provider)
    headers = studio["headers"]
    ask(client, headers, conversation(client, headers), "Where are my leads?")
    raw = provider.calls[1]["messages"][-1]["content"][0]["content"]
    return json.loads(unwrap(raw)), raw


def test_the_analyst_tool_hides_small_counts_and_names(
    client: TestClient, engine: Engine, studio: dict, use_provider
) -> None:
    tenant = studio["tenant_id"]
    big = add_clients(engine, tenant, TEL_AVIV, 6)
    add_clients(engine, tenant, KIRYAT_SHMONA, 3)
    add_leads(engine, tenant, TEL_AVIV, 5, stage="won")
    add_leads(engine, tenant, KIRYAT_SHMONA, 2)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app.locations SET city_code = :c WHERE tenant_id = :t"),
            {"c": TEL_AVIV, "t": tenant},
        )

    found, raw = run_tool(client, studio, use_provider)

    assert len(found["areas"]) == 1, "Kiryat Shmona has 3 clients and 2 leads: not listed"
    tel_aviv = found["areas"][0]
    assert tel_aviv["clients"] == 6 and tel_aviv["leads"] == 5
    assert tel_aviv["lead_conversion_percent"] == 100
    assert tel_aviv["has_branch_in_city"] is True
    assert found["other_cities"] == {"clients": None, "leads": None}
    # Nothing that identifies a person or a place goes to the model.
    assert not any(client_id in raw for client_id in big)
    assert "street" not in raw and "city_code" not in raw


def test_a_big_client_count_does_not_reveal_a_small_lead_count(
    client: TestClient, engine: Engine, studio: dict, use_provider
) -> None:
    add_clients(engine, studio["tenant_id"], TEL_AVIV, 7)
    add_leads(engine, studio["tenant_id"], TEL_AVIV, 2, stage="won")

    found, _ = run_tool(client, studio, use_provider)

    row = found["areas"][0]
    assert row["clients"] == 7
    assert row["leads"] is None and row["leads_won"] is None
    assert row["lead_conversion_percent"] is None
    assert row["has_branch_in_city"] is False
