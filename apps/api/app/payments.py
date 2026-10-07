"""Payment providers for client checkouts (see migrations 0019 and 0048, decision X13).

The business's payments provider (its own connection, or the platform default) is chosen in
app/providers/choice.py; `simulated` until a real provider is connected (O1, #46)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.providers.choice import choose

SIMULATED = "simulated"


def provider_for_business(db: Session | None = None, tenant_id: UUID | None = None) -> str:
    """The provider new checkouts of the business use."""
    if db is None:
        return SIMULATED
    return choose(db, tenant_id, "payments").info.name
