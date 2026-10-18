"""Business size: a business that signed up as "solo" grows out of it with people or branches."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def grow_from_solo(session: Session, tenant_id: UUID) -> None:
    """The first employee or the second branch ends solo mode: the team, schedule and branch
    areas open by themselves. Other sizes are the owner's own answer and stay as they are."""
    session.execute(
        text(
            "UPDATE app.tenants SET business_size = 'small' "
            "WHERE id = :t AND business_size = 'solo'"
        ),
        {"t": tenant_id},
    )
