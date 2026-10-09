"""Reviews (migration 0033): clients rate attended visits in the app; the business sees
satisfaction overall, per staff member and per service, with the latest comments."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.common import blank_to_none, not_found
from app.api.deps import ClientDep, TenantContext, require
from app.core.permissions import Permission

router = APIRouter(prefix="/reviews", tags=["reviews"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]

REVIEW_WINDOW_DAYS = 14  # how long after a visit the client is asked (and may rate it)


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment", mode="before")
    @classmethod
    def blank(cls, value: object) -> object:
        return blank_to_none(value)


class PendingReview(BaseModel):
    booking_id: UUID
    service_name: str
    starts_at: datetime


class MyReview(BaseModel):
    id: UUID
    booking_id: UUID
    rating: int
    comment: str | None
    created_at: datetime


@client_router.get("/reviews/pending")
def pending_reviews(context: ClientDep) -> list[PendingReview]:
    """Recent attended visits the client hasn't rated yet, newest first."""
    rows = context.session.execute(
        text("""
            SELECT b.id AS booking_id, sv.name AS service_name, s.starts_at
            FROM app.bookings b
            JOIN app.sessions s ON s.id = b.session_id
            JOIN app.services sv ON sv.id = s.service_id
            WHERE b.client_id = app.current_client_id() AND b.status = 'checked_in'
              AND s.starts_at > now() - make_interval(days => :days) AND s.starts_at < now()
              AND NOT EXISTS (SELECT 1 FROM app.reviews r WHERE r.booking_id = b.id)
            ORDER BY s.starts_at DESC LIMIT 3
        """),
        {"days": REVIEW_WINDOW_DAYS},
    ).mappings()
    return [PendingReview.model_validate(dict(r)) for r in rows]


@client_router.post("/bookings/{booking_id}/review", status_code=status.HTTP_201_CREATED)
def review_visit(booking_id: UUID, body: ReviewCreate, context: ClientDep) -> MyReview:
    db = context.session
    visit = (
        db.execute(
            text("""
                SELECT b.status, s.starts_at, s.service_id, s.instructor_user_id,
                       s.starts_at > now() - make_interval(days => :days) AS recent
                FROM app.bookings b JOIN app.sessions s ON s.id = b.session_id
                WHERE b.id = :id AND b.client_id = app.current_client_id()
            """),
            {"id": booking_id, "days": REVIEW_WINDOW_DAYS},
        )
        .mappings()
        .first()
    )
    if visit is None:
        raise not_found()
    if visit["status"] != "checked_in" or not visit["recent"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_reviewable")
    try:
        with db.begin_nested():
            row = (
                db.execute(
                    text("""
                        INSERT INTO app.reviews
                            (tenant_id, client_id, booking_id, service_id, staff_user_id,
                             rating, comment)
                        VALUES (:t, app.current_client_id(), :b, :service, :staff, :rating,
                                :comment)
                        RETURNING id, booking_id, rating, comment, created_at
                    """),
                    {
                        "t": context.tenant_id,
                        "b": booking_id,
                        "service": visit["service_id"],
                        "staff": visit["instructor_user_id"],
                        "rating": body.rating,
                        "comment": body.comment,
                    },
                )
                .mappings()
                .one()
            )
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_reviewed"
        ) from error
    return MyReview.model_validate(dict(row))


# --- The business's view ----------------------------------------------------------------------


class RatingGroup(BaseModel):
    key: UUID
    name: str
    average: float
    count: int


class ReviewItem(BaseModel):
    id: UUID
    rating: int
    comment: str | None
    client_id: UUID
    client_name: str
    service_name: str
    staff_name: str | None
    created_at: datetime


class ReviewSummary(BaseModel):
    average: float | None
    count: int
    distribution: list[int] = Field(description="How many 1, 2, 3, 4 and 5-star reviews")
    by_staff: list[RatingGroup]
    by_service: list[RatingGroup]
    latest: list[ReviewItem]


STAFF_NAME = "coalesce(nullif(trim(u.full_name), ''), split_part(u.email, '@', 1))"


@router.get("")
def review_summary(
    context: ReadDep,
    days: Annotated[int, Query(ge=1, le=365)] = 90,
    client_id: UUID | None = None,
) -> ReviewSummary:
    """Ratings in the last `days` days (or all of one client's)."""
    db = context.session
    if client_id is not None:
        where, params = "r.client_id = :client", {"client": client_id}
    else:
        where, params = "r.created_at > now() - make_interval(days => :days)", {"days": days}
    stats = db.execute(
        text(f"""
            SELECT round(avg(rating)::numeric, 2) AS average, count(*) AS count,
                   array[count(*) FILTER (WHERE rating = 1), count(*) FILTER (WHERE rating = 2),
                         count(*) FILTER (WHERE rating = 3), count(*) FILTER (WHERE rating = 4),
                         count(*) FILTER (WHERE rating = 5)] AS distribution
            FROM app.reviews r WHERE {where}
        """),
        params,
    ).one()

    def groups(key: str, name: str, join: str) -> list[RatingGroup]:
        rows = db.execute(
            text(f"""
                SELECT {key} AS key, {name} AS name, round(avg(r.rating)::numeric, 2) AS average,
                       count(*) AS count
                FROM app.reviews r {join}
                WHERE {where} AND {key} IS NOT NULL
                GROUP BY 1, 2 ORDER BY 3 DESC, 4 DESC
            """),
            params,
        ).mappings()
        return [RatingGroup.model_validate(dict(r)) for r in rows]

    latest = db.execute(
        text(f"""
            SELECT r.id, r.rating, r.comment, r.client_id, r.created_at,
                   trim(c.first_name || ' ' || coalesce(c.last_name, '')) AS client_name,
                   sv.name AS service_name, {STAFF_NAME} AS staff_name
            FROM app.reviews r
            JOIN app.clients c ON c.id = r.client_id
            JOIN app.services sv ON sv.id = r.service_id
            LEFT JOIN app.users u ON u.id = r.staff_user_id
            WHERE {where} ORDER BY r.created_at DESC LIMIT 30
        """),
        params,
    ).mappings()
    return ReviewSummary(
        average=float(stats.average) if stats.average is not None else None,
        count=stats.count,
        distribution=list(stats.distribution),
        by_staff=groups(
            "r.staff_user_id", STAFF_NAME, "LEFT JOIN app.users u ON u.id = r.staff_user_id"
        ),
        by_service=groups(
            "r.service_id", "sv.name", "JOIN app.services sv ON sv.id = r.service_id"
        ),
        latest=[ReviewItem.model_validate(dict(r)) for r in latest],
    )
