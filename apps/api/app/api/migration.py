"""Moving an existing business onto the platform (round 6, M1).

A move is a session: the owner confirms the right to transfer the data, uploads the files from
the old system, checks what each file holds and which column is which field, looks at a dry run
(exactly what an import would create), then imports. Each import is a batch that can be undone
for 14 days. The files stay in the imports folder of the files area for 30 days."""

import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.ai import budget
from app.ai.agents import member_role_keys
from app.ai.gateway import (
    LLMProvider,
    ProviderBusy,
    ProviderUnavailable,
    credits,
    get_provider,
)
from app.api.assistant import _month_start
from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.catalog.importing import ImportFileError
from app.core.permissions import Permission
from app.files import store_file, system_folder_id
from app.files.content import detect_import_type
from app.migration.ai_mapping import ask, merge
from app.migration.fields import (
    FIELDS,
    Kind,
    guess_kind,
    suggest_mapping,
    valid_mapping,
)
from app.migration.formats import read_any
from app.migration.mover import (
    MAX_FILE_BYTES,
    MAX_MOVE_BYTES,
    LoadedFile,
    Mover,
    MoveReport,
)
from app.migration.templates import match_template

router = APIRouter(prefix="/migration", tags=["migration"])

ManageDep = Annotated[TenantContext, Depends(require(Permission.MIGRATION_MANAGE))]
ProviderDep = Annotated[LLMProvider | None, Depends(get_provider)]

# Model calls for column maps in one move, so a stuck page cannot run up the AI bill.
MAX_AI_MAPS_PER_MOVE = 20


def _bad_request(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=code)


class MigrationSessionCreate(BaseModel):
    origin: str = Field(min_length=1, max_length=60, description="Where the business comes from")
    rights_confirmed: bool = Field(description="The owner may transfer this data (must be true)")


class MigrationColumnOut(BaseModel):
    name: str
    example: str


class MigrationFileOut(BaseModel):
    id: UUID
    filename: str
    kind: Kind | None
    columns: list[MigrationColumnOut]
    mapping: list[str | None]
    rows: int
    fields: list[str] = Field(description="The fields a column can be mapped to, for this kind")


class MigrationFileUpdate(BaseModel):
    kind: Kind | None = None
    mapping: list[str | None] | None = Field(
        default=None, description="A field (or null) per column; suggested when left out"
    )


class MigrationBatchOut(BaseModel):
    id: UUID
    status: str
    counts: dict[str, int]
    created_at: datetime
    undo_until: datetime
    undone_at: datetime | None
    can_undo: bool


class MigrationSessionOut(BaseModel):
    id: UUID
    origin: str
    status: str
    created_at: datetime
    files: list[MigrationFileOut]
    batches: list[MigrationBatchOut]


class MigrationUndoRequest(BaseModel):
    include_edited: bool = Field(
        default=False, description="Also remove records that were edited after the import"
    )


class MigrationUndoReport(BaseModel):
    removed: dict[str, int]
    kept: dict[str, int] = Field(description="Records left: edited, or other data depends on them")


def _file_out(row: Any) -> MigrationFileOut:
    return MigrationFileOut(
        id=row.id,
        filename=row.filename,
        kind=row.kind,
        columns=[MigrationColumnOut(**column) for column in row.headers],
        mapping=row.mapping,
        rows=row.row_count,
        fields=list(FIELDS[row.kind]) if row.kind else [],
    )


def _session_out(context: TenantContext, session_id: UUID) -> MigrationSessionOut:
    db = context.session
    head = db.execute(
        text("SELECT id, origin, status, created_at FROM app.import_sessions WHERE id = :id"),
        {"id": session_id},
    ).first()
    if head is None:
        raise not_found()
    files = db.execute(
        text("""
            SELECT id, filename, kind, headers, mapping, row_count FROM app.import_files
            WHERE session_id = :id ORDER BY created_at
        """),
        {"id": session_id},
    ).all()
    batches = db.execute(
        text("""
            SELECT id, status, counts, created_at, undo_until, undone_at,
                   (status = 'done' AND undo_until > now()) AS can_undo
            FROM app.import_batches WHERE session_id = :id ORDER BY created_at DESC
        """),
        {"id": session_id},
    ).all()
    return MigrationSessionOut(
        id=head.id,
        origin=head.origin,
        status=head.status,
        created_at=head.created_at,
        files=[_file_out(file) for file in files],
        batches=[
            MigrationBatchOut.model_validate(batch, from_attributes=True) for batch in batches
        ],
    )


