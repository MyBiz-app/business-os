from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import AuthHeaders

TOKEN = "ExponentPushToken[abcdefghijklmnop]"


def count(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM app.push_tokens")).scalar_one()


def test_register_is_idempotent_and_unregister_removes(
    client: TestClient, auth: AuthHeaders, engine: Engine
) -> None:
    headers = auth(uuid4())
    body = {"token": TOKEN, "platform": "android"}
    assert client.get("/me", headers=headers).status_code == 200
    assert client.put("/me/push-tokens", json=body, headers=headers).status_code == 204
    assert client.put("/me/push-tokens", json=body, headers=headers).status_code == 204
    assert count(engine) == 1
    assert (
        client.request("DELETE", "/me/push-tokens", json=body, headers=headers).status_code == 204
    )
    assert count(engine) == 0


def test_one_person_cannot_remove_anothers_token(
    client: TestClient, auth: AuthHeaders, engine: Engine
) -> None:
    mine, other = auth(uuid4()), auth(uuid4())
    body = {"token": TOKEN, "platform": "ios"}
    for headers in (mine, other):
        client.get("/me", headers=headers)
    client.put("/me/push-tokens", json=body, headers=mine)
    client.request("DELETE", "/me/push-tokens", json=body, headers=other)
    assert count(engine) == 1


def test_rejects_unknown_platform(client: TestClient, auth: AuthHeaders) -> None:
    response = client.put(
        "/me/push-tokens", json={"token": TOKEN, "platform": "web"}, headers=auth(uuid4())
    )
    assert response.status_code == 422
