from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import AuthHeaders


def test_mark_seen_is_idempotent_and_reset_forgets(client: TestClient, auth: AuthHeaders) -> None:
    headers = auth(uuid4())
    assert client.get("/me", headers=headers).status_code == 200
    assert client.get("/me/tours", headers=headers).json() == {"seen": []}
    assert client.put("/me/tours/ai_team", headers=headers).status_code == 204
    assert client.put("/me/tours/ai_team", headers=headers).status_code == 204
    assert client.get("/me/tours", headers=headers).json() == {"seen": ["ai_team"]}
    assert client.delete("/me/tours/ai_team", headers=headers).status_code == 204
    assert client.get("/me/tours", headers=headers).json() == {"seen": []}


def test_seen_is_per_person(client: TestClient, auth: AuthHeaders) -> None:
    mine, other = auth(uuid4()), auth(uuid4())
    for headers in (mine, other):
        client.get("/me", headers=headers)
    client.put("/me/tours/ai_team", headers=mine)
    assert client.get("/me/tours", headers=other).json() == {"seen": []}
    client.delete("/me/tours/ai_team", headers=other)
    assert client.get("/me/tours", headers=mine).json() == {"seen": ["ai_team"]}


def test_unknown_tour_is_rejected(client: TestClient, auth: AuthHeaders) -> None:
    assert client.put("/me/tours/nope", headers=auth(uuid4())).status_code == 422
