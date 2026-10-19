"""The security center and the legal center in the MyBiz console (K4).

Read-only and owners only. Both are built from what the product already records: two-step
sign-in and the "I understand the risk" confirmations of business owners, the MyBiz team's visits
inside businesses, the accepted versions of the legal documents, and the privacy requests. The
findings of the security agent are read from the saved reports (`/platform/ai/reports`)."""

import datetime as dt
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.api.platform import OwnerDep
from app.core.mfa import RISK_VERSION
from app.legal.documents import VERSIONS

router = APIRouter(prefix="/platform", tags=["platform"])

Days = Annotated[int, Query(ge=1, le=365)]


class OwnerSecurity(BaseModel):
    email: str
    business_id: UUID
    business_name: str
    requires_mfa: bool = Field(description="The business requires two-step sign-in of its team")
    mfa_enrolled: bool | None = Field(description="None when the sign-in provider can't be read")
    risk_acknowledged_at: dt.datetime | None = Field(
        description="When the owner confirmed they understand the risk, for the current warning"
    )


class SecurityOwners(BaseModel):
    owners: int = Field(description="People who own at least one open business")
    with_mfa: int | None = Field(description="None when the sign-in provider can't be read")
    acknowledged_risk: int = Field(description="Without two-step sign-in, confirmed the risk")
    exposed: int | None = Field(description="Without two-step sign-in and no confirmation yet")
    businesses: int
    businesses_requiring_mfa: int
    risk_version: str
    rows: list[OwnerSecurity] = Field(description="Owners without two-step sign-in first")


class TeamVisit(BaseModel):
    actor_email: str
    business_id: UUID
    business_name: str
    views: int
    changes: int
    last_at: dt.datetime


class TeamVisits(BaseModel):
    days: int
    visits: list[TeamVisit]


@router.get("/security/owners")
def security_owners(db: OwnerDep) -> SecurityOwners:
    """Two-step sign-in and risk confirmations of business owners, with the exposed ones first."""
    rows = db.execute(
        text("SELECT * FROM app.platform_security_owners(:version)"), {"version": RISK_VERSION}
    ).mappings()
    owners = [OwnerSecurity.model_validate(r) for r in rows]
    # One person can own several businesses: protected or confirmed if any of their rows says so.
    protected: dict[str, bool | None] = {}
    confirmed: dict[str, bool] = {}
    for row in owners:
        protected[row.email] = (
            None if row.mfa_enrolled is None else bool(protected.get(row.email) or row.mfa_enrolled)
        )
        confirmed[row.email] = (
            confirmed.get(row.email, False) or row.risk_acknowledged_at is not None
        )
    known = None not in protected.values()
    without = [email for email, ok in protected.items() if not ok]
    acknowledged = [email for email in without if confirmed[email]]
    owners.sort(key=lambda o: (bool(o.mfa_enrolled), o.risk_acknowledged_at is not None))
    return SecurityOwners(
        owners=len(protected),
        with_mfa=len(protected) - len(without) if known else None,
        acknowledged_risk=len(acknowledged),
        exposed=len(without) - len(acknowledged) if known else None,
        businesses=len({o.business_id for o in owners}),
        businesses_requiring_mfa=len({o.business_id for o in owners if o.requires_mfa}),
        risk_version=RISK_VERSION,
        rows=owners,
    )


@router.get("/security/visits")
def security_visits(db: OwnerDep, days: Days = 30) -> TeamVisits:
    """How often each MyBiz team member viewed or changed a business, in the last days."""
    rows = db.execute(
        text("SELECT * FROM app.platform_security_visits(:days)"), {"days": days}
    ).mappings()
    return TeamVisits(days=days, visits=[TeamVisit.model_validate(r) for r in rows])


class DocumentCoverage(BaseModel):
    document: Literal["terms", "privacy", "dpa"]
    version: str
    accepted: int
    eligible: int = Field(description="People who have to accept it: everyone, or owners for dpa")


class Acceptance(BaseModel):
    accepted_at: dt.datetime
    email: str
    business_name: str | None
    document: Literal["terms", "privacy", "dpa"]
    version: str
    context: Literal["signup", "client_join", "reaccept"]


class PrivacyRequest(BaseModel):
    occurred_at: dt.datetime
    kind: Literal["business_export", "client_export", "client_erasure", "business_closure"]
    business_id: UUID
    business_name: str
    status: Literal["building", "ready", "failed", "done", "waiting"]
    delete_after: dt.datetime | None = Field(description="Closed businesses: the deletion date")


class LegalCenter(BaseModel):
    days: int
    documents: list[DocumentCoverage]
    acceptances: list[Acceptance] = Field(description="The latest 200")
    privacy_requests: list[PrivacyRequest] = Field(description="The last 12 months, latest 200")


@router.get("/legal")
def legal_center(db: OwnerDep, days: Days = 30) -> LegalCenter:
    """Current document versions and who accepted them, plus the privacy requests."""
    coverage = db.execute(
        text("SELECT * FROM app.platform_legal_coverage(CAST(:versions AS jsonb))"),
        {"versions": json.dumps(VERSIONS)},
    ).mappings()
    accepted = db.execute(
        text("SELECT * FROM app.platform_legal_acceptances(:days)"), {"days": days}
    ).mappings()
    requests = db.execute(text("SELECT * FROM app.platform_privacy_requests()")).mappings()
    return LegalCenter(
        days=days,
        documents=[DocumentCoverage.model_validate(r) for r in coverage],
        acceptances=[Acceptance.model_validate(r) for r in accepted],
        privacy_requests=[PrivacyRequest.model_validate(r) for r in requests],
    )
