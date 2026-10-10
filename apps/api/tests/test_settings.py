import struct
import zlib
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.conftest import AuthHeaders, add_member
from tests.test_tenants import STUDIO


def tiny_png() -> bytes:
    """A valid 1x1 PNG."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")
    )


@pytest.fixture
def studio(client: TestClient, auth: AuthHeaders) -> dict[str, UUID]:
    owner = uuid4()
    tenant_id = UUID(client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"])
    return {"owner": owner, "tenant_id": tenant_id}


def test_update_business_details_and_color(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])

    updated = client.patch(
        "/tenants/current",
        json={"name": " Flow Studio ", "locale": "en", "primary_color": "#0F766E"},
        headers=headers,
    )
    cleared = client.patch("/tenants/current", json={"primary_color": None}, headers=headers)

    assert updated.status_code == 200
    assert updated.json()["name"] == "Flow Studio"
    assert updated.json()["locale"] == "en"
    assert updated.json()["primary_color"] == "#0F766E"
    assert updated.json()["time_zone"] == "Asia/Jerusalem"
    assert cleared.json()["primary_color"] is None
    assert cleared.json()["name"] == "Flow Studio"


def test_schedule_default_view_is_kept_per_business(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    branch = client.get("/locations", headers=headers).json()[0]["id"]
    other = uuid4()
    foreign = client.post("/tenants", json=STUDIO, headers=auth(other)).json()["id"]
    foreign_branch = client.get("/locations", headers=auth(other, foreign)).json()[0]["id"]

    initial = client.get("/tenants/current", headers=headers).json()
    saved = client.patch(
        "/tenants/current",
        json={"schedule_default_view": "day", "schedule_default_branches": [branch]},
        headers=headers,
    )
    cleared = client.patch("/tenants/current", json={"schedule_default_branches": []}, headers=headers)
    rejected = [
        {"schedule_default_view": "year"},
        {"schedule_default_branches": [foreign_branch]},
        {"schedule_default_branches": [str(uuid4())]},
    ]

    assert (initial["schedule_default_view"], initial["schedule_default_branches"]) == ("week", [])
    assert saved.json()["schedule_default_view"] == "day"
    assert saved.json()["schedule_default_branches"] == [branch]
    assert cleared.json()["schedule_default_branches"] == []
    assert cleared.json()["schedule_default_view"] == "day"
    for body in rejected:
        assert client.patch("/tenants/current", json=body, headers=headers).status_code == 422


def test_rejects_invalid_settings(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    for body in [{"primary_color": "teal"}, {"time_zone": "Nowhere"}, {"name": " "}]:
        assert client.patch("/tenants/current", json=body, headers=headers).status_code == 422


def test_logo_upload_and_public_download(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    png = tiny_png()

    uploaded = client.put(
        "/tenants/current/logo", files={"file": ("logo.png", png, "image/png")}, headers=headers
    )
    logo_url = uploaded.json()["logo_url"]
    public = client.get(logo_url)  # no auth headers

    assert uploaded.status_code == 200
    assert logo_url.startswith(f"/public/tenants/{studio['tenant_id']}/logo?v=")
    assert public.status_code == 200
    assert public.content == png
    assert public.headers["content-type"] == "image/png"
    assert "immutable" in public.headers["cache-control"]

    removed = client.delete("/tenants/current/logo", headers=headers)
    assert removed.json()["logo_url"] is None
    assert client.get(f"/public/tenants/{studio['tenant_id']}/logo").status_code == 404


def test_logo_must_be_a_real_small_image(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    headers = auth(studio["owner"], studio["tenant_id"])
    fake = b"<svg onload=alert(1)></svg>"
    huge = tiny_png() + b"\x00" * (512 * 1024)

    disguised = client.put(
        "/tenants/current/logo", files={"file": ("logo.png", fake, "image/png")}, headers=headers
    )
    too_big = client.put(
        "/tenants/current/logo", files={"file": ("logo.png", huge, "image/png")}, headers=headers
    )

    assert disguised.status_code == 415
    assert too_big.status_code == 413


def test_only_owner_and_manager_change_settings(
    client: TestClient, auth: AuthHeaders, engine: Engine, studio: dict[str, UUID]
) -> None:
    desk = uuid4()
    add_member(engine, studio["tenant_id"], desk, "front_desk")
    headers = auth(desk, studio["tenant_id"])

    assert client.patch("/tenants/current", json={"name": "X"}, headers=headers).status_code == 403
    logo = client.put(
        "/tenants/current/logo", files={"file": ("l.png", tiny_png(), "image/png")}, headers=headers
    )
    assert logo.status_code == 403


def test_settings_only_change_own_business(
    client: TestClient, auth: AuthHeaders, studio: dict[str, UUID]
) -> None:
    other_owner = uuid4()
    other_tenant = client.post("/tenants", json=STUDIO, headers=auth(other_owner)).json()["id"]

    client.patch(
        "/tenants/current", json={"name": "Renamed"}, headers=auth(other_owner, other_tenant)
    )
    mine = client.get("/tenants/current", headers=auth(studio["owner"], studio["tenant_id"]))
    forged = client.patch(
        "/tenants/current", json={"name": "Hacked"}, headers=auth(other_owner, studio["tenant_id"])
    )

    assert mine.json()["name"] == STUDIO["name"]
    assert forged.status_code == 403
