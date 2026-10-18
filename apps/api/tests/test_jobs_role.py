"""Background jobs run as a role that cannot change the schema (migration 0128)."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import ProgrammingError

from app.jobs import JOBS, jobs_engine, run_job


@pytest.fixture
def as_jobs(engine: Engine) -> Engine:
    return jobs_engine(engine.url.render_as_string(hide_password=False))


def test_the_runner_connects_as_the_jobs_role(as_jobs: Engine) -> None:
    with as_jobs.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar_one() == "app_jobs"


def test_the_role_works_across_businesses_but_cannot_change_the_schema(as_jobs: Engine) -> None:
    with as_jobs.connect() as conn:
        # Rows are readable and writable without a business set (row-level security is bypassed).
        conn.execute(text("SELECT count(*) FROM app.tenants"))
        conn.execute(text("UPDATE app.tenants SET name = name"))
        conn.commit()
        for statement in (
            "CREATE TABLE app.should_not_exist (id int)",
            "ALTER TABLE app.tenants ADD COLUMN should_not_exist int",
            "DROP TABLE app.users",
            "TRUNCATE app.audit_log",
            "ALTER TABLE app.tenants DISABLE ROW LEVEL SECURITY",
            (
                "CREATE TRIGGER t BEFORE INSERT ON app.tenants "
                "EXECUTE FUNCTION app.check_reporting_line()"
            ),
        ):
            with pytest.raises(ProgrammingError):
                conn.execute(text(statement))
            conn.rollback()


def test_every_table_is_covered_by_the_role(engine: Engine) -> None:
    with engine.connect() as conn:
        missing = (
            conn.execute(
                text("""
                SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND c.relkind IN ('r', 'p') AND NOT (
                    has_table_privilege('app_jobs', c.oid, 'SELECT')
                    AND has_table_privilege('app_jobs', c.oid, 'INSERT')
                    AND has_table_privilege('app_jobs', c.oid, 'UPDATE')
                    AND has_table_privilege('app_jobs', c.oid, 'DELETE'))
            """)
            )
            .scalars()
            .all()
        )
    assert missing == [], f"app_jobs lacks rights on {missing}"


def test_the_role_is_the_only_way_jobs_connect_unless_switched_off(engine: Engine) -> None:
    plain = jobs_engine(engine.url.render_as_string(hide_password=False), role="")
    with plain.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar_one() != "app_jobs"


@pytest.mark.parametrize("name", list(JOBS))
def test_every_job_runs_as_the_jobs_role(as_jobs: Engine, name: str) -> None:
    run_job(as_jobs, name)
