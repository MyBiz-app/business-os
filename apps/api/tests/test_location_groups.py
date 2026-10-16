"""Branch groups: named sets of branches, a branch in several groups, tenant-private."""

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import STUDIO, AuthHeaders


def test_groups_hold_branches_and_a_branch_can_be_in_several(
    client: TestClient, studio: dict
) -> None:
    headers, main = studio["headers"], studio["location"]["id"]
    south = client.post("/locations", json={"name": "South"}, headers=headers).json()["id"]
    north = client.post("/locations", json={"name": "North"}, headers=headers).json()["id"]

    district = client.post(
        "/location-groups",
        json={"name": " South district ", "location_ids": [main, south, south]},
        headers=headers,
    )
    assert district.status_code == 201
    assert district.json()["name"] == "South district"
    assert sorted(district.json()["location_ids"]) == sorted([main, south])

    both = client.post(
        "/location-groups",
        json={"name": "Everything", "location_ids": [main, south, north]},
        headers=headers,
    ).json()
    assert len(both["location_ids"]) == 3
    listed = client.get("/location-groups", headers=headers).json()
    assert {group["name"] for group in listed} == {"South district", "Everything"}

    changed = client.patch(
        f"/location-groups/{district.json()['id']}",
        json={"name": "Centre", "location_ids": [north]},
        headers=headers,
    ).json()
    assert changed["name"] == "Centre" and changed["location_ids"] == [north]

    assert client.delete(f"/location-groups/{both['id']}", headers=headers).status_code == 204
    assert client.get(f"/locations/{north}", headers=headers).status_code == 200
    assert client.delete(f"/location-groups/{both['id']}", headers=headers).status_code == 404


def test_group_names_are_unique_and_branches_must_be_the_businesss_own(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    headers = studio["headers"]
    assert client.post("/location-groups", json={"name": "A"}, headers=headers).status_code == 201
    dup = client.post("/location-groups", json={"name": "a"}, headers=headers)
    assert dup.status_code == 409 and dup.json()["detail"] == "group_name_taken"

    other_owner = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()
    foreign = client.get("/locations", headers=auth(other_owner, other["id"])).json()[0]["id"]
    refused = client.post(
        "/location-groups", json={"name": "Spy", "location_ids": [foreign]}, headers=headers
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "invalid_reference"
    # Another business sees none of this business's groups.
    assert client.get("/location-groups", headers=auth(other_owner, other["id"])).json() == []


def test_only_the_owner_manages_groups(client: TestClient, auth: AuthHeaders, studio: dict) -> None:
    headers = studio["headers"]
    coach = auth(studio["coach"], studio["tenant_id"])
    group = client.post("/location-groups", json={"name": "G"}, headers=headers).json()
    assert client.get("/location-groups", headers=coach).status_code == 200
    changed = client.patch(f"/location-groups/{group['id']}", json={"name": "X"}, headers=coach)
    assert changed.status_code == 403
    assert client.delete(f"/location-groups/{group['id']}", headers=coach).status_code == 403
