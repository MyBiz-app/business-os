"""Every staff route with a `{client_id}` in its path must follow the client's home branch (GL2).

A member kept to some branches gets "not found" for another branch's client (`ensure_client_visible`
in app/api/deps.py). A new route that forgets the guard fails here, so it can't ship by accident.
The check reads each endpoint's source for one of the guard calls; a route that is allowed to skip
it is listed in `EXEMPT` with the reason."""

import inspect

from app.api.registry import ROUTERS

GUARDS = (
    "ensure_client_visible",
    "ensure_branch_visible",
    "client_branch_filter",
    "_client_row",
    "_client_exists",
    "_client_in_reach",
)

# (method, path) -> why no branch guard is needed
EXEMPT = {
    (
        "GET",
        "/mcp-oauth/clients/{client_id}",
    ): "an OAuth application id, not a client of a business",
    (
        "GET",
        "/clients/{client_id}/bookings",
    ): "the query keeps to bookings at the member's branches",
    (
        "POST",
        "/client/people/{client_id}/friend-request",
    ): "client app: another person, not a client row",
    ("DELETE", "/client/friends/{client_id}"): "client app: another person, not a client row",
    ("GET", "/client/people/{client_id}"): "client app: another person, not a client row",
    ("GET", "/client/people/{client_id}/avatar"): "client app: another person, not a client row",
}


def client_routes():
    for router in ROUTERS:
        for route in router.routes:
            if "{client_id}" in route.path:
                for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                    yield method, route.path, route.endpoint


def test_every_client_route_follows_the_clients_branch() -> None:
    routes = list(client_routes())
    assert len(routes) > 20  # the scan finds the routes at all
    unguarded = [
        f"{method} {path}"
        for method, path, endpoint in routes
        if (method, path) not in EXEMPT
        and not any(guard in inspect.getsource(endpoint) for guard in GUARDS)
    ]
    assert not unguarded, f"add ensure_client_visible (or list a reason in EXEMPT): {unguarded}"


def test_exemptions_still_exist() -> None:
    found = {(method, path) for method, path, _ in client_routes()}
    assert set(EXEMPT) <= found, set(EXEMPT) - found
