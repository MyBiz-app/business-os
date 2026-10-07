"""Which provider a business uses for a capability: its own connection (settings →
Integrations) when it has one, otherwise the platform's default (environment)."""

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.providers import ai, email, invoicing, messaging, payments, storage  # noqa: F401
from app.providers.registry import REGISTRY, Capability, ProviderInfo, check_settings
from app.providers.secrets import decrypt


@dataclass(frozen=True)
class Chosen:
    info: ProviderInfo
    instance: Any
    own: bool  # the business's own connection (not the platform default)


def platform_default(capability: Capability) -> tuple[str, dict[str, str]]:
    """The platform's provider for a capability and its settings (API_<CAP>_PROVIDER and
    API_<CAP>_SETTINGS, a JSON object)."""
    settings = get_settings()
    name = getattr(settings, f"{capability}_provider")
    raw = getattr(settings, f"{capability}_settings", None)
    values = json.loads(raw.get_secret_value()) if raw is not None else {}
    return name, values


def choose(db: Session | Connection, tenant_id: UUID | None, capability: Capability) -> Chosen:
    row = None
    if tenant_id is not None:
        # Through the function: a client's checkout or a provider's webhook reads it too.
        row = (
            db.execute(
                text("SELECT * FROM app.tenant_integration(:t, :c)"),
                {"t": tenant_id, "c": capability},
            )
            .mappings()
            .first()
        )
    if row is not None:
        info = REGISTRY.get(capability, row["provider"])
        values = {**(row["settings"] or {}), **decrypt(row["secrets"])}
        own = True
    else:
        name, values = platform_default(capability)
        info = REGISTRY.get(capability, name)
        own = False
    return Chosen(info=info, instance=info.factory(check_settings(info, values)), own=own)