def _draft_session(context: TenantContext, session_id: UUID, *, lock: bool = False) -> None:
    query = (
        "SELECT status FROM app.import_sessions WHERE id = :id FOR UPDATE"
        if lock
        else "SELECT status FROM app.import_sessions WHERE id = :id"
    )
    row = context.session.execute(text(query), {"id": session_id}).first()
    if row is None:
        raise not_found()
    if row.status != "draft":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="session_closed")


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_move_session(body: MigrationSessionCreate, context: ManageDep) -> MigrationSessionOut:
    if not body.rights_confirmed:
        raise _bad_request("rights_not_confirmed")
    session_id = context.session.execute(
        text("""
            INSERT INTO app.import_sessions (tenant_id, origin, created_by)
            VALUES (:t, :origin, app.current_user_id()) RETURNING id
        """),
        {"t": context.tenant_id, "origin": body.origin.strip()},
    ).scalar_one()
    return _session_out(context, session_id)


@router.get("/sessions")
def list_move_sessions(context: ManageDep) -> list[MigrationSessionOut]:
    ids = context.session.execute(
        text("SELECT id FROM app.import_sessions ORDER BY created_at DESC LIMIT 20")
    ).scalars()
    return [_session_out(context, session_id) for session_id in list(ids)]


@router.get("/sessions/{session_id}")
def get_move_session(session_id: UUID, context: ManageDep) -> MigrationSessionOut:
    return _session_out(context, session_id)


@router.post("/sessions/{session_id}/files", status_code=status.HTTP_201_CREATED)
def add_move_file(session_id: UUID, file: UploadFile, context: ManageDep) -> MigrationFileOut:
    _draft_session(context, session_id)
    data = file.file.read(MAX_FILE_BYTES + 1)
    filename = file.filename or "file"
    try:
        time_zone = context.session.execute(
            text("SELECT time_zone FROM app.tenants WHERE id = app.current_tenant_id()")
        ).scalar_one()
        table = read_any(data, filename, MAX_FILE_BYTES, time_zone)
    except ImportFileError as error:
        raise _bad_request(error.code) from error
    db = context.session
    used = db.execute(
        text("""
            SELECT coalesce(sum(f.size), 0) FROM app.import_files i
            JOIN app.business_files f ON f.id = i.file_id WHERE i.session_id = :id
        """),
        {"id": session_id},
    ).scalar_one()
    if used + len(data) > MAX_MOVE_BYTES:
        raise _bad_request("move_too_large")
    headers = table[0]
    kind: Kind | None
    known = match_template(headers)  # a saved map for a known system, before any guessing
    if known:
        kind, mapping = known[0].kind, known[1]
    else:
        kind = guess_kind(headers)
        mapping = suggest_mapping(kind, headers) if kind else [None] * len(headers)
    stored = store_file(
        db,
        context.tenant_id,
        system_folder_id(db, context.tenant_id, "imports"),
        name=filename,
        content=data,
        content_type=detect_import_type(data),
    )
    row = db.execute(
        text("""
            INSERT INTO app.import_files
                (tenant_id, session_id, file_id, filename, kind, headers, mapping, row_count)
            VALUES (:t, :session, :file, :name, :kind, CAST(:headers AS jsonb),
                    CAST(:mapping AS jsonb), :rows)
            RETURNING id, filename, kind, headers, mapping, row_count
        """),
        {
            "t": context.tenant_id,
            "session": session_id,
            "file": stored["id"],
            "name": filename[:200],
            "kind": kind,
            "headers": json.dumps(
                [
                    {"name": name, "example": next((r[i] for r in table[1:] if r[i]), "")[:80]}
                    for i, name in enumerate(headers)
                ],
                ensure_ascii=False,
            ),
            "mapping": json.dumps(mapping),
            "rows": len(table) - 1,
        },
    ).one()
    return _file_out(row)


