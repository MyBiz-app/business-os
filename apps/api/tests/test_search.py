"""Global search (Cmd+K): one business only, only what the person's role may open, and only the
branches a member is kept to."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import STUDIO, AuthHeaders, add_member, local_today
from tests.test_issued_documents import issue, make_licensed
from tests.test_leads import with_crm


def find(client: TestClient, headers: dict, q: str) -> list[dict]:
    response = client.get("/search", params={"q": q}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def titles(items: list[dict], kind: str | None = None) -> set[str]:
    return {i["title"] for i in items if kind is None or i["kind"] == kind}


def add_client(client: TestClient, headers: dict, name: str, **fields: object) -> str:
    created = client.post("/clients", json={"first_name": name, **fields}, headers=headers)
    assert created.status_code == 201, created.text
    return created.json()["id"]


def add_class(client: TestClient, studio: dict, branch: str | None, hour: str = "09:00") -> str:
    created = client.post(
        "/sessions",
        json={
            "service_id": studio["service"]["id"],
            "date": (local_today() + timedelta(days=3)).isoformat(),
            "start_time": hour,
            **({"location_id": branch} if branch else {}),
        },
        headers=studio["headers"],
    )
    assert created.status_code == 201, created.text
    return created.json()["session_ids"][0]


@pytest.fixture
def two_branches(client: TestClient, studio: dict) -> dict:
    """North (the main branch) and South, each with its own client, lead-free; owner headers."""
    owner = studio["headers"]
    north = studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=owner).json()["id"]
    return {
        "north": north,
        "south": south,
        "north_client": add_client(client, owner, "Nora Zebra", home_location_id=north),
        "south_client": add_client(client, owner, "Sami Zebra", home_location_id=south),
        "owner": owner,
    }


def member_at(
    client: TestClient,
    auth: AuthHeaders,
    engine: Engine,
    studio: dict,
    branch: str,
    role: str = "front_desk",
) -> dict[str, str]:
    member = uuid4()
    add_member(engine, studio["tenant_id"], member, role)
    kept = client.put(
        f"/staff/{member}/branches",
        json={"location_ids": [branch]},
        headers=studio["headers"],
    )
    assert kept.status_code == 200, kept.text
    return auth(member, studio["tenant_id"])


def another_business(client: TestClient, auth: AuthHeaders) -> dict:
    owner = uuid4()
    created = client.post("/tenants", json={**STUDIO, "name": "Other Studio"}, headers=auth(owner))
    tenant_id = UUID(created.json()["id"])
    return {"owner": owner, "tenant_id": tenant_id, "headers": auth(owner, tenant_id)}


# --- One business only -------------------------------------------------------------------------


def test_another_business_never_shows_up(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    other = another_business(client, auth)
    mine = studio["headers"]
    add_client(client, mine, "Mira Quokka")
    add_client(client, other["headers"], "Quinn Quokka")
    with_crm(client, studio)
    with_crm(client, other)
    for headers, name in ((mine, "Mira Quokka"), (other["headers"], "Quinn Quokka")):
        client.post("/leads", json={"first_name": name, "source": "other"}, headers=headers)

    found = find(client, mine, "quokka")

    assert titles(found, "client") == {"Mira Quokka"}
    assert titles(found, "lead") == {"Mira Quokka"}
    assert titles(find(client, other["headers"], "quokka")) == {"Quinn Quokka"}


def test_people_classes_and_invoices_of_another_business_are_not_found(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    other = another_business(client, auth)
    theirs = other["headers"]
    service = client.post(
        "/services",
        json={"name": "Narwhal Yoga", "duration_minutes": 50, "capacity": 5},
        headers=theirs,
    ).json()
    client.post(
        "/sessions",
        json={
            "service_id": service["id"],
            "date": (local_today() + timedelta(days=2)).isoformat(),
            "start_time": "10:00",
        },
        headers=theirs,
    )
    make_licensed(client, theirs)
    issue(client, theirs, client_name="Narwhal Customer")

    for q in ("narwhal", "1001"):
        assert find(client, studio["headers"], q) == []
    assert {i["kind"] for i in find(client, theirs, "narwhal")} == {"session", "invoice"}


def test_a_business_header_of_a_business_you_do_not_belong_to_is_refused(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    other = another_business(client, auth)
    outsider = auth(studio["owner"], other["tenant_id"])

    assert client.get("/search", params={"q": "anything"}, headers=outsider).status_code == 403
    assert client.get("/search", params={"q": "anything"}).status_code in (401, 403)


# --- Only what the role may open ---------------------------------------------------------------


def test_each_kind_follows_the_permission_of_its_list(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict
) -> None:
    owner = studio["headers"]
    with_crm(client, studio)
    make_licensed(client, owner)
    add_client(client, owner, "Pia Walrus")
    client.post("/leads", json={"first_name": "Walrus Lead", "source": "other"}, headers=owner)
    issue(client, owner, client_name="Pia Walrus")
    client.patch(
        f"/staff/{studio['coach']}/organization", json={"job_title": "Walrus coach"}, headers=owner
    )

    everything = {i["kind"] for i in find(client, owner, "walrus")}
    assert everything == {"client", "lead", "invoice", "staff"}

    front_desk = uuid4()
    add_member(engine, studio["tenant_id"], front_desk, "front_desk")
    kinds = {i["kind"] for i in find(client, auth(front_desk, studio["tenant_id"]), "walrus")}
    # Clients, leads and invoices yes; the team (staff.read) no.
    assert kinds == {"client", "lead", "invoice"}

    instructor = uuid4()
    add_member(engine, studio["tenant_id"], instructor, "staff")
    staff_kinds = {i["kind"] for i in find(client, auth(instructor, studio["tenant_id"]), "walrus")}
    # An instructor reads clients and leads, but neither invoices (sales.manage) nor the team.
    assert staff_kinds == {"client", "lead"}


def test_leads_are_left_out_when_the_crm_module_is_off(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    with_crm(client, studio)
    client.post("/leads", json={"first_name": "Otter Lead", "source": "other"}, headers=owner)
    assert titles(find(client, owner, "otter"), "lead") == {"Otter Lead"}

    client.put("/tenants/current/modules", json={"modules": {}}, headers=owner)

    assert titles(find(client, owner, "otter"), "lead") == set()


def test_erased_clients_are_not_found(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    client_id = add_client(client, owner, "Gone Gecko", email="gecko@example.com")
    assert titles(find(client, owner, "gecko"), "client") == {"Gone Gecko"}

    erased = client.post(f"/clients/{client_id}/erase", json={"confirm": True}, headers=owner)
    assert erased.status_code in (200, 204), erased.text

    assert find(client, owner, "gecko") == []


# --- Only the branches a member is kept to -----------------------------------------------------


def test_a_member_kept_to_one_branch_finds_only_that_branchs_clients(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, two_branches: dict
) -> None:
    mine = member_at(client, auth, engine, studio, two_branches["north"])

    assert titles(find(client, mine, "zebra"), "client") == {"Nora Zebra"}
    assert titles(find(client, two_branches["owner"], "zebra"), "client") == {
        "Nora Zebra",
        "Sami Zebra",
    }
    # Asking for the other branch by header does not widen it either.
    sneaky = {**mine, "X-Location-Id": two_branches["south"]}
    assert titles(find(client, sneaky, "zebra"), "client") == {"Nora Zebra"}


def test_a_member_kept_to_one_branch_finds_only_that_branchs_classes(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, two_branches: dict
) -> None:
    north_class = add_class(client, studio, two_branches["north"], "09:00")
    south_class = add_class(client, studio, two_branches["south"], "11:00")
    mine = member_at(client, auth, engine, studio, two_branches["north"])

    seen = {i["id"] for i in find(client, mine, "pilates") if i["kind"] == "session"}
    assert seen == {north_class}
    owner_seen = {
        i["id"] for i in find(client, two_branches["owner"], "pilates") if i["kind"] == "session"
    }
    assert owner_seen == {north_class, south_class}


def test_a_member_kept_to_one_branch_finds_only_that_branchs_invoices(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, two_branches: dict
) -> None:
    make_licensed(client, two_branches["owner"])
    north_doc = issue(
        client,
        two_branches["owner"],
        client_name="Nora Zebra",
        client_id=two_branches["north_client"],
    )
    south_doc = issue(
        client,
        two_branches["owner"],
        client_name="Sami Zebra",
        client_id=two_branches["south_client"],
    )
    mine = member_at(client, auth, engine, studio, two_branches["north"])

    assert {i["id"] for i in find(client, mine, "zebra") if i["kind"] == "invoice"} == {
        north_doc["id"]
    }
    # By number too: both documents are number 1001 or 1002; the other branch's never shows.
    by_number = find(client, mine, str(south_doc["number"]))
    assert south_doc["id"] not in {i["id"] for i in by_number}
    assert {
        i["id"] for i in find(client, two_branches["owner"], "zebra") if i["kind"] == "invoice"
    } == {
        north_doc["id"],
        south_doc["id"],
    }


def test_a_branch_manager_finds_only_people_at_their_branches(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict, two_branches: dict
) -> None:
    owner = two_branches["owner"]
    north_coach, south_coach = uuid4(), uuid4()
    for coach, branch, name in (
        (north_coach, two_branches["north"], "Nina Lynx"),
        (south_coach, two_branches["south"], "Sol Lynx"),
    ):
        add_member(engine, studio["tenant_id"], coach, "staff")
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app.users SET full_name = :name WHERE id = :id"),
                {"name": name, "id": coach},
            )
        client.put(f"/staff/{coach}/branches", json={"location_ids": [branch]}, headers=owner)
    manager = member_at(client, auth, engine, studio, two_branches["north"], "branch_manager")

    assert titles(find(client, manager, "lynx"), "staff") == {"Nina Lynx"}
    assert titles(find(client, owner, "lynx"), "staff") == {"Nina Lynx", "Sol Lynx"}


# --- Bounded and safe --------------------------------------------------------------------------


def test_a_search_needs_two_characters_and_is_capped(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    for n in range(8):
        add_client(client, owner, f"Bulk Ibis {n}")

    assert client.get("/search", params={"q": "b"}, headers=owner).status_code == 422
    assert client.get("/search", params={"q": "x" * 101}, headers=owner).status_code == 422
    assert client.get("/search", headers=owner).status_code == 422
    assert find(client, owner, "  ") == []
    assert len([i for i in find(client, owner, "ibis") if i["kind"] == "client"]) == 5


def test_wildcards_are_taken_literally(client: TestClient, studio: dict) -> None:
    owner = studio["headers"]
    add_client(client, owner, "Plain Heron")

    assert find(client, owner, "%%") == []
    assert find(client, owner, "__") == []
    assert find(client, owner, "he%on") == []
    assert titles(find(client, owner, "heron")) == {"Plain Heron"}


def test_the_search_is_rate_limited_per_address() -> None:
    from fastapi import FastAPI

    from app.core.rate_limit import RULES, MemoryStore, limiter

    rule = next(r for r in RULES if r.name == "search")
    app = FastAPI()
    app.middleware("http")(
        limiter(MemoryStore(), trust_forwarded=False, rules=RULES, clock=lambda: 1000.0)
    )

    @app.get("/search")
    def search() -> dict:
        return {"ok": True}

    caller = TestClient(app)
    codes = [caller.get("/search").status_code for _ in range(rule.limit + 1)]

    assert codes[-2:] == [200, 429]
