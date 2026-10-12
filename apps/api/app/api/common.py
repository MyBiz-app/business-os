"""Small helpers shared by the tenant-scoped CRUD endpoints."""

import re
from collections.abc import Collection, Iterable
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def blank_to_none(value: object) -> object:
    """Treats empty or whitespace-only strings from forms as "not provided"."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


_IDENTIFIER = re.compile(r"[a-z_][a-z0-9_]*")


def check_columns(names: Iterable[str], allowed: Collection[str]) -> None:
    """Refuses any name that is not an allowed column, before it is put into SQL text.
    `allowed` is usually a Pydantic model's `model_fields`, plus columns the code adds."""
    for name in names:
        if name not in allowed or not _IDENTIFIER.fullmatch(name):
            raise ValueError(f"unsafe SQL identifier: {name!r}")


def set_clause(
    changes: dict[str, Any],
    allowed: Collection[str],
    casts: dict[str, str] | None = None,
    touch: bool = True,
) -> str:
    """SET clause for an UPDATE. Every key must be in `allowed`, because keys become column
    names. `casts` gives a column's SQL type (jsonb); `touch` also sets updated_at."""
    casts = casts or {}
    check_columns(changes, allowed)
    assignments = [
        f"{column} = CAST(:{column} AS {casts[column]})" if column in casts
        else f"{column} = :{column}"
        for column in changes
    ]  # fmt: skip
    if touch:
        assignments.append("updated_at = now()")
    return ", ".join(assignments)


def ensure_not_erased(db: Session, client_id: UUID) -> None:
    """Erased clients (privacy requests) keep their history but get nothing new."""
    erased = db.execute(
        text("SELECT erased_at IS NOT NULL FROM app.clients WHERE id = :id"), {"id": client_id}
    ).scalar()
    if erased:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="client_erased")


class RemoveResult(BaseModel):
    result: Literal["deleted", "archived"] = Field(
        description="`archived` when sold or scheduled items still refer to it: it is only hidden"
    )


def delete_or_archive(session: Session, table: str, row_id: UUID) -> RemoveResult:
    """Delete a catalog row nothing refers to; otherwise just deactivate it, so history stays.
    `table` is a literal chosen by the caller, never user input."""
    try:
        with session.begin_nested():
            deleted = session.execute(
                text(f"DELETE FROM app.{table} WHERE id = :id"), {"id": row_id}
            ).rowcount
    except IntegrityError:
        archived = session.execute(
            text(f"UPDATE app.{table} SET active = false WHERE id = :id"), {"id": row_id}
        ).rowcount
        if not archived:
            raise not_found() from None
        return RemoveResult(result="archived")
    if not deleted:
        raise not_found()
    return RemoveResult(result="deleted")
