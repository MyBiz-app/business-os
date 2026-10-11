"""Migrations survive a database that already holds a renumbered migration's changes."""

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text

from tests.conftest import API_DIR, SERVER_URL

DB_NAME = "business_os_migration_test"


def test_renumbered_palette_migration_can_rerun() -> None:
    """Staging applied the palette migration as 0058 before it became 0059 (shift planning took
    0058). The database then said 0058 with the palette columns present, and the deploy failed on
    "column palette_background already exists", leaving the API on old code."""
    server = create_engine(SERVER_URL, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {DB_NAME}"))
    url = make_url(SERVER_URL).set(database=DB_NAME)
    config = Config(os.path.join(API_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(API_DIR, "migrations"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    try:
        command.upgrade(config, "0059")  # every column below now exists
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("UPDATE public.alembic_version SET version_num = '0057'"))
        engine.dispose()

        command.upgrade(config, "head")

        engine = create_engine(url)
        with engine.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM public.alembic_version"))
            assert version.scalar_one() != "0057"
        engine.dispose()
    finally:
        with server.connect() as connection:
            connection.execute(text(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE)"))
        server.dispose()
