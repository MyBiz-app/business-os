# ruff: noqa: F811, F401
"""The defensive security agent (slice C5): read-only database checks, reports with a severity
the server sorts and counts, refusal outside staging, and the console permission."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai import security
from app.core.config import ENVIRONMENTS
from tests.conftest import AuthHeaders
from tests.test_assistant import FakeProvider, calls, says, use_provider
from tests.test_platform_ai import staff


def ask_security(client: TestClient, headers: dict, text_: str = "Check security"):
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "security"}, headers=headers
    )
    assert chat.status_code == 201, chat.text
    return client.post(
        f"/platform/ai/assistant/conversations/{chat.json()['id']}/messages",
        json={"text": text_},
        headers=headers,
    )


def result_of(provider: FakeProvider, index: int) -> dict:
    return provider.calls[index]["messages"][-1]["content"][0]


def test_production_is_never_an_allowed_environment() -> None:
    assert "production" in ENVIRONMENTS and "production" not in security.ALLOWED_ENVIRONMENTS


def test_the_database_checks_flag_a_table_the_api_reaches_without_rls(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, member = staff(engine, auth, "incidents.manage")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE app.zz_open_table (tenant_id uuid, note text)"))
        connection.execute(text("GRANT SELECT ON app.zz_open_table TO app_api"))
    try:
        provider = FakeProvider([calls("security_db_checks", {}), says("Found one.")])
        use_provider(provider)
        assert ask_security(client, member).status_code == 200
        out = result_of(provider, 1)["content"]
        assert "zz_open_table" in out and "table_without_rls" in out and "tables" in out
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE app.zz_open_table"))


def test_a_security_report_is_sorted_and_counted_by_the_server(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, member = staff(engine, auth, "incidents.manage")
    findings = [
        {"severity": "low", "status": "open", "title": "B", "evidence": "e", "fix": "f"},
        {"severity": "high", "status": "in_progress", "title": "A", "evidence": "e", "fix": "f"},
    ]
    provider = FakeProvider(
        [
            calls(
                "save_security_report", {"title": "Weekly", "summary": "Two.", "findings": findings}
            ),
            says("Saved."),
        ]
    )
    use_provider(provider)
    assert ask_security(client, member).status_code == 200
    assert "is_error" not in result_of(provider, 1)
    listed = client.get("/platform/ai/reports?kind=security", headers=member).json()
    report = client.get(f"/platform/ai/reports/{listed[0]['id']}", headers=member).json()
    assert [f["title"] for f in report["body"]["findings"]] == ["A", "B"]
    assert report["body"]["counts"]["high"] == 1 and report["body"]["counts"]["low"] == 1


def test_a_finding_without_a_valid_severity_or_a_fix_is_refused(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider
) -> None:
    _, _, member = staff(engine, auth, "incidents.manage")
    good = {"severity": "low", "status": "open", "title": "T", "evidence": "e", "fix": "f"}
    bad = [good | {"severity": "scary"}, good | {"status": "later"}, good | {"fix": " "}]
    steps = [
        calls("save_security_report", {"title": "t", "summary": "s", "findings": [b]}) for b in bad
    ]
    provider = FakeProvider([*steps, says("Could not save.")])
    use_provider(provider)
    assert ask_security(client, member).status_code == 200
    results = [result_of(provider, i) for i in range(1, 4)]
    assert all(r.get("is_error") for r in results)
    assert client.get("/platform/ai/reports?kind=security", headers=member).json() == []


def test_the_agent_refuses_to_run_in_production(
    client: TestClient, engine: Engine, auth: AuthHeaders, use_provider, monkeypatch
) -> None:
    _, _, member = staff(engine, auth, "incidents.manage")
    monkeypatch.setattr(security, "environment", lambda: "production")
    provider = FakeProvider([calls("security_db_checks", {}), says("Off.")])
    use_provider(provider)
    assert ask_security(client, member).status_code == 200
    assert result_of(provider, 1).get("is_error")
    assert "staging only" in result_of(provider, 1)["content"]


def test_without_the_permission_the_agent_and_its_checks_are_closed(
    client: TestClient, engine: Engine, auth: AuthHeaders, studio: dict
) -> None:
    _, _, nobody = staff(engine, auth)
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": "security"}, headers=nobody
    )
    assert chat.status_code in (403, 404)
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL ROLE app_api"))
        denied = False
        try:
            connection.execute(text("SELECT * FROM app.platform_security_db_checks()"))
        except Exception:
            denied = True
    assert denied
