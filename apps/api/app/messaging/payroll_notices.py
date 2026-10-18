"""Pushes about payroll (round 6, P4): the owner's reminder on the 1st and 5th of the month while
last month's run is not approved, and the "your payslip is ready" push to each person when a run
is approved. Both go to people's phones only; nothing is emailed or sent to a bank.

The reminder is a daily job (`remind-payroll`); each reminder day is recorded in the audit log, so
running the job twice in one day sends once."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, text

from app.messaging.email import MESSAGES_DIR, _fill, load_messages
from app.messaging.push import PushSender, push_to_user

REMINDER_DAYS = (1, 5)
REMINDER_ACTION = "payroll.reminder_sent"


def _month_label(period: Any) -> str:
    return f"{period.month:02d}/{period.year}"


def _text(
    cache: dict[str, dict[str, Any]], messages_dir: Path, locale: str | None, key: str, **values
) -> tuple[str, str]:
    code = locale if locale in ("he", "en") else "en"
    if code not in cache:
        cache[code] = load_messages(code, messages_dir)
    entry = cache[code][key]
    return _fill(entry["title"], values), _fill(entry["body"], values)


def remind_payroll(
    conn: Connection,
    push: PushSender | None,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
) -> dict[str, int]:
    """Reminds the owners of businesses with the payroll module whose run for last month is not
    approved, on the 1st and 5th of the month (business-local dates). Returns the businesses
    reminded and the owners pushed."""
    now = now or datetime.now(UTC)
    rows = (
        conn.execute(
            text("""
                SELECT t.id AS tenant_id, t.name AS business, t.time_zone,
                       (CAST(:now AS timestamptz) AT TIME ZONE t.time_zone)::date AS today
                FROM app.tenants t
                WHERE t.closed_at IS NULL
                  AND EXISTS (SELECT 1 FROM app.tenant_modules m
                              WHERE m.tenant_id = t.id AND m.module_key = 'payroll')
            """),
            {"now": now},
        )
        .mappings()
        .all()
    )
    cache: dict[str, dict[str, Any]] = {}
    businesses = pushed = 0
    for row in rows:
        today = row["today"]
        if today.day not in REMINDER_DAYS:
            continue
        period = (today.replace(day=1) - timedelta(days=1)).replace(day=1)  # last month
        approved = conn.execute(
            text("""
                SELECT EXISTS (SELECT 1 FROM app.payroll_runs
                               WHERE tenant_id = :t AND period = :p AND stage = 'approved')
            """),
            {"t": row["tenant_id"], "p": period},
        ).scalar_one()
        if approved:
            continue
        claimed = conn.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, action, entity_type, details)
                SELECT :t, 'system', :action, 'payroll_run',
                       jsonb_build_object('period', CAST(:p AS text), 'day', CAST(:d AS int))
                WHERE NOT EXISTS (
                    SELECT 1 FROM app.audit_log
                    WHERE tenant_id = :t AND action = :action
                      AND details->>'period' = CAST(:p AS text)
                      AND (details->>'day')::int = :d
                )
                RETURNING id
            """),
            {"t": row["tenant_id"], "action": REMINDER_ACTION, "p": period, "d": today.day},
        ).scalar()
        if claimed is None or push is None:
            continue
        businesses += 1
        owners = conn.execute(
            text("""
                SELECT m.user_id, u.locale
                FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
                WHERE m.tenant_id = :t AND m.role = 'owner'
            """),
            {"t": row["tenant_id"]},
        ).all()
        for owner in owners:
            title, body = _text(
                cache,
                messages_dir,
                owner.locale,
                "payrollReminder",
                business=row["business"],
                month=_month_label(period),
            )
            pushed += push_to_user(conn, push, owner.user_id, title, body)
    return {"businesses": businesses, "pushed": pushed}


PAYSLIPS_ACTION = "payroll.payslips_notified"
PAYSLIP_WINDOW_DAYS = 3


def notify_payslips_ready(
    conn: Connection,
    push: PushSender | None,
    now: datetime | None = None,
    messages_dir: Path = MESSAGES_DIR,
) -> dict[str, int]:
    """Pushes "your payslip is ready" to everyone with a line in a run approved in the last few
    days, once per run (the audit log remembers). A person without a registered phone simply
    finds the payslip in the app. Returns the runs announced and the phones that accepted."""
    now = now or datetime.now(UTC)
    runs = (
        conn.execute(
            text("""
                SELECT r.id, r.tenant_id, r.period, t.name AS business, t.locale
                FROM app.payroll_runs r JOIN app.tenants t ON t.id = r.tenant_id
                WHERE r.stage = 'approved' AND r.approved_at > :since AND t.closed_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM app.audit_log a
                      WHERE a.tenant_id = r.tenant_id AND a.action = :action
                        AND a.entity_id = r.id
                  )
            """),
            {"since": now - timedelta(days=PAYSLIP_WINDOW_DAYS), "action": PAYSLIPS_ACTION},
        )
        .mappings()
        .all()
    )
    cache: dict[str, dict[str, Any]] = {}
    announced = pushed = 0
    for run in runs:
        conn.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, action, entity_type, entity_id)
                VALUES (:t, 'system', :action, 'payroll_run', :run)
            """),
            {"t": run["tenant_id"], "action": PAYSLIPS_ACTION, "run": run["id"]},
        )
        announced += 1
        people = conn.execute(
            text("""
                SELECT l.user_id, COALESCE(u.locale, :locale) AS locale
                FROM app.payroll_run_lines l JOIN app.users u ON u.id = l.user_id
                WHERE l.run_id = :run
            """),
            {"run": run["id"], "locale": run["locale"]},
        ).all()
        for person in people:
            title, body = _text(
                cache,
                messages_dir,
                person.locale,
                "payslipReady",
                business=run["business"],
                month=_month_label(run["period"]),
            )
            pushed += push is not None and push_to_user(conn, push, person.user_id, title, body)
    return {"runs": announced, "pushed": pushed}
