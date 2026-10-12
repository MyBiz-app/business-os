"""Job heartbeats: every background job run is recorded, so a late or failing job is noticed.

`app.jobs` writes a row when a job starts and completes it when the job ends (ok or not).
`python -m app.jobs check-jobs` compares each scheduled job's last successful run with how often
it should run, and fails when one is late; a scheduled workflow runs it and GitHub emails the
failure. MyBiz's own table: RLS with no policy and no grant, so the API role cannot reach it.

Revision ID: 0075
Revises: 0074
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0075"
down_revision: str | None = "0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.job_runs (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            job text NOT NULL,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            ok boolean,
            result text,
            CHECK ((finished_at IS NULL) = (ok IS NULL))
        )
    """)
    op.execute("CREATE INDEX job_runs_job_idx ON app.job_runs (job, started_at DESC)")
    op.execute("ALTER TABLE app.job_runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP TABLE app.job_runs")
