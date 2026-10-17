"""Per-business isolation for background jobs (go-live GL14).

A job walks over many businesses. Each business is worked on inside its own savepoint, so one
that fails (bad data, a broken provider) is rolled back alone and counted, and every other
business still gets its turn. `app.jobs.run_job` reads the counts and records them in
app.job_runs (succeeded, failed)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Connection

logger = logging.getLogger(__name__)

TALLY_KEY = "job_tally"
LISTED_FAILURES = 5  # business ids named in a run's result; the count is always complete


@dataclass
class Tally:
    ok: set[UUID] = field(default_factory=set)
    failed: dict[UUID, str] = field(default_factory=dict)

    @property
    def succeeded(self) -> int:
        return len(self.ok - self.failed.keys())

    def summary(self) -> str:
        if not self.failed:
            return ""
        ids = ", ".join(str(tenant) for tenant in list(self.failed)[:LISTED_FAILURES])
        return f"failed businesses: {len(self.failed)} ({ids})"


def start_tally(conn: Connection) -> Tally:
    tally = conn.info[TALLY_KEY] = Tally()
    return tally


@contextmanager
def tenant_scope(conn: Connection, tenant_id: UUID) -> Iterator[None]:
    """Runs the block for one business in a savepoint. An error rolls that business back,
    is logged and counted; it does not reach the caller."""
    tally = conn.info.setdefault(TALLY_KEY, Tally())
    try:
        with conn.begin_nested():
            yield
    except Exception as error:  # any provider or data error stays with this business
        tally.failed[tenant_id] = f"{type(error).__name__}: {error}"[:300]
        logger.exception("job failed for business %s", tenant_id)
    else:
        tally.ok.add(tenant_id)
