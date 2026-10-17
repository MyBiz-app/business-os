"""Background jobs, run on a schedule (see .github/workflows/jobs-staging.yml).

    uv run python -m app.jobs extend-series [--database-url URL]
    uv run python -m app.jobs remind-sessions
    uv run python -m app.jobs remind-plans
    uv run python -m app.jobs send-emails     (needs API_EMAIL_PROVIDER; see app/messaging/email.py)
    uv run python -m app.jobs message-reminders (WhatsApp copies of today's reminders, simulated)
    uv run python -m app.jobs bill-businesses (simulated platform billing; app/commerce/billing.py)
    uv run python -m app.jobs dunning         (unpaid MyBiz invoices: reminders, read-only, hold)
    uv run python -m app.jobs notify-shifts    (emails staff new and edited published shifts)
    uv run python -m app.jobs publish-shifts  (hourly: the shifts roster goes out on schedule)
    uv run python -m app.jobs send-messages   (the outbox, through each business's provider)
    uv run python -m app.jobs send-announcements (the broadcast center: email, push, pop-ups)
    uv run python -m app.jobs answer-whatsapp (AI replies to clients' WhatsApp messages; idle
                                               until a real WhatsApp provider fills the inbox)
    uv run python -m app.jobs issue-documents (receipts to each business's invoicing provider)
    uv run python -m app.jobs delete-closed-businesses [--apply] (dry run unless --apply)
    uv run python -m app.jobs sync-social     (reads the numbers of connected social accounts)
    uv run python -m app.jobs move-files      (documents kept in the database → the object store)
    uv run python -m app.jobs rotate-secrets [--apply] (re-encrypts with the newest key; manual)
    uv run python -m app.jobs run-daily       (every daily job in turn, for a cron service)
    uv run python -m app.jobs run-hourly      (every hourly job in turn)
    uv run python -m app.jobs check-jobs      (fails when a scheduled job is late, and alerts the
                                               MyBiz owners' phones and email)
    uv run python -m app.jobs test-alert      (sends a test alert, to check the phones receive it)

Every run is recorded in app.job_runs (started, finished, ok, result), so a job that stopped
running or keeps failing is noticed by check-jobs (.github/workflows/check-jobs-staging.yml).

Jobs run with the migration (owner) connection, across all businesses, so they must only do
system work that needs no user's permission.

Where the code lives: `schedule.py`, `retention.py`, `outbound.py` (the jobs) and `runner.py`
(registry, locking, run records, alerts and the command line)."""

from app.jobs.base import HORIZON_DAYS as HORIZON_DAYS
from app.jobs.base import LOCK_PREFIX as LOCK_PREFIX
from app.jobs.outbound import _publish_moment as _publish_moment
from app.jobs.outbound import issue_documents as issue_documents
from app.jobs.outbound import move_files as move_files
from app.jobs.outbound import notify_shifts as notify_shifts
from app.jobs.outbound import publish_shifts as publish_shifts
from app.jobs.outbound import run_ai_tasks as run_ai_tasks
from app.jobs.outbound import send_announcements as send_announcements
from app.jobs.outbound import send_messages as send_messages
from app.jobs.outbound import send_notification_emails as send_notification_emails
from app.jobs.outbound import sync_social as sync_social
from app.jobs.retention import delete_closed_businesses as delete_closed_businesses
from app.jobs.retention import purge_expired as purge_expired
from app.jobs.retention import purge_expired_exports as purge_expired_exports
from app.jobs.runner import APPLY_JOBS as APPLY_JOBS
from app.jobs.runner import DAILY as DAILY
from app.jobs.runner import HOURLY as HOURLY
from app.jobs.runner import JOBS as JOBS
from app.jobs.runner import MAX_HOURS as MAX_HOURS
from app.jobs.runner import OPTIONAL as OPTIONAL
from app.jobs.runner import late_jobs as late_jobs
from app.jobs.runner import main as main
from app.jobs.runner import notify_team as notify_team
from app.jobs.runner import run_group as run_group
from app.jobs.runner import run_job as run_job
from app.jobs.schedule import extend_series as extend_series
from app.jobs.schedule import follow_up_leads as follow_up_leads
from app.jobs.schedule import message_reminders as message_reminders
from app.jobs.schedule import remind_plans as remind_plans
from app.jobs.schedule import remind_sessions as remind_sessions
