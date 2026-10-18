"""Request and response shapes of the schedule endpoints."""

import datetime as dt
from datetime import datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.common import blank_to_none

MAX_SERIES_DAYS = 26 * 7  # Series are expanded up front; a background job will extend them.
DEFAULT_SERIES_DAYS = 12 * 7

SessionStatus = Literal["scheduled", "cancelled"]
JobStatus = Literal["scheduled", "on_the_way", "in_progress", "done"]


class Placement(BaseModel):
    location_id: UUID | None = None
    room_id: UUID | None = None
    instructor_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def blank_notes(cls, value: object) -> object:
        return blank_to_none(value)


class Repeat(BaseModel):
    weekdays: list[int] = Field(min_length=1, description="0 = Monday … 6 = Sunday")
    ends_on: dt.date | None = None

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("weekdays are 0 (Monday) to 6 (Sunday)")
        return sorted(set(value))


class SessionCreate(Placement):
    service_id: UUID
    date: dt.date = Field(description="Local date in the business's time zone")
    start_time: time = Field(description="Local wall-clock time")
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    repeat: Repeat | None = None

    @model_validator(mode="after")
    def bounded_series(self) -> "SessionCreate":
        if self.repeat and self.repeat.ends_on:
            if self.repeat.ends_on < self.date:
                raise ValueError("repeat.ends_on is before date")
            if (self.repeat.ends_on - self.date).days > MAX_SERIES_DAYS:
                raise ValueError(f"a series can span at most {MAX_SERIES_DAYS} days")
        return self


class SessionUpdate(Placement):
    date: dt.date | None = None
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    capacity: int | None = Field(default=None, ge=1, le=1000)
    status: SessionStatus | None = None


class ServiceSummary(BaseModel):
    id: UUID
    name: str
    color: str | None


class ScheduledSession(BaseModel):
    id: UUID
    series_id: UUID | None
    service: ServiceSummary
    location_id: UUID | None
    location_name: str | None
    room_id: UUID | None
    room_name: str | None
    instructor_user_id: UUID | None
    instructor_email: str | None
    starts_at: datetime
    ends_at: datetime
    capacity: int
    booked: int
    waitlisted: int
    waiting_requests: int = Field(
        default=0,
        description="Clients waiting for a spot like this one (a range, a whole day or this exact"
        " time), on top of those on the class's own waitlist",
    )
    series_open_ended: bool | None = Field(
        description="For a session in a weekly series: whether the series keeps going"
    )
    status: SessionStatus
    notes: str | None
    booking_mode: Literal["class", "appointment", "resource"] = Field(
        description="appointment: a one-to-one booking with the instructor;"
        " resource: a room or court reserved by the hour"
    )
    appointment_client: str | None = Field(
        description="For an appointment or a reservation: who it is with"
    )
    price_amount: int | None = Field(
        default=None, description="For a reservation: its price, fixed when it was made"
    )
    price_currency: str | None = None
    paid: bool | None = Field(default=None, description="For a reservation: whether it is paid")
    address: str | None = Field(default=None, description="An on-site job: where (#42)")
    address_notes: str | None = Field(
        default=None, description="An on-site job: how to get in (gate code, floor)"
    )
    job_status: JobStatus | None = Field(default=None, description="An on-site job's progress")
    travel_minutes: int = Field(default=0, description="Time to get there, before the job")


class OptionItem(BaseModel):
    id: UUID
    name: str


class ServiceOption(OptionItem):
    duration_minutes: int
    capacity: int


class RoomOption(OptionItem):
    location_id: UUID


class InstructorOption(BaseModel):
    user_id: UUID
    email: str
    full_name: str | None


class ScheduleOptions(BaseModel):
    services: list[ServiceOption]
    locations: list[OptionItem]
    rooms: list[RoomOption]
    instructors: list[InstructorOption]


class CreatedSessions(BaseModel):
    series_id: UUID | None
    session_ids: list[UUID]