@router.put("/sessions/{session_id}/files/{file_id}")
def update_move_file(
    session_id: UUID, file_id: UUID, body: MigrationFileUpdate, context: ManageDep
) -> MigrationFileOut:
    _draft_session(context, session_id)
    row = context.session.execute(
        text("""
            SELECT id, filename, kind, headers, mapping, row_count FROM app.import_files
            WHERE id = :id AND session_id = :session
        """),
        {"id": file_id, "session": session_id},
    ).first()
    if row is None:
        raise not_found()
    kind = body.kind or row.kind
    if kind is None:
        raise _bad_request("kind_required")
    names = [column["name"] for column in row.headers]
    if body.mapping is not None:
        mapping = body.mapping
    elif kind == row.kind:
        mapping = row.mapping
    else:
        mapping = suggest_mapping(kind, names)
    if not valid_mapping(kind, names, mapping):
        raise _bad_request("invalid_mapping")
    updated = context.session.execute(
        text("""
            UPDATE app.import_files SET kind = :kind, mapping = CAST(:mapping AS jsonb)
            WHERE id = :id
            RETURNING id, filename, kind, headers, mapping, row_count
        """),
        {"kind": kind, "mapping": json.dumps(mapping), "id": file_id},
    ).one()
    return _file_out(updated)


class MigrationAiMapOut(BaseModel):
    file: MigrationFileOut
    confidence: list[float | None] = Field(description="0 to 1 per column; null when unmapped")
    source: list[str | None] = Field(description='Per column: "name", "ai" or null')
    credits: float = Field(description="AI credits this suggestion used")


def _check_ai_budget(context: TenantContext, provider: LLMProvider) -> None:
    """The same soft monthly limits as the assistant. Demo answers cost nothing."""
    if getattr(provider, "model", None) == "demo":
        return
    db = context.session
    month_start = _month_start(db)
    if budget.over_limit(db, month_start):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ai_limit_reached")
    user_id = db.execute(text("SELECT app.current_user_id()")).scalar_one()
    if budget.over_person_limit(db, user_id, member_role_keys(db, context.role), month_start):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ai_user_limit_reached")
    if budget.over_day_pace(db, user_id, context.role):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ai_daily_pace_reached")


