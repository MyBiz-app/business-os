"""Guided tours: which ones the signed-in person has already seen (per person, not per business)."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import SessionDep, UserDep

router = APIRouter(prefix="/me/tours", tags=["account"])

# The tours the product has. A new tour is added here together with its screens.
TourKey = Literal["ai_team", "website_offer"]


class SeenTours(BaseModel):
    seen: list[TourKey]


@router.get("")
def list_seen_tours(user: UserDep, session: SessionDep) -> SeenTours:
    """The tours this person has finished or skipped."""
    rows = session.execute(
        text("SELECT tour_key FROM app.user_tours WHERE user_id = :user ORDER BY tour_key"),
        {"user": user.id},
    ).scalars()
    return SeenTours(seen=[key for key in rows if key in TourKey.__args__])  # type: ignore[attr-defined]


@router.put("/{key}", status_code=204)
def mark_tour_seen(key: TourKey, user: UserDep, session: SessionDep) -> Response:
    """Remember that the tour was seen; safe to call again."""
    session.execute(
        text("""
            INSERT INTO app.user_tours (user_id, tour_key) VALUES (:user, :key)
            ON CONFLICT (user_id, tour_key) DO NOTHING
        """),
        {"user": user.id, "key": key},
    )
    return Response(status_code=204)


@router.delete("/{key}", status_code=204)
def reset_tour(key: TourKey, user: UserDep, session: SessionDep) -> Response:
    """Forget that the tour was seen, so it shows again on the next visit."""
    session.execute(
        text("DELETE FROM app.user_tours WHERE user_id = :user AND tour_key = :key"),
        {"user": user.id, "key": key},
    )
    return Response(status_code=204)
