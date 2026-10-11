"""Blocking database calls must never run on the event loop (P1-1), and the engine takes its
pool settings from configuration (P1-2)."""

import inspect

from app.core.config import Settings
from app.core.db import get_engine
from app.main import create_app

DOC_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def test_no_route_handler_is_async() -> None:
    """A route declared `async def` runs on the event loop; one blocking query would stall every
    request in the worker. Handlers are plain `def` (run in the thread pool); the few things that
    need `await` (reading a request body) live in dependencies."""
    offenders = [
        f"{route.path} -> {route.endpoint.__name__}"
        for route in create_app().routes
        if hasattr(route, "endpoint")
        and inspect.iscoroutinefunction(route.endpoint)
        and route.path not in DOC_PATHS  # FastAPI's own, no database
    ]
    assert offenders == []


def test_engine_uses_pool_settings(monkeypatch) -> None:
    monkeypatch.setenv("API_DB_POOL_SIZE", "3")
    monkeypatch.setenv("API_DB_MAX_OVERFLOW", "4")
    monkeypatch.setenv("API_DB_POOL_TIMEOUT", "7")
    from app.core import config

    config.get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        pool = get_engine().pool
        assert (pool.size(), pool._max_overflow, pool._timeout) == (3, 4, 7)
    finally:
        config.get_settings.cache_clear()
        get_engine.cache_clear()


def test_prepared_statements_are_off_by_default() -> None:
    assert Settings().db_prepared_statements is False
