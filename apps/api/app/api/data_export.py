"""Exporting the whole business (go-live, GL8): the owner asks, a ZIP of CSVs and files is built
in the background, and a link valid for 24 hours is emailed to them. Owners only, with a
second sign-in step once that is required (app/core/mfa.py); both the
request and the download are written to the audit log."""

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import AnonymousSessionDep, TenantContext, get_tenant_context
from app.core.business_export import build_archive
from app.core.config import get_settings
from app.core.db import EngineDep, open_session
from app.core.logging import log
from app.core.mfa import mfa_required, sensitive_action_needs_mfa
from app.core.signed_links import sign, verify
from app.messaging.email import Email, sender_from_settings
from app.providers.choice import choose
from app.providers.storage import StorageError, tenant_key

router = APIRouter(prefix="/tenants/current/data-exports", tags=["settings"])
public_router = APIRouter(tags=["settings"])

LINK_HOURS = 24


def require_owner(context: Annotated[TenantContext, Depends(get_tenant_context)]) -> TenantContext:
    if context.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_only")
    if sensitive_action_needs_mfa(context.aal):
        raise mfa_required()
    return context


OwnerDep = Annotated[TenantContext, Depends(require_owner)]


class DataExport(BaseModel):
    id: UUID
    status: str = Field(description="building, ready or failed")
    created_at: str
    expires_at: str | None = Field(description="After this the file is deleted")
    size: int | None
    file_count: int | None


class ExportLink(BaseModel):
    url: str = Field(description="Downloads the ZIP without signing in, for 24 hours")


def _model(row: dict) -> DataExport:
    return DataExport(
        id=row["id"],
        status=row["status"],
        created_at=row["created_at"].isoformat(),
        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
        size=row["size"],
        file_count=row["file_count"],
    )


def _audit(db: Session, action: str, export_id: UUID) -> None:
    db.execute(
        text("""
            INSERT INTO app.audit_log
                (tenant_id, actor_type, actor_id, action, entity_type, entity_id)
            VALUES (app.current_tenant_id(), 'user', app.current_user_id(), :action,
                    'data_export', :id)
        """),
        {"action": action, "id": export_id},
    )


def download_url(tenant_id: UUID, export_id: UUID) -> str:
    token = sign(f"export:{tenant_id}:{export_id}", ttl=LINK_HOURS * 3600)
    return f"{get_settings().api_url}/public/data-exports/{token}"


@router.get("")
def list_exports(context: OwnerDep) -> list[DataExport]:
    rows = context.session.execute(
        text("""
            SELECT id, status, created_at, expires_at, size, file_count
            FROM app.data_exports ORDER BY created_at DESC LIMIT 10
        """)
    ).mappings()
    return [_model(dict(row)) for row in rows]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def request_export(context: OwnerDep, background: BackgroundTasks, engine: EngineDep) -> DataExport:
    """Starts building the ZIP. One at a time; ask again once it is ready or has failed."""
    db = context.session
    running = db.execute(
        text("""
            SELECT 1 FROM app.data_exports
            WHERE status = 'building' AND created_at > now() - interval '30 minutes'
        """)
    ).first()
    if running:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="export_in_progress")
    row = (
        db.execute(
            text("""
                INSERT INTO app.data_exports (tenant_id, requested_by)
                VALUES (app.current_tenant_id(), app.current_user_id())
                RETURNING id, status, created_at, expires_at, size, file_count
            """)
        )
        .mappings()
        .one()
    )
    _audit(db, "business.export_requested", row["id"])
    user_id = db.execute(text("SELECT app.current_user_id()")).scalar_one()
    db.commit()  # the background task reads the row, so it must be committed first
    background.add_task(build_export, engine, context.tenant_id, user_id, row["id"])
    return _model(dict(row))


