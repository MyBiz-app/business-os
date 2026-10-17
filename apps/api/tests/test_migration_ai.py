import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.ai.gateway import LLMResponse, ProviderBusy, Usage, get_provider
from app.migration.ai_mapping import hide
from tests.conftest import STUDIO, AuthHeaders
from tests.test_migration import add, start

# Hebrew headers the synonym table does not know, with an ID number and a card in the examples.
ODD = (
    'שם המתאמן,ת"ז,כרטיס אשראי,כמה נשאר,פג ב\nדנה לוי,123456789,4580 1234 5678 9012,7,2027-01-31\n'
).encode()


class FakeProvider:
    model = "claude-haiku-5-5"

    def __init__(self, answer: object, fail: Exception | None = None) -> None:
        self.answer = answer
        self.fail = fail
        self.sent: list[str] = []

    def create(self, system, messages, tools, strong=False):
        self.sent.append(messages[0]["content"])
        if self.fail:
            raise self.fail
        text_ = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return LLMResponse(
            content=[{"type": "text", "text": text_}],
            stop_reason="end_turn",
            model=self.model,
            usage=Usage(input_tokens=600, output_tokens=120),
        )


@pytest.fixture
def use_provider(client: TestClient):
    def install(provider: FakeProvider | None) -> None:
        client.app.dependency_overrides[get_provider] = lambda: provider  # type: ignore[attr-defined]

    yield install
    client.app.dependency_overrides.pop(get_provider, None)  # type: ignore[attr-defined]


