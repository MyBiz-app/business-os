import json

from fastapi.testclient import TestClient

from app.main import create_app


def test_response_carries_a_request_id_and_keeps_a_plain_one() -> None:
    client = TestClient(create_app())

    generated = client.get("/health").headers["X-Request-ID"]
    kept = client.get("/health", headers={"X-Request-ID": "abc-123"}).headers["X-Request-ID"]
    replaced = client.get("/health", headers={"X-Request-ID": "bad id\r\n<x>"}).headers[
        "X-Request-ID"
    ]

    assert len(generated) == 32
    assert kept == "abc-123"
    assert replaced != "bad id\r\n<x>"


def test_request_line_is_json_with_route_template_and_no_query(capsys) -> None:
    client = TestClient(create_app())

    client.get("/health?email=someone@example.com", headers={"X-Request-ID": "rid-1"})

    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["message"] == "request"
    assert line["request_id"] == "rid-1"
    assert line["path"] == "/health"
    assert line["status"] == 200
    assert "someone@example.com" not in json.dumps(line)


def test_unhandled_error_returns_a_stable_body_with_the_request_id(capsys) -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret detail")

    response = TestClient(app, raise_server_exceptions=False).get(
        "/boom", headers={"X-Request-ID": "rid-2"}
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error", "request_id": "rid-2"}
    assert response.headers["X-Request-ID"] == "rid-2"
    out = capsys.readouterr().out
    assert "unhandled error" in out and "rid-2" in out
    assert "secret detail" not in response.text


def test_slow_queries_are_logged_without_parameters(engine, capsys) -> None:
    from sqlalchemy import create_engine, text

    from app.core.db import log_slow_queries

    own = create_engine(engine.url)
    log_slow_queries(own, 1)
    with own.connect() as connection:
        connection.execute(text("SELECT pg_sleep(0.05), :secret"), {"secret": "personal@x.com"})
    own.dispose()

    out = capsys.readouterr().out
    assert "slow query" in out
    assert "personal@x.com" not in out
