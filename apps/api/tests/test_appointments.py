from datetime import datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders, local_today
from tests.test_bookings import new_client, set_status
from tests.test_client_app import join, join_code

TZ = ZoneInfo("Asia/Jerusalem")
EVERY_DAY = [{"weekday": d, "starts": "09:00", "ends": "17:00"} for d in range(7)]


@pytest.fixture
def barber(client: TestClient, auth: AuthHeaders) -> dict:
    """A beauty business: its pack gives it appointment services; the owner takes bookings."""
    owner = uuid4()
    business = {"name": "Dana Hair", "vertical": "beauty", "locale": "en",
                "time_zone": "Asia/Jerusalem", "currency": "ILS"}  # fmt: skip
    tenant_id = client.post("/tenants", json=business, headers=auth(owner)).json()["id"]
    headers = auth(owner, tenant_id)
    services = client.get("/services", headers=headers).json()
    haircut = next(s for s in services if s["name"] == "Men's haircut")
    hours = client.put(f"/staff/{owner}/hours", json=EVERY_DAY, headers=headers)
    assert hours.status_code == 200, hours.text
    return {"owner": owner, "tenant_id": tenant_id, "headers": headers, "haircut": haircut,
            "day": local_today() + timedelta(days=2)}  # fmt: skip


def at(day, hhmm: str) -> str:
    hour, minute = map(int, hhmm.split(":"))
    return datetime.combine(day, time(hour, minute), tzinfo=TZ).isoformat()


def local_times(slots: list[dict]) -> list[str]:
    return [datetime.fromisoformat(s["starts_at"]).astimezone(TZ).strftime("%H:%M") for s in slots]


def test_new_beauty_business_gets_appointment_services(client: TestClient, barber: dict) -> None:
    services = client.get("/services", headers=barber["headers"]).json()
    assert len(services) == 4
    assert {s["booking_mode"] for s in services} == {"appointment"}
    assert barber["haircut"]["duration_minutes"] == 30 and barber["haircut"]["capacity"] == 1


def test_free_times_and_booking(client: TestClient, barber: dict) -> None:
    headers, day, haircut = barber["headers"], barber["day"], barber["haircut"]
    params = {"service_id": haircut["id"], "date": day.isoformat()}

    slots = client.get("/appointments/slots", params=params, headers=headers).json()
    assert local_times(slots)[:3] == ["09:00", "09:15", "09:30"]
    assert local_times(slots)[-1] == "16:30"  # the last 30 minutes before 17:00

    dana = new_client(client, headers, "Dana")
    body = {"service_id": haircut["id"], "staff_user_id": str(barber["owner"]),
            "starts_at": at(day, "09:00"), "client_id": dana}  # fmt: skip
    booked = client.post("/appointments", json=body, headers=headers)
    again = client.post(
        "/appointments", json={**body, "starts_at": at(day, "09:15")}, headers=headers
    )
    late = client.post(
        "/appointments", json={**body, "starts_at": at(day, "16:45")}, headers=headers
    )

    assert booked.status_code == 201, booked.text
    assert booked.json()["status"] == "booked"
    assert again.status_code == 409 and again.json()["detail"] == "slot_taken"
    assert late.status_code == 409 and late.json()["detail"] == "outside_hours"
    after = local_times(client.get("/appointments/slots", params=params, headers=headers).json())
    assert after[:2] == ["09:30", "09:45"]
    # Checked in, it still holds the time; staff see it with the client's name.
    set_status(client, headers, booked.json()["id"], "checked_in")
    held = local_times(client.get("/appointments/slots", params=params, headers=headers).json())
    assert held[0] == "09:30"
    [listed] = client.get(
        "/sessions", params={"start": day.isoformat(), "days": 1}, headers=headers
    ).json()
    assert listed["booking_mode"] == "appointment" and listed["appointment_client"] == "Dana"


def test_clients_book_and_cancel_in_the_app(
    client: TestClient, barber: dict, auth: AuthHeaders
) -> None:
    user = uuid4()
    join(client, auth, user, join_code(client, barber))
    me = auth(user, barber["tenant_id"])
    day, haircut = barber["day"], barber["haircut"]
    params = {"service_id": haircut["id"], "date": day.isoformat()}

    services = client.get("/client/appointments/services", headers=me).json()
    assert haircut["id"] in [s["id"] for s in services] and len(services) == 4
    staff = client.get("/client/appointments/staff", headers=me).json()
    slots = client.get("/client/appointments/slots", params=params, headers=me).json()
    booked = client.post(
        "/client/appointments",
        json={
            "service_id": haircut["id"],
            "staff_user_id": staff[0]["user_id"],
            "starts_at": slots[0]["starts_at"],
        },
        headers=me,
    )

    assert [s["user_id"] for s in staff] == [str(barber["owner"])]
    assert booked.status_code == 201, booked.text
    session = booked.json()
    assert session["my_booking"]["status"] == "booked"
    assert (
        local_times(client.get("/client/appointments/slots", params=params, headers=me).json())[0]
        == "09:30"
    )

    cancelled = client.post(f"/client/bookings/{session['my_booking']['id']}/cancel", headers=me)
    assert cancelled.status_code == 200, cancelled.text
    # The time is free again for everyone, and the empty appointment is not listed anywhere.
    listed = client.get(
        "/sessions", params={"start": day.isoformat(), "days": 1}, headers=barber["headers"]
    ).json()
    assert listed == []
    assert (
        local_times(client.get("/client/appointments/slots", params=params, headers=me).json())[0]
        == "09:00"
    )


def test_rules(client: TestClient, barber: dict) -> None:
    headers, day = barber["headers"], barber["day"]
    overlapping = client.put(
        f"/staff/{barber['owner']}/hours",
        json=[
            {"weekday": 0, "starts": "09:00", "ends": "12:00"},
            {"weekday": 0, "starts": "11:00", "ends": "14:00"},
        ],
        headers=headers,
    )
    group = client.post(
        "/services",
        json={"name": "Workshop", "duration_minutes": 60, "capacity": 8},
        headers=headers,
    ).json()
    closed = client.post("/closed-days", json={"day": day.isoformat()}, headers=headers)
    params = {"service_id": barber["haircut"]["id"], "date": day.isoformat()}

    assert overlapping.status_code == 422
    assert group["booking_mode"] == "class"
    assert (
        client.get(
            "/appointments/slots", params={**params, "service_id": group["id"]}, headers=headers
        ).status_code
        == 404
    )
    assert closed.status_code == 201
    assert client.get("/appointments/slots", params=params, headers=headers).json() == []