@router.post("/{export_id}/link")
def new_link(export_id: UUID, context: OwnerDep) -> ExportLink:
    """A fresh 24-hour link for a ready export (the emailed one may have expired)."""
    row = context.session.execute(
        text("""
            SELECT 1 FROM app.data_exports
            WHERE id = :id AND status = 'ready' AND expires_at > now()
        """),
        {"id": export_id},
    ).first()
    if row is None:
        raise not_found()
    _audit(context.session, "business.export_link", export_id)
    return ExportLink(url=download_url(context.tenant_id, export_id))


def build_export(engine: Engine, tenant_id: UUID, user_id: UUID, export_id: UUID) -> None:
    """Runs after the response: builds the ZIP as the owner, keeps it 24 hours and emails the
    link. A failure marks the export failed (the owner sees it and can ask again)."""
    session = open_session(engine, user_id, tenant_id)
    try:
        try:
            archive, files = build_archive(session, tenant_id)
            key, content = None, archive
            storage = choose(session, None, "storage").instance
            if not storage.in_database:
                key = tenant_key(tenant_id, "exports", uuid4())
                storage.put(key, archive, "application/zip")
                content = None
            session.execute(
                text("""
                    UPDATE app.data_exports
                    SET status = 'ready', content = :content, storage_key = :key, size = :size,
                        file_count = :files, ready_at = now(),
                        expires_at = now() + make_interval(hours => :hours)
                    WHERE id = :id
                """),
                {
                    "content": content,
                    "key": key,
                    "size": len(archive),
                    "files": files,
                    "hours": LINK_HOURS,
                    "id": export_id,
                },
            )
            _audit(session, "business.exported", export_id)
            session.commit()
        except Exception as error:
            session.rollback()
            log(logging.ERROR, "business export failed", error=type(error).__name__)
            session.execute(
                text("UPDATE app.data_exports SET status = 'failed' WHERE id = :id"),
                {"id": export_id},
            )
            session.commit()
            return
        _email_link(session, tenant_id, export_id)
    finally:
        session.close()


def _email_link(session: Session, tenant_id: UUID, export_id: UUID) -> None:
    sender = sender_from_settings()
    if sender is None:
        return
    row = (
        session.execute(
            text("""
                SELECT u.email, t.name, t.locale FROM app.data_exports e
                JOIN app.users u ON u.id = e.requested_by
                JOIN app.tenants t ON t.id = e.tenant_id WHERE e.id = :id
            """),
            {"id": export_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return
    url = download_url(tenant_id, export_id)
    if row["locale"] == "en":
        subject, body = (
            f"Your {row['name']} data export is ready",
            f"Your export is ready.\n\nDownload it here (the link works for {LINK_HOURS} hours):"
            f"\n{url}",
        )
    else:
        subject, body = (
            f"ייצוא הנתונים של {row['name']} מוכן",
            f"הייצוא מוכן.\n\nמורידים כאן (הקישור תקף {LINK_HOURS} שעות):\n{url}",
        )
    try:
        sender.send(Email(to=row["email"], subject=subject, text=body, locale=row["locale"]))
    except Exception as error:  # the link is also in the app; a mail failure is not the export's
        log(logging.WARNING, "export email failed", error=type(error).__name__)


@public_router.get("/public/data-exports/{token}")
def download_export(token: str, session: AnonymousSessionDep) -> Response:
    subject = verify(token)
    if subject is None or not subject.startswith("export:"):
        raise not_found()
    _, tenant_id, export_id = subject.split(":")
    row = (
        session.execute(
            text("SELECT * FROM app.data_export(:id, :tenant)"),
            {"id": export_id, "tenant": tenant_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    if row["content"] is not None:
        payload = bytes(row["content"])
    else:
        try:
            payload = choose(session, None, "storage").instance.get(row["storage_key"])
        except (StorageError, LookupError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="storage_unavailable"
            ) from error
    return Response(
        payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="business-data.zip"',
            "Cache-Control": "no-store",
        },
    )
