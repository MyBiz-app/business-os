import importlib
import pkgutil

from fastapi import APIRouter

import app.api as api_package
from app.api.registry import ROUTERS


def test_every_router_is_registered() -> None:
    registered = {id(router) for router in ROUTERS}
    missing = []
    for info in pkgutil.iter_modules(api_package.__path__):
        module = importlib.import_module(f"app.api.{info.name}")
        missing += [
            f"{info.name}.{name}"
            for name, value in vars(module).items()
            if isinstance(value, APIRouter) and id(value) not in registered
        ]
    assert not missing, f"routers not listed in app/api/registry.py: {missing}"
