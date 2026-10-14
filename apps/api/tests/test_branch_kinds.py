from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import STUDIO, AuthHeaders
from tests.test_bookings import new_client


def test_a_branch_kind_must_be_in_the_business_category(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    main = studio["location"]["id"]

    created = client.post("/locations", json={"name": "Yoga", "kind": "yoga"}, headers=headers)
    assert created.status_code == 201
    assert created.json()["kind"] == "yoga" and created.json()["effective_kind"] == "yoga"
    assert created.json()["schedule_view"] == "class_blocks"

    # A sub-category of another category is refused, on create and on update.
    refused = client.post(
        "/locations", json={"name": "Cuts", "kind": "barbershop"}, headers=headers
    )
    assert refused.status_code == 422 and refused.json()["detail"] == "invalid_branch_kind"
    refused = client.patch(f"/locations/{main}", json={"kind": "dance"}, headers=headers)
    assert refused.status_code == 422

    # No kind means "like the business"; the kind can be set and cleared.
    plain = client.get(f"/locations/{main}", headers=headers).json()
    assert plain["kind"] is None and plain["effective_kind"] == "fitness"
    assert plain["social"] == "on"
    set_kind = client.patch(f"/locations/{main}", json={"kind": "crossfit"}, headers=headers)
    assert set_kind.json()["kind"] == "crossfit"
    cleared = client.patch(f"/locations/{main}", json={"kind": None}, headers=headers)
    assert cleared.json()["kind"] is None


def test_a_courts_business_defaults_to_the_courts_view(
    client: TestClient, auth: AuthHeaders
) -> None:
    owner = uuid4()
    tenant = client.post(
        "/tenants", json={**STUDIO, "vertical": "sports"}, headers=auth(owner)
    ).json()
    branch = client.get("/locations", headers=auth(owner, tenant["id"])).json()[0]
    assert branch["schedule_view"] == "courts" and branch["social"] == "on"


def test_the_network_policy_defaults_to_network_and_can_change(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    assert client.get("/tenants/current", headers=headers).json()["network_scope"] == "network"
    changed = client.patch("/tenants/current", json={"network_scope": "branch"}, headers=headers)
    assert changed.json()["network_scope"] == "branch"
    invalid = client.patch("/tenants/current", json={"network_scope": "nope"}, headers=headers)
    assert invalid.status_code == 422


def test_clients_follow_their_branches_when_the_business_is_branch_scoped(
    client: TestClient, studio: dict
) -> None:
    headers = studio["headers"]
    main = studio["location"]["id"]
    haifa = client.post("/locations", json={"name": "Haifa"}, headers=headers).json()["id"]
    client.patch("/tenants/current", json={"network_scope": "branch"}, headers=headers)

    at_main = client.post(
        "/clients", json={"first_name": "Dana", "home_location_id": main}, headers=headers
    ).json()["id"]
    at_both = new_client(client, headers, "Eli")
    unplaced = new_client(client, headers, "Gil")
    assert client.get(f"/clients/{at_main}/branches", headers=headers).json() == [main]
    put = client.put(
        f"/clients/{at_both}/branches", json={"location_ids": [main, haifa]}, headers=headers
    )
    assert put.status_code == 200 and sorted(put.json()) == sorted([main, haifa])

    def names(branch: str) -> set[str]:
        page = client.get("/clients", headers={**headers, "X-Location-Id": branch}).json()
        return {c["first_name"] for c in page["items"]}

    assert names(main) == {"Dana", "Eli", "Gil"}
    assert names(haifa) == {"Eli", "Gil"}  # Dana is only at the main branch

    client.put(f"/clients/{at_both}/branches", json={"location_ids": [haifa]}, headers=headers)
    assert names(main) == {"Dana", "Gil"}
    unknown = client.put(
        f"/clients/{unplaced}/branches", json={"location_ids": [str(uuid4())]}, headers=headers
    )
    assert unknown.status_code == 422 and unknown.json()["detail"] == "unknown_branch"


def test_another_business_cannot_read_or_change_a_clients_branches(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    mine = new_client(client, studio["headers"], "Dana")
    stranger = uuid4()
    other = client.post("/tenants", json=STUDIO, headers=auth(stranger)).json()
    theirs = auth(stranger, other["id"])
    assert client.get(f"/clients/{mine}/branches", headers=theirs).status_code == 404
    assert (
        client.put(
            f"/clients/{mine}/branches", json={"location_ids": []}, headers=theirs
        ).status_code
        == 404
    )
