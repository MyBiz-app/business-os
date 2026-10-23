"""The part a demo business plays, read from its industry instead of its name.

The extra demo layers (rounds 6 and 7) write content that fits the kind of business: quotes for
a gym's corporate workshops, a pizzeria's catering, and so on. They used to look it up by the
names of the original three demo businesses; a role keeps them working for any demo's
businesses, whatever they are called.
"""

from uuid import UUID

from sqlalchemy import Connection, text

# industry (catalog key) -> role
ROLE_BY_VERTICAL = {
    "gym": "gym",
    "pilates": "gym",
    "crossfit": "gym",
    "hair_salon": "salon",
    "barbershop": "barber",
    "pizzeria": "pizza",
    "padel_tennis": "courts",
    "physiotherapy": "clinic",
    "nutrition": "clinic",
}


def role_of(conn: Connection, tenant_id: UUID) -> str | None:
    """The business's role, or None for an industry the layers have no tailored content for."""
    vertical = conn.execute(
        text("SELECT vertical FROM app.tenants WHERE id = :t"), {"t": tenant_id}
    ).scalar_one()
    return ROLE_BY_VERTICAL.get(vertical)
