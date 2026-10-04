"""Health declarations: clients sign the business's health form in the app; staff review
declarations that answered "yes" to any question.

A client's current state comes from their latest declaration:
missing (none), expired, needs_review, rejected, or ok (all "no", or approved by staff)."""

import json
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, require
from app.health import FORMS, HealthForm
from app.permissions import Permission

router = APIRouter(tags=["health"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

HealthState = Literal["missing", "expired", "needs_review", "rejected", "ok"]
DeclarationStatus = Literal["valid", "needs_review", "approved", "rejected"]
Locale = Literal["he", "en"]

# The client's state from their latest declaration. Needs `c` (app.clients) and `t`
# (app.tenants) in scope; "today" is the business's local date.
HEALTH_STATE_SQL = """
    coalesce((
        SELECT CASE
                   WHEN d.valid_until < (now() AT TIME ZONE t.time_zone)::date THEN 'expired'
                   WHEN d.status IN ('valid', 'approved') THEN 'ok'
                   ELSE d.status
               END
        FROM app.health_declarations d
        WHERE d.tenant_id = c.tenant_id AND d.client_id = c.id
        ORDER BY d.signed_at DESC LIMIT 1
    ), 'missing')
"""


class Answer(BaseModel):
    id: str
    question: str
    answer: bool


class Declaration(BaseModel):
    id: UUID
    form_key: str
    locale: Locale
    answers: list[Answer] = Field(description="The questions exactly as signed, with answers")
    statement: str
    all_clear: bool = Field(description='Every answer was "no"')
    signed_name: str
    signed_at: datetime
    valid_until: date = Field(description="Last local date the declaration is valid")
    status: DeclarationStatus
    reviewed_at: datetime | None
    review_note: str | None


class FormQuestion(BaseModel):
    id: str
    text: str


class Form(BaseModel):
    key: str
    questions: list[FormQuestion]
    statement: str


class MyHealth(BaseModel):
    required: bool = Field(description="The business requires a declaration to book in the app")
    state: HealthState
    form: Form | None = Field(description="The form to sign; null if the business has none")
    current: Declaration | None


class DeclarationCreate(BaseModel):
    locale: Locale
    answers: dict[str, bool]
    signed_name: str = Field(min_length=2, max_length=200)
    accept: Literal[True] = Field(description="The client accepts the statement")

    @field_validator("signed_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("signed_name is too short")
        return value


class Review(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


DECLARATION_COLUMNS = """
    id, form_key, locale, answers, statement, all_clear, signed_name, signed_at,
    valid_until, status, reviewed_at, review_note
"""


def health_state(db: Session, client_id: UUID) -> HealthState:
    return db.execute(
        text(f"""
            SELECT {HEALTH_STATE_SQL}
            FROM app.clients c JOIN app.tenants t ON t.id = c.tenant_id
            WHERE c.id = :id
        """),
        {"id": client_id},
    ).scalar_one()


def ensure_may_book(db: Session, tenant_id: UUID, client_id: UUID) -> None:
    """Client-app bookings: a business that requires a declaration needs one that is ok."""
    required = db.execute(
        text("SELECT requires_health_declaration FROM app.tenants WHERE id = :id"),
        {"id": tenant_id},
    ).scalar_one()
    if not required:
        return
    state = health_state(db, client_id)
    if state in ("needs_review", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="health_declaration_review"
        )
    if state != "ok":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="health_declaration_required"
        )


def _business_form(db: Session) -> tuple[HealthForm | None, bool, str]:
    row = db.execute(
        text("""
            SELECT vertical, requires_health_declaration, time_zone
            FROM app.tenants WHERE id = app.client_tenant_id()
        """)
    ).one()
    return FORMS.get(row.vertical), row.requires_health_declaration, row.time_zone


def _latest(db: Session, client_id: UUID) -> Declaration | None:
    row = (
        db.execute(
            text(f"""
                SELECT {DECLARATION_COLUMNS} FROM app.health_declarations
                WHERE client_id = :id ORDER BY signed_at DESC LIMIT 1
            """),
            {"id": client_id},
        )
        .mappings()
        .first()
    )
    return Declaration.model_validate(dict(row)) if row else None


def _my_health(db: Session, client_id: UUID, locale: Locale) -> MyHealth:
    form, required, _ = _business_form(db)
    return MyHealth(
        required=required,
        state=health_state(db, client_id),
        form=(
            Form(
                key=form.key,
                questions=[
                    FormQuestion(id=question_id, text=texts[locale])
                    for question_id, texts in form.questions.items()
                ],
                statement=form.statement[locale],
            )
            if form
            else None
        ),
        current=_latest(db, client_id),
    )


@client_router.get("/health-declaration")
def my_health_declaration(
    context: ClientDep, locale: Annotated[Locale, Query()] = "he"
) -> MyHealth:
    return _my_health(context.session, context.client_id, locale)


@client_router.post("/health-declaration", status_code=status.HTTP_201_CREATED)
def sign_health_declaration(body: DeclarationCreate, context: ClientDep) -> MyHealth:
    """Signs a new declaration; it replaces the previous one."""
    db = context.session
    form, _, time_zone = _business_form(db)
    if form is None:
        raise not_found()
    if set(body.answers) != set(form.questions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="answers_incomplete"
        )
    answers = [
        {"id": question_id, "question": texts[body.locale], "answer": body.answers[question_id]}
        for question_id, texts in form.questions.items()
    ]
    all_clear = not any(body.answers.values())
    db.execute(
        text("""
            INSERT INTO app.health_declarations
                (tenant_id, client_id, form_key, locale, answers, statement, all_clear,
                 signed_name, signed_by, valid_until, status)
            VALUES (:tenant_id, :client_id, :form_key, :locale, :answers, :statement,
                    :all_clear, :signed_name, app.current_user_id(),
                    (now() AT TIME ZONE :time_zone)::date + :days, :status)
        """),
        {
            "tenant_id": context.tenant_id,
            "client_id": context.client_id,
            "form_key": form.key,
            "locale": body.locale,
            "answers": json.dumps(answers, ensure_ascii=False),
            "statement": form.statement[body.locale],
            "all_clear": all_clear,
            "signed_name": body.signed_name,
            "time_zone": time_zone,
            "days": form.validity_days,
            "status": "valid" if all_clear else "needs_review",
        },
    )
    return _my_health(db, context.client_id, body.locale)


class ClientHealth(BaseModel):
    state: HealthState
    declarations: list[Declaration] = Field(description="Newest first")


@router.get("/clients/{client_id}/health-declarations")
def client_health_declarations(client_id: UUID, context: ReadDep) -> ClientHealth:
    db = context.session
    exists = db.execute(
        text("SELECT 1 FROM app.clients WHERE id = :id"), {"id": client_id}
    ).scalar()
    if exists is None:
        raise not_found()
    rows = db.execute(
        text(f"""
            SELECT {DECLARATION_COLUMNS} FROM app.health_declarations
            WHERE client_id = :id ORDER BY signed_at DESC LIMIT 20
        """),
        {"id": client_id},
    ).mappings()
    return ClientHealth(
        state=health_state(db, client_id),
        declarations=[Declaration.model_validate(dict(row)) for row in rows],
    )


@router.post("/health-declarations/{declaration_id}/review")
def review_health_declaration(declaration_id: UUID, body: Review, context: WriteDep) -> Declaration:
    """Approves or rejects a declaration that answered "yes" to a question."""
    db = context.session
    current = db.execute(
        text("SELECT status FROM app.health_declarations WHERE id = :id FOR UPDATE"),
        {"id": declaration_id},
    ).scalar()
    if current is None:
        raise not_found()
    if current != "needs_review":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="not_awaiting_review")
    row = (
        db.execute(
            text(f"""
                UPDATE app.health_declarations
                SET status = :status, reviewed_by = app.current_user_id(), reviewed_at = now(),
                    review_note = :note
                WHERE id = :id
                RETURNING {DECLARATION_COLUMNS}
            """),
            {
                "status": "approved" if body.approve else "rejected",
                "note": (body.note or "").strip() or None,
                "id": declaration_id,
            },
        )
        .mappings()
        .one()
    )
    return Declaration.model_validate(dict(row))
