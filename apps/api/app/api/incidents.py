"""Incident banners (go-live, GL23; migration 0121): the MyBiz console opens a banner for an
incident, planned maintenance or a security event, and every page of the web app and the mobile app
shows it until the team resolves it. The open banners are public (no personal data), so the sign-in
page can show them too. The response playbook is docs/deploy/on-call.md."""

import datetime as dt
import json
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import AnonymousSessionDep
from app.api.platform import PlatformPermission, require_platform, run_rule

router = APIRouter(tags=["incidents"])

IncidentsDep = Annotated[Session, Depends(require_platform(PlatformPermission.BROADCASTS_MANAGE))]

Kind = Literal["incident", "maintenance", "security"]
Locale = Literal["he", "en"]


class IncidentTexts(BaseModel):
    title: str = Field(default="", max_length=150)
    body: str = Field(default="", max_length=600)


class IncidentBody(BaseModel):
    kind: Kind
    content: dict[Locale, IncidentTexts]
    status_url: str = Field(default="", max_length=500, description="The status page, if any")

    @field_validator("status_url")
    @classmethod
    def web_address(cls, value: str) -> str:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("must be a web address")
        return value

    @field_validator("content")
    @classmethod
    def some_text(cls, value: dict[Locale, IncidentTexts]) -> dict[Locale, IncidentTexts]:
        if not any(texts.title.strip() for texts in value.values()):
            raise ValueError("a title is required")
        return value


class ActiveIncident(BaseModel):
    id: UUID
    kind: Kind
    content: dict[Locale, IncidentTexts]
    status_url: str
    created_at: dt.datetime


class Incident(ActiveIncident):
    created_by: str
    resolved_at: dt.datetime | None
    resolved_by: str | None


@router.get("/public/incidents")
def active_incidents(db: AnonymousSessionDep) -> list[ActiveIncident]:
    """The banners that are open now, newest first."""
    rows = db.execute(text("SELECT * FROM app.active_incidents()")).mappings().all()
    return [ActiveIncident.model_validate(dict(row)) for row in rows]


@router.get("/platform/incidents")
def list_incidents(db: IncidentsDep) -> list[Incident]:
    rows = db.execute(text("SELECT * FROM app.incident_rows()")).mappings().all()
    return [Incident.model_validate(dict(row)) for row in rows]


@router.post("/platform/incidents", status_code=201)
def open_incident(body: IncidentBody, db: IncidentsDep) -> Incident:
    content: dict[str, Any] = {k: v.model_dump() for k, v in body.content.items()}
    incident_id = run_rule(
        db,
        "SELECT app.incident_open(:kind, CAST(:content AS jsonb), :url)",
        {"kind": body.kind, "content": json.dumps(content), "url": body.status_url},
    )
    return _one(db, incident_id)


@router.post("/platform/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: UUID, db: IncidentsDep) -> Incident:
    run_rule(db, "SELECT app.incident_resolve(:id)", {"id": incident_id})
    return _one(db, incident_id)


def _one(db: Session, incident_id: UUID) -> Incident:
    for incident in list_incidents(db):
        if incident.id == incident_id:
            return incident
    raise HTTPException(status_code=404, detail="not_found")
