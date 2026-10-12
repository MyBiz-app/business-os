"""Shared paging for list endpoints: `limit` (default 50, at most 200) and `offset`."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

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
