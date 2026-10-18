"""The job registry, the locked runner with its run records, alerts and the command line."""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, Engine, create_engine, event, text

from app.commerce.billing import bill_businesses
from app.commerce.dunning import run_dunning
from app.core.brand import NAME
from app.core.config import get_settings
from app.core.tenant_scope import Tally, start_tally
from app.jobs.base import LOCK_PREFIX
from app.jobs.outbound import (
    issue_documents,
    move_files,
    notify_payslips,
    notify_shifts,
    publish_shifts,
    remind_payroll_job,
    run_ai_tasks,
    send_announcements,
    send_messages,
    send_notification_emails,
    sync_social,
)
from app.jobs.retention import delete_closed_businesses, purge_expired
from app.jobs.schedule import (
    extend_series,
    follow_up_leads,
    message_reminders,
    remind_plans,
    remind_sessions,
)
from app.messaging.alerts import AlertResult, alert_team
from app.messaging.email import (
    sender_from_settings,
)
from app.messaging.push import push_sender_from_settings
from app.messaging.whatsapp_ai import answer_inbox
from app.secrets_rotation import rotate_secrets

JOBS = {
    "extend-series": extend_series,
    "remind-sessions": remind_sessions,
    "remind-plans": remind_plans,
    "send-emails": send_notification_emails,
    "notify-shifts": notify_shifts,
    "remind-payroll": remind_payroll_job,
    "notify-payslips": notify_payslips,
    "message-reminders": message_reminders,
    "follow-up-leads": follow_up_leads,
    "purge-expired": purge_expired,
    "delete-closed-businesses": delete_closed_businesses,
    "bill-businesses": bill_businesses,
    "dunning": run_dunning,
    "publish-shifts": publish_shifts,
    "send-messages": send_messages,
    "send-announcements": send_announcements,
    "answer-whatsapp": answer_inbox,
    "issue-documents": issue_documents,
    "move-files": move_files,
    "run-ai-tasks": run_ai_tasks,
    "sync-social": sync_social,
    "rotate-secrets": rotate_secrets,
}

# Jobs that only report unless told `--apply`.
APPLY_JOBS = (delete_closed_businesses, rotate_secrets)

# How often each scheduled job must succeed, in hours: the schedule plus slack for a delayed
# run (GitHub's scheduler can start a run late). check-jobs reports a job as late after that.
DAILY = [
    "extend-series",
    "remind-sessions",
    "remind-plans",
    "remind-payroll",
    "bill-businesses",
    "dunning",
    "message-reminders",
    "follow-up-leads",
    "purge-expired",
    "delete-closed-businesses",
    "send-messages",
    "issue-documents",
    "sync-social",
]
HOURLY = [
    "publish-shifts",
    "send-emails",
    "notify-shifts",
    "send-announcements",
    "notify-payslips",
]
# GitHub's free scheduler throttles "hourly" crons on staging to a run every 1-6 hours (observed
# gaps up to ~6h), so an hourly job is late only after 8 hours without a success.
MAX_HOURS = {**{job: 27 for job in DAILY}, **{job: 8 for job in HOURLY}}
# Jobs whose staging workflow runs only once an email provider is set: they count as late only
# after they have run at least once.
OPTIONAL = {"send-emails", "notify-shifts"}


JOBS_ROLE = "app_jobs"


def jobs_engine(database_url: str, role: str | None = JOBS_ROLE) -> Engine:
    """An engine whose every connection runs as the least-privilege jobs role."""
    engine = create_engine(database_url)
    if role:

        @event.listens_for(engine, "connect")
        def _use_jobs_role(dbapi_connection, _record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute(f'SET ROLE "{role}"')
            cursor.close()
            dbapi_connection.commit()

    return engine


def run_job(engine: Engine, name: str, apply: bool = False) -> object:
    """Runs one job in its own transaction and records the run in app.job_runs, failed runs
    included (the record is written apart from the job, so a rollback doesn't lose it).

    A job never runs twice at once: it holds an advisory lock for its whole run, and a second
    start (a delayed cron overlapping the next one) records itself as skipped and returns. The
    run also records how many businesses were handled and how many failed (see tenant_scope)."""
    with engine.connect() as lock:
        got = lock.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
            {"key": f"{LOCK_PREFIX}{name}"},
        ).scalar_one()
        lock.commit()  # the lock belongs to the session, not to this transaction
        if not got:
            return _record_skip(engine, name)
        try:
            return _run_locked(engine, name, apply)
        finally:
            lock.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                {"key": f"{LOCK_PREFIX}{name}"},
            )
            lock.commit()