def spend_credits(engine: Engine, credits: float) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity)
                SELECT id, 'ai_credits', :q FROM app.tenants
            """),
            {"q": credits},
        )


def with_ai(client: TestClient, studio: dict) -> None:
    response = client.put(
        "/tenants/current/modules",
        json={"modules": {"client_app": 1, "ai_pro": 1}},
        headers=studio["headers"],
    )
    assert response.status_code == 200, response.text


def ai_map(client: TestClient, studio: dict, session: str, file_id: str):
    return client.post(
        f"/migration/sessions/{session}/files/{file_id}/ai-map", headers=studio["headers"]
    )


ANSWER = {
    "kind": "memberships",
    "columns": [
        {"field": "client_name", "confidence": 0.95},
        {"field": "client_name", "confidence": 0.9},  # a field twice: the first one wins
        {"field": "price", "confidence": 0.2},  # too unsure: stays unmapped
        {"field": "credits_left", "confidence": 0.9},
        {"field": "ends_on", "confidence": 0.85},
    ],
}


def test_hide_blanks_long_numbers_and_emails() -> None:
    assert hide("123456789") == "#########"
    assert hide("4580 1234 5678 9012") == "#### #### #### ####"
    assert hide("050-123-4567") == "###-###-####"
    assert hide("dana@example.org") == "user@example.com"
    assert hide("2026-10-17") == "2026-10-17"  # a date is not hidden
    assert hide("7") == "7"


def test_ai_fills_the_unrecognized_columns_and_the_model_never_sees_numbers(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    with_ai(client, studio)
    provider = FakeProvider(ANSWER)
    use_provider(provider)
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "odd.csv", ODD)
    assert uploaded["kind"] is None

    response = ai_map(client, studio, session, uploaded["id"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file"]["kind"] == "memberships"
    assert body["file"]["mapping"] == ["client_name", None, None, "credits_left", "ends_on"]
    assert body["source"] == ["ai", None, None, "ai", "ai"]
    assert body["confidence"][0] == 0.95 and body["confidence"][1] is None
    assert body["credits"] > 0

    sent = provider.sent[0]
    assert "123456789" not in sent and "4580" not in sent and "#########" in sent
    assert "דנה לוי" in sent  # a name is needed to see it is a name
    with engine.connect() as connection:
        used = connection.execute(
            text("""
                SELECT count(*), sum(quantity) FROM app.usage_events
                WHERE meter = 'ai_credits' AND details ->> 'channel' = 'migration'
            """)
        ).one()
    assert used[0] == 1 and float(used[1]) == body["credits"]


def test_recognized_columns_and_the_chosen_kind_are_kept(
    client: TestClient, studio: dict, use_provider
) -> None:
    with_ai(client, studio)
    use_provider(
        FakeProvider(
            {
                "kind": "services",  # ignored: the file is already known to be clients
                "columns": [
                    {"field": "phone", "confidence": 0.9},
                    {"field": "first_name", "confidence": 0.9},
                    {"field": "notes", "confidence": 0.8},
                ],
            }
        )
    )
    session = start(client, studio["headers"])
    uploaded = add(
        client,
        studio["headers"],
        session,
        "c.csv",
        b"Email,Last name,Mystery\na@b.co,Levi,x\n",
    )
    assert uploaded["kind"] == "clients"
    body = ai_map(client, studio, session, uploaded["id"]).json()
    assert body["file"]["kind"] == "clients"
    assert body["file"]["mapping"] == ["email", "last_name", "notes"]
    assert body["source"] == ["name", "name", "ai"]


@pytest.mark.parametrize(
    "answer",
    ["not json at all", {"kind": "nonsense"}, {"kind": "clients", "columns": [{"field": "x"}]}],
)
def test_a_bad_answer_changes_nothing(
    client: TestClient, studio: dict, use_provider, answer: object
) -> None:
    with_ai(client, studio)
    use_provider(FakeProvider(answer))
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "odd.csv", ODD)
    body = ai_map(client, studio, session, uploaded["id"]).json()
    assert body["file"]["kind"] is None
    assert body["file"]["mapping"] == [None] * 5


def test_ai_unavailable_busy_or_over_the_limit(
    client: TestClient, studio: dict, use_provider, engine: Engine
) -> None:
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "odd.csv", ODD)

    use_provider(None)
    assert ai_map(client, studio, session, uploaded["id"]).json()["detail"] == "ai_not_configured"

    spend_credits(engine, 100000)  # the month's allowance is gone
    use_provider(FakeProvider(ANSWER))
    response = ai_map(client, studio, session, uploaded["id"])
    assert response.status_code == 409 and response.json()["detail"] == "ai_limit_reached"

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM app.usage_events"))
    use_provider(FakeProvider(ANSWER, fail=ProviderBusy()))
    assert ai_map(client, studio, session, uploaded["id"]).status_code == 429


def test_the_number_of_ai_maps_per_move_is_limited(
    client: TestClient, studio: dict, use_provider
) -> None:
    with_ai(client, studio)
    use_provider(FakeProvider({"kind": None}))
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "odd.csv", ODD)
    for _ in range(20):
        assert ai_map(client, studio, session, uploaded["id"]).status_code == 200
    response = ai_map(client, studio, session, uploaded["id"])
    assert response.status_code == 429 and response.json()["detail"] == "ai_map_limit"


def test_another_business_cannot_use_the_file(
    client: TestClient, studio: dict, auth: AuthHeaders, use_provider
) -> None:
    stranger = uuid4()
    tenant = UUID(client.post("/tenants", json=STUDIO, headers=auth(stranger)).json()["id"])
    other_studio = {"headers": auth(stranger, tenant)}
    use_provider(FakeProvider(ANSWER))
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "odd.csv", ODD)
    response = client.post(
        f"/migration/sessions/{session}/files/{uploaded['id']}/ai-map",
        headers=other_studio["headers"],
    )
    assert response.status_code == 404


def test_google_contacts_template_needs_no_ai(client: TestClient, studio: dict) -> None:
    csv = (
        b"First Name,Middle Name,Last Name,Birthday,E-mail 1 - Label,E-mail 1 - Value,"
        b"Phone 1 - Label,Phone 1 - Value,Notes\n"
        b"Dana,,Levi,1990-05-12,Home,dana@example.com,Mobile,0501234567,VIP\n"
    )
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "contacts.csv", csv)
    assert uploaded["kind"] == "clients"
    assert uploaded["mapping"] == [
        "first_name", None, "last_name", "date_of_birth", None, "email", None, "phone", "notes"
    ]  # fmt: skip


def test_vcard_file_becomes_clients(client: TestClient, studio: dict) -> None:
    vcf = (
        b"BEGIN:VCARD\r\nVERSION:3.0\r\nN:Levi;Dana;;;\r\nFN:Dana Levi\r\n"
        b"TEL;TYPE=CELL:050-123-4567\r\nEMAIL:dana@example.com\r\nEND:VCARD\r\n"
        b"BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Yossi Cohen\r\nTEL:052-111-2233\r\nEND:VCARD\r\n"
    )
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "phone.vcf", vcf)
    assert uploaded["kind"] == "clients" and uploaded["rows"] == 2
    assert [c["example"] for c in uploaded["columns"]][:4] == [
        "Dana", "Levi", "050-123-4567", "dana@example.com"
    ]  # fmt: skip


def test_calendar_file_becomes_appointments(client: TestClient, studio: dict) -> None:
    ics = (
        b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Yoga\r\n"
        b'ATTENDEE;CN="Dana Levi":mailto:dana@example.com\r\n'
        b"DTSTART:20261103T093000\r\nDTEND:20261103T103000\r\nEND:VEVENT\r\n"
        b"BEGIN:VEVENT\r\nSUMMARY:Pilates\r\nDTSTART;VALUE=DATE:20261104\r\nEND:VEVENT\r\n"
        b"END:VCALENDAR\r\n"
    )
    session = start(client, studio["headers"])
    uploaded = add(client, studio["headers"], session, "cal.ics", ics)
    assert uploaded["kind"] == "appointments" and uploaded["rows"] == 2
    examples = {c["name"]: c["example"] for c in uploaded["columns"]}
    assert examples["Service"] == "Yoga" and examples["Client"] == "Dana Levi"
    assert examples["Date"] == "2026-11-03" and examples["Time"] == "09:30"
    assert examples["Duration"] == "60"