@router.post("/sessions/{session_id}/files/{file_id}/ai-map")
def ai_map_file(
    session_id: UUID, file_id: UUID, context: ManageDep, provider: ProviderDep
) -> MigrationAiMapOut:
    """Ask the AI for the columns the names alone did not explain (and the kind, if unknown).
    It sees headers and one hidden example per column, never the file; it costs credits from the
    monthly AI allowance. Columns already recognized are kept; the owner still checks the map."""
    _draft_session(context, session_id)
    db = context.session
    row = db.execute(
        text("""
            SELECT id, filename, kind, headers, mapping, row_count FROM app.import_files
            WHERE id = :id AND session_id = :session
        """),
        {"id": file_id, "session": session_id},
    ).first()
    if row is None:
        raise not_found()
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ai_not_configured"
        )
    _check_ai_budget(context, provider)
    ref = f"import_session:{session_id}"
    asked = db.execute(
        text("""
            SELECT count(*) FROM app.usage_events
            WHERE meter = 'ai_credits' AND source_ref = :ref
        """),
        {"ref": ref},
    ).scalar_one()
    if asked >= MAX_AI_MAPS_PER_MOVE:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="ai_map_limit")
    columns = row.headers[:60]
    if len(row.headers) > 60:
        raise _bad_request("too_many_columns")
    try:
        answer, response = ask(provider, columns, row.kind)
    except ProviderBusy as error:
        raise HTTPException(status_code=429, detail="ai_busy") from error
    except ProviderUnavailable as error:
        raise HTTPException(status_code=502, detail="ai_unavailable") from error
    cost = credits(response.model, response.usage)
    db.execute(
        text("""
            INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref)
            VALUES (:t, 'ai_credits', :quantity, CAST(:details AS jsonb), :ref)
        """),
        {
            "t": context.tenant_id,
            "quantity": cost,
            "details": json.dumps(
                {
                    "model": response.model,
                    "channel": "migration",
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            ),
            "ref": ref,
        },
    )
    suggestion = merge(columns, row.kind, row.mapping, answer)
    updated = db.execute(
        text("""
            UPDATE app.import_files SET kind = :kind, mapping = CAST(:mapping AS jsonb)
            WHERE id = :id
            RETURNING id, filename, kind, headers, mapping, row_count
        """),
        {"kind": suggestion.kind, "mapping": json.dumps(suggestion.mapping), "id": file_id},
    ).one()
    return MigrationAiMapOut(
        file=_file_out(updated),
        confidence=suggestion.confidence,
        source=suggestion.source,
        credits=cost,
    )


@router.delete("/sessions/{session_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_move_file(session_id: UUID, file_id: UUID, context: ManageDep) -> None:
    _draft_session(context, session_id)
    gone = context.session.execute(
        text("""
            DELETE FROM app.import_files WHERE id = :id AND session_id = :session
            RETURNING file_id
        """),
        {"id": file_id, "session": session_id},
    ).first()
    if gone is None:
        raise not_found()
    if gone.file_id:  # the uploaded copy goes with it
        context.session.execute(
            text("DELETE FROM app.business_files WHERE id = :id"), {"id": gone.file_id}
        )


def _move(context: TenantContext, session_id: UUID, *, commit: bool) -> MoveReport:
    _draft_session(context, session_id, lock=commit)
    db = context.session
    rows = db.execute(
        text("""
            SELECT id, file_id, filename, kind, mapping FROM app.import_files
            WHERE session_id = :id ORDER BY created_at
        """),
        {"id": session_id},
    ).all()
    if not rows:
        raise _bad_request("no_files")
    if commit and any(row.kind is None for row in rows):
        raise _bad_request("unmapped_file")
    files = [LoadedFile(r.id, r.file_id, r.filename, r.kind, r.mapping) for r in rows]
    mover = Mover(db, context.tenant_id, session_id, context.role)
    # The dry run is the real run inside a savepoint that is rolled back.
    savepoint = db.begin_nested()
    try:
        reports = mover.run(files)
        if commit and not mover.items:
            raise _bad_request("nothing_to_import")
    except BaseException:
        savepoint.rollback()
        raise
    if not commit:
        savepoint.rollback()
        return MoveReport(
            files=reports, committed=False, batch_id=None, undo_until=None, invitations=[]
        )
    savepoint.commit()
    undo_until = db.execute(
        text("SELECT undo_until FROM app.import_batches WHERE id = :id"), {"id": mover.batch_id}
    ).scalar_one()
    db.execute(
        text(
            "UPDATE app.import_sessions SET status = 'imported', updated_at = now() WHERE id = :id"
        ),
        {"id": session_id},
    )
    db.execute(
        text("""
            INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
            VALUES (:t, 'user', app.current_user_id(), 'migration.import', CAST(:details AS jsonb))
        """),
        {
            "t": context.tenant_id,
            "details": json.dumps(
                {
                    "batch": str(mover.batch_id),
                    "created": {r.kind: r.ready for r in reports if r.kind},
                },
                ensure_ascii=False,
            ),
        },
    )
    return MoveReport(
        files=reports,
        committed=True,
        batch_id=mover.batch_id,
        undo_until=undo_until,
        invitations=mover.invitations,
    )


@router.post("/sessions/{session_id}/preview")
def preview_move(session_id: UUID, context: ManageDep) -> MoveReport:
    return _move(context, session_id, commit=False)


@router.post("/sessions/{session_id}/import")
def run_move_import(session_id: UUID, context: ManageDep) -> MoveReport:
    return _move(context, session_id, commit=True)


def _undo(
    context: TenantContext, batch_id: UUID, include_edited: bool, *, commit: bool
) -> MigrationUndoReport:
    db = context.session
    batch = db.execute(
        text("""
            SELECT status, undo_until > now() AS open FROM app.import_batches WHERE id = :id
            FOR UPDATE
        """),
        {"id": batch_id},
    ).first()
    if batch is None:
        raise not_found()
    if batch.status != "done" or not batch.open:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="undo_closed")
    savepoint = db.begin_nested()
    result = db.execute(
        text("SELECT app.undo_import_batch(:id, :edited)"),
        {"id": batch_id, "edited": include_edited},
    ).scalar_one()
    if commit:
        savepoint.commit()
        db.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
                VALUES (:t, 'user', app.current_user_id(), 'migration.undo',
                        CAST(:details AS jsonb))
            """),
            {"t": context.tenant_id, "details": json.dumps({"batch": str(batch_id), **result})},
        )
    else:
        savepoint.rollback()
    return MigrationUndoReport(removed=result["removed"], kept=result["kept"])


@router.post("/batches/{batch_id}/undo-preview")
def undo_move_preview(
    batch_id: UUID, body: MigrationUndoRequest, context: ManageDep
) -> MigrationUndoReport:
    return _undo(context, batch_id, body.include_edited, commit=False)


@router.post("/batches/{batch_id}/undo")
def undo_move_batch(
    batch_id: UUID, body: MigrationUndoRequest, context: ManageDep
) -> MigrationUndoReport:
    return _undo(context, batch_id, body.include_edited, commit=True)
