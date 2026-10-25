from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import STUDIO, AuthHeaders


def gym(client: TestClient, auth: AuthHeaders) -> dict:
    """A business of a concrete industry (a category-level one has no starting activities)."""
    owner = uuid4()
    tenant = client.post("/tenants", json={**STUDIO, "vertical": "gym"}, headers=auth(owner)).json()
    headers = auth(owner, tenant["id"])
    location = client.get("/locations", headers=headers).json()[0]
    return {"headers": headers, "location": location}


def test_a_new_business_starts_with_its_industrys_activities(
    client: TestClient, auth: AuthHeaders
) -> None:
    studio = gym(client, auth)
    headers = studio["headers"]
    activities = client.get("/activities", headers=headers).json()
    assert activities and all(a["enabled"] for a in activities)
    assert {a["business_type"] for a in activities} == {"gym"}
    # The main branch offers all of them.
    main = studio["location"]["id"]
    offered = client.get(f"/locations/{main}/activities", headers=headers).json()
    assert sorted(offered) == sorted(a["id"] for a in activities)


def test_a_new_branch_offers_every_activity_and_can_be_narrowed(
    client: TestClient, auth: AuthHeaders
) -> None:
    studio = gym(client, auth)
    headers = studio["headers"]
    everything = [a["id"] for a in client.get("/activities", headers=headers).json()]
    branch = client.post("/locations", json={"name": "Haifa"}, headers=headers).json()["id"]
    assert sorted(client.get(f"/locations/{branch}/activities", headers=headers).json()) == sorted(
        everything
    )
    narrowed = client.put(
        f"/locations/{branch}/activities", json={"activity_ids": everything[:1]}, headers=headers
    )
    assert narrowed.status_code == 200 and narrowed.json() == everything[:1]
    unknown = client.put(
        f"/locations/{branch}/activities", json={"activity_ids": [str(uuid4())]}, headers=headers
    )
    assert unknown.status_code == 422 and unknown.json()["detail"] == "unknown_activity"


def test_a_business_can_mix_activities_of_different_types(
    client: TestClient, auth: AuthHeaders
) -> None:
    studio = gym(client, auth)
    headers = studio["headers"]
    main = studio["location"]["id"]
    before = client.get("/activities", headers=headers).json()
    first = before[0]
    chosen = [
        {"business_type": first["business_type"], "activity_key": first["activity_key"]},
        {"business_type": "tennis_club", "activity_key": "court_rental"},
    ]
    result = client.put("/activities", json={"activities": chosen}, headers=headers)
    assert result.status_code == 200
    enabled = {(a["business_type"], a["activity_key"]) for a in result.json() if a["enabled"]}
    assert enabled == {(c["business_type"], c["activity_key"]) for c in chosen}
    rental = next(a for a in result.json() if a["activity_key"] == "court_rental")
    assert rental["model"] == "resource_rental" and rental["resource_type"] == "tennis_court"
    # The branch gains the new activity, and a switched-off one is no longer offered there.
    offered = client.get(f"/locations/{main}/activities", headers=headers).json()
    assert rental["id"] in offered and len(offered) == 2

    refused = client.put(
        "/activities",
        json={"activities": [{"business_type": "tennis_club", "activity_key": "nope"}]},
        headers=headers,
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "unknown_activity"


def test_another_business_cannot_see_or_change_the_activities(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    main = studio["location"]["id"]
    stranger = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(stranger)).json()
    theirs = auth(stranger, other["id"])
    mine = {a["id"] for a in client.get("/activities", headers=studio["headers"]).json()}
    assert mine.isdisjoint({a["id"] for a in client.get("/activities", headers=theirs).json()})
    assert client.get(f"/locations/{main}/activities", headers=theirs).status_code == 404
    assert (
        client.put(
            f"/locations/{main}/activities", json={"activity_ids": []}, headers=theirs
        ).status_code
        == 404
    )
