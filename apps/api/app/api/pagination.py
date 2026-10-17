"""Shared paging for list endpoints: `limit` (default 50, at most 200) and `offset`; keyset
(`after` cursor) for the lists that grow without end."""

import base64
import json
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass(frozen=True)
class Page:
    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Rows per page")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, le=100_000, description="Rows to skip")] = 0,
) -> Page:
    return Page(limit=limit, offset=offset)


PageDep = Annotated[Page, Depends(page_params)]


def wide_page_params(
    limit: Annotated[int, Query(ge=1, le=1000, description="Rows per page")] = 500,
    offset: Annotated[int, Query(ge=0, le=100_000, description="Rows to skip")] = 0,
) -> Page:
    return Page(limit=limit, offset=offset)


# For lists a screen shows whole (a week of shifts, a class roster): the default is high enough
# that a normal view is one page, but the list can no longer grow without bound.
WidePageDep = Annotated[Page, Depends(wide_page_params)]


# --- Keyset paging ----------------------------------------------------------------------------
# For lists that grow without end and are read newest first (notifications, receipts, orders,
# documents, a client's bookings). The next page starts after the last row seen, by the sort key,
# so it costs the same on page 500 as on page 1 and does not shift when rows are added meanwhile.
# `offset` keeps working beside it on the endpoints that had it.

NEXT_CURSOR_HEADER = "X-Next-Cursor"


@dataclass(frozen=True)
class KeysetPage:
    limit: int
    offset: int
    after: list[str] | None  # the sort key of the last row seen, as strings

    @property
    def fetch(self) -> int:
        """Rows to read: one more than a page, to know whether another page exists."""
        return self.limit + 1


def encode_cursor(*key: object) -> str:
    raw = json.dumps([str(part) for part in key], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> list[str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        key = json.loads(base64.urlsafe_b64decode(padded.encode()))
        if isinstance(key, list) and key and all(isinstance(part, str) for part in key):
            return key
    except ValueError:
        pass
    raise HTTPException(status_code=422, detail="invalid_cursor")


def keyset_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Rows per page")] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0, le=100_000, description="Rows to skip")] = 0,
    after: Annotated[
        str | None, Query(max_length=400, description="`next_cursor` of the previous page")
    ] = None,
) -> KeysetPage:
    return KeysetPage(
        limit=limit, offset=0 if after else offset, after=decode_cursor(after) if after else None
    )


KeysetDep = Annotated[KeysetPage, Depends(keyset_params)]


def full_page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Rows per page")] = MAX_LIMIT,
    offset: Annotated[int, Query(ge=0, le=100_000, description="Rows to skip")] = 0,
) -> Page:
    return Page(limit=limit, offset=offset)


# For lists a screen shows whole (a client's documents, a folder's files): up to 200 rows in one
# page by default, and further pages by `offset` beyond that.
FullPageDep = Annotated[Page, Depends(full_page_params)]