def _record_skip(engine: Engine, name: str) -> str:
    result = "skipped: the previous run of this job is still going"
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app.job_runs (job, finished_at, ok, result)
                VALUES (:job, now(), false, :result)
            """),
            {"job": name, "result": result},
        )
    return result


def _run_locked(engine: Engine, name: str, apply: bool) -> object:
    with engine.begin() as conn:
        run_id = conn.execute(
            text("INSERT INTO app.job_runs (job) VALUES (:job) RETURNING id"), {"job": name}
        ).scalar_one()
    ok, result, tally = False, None, Tally()
    try:
        with engine.begin() as conn:
            tally = start_tally(conn)
            job = JOBS[name]
            result = job(conn, apply=apply) if job in APPLY_JOBS else job(conn)
        ok = True
        return result
    except Exception as error:
        result = f"{type(error).__name__}: {error}"
        _alert_failure(engine, name, run_id, result)
        raise
    finally:
        recorded = str(result)
        if tally.failed:
            recorded = f"{recorded} | {tally.summary()}"
            print(f"{name}: {tally.summary()}", file=sys.stderr)
        with engine.begin() as conn:
            conn.execute(
                text("""
                UPDATE app.job_runs
                SET finished_at = now(), ok = :ok, result = :result,
                    succeeded = :succeeded, failed = :failed
                WHERE id = :id
            """),
                {
                    "id": run_id,
                    "ok": ok,
                    "result": recorded[:2000],
                    "succeeded": tally.succeeded,
                    "failed": len(tally.failed),
                },
            )


def notify_team(engine: Engine, title: str, body: str) -> AlertResult:
    """Alerts the MyBiz owners (push, then email). Never raises: a broken alert channel must not
    hide the failure that is being reported, which is also in the logs and the job runs."""
    try:
        sender = sender_from_settings()
    except SystemExit:  # a provider without its key
        sender = None
    try:
        with engine.begin() as conn:
            return alert_team(conn, title, body, push_sender_from_settings(), sender)
    except Exception as error:
        print(f"alert not sent: {type(error).__name__}: {error}", file=sys.stderr)
        return AlertResult()


def _alert_failure(engine: Engine, name: str, run_id: int, error: str) -> None:
    """Alerts when a job starts failing, once: a job that was already failing on its previous
    run does not alert again (the daily check-jobs reminds while it stays broken)."""
    try:
        with engine.connect() as conn:
            previous_ok = conn.execute(
                text("""
                    SELECT ok FROM app.job_runs
                    WHERE job = :job AND id < :id AND finished_at IS NOT NULL
                    ORDER BY id DESC LIMIT 1
                """),
                {"job": name, "id": run_id},
            ).scalar()
    except Exception:
        previous_ok = None
    if previous_ok is False:
        return
    notify_team(
        engine,
        f"{NAME} job failed: {name}",
        f"{name} failed on {get_settings().environment}.\n\n{error[:300]}",
    )


def late_jobs(conn: Connection, now: datetime | None = None) -> list[dict]:
    """The scheduled jobs whose last successful run is older than they allow (or never ran)."""
    now = now or datetime.now(UTC)
    last = dict(
        conn.execute(
            text("SELECT job, max(finished_at) FROM app.job_runs WHERE ok GROUP BY job")
        ).all()
    )
    return [
        {"job": job, "last_ok": last.get(job), "max_hours": hours}
        for job, hours in MAX_HOURS.items()
        if (last.get(job) is None and job not in OPTIONAL)
        or (last.get(job) is not None and now - last[job] > timedelta(hours=hours))
    ]


def run_group(engine: Engine, names: list[str]) -> list[str]:
    """Runs jobs one after another; a failure is recorded and the rest still run.
    Returns the names of the jobs that failed."""
    failed = []
    for name in names:
        try:
            print(f"{name}: {run_job(engine, name)}")
        except Exception as error:
            print(f"{name}: FAILED {type(error).__name__}: {error}", file=sys.stderr)
            failed.append(name)
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a background job.")
    parser.add_argument(
        "job", choices=[*JOBS, "run-daily", "run-hourly", "check-jobs", "test-alert"]
    )
    parser.add_argument("--database-url", default=None, help="Defaults to API_DATABASE_URL")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Really change data (delete-closed-businesses, rotate-secrets: a report without it)",
    )
    args = parser.parse_args()
    settings = get_settings()
    engine = jobs_engine(args.database_url or settings.database_url, settings.jobs_db_role)
    if args.job == "check-jobs":
        with engine.connect() as conn:
            late = late_jobs(conn)
        for item in late:
            last = item["last_ok"].isoformat() if item["last_ok"] else "never"
            # The ::error:: prefix shows as an annotation on the GitHub run.
            print(
                f"::error::{item['job']} is late: last success {last}, "
                f"expected every {item['max_hours']}h at most"
            )
        print(f"check-jobs: {len(late)} late of {len(MAX_HOURS)}")
        if late:
            names = ", ".join(item["job"] for item in late)
            sent = notify_team(
                engine,
                f"{NAME}: {len(late)} background job(s) late",
                f"Late on {get_settings().environment}: {names}.",
            )
            print(f"alert: {sent.pushed} push, {sent.emailed} email, {sent.recipients} owners")
        sys.exit(1 if late else 0)
    if args.job == "test-alert":
        sent = notify_team(
            engine,
            f"{NAME} test alert",
            f"If this reached your phone, alerts work ({get_settings().environment}).",
        )
        print(f"test-alert: {sent.pushed} push, {sent.emailed} email, {sent.recipients} owners")
        sys.exit(0 if sent.pushed or sent.emailed else 1)
    if args.job in ("run-daily", "run-hourly"):
        failed = run_group(engine, DAILY if args.job == "run-daily" else HOURLY)
        sys.exit(1 if failed else 0)
    print(f"{args.job}: {run_job(engine, args.job, apply=args.apply)}")


if __name__ == "__main__":
    main()
