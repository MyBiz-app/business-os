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
