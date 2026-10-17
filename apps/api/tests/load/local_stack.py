"""A local stack for the k6 load tests (tests/load/k6): a migrated database with one demo business
at a chosen size, a signing key, and the key set the API checks sign-in tokens against.

    uv run python -m tests.load.local_stack --clients 5000      # prints the tenant id and a token

then, in another terminal, start the API against the same database with
`API_JWKS_URL=http://127.0.0.1:54399/jwks.json` (see docs/reviews/load-test-2026-10.md). The script
keeps serving the key set until it is stopped. Nothing here touches staging or production."""

import argparse
import base64
import dataclasses
import json
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

import jwt
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.seed import seed
from app.seed.common import STUDIO

API_DIR = Path(__file__).resolve().parents[2]
KEY_ID = "load-test"
PORT = 54399


def b64(number: int) -> str:
    return base64.urlsafe_b64encode(number.to_bytes(32, "big")).rstrip(b"=").decode()


def jwks_for(key: ec.EllipticCurvePrivateKey) -> dict:
    numbers = key.public_key().public_numbers()
    jwk = {"kty": "EC", "crv": "P-256", "alg": "ES256", "use": "sig", "kid": KEY_ID}
    return {"keys": [{**jwk, "x": b64(numbers.x), "y": b64(numbers.y)}]}


def migrate(server_url: str, name: str) -> str:
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {name}"))
    admin.dispose()
    url = make_url(server_url).set(database=name).render_as_string(hide_password=False)
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server-url", default="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres"
    )
    parser.add_argument("--database", default="business_os_load")
    parser.add_argument("--clients", type=int, default=8500, help="50x the demo studio's 170")
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--hours", type=int, default=6, help="how long the token lasts")
    args = parser.parse_args()

    url = migrate(args.server_url, args.database)
    engine = create_engine(url)
    owner = uuid4()
    email = f"load-{owner}@example.com"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email)"),
            {"id": owner, "email": email},
        )
        tenant_id = seed(
            connection,
            email,
            args.months,
            random.Random(7),
            dataclasses.replace(STUDIO, clients=args.clients),
        )
        connection.execute(text("ANALYZE"))

    key = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(owner),
            "email": email,
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + args.hours * 3600,
        },
        key,
        algorithm="ES256",
        headers={"kid": KEY_ID},
    )
    print(json.dumps({"database_url": url, "tenant_id": str(tenant_id), "token": token}))

    body = json.dumps(jwks_for(key)).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
