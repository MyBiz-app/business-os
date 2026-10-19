# ruff: noqa: F811, F401
"""The legal and accountant agents (slice C3b): the country of a business, the fixed "not advice"
line, the guides their libraries start with, and the 40-question test set."""

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai import professional, professional_eval
from app.ai.untrusted import unwrap
from tests.conftest import AuthHeaders, make_staff
from tests.test_assistant import FakeProvider, calls, says, use_provider

MIGRATION = (
    Path(__file__).parents[1] / "migrations/versions/0149_country_and_professional_guides.py"
)


def migration():
    spec = importlib.util.spec_from_file_location("country_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def owner(engine: Engine, auth: AuthHeaders) -> dict:
    user = uuid4()
    make_staff(engine, user, "owner", ("billing.manage", "businesses.read"))
    return auth(user)


def ask_agent(client: TestClient, headers: dict, role: str, question: str) -> dict:
    chat = client.post(
        "/platform/ai/assistant/conversations", json={"role": role}, headers=headers
    ).json()
    reply = client.post(
        f"/platform/ai/assistant/conversations/{chat['id']}/messages",
        json={"text": question},
        headers=headers,
    )
    assert reply.status_code == 200, reply.text
    return reply.json()


# --- The notice ---------------------------------------------------------------------------------


def test_the_notice_follows_the_language_of_the_question_and_only_these_two_agents() -> None:
    assert "ייעוץ משפטי" in professional.notice_for("legal", "מה החוק?")
    assert "legal advice" in professional.notice_for("legal", "What is the law?")
    assert "רואה חשבון" in professional.notice_for("accountant", 'כמה מע"מ?')
    assert "accounting or tax advice" in professional.notice_for("accountant", "How much VAT?")
    assert professional.notice_for("billing", "How much VAT?") is None


def test_the_notice_is_added_once() -> None:
    first = professional.with_notice("legal", "Is it legal?", "Yes, see the guide.")
    assert first.endswith(professional.notice_for("legal", "Is it legal?"))
    assert professional.with_notice("legal", "Is it legal?", first) == first


def test_every_answer_of_the_legal_and_accountant_agents_ends_with_the_notice(
    client: TestClient, owner: dict, use_provider
) -> None:
    for role, question, line in (
        (
            "legal",
            "May we text clients?",
            "This is a draft, not legal advice. Check it with a lawyer.",
        ),
        ("accountant", 'מה שיעור המע"מ?', "יש לבדוק אותה עם רואה חשבון."),
    ):
        use_provider(FakeProvider([says("Short answer.")]))
        chat = ask_agent(client, owner, role, question)
        assert chat["turns"][-1]["text"].endswith(line)
    use_provider(FakeProvider([says("Short answer.")]))
    other = ask_agent(client, owner, "billing", "How much was billed?")
    assert "not legal advice" not in other["turns"][-1]["text"]


# --- Country --------------------------------------------------------------------------------------


def test_a_business_gets_its_country_from_its_currency(engine: Engine) -> None:
    assert professional.country_of("ILS") == "IL" and professional.country_of("USD") == "US"
    assert professional.country_of("EUR") is None
    with engine.begin() as connection:
        rows = {}
        for currency in ("ILS", "USD", "EUR"):
            rows[currency] = connection.execute(
                text(
                    "INSERT INTO app.tenants (name, vertical, locale, time_zone, currency) "
                    "VALUES ('Country test', 'fitness', 'en', 'UTC', :c) RETURNING country"
                ),
                {"c": currency},
            ).scalar_one()
        assert rows == {"ILS": "IL", "USD": "US", "EUR": None}
        connection.execute(text("DELETE FROM app.tenants WHERE name = 'Country test'"))


def test_the_agents_see_the_country_of_a_business(
    client: TestClient, engine: Engine, owner: dict, use_provider
) -> None:
    with engine.begin() as connection:
        tenant = connection.execute(
            text(
                "INSERT INTO app.tenants (name, vertical, locale, time_zone, currency) "
                "VALUES ('Texas Studio', 'fitness', 'en', 'America/Chicago', 'USD') RETURNING id"
            )
        ).scalar_one()
    provider = FakeProvider(
        [calls("business_detail", {"id": str(tenant)}), says("Texas Studio is in the US.")]
    )
    use_provider(provider)
    ask_agent(client, owner, "legal", "Which rules apply to Texas Studio?")
    names = {t["name"] for t in provider.calls[0]["tools"]}
    assert {"business_detail", "list_businesses", "search_library"} <= names
    detail = json.loads(unwrap(provider.calls[1]["messages"][-1]["content"][0]["content"]))
    assert detail["country"] == "US"
    system = provider.calls[0]["system"]
    assert "Israel (IL) and the United States (US)" in system
    assert "I did not find this in the library" in system


# --- The guides -----------------------------------------------------------------------------------


def test_the_guides_are_cut_into_sections_with_a_source_for_each() -> None:
    module = migration()
    for _agent, name, *_ in module.GUIDE_DOCUMENTS:
        body = professional.guide(name)
        parts = module.sections(body)
        assert len(parts) >= 6
        assert all(heading for heading, _ in parts[1:])
        # every rule section names where it comes from; the last one says what is not covered
        for heading, content in parts[:-1]:
            if heading and "Status" not in content[:7]:
                assert "Source" in content or "source" in content, (name, heading)
    assert {a for a, *_ in module.GUIDE_DOCUMENTS} == {"legal", "accountant"}


def test_the_legal_and_accountant_libraries_answer_from_their_guides(
    client: TestClient, engine: Engine, owner: dict
) -> None:
    module = migration()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM app.platform_kb_documents"))
        module.seed_guides(connection)
    legal = client.get("/platform/ai/agents/legal/library", headers=owner).json()
    assert {d["title"] for d in legal} == {
        "Draft guide: legal, Israel",
        "Draft guide: legal, United States",
    }
    assert all(d["reviewed_on"] is None and d["chunks"] >= 6 for d in legal)  # not reviewed yet
    hits = client.get(
        "/platform/ai/agents/accountant/library/search",
        params={"q": "allocation number invoice"},
        headers=owner,
    ).json()
    assert hits and hits[0]["document"] == "Draft guide: tax, Israel"
    assert hits[0]["country"] == "il"


# --- The test set ---------------------------------------------------------------------------------


def test_the_test_set_has_enough_questions_for_both_agents_and_both_countries() -> None:
    rows = professional_eval.questions()
    assert 30 <= len(rows) <= 50
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    for agent in ("legal", "accountant"):
        for country in ("IL", "US"):
            assert sum(r["agent"] == agent and r["country"] == country for r in rows) >= 5
    assert {r["kind"] for r in rows} == set(professional_eval.KINDS)
    assert {r["lang"] for r in rows} == {"he", "en"}
    for r in rows:
        assert r["question"].strip() and r["must"] and all(r["must"])
        assert all(isinstance(g, list) and g for g in r["must"])


def test_the_scoring_needs_every_group_and_the_notice() -> None:
    row = next(r for r in professional_eval.questions() if r["id"] == "acc-us-02")
    good = professional.with_notice("accountant", row["question"], "Form 941, every quarter.")
    assert professional_eval.score(row, good).passed
    assert not professional_eval.score(row, "Form 941, every quarter.").passed  # no notice
    wrong = professional.with_notice("accountant", row["question"], "Form 1040.")
    result = professional_eval.score(row, wrong)
    assert not result.passed and result.missing == [["941"]]


def test_a_run_gives_a_score_and_lists_what_failed() -> None:
    def ask(agent: str, question: str) -> str:
        return professional.with_notice(agent, question, "I did not find this in the library.")

    _, report = professional_eval.run(ask, "legal", limit=4)
    assert report["questions"] == 4 and report["passed"] <= 4
    assert report["failed"] and report["score"] == round(100 * report["passed"] / 4)
