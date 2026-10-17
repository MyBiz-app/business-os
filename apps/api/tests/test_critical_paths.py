"""Launch-critical paths (readiness review P1-8): every industry can sign up, a failed sign-up
leaves nothing behind, and no route is reachable without signing in unless it is meant to be."""

import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.catalog.verticals import VERTICAL_PACKS
from tests.conftest import STUDIO, AuthHeaders
from tests.test_bookings import new_client, new_session


@pytest.mark.parametrize("locale", ["he", "en"])
@pytest.mark.parametrize("vertical", sorted(VERTICAL_PACKS))
def test_every_industry_can_sign_up(
    client: TestClient, auth: AuthHeaders, vertical: str, locale: str
) -> None:
    owner = uuid4()
    created = client.post(
        "/tenants", json={**STUDIO, "vertical": vertical, "locale": locale}, headers=auth(owner)
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    assert tenant["role"] == "owner" and tenant["vertical"] == vertical

    headers = auth(owner, tenant["id"])
    branches = client.get("/locations", headers=headers).json()
    assert len(branches) == 1 and branches[0]["name"]  # the main branch, in the business's language
    assert client.get("/tenants/current", headers=headers).json()["id"] == tenant["id"]
    # The owner can use the core screens straight away.
    assert client.get("/services", headers=headers).status_code == 200
    assert client.get("/clients", headers=headers).status_code == 200
    assert client.get("/staff", headers=headers).status_code == 200


def test_sign_up_with_extra_branches_files_the_main_branch_first(
    client: TestClient, auth: AuthHeaders
) -> None:
    owner = uuid4()
    created = client.post(
        "/tenants", json={**STUDIO, "modules": {"extra_location": 2}}, headers=auth(owner)
    )
    assert created.status_code == 201, created.text
    branches = client.get("/locations", headers=auth(owner, created.json()["id"])).json()
    assert len(branches) == 3
    assert len({b["name"] for b in branches}) == 3


def test_a_refused_sign_up_leaves_no_business_behind(client: TestClient, auth: AuthHeaders) -> None:
    owner = uuid4()
    refused = client.post(
        "/tenants", json={**STUDIO, "modules": {"no_such_module": 1}}, headers=auth(owner)
    )
    assert refused.status_code == 422
    assert client.get("/me", headers=auth(owner)).json()["memberships"] == []
    # The same person can then sign up properly.
    assert client.post("/tenants", json=STUDIO, headers=auth(owner)).status_code == 201


def test_one_person_can_own_several_businesses_without_mixing_them(
    client: TestClient, auth: AuthHeaders
) -> None:
    owner = uuid4()
    first = client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"]
    second = client.post("/tenants", json={**STUDIO, "name": "Second"}, headers=auth(owner)).json()[
        "id"
    ]
    client.post("/clients", json={"first_name": "Dana"}, headers=auth(owner, first))
    assert client.get("/clients", headers=auth(owner, first)).json()["total"] == 1
    assert client.get("/clients", headers=auth(owner, second)).json()["total"] == 0
    names = {m["tenant_name"] for m in client.get("/me", headers=auth(owner)).json()["memberships"]}
    assert names == {"Studio Flow", "Second"}


def test_a_cancelled_session_cannot_be_booked(
    client: TestClient, auth: AuthHeaders, studio: dict
) -> None:
    session_id = new_session(client, studio, capacity=2)
    headers = studio["headers"]
    cancelled = client.patch(
        f"/sessions/{session_id}", json={"status": "cancelled"}, headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text

    desk = client.post(
        f"/sessions/{session_id}/bookings",
        json={"client_id": new_client(client, headers, "Dana")},
        headers=headers,
    )
    assert desk.status_code in (404, 409, 422), desk.text

    user = uuid4()
    code = client.get("/tenants/current", headers=headers).json()["join_code"]
    client.post("/client/businesses", json={"code": code}, headers=auth(user))
    own = client.post(
        f"/client/sessions/{session_id}/bookings", headers=auth(user, studio["tenant_id"])
    )
    assert own.status_code in (404, 409, 422), own.text
    assert client.get(f"/sessions/{session_id}", headers=headers).json()["booked"] == 0


# Routes that are public on purpose: health checks, webhooks (verified by signature, not login),
# and the pages a business shares by link or join code.
PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("POST", "/webhooks/payments/{provider}/{tenant_id}"),
    ("POST", "/webhooks/whatsapp/{provider}/{tenant_id}"),
    ("GET", "/public/quotes/{token}"),
    ("POST", "/public/quotes/{token}/answer"),
    ("POST", "/public/quotes/{token}/deposit"),
    ("GET", "/public/business-files/{token}"),
    ("GET", "/public/files/{token}"),
    ("POST", "/public/businesses/{code}/inquiries"),
    ("GET", "/public/pricing"),
    ("POST", "/public/contact"),
    ("GET", "/public/announcements/unsubscribe"),
    ("GET", "/public/businesses/{code}"),
    ("GET", "/public/tenants/{tenant_id}/logo"),
    ("GET", "/public/locations/{location_id}/logo"),
}


def test_every_route_needs_a_login_unless_listed_as_public(client: TestClient) -> None:
    """A new endpoint that forgets its permission dependency fails here, not in production."""
    spec = client.get("/openapi.json").json()
    open_routes: set[tuple[str, str]] = set()
    for path, operations in spec["paths"].items():
        for method in operations:
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
            body = None if method == "get" else {}
            response = client.request(method.upper(), url, json=body)
            if response.status_code not in (401, 403):
                open_routes.add((method.upper(), path))
    assert open_routes == PUBLIC_ROUTES, (
        f"unexpectedly open: {sorted(open_routes - PUBLIC_ROUTES)}; "
        f"no longer open: {sorted(PUBLIC_ROUTES - open_routes)}"
    )
