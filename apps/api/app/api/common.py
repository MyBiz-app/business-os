"""Small helpers shared by the tenant-scoped CRUD endpoints."""

from typing import Any

from fastapi import HTTPException, status


def blank_to_none(value: object) -> object:
    """Treats empty or whitespace-only strings from forms as "not provided"."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


def set_clause(changes: dict[str, Any]) -> str:
    """SET clause for an UPDATE. Keys must come from a Pydantic model's fields, never from
    user input, because they become column names."""
    assignments = [f"{column} = :{column}" for column in changes]
    return ", ".join([*assignments, "updated_at = now()"])
