from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import local_today
from tests.test_bookings import book, new_client, new_session
from tests.test_leads import with_crm


def test_page_limit_is_capped_at_200(client: TestClient, studio: dict) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    for path in ["/clients", "/leads"]:
        assert client.get(path, params={"limit": 200}, headers=headers).status_code == 200
        assert client.get(path, params={"limit": 201}, headers=headers).status_code == 422
        assert client.get(path, params={"limit": 0}, headers=headers).status_code == 422
        assert client.get(path, params={"offset": -1}, headers=headers).status_code == 422


def test_client_bookings_are_paged(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    sessions = [
        new_session(client, studio, on=local_today() + timedelta(days=d)) for d in (1, 2, 3)
    ]
    for session_id in sessions:
        book(client, headers, session_id, dana)

    first = client.get(f"/clients/{dana}/bookings", params={"limit": 2}, headers=headers).json()
    rest = client.get(
        f"/clients/{dana}/bookings", params={"limit": 2, "offset": 2}, headers=headers
    ).json()

    assert [b["session_id"] for b in first + rest] == list(reversed(sessions))


@pytest.mark.parametrize("count", [3])
def test_leads_board_is_paged_with_whole_board_counts(
    client: TestClient, studio: dict, count: int
) -> None:
    with_crm(client, studio)
    headers = studio["headers"]
    for n in range(count):
        created = client.post(
            "/leads", json={"first_name": f"Lead{n}", "source": "other"}, headers=headers
        )
        assert created.status_code == 201, created.text

    page = client.get("/leads", params={"limit": 2}, headers=headers).json()
    rest = client.get("/leads", params={"limit": 2, "offset": 2}, headers=headers).json()

    assert (len(page["items"]), len(rest["items"])) == (2, 1)
    assert page["total"] == rest["total"] == count
    assert {c["stage"]: c["count"] for c in page["counts"]}["new"] == count


# --- Every list is bounded (go-live GL17) -----------------------------------------------------

# GET endpoints that return a list without a `limit` parameter, and why none of them can grow
# past 200 rows: a date window the caller must give (at most 92 days), a catalog that is small by
# nature (services, branches, plans), or rows of one person. A new list endpoint either takes
# `limit` (see app/api/pagination.py) or is added here with its reason.
BOUNDED = {
    # the console's unpaid-invoice list: the function returns at most 500 businesses
    "/platform/billing/overdue": "capped",
    # the SQL function returns at most 5 open banners, or the latest 50
    "/public/incidents": "limit in SQL",
    "/platform/incidents": "limit in SQL",
    # a required date window of at most 42 days
    "/sessions": "window",
    "/client/sessions": "window",
    "/client/appointments/slots": "window",
    "/appointments/slots": "window",
    "/resources/slots": "window",
    "/client/resources/slots": "window",
    "/shifts/planning": "window",
    "/shifts/time-off": "window",
    "/shifts/coverage": "window",
    "/shifts/availability": "window",
    "/jobs": "one day",
    "/closed-days": "window",
    "/client/closed-days": "window",
    "/bills/preview": "window",
    "/metrics": "report",
    "/metrics/{key}/series": "report",
    "/metrics/breakdown/{dimension}": "report",
    "/metrics/members-at-risk": "capped at 500 in code",
    "/metrics/branches": "report",
    "/reports/resources": "report",
    "/attention": "capped in code",
    # small catalogs of one business
    "/services": "catalog",
    "/locations": "catalog",
    "/location-groups": "catalog",
    "/stations": "catalog",
    "/resources": "catalog",
    "/plans": "catalog",
    "/promo-codes": "catalog",
    "/shift-templates": "catalog",
    "/messages/audiences": "catalog",
    "/messages/templates": "catalog",
    "/integrations": "catalog",
    "/platform/integrations": "catalog",
    "/issued-documents/series": "one row per kind",
    "/audit-log/kinds": "fixed list",
    "/clients/fields": "the industry pack's fields",
    "/files/folders": "folders of one business",
    "/leads/owners": "staff of one business",
    "/social/accounts": "connected accounts",
    "/social/audience": "one row per network",
    "/platform/staff": "the MyBiz team",
    "/platform/website-orders": "one order per business, capped at 300 in SQL",
    "/platform/usage": "one row per day, at most 366",
    "/platform/funnel": "one row per sign-up step, nine",
    "/platform/activity": "one row per day, at most 90",
    "/platform/billing": "one row per month",
    "/platform/broadcasts": "announcements",
    "/platform/businesses/{tenant_id}/invoices": "one row per month",
    "/payroll/rates": "one row per rate",
    # the rows of one person
    "/me/devices": "capped in code",
    "/me/businesses": "the person's own businesses",
    "/me/announcements": "pop-ups not yet dismissed",
    "/me/pay-components": "the person's own",
    "/me/form101": "one row per tax year",
    "/staff/{user_id}/form101": "one row per tax year",
    "/staff/{user_id}/pay-components": "one person's",
    "/staff/{user_id}/time-off": "one person's",
    "/client/businesses": "the person's own businesses",
    "/client/locations": "catalog",
    "/client/plans": "catalog",
    "/client/dependents": "a family",
    "/clients/{client_id}/dependents": "a family",
    "/client/addresses": "a person's addresses",
    "/clients/{client_id}/addresses": "a person's addresses",
    "/clients/{client_id}/branches": "branches of one client",
    "/clients/{client_id}/consent-events": "capped in code",
    "/client/friends": "a person's friends",
    "/client/invites": "invitations that still hold a spot",
    "/client/sessions/{session_id}/participants": "the roster of one class",
    "/client/reviews/pending": "capped in code",
    "/client/appointments/staff": "staff of one business",
    "/client/appointments/services": "catalog",
    "/appointments/staff": "staff of one business",
    "/client/resources": "catalog",
    "/shift-swaps/colleagues": "staff of one business",
    "/payroll/runs/{period}/payslips/{user_id}/corrections": "one payslip's",
    "/ai/tasks/{task_id}/runs": "capped in code",
    # hard caps of 200 or fewer in the query
    "/shift-swaps": "capped at 200 in code",
    "/time-off-requests": "capped at 200 in code",
    "/clients/{client_id}/notes": "capped at 200 in code",
    "/ai/conversations": "capped at 20 in code",
    "/whatsapp-ai/conversations": "capped at 50 in code",
    "/platform/ai/assistant/conversations": "capped at 30 in code",
    "/messages/campaigns": "capped at 100 in code",
    "/migration/sessions": "capped at 20 in code",
    "/tenants/current/data-exports": "capped at 10 in code",
    "/social/drafts": "capped at 50 in code",
    "/payroll/runs": "capped at 24 in code",
    "/me/payslips": "capped in code",
    "/payroll/bonuses": "capped in code",
    "/client/bookings": "capped at 200 in code",
    "/client/receipts": "capped at 100 in code",
    "/events": "window",
    "/me/legal": "one row per legal document",
}


def test_every_list_endpoint_is_paged_or_bounded() -> None:
    from app.main import app

    unpaged = []
    for path, operations in app.openapi()["paths"].items():
        get = operations.get("get")
        if get is None:
            continue
        schema = (
            get["responses"].get("200", {}).get("content", {}).get("application/json", {})
        ).get("schema", {})
        if schema.get("type") != "array":
            continue
        if "limit" not in {p["name"] for p in get.get("parameters", [])} and path not in BOUNDED:
            unpaged.append(path)
    assert unpaged == [], (
        "These lists take no `limit` and are not known to be bounded. Use PageDep / "
        f"FullPageDep (app/api/pagination.py) or list them in BOUNDED with the reason: {unpaged}"
    )


def test_client_bookings_keyset_pages_follow_the_cursor(client: TestClient, studio: dict) -> None:
    headers = studio["headers"]
    dana = new_client(client, headers, "Dana")
    sessions = [
        new_session(client, studio, on=local_today() + timedelta(days=d)) for d in (1, 2, 3, 4, 5)
    ]
    for session_id in sessions:
        book(client, headers, session_id, dana)
    path = f"/clients/{dana}/bookings"

    first = client.get(path, params={"limit": 2}, headers=headers)
    cursor = first.headers["X-Next-Cursor"]
    second = client.get(path, params={"limit": 2, "after": cursor}, headers=headers)
    third = client.get(
        path, params={"limit": 2, "after": second.headers["X-Next-Cursor"]}, headers=headers
    )

    seen = [b["session_id"] for r in (first, second, third) for b in r.json()]
    assert seen == list(reversed(sessions))
    assert "X-Next-Cursor" not in third.headers  # the last page


def test_a_garbled_cursor_is_refused(client: TestClient, studio: dict) -> None:
    dana = new_client(client, studio["headers"], "Dana")
    refused = client.get(
        f"/clients/{dana}/bookings", params={"after": "not-a-cursor"}, headers=studio["headers"]
    )
    assert refused.status_code == 422
